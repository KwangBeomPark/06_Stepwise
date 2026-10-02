"""Macro schema validation and version checks (Section 6)."""

from __future__ import annotations

from typing import Any

from stepwise.engine.errors import MacroSyntaxError

CURRENT_SCHEMA_VERSION = 1
VALID_ACTION_TYPES = {
    "click",
    "click_image",
    "type_text",
    "key",
    "wait",
    "wait_image",
    "wait_image_gone",
    "group",
}


def validate_macro_dict(data: dict[str, Any]) -> None:
    """Validate macro JSON dictionary structure."""
    if not isinstance(data, dict):
        raise MacroSyntaxError("Macro must be a JSON object.")

    version = data.get("schema_version")
    if version is None:
        raise MacroSyntaxError("Missing 'schema_version' in macro file.")
    try:
        ver_int = int(version)
    except (ValueError, TypeError) as err:
        raise MacroSyntaxError(f"Invalid schema_version: {version}") from err

    if ver_int > CURRENT_SCHEMA_VERSION:
        raise MacroSyntaxError(
            f"This macro was created with a newer version of Stepwise (v{ver_int}). "
            "Please update Stepwise to open this file."
        )

    for section_name in ("setup", "per_row", "cleanup"):
        items = data.get(section_name)
        if items is not None:
            if not isinstance(items, list):
                raise MacroSyntaxError(f"Section '{section_name}' must be a list of actions.")
            _validate_items(items, in_group=False)


def _validate_items(items: list[Any], in_group: bool = False) -> None:
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise MacroSyntaxError(f"Action item at index {idx} must be a JSON object.")

        act_type = item.get("type")
        if not act_type or act_type not in VALID_ACTION_TYPES:
            raise MacroSyntaxError(f"Unknown action type '{act_type}' at item {idx}.")

        if act_type == "group":
            if in_group:
                raise MacroSyntaxError("Nested groups are not supported in MVP.")
            child_items = item.get("items")
            if child_items is not None and not isinstance(child_items, list):
                raise MacroSyntaxError(f"Group '{item.get('name', '')}' items must be a list.")
            if child_items:
                _validate_items(child_items, in_group=True)
        else:
            # Check Guard / Verify compatibility
            if act_type in ("click_image", "wait_image", "wait_image_gone"):
                if item.get("guard") or item.get("verify"):
                    raise MacroSyntaxError(
                        f"Image action '{act_type}' cannot have separate Guard or Verify images."
                    )
