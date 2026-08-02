from __future__ import annotations

import base64
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from zyrelay.relay import RelayRequest, RelayService
from zyrelay.relay.models import RelayInput, RelayMode


router = APIRouter(prefix="/api/v1/relay", tags=["relay"])


def _service(request: Request) -> RelayService:
    return request.app.state.relay_service


@router.post("/process")
async def process(
    request: Request,
    file: UploadFile = File(...),
    enterprise_id: str = Form("default"),
    team_id: str | None = Form(None),
    project_id: str | None = Form(None),
    mode: RelayMode = Form(RelayMode.CODE_CONVENTION),
    ground_profile_id: str | None = Form(None),
    resource_profile_id: str | None = Form(None),
    enable_ocr: bool = Form(True),
    enable_layout_model: bool = Form(False),
    enable_llm: bool = Form(False),
    output_detail: str = Form("standard"),
):
    if output_detail not in {"summary", "standard", "full"}:
        raise HTTPException(status_code=422, detail="invalid_output_detail")
    content = await file.read()
    relay_request = RelayRequest(
        request_id=request.state.request_id,
        enterprise_id=enterprise_id,
        team_id=team_id,
        project_id=project_id,
        mode=mode,
        ground_profile_id=ground_profile_id,
        resource_profile_id=resource_profile_id,
        enable_ocr=enable_ocr,
        enable_layout_model=enable_layout_model,
        enable_llm=enable_llm,
        output_detail=output_detail,
        input=RelayInput(
            file_name=Path(file.filename or "upload").name,
            content_type=file.content_type,
            content_base64=base64.b64encode(content).decode("ascii"),
        ),
        metadata={"_transport": "http"},
    )
    result = _service(request).process(relay_request)
    return result


@router.get("/executions/{execution_id}")
def get_execution(execution_id: str, request: Request):
    return _load_or_404(lambda: _service(request).get_execution(execution_id))


@router.get("/executions/{execution_id}/ground")
def get_ground(execution_id: str, request: Request):
    return _load_or_404(lambda: _service(request).get_ground(execution_id))


@router.get("/executions/{execution_id}/resources")
def get_resources(execution_id: str, request: Request):
    return _load_or_404(lambda: _service(request).get_resources(execution_id))


@router.get("/executions/{execution_id}/models")
def get_models(execution_id: str, request: Request):
    return _service(request).get_models(execution_id)


@router.get("/provenance/{provenance_id}")
def get_provenance(provenance_id: str, request: Request):
    return _load_or_404(lambda: _service(request).get_provenance(provenance_id))


@router.get("/conventions/{convention_id}/provenance")
def get_convention_provenance(convention_id: str, request: Request):
    return _load_or_404(
        lambda: _service(request).get_convention_provenance(convention_id)
    )


def _load_or_404(loader):
    try:
        return loader()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="relay_record_not_found") from exc
