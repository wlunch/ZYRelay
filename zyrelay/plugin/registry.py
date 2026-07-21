from __future__ import annotations

from .facade import DocIntelligencePlugin


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, DocIntelligencePlugin] = {}

    def register(self, plugin: DocIntelligencePlugin) -> None:
        plugin_id = plugin.get_manifest().plugin_id
        if plugin_id in self._plugins:
            raise ValueError(f"插件已注册：{plugin_id}")
        self._plugins[plugin_id] = plugin

    def unregister(self, plugin_id: str) -> None:
        self._plugins.pop(plugin_id, None)

    def get(self, plugin_id: str) -> DocIntelligencePlugin:
        try:
            return self._plugins[plugin_id]
        except KeyError as exc:
            raise KeyError(f"插件不存在：{plugin_id}") from exc

    def list_plugins(self) -> list[DocIntelligencePlugin]:
        return [self._plugins[key] for key in sorted(self._plugins)]

    def get_manifest(self, plugin_id: str):
        return self.get(plugin_id).get_manifest()
