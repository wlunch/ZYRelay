"""Create a portable benchmark summary from independently executed cases."""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmark.scripts.common import (
    RESULTS_ROOT,
    json_dump,
    json_load,
    now_utc,
    sha256_file,
)


def _git_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).resolve().parents[2],
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _first_model_version(case_dir: Path) -> str | None:
    models = json_load(case_dir / "models.json", [])
    for model in models:
        if model.get("model_name"):
            return f"{model['model_name']}@{model.get('model_version', 'unknown')}"
    return None


def finalize(output: Path) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    model_versions: set[str] = set()
    for evaluation_path in sorted(output.glob("BC-*/evaluation.json")):
        case_dir = evaluation_path.parent
        evaluation = json_load(evaluation_path, {})
        relay_result = json_load(case_dir / "relay_result.json", {})
        record = {
            "case_id": case_dir.name,
            "status": relay_result.get("status", "unknown"),
            **evaluation,
            "duration_ms": relay_result.get("metrics", {}).get("total_duration_ms", 0),
        }
        cases.append(record)
        if version := _first_model_version(case_dir):
            model_versions.add(version)
    total_duration = sum(int(item.get("duration_ms") or 0) for item in cases)
    config_files = [
        Path(__file__).resolve().parents[1] / "config" / "sources.yaml",
        Path(__file__).resolve().parents[1] / "config" / "benchmark.yaml",
        Path(__file__).resolve().parents[1] / "manifest.json",
    ]
    report = {
        "generated_at": now_utc(),
        "relay_version": __import__("zyrelay").__version__,
        "git_revision": _git_revision(),
        "python": sys.version,
        "platform": platform.platform(),
        "model_versions": sorted(model_versions),
        "input_hashes": {
            path.name: sha256_file(path) for path in config_files if path.exists()
        },
        "summary": {
            "case_count": len(cases),
            "successful_cases": sum(
                item.get("status") in {"completed", "partial"} for item in cases
            ),
            "failed_cases": sum(item.get("status") == "failed" for item in cases),
            "total_duration_ms": total_duration,
            "expected_item_recall": round(
                sum(float(item.get("expected_item_recall", 0)) for item in cases)
                / len(cases),
                4,
            )
            if cases
            else 0.0,
            "evidence_valid_rate": round(
                sum(float(item.get("evidence_valid_rate", 0)) for item in cases)
                / len(cases),
                4,
            )
            if cases
            else 0.0,
            "provenance_valid_rate": round(
                sum(float(item.get("provenance_valid_rate", 0)) for item in cases)
                / len(cases),
                4,
            )
            if cases
            else 0.0,
        },
        "cases": cases,
    }
    json_dump(output / "summary.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=RESULTS_ROOT / "baseline")
    args = parser.parse_args()
    report = finalize(args.output)
    print(
        f"cases={report['summary']['case_count']} success={report['summary']['successful_cases']}"
    )
    return 0 if report["summary"]["failed_cases"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
