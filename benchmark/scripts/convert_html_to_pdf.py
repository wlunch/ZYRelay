"""Convert downloaded official HTML references to PDF without rewriting content."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmark.scripts.common import (
    CONFIG_ROOT, json_dump, now_utc, sha256_file, source_by_id,
    source_download_path, source_metadata_path, source_pdf_path, load_yaml,
)


def find_soffice() -> str:
    return (
        shutil.which("soffice")
        or "/Users/lunchw/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/soffice"
    )


def convert_source(source: dict, force: bool = False) -> dict:
    if source["source_type"] != "html":
        return {"source_id": source["source_id"], "status": "skipped", "reason": "not_html"}
    html_path = source_download_path(source)
    target = source_pdf_path(source)
    if not html_path.exists():
        return {"source_id": source["source_id"], "status": "failed", "error": "download_missing"}
    if target.exists() and not force:
        return {"source_id": source["source_id"], "status": "existing", "path": str(target)}
    target.parent.mkdir(parents=True, exist_ok=True)
    office = find_soffice()
    if not Path(office).exists() and not shutil.which("soffice"):
        return {"source_id": source["source_id"], "status": "failed", "error": "soffice_not_found"}
    with tempfile.TemporaryDirectory(prefix="zyrelay-html-pdf-") as directory:
        work = Path(directory)
        input_html = work / f"{source['source_id']}.html"
        input_html.write_bytes(html_path.read_bytes())
        command = [office, "--headless", "--convert-to", "pdf:writer_pdf_Export", "--outdir", str(work), str(input_html)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        output = work / f"{source['source_id']}.pdf"
        if completed.returncode != 0 or not output.exists():
            return {"source_id": source["source_id"], "status": "failed", "error": (completed.stderr or completed.stdout or "pdf_conversion_failed")[-1000:]}
        temp_target = target.with_suffix(".pdf.tmp")
        temp_target.write_bytes(output.read_bytes())
        temp_target.replace(target)
    metadata = {
        "source_id": source["source_id"], "source_url": source["source_url"],
        "converted_at": now_utc(), "conversion_tool": "LibreOffice soffice writer_pdf_Export",
        "sha256": sha256_file(target), "file_size": target.stat().st_size,
    }
    previous = source_metadata_path(source)
    current = __import__("json").loads(previous.read_text(encoding="utf-8")) if previous.exists() else {}
    current["pdf_conversion"] = metadata
    json_dump(previous, current)
    return {"source_id": source["source_id"], "status": "converted", "path": str(target), **metadata}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    selected = [s for s in load_yaml(CONFIG_ROOT / "sources.yaml")["sources"] if s.get("enabled") and (not args.source_id or s["source_id"] == args.source_id)]
    results = [convert_source(source, args.force) for source in selected]
    json_dump(CONFIG_ROOT.parent / "results" / "conversion_report.json", results)
    for result in results:
        print(f"{result['source_id']}: {result['status']}")
    return 1 if any(item["status"] == "failed" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
