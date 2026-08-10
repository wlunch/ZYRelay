# Migration Guide: 0.8 to 1.0

Existing document, Relay, plugin and search endpoints remain compatible. UOM
top-level `schema_version` remains `1.0`. Additive fields are introduced only:
`processing.configuration`, `processing.execution_context`,
`processing.performance`, semantic-object `schema_version`, and resource-plan
scope/configuration data.

Semantic migration is exposed by `migrate_semantic_object()` and only fills
`schema_version`; it never recalculates object IDs. Update version assertions to
`1.0.0`, add `languages.yaml` and `thresholds.yaml` to deployments, and use the
new plugin lifecycle endpoints when an operational disable switch is required.
