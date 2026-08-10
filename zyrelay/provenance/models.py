from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from zyrelay.app.models.document import utc_now


class ProvenanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provenance_id: str
    execution_id: str
    document_id: str
    ground_selection_id: str
    ground_snapshot_id: str
    resource_plan_id: str
    object_id: str | None = None
    source_pages: list[int] = Field(default_factory=list)
    source_offsets: list[dict[str, int]] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)
    execution_timestamp: datetime = Field(default_factory=utc_now)
    source_block_ids: list[str] = Field(default_factory=list)
    source_mention_ids: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    model_execution_ids: list[str] = Field(default_factory=list)
    validation_records: list[str] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    model_details: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
