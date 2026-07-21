from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    file_name: str
    file_type: str
    file_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_uri: str | None = None
    language: str = "zh-CN"
    created_at: datetime = Field(default_factory=utc_now)
    page_count: int | None = Field(default=None, ge=0)
    parser: str | None = None
    parser_version: str | None = None
    requires_ocr: bool = False
    status: DocumentStatus = DocumentStatus.PROCESSING

