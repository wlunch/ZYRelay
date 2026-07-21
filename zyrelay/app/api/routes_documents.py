from fastapi import APIRouter, File, Request, UploadFile

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
    return {"document_id": document_id, "blocks": _service(request).get_blocks(document_id)}


@router.get("/{document_id}/labels")
def get_labels(document_id: str, request: Request):
    return {
        "document_id": document_id,
        "mentions": _service(request).get_mentions(document_id),
    }


@router.get("/{document_id}/semantic-index")
def get_semantic_index(document_id: str, request: Request):
    return _service(request).get_semantic_index(document_id)


@router.get("/{document_id}/uom")
def get_uom(document_id: str, request: Request):
    return _service(request).get_package(document_id)

