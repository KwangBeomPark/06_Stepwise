"""Tests for Milestone 5: SettingsDialog and CaptureOverlay."""

import pytest
from PySide6.QtWidgets import QApplication

from stepwise.ui.capture_overlay import CaptureOverlay
from stepwise.ui.settings_dialog import SettingsDialog


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_settings_dialog_save_and_retrieve(qapp: QApplication) -> None:
    initial = {
        "library_dir": "custom_macros",
        "results_dir": "custom_results",
        "countdown_seconds": 3,
        "default_wait_before": 0.5,
        "poll_interval": 0.3,
    }
    dlg = SettingsDialog(settings_dict=initial)
    assert dlg.txt_lib_dir.text() == "custom_macros"
    assert dlg.txt_res_dir.text() == "custom_results"
    assert dlg.spin_countdown.value() == 3

    # Edit a value
    dlg.spin_countdown.setValue(7)
    dlg._on_save()

    updated = dlg.get_settings()
    assert updated["countdown_seconds"] == 7
    dlg.close()


def test_capture_overlay_cancellation(qapp: QApplication) -> None:
    cancelled_received = False

    overlay = CaptureOverlay(mode="pick")

    def _on_cancelled() -> None:
        nonlocal cancelled_received
        cancelled_received = True

    overlay.cancelled.connect(_on_cancelled)
    overlay.cancelled.emit()
    assert cancelled_received is True
    overlay.close()
