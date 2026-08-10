from pathlib import Path

from fastapi.testclient import TestClient

from zyrelay.app.core.config import (
    PROJECT_ROOT,
    Settings,
    configuration_inventory,
    validate_configuration,
)
from zyrelay.app.main import create_app
from zyrelay.app.semantics.migration import migrate_semantic_object
from zyrelay.plugin.dependencies import create_default_dependencies
from zyrelay.plugin.facade import DocIntelligencePlugin
from zyrelay.plugin.lifecycle import PluginLifecycleManager
from zyrelay.plugin.registry import PluginRegistry
from zyrelay.relay import RelayRequest, RelayService
from zyrelay.relay.models import RelayEnvironment, RelayInput, RelayMode
from zyrelay.resources import create_default_registry


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path / "data",
        enterprise_config_dir=PROJECT_ROOT / "config" / "enterprises",
        model_config=PROJECT_ROOT / "config" / "models.yaml",
        language_config=PROJECT_ROOT / "config" / "languages.yaml",
        threshold_config=PROJECT_ROOT / "config" / "thresholds.yaml",
    )


def test_configuration_center_is_versioned_and_valid(tmp_path) -> None:
    settings = _settings(tmp_path)
    inventory = configuration_inventory(settings)
    assert {"labels", "business_objects", "models", "languages", "thresholds"} <= set(
        inventory
    )
    assert all(len(item["hash"]) == 64 for item in inventory.values())
    assert validate_configuration(settings.language_config) == []


def test_resource_registry_exposes_marketplace_manifest(tmp_path) -> None:
    registry = create_default_registry(_settings(tmp_path), include_paddleocr=False)
    manifest = registry.manifest("heuristic-layout")
    assert manifest.compatibility["api_version"] == "v1"
    assert manifest.license
    assert registry.health()["heuristic-layout"]["available"] is True


def test_plugin_lifecycle_can_validate_and_disable(tmp_path) -> None:
    plugin = DocIntelligencePlugin(
        create_default_dependencies(settings=_settings(tmp_path))
    )
    registry = PluginRegistry()
    registry.register(plugin)
    lifecycle = PluginLifecycleManager(registry)
    assert lifecycle.validate_manifest(plugin.get_manifest()).valid is True
    lifecycle.disable(plugin.get_manifest().plugin_id)
    assert lifecycle.enabled(plugin.get_manifest().plugin_id) is False


def test_semantic_migration_is_additive_and_keeps_id() -> None:
    value = migrate_semantic_object({"object_id": "SOBJ-TEST"})
    assert value == {"object_id": "SOBJ-TEST", "schema_version": "1.0"}


def test_relay_records_enterprise_scope_history_and_performance(
    sample_docx, tmp_path
) -> None:
    relay = RelayService(_settings(tmp_path))
    result = relay.process(
        RelayRequest(
            enterprise_id="default",
            department_id="engineering",
            team_id="platform",
            project_id="relay",
            environment=RelayEnvironment.TEST,
            mode=RelayMode.CODE_CONVENTION,
            input=RelayInput(file_name=sample_docx.name, file_path=str(sample_docx)),
        )
    )
    execution = relay.get_execution(result.execution_id)
    plan = relay.get_resources(result.execution_id)
    assert execution.execution_history
    assert plan.environment == "test"
    assert plan.department_id == "engineering"
    assert result.metrics["total_duration_ms"] >= 0


def test_plugin_health_and_lifecycle_http(tmp_path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    plugin_id = "zyrelay.doc-intelligence"
    assert client.get(f"/api/v1/plugins/{plugin_id}/health").json()["manifest_valid"]
    assert client.post(f"/api/v1/plugins/{plugin_id}/lifecycle/install").json()["valid"]
    assert client.post(f"/api/v1/plugins/{plugin_id}/lifecycle/update").json()["valid"]
    assert (
        client.post(f"/api/v1/plugins/{plugin_id}/lifecycle/disable").status_code == 200
    )
    assert client.get(f"/api/v1/plugins/{plugin_id}/health").json()["enabled"] is False
    assert (
        client.post(f"/api/v1/plugins/{plugin_id}/lifecycle/enable").json()["enabled"]
        is True
    )
