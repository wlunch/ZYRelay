from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import fitz
import yaml


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = ROOT / "benchmark"
CONFIG_ROOT = BENCHMARK_ROOT / "config"
PRIVATE_ROOT = BENCHMARK_ROOT / "private"
SOURCES_ROOT = BENCHMARK_ROOT / "sources"
SCANNED_ROOT = BENCHMARK_ROOT / "scanned"
CASES_ROOT = BENCHMARK_ROOT / "cases"
RESULTS_ROOT = BENCHMARK_ROOT / "results"


def now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def dump_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(value, handle, allow_unicode=True, sort_keys=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload + "\n", encoding="utf-8")
    json.loads(tmp.read_text(encoding="utf-8"))
    tmp.replace(path)


def json_load(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def stable_benchmark_id(category: str, number: int) -> str:
    prefix = {
        "code_convention": "CODE",
        "contract": "CONTRACT",
        "enterprise_policy": "POLICY",
        "api_specification": "API",
        "scanned_document": "SCAN",
    }[category]
    return f"BC-{prefix}-{number:03d}"


def source_by_id(source_id: str) -> dict[str, Any]:
    sources = load_yaml(CONFIG_ROOT / "sources.yaml").get("sources", [])
    for source in sources:
        if source["source_id"] == source_id:
            return source
    raise KeyError(f"unknown source_id: {source_id}")


def validate_source_url(source: dict[str, Any]) -> None:
    parsed = urlparse(source["source_url"])
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"source URL must use HTTPS: {source['source_id']}")
    domain = source["source_domain"].lower()
    actual = parsed.hostname.lower() if parsed.hostname else ""
    if actual != domain and not actual.endswith("." + domain):
        raise ValueError(f"source domain is not whitelisted: {actual}")


def source_download_path(source: dict[str, Any]) -> Path:
    if source["source_type"] == "pdf":
        return source_pdf_path(source)
    suffix = ".pdf" if source["source_type"] == "pdf" else ".html"
    return PRIVATE_ROOT / source["category"] / f"{source['source_id']}{suffix}"


def source_pdf_path(source: dict[str, Any]) -> Path:
    return SOURCES_ROOT / source["category"] / f"{source['source_id']}.pdf"


def source_metadata_path(source: dict[str, Any]) -> Path:
    return PRIVATE_ROOT / source["category"] / f"{source['source_id']}.metadata.json"


def document_info(path: Path) -> dict[str, Any]:
    mime_type, _ = mimetypes.guess_type(path.name)
    info: dict[str, Any] = {
        "file_name": path.name,
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
        "mime_type": mime_type or "application/octet-stream",
        "page_count": 0,
        "extractable_text_length": 0,
        "is_scanned": False,
        "pages_with_text": 0,
        "pages_with_images": 0,
        "average_text_density": 0.0,
        "has_tables": False,
        "has_code_blocks": False,
        "has_headings": False,
        "parser_status": "not_pdf",
        "warnings": [],
    }
    if path.suffix.lower() != ".pdf":
        return info
    try:
        document = fitz.open(path)
        page_texts = [page.get_text("text") for page in document]
        image_pages = sum(1 for page in document if page.get_images(full=True))
        text_length = sum(len(text.strip()) for text in page_texts)
        joined = "\n".join(page_texts)
        info.update(
            page_count=document.page_count,
            extractable_text_length=text_length,
            pages_with_text=sum(1 for text in page_texts if text.strip()),
            pages_with_images=image_pages,
            average_text_density=round(text_length / max(document.page_count, 1), 2),
            is_scanned=text_length <= max(20, document.page_count * 5) and image_pages > 0,
            has_tables=bool(re.search(r"\b(table|column|row)\b|\|.{2,}\|", joined, re.I)),
            has_code_blocks=bool(re.search(r"\b(class|def|function|curl|HTTP/|\{\s*\})\b", joined, re.I)),
            has_headings=bool(re.search(r"(?m)^(\d+(\.\d+)*\s+|[A-Z][A-Z\s]{5,}$)", joined)),
            parser_status="ok",
        )
        document.close()
    except Exception as exc:  # pragma: no cover - defensive for malformed PDFs
        info["parser_status"] = "failed"
        info["warnings"].append(str(exc))
    return info


def copy_atomic(source: Path, target: Path, overwrite: bool = False) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
        temp = Path(handle.name)
    try:
        shutil.copyfile(source, temp)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


def write_manifest_csv(entries: list[dict[str, Any]], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({key for entry in entries for key in entry})
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for entry in entries:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in entry.items()})
