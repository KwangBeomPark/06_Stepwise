"""Tests for Anti-Lock Jiggler service and UI integrations."""

from __future__ import annotations

import threading
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from stepwise.core.models import ActionItem, Macro
from stepwise.engine.runner import run_macro
from stepwise.engine.timing import ExecutionController
from stepwise.services.jiggler import (
    Jiggler,
    active_jiggler,
    safe_jiggler_interval,
    send_jiggle_pulse,
)
from stepwise.ui.scheduler_dialog import SchedulerDialog
from stepwise.ui.settings_dialog import SettingsDialog


def test_safe_jiggler_interval_robustness():
    assert safe_jiggler_interval(45) == 45.0
    assert safe_jiggler_interval(100.5) == 100.5
    assert safe_jiggler_interval(None) == 45.0
    assert safe_jiggler_interval("invalid") == 45.0
    assert safe_jiggler_interval(2.0, min_val=10.0) == 10.0
    assert safe_jiggler_interval("60", min_val=10.0) == 60.0
    # Robustness against inf, nan, large values, and overflow
    assert safe_jiggler_interval(float("inf")) == 45.0
    assert safe_jiggler_interval("inf") == 45.0
    assert safe_jiggler_interval("-inf") == 45.0
    assert safe_jiggler_interval(float("nan")) == 45.0
    assert safe_jiggler_interval("nan") == 45.0
    assert safe_jiggler_interval("1e309") == 45.0  # Overflow to inf string
    assert safe_jiggler_interval(10**500) == 45.0  # Massive int causing OverflowError
    assert safe_jiggler_interval(10000.0, max_val=3600.0) == 3600.0


def test_send_jiggle_pulse_success():
    with patch("stepwise.services.input_win.send_inputs", return_value=2) as mock_send:
        result = send_jiggle_pulse()
        assert result is True
        mock_send.assert_called_once()
        inputs = mock_send.call_args[0][0]
        assert len(inputs) == 2
        # Check that VK_F15 (0x7E) was sent
        assert inputs[0].u.ki.wVk == 0x7E
        assert inputs[0].u.ki.dwFlags == 0
        assert inputs[1].u.ki.wVk == 0x7E
        assert inputs[1].u.ki.dwFlags != 0  # KEYEVENTF_KEYUP


def test_send_jiggle_pulse_handles_exception():
    with patch("stepwise.services.input_win.send_inputs", side_effect=RuntimeError("win32 error")):
        result = send_jiggle_pulse()
        assert result is False


def test_jiggler_lifecycle_and_stop():
    jiggler = Jiggler(interval_seconds=0.05, min_interval=0.01)
    assert not jiggler.is_running()

    pulse_event = threading.Event()

    def _on_pulse():
        pulse_event.set()
        return True

    with (
        patch("stepwise.services.jiggler.send_jiggle_pulse", side_effect=_on_pulse),
        patch("stepwise.services.jiggler.get_idle_duration_seconds", return_value=10.0),
    ):
        jiggler.start()
        assert jiggler.is_running()

        # Idempotent start
        jiggler.start()
        assert jiggler.is_running()

        # Wait for pulse to fire via Event
        assert pulse_event.wait(timeout=1.0)
        jiggler.stop()
        assert not jiggler.is_running()

        # Stop when already stopped
        jiggler.stop()
        assert not jiggler.is_running()


def test_jiggler_skips_pulse_when_system_is_active():
    # When user/macro is actively typing/clicking, idle duration is 0 -> should skip pulse
    jiggler = Jiggler(interval_seconds=0.05, min_interval=0.01)
    with (
        patch("stepwise.services.jiggler.send_jiggle_pulse") as mock_pulse,
        patch("stepwise.services.jiggler.get_idle_duration_seconds", return_value=0.0),
    ):
        jiggler.start()
        threading.Event().wait(timeout=0.1)
        jiggler.stop()
        mock_pulse.assert_not_called()


def test_jiggler_skips_pulse_when_idle_duration_is_none():
    # When GetLastInputInfo fails or on non-Windows (returns None) -> must skip pulse for safety
    jiggler = Jiggler(interval_seconds=0.05, min_interval=0.01)
    with (
        patch("stepwise.services.jiggler.send_jiggle_pulse") as mock_pulse,
        patch("stepwise.services.jiggler.get_idle_duration_seconds", return_value=None),
    ):
        jiggler.start()
        threading.Event().wait(timeout=0.1)
        jiggler.stop()
        mock_pulse.assert_not_called()


def test_jiggler_skips_pulse_when_paused():
    is_paused = True
    jiggler = Jiggler(
        interval_seconds=0.05,
        min_interval=0.01,
        should_pulse=lambda: not is_paused,
    )
    with (
        patch("stepwise.services.jiggler.send_jiggle_pulse") as mock_pulse,
        patch("stepwise.services.jiggler.get_idle_duration_seconds", return_value=10.0),
    ):
        jiggler.start()
        threading.Event().wait(timeout=0.1)
        mock_pulse.assert_not_called()
        assert jiggler.is_running(), "Jiggler thread must not terminate when paused"

        # Now resume -> pulse should fire
        is_paused = False
        pulse_event = threading.Event()
        mock_pulse.side_effect = lambda: (pulse_event.set(), True)[1]
        assert pulse_event.wait(timeout=1.0)
        assert jiggler.is_running()
        jiggler.stop()
        assert mock_pulse.call_count >= 1


def test_jiggler_pause_race_condition_does_not_break_loop():
    # Specifically tests final check branch: if should_pulse was True during loop start
    # but becomes False immediately before send_jiggle_pulse, it must 'continue' (not 'break').
    sequence = [True, False, True, True]
    idx = 0

    def check_pulse():
        nonlocal idx
        val = sequence[min(idx, len(sequence) - 1)]
        idx += 1
        return val

    jiggler = Jiggler(
        interval_seconds=0.05,
        min_interval=0.01,
        should_pulse=check_pulse,
    )

    pulse_event = threading.Event()

    with (
        patch("stepwise.services.jiggler.send_jiggle_pulse", side_effect=lambda: (pulse_event.set(), True)[1]),
        patch("stepwise.services.jiggler.get_idle_duration_seconds", return_value=10.0),
    ):
        jiggler.start()
        # Even though 2nd check (final gate) returned False, thread must continue and eventually pulse
        assert pulse_event.wait(timeout=1.0)
        assert jiggler.is_running()
        jiggler.stop()
        assert not jiggler.is_running()


def test_active_jiggler_context_manager():
    # Enabled
    with patch.object(Jiggler, "start") as mock_start, patch.object(Jiggler, "stop") as mock_stop:
        with active_jiggler(enabled=True, interval_seconds=30.0) as j:
            assert isinstance(j, Jiggler)
            assert j.interval == 30.0
            mock_start.assert_called_once()
            mock_stop.assert_not_called()
        mock_stop.assert_called_once()

    # Disabled
    with patch.object(Jiggler, "start") as mock_start, patch.object(Jiggler, "stop") as mock_stop:
        with active_jiggler(enabled=False) as j:
            assert j is None
        mock_start.assert_not_called()
        mock_stop.assert_not_called()


def test_run_macro_passes_jiggler_options_and_pause_gating():
    macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.01)])
    ctrl = ExecutionController()

    with patch("stepwise.engine.runner.active_jiggler") as mock_active:
        run_macro(
            macro=macro,
            rows_data=[{"col": "val"}],
            controller=ctrl,
            anti_lock_jiggler=True,
            jiggler_interval_seconds=50.0,
        )
        mock_active.assert_called_once()
        kwargs = mock_active.call_args[1]
        assert kwargs["enabled"] is True
        assert kwargs["interval_seconds"] == 50.0
        # Verify should_pulse evaluates to True when running, False when paused or stopped
        should_pulse = kwargs["should_pulse"]
        assert should_pulse() is True
        ctrl.pause()
        assert should_pulse() is False
        ctrl.resume()
        assert should_pulse() is True
        ctrl.stop()
        assert should_pulse() is False


def test_scheduler_dialog_uses_injected_settings(qapp: QApplication):
    macro = Macro(name="SchedMacro")
    # Initialized with user settings enabled=False, interval=60
    dlg = SchedulerDialog(macro=macro, jiggler_enabled=False, jiggler_interval=60.0)
    assert not dlg.chk_anti_lock.isChecked()
    assert dlg._jiggler_interval == 60.0
    assert "60" in dlg.chk_anti_lock.toolTip()

    # Initialized with user settings enabled=True, interval=30
    dlg_enabled = SchedulerDialog(macro=macro, jiggler_enabled=True, jiggler_interval=30.0)
    assert dlg_enabled.chk_anti_lock.isChecked()
    assert dlg_enabled._jiggler_interval == 30.0
    assert "30" in dlg_enabled.chk_anti_lock.toolTip()

    with patch("stepwise.ui.scheduler_dialog.Jiggler") as mock_jiggler_cls:
        instance = mock_jiggler_cls.return_value
        dlg_enabled.arm_schedule()
        assert dlg_enabled.is_armed
        mock_jiggler_cls.assert_called_once_with(interval_seconds=30.0)
        instance.start.assert_called_once()

        dlg_enabled.disarm_schedule()
        assert not dlg_enabled.is_armed
        instance.stop.assert_called_once()


def test_settings_dialog_loads_and_saves_jiggler_config(qapp: QApplication):
    settings_dict = {
        "anti_lock_jiggler_enabled": True,
        "anti_lock_jiggler_interval_sec": "50",  # String from JSON should be parsed safely
    }

    dlg = SettingsDialog(settings_dict=settings_dict)
    assert dlg.chk_jiggler.isChecked() is True
    assert dlg.spin_jiggler_interval.value() == 50

    # Modify settings in UI
    dlg.chk_jiggler.setChecked(False)
    dlg.spin_jiggler_interval.setValue(90)

    with patch("stepwise.ui.settings_dialog.save_user_settings") as mock_save:
        dlg._on_save()
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert saved["anti_lock_jiggler_enabled"] is False
        assert saved["anti_lock_jiggler_interval_sec"] == 90
