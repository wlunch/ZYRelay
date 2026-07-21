from zyrelay.app.core.exceptions import ParseFailedError
from zyrelay.plugin.contracts import (
    OutputDetail,
    PluginInput,
    PluginOperation,
    PluginOptions,
    PluginRequest,
    PluginStatus,
    SourceType,
)
from zyrelay.plugin.error_mapper import map_exception


DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _request(path, **options) -> PluginRequest:
    return PluginRequest(
        input=PluginInput(
            source_type=SourceType.FILE,
            file_path=str(path),
            file_name=path.name,
            content_type=DOCX_MIME,
        ),
        options=PluginOptions(**options),
    )


def test_old_and_plugin_entries_produce_same_document(
    plugin_factory, sample_convention_docx
) -> None:
    plugin = plugin_factory()
    service = plugin.dependencies.document_service
    document_id, _ = service.process(
        sample_convention_docx.name, sample_convention_docx.read_bytes()
    )
    legacy = service.get_package(document_id)

    response = plugin.execute(
        _request(sample_convention_docx, output_detail=OutputDetail.FULL)
    )
    assert response.result is not None
    assert response.result.summary.document_id == document_id
    assert len(response.result.code_conventions) == len(
        legacy.som.code_conventions
    )
    assert response.result.code_conventions[0]["rule_expression"] == (
        legacy.som.code_conventions[0].rule_expression.model_dump(mode="json")
    )
    assert response.result.code_conventions[0]["source_evidence"] == [
        item.model_dump(mode="json")
        for item in legacy.som.code_conventions[0].source_evidence
    ]


def test_operations_overrides_and_llm_failure_warning(
    plugin_factory, sample_docx
) -> None:
    plugin = plugin_factory()
    validation = plugin.execute(
        _request(sample_docx).model_copy(
            update={"operation": PluginOperation.VALIDATE_DOCUMENT}
        )
    )
    assert validation.status == PluginStatus.COMPLETED
    assert validation.result.document["valid"] is True

    response = plugin.execute(
        _request(
            sample_docx,
            config_overrides={
                "output_detail": "summary",
                "enable_llm": True,
            },
        )
    )
    assert response.status == PluginStatus.PARTIAL
    assert response.result is not None
    assert response.result.blocks == []
    assert response.result.mentions == []
    assert any(item.code == "llm_enrichment_failed" for item in response.warnings)

    fetched = plugin.execute(
        PluginRequest(
            operation=PluginOperation.GET_UOM,
            input=PluginInput(
                source_type=SourceType.DOCUMENT,
                document_id=response.result.summary.document_id,
            ),
            options=PluginOptions(output_detail=OutputDetail.SUMMARY),
        )
    )
    assert fetched.status == PluginStatus.PARTIAL
    assert fetched.result.summary.document_id == response.result.summary.document_id


def test_error_mapping_is_stable_and_hides_traceback() -> None:
    error = map_exception(
        ParseFailedError("解析器内部失败", details={"page": 1})
    )
    assert error.code == "parse_failed"
    assert error.stage == "parsing"
    assert "traceback" not in error.model_dump_json().lower()
