from __future__ import annotations

import base64
import binascii
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from zyrelay.app.core.config import Settings

from ..config import PluginRuntimeConfig
from ..contracts import (
    PluginError,
    PluginOperation,
    PluginOptions,
    PluginRequest,
    PluginWarning,
    SourceType,
    ValidationResult,
)

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_TO_EXTENSION = {PDF_MIME: ".pdf", DOCX_MIME: ".docx"}
DOCUMENT_ID = re.compile(r"^DOC-[A-F0-9]{16}$")
EXECUTION_ID = re.compile(r"^EXEC-[A-F0-9]{16}$")


@dataclass(frozen=True)
class MappedPluginInput:
    file_name: str
    content_type: str
    content: bytes
    source_type: str
    source_uri: str | None


class PluginRequestMapper:
    def __init__(self, config: PluginRuntimeConfig, settings: Settings) -> None:
        self.config = config
        self.settings = settings

    @property
    def max_file_size(self) -> int:
        return min(
            self.settings.max_file_size,
            self.config.execution.max_file_size_bytes,
        )

    def validate(self, request: PluginRequest) -> ValidationResult:
        errors: list[PluginError] = []
        warnings: list[PluginWarning] = []
        if not self.config.plugin.enabled:
            errors.append(self._error("plugin_disabled", "插件已禁用"))
            return ValidationResult(valid=False, errors=errors)

        if request.execution_id and not EXECUTION_ID.fullmatch(request.execution_id):
            errors.append(self._error("invalid_request", "execution_id 格式无效"))

        invalid_overrides = sorted(
            set(request.options.config_overrides) - set(self.config.overrides.allowed)
        )
        if invalid_overrides:
            errors.append(
                self._error(
                    "invalid_request",
                    "包含不允许覆盖的配置",
                    details={"keys": invalid_overrides},
                )
            )
        elif request.options.config_overrides:
            try:
                self.effective_options(request.options)
            except ValueError as exc:
                errors.append(
                    self._error(
                        "invalid_request",
                        "config_overrides 的值无效",
                        details={"reason": str(exc)},
                    )
                )

        if request.callback is not None:
            warnings.append(
                PluginWarning(
                    code="callback_not_executed",
                    message="同步 MVP 不执行 callback",
                    stage="validation",
                )
            )

        if request.operation == PluginOperation.GET_CAPABILITIES:
            return ValidationResult(valid=not errors, errors=errors, warnings=warnings)

        if request.input is None:
            errors.append(self._error("missing_input", "请求缺少 input"))
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        plugin_input = request.input
        raw_fields = [
            bool(plugin_input.file_path),
            bool(plugin_input.content_base64),
            bool(plugin_input.text),
        ]
        if sum(raw_fields) > 1:
            errors.append(self._error("conflicting_input", "原始内容输入只能提供一种"))

        if request.operation == PluginOperation.GET_UOM:
            if not plugin_input.document_id:
                errors.append(self._error("missing_input", "get_uom 需要 document_id"))
            elif not DOCUMENT_ID.fullmatch(plugin_input.document_id):
                errors.append(self._error("invalid_request", "document_id 格式无效"))
            if any(raw_fields):
                errors.append(
                    self._error(
                        "conflicting_input",
                        "get_uom 不能同时提供原始内容",
                    )
                )
            if plugin_input.source_type != SourceType.DOCUMENT:
                errors.append(
                    self._error(
                        "invalid_request",
                        "get_uom 的 source_type 必须为 document",
                    )
                )
            return ValidationResult(valid=not errors, errors=errors, warnings=warnings)

        if not plugin_input.file_path and not plugin_input.content_base64:
            errors.append(
                self._error(
                    "missing_input",
                    "需要 file_path 或 content_base64",
                )
            )
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        if (plugin_input.file_path and plugin_input.source_type != SourceType.FILE) or (
            plugin_input.content_base64
            and plugin_input.source_type != SourceType.BASE64
        ):
            errors.append(
                self._error(
                    "invalid_request",
                    "source_type 与实际输入方式不一致",
                )
            )

        if plugin_input.text:
            errors.append(
                self._error(
                    "unsupported_content_type",
                    "第一阶段不支持纯文本输入",
                )
            )
        if plugin_input.file_path and request.metadata.get("_transport") == "http":
            errors.append(
                self._error(
                    "invalid_request",
                    "HTTP JSON 调用不允许读取服务器 file_path",
                )
            )

        if not plugin_input.file_name or not plugin_input.content_type:
            errors.append(
                self._error(
                    "invalid_request",
                    "原始文件需要 file_name 和 content_type",
                )
            )
            return ValidationResult(valid=not errors, errors=errors, warnings=warnings)

        extension = Path(plugin_input.file_name).suffix.lower()
        expected_extension = MIME_TO_EXTENSION.get(plugin_input.content_type)
        if expected_extension is None or extension != expected_extension:
            errors.append(
                self._error(
                    "unsupported_content_type",
                    "content_type、扩展名或支持类型不匹配",
                    details={
                        "content_type": plugin_input.content_type,
                        "extension": extension,
                    },
                )
            )

        if plugin_input.file_path and request.metadata.get("_transport") != "http":
            path = Path(plugin_input.file_path).expanduser()
            if not path.is_file():
                errors.append(self._error("invalid_file", "file_path 不存在或不是文件"))
            elif path.stat().st_size > self.max_file_size:
                errors.append(self._error("file_too_large", "文件超过大小限制"))
            elif expected_extension:
                signature_error = self._signature_error(
                    expected_extension, path.read_bytes()
                )
                if signature_error:
                    errors.append(signature_error)

        if plugin_input.content_base64:
            estimated_size = len(plugin_input.content_base64) * 3 // 4
            if estimated_size > self.max_file_size + 3:
                errors.append(self._error("file_too_large", "base64 内容超过大小限制"))
            else:
                try:
                    content = base64.b64decode(
                        plugin_input.content_base64, validate=True
                    )
                    if len(content) > self.max_file_size:
                        errors.append(self._error("file_too_large", "文件超过大小限制"))
                    elif expected_extension:
                        signature_error = self._signature_error(
                            expected_extension, content
                        )
                        if signature_error:
                            errors.append(signature_error)
                except (binascii.Error, ValueError):
                    errors.append(self._error("invalid_file", "base64 编码无效"))

        return ValidationResult(valid=not errors, errors=errors, warnings=warnings)

    @staticmethod
    def effective_options(options: PluginOptions) -> PluginOptions:
        values = options.model_dump(mode="python")
        overrides = values.pop("config_overrides")
        values.update(overrides)
        values["config_overrides"] = overrides
        return PluginOptions.model_validate(values)

    def map(self, request: PluginRequest) -> MappedPluginInput:
        validation = self.validate(request)
        if not validation.valid or request.input is None:
            raise ValueError("request validation failed")
        plugin_input = request.input
        if plugin_input.file_path:
            content = Path(plugin_input.file_path).expanduser().read_bytes()
        else:
            content = base64.b64decode(plugin_input.content_base64 or "", validate=True)
        extension = MIME_TO_EXTENSION[plugin_input.content_type or ""]
        signature_error = self._signature_error(extension, content)
        if signature_error:
            raise ValueError(signature_error.message)
        return MappedPluginInput(
            file_name=Path(plugin_input.file_name or "upload").name,
            content_type=plugin_input.content_type or "application/octet-stream",
            content=content,
            source_type=plugin_input.source_type.value,
            source_uri=plugin_input.source_uri,
        )

    def _signature_error(self, extension: str, content: bytes) -> PluginError | None:
        if not content:
            return self._error("invalid_file", "文件内容为空")
        if extension == ".pdf" and not content.startswith(b"%PDF-"):
            return self._error("invalid_file", "PDF 文件签名无效")
        if extension == ".docx":
            if not content.startswith(b"PK"):
                return self._error("invalid_file", "DOCX ZIP 签名无效")
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    if "word/document.xml" not in archive.namelist():
                        return self._error(
                            "invalid_file", "DOCX 缺少 word/document.xml"
                        )
            except zipfile.BadZipFile:
                return self._error("invalid_file", "DOCX ZIP 结构无效")
        return None

    @staticmethod
    def _error(
        code: str,
        message: str,
        *,
        details: dict | None = None,
    ) -> PluginError:
        return PluginError(
            code=code,
            message=message,
            stage="validation",
            retryable=False,
            details=details or {},
        )
