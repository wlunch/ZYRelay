from __future__ import annotations

from pathlib import Path

import pytest

from zyrelay.app.core.config import PROJECT_ROOT
from zyrelay.relay import RelayService, RelayRequest
from zyrelay.relay.models import RelayInput, RelayStatus


@pytest.mark.model_integration
@pytest.mark.slow
def test_real_paddleocr_scanned_pdf_has_traceable_conventions() -> None:
    """Runs the pre-provisioned local PaddleOCR model; it never downloads a model."""

    sample = PROJECT_ROOT / "examples" / "team_code_convention_scanned.pdf"
    if not sample.is_file():
        pytest.skip("缺少真实扫描 PDF 样本")
    service = RelayService()
    health = service.resources.get("paddleocr").health_check()
    if not health.available:
        pytest.skip("PaddleOCR 或其离线模型缓存未就绪")

    result = service.process(
        RelayRequest(
            input=RelayInput(file_name=sample.name, file_path=str(sample)),
            output_detail="full",
        )
    )

    assert result.status == RelayStatus.COMPLETED
    execution = result.result["model_executions"][0]
    assert execution["resource_id"] == "paddleocr"
    assert execution["fallback_used"] is False
    assert execution["details"]["line_count"] > 0
    assert len(execution["details"]["page_metrics"]) == 2
    blocks = result.result["blocks"]
    assert blocks
    assert all(block["metadata"]["source_method"] == "ocr" for block in blocks)
    assert all(block["metadata"]["model_execution_id"] == execution["model_execution_id"] for block in blocks)
    assert any(block["metadata"]["bbox"][2] > block["metadata"]["bbox"][0] for block in blocks)
    assert any("System.out.println" in block["text"] for block in blocks)
    assert any("80" in block["text"] for block in blocks)
    candidates = result.result["code_conventions"]
    assert candidates
    assert any(item["rule_expression"]["expected"] == 80 for item in candidates if item["rule_expression"])
    provenance = service.get_provenance(candidates[0]["provenance_id"])
    assert provenance.model_execution_ids == [execution["model_execution_id"]]
    assert provenance.evidence[0]["metadata"]["resource_id"] == "paddleocr"
    assert provenance.model_details[0]["details"]["paddleocr_version"] == "3.7.0"
