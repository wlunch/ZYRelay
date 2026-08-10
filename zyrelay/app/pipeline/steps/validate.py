import hashlib
import zipfile
from pathlib import Path

from zyrelay.app.core.config import Settings
from zyrelay.app.core.exceptions import (
    FileTooLargeError,
    InvalidFileError,
    UnsupportedFileTypeError,
)
from zyrelay.app.models import SourceDocument
from zyrelay.app.pipeline.context import ProcessingContext


class ValidateFileStep:
    name = "validate_file"
    supported = {".pdf": "pdf", ".docx": "docx"}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        content = context.file_bytes
        if not content:
            raise InvalidFileError("上传文件为空")
        if len(content) > self.settings.max_file_size:
            raise FileTooLargeError(
                f"文件超过大小限制：{len(content)} > {self.settings.max_file_size}"
            )

        suffix = Path(context.file_name).suffix.lower()
        if suffix not in self.supported:
            raise UnsupportedFileTypeError(f"不支持的文件类型：{suffix or 'unknown'}")
        self._validate_signature(suffix, content, context.input_path)

        digest = hashlib.sha256(content).hexdigest()
        context.document = SourceDocument(
            document_id=f"DOC-{digest[:16].upper()}",
            file_name=Path(context.file_name).name,
            file_type=self.supported[suffix],
            file_size=len(content),
            sha256=digest,
        )
        return context

    @staticmethod
    def _validate_signature(suffix: str, content: bytes, path: Path) -> None:
        if suffix == ".pdf" and not content.startswith(b"%PDF-"):
            raise InvalidFileError("文件扩展名为 PDF，但文件签名无效")
        if suffix == ".docx":
            if not content.startswith(b"PK"):
                raise InvalidFileError("文件扩展名为 DOCX，但 ZIP 签名无效")
            try:
                with zipfile.ZipFile(path) as archive:
                    if "word/document.xml" not in archive.namelist():
                        raise InvalidFileError("DOCX 缺少 word/document.xml")
            except zipfile.BadZipFile as exc:
                raise InvalidFileError("DOCX ZIP 结构无效") from exc
