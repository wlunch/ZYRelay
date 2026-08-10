from __future__ import annotations

from dataclasses import replace
from time import perf_counter
from typing import Any

from zyrelay.app.models import UOMPackage

from .contracts import (
    OutputDetail,
    PluginError,
    PluginOperation,
    PluginRequest,
    PluginResponse,
    PluginResult,
    PluginStatus,
    PluginSummary,
    ValidationResult,
)
from .dependencies import PluginDependencies, create_default_dependencies
from .error_mapper import map_exception
from .execution_repository import PluginExecutionRecord
from .mappers import PluginRequestMapper, PluginResponseMapper
from .mappers.request_mapper import EXECUTION_ID


class DocIntelligencePlugin:
    def __init__(self, dependencies: PluginDependencies | None = None) -> None:
        self.dependencies = dependencies or create_default_dependencies()
        self.request_mapper = PluginRequestMapper(
            self.dependencies.config,
            self.dependencies.settings,
        )
        self.response_mapper = PluginResponseMapper()

    def get_manifest(self):
        return self.dependencies.manifest_provider.get()

    def get_capabilities(self):
        return self.dependencies.capabilities_provider.get()

    def validate(self, request: PluginRequest) -> ValidationResult:
        return self.request_mapper.validate(request)

    def execute(self, request: PluginRequest) -> PluginResponse:
        started_at = self.dependencies.clock()
        started = perf_counter()
        request_id = request.request_id or self.dependencies.id_generator("REQ")
        execution_id = (
            request.execution_id
            if request.execution_id and EXECUTION_ID.fullmatch(request.execution_id)
            else self.dependencies.id_generator("EXEC")
        )
        validation = self.validate(request)
        if not validation.valid:
            response = self._response(
                request=request,
                request_id=request_id,
                execution_id=execution_id,
                started_at=started_at,
                started=started,
                status=PluginStatus.FAILED,
                errors=validation.errors,
                warnings=validation.warnings,
            )
            self._save_execution(request, response, input_summary={})
            return response

        effective_options = self.request_mapper.effective_options(request.options)
        request = request.model_copy(update={"options": effective_options})

        if request.operation == PluginOperation.GET_CAPABILITIES:
            response = self._response(
                request=request,
                request_id=request_id,
                execution_id=execution_id,
                started_at=started_at,
                started=started,
                status=PluginStatus.COMPLETED,
                result=PluginResult(
                    document={
                        "capabilities": self.get_capabilities().model_dump(mode="json")
                    },
                    summary=PluginSummary(status="completed"),
                ),
                warnings=validation.warnings,
            )
            self._save_execution(request, response, input_summary={})
            return response

        try:
            if request.operation == PluginOperation.GET_UOM:
                assert request.input is not None
                service = self.dependencies.document_service
                package = service.get_package(request.input.document_id or "")
                input_summary = {
                    "document_id": request.input.document_id,
                    "source_type": "document",
                }
            else:
                mapped = self.request_mapper.map(request)
                input_summary = self.dependencies.execution_repository.input_summary(
                    file_name=mapped.file_name,
                    content_type=mapped.content_type,
                    content=mapped.content,
                    source_type=mapped.source_type,
                )
                if request.operation == PluginOperation.VALIDATE_DOCUMENT:
                    result = PluginResult(
                        document={
                            "file_name": mapped.file_name,
                            "content_type": mapped.content_type,
                            "size": len(mapped.content),
                            "valid": True,
                        },
                        summary=PluginSummary(status="completed"),
                    )
                    response = self._response(
                        request=request,
                        request_id=request_id,
                        execution_id=execution_id,
                        started_at=started_at,
                        started=started,
                        status=PluginStatus.COMPLETED,
                        result=result,
                        warnings=validation.warnings,
                    )
                    self._save_execution(request, response, input_summary=input_summary)
                    return response

                service = self._service_for(request)
                document_id, _ = service.process(
                    mapped.file_name,
                    mapped.content,
                    request_id=request_id,
                )
                package = service.get_package(document_id)

            artifacts = self._save_artifacts(execution_id, package)
            result = self.response_mapper.map_result(
                package,
                operation=request.operation,
                options=request.options,
                execution_id=execution_id,
                artifacts=artifacts,
            )
            warnings = [
                *validation.warnings,
                *self.response_mapper.warnings(package),
            ]
            status = (
                PluginStatus.PARTIAL
                if any(item.code == "llm_enrichment_failed" for item in warnings)
                else PluginStatus.COMPLETED
            )
            trace = (
                [step.model_dump(mode="json") for step in package.processing.steps]
                if request.options.output_detail == OutputDetail.FULL
                else []
            )
            response = self._response(
                request=request,
                request_id=request_id,
                execution_id=execution_id,
                started_at=started_at,
                started=started,
                status=status,
                result=result,
                artifacts=artifacts,
                warnings=warnings,
                trace=trace,
            )
            self._save_execution(request, response, input_summary=input_summary)
            return response
        except Exception as exc:
            response = self._response(
                request=request,
                request_id=request_id,
                execution_id=execution_id,
                started_at=started_at,
                started=started,
                status=PluginStatus.FAILED,
                errors=[map_exception(exc)],
                warnings=validation.warnings,
            )
            self._save_execution(request, response, input_summary={})
            return response

    def get_result(self, execution_id: str) -> PluginResponse:
        try:
            return self.dependencies.execution_repository.load_response(execution_id)
        except (FileNotFoundError, ValueError):
            now = self.dependencies.clock()
            manifest = self.get_manifest()
            return PluginResponse(
                request_id=self.dependencies.id_generator("REQ"),
                execution_id=(
                    execution_id
                    if EXECUTION_ID.fullmatch(execution_id)
                    else self.dependencies.id_generator("EXEC")
                ),
                plugin_id=manifest.plugin_id,
                plugin_version=manifest.version,
                api_version=manifest.api_version,
                operation=PluginOperation.PROCESS_DOCUMENT,
                status=PluginStatus.FAILED,
                started_at=now,
                completed_at=now,
                duration_ms=0,
                errors=[
                    PluginError(
                        code="result_not_found",
                        message="执行结果不存在",
                        stage="result",
                        retryable=False,
                    )
                ],
            )

    def _service_for(self, request: PluginRequest):
        options = request.options
        settings = replace(
            self.dependencies.settings,
            llm_enabled=options.enable_llm,
            fuzzy_enabled=options.enable_fuzzy_matching,
            keep_prepared=options.retain_intermediate,
        )
        if settings == self.dependencies.settings:
            return self.dependencies.document_service
        return self.dependencies.service_factory(settings)

    def _save_artifacts(self, execution_id: str, package: UOMPackage):
        safe_uom = self.response_mapper.sanitize(
            package.model_dump(mode="json", exclude_none=False),
            artifact_uri=f"plugin://executions/{execution_id}/uom",
        )
        return [
            self.dependencies.artifact_repository.save_json(
                execution_id,
                artifact_type="uom_package",
                file_name=f"{package.source.document_id}.uom.json",
                value=safe_uom,
                metadata={"document_id": package.source.document_id},
            )
        ]

    def _save_execution(
        self,
        request: PluginRequest,
        response: PluginResponse,
        *,
        input_summary: dict[str, Any],
    ) -> None:
        context = request.context
        safe_metadata = {
            key: value
            for key, value in request.metadata.items()
            if not key.startswith("_")
        }
        record = PluginExecutionRecord(
            execution_id=response.execution_id,
            request_id=response.request_id,
            plugin_id=response.plugin_id,
            plugin_version=response.plugin_version,
            operation=response.operation.value,
            input_summary=input_summary,
            options=request.options.model_dump(mode="json"),
            status=response.status,
            started_at=response.started_at,
            completed_at=response.completed_at,
            duration_ms=response.duration_ms,
            document_id=(
                response.result.summary.document_id
                if response.result and response.result.summary
                else None
            ),
            artifact_ids=[item.artifact_id for item in response.artifacts],
            warnings=response.warnings,
            errors=response.errors,
            trace_id=context.trace_id if context else None,
            metadata=safe_metadata,
        )
        self.dependencies.execution_repository.save(record, response)

    def _response(
        self,
        *,
        request: PluginRequest,
        request_id: str,
        execution_id: str,
        started_at,
        started: float,
        status: PluginStatus,
        result: PluginResult | None = None,
        artifacts=None,
        warnings=None,
        errors=None,
        trace=None,
    ) -> PluginResponse:
        manifest = self.get_manifest()
        completed_at = self.dependencies.clock()
        safe_metadata = {
            key: value
            for key, value in request.metadata.items()
            if not key.startswith("_")
        }
        if request.context is not None:
            safe_metadata["context"] = request.context.model_dump(mode="json")
        return PluginResponse(
            request_id=request_id,
            execution_id=execution_id,
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            api_version=manifest.api_version,
            operation=request.operation,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=(perf_counter() - started) * 1000,
            result=result,
            artifacts=artifacts or [],
            warnings=warnings or [],
            errors=errors or [],
            trace=trace or [],
            metadata=safe_metadata,
        )
