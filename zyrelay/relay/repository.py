from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

Record = TypeVar("Record", bound=BaseModel)


class JsonRecordRepository:
    """Small local, atomic JSON repository for Relay audit records."""

    def __init__(self, directory: Path, model_type: type[Record]) -> None:
        self.directory = directory
        self.model_type = model_type
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, value: Record, record_id: str) -> Path:
        path = self.directory / f"{record_id}.json"
        self._atomic_json(path, value.model_dump(mode="json"))
        return path

    def load(self, record_id: str) -> Record:
        path = self.directory / f"{record_id}.json"
        if not path.is_file():
            raise FileNotFoundError(record_id)
        return self.model_type.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[Record]:
        return [
            self.model_type.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.directory.glob("*.json"))
        ]

    @staticmethod
    def _atomic_json(path: Path, value: object) -> None:
        encoded = json.dumps(
            value, ensure_ascii=False, indent=2, allow_nan=False
        ).encode("utf-8")
        json.loads(encoded)
        path.parent.mkdir(parents=True, exist_ok=True)
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
