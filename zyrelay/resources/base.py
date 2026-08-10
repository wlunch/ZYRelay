from __future__ import annotations

from typing import Protocol

from .models import ResourceHealth, ResourceRequest, ResourceResponse


class ResourcePlugin(Protocol):
    resource_id: str
    resource_type: str
    version: str

    # v0.6 aliases make model resources consumable by SDKs without exposing the
    # older ``health_check`` naming.  Existing non-model resources remain
    # compatible through the registry's health_check contract.
    def available(self) -> bool: ...

    def health(self) -> ResourceHealth: ...

    def metadata(self) -> dict: ...

    def health_check(self) -> ResourceHealth: ...

    def supports(self, request: ResourceRequest) -> bool: ...

    def execute(
        self, request: ResourceRequest, context: object
    ) -> ResourceResponse: ...
