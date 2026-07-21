from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Protocol

from .contracts import ArtifactReference
from .execution_repository import LocalExecutionRepository


ARTIFACT_ID = re.compile(r"^ART-[A-F0-9]{16}$")


class ArtifactRepository(Protocol):
    def save_json(
        self,
        execution_id: str,
        *,
        artifact_type: str,
        file_name: str,
        value: object,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactReference: ...

    def list(self, execution_id: str) -> list[ArtifactReference]: ...

    def load(
        self, execution_id: str, artifact_id: str
    ) -> tuple[ArtifactReference, bytes]: ...


class LocalArtifactRepository:
    def __init__(self, root: Path, id_generator) -> None:
        self.root = root
        self.id_generator = id_generator
        self.root.mkdir(parents=True, exist_ok=True)

    def save_json(
        self,
        execution_id: str,
        *,
        artifact_type: str,
        file_name: str,
        value: object,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactReference:
        LocalExecutionRepository._validate_id(execution_id)
        artifact_id = self.id_generator("ART")
        self._validate_artifact_id(artifact_id)
        payload = json.dumps(
            value, ensure_ascii=False, indent=2, allow_nan=False
        ).encode("utf-8")
        directory = self.root / execution_id
        directory.mkdir(parents=True, exist_ok=True)
        data_path = directory / f"{artifact_id}.json"
        LocalExecutionRepository._atomic_json(data_path, json.loads(payload))
        reference = ArtifactReference(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            media_type="application/json",
            file_name=Path(file_name).name,
            uri=(
                f"plugin://executions/{execution_id}/artifacts/{artifact_id}"
            ),
            checksum=hashlib.sha256(payload).hexdigest(),
            size=len(payload),
            metadata=metadata or {},
        )
        LocalExecutionRepository._atomic_json(
            directory / f"{artifact_id}.meta.json",
            reference.model_dump(mode="json"),
        )
        return reference

    def list(self, execution_id: str) -> list[ArtifactReference]:
        LocalExecutionRepository._validate_id(execution_id)
        directory = self.root / execution_id
        if not directory.is_dir():
            return []
        return [
            ArtifactReference.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("ART-*.meta.json"))
        ]

    def load(
        self, execution_id: str, artifact_id: str
    ) -> tuple[ArtifactReference, bytes]:
        LocalExecutionRepository._validate_id(execution_id)
        self._validate_artifact_id(artifact_id)
        directory = (self.root / execution_id).resolve()
        if self.root.resolve() not in directory.parents:
            raise ValueError("invalid artifact path")
        meta_path = directory / f"{artifact_id}.meta.json"
        data_path = directory / f"{artifact_id}.json"
        if not meta_path.is_file() or not data_path.is_file():
            raise FileNotFoundError(artifact_id)
        reference = ArtifactReference.model_validate_json(
            meta_path.read_text(encoding="utf-8")
        )
        return reference, data_path.read_bytes()

    @staticmethod
    def _validate_artifact_id(artifact_id: str) -> None:
        if not ARTIFACT_ID.fullmatch(artifact_id):
            raise ValueError("invalid artifact_id")
