from pathlib import Path
from typing import Protocol

from zyrelay.app.models import DocumentBlock, UOMPackage
from zyrelay.app.parsers import ParsedPage


class Storage(Protocol):
    def save_source(self, document_id: str, file_name: str, content: bytes) -> Path: ...

    def save_prepared(
        self,
        document_id: str,
        pages: list[ParsedPage],
        blocks: list[DocumentBlock],
    ) -> None: ...

    def save_package(self, package: UOMPackage) -> Path: ...

    def load_package(self, document_id: str) -> UOMPackage: ...
