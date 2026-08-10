from types import SimpleNamespace

from zyrelay.app.models import SourceDocument
from zyrelay.relay.model_router import ModelRouter
from zyrelay.relay.models import RelayInput, RelayMode, RelayRequest


def _context(file_type: str, *, requires_ocr: bool = False, blocks=None):
    document = SourceDocument(
        document_id="DOC-ROUTER-0001",
        file_name=f"sample.{file_type}",
        file_type=file_type,
        file_size=1,
        sha256="a" * 64,
        requires_ocr=requires_ocr,
    )
    return SimpleNamespace(
        document=document,
        parsed_document=None,
        blocks=blocks or [],
        labels=[],
        mentions=[],
    )


def _request(mode: RelayMode = RelayMode.CODE_CONVENTION, **kwargs):
    return RelayRequest(
        input=RelayInput(file_name="sample.docx", content_base64="eA=="),
        mode=mode,
        **kwargs,
    )


def test_router_skips_docx_visual_and_ocr_models() -> None:
    router = ModelRouter()
    context = _context("docx")
    assert (
        router.decide(
            "ocr", context=context, request=_request(), resource_id="paddleocr"
        ).reason
        == "not_pdf"
    )
    layout = router.decide(
        "layout", context=context, request=_request(), resource_id="doclayout-yolo"
    )
    assert layout.should_run is False
    assert layout.reason == "docx_logical_blocks_are_sufficient"
    classifier = router.decide(
        "document_classifier",
        context=context,
        request=_request(),
        resource_id="minilm-document-classifier",
    )
    assert classifier.reason == "document_mode_already_known"


def test_router_runs_only_scanned_ocr_and_code_detection() -> None:
    router = ModelRouter()
    text_pdf = _context("pdf")
    assert not router.decide(
        "ocr", context=text_pdf, request=_request(), resource_id="paddleocr"
    ).should_run
    assert router.decide(
        "layout", context=text_pdf, request=_request(), resource_id="heuristic-layout"
    ).should_run
    scanned = _context("pdf", requires_ocr=True)
    assert router.decide(
        "ocr", context=scanned, request=_request(), resource_id="paddleocr"
    ).should_run
    assert router.decide(
        "code_detection",
        context=scanned,
        request=_request(),
        resource_id="tree-sitter-code",
    ).should_run


def test_enterprise_profile_can_disable_model(relay_service) -> None:
    plan = relay_service.resource_planner.build(
        execution_id="EXEC-ROUTER-0001",
        enterprise_id="enterprise-b",
        requested_profile_id=None,
        recommended_profile_id=None,
    )
    assert plan.bindings["ner"] == "disabled"
    record = next(item for item in plan.selection_records if item.capability == "ner")
    assert record.enabled is False
    assert record.skip_reason == "enterprise_profile_disabled"


def test_router_records_skips_and_metrics(
    relay_service, sample_convention_docx
) -> None:
    result = relay_service.process(
        RelayRequest(
            input=RelayInput(
                file_name=sample_convention_docx.name,
                file_path=str(sample_convention_docx),
            ),
            mode=RelayMode.CODE_CONVENTION,
            output_detail="full",
        )
    )
    skipped = [
        item
        for item in result.result["model_executions"]
        if item["status"] == "skipped"
    ]
    assert skipped
    assert result.metrics["model_skipped_count"] == len(skipped)
    assert result.metrics["model_executed_count"] > 0


def test_text_contract_pdf_skips_ocr(relay_service, sample_pdf) -> None:
    result = relay_service.process(
        RelayRequest(
            input=RelayInput(file_name=sample_pdf.name, file_path=str(sample_pdf)),
            mode=RelayMode.CONTRACT,
            output_detail="full",
        )
    )
    ocr = next(
        item
        for item in result.result["model_executions"]
        if item["capability"] == "ocr"
    )
    assert ocr["status"] == "skipped"
    assert ocr["details"]["routing"]["reason"] == "native_text_available"
