from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LabelCategory(StrEnum):
    DOCUMENT = "document"
    FIELD = "field"
    ENTITY = "entity"
    RELATION = "relation"
    EVENT = "event"
    BUSINESS_OBJECT = "business_object"
    RULE_ELEMENT = "rule_element"
    SEVERITY = "severity"
    CONVENTION_TYPE = "convention_type"
    EXAMPLE = "example"
    SCOPE = "scope"
    ENFORCEMENT = "enforcement"


class MatchMethod(StrEnum):
    REGEX = "regex"
    ALIAS_EXACT = "alias_exact"
    ALIAS_FUZZY = "alias_fuzzy"
    LLM = "llm"


class LabelDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    category: LabelCategory
    value_type: str
    aliases: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    description: str = ""
    ontology_uri: str | None = None
    business_object_type: str | None = None
    enabled: bool = True


class LabelMention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mention_id: str
    document_id: str
    block_id: str
    page_no: int | None = Field(default=None, ge=1)
    label_code: str
    matched_text: str
    normalized_value: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    match_method: MatchMethod
    evidence: str

    @model_validator(mode="after")
    def validate_offsets(self) -> "LabelMention":
        if self.end_offset <= self.start_offset:
            raise ValueError("mention offsets must describe non-empty evidence")
        return self
