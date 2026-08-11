from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter(include_in_schema=False)
_DEMO_ROOT = Path(__file__).resolve().parents[1] / "demo"


@router.get("/demo", include_in_schema=False)
def document_intelligence_demo() -> FileResponse:
    """Serve the local, API-driven Relay demonstration page."""

    return FileResponse(_DEMO_ROOT / "index.html")
