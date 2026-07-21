from fastapi import APIRouter, Query, Request

from zyrelay.app.services import DocumentService
from zyrelay.app.conventions import (
    ConventionStatus,
    RequirementLevel,
    RuleType,
)


router = APIRouter(tags=["code-conventions"])


def _service(request: Request) -> DocumentService:
    return request.app.state.document_service


@router.get("/api/v1/documents/{document_id}/code-conventions")
def get_code_conventions(
    document_id: str,
    request: Request,
    category: RuleType | None = None,
    language: str | None = None,
    requirement_level: RequirementLevel | None = None,
    status: ConventionStatus | None = None,
):
    conventions = _service(request).get_code_conventions(
        document_id,
        category=category,
        language=language,
        requirement_level=requirement_level,
        status=status,
    )
    return {
        "document_id": document_id,
        "count": len(conventions),
        "code_conventions": conventions,
    }


@router.get("/api/v1/documents/{document_id}/convention-index")
def get_convention_index(document_id: str, request: Request):
    return _service(request).get_convention_index(document_id)


@router.get("/api/v1/conventions/search")
def search_conventions(
    request: Request,
    document_id: str | None = None,
    category: RuleType | None = None,
    language: str | None = None,
    requirement_level: RequirementLevel | None = None,
    keyword: str | None = Query(default=None, min_length=1),
    executable: bool | None = None,
):
    results = _service(request).search_conventions(
        document_id=document_id,
        category=category,
        language=language,
        requirement_level=requirement_level,
        keyword=keyword,
        executable=executable,
    )
    return {"count": len(results), "results": results}
