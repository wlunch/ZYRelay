from __future__ import annotations

import importlib.util
import time
import uuid
from pathlib import Path

import fitz

from zyrelay.app.core.config import Settings, load_yaml

from .models import OCRLine, ResourceHealth, ResourceRequest, ResourceResponse


class PaddleOCRResource:
    """Optional, lazy PaddleOCR adapter. It never downloads a model in a request."""

    resource_id = "paddleocr"
    resource_type = "ocr"
    version = "optional"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()

    def health_check(self) -> ResourceHealth:
        config = self._config()
        installed = importlib.util.find_spec("paddleocr") is not None
        cache = self._cache_dir(config)
        ready = (cache / "ready.json").is_file()
        return ResourceHealth(
            available=bool(config.get("enabled", True) and installed and ready),
            status="available" if installed and ready else "model_not_available",
            details={
                "package_installed": installed,
                "cache_ready": ready,
                "allow_download": bool(config.get("allow_download", False)),
            },
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "ocr"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        health = self.health_check()
        if not health.available:
            return ResourceResponse(
                status="unavailable",
                payload=[],
                warnings=["PaddleOCR 模型未安装或缓存未就绪，未下载模型"],
                metadata=health.details,
            )
        started = time.perf_counter()
        model_execution_id = f"MEXEC-{uuid.uuid4().hex[:16].upper()}"
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-not-found]

            config = self._config()
            # A ready marker is created only by offline provisioning. No API is
            # called to acquire weights during document processing.
            ocr = PaddleOCR(lang=str(config.get("language", "ch")), use_gpu=False)
            lines = self._recognize(
                ocr,
                Path(request.file_path or ""),
                model_execution_id,
            )
            return ResourceResponse(
                status="completed",
                payload=lines,
                metadata={
                    "model_execution_id": model_execution_id,
                    "duration_ms": (time.perf_counter() - started) * 1000,
                },
            )
        except Exception as exc:
            return ResourceResponse(
                status="unavailable",
                payload=[],
                warnings=[f"PaddleOCR 执行失败，已保留 NoOp 回退：{exc}"],
                metadata={"model_execution_id": model_execution_id},
            )

    @staticmethod
    def _recognize(ocr, path: Path, model_execution_id: str) -> list[OCRLine]:
        lines: list[OCRLine] = []
        pdf = fitz.open(path)
        try:
            for page_index, page in enumerate(pdf):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                result = ocr.ocr(pix.tobytes("png"), cls=True) or []
                reading_order = 0
                for item in result[0] if result else []:
                    box, text_info = item
                    text, confidence = text_info
                    xs = [point[0] for point in box]
                    ys = [point[1] for point in box]
                    lines.append(
                        OCRLine(
                            line_id=f"OCR-{page_index + 1:03d}-{reading_order + 1:04d}",
                            page_no=page_index + 1,
                            text=str(text),
                            bbox=[min(xs), min(ys), max(xs), max(ys)],
                            confidence=float(confidence),
                            reading_order=reading_order,
                            model_execution_id=model_execution_id,
                        )
                    )
                    reading_order += 1
        finally:
            pdf.close()
        return lines

    def _config(self) -> dict:
        raw = load_yaml(self.settings.model_config)
        return dict(raw.get("models", {}).get("paddleocr", {}))

    def _cache_dir(self, config: dict) -> Path:
        configured = Path(str(config.get("cache_dir", "data/model_cache/paddleocr")))
        if configured.is_absolute():
            return configured
        if configured.parts and configured.parts[0] == "data":
            return self.settings.data_root.joinpath(*configured.parts[1:])
        return self.settings.data_root / configured
