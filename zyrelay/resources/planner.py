from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from zyrelay.app.core.config import Settings, load_yaml
from zyrelay.relay.repository import JsonRecordRepository

from .models import ResourceBindingRecord, ResourcePlan
from .registry import ResourceRegistry


class ResourcePlanner:
    default_bindings = {
        "pdf_parser": "pymupdf-parser",
        "docx_parser": "python-docx-parser",
        "ocr": "paddleocr",
        "layout": "heuristic-layout",
        "convention_classifier": "rule-convention-classifier",
        "evidence_validator": "rule-evidence-validator",
        "storage": "local-storage",
    }

    def __init__(self, settings: Settings, registry: ResourceRegistry) -> None:
        self.settings = settings
        self.registry = registry
        self.store = JsonRecordRepository(
            settings.data_root / "resource_plans", ResourcePlan
        )

    def build(
        self,
        *,
        execution_id: str,
        enterprise_id: str,
        requested_profile_id: str | None,
        recommended_profile_id: str | None,
    ) -> ResourcePlan:
        profile_path = self._profile_path(enterprise_id)
        config = load_yaml(profile_path) if profile_path.is_file() else {}
        resources = config.get("resources", {})
        bindings: dict[str, str] = {}
        fallbacks: dict[str, list[str]] = {}
        records: list[ResourceBindingRecord] = []
        for capability, system_default in self.default_bindings.items():
            configured = resources.get(capability, {})
            primary = str(configured.get("primary") or system_default)
            alternatives = [str(item) for item in configured.get("fallbacks", [])]
            if capability == "ocr" and "noop-ocr" not in alternatives:
                alternatives.append("noop-ocr")
            selected = primary if self.registry.available(primary) else None
            fallback_used = False
            rejected: list[str] = []
            if selected is None:
                rejected.append(primary)
                for item in alternatives:
                    if self.registry.available(item):
                        selected = item
                        fallback_used = True
                        break
                    rejected.append(item)
            if selected is None:
                raise ValueError(f"资源不可用且没有 fallback：{capability}")
            bindings[capability] = selected
            fallbacks[capability] = alternatives
            records.append(
                ResourceBindingRecord(
                    capability=capability,
                    selected_resource_id=selected,
                    selection_reason=(
                        "enterprise_profile" if configured else "system_default"
                    ),
                    fallback_used=fallback_used,
                    rejected_resources=rejected,
                )
            )
        profile_id = requested_profile_id or recommended_profile_id or str(
            config.get("profile_id", "system-default")
        )
        plan_hash = hashlib.sha256(
            json.dumps(
                {"profile_id": profile_id, "bindings": bindings, "fallbacks": fallbacks},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        plan = ResourcePlan(
            plan_id=f"RPLAN-{uuid.uuid4().hex[:16].upper()}",
            execution_id=execution_id,
            enterprise_id=enterprise_id,
            resource_profile_id=profile_id,
            bindings=bindings,
            fallback_bindings=fallbacks,
            selection_records=records,
            plan_hash=plan_hash,
        )
        self.store.save(plan, plan.plan_id)
        return plan

    def _profile_path(self, enterprise_id: str) -> Path:
        selected = self.settings.enterprise_config_dir / enterprise_id / "resources.yaml"
        if selected.is_file():
            return selected
        return self.settings.enterprise_config_dir / "default" / "resources.yaml"
