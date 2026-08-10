# Plugin SDK

The public plugin entry point is `DocIntelligencePlugin`. Python callers use
`get_manifest()`, `get_capabilities()`, `validate()` and `execute()`; HTTP
callers use `/api/v1/plugins/{plugin_id}`; CLI callers use `zyrelay-plugin`.

Each plugin manifest declares its version, dependencies, health endpoint,
configuration schema, supported content types/languages, author, license and
permissions. The local lifecycle API supports validation, disable and enable.
Installation/update validates an already trusted in-process plugin; ZYRelay does
not download arbitrary executable code from a marketplace.

```python
from zyrelay.plugin import DocIntelligencePlugin
plugin = DocIntelligencePlugin()
print(plugin.get_manifest().model_dump())
```

Resource plugins additionally expose `available`, `health`, `execute`,
`version`, metadata, and a generated marketplace-compatible ResourceManifest.
