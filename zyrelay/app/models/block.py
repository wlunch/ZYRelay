from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BlockType(StrEnum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"
    HEADER = "header"
    FOOTER = "footer"
    UNKNOWN = "unknown"


class DocumentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    document_id: str
    page_no: int | None = Field(default=None, ge=1)
    block_type: BlockType
    sequence: int = Field(ge=0)
    text: str
    normalized_text: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    heading_level: int | None = Field(default=None, ge=1, le=9)
    parent_block_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_offsets(self) -> "DocumentBlock":
        if self.end_offset < self.start_offset:
            raise ValueError("end_offset must not precede start_offset")
        return self

