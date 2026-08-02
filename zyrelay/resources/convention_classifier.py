from __future__ import annotations

from .models import ResourceHealth, ResourceRequest, ResourceResponse


class RuleConventionClassifierResource:
    resource_id = "rule-convention-classifier"
    resource_type = "convention_classifier"
    version = "1.0.0"

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(available=True, status="available")

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "convention_classifier"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        return ResourceResponse(status="completed", metadata={"delegates_to": "existing_rules"})
