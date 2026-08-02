from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from zyrelay.app.models.document import utc_now


class GroundProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    name: str
    version: str
    status: str = "active"
    applicable_modes: list[str] = Field(default_factory=list)
    extends: str | None = None
    labels: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    rule_patterns: list[str] = Field(default_factory=list)
    business_objects: list[str] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)
    resource_profile_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    version: str
    matched: bool
    rejection_reason: str | None = None
    priority: int


class GroundSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_id: str
    execution_id: str
    requested_profile_id: str | None = None
    selected_profile_id: str
    selected_profile_version: str
    selection_reason: str
    candidate_profiles: list[CandidateProfile] = Field(default_factory=list)
    rejected_profiles: list[CandidateProfile] = Field(default_factory=list)
    inherited_profiles: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    resolved_profile_hash: str
    created_at: datetime = Field(default_factory=utc_now)


class GroundSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    execution_id: str
    profile_id: str
    profile_version: str
    labels: list[Any] = Field(default_factory=list)
    aliases: list[Any] = Field(default_factory=list)
    rule_patterns: list[Any] = Field(default_factory=list)
    business_objects: list[Any] = Field(default_factory=list)
    validation_rules: list[Any] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    resolved_hash: str
    created_at: datetime = Field(default_factory=utc_now)
