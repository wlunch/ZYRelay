from __future__ import annotations

import importlib.util
from pathlib import Path

from zyrelay.app.core.config import Settings, load_yaml


class ModelManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()

    def paddleocr_status(self) -> dict:
        config = load_yaml(self.settings.model_config).get("models", {}).get("paddleocr", {})
        raw_cache = Path(str(config.get("cache_dir", "data/model_cache/paddleocr")))
        cache = self._resolve_cache_dir(raw_cache)
        return {
            "model": "paddleocr",
            "enabled": bool(config.get("enabled", False)),
            "package_installed": importlib.util.find_spec("paddleocr") is not None,
            "cache_dir": str(cache),
            "cache_ready": (cache / "ready.json").is_file(),
            "allow_download": bool(config.get("allow_download", False)),
        }

    def verify(self, name: str) -> dict:
        if name != "paddleocr":
            raise ValueError("只支持验证 paddleocr")
        status = self.paddleocr_status()
        status["verified"] = status["package_installed"] and status["cache_ready"]
        return status

    def _resolve_cache_dir(self, raw_cache: Path) -> Path:
        if raw_cache.is_absolute():
            return raw_cache
        if raw_cache.parts and raw_cache.parts[0] == "data":
            return self.settings.data_root.joinpath(*raw_cache.parts[1:])
        return self.settings.data_root / raw_cache
