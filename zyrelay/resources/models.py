from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from zyrelay.app.models.document import utc_now


class ResourceHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    status: str
    details: dict[str, Any] = Field(default_factory=dict)


class ResourceManifest(BaseModel):
    """Marketplace-compatible description generated for every resource plugin."""

    model_config = ConfigDict(extra="forbid")

    resource_id: str
    resource_type: str
    version: str
    dependencies: dict[str, str] = Field(default_factory=dict)
    configuration_schema: dict[str, Any] = Field(default_factory=dict)
    supported_content_types: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]
    )
    supported_languages: list[str] = Field(
        default_factory=lambda: ["zh", "en", "mixed"]
    )
    license: str = "Apache-2.0"
    author: str = "ZYRelay"
    compatibility: dict[str, str] = Field(
        default_factory=lambda: {"api_version": "v1", "python": ">=3.11"}
    )


class ResourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    capability: str
    file_path: str | None = None
    document_type: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ResourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    status: str
    payload: Any = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResourceBindingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str
    selected_resource_id: str
    selection_reason: str
    fallback_used: bool = False
    rejected_resources: list[str] = Field(default_factory=list)
    plugin_name: str | None = None
    model_version: str | None = None
    model_execution_id: str | None = None
    latency_ms: float | None = None
    health: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    planned_execution: bool = True
    actual_execution: bool = False
    skip_reason: str | None = None
    gate_decision: str | None = None
    input_signals: dict[str, Any] = Field(default_factory=dict)
    compatibility: dict[str, Any] = Field(default_factory=dict)


class ResourcePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    execution_id: str
    enterprise_id: str
    department_id: str | None = None
    team_id: str | None = None
    project_id: str | None = None
    environment: str = "dev"
    resource_config_version: str | None = None
    resource_config_hash: str | None = None
    resource_profile_id: str
    bindings: dict[str, str]
    fallback_bindings: dict[str, list[str]] = Field(default_factory=dict)
    selection_records: list[ResourceBindingRecord] = Field(default_factory=list)
    resource_health: dict[str, dict[str, Any]] = Field(default_factory=dict)
    plan_hash: str
    created_at: datetime = Field(default_factory=utc_now)


class OCRLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: str
    page_no: int
    text: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    polygon: list[list[float]] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    reading_order: int = Field(ge=0)
    model_execution_id: str


class OCRPageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_no: int
    width: int
    height: int
    orientation: int | None = None
    orientation_confidence: float | None = Field(default=None, ge=0, le=1)
    lines: list[OCRLine] = Field(default_factory=list)
    average_confidence: float = Field(ge=0, le=1)
    resource_id: str
    resource_version: str
    model_execution_id: str
    page_artifact: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
