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


class ResourcePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    execution_id: str
    enterprise_id: str
    resource_profile_id: str
    bindings: dict[str, str]
    fallback_bindings: dict[str, list[str]] = Field(default_factory=dict)
    selection_records: list[ResourceBindingRecord] = Field(default_factory=list)
    plan_hash: str
    created_at: datetime = Field(default_factory=utc_now)


class OCRLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: str
    page_no: int
    text: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    confidence: float = Field(ge=0, le=1)
    reading_order: int = Field(ge=0)
    model_execution_id: str
