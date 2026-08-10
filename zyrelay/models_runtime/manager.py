from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from zyrelay.app.core.config import Settings, load_yaml
from zyrelay.relay.repository import JsonRecordRepository
from zyrelay.resources.paddleocr_adapter import (
    PaddleOCRResource,
    normalize_paddleocr_result,
)

from .models import ModelInstallRecord


class ModelManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.install_store = JsonRecordRepository(
            self.settings.data_root / "model_installations", ModelInstallRecord
        )

    def paddleocr_status(self) -> dict[str, Any]:
        config = self._config()
        cache = self._cache_dir(config)
        required = [str(item) for item in config.get("required_models", [])]
        models_ready = self._models_ready(cache, required)
        ready_file = cache / "ready.json"
        ready_data = self._read_json(ready_file)
        return {
            "model": "paddleocr",
            "enabled": bool(config.get("enabled", False)),
            "provider": config.get("provider", "paddleocr"),
            "package_installed": importlib.util.find_spec("paddleocr") is not None,
            "paddleocr_version": self._version("paddleocr"),
            "paddlepaddle_version": self._version("paddlepaddle"),
            "cache_dir": str(cache),
            "required_models": required,
            "models_ready": models_ready,
            "offline_ready": bool(ready_data) and models_ready,
            "cache_ready": bool(ready_data) and models_ready,
            "allow_download": bool(config.get("allow_download", False)),
            "model_version": config.get("model_version"),
            "install_id": ready_data.get("install_id"),
            "checksum_count": len(ready_data.get("file_checksums", {})),
        }

    def verify(self, name: str) -> dict[str, Any]:
        if name == "all":
            results = {key: self.verify(key) for key in self._all_model_configs()}
            return {
                "model": "all",
                "models": results,
                "verified": all(item["verified"] for item in results.values()),
            }
        if name != "paddleocr":
            status = self.model_status(name)
            status["verified"] = bool(
                status["enabled"] and status["packages_ready"] and status["cache_ready"]
            )
            return status
        status = self.paddleocr_status()
        status["verified"] = bool(
            status["package_installed"] and status["offline_ready"]
        )
        return status

    def install(self, name: str) -> dict[str, Any]:
        """Administrative-only model provisioning; the Relay path never calls this."""

        if name == "all":
            results = {key: self.install(key) for key in self._all_model_configs()}
            return {
                "model": "all",
                "models": results,
                "verified": all(
                    item.get("verified", False) for item in results.values()
                ),
            }
        if name != "paddleocr":
            return self._install_generic(name)
        if importlib.util.find_spec("paddleocr") is None:
            raise RuntimeError(
                "未安装 paddleocr；请先在兼容环境安装项目 paddleocr extra"
            )
        if importlib.util.find_spec("paddle") is None:
            raise RuntimeError(
                "未安装 paddlepaddle；请先在兼容环境安装项目 paddleocr extra"
            )

        config = self._config()
        cache = self._cache_dir(config)
        required = [str(item) for item in config.get("required_models", [])]
        PaddleOCRResource._configure_runtime(cache, allow_download=True)
        started = time.perf_counter()
        from paddleocr import PaddleOCR
        from PIL import Image, ImageDraw, ImageFont

        image_path = cache / "install-smoke.png"
        cache.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (1600, 240), "white")
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 64)
        except OSError:
            font = ImageFont.load_default()
        draw.text((48, 80), "PaddleOCR 80 System.out.println", fill="black", font=font)
        image.save(image_path)

        ocr = PaddleOCR(
            lang=str(config.get("language", "ch")),
            use_doc_orientation_classify=bool(config.get("use_orientation", True)),
            use_doc_unwarping=False,
            use_textline_orientation=bool(config.get("use_orientation", True)),
        )
        raw_results = ocr.predict(str(image_path))
        raw_result = (
            raw_results[0] if isinstance(raw_results, list) and raw_results else None
        )
        page = normalize_paddleocr_result(
            raw_result,
            page_no=1,
            width=image.width,
            height=image.height,
            resource_id="paddleocr",
            resource_version=self._version("paddleocr") or "unknown",
            model_execution_id="INSTALL-SMOKE",
            page_artifact={"uri": "model-install://paddleocr/smoke", "page_no": 1},
        )
        if not self._models_ready(cache, required):
            raise RuntimeError("PaddleOCR 初始化完成但必需模型文件未完整写入缓存")
        if not page.lines:
            raise RuntimeError("PaddleOCR 模型已加载，但安装烟雾测试未识别出文本")

        checksums = self._model_checksums(cache, required)
        record = ModelInstallRecord(
            install_id=f"MINST-{uuid.uuid4().hex[:16].upper()}",
            model_name="paddleocr",
            provider="paddleocr",
            paddleocr_version=self._version("paddleocr") or "unknown",
            paddlepaddle_version=self._version("paddlepaddle") or "unknown",
            model_version=str(config.get("model_version", "unknown")),
            cache_dir=str(cache),
            model_source=str(config.get("model_source", "bos")),
            required_models=required,
            file_checksums=checksums,
            smoke_test_line_count=len(page.lines),
            metadata={
                "device": str(config.get("device", "cpu")),
                "duration_ms": (time.perf_counter() - started) * 1000,
                "smoke_text": [line.text for line in page.lines],
            },
        )
        self.install_store.save(record, record.install_id)
        self._atomic_json(
            cache / "ready.json",
            {
                "install_id": record.install_id,
                "offline_ready": True,
                "paddleocr_version": record.paddleocr_version,
                "paddlepaddle_version": record.paddlepaddle_version,
                "model_version": record.model_version,
                "required_models": record.required_models,
                "file_checksums": record.file_checksums,
            },
        )
        return {
            **self.verify("paddleocr"),
            "install_record": record.model_dump(mode="json"),
        }

    def model_status(self, name: str) -> dict[str, Any]:
        config = self._all_model_configs().get(name)
        if config is None:
            raise ValueError(f"未知模型：{name}")
        cache = self._cache_dir_for(config)
        packages = [str(item) for item in config.get("packages", [])]
        missing_packages = [
            item for item in packages if importlib.util.find_spec(item) is None
        ]
        files = [str(item) for item in config.get("required_files", [])]
        missing_files = [item for item in files if not (cache / item).is_file()]
        return {
            "model": name,
            "enabled": bool(config.get("enabled", False)),
            "provider": config.get("provider"),
            "model_id": config.get("model_id"),
            "model_version": config.get("model_version"),
            "cache_dir": str(cache),
            "packages": packages,
            "packages_ready": not missing_packages,
            "missing_packages": missing_packages,
            "required_files": files,
            "cache_ready": not missing_files,
            "missing_files": missing_files,
            "allow_download": bool(config.get("allow_download", False)),
        }

    def warmup(self) -> dict[str, Any]:
        """Load only locally verified resources; never invokes an installer."""
        from zyrelay.resources import create_default_registry
        from zyrelay.resources.models import ResourceRequest

        registry = create_default_registry(self.settings)
        resources = {
            "paddleocr": ("paddleocr", "ocr", {}),
            "minilm_classifier": (
                "minilm-document-classifier",
                "document_classifier",
                {"text": "warmup"},
            ),
            "fasttext_language": (
                "fasttext-language",
                "language_detection",
                {"blocks": []},
            ),
            "doclayout_yolo": ("doclayout-yolo", "layout", {"page_images": []}),
            "table_transformer": (
                "table-transformer",
                "table_recognition",
                {"blocks": [], "table_images": []},
            ),
            "gliner": ("gliner-ner", "ner", {"blocks": []}),
            "tree_sitter": ("tree-sitter-code", "code_detection", {"blocks": []}),
            "symspell": ("symspell", "spell_correction", {"blocks": []}),
        }
        results: dict[str, Any] = {}
        for model_name, (resource_id, capability, options) in resources.items():
            resource = registry.get(resource_id)
            health = resource.health_check()
            if not health.available:
                results[model_name] = {"warmed": False, "reason": health.status}
                continue
            started = time.perf_counter()
            try:
                if resource_id == "paddleocr":
                    resource._get_ocr()  # local, cached-only initialization
                else:
                    resource.execute(
                        ResourceRequest(capability=capability, options=options),
                        object(),
                    )
                results[model_name] = {
                    "warmed": True,
                    "duration_ms": (time.perf_counter() - started) * 1000,
                }
            except Exception as exc:
                results[model_name] = {"warmed": False, "reason": str(exc)}
        return {"models": results, "downloaded": False}

    def _install_generic(self, name: str) -> dict[str, Any]:
        """Best-effort offline-cache provisioning for non-OCR auxiliary models.

        Relay never invokes this method.  It is safe to run repeatedly; a failed
        package or Hugging Face download returns a structured result so the
        ResourcePlan can continue with its configured fallback.
        """
        config = self._all_model_configs().get(name)
        if config is None:
            raise ValueError(f"未知模型：{name}")
        cache = self._cache_dir_for(config)
        cache.mkdir(parents=True, exist_ok=True)
        warnings: list[str] = []
        package_names = [str(item) for item in config.get("packages", [])]
        distribution_names = {
            "fasttext": "fasttext-wheel",
            "sentence_transformers": "sentence-transformers",
            "tree_sitter": "tree-sitter",
            "tree_sitter_python": "tree-sitter-python",
        }
        for package in package_names:
            if importlib.util.find_spec(package) is not None:
                continue
            try:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        distribution_names.get(package, package),
                    ],
                    check=True,
                    timeout=600,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                warnings.append(f"package install failed for {package}: {exc}")
        model_id = str(config.get("model_id") or "")
        if (
            config.get("allow_download", False)
            and model_id
            and not self.model_status(name)["cache_ready"]
        ):
            try:
                from huggingface_hub import snapshot_download

                snapshot_download(
                    repo_id=model_id, local_dir=str(cache), local_dir_use_symlinks=False
                )
                backbone_model_id = str(config.get("backbone_model_id") or "")
                if backbone_model_id:
                    snapshot_download(
                        repo_id=backbone_model_id,
                        local_dir=str(cache / Path(backbone_model_id).name),
                        local_dir_use_symlinks=False,
                    )
            except Exception as exc:
                warnings.append(f"model download failed for {model_id}: {exc}")
        status = self.verify(name)
        record = ModelInstallRecord(
            install_id=f"MINST-{uuid.uuid4().hex[:16].upper()}",
            model_name=name,
            provider=str(config.get("provider", "unknown")),
            paddleocr_version=self._version("paddleocr") or "",
            paddlepaddle_version=self._version("paddlepaddle") or "",
            model_version=str(config.get("model_version", "unknown")),
            cache_dir=str(cache),
            model_source=model_id,
            required_models=[str(item) for item in config.get("required_files", [])],
            metadata={"warnings": warnings, "packages": package_names},
        )
        self.install_store.save(record, record.install_id)
        return {
            **status,
            "warnings": warnings,
            "install_record": record.model_dump(mode="json"),
        }

    def _config(self) -> dict[str, Any]:
        return dict(
            load_yaml(self.settings.model_config).get("models", {}).get("paddleocr", {})
        )

    def _all_model_configs(self) -> dict[str, dict[str, Any]]:
        return {
            key: dict(value)
            for key, value in load_yaml(self.settings.model_config)
            .get("models", {})
            .items()
            if key != "paddleocr"
        }

    def _cache_dir(self, config: dict[str, Any]) -> Path:
        raw = Path(str(config.get("cache_dir", "data/model_cache/paddleocr")))
        if raw.is_absolute():
            return raw
        if raw.parts and raw.parts[0] == "data":
            return self.settings.data_root.joinpath(*raw.parts[1:])
        return self.settings.data_root / raw

    def _cache_dir_for(self, config: dict[str, Any]) -> Path:
        return self._cache_dir(config)

    @staticmethod
    def _version(package: str) -> str | None:
        try:
            return importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            return None

    @staticmethod
    def _models_ready(cache: Path, models: list[str]) -> bool:
        base = cache / "paddlex" / "official_models"
        return bool(models) and all(
            (base / name / "inference.pdiparams").is_file()
            and (base / name / "inference.yml").is_file()
            for name in models
        )

    @staticmethod
    def _model_checksums(cache: Path, models: list[str]) -> dict[str, str]:
        checksums: dict[str, str] = {}
        base = cache / "paddlex" / "official_models"
        for name in models:
            for path in sorted((base / name).glob("inference.*")):
                if path.is_file():
                    checksums[str(path.relative_to(cache))] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
        return checksums

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
            temp_path = Path(stream.name)
        os.replace(temp_path, path)
