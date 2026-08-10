# Object Mapping Model

```text
Document block / label mention / convention candidate
                 ↓
          Evidence object
                 ↓
Entity · Observation · Rule · Event · BusinessObject
                 ↓
       Explicit evidence-backed Relation
```

Candidate compatibility is preserved:

| Existing result | v0.8 mapping |
| --- | --- |
| `SemanticCandidate(entity)` | `entity` when source mentions resolve to evidence |
| `SemanticCandidate(event)` | `event` when source mentions resolve to evidence |
| `SemanticCandidate(business_object)` | `business_object` with `candidate_id` and semantic references |
| `CodeConventionCandidate` | `rule` with target, operator, value, category, language, tool and requirement level |
| Field mention | `observation` |
| Entity mention | `entity` |
| NER result | `observation` until a governed label confirms it |

Relations use only `applies_to`, `defined_by`, `references`, `depends_on`, `belongs_to`, `generated_from` and `supported_by`. ZYRelay emits a relation only when both endpoints and source evidence exist. It does not infer missing relations.
