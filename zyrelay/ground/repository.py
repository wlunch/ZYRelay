from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from zyrelay.app.core.config import CONFIG_ROOT, Settings, load_yaml
from zyrelay.relay.repository import JsonRecordRepository

from .models import GroundProfile, GroundSelection, GroundSnapshot


class GroundRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.ground_config_dir
        self.selection_store = JsonRecordRepository(
            settings.data_root / "ground_selections", GroundSelection
        )
        self.snapshot_store = JsonRecordRepository(
            settings.data_root / "ground_snapshots", GroundSnapshot
        )

    def profiles(self) -> dict[str, GroundProfile]:
        result: dict[str, GroundProfile] = {}
        for path in sorted(self.root.glob("*.yaml")):
            if path.name == "profiles.yaml":
                continue
            raw = load_yaml(path)
            if raw.get("profile_id"):
                result[raw["profile_id"]] = GroundProfile.model_validate(raw)
        return result

    def bindings(self) -> dict[str, Any]:
        path = self.root / "profiles.yaml"
        return load_yaml(path) if path.is_file() else {}

    def resolve_profile(
        self, profile_id: str
    ) -> tuple[GroundProfile, list[GroundProfile]]:
        profiles = self.profiles()
        if profile_id not in profiles:
            raise ValueError(f"Ground Profile 不存在：{profile_id}")
        chain: list[GroundProfile] = []
        seen: set[str] = set()
        current = profiles[profile_id]
        while current:
            if current.profile_id in seen:
                raise ValueError("Ground Profile extends 存在循环继承")
            seen.add(current.profile_id)
            chain.append(current)
            current = profiles.get(current.extends) if current.extends else None
            if current is None and chain[-1].extends:
                raise ValueError(f"父 Ground Profile 不存在：{chain[-1].extends}")
        chain.reverse()
        merged: dict[str, Any] = {}
        for item in chain:
            merged = self._merge_profile(merged, item.model_dump(mode="python"))
        return GroundProfile.model_validate(merged), chain

    def create_snapshot(
        self,
        *,
        snapshot_id: str,
        execution_id: str,
        profile: GroundProfile,
        inherited: list[GroundProfile],
    ) -> GroundSnapshot:
        assets = {
            "labels": profile.labels,
            "aliases": profile.aliases,
            "rule_patterns": profile.rule_patterns,
            "business_objects": profile.business_objects,
            "validation_rules": profile.validation_rules,
        }
        source_files: list[str] = []
        source_hashes: dict[str, str] = {}
        resolved: dict[str, list[Any]] = {}
        for kind, paths in assets.items():
            values: list[Any] = []
            for item in paths:
                path = self._resolve_asset_path(item)
                logical = self._logical_path(path)
                content = load_yaml(path)
                source_files.append(logical)
                source_hashes[logical] = self._sha256(path.read_bytes())
                values.append(content)
            resolved[kind] = values
        resolved_hash = self._hash_json(
            {
                "profile": profile.model_dump(mode="json"),
                "assets": resolved,
                "inherited": [item.profile_id for item in inherited],
            }
        )
        snapshot = GroundSnapshot(
            snapshot_id=snapshot_id,
            execution_id=execution_id,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            labels=resolved["labels"],
            aliases=resolved["aliases"],
            rule_patterns=resolved["rule_patterns"],
            business_objects=resolved["business_objects"],
            validation_rules=resolved["validation_rules"],
            source_files=list(dict.fromkeys(source_files)),
            source_hashes=source_hashes,
            resolved_hash=resolved_hash,
        )
        self.snapshot_store.save(snapshot, snapshot.snapshot_id)
        return snapshot

    def profile_sources(
        self, profiles: list[GroundProfile]
    ) -> tuple[list[str], dict[str, str]]:
        files: list[str] = []
        hashes: dict[str, str] = {}
        profile_map = self.profiles()
        for profile in profiles:
            path = self.root / f"{profile.profile_id}.yaml"
            if not path.is_file() and profile.profile_id in profile_map:
                path = self.root / f"{profile_map[profile.profile_id].profile_id}.yaml"
            if path.is_file():
                logical = self._logical_path(path)
                files.append(logical)
                hashes[logical] = self._sha256(path.read_bytes())
        return files, hashes

    @staticmethod
    def _merge_profile(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = {**base}
        for key, value in override.items():
            if key == "extends" and value is None:
                continue
            if isinstance(value, list):
                merged[key] = list(dict.fromkeys([*(base.get(key) or []), *value]))
            elif value is not None:
                merged[key] = value
        return merged

    @staticmethod
    def _sha256(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()

    @classmethod
    def _hash_json(cls, value: object) -> str:
        payload = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return cls._sha256(payload)

    def _resolve_asset_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        parts = path.parts
        if parts and parts[0] == "config":
            return CONFIG_ROOT.joinpath(*parts[1:])
        candidate = self.root / path
        return candidate

    @staticmethod
    def _logical_path(path: Path) -> str:
        try:
            return str(path.relative_to(CONFIG_ROOT.parent))
        except ValueError:
            return path.name
