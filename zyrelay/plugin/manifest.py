from __future__ import annotations

from .capabilities import CapabilitiesProvider
from .config import PluginRuntimeConfig
from .contracts import PluginManifest, PluginRequest, PluginResponse

ERROR_CODES = [
    "plugin_disabled",
    "unsupported_operation",
    "invalid_request",
    "missing_input",
    "conflicting_input",
    "unsupported_content_type",
    "file_too_large",
    "invalid_file",
    "parse_failed",
    "empty_document",
    "configuration_error",
    "execution_failed",
    "result_not_found",
    "artifact_not_found",
    "llm_failed",
    "internal_error",
]


class ManifestProvider:
    def __init__(
        self,
        config: PluginRuntimeConfig,
        capabilities: CapabilitiesProvider,
    ) -> None:
        self.config = config
        self.capabilities_provider = capabilities

    def get(self) -> PluginManifest:
        plugin = self.config.plugin
        capabilities = self.capabilities_provider.get()
        return PluginManifest(
            plugin_id=plugin.plugin_id,
            name=plugin.name,
            description=plugin.description,
            version=plugin.version,
            api_version=plugin.api_version,
            vendor=plugin.vendor,
            plugin_type=plugin.plugin_type,
            entrypoint="zyrelay.plugin.facade:DocIntelligencePlugin",
            supported_inputs=plugin.supported_content_types
            or [
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ],
            supported_outputs=[
                "uom_package",
                "document_blocks",
                "semantic_index",
                "code_conventions",
                "convention_index",
            ],
            capabilities=[
                "document_parse",
                "label_extract",
                "semantic_index",
                "contract_candidate",
                "code_convention_extract",
                "rule_expression_extract",
            ],
            configuration_schema={
                "$ref": f"/api/v1/plugins/{plugin.plugin_id}/schemas/configuration"
            },
            input_schema={"$ref": f"/api/v1/plugins/{plugin.plugin_id}/schemas/input"},
            output_schema={
                "$ref": f"/api/v1/plugins/{plugin.plugin_id}/schemas/output"
            },
            error_codes=ERROR_CODES,
            health_check="/health",
            documentation="/docs",
            dependencies=plugin.dependencies,
            supported_languages=plugin.supported_languages,
            license=plugin.license,
            author=plugin.author,
            permissions=plugin.permissions,
            compatibility={
                "api_version": plugin.api_version,
                "uom_schema_version": "1.0",
                "python": ">=3.11",
            },
            metadata={
                "capabilities": capabilities.model_dump(mode="json"),
                "lifecycle_operations": ["install", "validate", "update", "disable"],
            },
        )

    @staticmethod
    def input_schema() -> dict:
        return PluginRequest.model_json_schema()

    @staticmethod
    def output_schema() -> dict:
        return PluginResponse.model_json_schema()
