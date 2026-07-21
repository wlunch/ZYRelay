from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    artifact_type: str
    media_type: str
    file_name: str
    uri: str
    checksum: str
    size: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
