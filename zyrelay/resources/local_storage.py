from __future__ import annotations

from .models import ResourceHealth, ResourceRequest, ResourceResponse


class LocalStorageResource:
    resource_id = "local-storage"
    resource_type = "storage"
    version = "1.0.0"

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(available=True, status="available")

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "storage"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        return ResourceResponse(
            status="completed", metadata={"delegates_to": "LocalStorage"}
        )
