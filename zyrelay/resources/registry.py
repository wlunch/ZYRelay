from __future__ import annotations

from .base import ResourcePlugin
from .convention_classifier import RuleConventionClassifierResource
from .docx_parser import PythonDocxParserResource
from .evidence_validator import RuleEvidenceValidatorResource
from .heuristic_layout import HeuristicLayoutResource
from .local_storage import LocalStorageResource
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
        return resource_id in self._resources and self._resources[resource_id].health_check().available

    def ids(self) -> list[str]:
        return sorted(self._resources)


def create_default_registry(include_paddleocr: bool = True) -> ResourceRegistry:
    registry = ResourceRegistry()
    for resource in (
        PyMuPDFPdfParserResource(),
        PythonDocxParserResource(),
        NoOpOCRResource(),
        HeuristicLayoutResource(),
        LocalStorageResource(),
        RuleConventionClassifierResource(),
        RuleEvidenceValidatorResource(),
    ):
        registry.register(resource)
    if include_paddleocr:
        from .paddleocr_adapter import PaddleOCRResource

        registry.register(PaddleOCRResource())
    return registry
