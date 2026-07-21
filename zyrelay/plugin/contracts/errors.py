from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PluginError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    stage: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
    source_error_code: str | None = None


class PluginWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    stage: str
    details: dict[str, Any] = Field(default_factory=dict)
