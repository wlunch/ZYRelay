from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zyrelay.app.models import (
    DocumentBlock,
    LabelDefinition,
    LabelMention,
    SemanticCandidate,
    SemanticIndexBucket,
    SourceDocument,
    UOMPackage,
)
from zyrelay.app.parsers import ParsedDocument
from zyrelay.app.conventions import (
    CodeConventionCandidate,
    ConventionIndex,
    ConventionSection,
)


@dataclass
class ProcessingContext:
    task_id: str
    request_id: str
    input_path: Path
    file_name: str
    file_bytes: bytes
    document: SourceDocument | None = None
    parsed_document: ParsedDocument | None = None
    blocks: list[DocumentBlock] = field(default_factory=list)
    labels: list[LabelDefinition] = field(default_factory=list)
    mentions: list[LabelMention] = field(default_factory=list)
    semantic_index: dict[str, SemanticIndexBucket] = field(default_factory=dict)
    raw_token_index: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    candidates: list[SemanticCandidate] = field(default_factory=list)
    convention_sections: list[ConventionSection] = field(default_factory=list)
    code_conventions: list[CodeConventionCandidate] = field(default_factory=list)
    convention_index: ConventionIndex = field(default_factory=ConventionIndex)
    package: UOMPackage | None = None
    steps: list[Any] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
