"""Package serialization and atomic file I/O for .swm (Stepwise Macro) archives.

Section 6.1 specifications:
- .swm is a zip package containing macro.json and images/
- Never bundles business data files
- Uses atomic write (temp file -> os.replace) to prevent file corruption
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from collections.abc import Mapping

from stepwise.core.migration import migrate_macro_data
from stepwise.core.models import Macro
from stepwise.core.schema import validate_macro_dict


def load_package(swm_path: str, extract_dir: str | None = None) -> tuple[Macro, str]:
    """Load a .swm package file, extract images to a directory, and return Macro and unpack directory."""
    if not os.path.exists(swm_path):
        raise FileNotFoundError(f"Macro package not found: {swm_path}")

    # If already a raw directory or JSON file
    if os.path.isdir(swm_path):
        json_path = os.path.join(swm_path, "macro.json")
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        validate_macro_dict(data)
        migrated = migrate_macro_data(data)
        return Macro.from_dict(migrated), swm_path

    if swm_path.endswith(".json"):
        with open(swm_path, encoding="utf-8") as f:
            data = json.load(f)
        validate_macro_dict(data)
        migrated = migrate_macro_data(data)
        return Macro.from_dict(migrated), os.path.dirname(os.path.abspath(swm_path))

    # Standard .swm (ZIP archive)
    target_dir = extract_dir or tempfile.mkdtemp(prefix="stepwise_pkg_")
    with zipfile.ZipFile(swm_path, "r") as zf:
        zf.extractall(target_dir)

    json_path = os.path.join(target_dir, "macro.json")
    if not os.path.exists(json_path):
        raise ValueError(f"Corrupt .swm package: missing macro.json in {swm_path}")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    validate_macro_dict(data)
    migrated = migrate_macro_data(data)
    return Macro.from_dict(migrated), target_dir


def save_package(
    macro: Macro,
    swm_path: str,
    image_files: Mapping[str, str | bytes] | None = None,
) -> None:
    """Save Macro to a .swm zip package using atomic write."""
    macro_dir = os.path.dirname(os.path.abspath(swm_path))
    os.makedirs(macro_dir, exist_ok=True)

    # Use a temporary file in the same directory for atomic replace across filesystem boundaries
    fd, temp_zip = tempfile.mkstemp(dir=macro_dir, prefix="stepwise_tmp_", suffix=".swm")
    os.close(fd)

    try:
        macro_dict = macro.to_dict()
        validate_macro_dict(macro_dict)
        json_bytes = json.dumps(macro_dict, indent=2, ensure_ascii=False).encode("utf-8")

        with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. Write macro.json
            zf.writestr("macro.json", json_bytes)

            # 2. Write images
            if image_files:
                for img_name, img_data in image_files.items():
                    # Normalize zip entry path under images/
                    entry_name = img_name if img_name.startswith("images/") else f"images/{img_name}"
                    if isinstance(img_data, bytes):
                        zf.writestr(entry_name, img_data)
                    elif isinstance(img_data, str) and os.path.exists(img_data):
                        zf.write(img_data, arcname=entry_name)

        # Atomic replacement
        os.replace(temp_zip, swm_path)
    finally:
        if os.path.exists(temp_zip):
            try:
                os.remove(temp_zip)
            except OSError:
                pass
