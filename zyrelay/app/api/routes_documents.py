from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from zyrelay.app.services import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _service(request: Request) -> DocumentService:
    return request.app.state.document_service


@router.post("", status_code=201)
async def upload_document(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    document_id, task_id = _service(request).process(
        file.filename or "upload", content, request_id=request.state.request_id
    )
    return {
        "document_id": document_id,
        "task_id": task_id,
        "status": "completed",
    }


@router.get("/{document_id}")
def get_document(document_id: str, request: Request):
    return _service(request).get_document(document_id)


@router.get("/{document_id}/blocks")
def get_blocks(document_id: str, request: Request):
    return {
        "document_id": document_id,
        "blocks": _service(request).get_blocks(document_id),
    }


@router.get("/{document_id}/labels")
def get_labels(document_id: str, request: Request):
    return {
        "document_id": document_id,
        "mentions": _service(request).get_mentions(document_id),
    }


@router.get("/{document_id}/semantic-index")
def get_semantic_index(document_id: str, request: Request):
    return _service(request).get_semantic_index(document_id)


@router.get("/{document_id}/semantic-objects")
def get_semantic_objects(
    document_id: str,
    request: Request,
    object_type: str | None = None,
    category: str | None = None,
    language: str | None = None,
    page: int | None = Query(default=None, ge=1),
):
    return {
        "document_id": document_id,
        "objects": _service(request).get_semantic_objects(
            document_id,
            object_type=object_type,
            category=category,
            language=language,
            page=page,
        ),
    }


def _typed_semantic_objects(document_id: str, request: Request, object_type: str):
    return {
        "document_id": document_id,
        "objects": _service(request).get_semantic_objects(
            document_id, object_type=object_type
        ),
    }


@router.get("/{document_id}/entities")
def get_entities(document_id: str, request: Request):
    return _typed_semantic_objects(document_id, request, "entity")


@router.get("/{document_id}/rules")
def get_rules(document_id: str, request: Request):
    return _typed_semantic_objects(document_id, request, "rule")


@router.get("/{document_id}/relations")
def get_relations(document_id: str, request: Request):
    return _typed_semantic_objects(document_id, request, "relation")


@router.get("/{document_id}/events")
def get_events(document_id: str, request: Request):
    return _typed_semantic_objects(document_id, request, "event")


@router.get("/{document_id}/evidence")
def get_evidence(document_id: str, request: Request):
    return _typed_semantic_objects(document_id, request, "evidence")


@router.get("/{document_id}/business-objects")
def get_business_objects(document_id: str, request: Request):
    return _typed_semantic_objects(document_id, request, "business_object")


@router.get("/{document_id}/semantic-objects/export")
def export_semantic_objects(
    document_id: str,
    request: Request,
    format: str = Query(default="json", pattern="^(json|json-ld|graph-json)$"),
):
    try:
        return _service(request).export_semantic_objects(document_id, format)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="unsupported_semantic_export_format"
        ) from exc


@router.get("/{document_id}/uom")
def get_uom(document_id: str, request: Request):
    return _service(request).get_package(document_id)
