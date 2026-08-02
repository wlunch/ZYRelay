import base64

import fitz

from zyrelay.relay.models import RelayInput, RelayRequest, RelayStatus
from zyrelay.resources.models import OCRLine, ResourceHealth, ResourceResponse


def _scan_pdf(tmp_path):
    path = tmp_path / "scan.pdf"
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_image(fitz.Rect(72, 72, 200, 200), stream=png)
    pdf.save(path)
    pdf.close()
    return path


class FakeOCRResource:
    resource_id = "paddleocr"
    resource_type = "ocr"
    version = "fake-1.0"

    def health_check(self):
        return ResourceHealth(available=True, status="available")

    def supports(self, request):
        return request.capability == "ocr"

    def execute(self, request, context):
        return ResourceResponse(
            status="completed",
            payload=[
                OCRLine(
                    line_id="OCR-001-0001",
                    page_no=1,
                    text="Java 类名必须使用大驼峰命名。",
                    bbox=[10, 20, 200, 42],
                    confidence=0.96,
                    reading_order=0,
                    model_execution_id="MEXEC-FAKE-000001",
                )
            ],
            metadata={"model_execution_id": "MEXEC-FAKE-000001"},
        )


def test_scanned_pdf_uses_noop_fallback_without_download(relay_service, tmp_path) -> None:
    path = _scan_pdf(tmp_path)
    result = relay_service.process(
        RelayRequest(
            input=RelayInput(file_name=path.name, file_path=str(path)),
            output_detail="full",
        )
    )
    assert result.status == RelayStatus.PARTIAL
    assert result.resources["bindings"]["ocr"] == "noop-ocr"
    assert result.result["blocks"] == []
    assert any("未生成伪造文本" in item for item in result.warnings)


def test_fake_ocr_adds_traceable_block_metadata(relay_service, tmp_path) -> None:
    relay_service.resources.register(FakeOCRResource())
    path = _scan_pdf(tmp_path)
    result = relay_service.process(
        RelayRequest(
            input=RelayInput(file_name=path.name, file_path=str(path)),
            output_detail="full",
        )
    )
    assert result.status == RelayStatus.COMPLETED
    block = result.result["blocks"][0]
    assert block["metadata"]["source_method"] == "ocr"
    assert block["metadata"]["bbox"] == [10.0, 20.0, 200.0, 42.0]
    assert block["metadata"]["ocr_confidence"] == 0.96
    assert block["metadata"]["model_execution_id"] == "MEXEC-FAKE-000001"
    assert result.result["model_executions"][0]["model_execution_id"] == "MEXEC-FAKE-000001"
