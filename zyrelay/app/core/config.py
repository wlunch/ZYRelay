from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = (
    PROJECT_ROOT / "config"
    if (PROJECT_ROOT / "config").is_dir()
    else PACKAGE_ROOT / "_config"
)
DEFAULT_DATA_ROOT = (
    PROJECT_ROOT / "data"
    if (PROJECT_ROOT / "config").is_dir()
    else Path.home() / ".zyrelay" / "data"
)


@dataclass(frozen=True)
class Settings:
    data_root: Path = DEFAULT_DATA_ROOT
    label_config: Path = CONFIG_ROOT / "labels.yaml"
    business_object_config: Path = CONFIG_ROOT / "business_objects.yaml"
    code_convention_label_config: Path = (
        CONFIG_ROOT / "code_convention_labels.yaml"
    )
    code_rule_pattern_config: Path = CONFIG_ROOT / "code_rule_patterns.yaml"
    plugin_config: Path = CONFIG_ROOT / "plugin.yaml"
    ground_config_dir: Path = CONFIG_ROOT / "ground"
    enterprise_config_dir: Path = CONFIG_ROOT / "enterprises"
    model_config: Path = CONFIG_ROOT / "models.yaml"
    ground_truth_dir: Path = CONFIG_ROOT / "ground_truth"
    max_file_size: int = 25 * 1024 * 1024
    keep_prepared: bool = True
    fuzzy_enabled: bool = False
    fuzzy_threshold: float = 88.0
    llm_enabled: bool = False
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_root=Path(os.getenv("ZYRELAY_DATA_ROOT", cls.data_root)),
            label_config=Path(os.getenv("ZYRELAY_LABEL_CONFIG", cls.label_config)),
            business_object_config=Path(
                os.getenv("ZYRELAY_BUSINESS_OBJECT_CONFIG", cls.business_object_config)
            ),
            code_convention_label_config=Path(
                os.getenv(
                    "ZYRELAY_CODE_CONVENTION_LABEL_CONFIG",
                    cls.code_convention_label_config,
                )
            ),
            code_rule_pattern_config=Path(
                os.getenv(
                    "ZYRELAY_CODE_RULE_PATTERN_CONFIG",
                    cls.code_rule_pattern_config,
                )
            ),
            plugin_config=Path(
                os.getenv("ZYRELAY_PLUGIN_CONFIG", cls.plugin_config)
            ),
            ground_config_dir=Path(
                os.getenv("ZYRELAY_GROUND_CONFIG_DIR", cls.ground_config_dir)
            ),
            enterprise_config_dir=Path(
                os.getenv(
                    "ZYRELAY_ENTERPRISE_CONFIG_DIR", cls.enterprise_config_dir
                )
            ),
            model_config=Path(
                os.getenv("ZYRELAY_MODEL_CONFIG", cls.model_config)
            ),
            ground_truth_dir=Path(
                os.getenv("ZYRELAY_GROUND_TRUTH_DIR", cls.ground_truth_dir)
            ),
            max_file_size=int(os.getenv("ZYRELAY_MAX_FILE_SIZE", cls.max_file_size)),
            keep_prepared=_env_bool("ZYRELAY_KEEP_PREPARED", cls.keep_prepared),
            fuzzy_enabled=_env_bool("ZYRELAY_FUZZY_ENABLED", cls.fuzzy_enabled),
            fuzzy_threshold=float(
                os.getenv("ZYRELAY_FUZZY_THRESHOLD", cls.fuzzy_threshold)
            ),
            llm_enabled=_env_bool("ZYRELAY_LLM_ENABLED", cls.llm_enabled),
            llm_base_url=os.getenv("ZYRELAY_LLM_BASE_URL", ""),
            llm_api_key=os.getenv("ZYRELAY_LLM_API_KEY", ""),
            llm_model=os.getenv("ZYRELAY_LLM_MODEL", ""),
        )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.lower() in {"1", "true", "yes", "on"}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        content = yaml.safe_load(stream)
    return content or {}


def config_hash(path: Path) -> str:
    canonical = json.dumps(
        load_yaml(path), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def ground_truth_version(settings: Settings) -> str:
    metadata = load_yaml(settings.ground_truth_dir / "labels.yaml")
    return str(metadata.get("version", "unversioned"))
