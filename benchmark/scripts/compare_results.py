from __future__ import annotations

import argparse
from pathlib import Path

if __package__ in {None, ""}:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmark.scripts.common import RESULTS_ROOT, json_dump, json_load, load_yaml


def compare(baseline: Path, latest: Path) -> dict:
    base = {item["case_id"]: item for item in json_load(baseline / "summary.json", {"cases": []})["cases"]}
    current = {item["case_id"]: item for item in json_load(latest / "summary.json", {"cases": []})["cases"]}
    threshold = load_yaml(Path(__file__).resolve().parents[1] / "config" / "benchmark.yaml")["regression"]
    changes = []
    for case_id in sorted(set(base) | set(current)):
        before, after = base.get(case_id), current.get(case_id)
        flags = []
        if not before or not after:
            flags.append("case_added_or_removed")
        else:
            if after.get("expected_item_recall", 0) < before.get("expected_item_recall", 0): flags.append("expected_recall_drop")
            if after.get("evidence_valid_rate", 0) < before.get("evidence_valid_rate", 0): flags.append("evidence_drop")
            if after.get("provenance_valid_rate") != 1.0: flags.append("provenance_invalid")
            if before.get("duration_ms", 0) and after.get("duration_ms", 0) > before["duration_ms"] * (1 + threshold["duration_growth_warning"]): flags.append("duration_warning")
        changes.append({"case_id": case_id, "baseline": before, "latest": after, "flags": flags})
    report = {"regression": any(any(flag in {"expected_recall_drop","evidence_drop","provenance_invalid"} for flag in row["flags"]) for row in changes), "changes": changes}
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=RESULTS_ROOT / "baseline")
    parser.add_argument("--latest", type=Path, default=RESULTS_ROOT / "latest")
    args = parser.parse_args()
    report = compare(args.baseline, args.latest)
    json_dump(RESULTS_ROOT / "reports" / "comparison.json", report)
    print(f"regression={report['regression']}")
    return 1 if report["regression"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
