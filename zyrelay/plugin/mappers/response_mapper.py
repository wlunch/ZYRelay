from __future__ import annotations

from typing import Any

from zyrelay.app.models import UOMPackage

from ..contracts import (
    ArtifactReference,
    OutputDetail,
    PluginOperation,
    PluginOptions,
    PluginResult,
    PluginSummary,
    PluginWarning,
)


class PluginResponseMapper:
    def map_result(
        self,
        package: UOMPackage,
        *,
        operation: PluginOperation,
        options: PluginOptions,
        execution_id: str,
        artifacts: list[ArtifactReference],
    ) -> PluginResult:
        raw = package.model_dump(mode="json", exclude_none=False)
        artifact_uri = artifacts[0].uri if artifacts else None
        sanitized = self.sanitize(raw, artifact_uri=artifact_uri)
        document = sanitized["source"]
        blocks = sanitized["mom"]["blocks"]
        som = sanitized["som"]
        business_objects = sanitized["bom"]["business_objects"]
        conventions = som.get("code_conventions", [])

        if operation == PluginOperation.EXTRACT_CONTRACT:
            conventions = []
        summary = PluginSummary(
            document_id=document.get("document_id"),
            status=document.get("status", "completed"),
            block_count=len(blocks),
            mention_count=len(som["mentions"]),
            convention_count=len(conventions),
            business_object_count=len(business_objects),
            warning_count=len(sanitized["processing"]["warnings"]),
        )
        result = PluginResult(
            document={
                "document_id": document.get("document_id"),
                "status": document.get("status"),
            },
            artifacts=artifacts,
            summary=summary,
        )
        if options.output_detail == OutputDetail.SUMMARY:
            return result

        result.document = document
        if options.extract_labels:
            result.mentions = som["mentions"]
        if options.build_semantic_index:
            result.semantic_index = self._semantic_index_summary(som["semantic_index"])
        if options.extract_business_objects:
            result.business_objects = business_objects
        if options.extract_code_conventions:
            result.code_conventions = conventions
        if (
            options.build_convention_index
            and operation != PluginOperation.EXTRACT_CONTRACT
        ):
            result.convention_index = som.get("convention_index", {})

        if options.output_detail == OutputDetail.FULL:
            result.blocks = blocks if options.extract_blocks else []
            result.labels = som["labels"] if options.extract_labels else []
            result.semantic_index = (
                som["semantic_index"] if options.build_semantic_index else {}
            )
            result.semantic_candidates = som["candidates"]
            result.uom_package = sanitized
        return result

    @classmethod
    def sanitize(cls, value: Any, *, artifact_uri: str | None) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                if key == "source_uri" and isinstance(item, str):
                    sanitized[key] = artifact_uri
                else:
                    sanitized[key] = cls.sanitize(item, artifact_uri=artifact_uri)
            return sanitized
        if isinstance(value, list):
            return [cls.sanitize(item, artifact_uri=artifact_uri) for item in value]
        return value

    @staticmethod
    def warnings(package: UOMPackage) -> list[PluginWarning]:
        result: list[PluginWarning] = []
        for warning in package.processing.warnings:
            lowered = warning.casefold()
            if "ocr" in lowered:
                code = "requires_ocr"
            elif "llm" in lowered and "失败" in warning:
                code = "llm_enrichment_failed"
            elif "分页" in warning or "布局" in warning:
                code = "unsupported_layout"
            else:
                code = "partial_extraction"
            result.append(
                PluginWarning(
                    code=code,
                    message=warning,
                    stage="processing",
                )
            )
        return result

    @staticmethod
    def _semantic_index_summary(index: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for label_code, bucket in index.items():
            documents = bucket.get("documents", {})
            result[label_code] = {
                "label_code": label_code,
                "document_count": len(documents),
                "occurrence_count": sum(len(items) for items in documents.values()),
            }
        return result
