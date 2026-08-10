from pathlib import Path

import pytest

from zyrelay.app.core.config import PROJECT_ROOT, Settings
from zyrelay.plugin.dependencies import create_default_dependencies
from zyrelay.plugin.facade import DocIntelligencePlugin


@pytest.fixture
def plugin_factory(tmp_path: Path):
    def build() -> DocIntelligencePlugin:
        settings = Settings(
            data_root=tmp_path / "data",
            label_config=PROJECT_ROOT / "config" / "labels.yaml",
            business_object_config=(PROJECT_ROOT / "config" / "business_objects.yaml"),
            code_convention_label_config=(
                PROJECT_ROOT / "config" / "code_convention_labels.yaml"
            ),
            code_rule_pattern_config=(
                PROJECT_ROOT / "config" / "code_rule_patterns.yaml"
            ),
            plugin_config=PROJECT_ROOT / "config" / "plugin.yaml",
            ground_truth_dir=PROJECT_ROOT / "config" / "ground_truth",
            llm_enabled=False,
        )
        return DocIntelligencePlugin(create_default_dependencies(settings=settings))

    return build
