"""Unit tests for PL Suite UserSetting path conventions and settings persistence."""

import json
from pathlib import Path

from stepwise.core.app_paths import (
    APPLICATION_NAME,
    PRODUCT_ID,
    USER_SETTING_DIR,
    default_library_directory,
    default_results_directory,
    installation_directory,
    load_user_settings,
    save_user_settings,
    user_settings_directory,
)


def test_naming_constants() -> None:
    assert APPLICATION_NAME == "Stepwise"
    assert PRODUCT_ID == "App06_Stepwise"
    assert USER_SETTING_DIR == "UserSetting"


def test_paths_structure() -> None:
    inst_dir = installation_directory()
    assert inst_dir.name == "Stepwise"
    assert "Programs" in str(inst_dir)

    u_dir = user_settings_directory()
    assert u_dir.name == "UserSetting"
    assert u_dir.is_dir()

    lib_dir = default_library_directory()
    assert lib_dir.name == "macros"
    assert lib_dir.parent == u_dir
    assert lib_dir.is_dir()

    res_dir = default_results_directory()
    assert res_dir.name == "results"
    assert res_dir.parent == u_dir
    assert res_dir.is_dir()


def test_load_and_save_user_settings(tmp_path: Path, monkeypatch) -> None:
    fake_user_setting = tmp_path / "UserSetting"
    fake_user_setting.mkdir()

    monkeypatch.setattr(
        "stepwise.core.app_paths.user_settings_directory",
        lambda: fake_user_setting,
    )
    monkeypatch.setattr(
        "stepwise.core.app_paths.config_file_path",
        lambda: fake_user_setting / "settings.json",
    )

    # Initial load returns defaults
    settings = load_user_settings()
    assert "library_dir" in settings
    assert "results_dir" in settings
    assert settings["countdown_seconds"] == 3

    # Modify and save
    settings["countdown_seconds"] = 10
    settings["test_custom_key"] = "hello"
    save_user_settings(settings)

    # Verify written file
    cfg_file = fake_user_setting / "settings.json"
    assert cfg_file.is_file()
    with open(cfg_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["countdown_seconds"] == 10
    assert data["test_custom_key"] == "hello"

    # Reload
    reloaded = load_user_settings()
    assert reloaded["countdown_seconds"] == 10
    assert reloaded["test_custom_key"] == "hello"
