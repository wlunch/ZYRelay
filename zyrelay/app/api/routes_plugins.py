from __future__ import annotations

import base64
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from zyrelay.plugin import PluginInput, PluginOptions, PluginRequest
from zyrelay.plugin.contracts import (
    OutputDetail,
    PluginMode,
    PluginOperation,
    PluginResponse,
    PluginStatus,
    SourceType,
)
from zyrelay.plugin.registry import PluginRegistry

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _registry(request: Request) -> PluginRegistry:
    return request.app.state.plugin_registry


def _lifecycle(request: Request):
    return request.app.state.plugin_lifecycle


def _plugin(request: Request, plugin_id: str):
    try:
        return _registry(request).get(plugin_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="plugin_not_found") from exc


def _http_request(value: PluginRequest) -> PluginRequest:
    metadata = {**value.metadata, "_transport": "http"}
    return value.model_copy(update={"metadata": metadata})


def _status_code(response: PluginResponse) -> int:
    if response.status != PluginStatus.FAILED:
        return 200
    codes = {item.code for item in response.errors}
    if codes & {"result_not_found", "artifact_not_found"}:
        return 404
    if "file_too_large" in codes:
        return 413
    if "unsupported_content_type" in codes:
        return 415
    if codes & {
        "invalid_request",
        "missing_input",
        "conflicting_input",
        "invalid_file",
        "unsupported_operation",
    }:
        return 400
    return 500


def _response(value: PluginResponse) -> Response:
    return Response(
        content=value.model_dump_json(exclude_none=True),
        status_code=_status_code(value),
        media_type="application/json",
    )


@router.get("")
def list_plugins(request: Request):
    return [
        plugin.get_manifest().model_dump(mode="json")
        for plugin in _registry(request).list_plugins()
    ]


@router.get("/{plugin_id}")
def get_manifest(plugin_id: str, request: Request):
    return _plugin(request, plugin_id).get_manifest()


@router.get("/{plugin_id}/capabilities")
def get_capabilities(plugin_id: str, request: Request):
    return _plugin(request, plugin_id).get_capabilities()


@router.post("/{plugin_id}/validate")
def validate_request(plugin_id: str, value: PluginRequest, request: Request):
    return _plugin(request, plugin_id).validate(_http_request(value))


@router.post("/{plugin_id}/execute")
def execute(plugin_id: str, value: PluginRequest, request: Request):
    if not _lifecycle(request).enabled(plugin_id):
        raise HTTPException(status_code=503, detail="plugin_disabled")
    return _response(_plugin(request, plugin_id).execute(_http_request(value)))


@router.post("/{plugin_id}/execute-file")
async def execute_file(
    plugin_id: str,
    request: Request,
    file: UploadFile = File(...),
    mode: PluginMode = Form(PluginMode.AUTO),
    output_detail: OutputDetail = Form(OutputDetail.STANDARD),
    enable_llm: bool = Form(False),
    enable_fuzzy_matching: bool = Form(False),
):
    if not _lifecycle(request).enabled(plugin_id):
        raise HTTPException(status_code=503, detail="plugin_disabled")
    content = await file.read()
    file_name = Path(file.filename or "upload").name
    content_type = file.content_type or _content_type(file_name)
    value = PluginRequest(
        operation=PluginOperation.PROCESS_DOCUMENT,
        input=PluginInput(
            source_type=SourceType.BASE64,
            file_name=file_name,
            content_type=content_type,
            content_base64=base64.b64encode(content).decode("ascii"),
        ),
        options=PluginOptions(
            mode=mode,
            output_detail=output_detail,
            enable_llm=enable_llm,
            enable_fuzzy_matching=enable_fuzzy_matching,
        ),
        metadata={"_transport": "http"},
    )
    return _response(_plugin(request, plugin_id).execute(value))


@router.get("/{plugin_id}/schemas/input")
def input_schema(plugin_id: str, request: Request):
    plugin = _plugin(request, plugin_id)
    return plugin.dependencies.manifest_provider.input_schema()


@router.get("/{plugin_id}/schemas/output")
def output_schema(plugin_id: str, request: Request):
    plugin = _plugin(request, plugin_id)
    return plugin.dependencies.manifest_provider.output_schema()


@router.get("/{plugin_id}/schemas/configuration")
def configuration_schema(plugin_id: str, request: Request):
    plugin = _plugin(request, plugin_id)
    return plugin.dependencies.config.__class__.model_json_schema()


@router.get("/{plugin_id}/health")
def plugin_health(plugin_id: str, request: Request):
    _plugin(request, plugin_id)
    return _lifecycle(request).health(plugin_id)


@router.post("/{plugin_id}/lifecycle/validate")
def validate_manifest(plugin_id: str, request: Request):
    plugin = _plugin(request, plugin_id)
    return _lifecycle(request).validate_manifest(plugin.get_manifest()).__dict__


@router.post("/{plugin_id}/lifecycle/install")
def install_plugin(plugin_id: str, request: Request):
    """Validate/register a trusted in-process plugin; never downloads code."""
    plugin = _plugin(request, plugin_id)
    return _lifecycle(request).install(plugin).__dict__


@router.post("/{plugin_id}/lifecycle/update")
def update_plugin(plugin_id: str, request: Request):
    """Revalidate/re-register the installed plugin manifest atomically."""
    plugin = _plugin(request, plugin_id)
    return _lifecycle(request).update(plugin).__dict__


@router.post("/{plugin_id}/lifecycle/disable")
def disable_plugin(plugin_id: str, request: Request):
    _lifecycle(request).disable(plugin_id)
    return {"plugin_id": plugin_id, "enabled": False}


@router.post("/{plugin_id}/lifecycle/enable")
def enable_plugin(plugin_id: str, request: Request):
    _lifecycle(request).enable(plugin_id)
    return {"plugin_id": plugin_id, "enabled": True}


@router.get("/{plugin_id}/executions/{execution_id}")
def get_execution(plugin_id: str, execution_id: str, request: Request):
    return _response(_plugin(request, plugin_id).get_result(execution_id))


@router.get("/{plugin_id}/executions/{execution_id}/artifacts")
def list_artifacts(plugin_id: str, execution_id: str, request: Request):
    plugin = _plugin(request, plugin_id)
    try:
        return plugin.dependencies.artifact_repository.list(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_execution_id") from exc


@router.get("/{plugin_id}/executions/{execution_id}/artifacts/{artifact_id}")
def get_artifact(
    plugin_id: str,
    execution_id: str,
    artifact_id: str,
    request: Request,
):
    plugin = _plugin(request, plugin_id)
    try:
        reference, content = plugin.dependencies.artifact_repository.load(
            execution_id, artifact_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_artifact_id") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="artifact_not_found") from exc
    return Response(
        content=content,
        media_type=reference.media_type,
        headers={
            "Content-Disposition": (f'attachment; filename="{reference.file_name}"')
        },
    )


def _content_type(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".docx":
        return DOCX_MIME
    return "application/octet-stream"
