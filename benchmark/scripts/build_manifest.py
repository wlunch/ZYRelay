"""Build deterministic manifest entries and partial-annotation benchmark cases."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmark.scripts.common import (
    BENCHMARK_ROOT,
    CASES_ROOT,
    CONFIG_ROOT,
    SCANNED_ROOT,
    document_info,
    dump_yaml,
    json_dump,
    load_yaml,
    now_utc,
    relative,
    source_metadata_path,
    source_pdf_path,
    stable_benchmark_id,
    write_manifest_csv,
)


def _mode(category: str) -> str:
    return (
        "contract"
        if category == "contract"
        else "code_convention"
        if category == "code_convention"
        else "auto"
    )


def _case_expected(category: str, is_scanned: bool) -> dict:
    expected = {
        "minimum_blocks": 1,
        "minimum_conventions": 0,
        "evidence_required": True,
        "provenance_required": True,
        "block_order_required": True,
        "forbidden": ["evidence_missing", "invalid_offset"],
    }
    if category == "contract":
        expected["required_labels"] = []
        expected["contract_candidate_required"] = False
    if is_scanned:
        expected.update(
            {
                "ocr_executed": True,
                "non_empty_ocr_text": True,
                "bbox_required": True,
                "minimum_keyword_recall": 0.0,
            }
        )
    return expected


def _write_case(entry: dict) -> None:
    category = entry["category"]
    folder = "scanned_document" if entry["is_scanned"] else category
    case = {
        "case_id": entry["benchmark_id"],
        "name": entry["title"],
        "category": folder,
        "document": {"manifest_id": entry["benchmark_id"]},
        "relay": {
            "mode": entry["mode"],
            "ground_profile_id": entry["ground_profile_id"],
            "enable_ocr": bool(entry["is_scanned"]),
            "output_detail": "full",
        },
        "expected": _case_expected(category, bool(entry["is_scanned"])),
        "expected_mentions": [],
        "expected_rules": [],
    }
    dump_yaml(CASES_ROOT / folder / f"{entry['benchmark_id']}.yaml", case)


def build_manifest() -> list[dict]:
    config = load_yaml(CONFIG_ROOT / "sources.yaml")
    entries: list[dict] = []
    counters: defaultdict[str, int] = defaultdict(int)
    source_ids: dict[str, str] = {}
    for source in config["sources"]:
        path = source_pdf_path(source)
        if not path.exists():
            continue
        counters[source["category"]] += 1
        benchmark_id = stable_benchmark_id(
            source["category"], counters[source["category"]]
        )
        source_ids[source["source_id"]] = benchmark_id
        inspection = document_info(path)
        metadata = (
            __import__("json").loads(
                source_metadata_path(source).read_text(encoding="utf-8")
            )
            if source_metadata_path(source).exists()
            else {}
        )
        entries.append(
            {
                "benchmark_id": benchmark_id,
                "source_id": source["source_id"],
                "category": source["category"],
                "title": source["title"],
                "publisher": source["publisher"],
                "source_url": source["source_url"],
                "source_domain": source["source_domain"],
                "local_path": relative(path),
                "private": not source["redistribution_allowed"],
                "redistribution_allowed": source["redistribution_allowed"],
                "original_format": source["source_type"],
                "generated_format": "pdf",
                "language": source["language"],
                "sha256": inspection["sha256"],
                "size_bytes": inspection["size"],
                "page_count": inspection["page_count"],
                "is_scanned": False,
                "source_document_id": None,
                "scan_quality": None,
                "expected_case_id": benchmark_id,
                "ground_profile_id": "contract-default"
                if source["category"] == "contract"
                else "code-convention-sampling",
                "mode": _mode(source["category"]),
                "expected_features": source["expected_features"],
                "license": source["license"],
                "access_date": metadata.get(
                    "downloaded_at", metadata.get("converted_at", now_utc())
                ),
                "tool_versions": {"PyMuPDF": __import__("fitz").VersionBind},
                "notes": "Official source; binary retained locally and ignored by Git.",
            }
        )
    scans = load_yaml(CONFIG_ROOT / "benchmark.yaml").get("scan_variants", [])
    for scan in scans:
        source_id = scan["source_id"]
        candidate = list(SCANNED_ROOT.rglob(f"{scan['benchmark_id']}.pdf"))
        if not candidate or source_id not in source_ids:
            continue
        path = candidate[0]
        source = next(
            item for item in config["sources"] if item["source_id"] == source_id
        )
        inspection = document_info(path)
        entries.append(
            {
                "benchmark_id": scan["benchmark_id"],
                "source_id": source_id,
                "category": source["category"],
                "title": f"Scanned sample – {source['title']}",
                "publisher": source["publisher"],
                "source_url": source["source_url"],
                "source_domain": source["source_domain"],
                "local_path": relative(path),
                "private": True,
                "redistribution_allowed": False,
                "original_format": "pdf",
                "generated_format": "image_only_pdf",
                "language": source["language"],
                "sha256": inspection["sha256"],
                "size_bytes": inspection["size"],
                "page_count": inspection["page_count"],
                "is_scanned": True,
                "source_document_id": source_ids[source_id],
                "scan_quality": scan["quality"],
                "expected_case_id": scan["benchmark_id"],
                "ground_profile_id": "contract-default"
                if source["category"] == "contract"
                else "code-convention-sampling",
                "mode": _mode(source["category"]),
                "expected_features": [
                    *source["expected_features"],
                    "ocr",
                    "bbox",
                    "provenance",
                ],
                "license": source["license"],
                "access_date": now_utc(),
                "tool_versions": {"PyMuPDF": __import__("fitz").VersionBind},
                "notes": "Image-only OCR sample generated locally from a capped page sample; no original text layer.",
            }
        )
    entries.sort(key=lambda item: item["benchmark_id"])
    json_dump(
        BENCHMARK_ROOT / "manifest.json",
        {"version": "1.0", "generated_at": now_utc(), "entries": entries},
    )
    write_manifest_csv(entries, BENCHMARK_ROOT / "manifest.csv")
    for entry in entries:
        _write_case(entry)
    return entries


def main() -> int:
    argparse.ArgumentParser().parse_args()
    entries = build_manifest()
    print(f"manifest_entries={len(entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
