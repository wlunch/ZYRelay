"""Download only sources explicitly listed in benchmark/config/sources.yaml."""

from __future__ import annotations

import argparse
import ssl
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmark.scripts.common import (
    CONFIG_ROOT,
    json_dump,
    load_yaml,
    now_utc,
    sha256_file,
    source_download_path,
    source_metadata_path,
    validate_source_url,
)


def download_source(source: dict, max_bytes: int, force: bool = False) -> dict:
    validate_source_url(source)
    target = source_download_path(source)
    if target.exists() and not force:
        return {
            "source_id": source["source_id"],
            "status": "existing",
            "path": str(target),
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        source["source_url"], headers={"User-Agent": "ZYRelay-Benchmark/1.0"}
    )
    temp_path: Path | None = None
    try:
        # Use certifi rather than disabling certificate verification. Some local
        # Python builds do not inherit the macOS trust store.
        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
        response = None
        last_error = None
        for attempt in range(3):
            try:
                response = urlopen(request, timeout=30, context=context)
                break
            except URLError as exc:
                last_error = exc
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)
        if response is None:
            raise last_error or URLError("download_failed")
        with response:
            content_type = response.headers.get_content_type()
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise ValueError(f"response exceeds max bytes: {length}")
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                temp_path = Path(handle.name)
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("response exceeds max bytes")
                    handle.write(chunk)
            temp_path.replace(target)
            metadata = {
                "source_id": source["source_id"],
                "source_url": source["source_url"],
                "downloaded_at": now_utc(),
                "content_type": content_type,
                "original_file_name": Path(response.geturl()).name or target.name,
                "file_size": target.stat().st_size,
                "sha256": sha256_file(target),
                "download_method": "urllib_https_whitelist",
            }
            json_dump(source_metadata_path(source), metadata)
            return {
                "source_id": source["source_id"],
                "status": "downloaded",
                "path": str(target),
                **metadata,
            }
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        # A small number of official HTTPS sites close Python's TLS connection
        # early while curl succeeds with the platform trust store. This remains
        # safe because the URL was already read from the whitelist above.
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                temp_path = Path(handle.name)
            completed = subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--location",
                    "--silent",
                    "--show-error",
                    "--proto",
                    "=https",
                    "--max-filesize",
                    str(max_bytes),
                    "--output",
                    str(temp_path),
                    source["source_url"],
                ],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            if completed.returncode != 0 or temp_path.stat().st_size > max_bytes:
                raise ValueError(completed.stderr.strip() or "curl_download_failed")
            temp_path.replace(target)
            metadata = {
                "source_id": source["source_id"],
                "source_url": source["source_url"],
                "downloaded_at": now_utc(),
                "content_type": "unknown",
                "original_file_name": target.name,
                "file_size": target.stat().st_size,
                "sha256": sha256_file(target),
                "download_method": "curl_https_whitelist_fallback",
            }
            json_dump(source_metadata_path(source), metadata)
            return {
                "source_id": source["source_id"],
                "status": "downloaded",
                "path": str(target),
                **metadata,
            }
        except (OSError, ValueError, subprocess.TimeoutExpired) as fallback_error:
            if temp_path:
                temp_path.unlink(missing_ok=True)
            return {
                "source_id": source["source_id"],
                "status": "failed",
                "error": f"{exc}; fallback={fallback_error}",
            }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    config = load_yaml(CONFIG_ROOT / "sources.yaml")
    selected = [
        item
        for item in config["sources"]
        if item.get("enabled")
        and (not args.source_id or item["source_id"] == args.source_id)
    ]
    results = [
        download_source(
            item, int(config.get("max_download_bytes", 25 * 1024 * 1024)), args.force
        )
        for item in selected
    ]
    json_dump(CONFIG_ROOT.parent / "results" / "download_report.json", results)
    for result in results:
        print(f"{result['source_id']}: {result['status']}")
    return 1 if any(item["status"] == "failed" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
