from __future__ import annotations

from .models import ResourceHealth, ResourceRequest, ResourceResponse


class RuleEvidenceValidatorResource:
    resource_id = "rule-evidence-validator"
    resource_type = "evidence_validator"
    version = "1.0.0"

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(available=True, status="available")

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "evidence_validator"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        return ResourceResponse(status="completed", metadata={"delegates_to": "existing_validator"})
