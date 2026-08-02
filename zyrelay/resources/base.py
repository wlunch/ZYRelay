from __future__ import annotations

from typing import Protocol

from .models import ResourceHealth, ResourceRequest, ResourceResponse


class ResourcePlugin(Protocol):
    resource_id: str
    resource_type: str
    version: str

    def health_check(self) -> ResourceHealth: ...

    def supports(self, request: ResourceRequest) -> bool: ...

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse: ...
