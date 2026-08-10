from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RequirementLevel(StrEnum):
    MANDATORY = "mandatory"
    PROHIBITED = "prohibited"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"
    UNKNOWN = "unknown"


class RuleType(StrEnum):
    NAMING = "naming"
    FORMATTING = "formatting"
    COMMENT = "comment"
    EXCEPTION = "exception"
    LOGGING = "logging"
    API = "api"
    DATABASE = "database"
    SECURITY = "security"
    TESTING = "testing"
    GIT = "git"
    REVIEW = "review"
    ARCHITECTURE = "architecture"
    DEPENDENCY = "dependency"
    PERFORMANCE = "performance"
    GENERAL = "general"


class ConventionStatus(StrEnum):
    DETECTED = "detected"
    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class RuleOperator(StrEnum):
    MATCHES_REGEX = "matches_regex"
    NOT_MATCHES_REGEX = "not_matches_regex"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    IN_SET = "in_set"
    NOT_IN_SET = "not_in_set"
    REQUIRED = "required"
    PROHIBITED = "prohibited"
    UNSPECIFIED_LIMIT = "unspecified_limit"
    NOT_CONTAINS_SENSITIVE_SECRET = "not_contains_sensitive_secret"


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    block_id: str
    page_no: int | None = Field(default=None, ge=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    evidence_text: str
    mention_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_offsets(self) -> EvidenceReference:
        if self.end_offset <= self.start_offset:
            raise ValueError("evidence offsets must describe non-empty text")
        return self


class CodeExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    example_type: str = Field(pattern=r"^(positive|negative|neutral)$")
    language: str | None = None
    code: str
    explanation: str | None = None
    source_block_id: str
    generated_explanation: bool = False


class RuleExpression(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    operator: RuleOperator
    expected: Any = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    executable: bool = False
    tool_hint: str | None = None


class ConventionSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    title: str
    level: int = Field(ge=0, le=9)
    block_ids: list[str]
    text: str
    start_page: int | None = Field(default=None, ge=1)
    end_page: int | None = Field(default=None, ge=1)
    detected_categories: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class CodeConventionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    convention_id: str
    title: str
    description: str
    category: RuleType
    subcategory: str | None = None
    requirement_level: RequirementLevel
    rule_type: RuleType
    language: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    applicable_scope: list[str] = Field(default_factory=list)
    positive_examples: list[CodeExample] = Field(default_factory=list)
    negative_examples: list[CodeExample] = Field(default_factory=list)
    rationale: str | None = None
    verification_method: str | None = None
    suggested_tools: list[str] = Field(default_factory=list)
    source_mentions: list[str] = Field(default_factory=list)
    source_evidence: list[EvidenceReference] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    status: ConventionStatus = ConventionStatus.DETECTED
    ontology_uri: str | None = "uom://som/CodeConvention"
    rule_expression: RuleExpression | None = None
    provenance_id: str | None = None
    version: str = "1.0"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConventionIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by_category: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    by_language: dict[str, list[str]] = Field(default_factory=dict)
    by_requirement_level: dict[str, list[str]] = Field(default_factory=dict)
    by_tool: dict[str, list[str]] = Field(default_factory=dict)
    by_document: dict[str, list[str]] = Field(default_factory=dict)
