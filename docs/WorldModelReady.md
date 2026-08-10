# World-Model-Ready Export

ZYRelay remains a deterministic document intelligence engine. It does not create a World Model, knowledge graph, vector index, RAG service or Agent framework.

It exports trusted semantic objects for those systems to consume later:

```text
PDF / DOCX → Relay rules and evidence → Semantic Objects → downstream World Model / KG / Agent
```

Available document APIs:

```text
GET /api/v1/documents/{id}/semantic-objects
GET /api/v1/documents/{id}/entities
GET /api/v1/documents/{id}/rules
GET /api/v1/documents/{id}/relations
GET /api/v1/documents/{id}/events
GET /api/v1/documents/{id}/evidence
GET /api/v1/documents/{id}/business-objects
GET /api/v1/documents/{id}/semantic-objects/export?format=json|json-ld|graph-json
```

Semantic-object queries accept `object_type`, `category`, `language` and `page`. Exports are files-in-response only: JSON is the native record list, JSON-LD has a minimal context, and Graph JSON contains nodes and evidence-backed edges. No exporter writes to an external database.

The direct document API persists local object-level provenance with the explicit `GROUND-STANDALONE` / `RPLAN-STANDALONE` markers. Relay executions replace these markers with the selected immutable Ground snapshot and ResourcePlan IDs.
