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
        "document_classifier": "minilm-document-classifier",
        "language_detection": "fasttext-language",
        "layout": "doclayout-yolo",
        "table_recognition": "table-transformer",
        "spell_correction": "symspell",
        "code_detection": "tree-sitter-code",
        "ner": "gliner-ner",
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
        department_id: str | None = None,
        team_id: str | None = None,
        project_id: str | None = None,
        environment: str = "dev",
        requested_profile_id: str | None,
        recommended_profile_id: str | None,
    ) -> ResourcePlan:
        profile_path = self._profile_path(enterprise_id)
        config = load_yaml(profile_path) if profile_path.is_file() else {}
        default_path = (
            self.settings.enterprise_config_dir / "default" / "resources.yaml"
        )
        default_resources = (
            load_yaml(default_path).get("resources", {})
            if default_path.is_file()
            else {}
        )
        # Enterprise profiles are overrides, not complete copies of the default
        # profile. This preserves parser/storage fallbacks while allowing one
        # enterprise to disable or replace a single model capability.
        resources = {
            capability: {**value} for capability, value in default_resources.items()
        }
        for capability, value in config.get("resources", {}).items():
            resources[capability] = {**resources.get(capability, {}), **value}
        # Context entries are deliberately YAML-only overlays.  The precedence
        # is environment < department < team < project, making resource choice
        # deterministic and auditable without a new orchestration layer.
        contexts = config.get("contexts", {})
        selectors = [
            ("environments", environment),
            ("departments", department_id),
            ("teams", team_id),
            ("projects", project_id),
        ]
        applied_contexts: list[str] = []
        for group, identifier in selectors:
            overlay = contexts.get(group, {}).get(identifier or "", {})
            for capability, value in overlay.get("resources", {}).items():
                resources[capability] = {**resources.get(capability, {}), **value}
            if overlay:
                applied_contexts.append(f"{group}:{identifier}")
        bindings: dict[str, str] = {}
        fallbacks: dict[str, list[str]] = {}
        records: list[ResourceBindingRecord] = []
        health: dict[str, dict] = {}
        for capability, system_default in self.default_bindings.items():
            configured = resources.get(capability, {})
            if configured and configured.get("enabled") is False:
                bindings[capability] = "disabled"
                fallbacks[capability] = []
                health[capability] = {
                    "selected_resource_id": "disabled",
                    "available": False,
                    "status": "disabled_by_enterprise_profile",
                    "primary_resource_id": None,
                    "fallbacks": [],
                }
                records.append(
                    ResourceBindingRecord(
                        capability=capability,
                        selected_resource_id="disabled",
                        selection_reason="enterprise_profile_disabled",
                        enabled=False,
                        planned_execution=False,
                        actual_execution=False,
                        skip_reason="enterprise_profile_disabled",
                        gate_decision="skip",
                        compatibility={"api_version": "v1", "status": "disabled"},
                    )
                )
                continue
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
            selected_health = self.registry.get(selected).health_check()
            selected_resource = self.registry.get(selected)
            health[capability] = {
                "selected_resource_id": selected,
                "available": selected_health.available,
                "status": selected_health.status,
                "details": selected_health.details,
                "primary_resource_id": primary,
                "primary_available": self.registry.available(primary),
                "fallbacks": alternatives,
                "plugin_name": selected,
                "model_version": str(getattr(selected_resource, "version", "unknown")),
            }
            records.append(
                ResourceBindingRecord(
                    capability=capability,
                    selected_resource_id=selected,
                    selection_reason=(
                        "enterprise_profile" if configured else "system_default"
                    ),
                    fallback_used=fallback_used,
                    rejected_resources=rejected,
                    plugin_name=selected,
                    model_version=str(getattr(selected_resource, "version", "unknown")),
                    health=selected_health.model_dump(mode="json"),
                    compatibility={"api_version": "v1", "status": "compatible"},
                )
            )
        profile_id = (
            requested_profile_id
            or recommended_profile_id
            or str(config.get("profile_id", "system-default"))
        )
        plan_hash = hashlib.sha256(
            json.dumps(
                {
                    "profile_id": profile_id,
                    "bindings": bindings,
                    "fallbacks": fallbacks,
                    "enterprise": enterprise_id,
                    "department": department_id,
                    "team": team_id,
                    "project": project_id,
                    "environment": environment,
                    "contexts": applied_contexts,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        plan = ResourcePlan(
            plan_id=f"RPLAN-{uuid.uuid4().hex[:16].upper()}",
            execution_id=execution_id,
            enterprise_id=enterprise_id,
            department_id=department_id,
            team_id=team_id,
            project_id=project_id,
            environment=environment,
            resource_config_version=str(config.get("version", "unversioned")),
            resource_config_hash=hashlib.sha256(
                json.dumps(config, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            resource_profile_id=profile_id,
            bindings=bindings,
            fallback_bindings=fallbacks,
            selection_records=records,
            resource_health=health,
            plan_hash=plan_hash,
        )
        self.store.save(plan, plan.plan_id)
        return plan

    def _profile_path(self, enterprise_id: str) -> Path:
        selected = (
            self.settings.enterprise_config_dir / enterprise_id / "resources.yaml"
        )
        if selected.is_file():
            return selected
        return self.settings.enterprise_config_dir / "default" / "resources.yaml"
