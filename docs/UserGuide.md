# User Guide

Start the service and open `/docs`. Upload a PDF or DOCX through
`POST /api/v1/documents`, then retrieve its UOM with
`GET /api/v1/documents/{document_id}/uom`.

Use `GET /api/v1/search?label_code=contract_no&document_id=DOC-...` to locate
a label. Evidence includes page, block ID, source offsets and original text.
For code-convention and enterprise-scoped processing, use
`POST /api/v1/relay/process` with optional `enterprise_id`, `department_id`,
`team_id`, `project_id`, and `environment` form fields.
