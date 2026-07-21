from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PluginCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_types: list[str]
    processing_modes: list[str]
    features: dict[str, bool]
    limits: dict[str, Any]


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_id: str
    name: str
    description: str
    version: str
    api_version: str
    vendor: str
    plugin_type: str
    entrypoint: str
    supported_inputs: list[str]
    supported_outputs: list[str]
    capabilities: list[str]
    configuration_schema: dict[str, Any] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    error_codes: list[str] = Field(default_factory=list)
    health_check: str
    documentation: str
    compatibility: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
