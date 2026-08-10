from __future__ import annotations

from zyrelay.app.core.exceptions import ZYRelayError

from .contracts import PluginError

ERROR_MAP = {
    "unsupported_file_type": ("unsupported_content_type", "validation"),
    "invalid_file": ("invalid_file", "validation"),
    "file_too_large": ("file_too_large", "validation"),
    "parse_failed": ("parse_failed", "parsing"),
    "empty_document": ("empty_document", "extraction"),
    "label_config_invalid": ("configuration_error", "configuration"),
    "index_build_failed": ("execution_failed", "indexing"),
    "storage_failed": ("execution_failed", "storage"),
    "llm_failed": ("llm_failed", "enrichment"),
    "document_not_found": ("result_not_found", "result"),
}


def map_exception(exc: Exception) -> PluginError:
    source_code = getattr(exc, "error_code", None)
    code, stage = ERROR_MAP.get(source_code, ("internal_error", "execution"))
    message = exc.message if isinstance(exc, ZYRelayError) else "插件执行失败"
    details = exc.details if isinstance(exc, ZYRelayError) else {}
    return PluginError(
        code=code,
        message=message,
        stage=stage,
        retryable=False,
        details=details,
        source_error_code=source_code,
    )
