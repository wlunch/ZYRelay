from __future__ import annotations

import argparse
from pathlib import Path

if __package__ in {None, ""}:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmark.scripts.common import RESULTS_ROOT, SCANNED_ROOT, SOURCES_ROOT, document_info, json_dump, relative


def inspect() -> list[dict]:
    entries = []
    for root in (SOURCES_ROOT, SCANNED_ROOT):
        for path in sorted(root.rglob("*.pdf")):
            info = document_info(path)
            info["local_path"] = relative(path)
            entries.append(info)
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    entries = inspect()
    json_dump(RESULTS_ROOT / "document_inspection.json", entries)
    print(f"inspected={len(entries)}")
    return 0 if all(item["parser_status"] == "ok" for item in entries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
