from __future__ import annotations

import argparse
from pathlib import Path

if __package__ in {None, ""}:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmark.scripts.common import BENCHMARK_ROOT, CASES_ROOT, RESULTS_ROOT, json_dump, json_load, load_yaml


def validate() -> dict:
    manifest = json_load(BENCHMARK_ROOT / "manifest.json", {"entries": []})
    entries = manifest["entries"]
    ids = [item["benchmark_id"] for item in entries]
    errors: list[str] = []
    if len(ids) != len(set(ids)):
        errors.append("duplicate_manifest_id")
    for entry in entries:
        case_folder = "scanned_document" if entry["is_scanned"] else entry["category"]
        case_path = CASES_ROOT / case_folder / f"{entry['benchmark_id']}.yaml"
        if not case_path.exists():
            errors.append(f"missing_case:{entry['benchmark_id']}")
        if entry["is_scanned"] and not entry["local_path"].startswith("benchmark/scanned/"):
            errors.append(f"scan_outside_scanned:{entry['benchmark_id']}")
    counts = {category: sum(1 for item in entries if item["category"] == category and not item["is_scanned"]) for category in ["code_convention", "contract", "enterprise_policy", "api_specification"]}
    scan_count = sum(1 for item in entries if item["is_scanned"])
    report = {"valid": not errors, "entry_count": len(entries), "counts": counts, "scan_count": scan_count, "errors": errors}
    json_dump(RESULTS_ROOT / "reports" / "dataset_validation.json", report)
    return report


def main() -> int:
    argparse.ArgumentParser().parse_args()
    report = validate()
    print(report)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
