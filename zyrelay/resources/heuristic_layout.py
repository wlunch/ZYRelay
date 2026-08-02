from __future__ import annotations

from zyrelay.app.models import BlockType
from zyrelay.app.parsers import ParsedDocument

from .models import ResourceHealth, ResourceRequest, ResourceResponse


class HeuristicLayoutResource:
    resource_id = "heuristic-layout"
    resource_type = "layout"
    version = "1.0.0"

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(available=True, status="available")

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "layout"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        parsed = request.options.get("parsed_document")
        if not isinstance(parsed, ParsedDocument):
            return ResourceResponse(status="completed", payload={})
        if parsed.elements:
            types = [item.block_type.value for item in parsed.elements]
        else:
            types = [BlockType.PARAGRAPH.value for page in parsed.pages if page.text.strip()]
        return ResourceResponse(
            status="completed",
            payload={"detected_block_types": types, "method": "heuristic"},
        )
