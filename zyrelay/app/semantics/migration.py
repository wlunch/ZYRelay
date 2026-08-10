"""Explicit, lossless migrations for semantic object payloads."""

from __future__ import annotations

from typing import Any

SEMANTIC_SCHEMA_VERSION = "1.0"


def migrate_semantic_object(value: dict[str, Any]) -> dict[str, Any]:
    """Make a pre-1.0 additive object readable without changing its ID."""
    migrated = dict(value)
    migrated.setdefault("schema_version", SEMANTIC_SCHEMA_VERSION)
    if migrated["schema_version"] != SEMANTIC_SCHEMA_VERSION:
        raise ValueError(f"unsupported_semantic_schema:{migrated['schema_version']}")
    return migrated


def migrate_semantic_section(value: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(value)
    migrated.setdefault("schema_version", SEMANTIC_SCHEMA_VERSION)
    migrated["objects"] = [
        migrate_semantic_object(item) for item in migrated.get("objects", [])
    ]
    return migrated
