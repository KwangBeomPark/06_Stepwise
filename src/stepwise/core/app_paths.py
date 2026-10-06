"""PL Suite storage convention and UserSetting path management for Stepwise.

Follows the PL Suite (App01 ~ App10) standard:
%LOCALAPPDATA%\\Programs\\Stepwise\\UserSetting
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

APPLICATION_NAME = "Stepwise"
PRODUCT_ID = "App06_Stepwise"
USER_SETTING_DIR = "UserSetting"
CONFIG_FILENAME = "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "library_dir": "",
    "results_dir": "",
    "countdown_seconds": 3,
    "default_wait_before": 0.2,
    "image_confidence": 0.95,
    "window_geometry": None,
    "splitter_state": None,
}


def local_appdata_directory() -> Path:
    """Return the user's LocalAppData directory."""
    if os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"])
    if os.environ.get("USERPROFILE"):
        return Path(os.environ["USERPROFILE"]) / "AppData" / "Local"
    return Path.home() / "AppData" / "Local"


def installation_directory() -> Path:
    """Return the standard installation directory in Programs."""
    return local_appdata_directory() / "Programs" / APPLICATION_NAME


def user_settings_directory() -> Path:
    """Return the persistent UserSetting directory.

    In frozen builds running from the installation folder, use the executable's
    sibling UserSetting directory if writable. Otherwise, use %LOCALAPPDATA%\\Programs\\Stepwise\\UserSetting.
    """
    if getattr(sys, "frozen", False):
        exe_parent = Path(sys.executable).parent
        candidate = exe_parent / USER_SETTING_DIR
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            # Verify write permissions
            test_probe = candidate / ".write_probe"
            test_probe.write_text("ok", encoding="utf-8")
            test_probe.unlink(missing_ok=True)
            return candidate
        except OSError:
            pass

    path = installation_directory() / USER_SETTING_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_library_directory() -> Path:
    """Return the default macro library directory under UserSetting."""
    path = user_settings_directory() / "macros"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_results_directory() -> Path:
    """Return the default run results directory under UserSetting."""
    path = user_settings_directory() / "results"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file_path() -> Path:
    """Return the full path to settings.json."""
    return user_settings_directory() / CONFIG_FILENAME


def load_user_settings() -> dict[str, Any]:
    """Load user settings from settings.json, merged with defaults."""
    settings = dict(DEFAULT_SETTINGS)
    # Ensure default directories are filled if empty
    settings["library_dir"] = str(default_library_directory())
    settings["results_dir"] = str(default_results_directory())

    cfg_path = config_file_path()
    if cfg_path.is_file():
        try:
            with open(cfg_path, encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    settings.update(loaded)
        except Exception:
            # Fallback to defaults on corrupted file
            pass

    return settings


def save_user_settings(settings: dict[str, Any]) -> None:
    """Save user settings to settings.json atomically to avoid corruption."""
    import time

    cfg_path = config_file_path()
    cfg_dir = cfg_path.parent
    cfg_dir.mkdir(parents=True, exist_ok=True)

    # Clean dict to ensure JSON serializability
    serializable = {}
    for k, v in settings.items():
        if isinstance(v, (str, int, float, bool, list, dict)) or v is None:
            serializable[k] = v
        else:
            serializable[k] = str(v)

    data = json.dumps(serializable, indent=2, ensure_ascii=False)
    temp_fd, temp_path = tempfile.mkstemp(prefix="settings_", suffix=".tmp", dir=str(cfg_dir))
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            f.write(data)

        # Windows retry loop for os.replace to tolerate transient file locks
        replaced = False
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                os.replace(temp_path, cfg_path)
                replaced = True
                break
            except PermissionError as pe:
                last_err = pe
                time.sleep(0.05 * (2**attempt))

        if not replaced and last_err:
            raise last_err
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise
