from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .common import (
    CallbackConfig,
    PluginContext,
    PluginOperation,
    PluginOptions,
    SourceType,
)


class PluginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    file_name: str | None = None
    content_type: str | None = None
    file_path: str | None = None
    content_base64: str | None = None
    source_uri: str | None = None
    document_id: str | None = None
    text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PluginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    execution_id: str | None = None
    operation: PluginOperation = PluginOperation.PROCESS_DOCUMENT
    input: PluginInput | None = None
    options: PluginOptions = Field(default_factory=PluginOptions)
    context: PluginContext | None = None
    callback: CallbackConfig | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
