"""Create image-only PDFs for OCR regression; no original text layer is retained."""
from __future__ import annotations

import argparse
from pathlib import Path

if __package__ in {None, ""}:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import fitz

from benchmark.scripts.common import json_dump, now_utc, sha256_file


QUALITY = {"clean": 200, "medium": 180, "degraded": 150}


def create_scanned_pdf(source: Path, target: Path, quality: str = "clean", max_pages: int | None = None) -> dict:
    if quality not in QUALITY:
        raise ValueError(f"unknown quality: {quality}")
    dpi = QUALITY[quality]
    original = fitz.open(source)
    output = fitz.open()
    dimensions: list[dict[str, int]] = []
    for index, page in enumerate(original):
        if max_pages is not None and index >= max_pages:
            break
        pixmap = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), colorspace=fitz.csRGB, alpha=False)
        # PDF page dimensions are expressed in points, not source image pixels.
        # Keeping the original physical size prevents a second renderer from
        # magnifying a 200-DPI image into an impractically large OCR page.
        new_page = output.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, pixmap=pixmap)
        dimensions.append({"page_no": index + 1, "width": pixmap.width, "height": pixmap.height})
    original.close()
    if not dimensions:
        output.close()
        raise ValueError("source PDF has no pages")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".pdf.tmp")
    output.save(temp, garbage=4, deflate=True)
    output.close()
    temp.replace(target)
    check = fitz.open(target)
    extracted = "".join(page.get_text("text") for page in check)
    image_pages = sum(1 for page in check if page.get_images(full=True))
    page_count = check.page_count
    check.close()
    if extracted.strip() or image_pages == 0:
        target.unlink(missing_ok=True)
        raise ValueError("generated scan retains text or has no images")
    return {
        "source_path": source.as_posix(), "target_path": target.as_posix(), "created_at": now_utc(),
        "quality": quality, "dpi": dpi, "page_count": page_count, "image_pages": image_pages,
        "dimensions": dimensions, "sha256": sha256_file(target), "file_size": target.stat().st_size,
        "tool": f"PyMuPDF {fitz.VersionBind}", "extractable_text_length": len(extracted.strip()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--quality", choices=QUALITY, default="clean")
    parser.add_argument("--max-pages", type=int)
    args = parser.parse_args()
    metadata = create_scanned_pdf(args.source, args.target, args.quality, args.max_pages)
    json_dump(args.target.with_suffix(".metadata.json"), metadata)
    print(metadata["target_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
