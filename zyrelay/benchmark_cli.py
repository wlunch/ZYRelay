"""Small CLI for comparing resource-model records produced by benchmarks."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path


def _load(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else value.get("models", [])


def _summary(records: list[dict], resource_id: str) -> dict:
    selected = [item for item in records if item.get("resource_id") == resource_id]
    completed = [item for item in selected if item.get("status") == "completed"]
    return {
        "resource_id": resource_id,
        "runs": len(selected),
        "completed": len(completed),
        "completion_rate": round(len(completed) / len(selected), 4)
        if selected
        else 0.0,
        "average_latency_ms": round(
            sum(float(item.get("duration_ms", 0)) for item in completed)
            / len(completed),
            4,
        )
        if completed
        else 0.0,
        "fallback_count": sum(bool(item.get("fallback_used")) for item in selected),
        "resource_usage": {"model_execution_count": len(selected)},
    }


def compare_models(
    left_records: list[dict], right_records: list[dict], left: str, right: str
) -> dict:
    left_summary, right_summary = (
        _summary(left_records, left),
        _summary(right_records, right),
    )
    return {
        "left": left_summary,
        "right": right_summary,
        "accuracy_difference": round(
            right_summary["completion_rate"] - left_summary["completion_rate"], 4
        ),
        "latency_difference_ms": round(
            right_summary["average_latency_ms"] - left_summary["average_latency_ms"], 4
        ),
        "resource_usage": {
            "left": left_summary["resource_usage"],
            "right": right_summary["resource_usage"],
        },
        "regressions": [
            name
            for name, condition in {
                "completion_rate_drop": right_summary["completion_rate"]
                < left_summary["completion_rate"],
                "fallback_increase": right_summary["fallback_count"]
                > left_summary["fallback_count"],
            }.items()
            if condition
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zyrelay")
    top = parser.add_subparsers(dest="command", required=True)
    benchmark = top.add_parser("benchmark")
    commands = benchmark.add_subparsers(dest="benchmark_command", required=True)
    compare = commands.add_parser("compare-models")
    compare.add_argument("--left-file", type=Path, required=True)
    compare.add_argument("--right-file", type=Path, required=True)
    compare.add_argument("--left-resource", required=True)
    compare.add_argument("--right-resource", required=True)
    args = parser.parse_args(argv)
    result = compare_models(
        _load(args.left_file),
        _load(args.right_file),
        args.left_resource,
        args.right_resource,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
