from fastapi import APIRouter, Query, Request

from zyrelay.app.services import DocumentService

router = APIRouter(tags=["search"])


@router.get("/api/v1/search")
def search(
    request: Request,
    label_code: str = Query(min_length=1),
    document_id: str | None = None,
    value: str | None = None,
):
    service: DocumentService = request.app.state.document_service
    results = service.search(
        label_code=label_code, document_id=document_id, value=value
    )
    return {"count": len(results), "results": results}
