from zyrelay.benchmark_cli import compare_models


def test_compare_models_reports_latency_and_regression() -> None:
    left = [
        {
            "resource_id": "noop-ocr",
            "status": "completed",
            "duration_ms": 1,
            "fallback_used": False,
        }
    ]
    right = [
        {
            "resource_id": "paddleocr",
            "status": "completed",
            "duration_ms": 10,
            "fallback_used": False,
        }
    ]
    result = compare_models(left, right, "noop-ocr", "paddleocr")
    assert result["latency_difference_ms"] == 9.0
    assert result["accuracy_difference"] == 0.0
    assert result["regressions"] == []
