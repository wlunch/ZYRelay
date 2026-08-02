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
    source_block_ids: list[str] = Field(default_factory=list)
    source_mention_ids: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    model_execution_ids: list[str] = Field(default_factory=list)
    validation_records: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
