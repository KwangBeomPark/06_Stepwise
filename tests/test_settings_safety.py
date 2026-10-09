"""Settings failures preserve the original file and stay visible to the user."""

import json
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from stepwise.core import app_paths
from stepwise.ui import settings_dialog


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def config(tmp_path, monkeypatch):
    folder = tmp_path / "UserSetting"
    folder.mkdir()
    path = folder / "settings.json"
    monkeypatch.setattr(app_paths, "user_settings_directory", lambda: folder)
    monkeypatch.setattr(app_paths, "config_file_path", lambda: path)
    return path


def test_saved_zero_and_custom_backup_locations_win_over_defaults(config):
    value = {
        "countdown_seconds": 0,
        "library_dir": "external macros",
        "results_dir": "external results",
    }
    config.write_text(json.dumps(value), encoding="utf-8")
    loaded = app_paths.load_user_settings()
    assert all(loaded[key] == value[key] for key in value)


def test_failed_replace_keeps_original_and_cleans_owned_temp(config, monkeypatch):
    original = b'{"countdown_seconds": 0}'
    config.write_bytes(original)
    calls = []

    def fail(*args):
        calls.append(args)
        raise PermissionError("injected lock")

    monkeypatch.setattr(app_paths.os, "replace", fail)
    monkeypatch.setattr(app_paths, "Event", lambda: SimpleNamespace(wait=lambda _: None))
    with pytest.raises(PermissionError):
        app_paths.save_user_settings({"countdown_seconds": 8})
    assert len(calls) == 3
    assert config.read_bytes() == original
    assert not list(config.parent.glob("*.tmp"))


def test_failed_fsync_does_not_replace_original(config, monkeypatch):
    original = b'{"original": true}'
    config.write_bytes(original)

    def fail(_):
        raise OSError("injected full disk")

    monkeypatch.setattr(app_paths.os, "fsync", fail)
    with pytest.raises(OSError):
        app_paths.save_user_settings({"value": 1})
    assert config.read_bytes() == original
    assert not list(config.parent.glob("*.tmp"))


@pytest.mark.parametrize("original", [b'{"partial":', b'[]', b'\xff'])
def test_fallback_defaults_cannot_replace_damaged_settings(config, original):
    config.write_bytes(original)
    loaded = app_paths.load_user_settings()
    loaded["window_geometry"] = "updated layout"
    with pytest.raises(OSError):
        app_paths.save_user_settings(loaded)
    assert config.read_bytes() == original
    assert not list(config.parent.glob("*.tmp"))


def test_layout_save_on_close_preserves_damaged_settings(config, qapp):
    from stepwise.ui.main_window import MainWindow

    original = b'{"interrupted":'
    config.write_bytes(original)
    window = MainWindow()
    window.close()
    assert config.read_bytes() == original
    assert qapp is not None


def test_damage_detected_after_temp_write_is_not_overwritten(config, monkeypatch):
    config.write_bytes(b'{}')
    damaged = b'{"external interrupted update":'
    monkeypatch.setattr(app_paths.os, "fsync", lambda _: config.write_bytes(damaged))
    with pytest.raises(OSError):
        app_paths.save_user_settings({"countdown_seconds": 8})
    assert config.read_bytes() == damaged
    assert not list(config.parent.glob("*.tmp"))


def test_writability_probe_does_not_overwrite_existing_probe(tmp_path, monkeypatch):
    folder = tmp_path / "UserSetting"
    folder.mkdir()
    sentinel = folder / ".write_probe"
    sentinel.write_bytes(b"user-owned file")
    monkeypatch.setattr(app_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_paths.sys, "executable", str(tmp_path / "Stepwise.exe"))
    assert app_paths.user_settings_directory() == folder
    assert sentinel.read_bytes() == b"user-owned file"
    assert list(folder.iterdir()) == [sentinel]


def test_dialog_save_failure_stays_open_with_original_values(qapp, monkeypatch):
    dialog = settings_dialog.SettingsDialog({"countdown_seconds": 0})
    original = dict(dialog.get_settings())
    dialog.spin_countdown.setValue(9)

    def fail(_):
        raise PermissionError("injected permission")

    monkeypatch.setattr(settings_dialog, "save_user_settings", fail)
    warnings = []
    monkeypatch.setattr(settings_dialog.QMessageBox, "warning", lambda *args: warnings.append(args))
    dialog._on_save()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.get_settings() == original
    assert len(warnings) == 1
    dialog.close()
    assert qapp is not None


def test_results_button_opens_the_configured_external_folder(qapp, monkeypatch):
    dialog = settings_dialog.SettingsDialog({"results_dir": "external results ż"})
    opened = []
    monkeypatch.setattr(settings_dialog.os, "startfile", opened.append)
    dialog._open_results()
    assert opened == ["external results ż"]
    dialog.close()
    assert qapp is not None


def test_preflight_checks_the_selected_results_folder(qapp, monkeypatch):
    from stepwise.core.models import Macro
    from stepwise.ui import preflight_dialog

    captured = []
    monkeypatch.setattr(
        preflight_dialog, "run_preflight_checks", lambda **kwargs: captured.append(kwargs) or []
    )
    dialog = preflight_dialog.PreflightDialog(Macro(), results_dir="external checks")
    assert captured[0]["results_dir"] == "external checks"
    dialog.close()
    assert qapp is not None


@pytest.mark.parametrize("override", [None, "explicit results"])
def test_cli_uses_explicit_or_saved_results_directory(tmp_path, monkeypatch, override):
    from stepwise import cli

    macro = tmp_path / "macro.json"
    macro.write_text('{"name":"Fixture macro"}', encoding="utf-8")
    argv = ["stepwise", "run", str(macro)]
    if override:
        argv += ["--results-dir", override]
    monkeypatch.setattr(cli.sys, "argv", argv)
    monkeypatch.setattr(cli, "load_user_settings", lambda: {"results_dir": "saved results"})
    monkeypatch.setattr(
        cli,
        "GlobalHotkeyManager",
        lambda: SimpleNamespace(
            start=lambda: None, stop=lambda: None, register_hotkey=lambda *args, **kwargs: None
        ),
    )
    captured = []

    def run(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(
            run_id="fixture",
            duration_sec=0,
            total_rows=0,
            done_count=0,
            failed_count=0,
            interrupted_count=0,
            failure=None,
        )

    monkeypatch.setattr(cli, "run_macro", run)
    cli.main()
    assert captured[0]["results_dir"] == (override or "saved results")
