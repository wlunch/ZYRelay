import base64

from zyrelay.plugin.contracts import (
    OutputDetail,
    PluginInput,
    PluginOperation,
    PluginOptions,
    PluginRequest,
    PluginStatus,
    SourceType,
)
from zyrelay.plugin.mappers import PluginRequestMapper
from zyrelay.plugin.registry import PluginRegistry

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_manifest_capabilities_and_schemas(plugin_factory) -> None:
    plugin = plugin_factory()
    manifest = plugin.get_manifest()
    capabilities = plugin.get_capabilities()

    assert manifest.plugin_id == "zyrelay.doc-intelligence"
    assert manifest.version == "1.0.0"
    assert manifest.model_dump_json()
    assert capabilities.features["ocr"] is False
    assert capabilities.features["llm_optional"] is True
    assert capabilities.features["async_execution"] is False
    assert "operation" in PluginRequest.model_json_schema()["properties"]


def test_registry_and_capabilities_operation(plugin_factory) -> None:
    plugin = plugin_factory()
    registry = PluginRegistry()
    registry.register(plugin)
    assert registry.get_manifest("zyrelay.doc-intelligence").version == "1.0.0"
    assert len(registry.list_plugins()) == 1
    response = plugin.execute(PluginRequest(operation=PluginOperation.GET_CAPABILITIES))
    assert response.status == PluginStatus.COMPLETED
    assert response.result.document["capabilities"]["features"]["ocr"] is False
    registry.unregister("zyrelay.doc-intelligence")
    assert registry.list_plugins() == []


def test_request_validation_rejects_bad_inputs(plugin_factory) -> None:
    plugin = plugin_factory()
    missing = plugin.validate(PluginRequest())
    assert not missing.valid
    assert missing.errors[0].code == "missing_input"

    conflicting = plugin.validate(
        PluginRequest(
            input=PluginInput(
                source_type=SourceType.FILE,
                file_name="x.pdf",
                content_type="application/pdf",
                file_path="x.pdf",
                content_base64=base64.b64encode(b"%PDF-x").decode(),
            )
        )
    )
    assert {item.code for item in conflicting.errors} >= {
        "conflicting_input",
        "invalid_file",
    }

    unsupported = plugin.validate(
        PluginRequest(
            input=PluginInput(
                source_type=SourceType.BASE64,
                file_name="notes.txt",
                content_type="text/plain",
                content_base64=base64.b64encode(b"hello").decode(),
            )
        )
    )
    assert not unsupported.valid
    assert unsupported.errors[0].code == "unsupported_content_type"

    bad_execution = plugin.execute(PluginRequest(execution_id="EXEC-../../etc/passwd"))
    assert bad_execution.status == PluginStatus.FAILED
    assert bad_execution.errors[0].code == "invalid_request"
    assert bad_execution.execution_id != "EXEC-../../etc/passwd"

    small_config = plugin.dependencies.config.model_copy(
        update={
            "execution": plugin.dependencies.config.execution.model_copy(
                update={"max_file_size_bytes": 4}
            )
        }
    )
    oversized = PluginRequestMapper(
        small_config, plugin.dependencies.settings
    ).validate(
        PluginRequest(
            input=PluginInput(
                source_type=SourceType.BASE64,
                file_name="large.pdf",
                content_type="application/pdf",
                content_base64=base64.b64encode(b"%PDF-too-large").decode(),
            )
        )
    )
    assert oversized.errors[0].code == "file_too_large"


def test_python_sdk_output_levels_and_execution_record(
    plugin_factory, sample_docx
) -> None:
    plugin = plugin_factory()
    request = PluginRequest(
        operation=PluginOperation.PROCESS_DOCUMENT,
        input=PluginInput(
            source_type=SourceType.FILE,
            file_path=str(sample_docx),
            file_name=sample_docx.name,
            content_type=DOCX_MIME,
        ),
        options=PluginOptions(output_detail=OutputDetail.STANDARD),
    )
    response = plugin.execute(request)

    assert response.status == PluginStatus.COMPLETED
    assert response.plugin_version == "1.0.0"
    assert response.result is not None
    assert response.result.summary.document_id
    assert response.result.mentions
    assert response.result.blocks == []
    assert response.result.uom_package is None
    assert response.artifacts[0].uri.startswith("plugin://executions/")
    assert "/Users/" not in response.model_dump_json()
    assert plugin.get_result(response.execution_id) == response

    full = plugin.execute(
        request.model_copy(
            update={
                "execution_id": None,
                "options": request.options.model_copy(
                    update={"output_detail": OutputDetail.FULL}
                ),
            }
        )
    )
    assert full.result is not None
    assert full.result.blocks
    assert full.result.uom_package is not None
    assert full.trace


def test_code_convention_mode_and_artifact_security(
    plugin_factory, sample_convention_docx
) -> None:
    plugin = plugin_factory()
    response = plugin.execute(
        PluginRequest(
            operation=PluginOperation.EXTRACT_CODE_CONVENTIONS,
            input=PluginInput(
                source_type=SourceType.FILE,
                file_path=str(sample_convention_docx),
                file_name=sample_convention_docx.name,
                content_type=DOCX_MIME,
            ),
            options=PluginOptions(mode="code_convention", output_detail="standard"),
        )
    )
    assert response.status == PluginStatus.COMPLETED
    assert response.result is not None
    assert response.result.code_conventions
    assert response.result.convention_index
    assert any(
        item.get("candidate_type") == "business_object"
        for item in response.result.business_objects
    )

    reference = response.artifacts[0]
    loaded, content = plugin.dependencies.artifact_repository.load(
        response.execution_id, reference.artifact_id
    )
    assert loaded.checksum == reference.checksum
    assert content.startswith(b"{")
    try:
        plugin.dependencies.artifact_repository.load(
            "../../etc/passwd", reference.artifact_id
        )
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal must be rejected")
