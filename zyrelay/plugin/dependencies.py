from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from zyrelay import __version__
from zyrelay.app.core.config import Settings
from zyrelay.app.services import DocumentService

from .artifact_repository import ArtifactRepository, LocalArtifactRepository
from .capabilities import CapabilitiesProvider
from .config import PluginRuntimeConfig, load_plugin_config
from .execution_repository import LocalExecutionRepository
from .manifest import ManifestProvider


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16].upper()}"


@dataclass
class PluginDependencies:
    settings: Settings
    config: PluginRuntimeConfig
    document_service: DocumentService
    service_factory: Callable[[Settings], DocumentService]
    execution_repository: LocalExecutionRepository
    artifact_repository: ArtifactRepository
    manifest_provider: ManifestProvider
    capabilities_provider: CapabilitiesProvider
    clock: Callable[[], datetime] = utc_now
    id_generator: Callable[[str], str] = generate_id


def create_default_dependencies(
    *,
    settings: Settings | None = None,
    document_service: DocumentService | None = None,
) -> PluginDependencies:
    settings = settings or Settings.from_env()
    config = load_plugin_config(settings.plugin_config)
    if config.plugin.version != __version__:
        raise RuntimeError(
            f"插件配置版本 {config.plugin.version} 与包版本 {__version__} 不一致"
        )
    service = document_service or DocumentService(settings)
    capabilities = CapabilitiesProvider(config, settings)
    artifacts_root = settings.data_root / "plugin_artifacts"
    executions_root = settings.data_root / "plugin_executions"
    return PluginDependencies(
        settings=settings,
        config=config,
        document_service=service,
        service_factory=DocumentService,
        execution_repository=LocalExecutionRepository(executions_root),
        artifact_repository=LocalArtifactRepository(
            artifacts_root, generate_id
        ),
        manifest_provider=ManifestProvider(config, capabilities),
        capabilities_provider=capabilities,
    )
