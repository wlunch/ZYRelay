from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from zyrelay.app.conventions import CodeConventionCandidate, ConventionIndex

from .block import DocumentBlock
from .document import SourceDocument, utc_now
from .label import LabelDefinition, LabelMention
from .semantic import (
    SemanticCandidate,
    SemanticIndexBucket,
    SemanticObject,
    SemanticValidationResult,
)


class ProcessingStepRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    started_at: datetime
    ended_at: datetime
    duration_ms: float = Field(ge=0)
    status: str
    warning: str | None = None
    error_code: str | None = None
    error: str | None = None


class ProcessingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline_version: str
    ground_truth_version: str
    label_config_hash: str
    business_object_config_hash: str
    code_convention_label_config_hash: str | None = None
    code_rule_pattern_config_hash: str | None = None
    relay_execution_id: str | None = None
    ground_selection_id: str | None = None
    ground_snapshot_id: str | None = None
    resource_plan_id: str | None = None
    resolved_ground_hash: str | None = None
    resource_plan_hash: str | None = None
    model_execution_ids: list[str] = Field(default_factory=list)
    layout: dict[str, Any] = Field(default_factory=dict)
    table: dict[str, Any] = Field(default_factory=dict)
    classifier: dict[str, Any] = Field(default_factory=dict)
    language: dict[str, Any] = Field(default_factory=dict)
    ner: dict[str, Any] = Field(default_factory=dict)
    spell: dict[str, Any] = Field(default_factory=dict)
    model_routing: dict[str, Any] = Field(default_factory=dict)
    configuration: dict[str, dict[str, str]] = Field(default_factory=dict)
    execution_context: dict[str, Any] = Field(default_factory=dict)
    performance: dict[str, Any] = Field(default_factory=dict)
    steps: list[ProcessingStepRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class MOMSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: SourceDocument
    blocks: list[DocumentBlock]


class SOMSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    labels: list[LabelDefinition]
    mentions: list[LabelMention]
    semantic_index: dict[str, SemanticIndexBucket]
    raw_token_index: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    candidates: list[SemanticCandidate]
    code_conventions: list[CodeConventionCandidate] = Field(default_factory=list)
    convention_index: ConventionIndex = Field(default_factory=ConventionIndex)


class BOMSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_objects: list[SemanticCandidate]
    team_convention_profiles: list[dict[str, Any]] = Field(default_factory=list)


class SemanticObjectSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    objects: list[SemanticObject] = Field(default_factory=list)
    validation: SemanticValidationResult = Field(
        default_factory=lambda: SemanticValidationResult(
            valid=True, object_count=0, relation_count=0, evidence_count=0
        )
    )


class UOMPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    package_id: str
    generated_at: datetime = Field(default_factory=utc_now)
    source: SourceDocument
    mom: MOMSection
    som: SOMSection
    semantic_objects: SemanticObjectSection = Field(
        default_factory=SemanticObjectSection
    )
    bom: BOMSection
    processing: ProcessingRecord
