from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from zyrelay.app.models.document import utc_now


class ModelInstallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    install_id: str
    model_name: str
    provider: str
    paddleocr_version: str
    paddlepaddle_version: str
    model_version: str
    cache_dir: str
    model_source: str
    required_models: list[str]
    file_checksums: dict[str, str] = Field(default_factory=dict)
    smoke_test_line_count: int = 0
    installed_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)
