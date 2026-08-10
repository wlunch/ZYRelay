from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from zyrelay.app.models.document import utc_now


class RelayMode(StrEnum):
    CODE_CONVENTION = "code_convention"
    CONTRACT = "contract"
    AUTO = "auto"


class RelayStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class RelayEnvironment(StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class ExecutionContext(BaseModel):
    """Immutable business scope carried by every Relay execution."""

    model_config = ConfigDict(extra="forbid")

    enterprise_id: str = "default"
    department_id: str | None = None
    team_id: str | None = None
    project_id: str | None = None
    environment: RelayEnvironment = RelayEnvironment.DEV
    retry_limit: int = Field(default=0, ge=0, le=3)


class RelayInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str
    content_type: str | None = None
    file_path: str | None = None
    content_base64: str | None = None
    source_uri: str | None = None

    @model_validator(mode="after")
    def validate_one_content_source(self) -> RelayInput:
        if bool(self.file_path) == bool(self.content_base64):
            raise ValueError("file_path 与 content_base64 必须二选一")
        return self


class RelayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    enterprise_id: str = "default"
    department_id: str | None = None
    team_id: str | None = None
    project_id: str | None = None
    environment: RelayEnvironment = RelayEnvironment.DEV
    retry_limit: int = Field(default=0, ge=0, le=3)
    mode: RelayMode = RelayMode.CODE_CONVENTION
    ground_profile_id: str | None = None
    resource_profile_id: str | None = None
    enable_ocr: bool = True
    enable_layout_model: bool = False
    enable_llm: bool = False
    output_detail: str = "standard"
    input: RelayInput
    metadata: dict[str, Any] = Field(default_factory=dict)


class StepRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_name: str
    status: str
    started_at: datetime
    completed_at: datetime
    duration_ms: float = Field(ge=0)
    resource_id: str | None = None
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    attempt: int = Field(default=1, ge=1)


class ModelExecutionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_execution_id: str
    execution_id: str
    step_name: str
    resource_id: str
    resource_version: str
    model_name: str
    model_version: str | None = None
    capability: str
    input_references: list[str] = Field(default_factory=list)
    output_references: list[str] = Field(default_factory=list)
    status: str
    started_at: datetime
    completed_at: datetime
    duration_ms: float = Field(ge=0)
    confidence_summary: dict[str, float] = Field(default_factory=dict)
    fallback_used: bool = False
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class RelayExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str
    request_id: str
    document_id: str | None = None
    enterprise_id: str
    department_id: str | None = None
    team_id: str | None = None
    project_id: str | None = None
    environment: RelayEnvironment = RelayEnvironment.DEV
    retry_limit: int = Field(default=0, ge=0)
    mode: RelayMode
    status: RelayStatus = RelayStatus.CREATED
    current_step: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    duration_ms: float | None = None
    ground_selection_id: str | None = None
    ground_snapshot_id: str | None = None
    resource_plan_id: str | None = None
    steps: list[StepRecord] = Field(default_factory=list)
    model_executions: list[ModelExecutionRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    execution_history: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelayResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str
    status: RelayStatus
    document_id: str | None = None
    ground: dict[str, Any] = Field(default_factory=dict)
    resources: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
