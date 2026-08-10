# Semantic Objects

ZYRelay v1.0 produces deterministic semantic objects in `UOMPackage.semantic_objects`. They are portable handoff records, not graph nodes and not a knowledge graph. The semantic section and every object declare `schema_version: "1.0"`; the additive migration helper preserves object IDs.

Each object has a stable `object_id`, type, confidence, document/page/block/offset coordinates, `provenance_id`, Ground snapshot, ResourcePlan and one or more evidence references. IDs use the source document SHA-256, object type, normalized value and source coordinates; rerunning the same input produces the same object IDs.

| Type | Source | Meaning |
| --- | --- | --- |
| `document_object` | source document | The input document, anchored to original text. |
| `evidence` | block / mention | Independent original-text evidence, including OCR geometry when present. |
| `entity` | entity label or candidate | Confirmed real-world object with type, aliases and evidence. |
| `observation` | field label or NER | Evidence-backed fact that is not confirmed as an entity. |
| `rule` | code convention | Executable or descriptive rule with target/operator/value. |
| `relation` | explicit source evidence | A supported source-to-target relation only. |
| `event` | explicit event candidate | Timestamp/participant event candidate. |
| `business_object` | existing BOM candidate | Composition that references semantic evidence objects. |

`SemanticValidationResult` verifies evidence, provenance, relation endpoints and business-object references. Validation never invents missing data.
