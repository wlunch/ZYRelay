# API Compatibility Report — 0.8 to 1.0

All existing routes remain available with the same request and response fields:

- `/health`
- `/api/v1/documents/*` and `/api/v1/search`
- `/api/v1/relay/process`, executions, Ground, ResourcePlan, model and
  provenance routes
- `/api/v1/plugins/*` execute, validate, artifact and schema routes

v1.0 additions are non-breaking: plugin `health` and lifecycle routes;
`department_id`, `environment`, and `retry_limit` optional Relay form fields;
ResourcePlan scope/configuration fields; UOM processing configuration,
execution-context and performance fields; semantic-object schema version.

The automated compatibility suite includes API and plugin HTTP tests and was
run with the full offline test command in this release.
