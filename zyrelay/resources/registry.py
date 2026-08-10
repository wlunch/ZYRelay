from __future__ import annotations

from zyrelay.app.core.config import Settings

from .auxiliary import (
    DocLayoutYOLOResource,
    FastTextLanguageResource,
    GLiNERResource,
    HeuristicCodeResource,
    HeuristicDocumentClassifierResource,
    HeuristicLanguageResource,
    HeuristicNERResource,
    HeuristicTableResource,
    MiniLMDocumentClassifierResource,
    NoOpSpellResource,
    SymSpellResource,
    TableTransformerResource,
    TreeSitterCodeResource,
)
from .base import ResourcePlugin
from .convention_classifier import RuleConventionClassifierResource
from .docx_parser import PythonDocxParserResource
from .evidence_validator import RuleEvidenceValidatorResource
from .heuristic_layout import HeuristicLayoutResource
from .local_storage import LocalStorageResource
from .models import ResourceManifest
from .noop_ocr import NoOpOCRResource
from .pdf_parser import PyMuPDFPdfParserResource


class ResourceRegistry:
    def __init__(self) -> None:
        self._resources: dict[str, ResourcePlugin] = {}

    def register(self, resource: ResourcePlugin) -> None:
        self._resources[resource.resource_id] = resource

    def get(self, resource_id: str) -> ResourcePlugin:
        return self._resources[resource_id]

    def available(self, resource_id: str) -> bool:
        return (
            resource_id in self._resources
            and self._resources[resource_id].health_check().available
        )

    def ids(self) -> list[str]:
        return sorted(self._resources)

    def manifest(self, resource_id: str) -> ResourceManifest:
        resource = self.get(resource_id)
        metadata = getattr(resource, "metadata", dict)()
        return ResourceManifest(
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            version=str(resource.version),
            dependencies=dict(metadata.get("dependencies", {})),
            configuration_schema=dict(metadata.get("configuration_schema", {})),
            supported_content_types=list(
                metadata.get(
                    "supported_content_types",
                    [
                        "application/pdf",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ],
                )
            ),
            supported_languages=list(
                metadata.get("supported_languages", ["zh", "en", "mixed"])
            ),
            license=str(metadata.get("license", "Apache-2.0")),
            author=str(metadata.get("author", "ZYRelay")),
            compatibility={
                "api_version": "v1",
                "python": ">=3.11",
                **dict(metadata.get("compatibility", {})),
            },
        )

    def health(self) -> dict[str, dict]:
        return {
            resource_id: self.get(resource_id).health_check().model_dump(mode="json")
            for resource_id in self.ids()
        }


def create_default_registry(
    settings: Settings | None = None, include_paddleocr: bool = True
) -> ResourceRegistry:
    settings = settings or Settings.from_env()
    registry = ResourceRegistry()
    for resource in (
        PyMuPDFPdfParserResource(),
        PythonDocxParserResource(),
        NoOpOCRResource(),
        HeuristicLayoutResource(),
        LocalStorageResource(),
        RuleConventionClassifierResource(),
        RuleEvidenceValidatorResource(),
        MiniLMDocumentClassifierResource(settings),
        HeuristicDocumentClassifierResource(settings),
        FastTextLanguageResource(settings),
        HeuristicLanguageResource(settings),
        DocLayoutYOLOResource(settings),
        TableTransformerResource(settings),
        HeuristicTableResource(settings),
        SymSpellResource(settings),
        NoOpSpellResource(settings),
        TreeSitterCodeResource(settings),
        HeuristicCodeResource(settings),
        GLiNERResource(settings),
        HeuristicNERResource(settings),
    ):
        registry.register(resource)
    if include_paddleocr:
        from .paddleocr_adapter import PaddleOCRResource

        registry.register(PaddleOCRResource(settings))
    return registry
