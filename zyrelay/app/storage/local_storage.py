from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from zyrelay.app.core.exceptions import DocumentNotFoundError, StorageError
from zyrelay.app.models import DocumentBlock, UOMPackage
from zyrelay.app.parsers import ParsedPage


class LocalStorage:
    def __init__(self, data_root: Path, *, keep_prepared: bool = True) -> None:
        self.data_root = data_root
        self.keep_prepared = keep_prepared
        self.documents_dir = data_root / "documents"
        self.prepare_dir = data_root / "doc_prepare"
        self.index_dir = data_root / "doc_index"
        for directory in (self.documents_dir, self.prepare_dir, self.index_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def save_source(
        self, document_id: str, file_name: str, content: bytes
    ) -> Path:
        extension = Path(file_name).suffix.lower()
        destination = self.documents_dir / document_id / f"source{extension}"
        self._atomic_write_bytes(destination, content)
        return destination

    def save_prepared(
        self,
        document_id: str,
        pages: list[ParsedPage],
        blocks: list[DocumentBlock],
    ) -> None:
        if not self.keep_prepared:
            return
        destination = self.prepare_dir / document_id
        destination.mkdir(parents=True, exist_ok=True)
        for page in pages:
            self._atomic_write_bytes(
                destination / f"page-{page.page_no:03d}.txt",
                page.text.encode("utf-8"),
            )
        self._atomic_write_json(
            destination / "blocks.json",
            [block.model_dump(mode="json") for block in blocks],
        )

    def save_package(self, package: UOMPackage) -> Path:
        destination = self.index_dir / f"{package.source.document_id}.json"
        self._atomic_write_json(
            destination, package.model_dump(mode="json", exclude_none=False)
        )
        return destination

    def load_package(self, document_id: str) -> UOMPackage:
        path = self.index_dir / f"{document_id}.json"
        if not path.is_file():
            raise DocumentNotFoundError(f"文档不存在：{document_id}")
        try:
            return UOMPackage.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StorageError(f"无法读取文档索引：{document_id}") from exc

    def list_packages(self) -> list[UOMPackage]:
        packages: list[UOMPackage] = []
        for path in sorted(self.index_dir.glob("DOC-*.json")):
            try:
                packages.append(
                    UOMPackage.model_validate_json(path.read_text(encoding="utf-8"))
                )
            except Exception as exc:
                raise StorageError(f"索引文件损坏：{path.name}") from exc
        return packages

    @staticmethod
    def _atomic_write_bytes(destination: Path, content: bytes) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=destination.parent, prefix=f".{destination.name}.", delete=False
            ) as stream:
                temp_path = stream.name
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, destination)
        except Exception as exc:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)
            raise StorageError(f"原子写入失败：{destination}") from exc

    @classmethod
    def _atomic_write_json(cls, destination: Path, value: object) -> None:
        try:
            encoded = json.dumps(
                value, ensure_ascii=False, indent=2, allow_nan=False
            ).encode("utf-8")
            json.loads(encoded)
        except (TypeError, ValueError) as exc:
            raise StorageError(f"JSON 序列化校验失败：{destination}") from exc
        cls._atomic_write_bytes(destination, encoded)

