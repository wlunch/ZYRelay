from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .contracts import PluginError, PluginResponse, PluginStatus, PluginWarning


EXECUTION_ID = re.compile(r"^EXEC-[A-F0-9]{16}$")


class PluginExecutionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str
    request_id: str
    plugin_id: str
    plugin_version: str
    operation: str
    input_summary: dict[str, Any]
    options: dict[str, Any]
    status: PluginStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: float = Field(ge=0)
    document_id: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    warnings: list[PluginWarning] = Field(default_factory=list)
    errors: list[PluginError] = Field(default_factory=list)
    trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LocalExecutionRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self, record: PluginExecutionRecord, response: PluginResponse
    ) -> None:
        self._validate_id(record.execution_id)
        self._atomic_json(
            self.root / f"{record.execution_id}.json",
            record.model_dump(mode="json"),
        )
        self._atomic_json(
            self.root / f"{record.execution_id}.response.json",
            response.model_dump(mode="json"),
        )

    def load_record(self, execution_id: str) -> PluginExecutionRecord:
        self._validate_id(execution_id)
        path = self.root / f"{execution_id}.json"
        if not path.is_file():
            raise FileNotFoundError(execution_id)
        return PluginExecutionRecord.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def load_response(self, execution_id: str) -> PluginResponse:
        self._validate_id(execution_id)
        path = self.root / f"{execution_id}.response.json"
        if not path.is_file():
            raise FileNotFoundError(execution_id)
        return PluginResponse.model_validate_json(path.read_text(encoding="utf-8"))

    @staticmethod
    def input_summary(
        *, file_name: str, content_type: str, content: bytes, source_type: str
    ) -> dict[str, Any]:
        return {
            "file_name": Path(file_name).name,
            "content_type": content_type,
            "size": len(content),
            "checksum": hashlib.sha256(content).hexdigest(),
            "source_type": source_type,
        }

    @staticmethod
    def _validate_id(execution_id: str) -> None:
        if not EXECUTION_ID.fullmatch(execution_id):
            raise ValueError("invalid execution_id")

    @staticmethod
    def _atomic_json(path: Path, value: object) -> None:
        encoded = json.dumps(
            value, ensure_ascii=False, indent=2, allow_nan=False
        ).encode("utf-8")
        json.loads(encoded)
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=path.parent, prefix=f".{path.name}.", delete=False
            ) as stream:
                temp_path = stream.name
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)
