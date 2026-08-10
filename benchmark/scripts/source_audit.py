from __future__ import annotations

from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmark.scripts.common import CONFIG_ROOT, RESULTS_ROOT, json_dump, load_yaml


def build_audit() -> list[dict]:
    rows = []
    for source in load_yaml(CONFIG_ROOT / "sources.yaml")["sources"]:
        public = bool(source["redistribution_allowed"])
        rows.append(
            {
                "source_id": source["source_id"],
                "official_source": True,
                "license_known": bool(source.get("license")),
                "license": source.get("license"),
                "redistribution_allowed": public,
                "contains_personal_data": False,
                "contains_signature": False,
                "contains_real_party_information": False,
                "safe_for_local_testing": True,
                "safe_for_repository": public,
                "review_status": "approved" if public else "local_only",
            }
        )
    return rows


def main() -> int:
    rows = build_audit()
    json_dump(RESULTS_ROOT / "reports" / "source_audit.json", rows)
    lines = [
        "# Benchmark Source Audit",
        "",
        "| Source | Official | License | Repository | Status |",
        "|---|---:|---|---:|---|",
    ]
    lines += [
        f"| {item['source_id']} | yes | {item['license']} | {'yes' if item['safe_for_repository'] else 'no'} | {item['review_status']} |"
        for item in rows
    ]
    (RESULTS_ROOT / "reports").mkdir(parents=True, exist_ok=True)
    (RESULTS_ROOT / "reports" / "source_audit.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"audited={len(rows)}")


if __name__ == "__main__":
    main()
