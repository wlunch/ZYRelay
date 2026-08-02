from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from zyrelay.app.core.config import load_yaml
from zyrelay.app.models import BlockType
from zyrelay.app.parsers import ParsedElement
from zyrelay.app.pipeline.base import Pipeline
from zyrelay.app.pipeline.context import ProcessingContext
from zyrelay.app.pipeline.steps import (
    BuildBlocksStep,
    BuildConventionIndexStep,
    BuildConventionSectionsStep,
    BuildSemanticCandidatesStep,
    BuildSemanticIndexStep,
    BuildUOMPackageStep,
    ExtractConventionCandidatesStep,
    LLMEnrichmentStep,
    MatchLabelsStep,
    NormalizeTextStep,
    SaveResultStep,
    ValidateConventionCandidatesStep,
    ValidateFileStep,
)
from zyrelay.app.storage import LocalStorage
from zyrelay.ground import GroundChooseService, GroundRepository
from zyrelay.provenance import ProvenanceService
from zyrelay.resources import ResourcePlanner, ResourceRegistry
from zyrelay.resources.models import OCRLine, OCRPageResult, ResourceRequest
from zyrelay.resources.pdf_render import render_pdf_pages

from .models import (
    ModelExecutionRecord,
    RelayExecution,
    RelayRequest,
    RelayStatus,
    StepRecord,
)


Value = TypeVar("Value")


class SimpleRelayPipeline:
    """Fixed Relay sequence; it deliberately is not a workflow engine."""

    def __init__(
        self,
        *,
        settings,
        ground_repository: GroundRepository,
        ground_chooser: GroundChooseService,
        resource_registry: ResourceRegistry,
        resource_planner: ResourcePlanner,
        provenance: ProvenanceService,
        model_execution_store,
    ) -> None:
        self.settings = settings
        self.storage = LocalStorage(settings.data_root, keep_prepared=settings.keep_prepared)
        self.ground_repository = ground_repository
        self.ground_chooser = ground_chooser
        self.resource_registry = resource_registry
        self.resource_planner = resource_planner
        self.provenance = provenance
        self.model_execution_store = model_execution_store

    def execute(self, request: RelayRequest, execution: RelayExecution):
        started = time.perf_counter()
        execution.status = RelayStatus.RUNNING
        content = self._read_input(request)
        suffix = Path(request.input.file_name).suffix.lower()
        incoming_dir = self.settings.data_root / ".incoming"
        work_dir = incoming_dir / execution.execution_id
        work_dir.mkdir(parents=True, exist_ok=True)
        fd, raw_path = tempfile.mkstemp(suffix=suffix, dir=work_dir)
        input_path = Path(raw_path)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            context = ProcessingContext(
                task_id=execution.execution_id,
                request_id=execution.request_id,
                input_path=input_path,
                file_name=Path(request.input.file_name).name,
                file_bytes=content,
            )
            self._run(execution, "create_execution", lambda: execution.execution_id)
            self._run(
                execution,
                "validate_input",
                lambda: ValidateFileStep(self.settings).execute(context),
                input_summary={"file_name": context.file_name, "size": len(content)},
            )
            if context.document is None:
                raise RuntimeError("validate_input 未生成 document")
            execution.document_id = context.document.document_id
            self._run(
                execution,
                "detect_file_type",
                lambda: context.document.file_type,
                output_summary={"file_type": context.document.file_type},
            )

            selection, profile, inherited = self._run(
                execution,
                "ground_choose",
                lambda: self.ground_chooser.choose(
                    execution_id=execution.execution_id,
                    enterprise_id=request.enterprise_id,
                    team_id=request.team_id,
                    project_id=request.project_id,
                    mode=request.mode.value,
                    document_type=context.document.file_type,
                    explicit_ground_profile_id=request.ground_profile_id,
                ),
            )
            execution.ground_selection_id = selection.selection_id
            snapshot = self._run(
                execution,
                "create_ground_snapshot",
                lambda: self.ground_repository.create_snapshot(
                    snapshot_id=f"GSNAP-{uuid.uuid4().hex[:16].upper()}",
                    execution_id=execution.execution_id,
                    profile=profile,
                    inherited=inherited,
                ),
            )
            execution.ground_snapshot_id = snapshot.snapshot_id
            plan = self._run(
                execution,
                "build_resource_plan",
                lambda: self.resource_planner.build(
                    execution_id=execution.execution_id,
                    enterprise_id=request.enterprise_id,
                    requested_profile_id=request.resource_profile_id,
                    recommended_profile_id=profile.resource_profile_id,
                ),
            )
            execution.resource_plan_id = plan.plan_id

            parser_capability = (
                "pdf_parser" if context.document.file_type == "pdf" else "docx_parser"
            )
            parser_id = plan.bindings[parser_capability]
            parser_response = self._run(
                execution,
                "parse_document",
                lambda: self.resource_registry.get(parser_id).execute(
                    ResourceRequest(
                        capability=parser_capability,
                        file_path=str(input_path),
                        document_type=context.document.file_type,
                    ),
                    context,
                ),
                resource_id=parser_id,
            )
            context.parsed_document = parser_response.payload
            context.warnings.extend(parser_response.warnings)
            parsed = context.parsed_document
            if parsed is None:
                raise RuntimeError("解析资源未返回 ParsedDocument")
            context.document.parser = parsed.parser
            context.document.parser_version = parsed.parser_version
            context.document.page_count = parsed.page_count
            context.document.requires_ocr = parsed.requires_ocr

            self._run(
                execution,
                "detect_ocr_requirement",
                lambda: parsed.requires_ocr,
                output_summary={"requires_ocr": parsed.requires_ocr},
            )
            if parsed.requires_ocr and context.document.file_type == "pdf":
                if not request.enable_ocr:
                    execution.warnings.append("OCR 已由请求显式关闭")
                else:
                    self._run_ocr(
                        execution,
                        plan.bindings["ocr"],
                        plan.fallback_bindings.get("ocr", []),
                        input_path,
                        work_dir,
                        context,
                    )
            elif request.enable_ocr:
                self._run(
                    execution,
                    "optional_ocr",
                    lambda: None,
                    output_summary={"skipped": "native_text_or_docx"},
                )

            layout_id = plan.bindings["layout"]
            self._run(
                execution,
                "detect_layout",
                lambda: self.resource_registry.get(layout_id).execute(
                    ResourceRequest(
                        capability="layout",
                        document_type=context.document.file_type,
                        options={"parsed_document": parsed},
                    ),
                    context,
                ),
                resource_id=layout_id,
            )

            core_settings = replace(self.settings, llm_enabled=False)
            if request.enable_llm:
                execution.warnings.append("Relay 打样流程未启用 LLM，已保持规则优先")
            self._run_core(execution, "build_blocks", BuildBlocksStep(), context)
            self._run_core(execution, "normalize_text", NormalizeTextStep(), context)
            self._run_core(
                execution,
                "run_existing_label_matching",
                MatchLabelsStep(core_settings),
                context,
            )
            self._run_core(
                execution,
                "build_semantic_index",
                BuildSemanticIndexStep(core_settings),
                context,
            )
            self._run_core(
                execution,
                "build_business_objects",
                BuildSemanticCandidatesStep(core_settings),
                context,
            )
            self._run_core(
                execution, "llm_gate", LLMEnrichmentStep(core_settings), context
            )
            self._run_core(
                execution,
                "build_convention_sections",
                BuildConventionSectionsStep(),
                context,
            )
            self._run_core(
                execution,
                "run_existing_convention_extraction",
                ExtractConventionCandidatesStep(core_settings),
                context,
                resource_id=plan.bindings["convention_classifier"],
            )
            self._run(
                execution,
                "validate_evidence",
                lambda: Pipeline([ValidateConventionCandidatesStep()]).execute(context),
                resource_id=plan.bindings["evidence_validator"],
                output_summary={"valid_conventions": len(context.code_conventions)},
            )
            self._run_core(
                execution,
                "build_convention_index",
                BuildConventionIndexStep(),
                context,
            )
            self._run(
                execution,
                "build_provenance",
                lambda: self._attach_provenance(
                    context,
                    execution,
                    selection.selection_id,
                    snapshot.snapshot_id,
                    plan.plan_id,
                ),
            )
            self._run(
                execution,
                "build_uom",
                lambda: Pipeline([BuildUOMPackageStep(core_settings)]).execute(context),
            )
            if context.package is None:
                raise RuntimeError("build_uom 未生成 UOM Package")
            context.package.processing.relay_execution_id = execution.execution_id
            context.package.processing.ground_selection_id = selection.selection_id
            context.package.processing.ground_snapshot_id = snapshot.snapshot_id
            context.package.processing.resource_plan_id = plan.plan_id
            context.package.processing.resolved_ground_hash = snapshot.resolved_hash
            context.package.processing.resource_plan_hash = plan.plan_hash
            context.package.processing.model_execution_ids = [
                item.model_execution_id for item in execution.model_executions
            ]
            self._run(
                execution,
                "save_artifacts",
                lambda: Pipeline([SaveResultStep(self.storage)]).execute(context),
                resource_id=plan.bindings["storage"],
            )
            context.package.processing.steps = context.steps
            context.package.processing.warnings = context.warnings
            context.package.processing.errors = context.errors
            self.storage.save_package(context.package)
            execution.warnings.extend(context.warnings)
            execution.metrics = {
                "total_duration_ms": (time.perf_counter() - started) * 1000,
                "pages_processed": context.document.page_count or 0,
                "blocks_generated": len(context.blocks),
                "conventions_generated": len(context.code_conventions),
            }
            execution.artifacts = [
                {
                    "artifact_type": "uom_package",
                    "uri": f"relay://executions/{execution.execution_id}/uom",
                    "document_id": context.document.document_id,
                }
            ]
            execution.status = (
                RelayStatus.PARTIAL
                if (
                    any(item.fallback_used for item in execution.model_executions)
                    or (parsed.requires_ocr and not request.enable_ocr)
                )
                else RelayStatus.COMPLETED
            )
            self._run(execution, "complete_execution", lambda: execution.status.value)
            return context.package, selection, snapshot, plan
        except Exception as exc:
            execution.status = RelayStatus.FAILED
            execution.errors.append(
                {
                    "error_code": getattr(exc, "error_code", "relay_execution_failed"),
                    "message": str(exc),
                }
            )
            raise
        finally:
            if self.settings.retain_ocr_intermediates:
                input_path.unlink(missing_ok=True)
            else:
                shutil.rmtree(work_dir, ignore_errors=True)
            execution.completed_at = datetime.now(timezone.utc)
            execution.duration_ms = (time.perf_counter() - started) * 1000
            execution.current_step = "complete_execution"

    def _run_ocr(
        self,
        execution,
        resource_id: str,
        fallback_resource_ids: list[str],
        path: Path,
        work_dir: Path,
        context,
    ) -> None:
        if context.parsed_document is None:
            raise RuntimeError("OCR requires a parsed document")
        page_numbers = [
            page.page_no
            for page in context.parsed_document.pages
            if not page.text.strip() and page.has_images
        ]
        if not page_numbers:
            execution.warnings.append("OCR Gate 未找到需要识别的图片型 PDF 页面")
            return
        ocr_config = load_yaml(self.settings.model_config).get("models", {}).get("paddleocr", {})
        dpi = int(ocr_config.get("dpi", 200))
        artifacts = self._run(
            execution,
            "render_ocr_pages",
            lambda: render_pdf_pages(
                path,
                page_numbers,
                work_dir / "ocr-pages",
                dpi=dpi,
                execution_id=execution.execution_id,
            ),
            input_summary={"page_numbers": page_numbers, "dpi": dpi},
        )
        public_artifacts = [
            {**artifact.public_metadata, "file_path": str(artifact.file_path)}
            for artifact in artifacts
        ]
        planned_model_execution_id = f"MEXEC-{uuid.uuid4().hex[:16].upper()}"
        response = self._run(
            execution,
            "optional_ocr",
            lambda: self.resource_registry.get(resource_id).execute(
                ResourceRequest(
                    capability="ocr",
                    file_path=str(path),
                    document_type="pdf",
                    options={
                        "page_artifacts": public_artifacts,
                        "model_execution_id": planned_model_execution_id,
                    },
                ),
                context,
            ),
            resource_id=resource_id,
        )
        if response.status != "completed" and resource_id != "noop-ocr":
            for fallback_id in fallback_resource_ids:
                if fallback_id == resource_id or not self.resource_registry.available(fallback_id):
                    continue
                execution.warnings.append(
                    f"OCR primary resource {resource_id} 不可用，已回退到 {fallback_id}"
                )
                response = self._run(
                    execution,
                    "optional_ocr_fallback",
                    lambda: self.resource_registry.get(fallback_id).execute(
                        ResourceRequest(
                            capability="ocr",
                            file_path=str(path),
                            document_type="pdf",
                            options={"page_artifacts": public_artifacts},
                        ),
                        context,
                    ),
                    resource_id=fallback_id,
                )
                resource_id = fallback_id
                break
        execution.warnings.extend(response.warnings)
        pages = response.payload if isinstance(response.payload, list) else []
        if pages and all(isinstance(item, OCRPageResult) for item in pages):
            self._apply_ocr_pages(context, pages, resource_id, ocr_config)
        elif pages and all(isinstance(item, OCRLine) for item in pages):
            # Compatibility for custom resources built against the 0.4 OCRLine
            # contract; production PaddleOCR always returns OCRPageResult.
            legacy_lines = list(pages)
            page_sizes = {
                page.page_no: (int(page.width or 0), int(page.height or 0))
                for page in context.parsed_document.pages
            }
            grouped: dict[int, list[OCRLine]] = {}
            for line in legacy_lines:
                grouped.setdefault(line.page_no, []).append(line)
            pages = [
                OCRPageResult(
                    page_no=page_no,
                    width=page_sizes.get(page_no, (0, 0))[0],
                    height=page_sizes.get(page_no, (0, 0))[1],
                    lines=group,
                    average_confidence=sum(line.confidence for line in group) / len(group),
                    resource_id=resource_id,
                    resource_version=self.resource_registry.get(resource_id).version,
                    model_execution_id=group[0].model_execution_id,
                )
                for page_no, group in grouped.items()
            ]
            self._apply_ocr_pages(context, pages, resource_id, ocr_config)
        lines = [line for page in pages if isinstance(page, OCRPageResult) for line in page.lines]
        if resource_id in {"paddleocr", "noop-ocr"}:
            model_id = response.metadata.get("model_execution_id") or planned_model_execution_id
            record = ModelExecutionRecord(
                model_execution_id=model_id,
                execution_id=execution.execution_id,
                step_name="optional_ocr",
                resource_id=resource_id,
                resource_version=str(
                    response.metadata.get("paddleocr_version")
                    or self.resource_registry.get(resource_id).version
                ),
                model_name="PaddleOCR" if resource_id == "paddleocr" else "NoOpOCR",
                model_version=response.metadata.get("model_version"),
                capability="ocr",
                input_references=[artifact["uri"] for artifact in public_artifacts],
                output_references=[
                    f"ocr_lines:{len(lines)}",
                    *[f"ocr_page:{page.page_no}" for page in pages if isinstance(page, OCRPageResult)],
                ],
                status=response.status,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=float(response.metadata.get("duration_ms", 0)),
                confidence_summary=self._confidence_summary(lines),
                fallback_used=resource_id == "noop-ocr" or response.status != "completed",
                warnings=response.warnings,
                details={
                    "device": response.metadata.get("device", "cpu"),
                    "paddleocr_version": response.metadata.get("paddleocr_version"),
                    "paddlepaddle_version": response.metadata.get("paddlepaddle_version"),
                    "model_load_ms": response.metadata.get("model_load_ms", 0.0),
                    "page_count": len(pages),
                    "line_count": len(lines),
                    "page_metrics": response.metadata.get("page_metrics", []),
                    "page_artifacts": [
                        {key: value for key, value in artifact.items() if key != "file_path"}
                        for artifact in public_artifacts
                    ],
                },
            )
            execution.model_executions.append(record)
            self.model_execution_store.save(record, record.model_execution_id)

    @staticmethod
    def _apply_ocr_pages(context, pages: list[OCRPageResult], resource_id: str, config: dict) -> None:
        lines = [line for page in pages for line in page.lines]
        resource_version = pages[0].resource_version if pages else "unknown"
        threshold = float(config.get("minimum_line_confidence", 0.5))
        context.parsed_document.elements = [
            ParsedElement(
                text=line.text,
                block_type=BlockType.PARAGRAPH,
                page_no=line.page_no,
                metadata={
                    "source_method": "ocr",
                    "resource_id": resource_id,
                    "resource_version": resource_version,
                    "model_execution_id": line.model_execution_id,
                    "ocr_confidence": line.confidence,
                    "bbox": line.bbox,
                    "polygon": line.polygon,
                    "page_no": line.page_no,
                    "reading_order": line.reading_order,
                    "low_confidence": line.confidence < threshold,
                },
            )
            for line in lines
            if line.text.strip()
        ]
        by_page: dict[int, list[str]] = {}
        for line in lines:
            by_page.setdefault(line.page_no, []).append(line.text)
        for page in context.parsed_document.pages:
            if page.page_no in by_page:
                page.text = "\n".join(by_page[page.page_no])
                page.text_source = "ocr"

    @staticmethod
    def _confidence_summary(lines: list[OCRLine]) -> dict[str, float]:
        if not lines:
            return {}
        values = [line.confidence for line in lines]
        return {"min": min(values), "max": max(values), "average": sum(values) / len(values)}

    @staticmethod
    def _read_input(request: RelayRequest) -> bytes:
        if request.input.file_path:
            return Path(request.input.file_path).expanduser().read_bytes()
        import base64

        return base64.b64decode(request.input.content_base64 or "", validate=True)

    def _attach_provenance(
        self,
        context,
        execution,
        selection_id: str,
        snapshot_id: str,
        plan_id: str,
    ) -> None:
        if context.document is None:
            raise RuntimeError("document is required for provenance")
        model_ids = [item.model_execution_id for item in execution.model_executions]
        updated = []
        for candidate in context.code_conventions:
            record = self.provenance.create_for_convention(
                candidate,
                execution_id=execution.execution_id,
                document_id=context.document.document_id,
                ground_selection_id=selection_id,
                ground_snapshot_id=snapshot_id,
                resource_plan_id=plan_id,
                model_execution_ids=model_ids,
                blocks=context.blocks,
                model_executions=execution.model_executions,
            )
            updated.append(candidate.model_copy(update={"provenance_id": record.provenance_id}))
        context.code_conventions = updated

    def _run(
        self,
        execution: RelayExecution,
        name: str,
        operation: Callable[[], Value],
        *,
        resource_id: str | None = None,
        input_summary: dict | None = None,
        output_summary: dict | None = None,
    ) -> Value:
        execution.current_step = name
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        try:
            result = operation()
        except Exception as exc:
            execution.steps.append(
                StepRecord(
                    step_name=name,
                    status="failed",
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    duration_ms=(time.perf_counter() - started) * 1000,
                    resource_id=resource_id,
                    input_summary=input_summary or {},
                    errors=[{"error_code": getattr(exc, "error_code", "unexpected_error"), "message": str(exc)}],
                )
            )
            raise
        execution.steps.append(
            StepRecord(
                step_name=name,
                status="completed",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(time.perf_counter() - started) * 1000,
                resource_id=resource_id,
                input_summary=input_summary or {},
                output_summary=output_summary or {},
            )
        )
        return result

    def _run_core(
        self,
        execution: RelayExecution,
        relay_step_name: str,
        step,
        context: ProcessingContext,
        *,
        resource_id: str | None = None,
    ) -> ProcessingContext:
        return self._run(
            execution,
            relay_step_name,
            lambda: Pipeline([step]).execute(context),
            resource_id=resource_id,
        )
