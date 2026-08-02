from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass(frozen=True)
class RenderedPageArtifact:
    """A private, short-lived PNG used as the OCR input evidence."""

    page_no: int
    dpi: int
    width: int
    height: int
    sha256: str
    file_path: Path
    execution_id: str

    @property
    def public_metadata(self) -> dict:
        return {
            "artifact_id": f"PAGE-{self.execution_id}-{self.page_no:03d}",
            "uri": f"relay://executions/{self.execution_id}/pages/{self.page_no:03d}.png",
            "page_no": self.page_no,
            "dpi": self.dpi,
            "width": self.width,
            "height": self.height,
            "sha256": self.sha256,
            "temporary": True,
        }


def render_pdf_pages(
    pdf_path: Path,
    page_numbers: list[int],
    destination: Path,
    *,
    dpi: int,
    execution_id: str,
) -> list[RenderedPageArtifact]:
    """Render only OCR-gated PDF pages as RGB PNG files."""

    destination.mkdir(parents=True, exist_ok=True)
    zoom = dpi / 72
    artifacts: list[RenderedPageArtifact] = []
    pdf = fitz.open(pdf_path)
    try:
        for page_no in page_numbers:
            page = pdf[page_no - 1]
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csRGB, alpha=False
            )
            path = destination / f"page-{page_no:03d}.png"
            pixmap.save(path)
            artifacts.append(
                RenderedPageArtifact(
                    page_no=page_no,
                    dpi=dpi,
                    width=pixmap.width,
                    height=pixmap.height,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    file_path=path,
                    execution_id=execution_id,
                )
            )
    finally:
        pdf.close()
    return artifacts
