"""Macro schema migration handlers."""

from __future__ import annotations

from typing import Any

from stepwise.core.schema import CURRENT_SCHEMA_VERSION


def migrate_macro_data(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate macro data dictionary to the current schema version."""
    _version = int(data.get("schema_version", 1))

    # Future migrations from v1 -> v2 etc. will be chained here
    # Example:
    # if version == 0:
    #     data = _migrate_v0_to_v1(data)
    #     version = 1

    data["schema_version"] = CURRENT_SCHEMA_VERSION
    return data
