from pathlib import Path

from zyrelay.app.parsers import DOCXParser

from .models import ResourceHealth, ResourceRequest, ResourceResponse


class PythonDocxParserResource:
    resource_id = "python-docx-parser"
    resource_type = "docx_parser"
    version = DOCXParser.version

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(available=True, status="available")

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "docx_parser"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        parsed = DOCXParser().parse(Path(request.file_path or ""))
        return ResourceResponse(
            status="completed",
            payload=parsed,
            warnings=parsed.warnings,
            metadata={"page_count": parsed.page_count, "element_count": len(parsed.elements)},
        )
