from __future__ import annotations

from zyrelay.app.core.config import Settings

from .config import PluginRuntimeConfig
from .contracts import PluginCapabilities


class CapabilitiesProvider:
    def __init__(self, config: PluginRuntimeConfig, settings: Settings) -> None:
        self.config = config
        self.settings = settings

    def get(self) -> PluginCapabilities:
        features = self.config.features
        return PluginCapabilities(
            document_types=["pdf", "docx"],
            processing_modes=[
                "auto",
                "contract",
                "code_convention",
                "generic_document",
            ],
            features={
                "blocks": True,
                "labels": True,
                "semantic_index": features.semantic_index,
                "business_object_candidates": features.contracts,
                "code_conventions": features.code_conventions,
                "rule_expressions": features.code_conventions,
                "convention_index": features.convention_index,
                "ocr": False,
                "llm_optional": True,
                "llm_enabled": features.llm and self.settings.llm_enabled,
                "async_execution": not self.config.execution.synchronous,
                "remote_source_fetch": False,
            },
            limits={
                "max_file_size_bytes": min(
                    self.settings.max_file_size,
                    self.config.execution.max_file_size_bytes,
                ),
                "max_documents_per_request": 1,
                "supported_api_versions": [self.config.plugin.api_version],
            },
        )
