from __future__ import annotations

from .models import ResourceHealth, ResourceRequest, ResourceResponse


class NoOpOCRResource:
    resource_id = "noop-ocr"
    resource_type = "ocr"
    version = "1.0.0"

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(available=True, status="available")

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "ocr"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        return ResourceResponse(
            status="partial",
            payload=[],
            warnings=["OCR 模型不可用，扫描 PDF 未生成伪造文本"],
            metadata={"fallback": True},
        )
