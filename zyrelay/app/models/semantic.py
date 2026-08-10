from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .document import utc_now


class SemanticIndexOccurrence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    page_no: int | None = Field(default=None, ge=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    matched_text: str
    normalized_value: str
    confidence: float = Field(ge=0, le=1)


class SemanticIndexEntry(BaseModel):
    """Flat core index entry; useful for internal aggregation and tests."""

    model_config = ConfigDict(extra="forbid")

    token: str
    label_code: str
    document_id: str
    occurrences: list[SemanticIndexOccurrence] = Field(default_factory=list)


class SemanticIndexBucket(BaseModel):
    """Public label-first index shape."""

    model_config = ConfigDict(extra="forbid")

    label_code: str
    documents: dict[str, list[SemanticIndexOccurrence]] = Field(default_factory=dict)


class CandidateType(StrEnum):
    ENTITY = "entity"
    RELATION = "relation"
    EVENT = "event"
    BUSINESS_OBJECT = "business_object"


class CandidateStatus(StrEnum):
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class SemanticCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    candidate_type: CandidateType
    name: str
    source_mentions: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    ontology_uri: str | None = None
    status: CandidateStatus = CandidateStatus.DETECTED


class SemanticObjectType(StrEnum):
    ENTITY = "entity"
    RULE = "rule"
    RELATION = "relation"
    EVENT = "event"
    DOCUMENT_OBJECT = "document_object"
    OBSERVATION = "observation"
    EVIDENCE = "evidence"
    BUSINESS_OBJECT = "business_object"


class SemanticObjectStatus(StrEnum):
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class SemanticOffset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(ge=0)


class SemanticObject(BaseModel):
    """Deterministic, evidence-first handoff object for downstream systems."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    object_id: str
    object_type: SemanticObjectType
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    status: SemanticObjectStatus = SemanticObjectStatus.DETECTED
    document_id: str
    page: int | None = Field(default=None, ge=1)
    block_id: str | None = None
    offset: SemanticOffset | None = None
    provenance_id: str
    ground_snapshot_id: str | None = None
    resource_plan_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    evidence_ids: list[str] = Field(default_factory=list)
    source_object_id: str | None = None
    target_object_id: str | None = None
    category: str | None = None
    language: str | None = None


class SemanticValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    object_count: int = Field(ge=0)
    relation_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)
