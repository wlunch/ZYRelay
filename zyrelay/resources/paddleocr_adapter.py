from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import threading
import time
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from zyrelay.app.core.config import Settings, load_yaml

from .models import (
    OCRLine,
    OCRPageResult,
    ResourceHealth,
    ResourceRequest,
    ResourceResponse,
)


class PaddleOCRResource:
    """Offline-only PaddleOCR 3.x adapter with one lazy process-local instance."""

    resource_id = "paddleocr"
    resource_type = "ocr"
    version = "3.7.0"
    _lock = threading.Lock()
    _ocr: Any = None
    _loaded_cache_dir: Path | None = None
    _load_duration_ms = 0.0

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()

    def health_check(self) -> ResourceHealth:
        config = self._config()
        cache = self._cache_dir(config)
        package_installed = importlib.util.find_spec("paddleocr") is not None
        ready_models = self._required_models_ready(config, cache)
        ready_record = (cache / "ready.json").is_file()
        available = bool(
            config.get("enabled", True)
            and package_installed
            and ready_models
            and ready_record
        )
        return ResourceHealth(
            available=available,
            status="available" if available else "model_not_available",
            details={
                "package_installed": package_installed,
                "offline_ready": ready_record and ready_models,
                "cache_reference": str(
                    config.get("cache_dir", "data/model_cache/paddleocr")
                ),
                "required_models_ready": ready_models,
                "allow_download": bool(config.get("allow_download", False)),
                "model_version": config.get("model_version"),
                "paddleocr_version": self._package_version("paddleocr"),
                "paddlepaddle_version": self._package_version("paddlepaddle"),
                "device": str(config.get("device", "cpu")),
            },
        )

    def available(self) -> bool:
        return self.health_check().available

    def health(self) -> ResourceHealth:
        return self.health_check()

    def metadata(self) -> dict[str, Any]:
        config = self._config()
        return {
            "plugin_name": self.resource_id,
            "model_version": config.get("model_version", self.version),
            "cache_dir": str(self._cache_dir(config)),
            "enabled": bool(config.get("enabled", True)),
        }

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "ocr" and request.document_type == "pdf"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        health = self.health_check()
        if not health.available:
            return ResourceResponse(
                status="unavailable",
                payload=[],
                warnings=["model_not_available: PaddleOCR 未安装或离线模型缓存未就绪"],
                metadata=health.details,
            )

        artifacts = list(request.options.get("page_artifacts", []))
        if not artifacts:
            return ResourceResponse(
                status="completed",
                payload=[],
                warnings=["没有需要 OCR 的 PDF 页面"],
                metadata=health.details,
            )

        execution_id = str(request.options.get("model_execution_id") or self._new_id())
        started = time.perf_counter()
        pages: list[OCRPageResult] = []
        page_metrics: list[dict[str, float | int]] = []
        warnings: list[str] = []
        try:
            ocr, load_ms = self._get_ocr()
            for artifact in artifacts:
                page_started = time.perf_counter()
                raw_results = ocr.predict(str(artifact["file_path"]))
                raw_result = self._single_page_result(raw_results)
                page = normalize_paddleocr_result(
                    raw_result,
                    page_no=int(artifact["page_no"]),
                    width=int(artifact["width"]),
                    height=int(artifact["height"]),
                    resource_id=self.resource_id,
                    resource_version=self._package_version("paddleocr") or self.version,
                    model_execution_id=execution_id,
                    page_artifact={
                        key: value
                        for key, value in artifact.items()
                        if key != "file_path"
                    },
                )
                page_duration_ms = (time.perf_counter() - page_started) * 1000
                page.warnings.append(f"page_ocr_duration_ms={page_duration_ms:.2f}")
                pages.append(page)
                page_metrics.append(
                    {
                        "page_no": page.page_no,
                        "duration_ms": page_duration_ms,
                        "line_count": len(page.lines),
                        "average_confidence": page.average_confidence,
                    }
                )
        except Exception as exc:
            return ResourceResponse(
                status="unavailable",
                payload=[],
                warnings=[f"PaddleOCR 执行失败，已保留 NoOp 回退：{exc}"],
                metadata={**health.details, "model_execution_id": execution_id},
            )

        lines = [line for page in pages for line in page.lines]
        return ResourceResponse(
            status="completed",
            payload=pages,
            warnings=warnings,
            metadata={
                **health.details,
                "model_execution_id": execution_id,
                "duration_ms": (time.perf_counter() - started) * 1000,
                "model_load_ms": load_ms,
                "page_count": len(pages),
                "line_count": len(lines),
                "average_confidence": (
                    sum(line.confidence for line in lines) / len(lines)
                    if lines
                    else 0.0
                ),
                "page_metrics": page_metrics,
            },
        )

    def _get_ocr(self) -> tuple[Any, float]:
        config = self._config()
        cache = self._cache_dir(config)
        with self._lock:
            if self._ocr is not None and self._loaded_cache_dir == cache:
                return self._ocr, 0.0
            self._configure_runtime(cache, allow_download=False)
            started = time.perf_counter()
            from paddleocr import PaddleOCR  # Imported only after cache is configured.

            self._ocr = PaddleOCR(
                lang=str(config.get("language", "ch")),
                use_doc_orientation_classify=bool(config.get("use_orientation", True)),
                use_doc_unwarping=False,
                use_textline_orientation=bool(config.get("use_orientation", True)),
            )
            self._loaded_cache_dir = cache
            self._load_duration_ms = (time.perf_counter() - started) * 1000
            return self._ocr, self._load_duration_ms

    @staticmethod
    def _single_page_result(raw_results: Any) -> Any:
        if raw_results is None:
            return None
        if isinstance(raw_results, list):
            return raw_results[0] if raw_results else None
        if isinstance(raw_results, Iterable) and not isinstance(
            raw_results, (dict, str, bytes)
        ):
            return next(iter(raw_results), None)
        return raw_results

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

    @staticmethod
    def _package_version(name: str) -> str | None:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return None

    @staticmethod
    def _new_id() -> str:
        return f"MEXEC-{uuid.uuid4().hex[:16].upper()}"

    @staticmethod
    def _required_models_ready(config: dict, cache: Path) -> bool:
        required = config.get("required_models", [])
        base = cache / "paddlex" / "official_models"
        return bool(required) and all(
            (base / str(model) / "inference.pdiparams").is_file()
            and (base / str(model) / "inference.yml").is_file()
            for model in required
        )

    @staticmethod
    def _configure_runtime(cache: Path, *, allow_download: bool) -> None:
        cache.mkdir(parents=True, exist_ok=True)
        os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache / "paddlex")
        os.environ["PADDLE_PDX_MODEL_SOURCE"] = "bos"
        # The resource is offline-only. Paddlex will use local model folders and
        # must not probe a model host during normal Relay execution.
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = (
            "" if allow_download else "1"
        )


def normalize_paddleocr_result(
    raw_result: Any,
    *,
    page_no: int,
    width: int,
    height: int,
    resource_id: str,
    resource_version: str,
    model_execution_id: str,
    page_artifact: dict[str, Any],
) -> OCRPageResult:
    """Convert PaddleOCR 3.x result objects/dicts into the stable Relay protocol."""

    data = _result_as_dict(raw_result)
    payload = data.get("res", data)
    texts = _result_list(payload, "rec_texts", "texts")
    scores = _result_list(payload, "rec_scores", "scores")
    polygons = _result_list(payload, "rec_polys", "dt_polys")
    boxes = _result_list(payload, "rec_boxes", "boxes")
    lines: list[OCRLine] = []
    for index, value in enumerate(texts):
        text = str(value).strip()
        if not text:
            continue
        polygon = _polygon(polygons[index] if index < len(polygons) else None)
        bbox = _bbox(
            boxes[index] if index < len(boxes) else None,
            polygon,
        )
        confidence = _confidence(scores[index] if index < len(scores) else None)
        lines.append(
            OCRLine(
                line_id=f"OCR-{page_no:03d}-{len(lines) + 1:04d}",
                page_no=page_no,
                text=text,
                bbox=bbox,
                polygon=polygon,
                confidence=confidence,
                reading_order=len(lines),
                model_execution_id=model_execution_id,
            )
        )
    lines.sort(key=lambda line: (line.bbox[1], line.bbox[0], line.reading_order))
    lines = [
        line.model_copy(update={"reading_order": index})
        for index, line in enumerate(lines)
    ]
    orientation = _int_or_none((payload.get("doc_preprocessor_res") or {}).get("angle"))
    average = sum(line.confidence for line in lines) / len(lines) if lines else 0.0
    return OCRPageResult(
        page_no=page_no,
        width=width,
        height=height,
        orientation=orientation,
        lines=lines,
        average_confidence=average,
        resource_id=resource_id,
        resource_version=resource_version,
        model_execution_id=model_execution_id,
        page_artifact=page_artifact,
        warnings=[] if lines else ["PaddleOCR 未在页面中识别到文本"],
    )


def _result_as_dict(raw_result: Any) -> dict[str, Any]:
    if raw_result is None:
        return {}
    if isinstance(raw_result, dict):
        return raw_result
    json_value = getattr(raw_result, "json", None)
    if isinstance(json_value, dict):
        return json_value
    keys = getattr(raw_result, "keys", None)
    if callable(keys):
        return {key: raw_result[key] for key in keys()}
    return {}


def _result_list(payload: dict[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return list(value)
    return []


def _polygon(value: Any) -> list[list[float]]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    try:
        raw_points = list(value)
    except TypeError:
        return []
    points: list[list[float]] = []
    for point in raw_points:
        try:
            coords = list(point)
        except TypeError:
            continue
        if len(coords) >= 2:
            points.append([float(coords[0]), float(coords[1])])
    return points


def _bbox(value: Any, polygon: list[list[float]]) -> list[float]:
    if value is not None and not isinstance(value, (str, bytes)):
        try:
            values = list(value)
        except TypeError:
            values = []
        if len(values) >= 4 and not hasattr(values[0], "__iter__"):
            return [
                float(values[0]),
                float(values[1]),
                float(values[2]),
                float(values[3]),
            ]
    if polygon:
        xs = [point[0] for point in polygon]
        ys = [point[1] for point in polygon]
        return [min(xs), min(ys), max(xs), max(ys)]
    return [0.0, 0.0, 0.0, 0.0]


def _confidence(value: Any) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
