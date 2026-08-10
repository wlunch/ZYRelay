from __future__ import annotations

import json

import fitz
import pytest

from benchmark.scripts.build_manifest import _case_expected
from benchmark.scripts.common import (
    document_info,
    json_dump,
    stable_benchmark_id,
    validate_source_url,
)
from benchmark.scripts.compare_results import compare
from benchmark.scripts.create_scanned_pdf import create_scanned_pdf
from benchmark.scripts.finalize_results import finalize
from benchmark.scripts.run_benchmark import _evaluate
from benchmark.scripts.source_audit import build_audit
from benchmark.scripts.validate_dataset import validate


def test_source_config_uses_https_whitelist() -> None:
    validate_source_url(
        {
            "source_id": "ok",
            "source_url": "https://example.com/a.pdf",
            "source_domain": "example.com",
        }
    )
    with pytest.raises(ValueError):
        validate_source_url(
            {
                "source_id": "bad",
                "source_url": "http://example.com/a.pdf",
                "source_domain": "example.com",
            }
        )
    with pytest.raises(ValueError):
        validate_source_url(
            {
                "source_id": "bad",
                "source_url": "https://evil.example/a.pdf",
                "source_domain": "example.com",
            }
        )


def test_manifest_ids_and_dataset_validation() -> None:
    assert stable_benchmark_id("code_convention", 6) == "BC-CODE-006"
    assert stable_benchmark_id("scanned_document", 1) == "BC-SCAN-001"
    report = validate()
    assert report["valid"] is True
    assert report["entry_count"] >= 23
    assert report["scan_count"] >= 6


def test_scan_generation_removes_text_and_keeps_images(tmp_path) -> None:
    source = tmp_path / "native.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Example OCR text")
    document.save(source)
    document.close()
    target = tmp_path / "scan.pdf"
    metadata = create_scanned_pdf(source, target, quality="medium")
    info = document_info(target)
    assert metadata["extractable_text_length"] == 0
    assert info["is_scanned"] is True
    assert info["pages_with_images"] == 1


def test_expected_matcher_checks_evidence_offsets_and_ocr() -> None:
    case = {
        "expected": {**_case_expected("code_convention", True), "minimum_blocks": 1}
    }
    result = {
        "status": "completed",
        "warnings": [],
        "errors": [],
        "metrics": {},
        "result": {
            "blocks": [
                {
                    "sequence": 0,
                    "text": "OCR text",
                    "metadata": {"source_method": "ocr", "bbox": [1, 2, 3, 4]},
                }
            ],
            "code_conventions": [
                {"source_evidence": {"page_no": 1}, "provenance_id": "PROV-1"}
            ],
            "model_executions": [{"model_name": "paddleocr"}],
        },
    }
    evaluation = _evaluate(case, result)
    assert evaluation["expected_item_recall"] == 1.0
    assert all(evaluation["checks"].values())


def test_source_audit_has_no_personal_data_flags() -> None:
    rows = build_audit()
    assert len(rows) >= 17
    assert all(
        row["official_source"] and not row["contains_personal_data"] for row in rows
    )


def test_finalize_and_comparison_detect_semantic_regression(tmp_path) -> None:
    baseline = tmp_path / "baseline"
    case = baseline / "BC-CODE-001"
    case.mkdir(parents=True)
    json_dump(
        case / "evaluation.json",
        {
            "expected_item_recall": 1.0,
            "evidence_valid_rate": 1.0,
            "provenance_valid_rate": 1.0,
        },
    )
    json_dump(
        case / "relay_result.json",
        {"status": "completed", "metrics": {"total_duration_ms": 20}},
    )
    json_dump(case / "models.json", [])
    report = finalize(baseline)
    assert report["summary"]["successful_cases"] == 1
    latest = tmp_path / "latest"
    latest.mkdir()
    latest_summary = json.loads((baseline / "summary.json").read_text())
    latest_summary["cases"][0]["expected_item_recall"] = 0.0
    json_dump(latest / "summary.json", latest_summary)
    comparison = compare(baseline, latest)
    assert comparison["regression"] is True
