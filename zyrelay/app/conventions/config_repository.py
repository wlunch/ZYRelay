from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from zyrelay.app.core.config import load_yaml
from zyrelay.app.core.exceptions import LabelConfigInvalidError


class NamingStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aliases: list[str] = Field(min_length=1)
    regex: str


class ForbiddenCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    target: str
    tool_hint: str | None = None


class CodeRulePatternConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    category_labels: dict[str, str]
    naming_styles: dict[str, NamingStyle]
    targets: dict[str, list[str]]
    forbidden_calls: list[ForbiddenCall] = Field(default_factory=list)


class ConventionConfigRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> CodeRulePatternConfig:
        try:
            return CodeRulePatternConfig.model_validate(load_yaml(self.path))
        except (OSError, ValueError, ValidationError) as exc:
            raise LabelConfigInvalidError(f"代码规范规则配置无效：{exc}") from exc
