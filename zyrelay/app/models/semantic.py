from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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

