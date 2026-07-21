from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from zyrelay.app.core.config import load_yaml


class PluginIdentityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_id: str
    name: str
    description: str
    version: str
    api_version: str
    vendor: str
    plugin_type: str
    enabled: bool = True


class PluginExecutionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    synchronous: bool = True
    max_file_size_bytes: int = Field(gt=0)
    temp_dir: str
    retain_temp_files: bool = False
    default_output_detail: str = "standard"


class PluginFeatureConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contracts: bool = True
    code_conventions: bool = True
    semantic_index: bool = True
    convention_index: bool = True
    llm: bool = False
    fuzzy_matching: bool = False


class PluginOverrideConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: list[str] = Field(default_factory=list)


class PluginRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin: PluginIdentityConfig
    execution: PluginExecutionConfig
    features: PluginFeatureConfig
    overrides: PluginOverrideConfig


def load_plugin_config(path: Path) -> PluginRuntimeConfig:
    try:
        return PluginRuntimeConfig.model_validate(load_yaml(path))
    except (OSError, ValueError, ValidationError) as exc:
        raise RuntimeError(f"插件配置无效：{exc}") from exc
