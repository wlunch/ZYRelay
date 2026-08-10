from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from zyrelay.app.core.config import Settings
from zyrelay.app.models import UOMPackage
from zyrelay.app.pipeline.base import Pipeline
from zyrelay.app.pipeline.context import ProcessingContext
from zyrelay.app.pipeline.steps import (
    BuildBlocksStep,
    BuildConventionIndexStep,
    BuildConventionSectionsStep,
    BuildSemanticCandidatesStep,
    BuildSemanticIndexStep,
    BuildSemanticObjectsStep,
    BuildUOMPackageStep,
    ExtractConventionCandidatesStep,
    ExtractDocumentStep,
    LLMEnrichmentStep,
    MatchLabelsStep,
    NormalizeTextStep,
    SaveResultStep,
    ValidateConventionCandidatesStep,
    ValidateFileStep,
)
from zyrelay.app.storage import LocalStorage
from zyrelay.provenance import ProvenanceService


class DocumentService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.storage = LocalStorage(
            self.settings.data_root, keep_prepared=self.settings.keep_prepared
        )
        self.provenance = ProvenanceService(self.settings.data_root)

    def process(
        self, file_name: str, content: bytes, *, request_id: str | None = None
    ) -> tuple[str, str]:
        task_id = f"TASK-{uuid.uuid4().hex[:16].upper()}"
        request_id = request_id or f"REQ-{uuid.uuid4().hex[:16].upper()}"
        suffix = Path(file_name).suffix.lower()
        incoming_dir = self.settings.data_root / ".incoming"
        incoming_dir.mkdir(parents=True, exist_ok=True)
        fd, raw_path = tempfile.mkstemp(suffix=suffix, dir=incoming_dir)
        input_path = Path(raw_path)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            context = ProcessingContext(
                task_id=task_id,
                request_id=request_id,
                input_path=input_path,
                file_name=Path(file_name).name,
                file_bytes=content,
            )
            pipeline = Pipeline(
                [
                    ValidateFileStep(self.settings),
                    ExtractDocumentStep(),
                    BuildBlocksStep(),
                    NormalizeTextStep(),
                    MatchLabelsStep(self.settings),
                    BuildSemanticIndexStep(self.settings),
                    BuildSemanticCandidatesStep(self.settings),
                    LLMEnrichmentStep(self.settings),
                    BuildConventionSectionsStep(),
                    ExtractConventionCandidatesStep(self.settings),
                    ValidateConventionCandidatesStep(),
                    BuildConventionIndexStep(),
                    BuildSemanticObjectsStep(
                        ground_snapshot_id="GROUND-STANDALONE",
                        resource_plan_id="RPLAN-STANDALONE",
                    ),
                    BuildUOMPackageStep(self.settings),
                    SaveResultStep(self.storage),
                ]
            )
            context = pipeline.execute(context)
            if context.package is None or context.document is None:
                raise RuntimeError("pipeline did not produce a package")

            semantic_objects = []
            for item in context.semantic_objects:
                record = self.provenance.create_for_semantic_object(
                    item,
                    execution_id=task_id,
                    ground_selection_id="GROUND-STANDALONE",
                    ground_snapshot_id="GROUND-STANDALONE",
                    resource_plan_id="RPLAN-STANDALONE",
                    model_execution_ids=[],
                )
                semantic_objects.append(
                    item.model_copy(update={"provenance_id": record.provenance_id})
                )
            context.semantic_objects = semantic_objects
            context.package.semantic_objects.objects = semantic_objects

            # Build/save steps append their records after execution. Refresh the
            # persisted package so processing.steps is complete.
            context.package.processing.steps = context.steps
            context.package.processing.warnings = context.warnings
            context.package.processing.errors = context.errors
            self.storage.save_package(context.package)
            return context.document.document_id, task_id
        finally:
            input_path.unlink(missing_ok=True)

    def get_package(self, document_id: str) -> UOMPackage:
        return self.storage.load_package(document_id)

    def get_document(self, document_id: str):
        return self.get_package(document_id).source

    def get_blocks(self, document_id: str):
        return self.get_package(document_id).mom.blocks

    def get_mentions(self, document_id: str):
        return self.get_package(document_id).som.mentions

    def get_semantic_index(self, document_id: str):
        return self.get_package(document_id).som.semantic_index

    def get_semantic_objects(
        self,
        document_id: str,
        *,
        object_type: str | None = None,
        category: str | None = None,
        language: str | None = None,
        page: int | None = None,
    ):
        objects = self.get_package(document_id).semantic_objects.objects
        return [
            item
            for item in objects
            if (object_type is None or item.object_type.value == object_type)
            and (category is None or item.category == category)
            and (language is None or item.language == language)
            and (page is None or item.page == page)
        ]

    def export_semantic_objects(
        self, document_id: str, export_format: str
    ) -> dict[str, Any]:
        package = self.get_package(document_id)
        objects = [
            item.model_dump(mode="json", exclude_none=True)
            for item in package.semantic_objects.objects
        ]
        if export_format == "json":
            return {"document_id": document_id, "semantic_objects": objects}
        if export_format == "json-ld":
            return {
                "@context": {
                    "id": "@id",
                    "type": "@type",
                    "SemanticObject": "uom://semantic/SemanticObject",
                },
                "@id": f"uom://documents/{document_id}",
                "@graph": [
                    {"@id": item["object_id"], "@type": item["object_type"], **item}
                    for item in objects
                ],
            }
        if export_format == "graph-json":
            return {
                "document_id": document_id,
                "nodes": [
                    item for item in objects if item["object_type"] != "relation"
                ],
                "edges": [
                    {
                        "id": item["object_id"],
                        "type": item["name"],
                        "source": item.get("source_object_id"),
                        "target": item.get("target_object_id"),
                        "evidence_ids": item.get("evidence_ids", []),
                    }
                    for item in objects
                    if item["object_type"] == "relation"
                ],
            }
        raise ValueError("unsupported_semantic_export_format")

    def get_code_conventions(
        self,
        document_id: str,
        *,
        category: str | None = None,
        language: str | None = None,
        requirement_level: str | None = None,
        status: str | None = None,
    ):
        conventions = self.get_package(document_id).som.code_conventions
        return [
            convention
            for convention in conventions
            if (category is None or convention.category == category)
            and (
                language is None
                or language.casefold()
                in {item.casefold() for item in convention.language}
            )
            and (
                requirement_level is None
                or convention.requirement_level == requirement_level
            )
            and (status is None or convention.status == status)
        ]

    def get_convention_index(self, document_id: str):
        return self.get_package(document_id).som.convention_index

    def search_conventions(
        self,
        *,
        document_id: str | None = None,
        category: str | None = None,
        language: str | None = None,
        requirement_level: str | None = None,
        keyword: str | None = None,
        executable: bool | None = None,
    ) -> list[dict[str, Any]]:
        packages = (
            [self.get_package(document_id)]
            if document_id
            else self.storage.list_packages()
        )
        results: list[dict[str, Any]] = []
        for package in packages:
            for convention in package.som.code_conventions:
                if category and convention.category != category:
                    continue
                if language and language.casefold() not in {
                    item.casefold() for item in convention.language
                }:
                    continue
                if (
                    requirement_level
                    and convention.requirement_level != requirement_level
                ):
                    continue
                if keyword and keyword.casefold() not in (
                    f"{convention.title}\n{convention.description}".casefold()
                ):
                    continue
                if executable is not None and (
                    convention.rule_expression is None
                    or convention.rule_expression.executable != executable
                ):
                    continue
                results.append(convention.model_dump(mode="json"))
        return results

    def search(
        self,
        *,
        label_code: str,
        document_id: str | None = None,
        value: str | None = None,
    ) -> list[dict[str, Any]]:
        packages = (
            [self.get_package(document_id)]
            if document_id
            else self.storage.list_packages()
        )
        results: list[dict[str, Any]] = []
        for package in packages:
            bucket = package.som.semantic_index.get(label_code)
            if bucket is None:
                continue
            for doc_id, occurrences in bucket.documents.items():
                for occurrence in occurrences:
                    if (
                        value
                        and value.casefold()
                        not in occurrence.normalized_value.casefold()
                    ):
                        continue
                    results.append(
                        {
                            "label_code": label_code,
                            "document_id": doc_id,
                            **occurrence.model_dump(mode="json"),
                        }
                    )
        return results
