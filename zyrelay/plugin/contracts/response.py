from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .artifacts import ArtifactReference
from .common import PluginOperation, PluginStatus
from .errors import PluginError, PluginWarning


class PluginSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str | None = None
    status: str
    block_count: int = 0
    mention_count: int = 0
    convention_count: int = 0
    business_object_count: int = 0
    warning_count: int = 0


class PluginResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: dict[str, Any] | None = None
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    labels: list[dict[str, Any]] = Field(default_factory=list)
    mentions: list[dict[str, Any]] = Field(default_factory=list)
    semantic_index: dict[str, Any] = Field(default_factory=dict)
    semantic_candidates: list[dict[str, Any]] = Field(default_factory=list)
    code_conventions: list[dict[str, Any]] = Field(default_factory=list)
    convention_index: dict[str, Any] = Field(default_factory=dict)
    business_objects: list[dict[str, Any]] = Field(default_factory=list)
    uom_package: dict[str, Any] | None = None
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    summary: PluginSummary | None = None


class PluginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    execution_id: str
    plugin_id: str
    plugin_version: str
    api_version: str
    operation: PluginOperation
    status: PluginStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: float = Field(ge=0)
    result: PluginResult | None = None
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    warnings: list[PluginWarning] = Field(default_factory=list)
    errors: list[PluginError] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
