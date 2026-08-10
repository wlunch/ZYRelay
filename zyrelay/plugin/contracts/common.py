from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PluginOperation(StrEnum):
    PROCESS_DOCUMENT = "process_document"
    VALIDATE_DOCUMENT = "validate_document"
    EXTRACT_CODE_CONVENTIONS = "extract_code_conventions"
    EXTRACT_CONTRACT = "extract_contract"
    GET_UOM = "get_uom"
    GET_CAPABILITIES = "get_capabilities"


class PluginMode(StrEnum):
    AUTO = "auto"
    CONTRACT = "contract"
    CODE_CONVENTION = "code_convention"
    GENERIC_DOCUMENT = "generic_document"


class OutputDetail(StrEnum):
    SUMMARY = "summary"
    STANDARD = "standard"
    FULL = "full"


class PluginStatus(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class SourceType(StrEnum):
    FILE = "file"
    BASE64 = "base64"
    DOCUMENT = "document"
    URI = "uri"
    TEXT = "text"


class PluginContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str | None = None
    team_id: str | None = None
    project_id: str | None = None
    user_id: str | None = None
    trace_id: str | None = None
    source_system: str | None = None
    correlation_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class CallbackConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = None
    secret_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PluginOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: PluginMode = PluginMode.AUTO
    extract_blocks: bool = True
    extract_labels: bool = True
    build_semantic_index: bool = True
    extract_business_objects: bool = True
    extract_code_conventions: bool = True
    build_convention_index: bool = True
    enable_llm: bool = False
    enable_fuzzy_matching: bool = False
    retain_intermediate: bool = False
    output_detail: OutputDetail = OutputDetail.STANDARD
    language_hint: str | None = None
    profile: str | None = None
    config_overrides: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    errors: list[PluginError] = Field(default_factory=list)
    warnings: list[PluginWarning] = Field(default_factory=list)


from .errors import PluginError, PluginWarning

ValidationResult.model_rebuild()
