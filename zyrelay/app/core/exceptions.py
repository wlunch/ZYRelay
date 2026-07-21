class ZYRelayError(Exception):
    error_code = "zyrelay_error"
    status_code = 500

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnsupportedFileTypeError(ZYRelayError):
    error_code = "unsupported_file_type"
    status_code = 415


class InvalidFileError(ZYRelayError):
    error_code = "invalid_file"
    status_code = 400


class FileTooLargeError(ZYRelayError):
    error_code = "file_too_large"
    status_code = 413


class ParseFailedError(ZYRelayError):
    error_code = "parse_failed"
    status_code = 422


class EmptyDocumentError(ZYRelayError):
    error_code = "empty_document"
    status_code = 422


class LabelConfigInvalidError(ZYRelayError):
    error_code = "label_config_invalid"
    status_code = 500


class IndexBuildError(ZYRelayError):
    error_code = "index_build_failed"
    status_code = 500


class StorageError(ZYRelayError):
    error_code = "storage_failed"
    status_code = 500


class LLMError(ZYRelayError):
    error_code = "llm_failed"
    status_code = 502


class DocumentNotFoundError(ZYRelayError):
    error_code = "document_not_found"
    status_code = 404

