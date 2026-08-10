"""Local marketplace lifecycle controls for signed-in-process plugins.

The MVP deliberately does not download arbitrary code.  "Install" and
"update" validate a supplied manifest and register an already loaded plugin;
this keeps the deployment trust boundary explicit while exposing a stable SDK
surface for a future marketplace.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import PluginManifest
from .registry import PluginRegistry


@dataclass(frozen=True)
class PluginValidation:
    valid: bool
    errors: list[str]
    warnings: list[str]


class PluginLifecycleManager:
    def __init__(self, registry: PluginRegistry) -> None:
        self.registry = registry
        self._disabled: set[str] = set()

    @staticmethod
    def validate_manifest(manifest: PluginManifest) -> PluginValidation:
        errors: list[str] = []
        if not manifest.plugin_id or not manifest.version:
            errors.append("plugin_id_and_version_required")
        if not manifest.entrypoint:
            errors.append("entrypoint_required")
        if not manifest.supported_inputs:
            errors.append("supported_inputs_required")
        if not manifest.configuration_schema:
            errors.append("configuration_schema_required")
        if not manifest.license:
            errors.append("license_required")
        if not manifest.author:
            errors.append("author_required")
        return PluginValidation(valid=not errors, errors=errors, warnings=[])

    def install(self, plugin) -> PluginValidation:
        validation = self.validate_manifest(plugin.get_manifest())
        if validation.valid:
            try:
                self.registry.register(plugin)
            except ValueError:
                return self.update(plugin)
        return validation

    def update(self, plugin) -> PluginValidation:
        validation = self.validate_manifest(plugin.get_manifest())
        if validation.valid:
            self.registry.unregister(plugin.get_manifest().plugin_id)
            self.registry.register(plugin)
        return validation

    def disable(self, plugin_id: str) -> None:
        self.registry.get(plugin_id)
        self._disabled.add(plugin_id)

    def enable(self, plugin_id: str) -> None:
        self.registry.get(plugin_id)
        self._disabled.discard(plugin_id)

    def enabled(self, plugin_id: str) -> bool:
        return plugin_id not in self._disabled

    def health(self, plugin_id: str) -> dict:
        plugin = self.registry.get(plugin_id)
        return {
            "plugin_id": plugin_id,
            "enabled": self.enabled(plugin_id),
            "manifest_valid": self.validate_manifest(plugin.get_manifest()).valid,
        }
