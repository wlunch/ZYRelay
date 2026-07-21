from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from zyrelay.app.models import BlockType


@dataclass
class ParsedPage:
    page_no: int
    text: str
    width: float | None = None
    height: float | None = None
    has_images: bool = False


@dataclass
class ParsedElement:
    text: str
    block_type: BlockType
    page_no: int | None = None
    heading_level: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    parser: str
    parser_version: str
    page_count: int | None
    pages: list[ParsedPage] = field(default_factory=list)
    elements: list[ParsedElement] = field(default_factory=list)
    requires_ocr: bool = False
    warnings: list[str] = field(default_factory=list)


class DocumentParser(Protocol):
    name: str
    version: str

    def parse(self, path: Path) -> ParsedDocument: ...


class OCRProvider(Protocol):
    name: str

    def extract_page(self, path: Path, page_no: int) -> str | None: ...


class NoOpOCRProvider:
    name = "noop"

    def extract_page(self, path: Path, page_no: int) -> str | None:
        return None
