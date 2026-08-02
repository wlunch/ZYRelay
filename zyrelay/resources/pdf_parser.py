from pathlib import Path

from zyrelay.app.parsers import PDFParser

from .models import ResourceHealth, ResourceRequest, ResourceResponse


class PyMuPDFPdfParserResource:
    resource_id = "pymupdf-parser"
    resource_type = "pdf_parser"
    version = PDFParser.version

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(available=True, status="available")

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "pdf_parser"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        parsed = PDFParser().parse(Path(request.file_path or ""))
        density = {
            page.page_no: len(page.text.strip())
            for page in parsed.pages
        }
        return ResourceResponse(
            status="completed",
            payload=parsed,
            warnings=parsed.warnings,
            metadata={
                "page_count": parsed.page_count,
                "requires_ocr": parsed.requires_ocr,
                "text_density": density,
            },
        )
