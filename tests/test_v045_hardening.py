"""Tests for v0.4.5 Hardening: Data integrity, input resilience, and fail-closed safety."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from stepwise.core.models import ActionItem, Macro
from stepwise.engine.actions import execute_action
from stepwise.engine.errors import AbortRequested, StepFailure
from stepwise.engine.timing import ExecutionController
from stepwise.services.clipboard import (
    is_clipboard_session_active,
    record_stepwise_clipboard_write,
    restore_clipboard_if_sequence_matches,
    scoped_clipboard_session,
    temporary_clipboard_text,
    write_clipboard_text,
)
from stepwise.services.data_source import (
    DuplicateHeaderError,
    col_idx_to_letter,
    validate_and_build_headers,
)
from stepwise.services.input_win import (
    press_keys,
    release_all_modifiers,
    release_keys,
    type_unicode_string,
)
from stepwise.services.updater import verify_authenticode_signature
from stepwise.ui.main_window import MainWindow
from stepwise.ui.preflight_dialog import PreflightDialog
from stepwise.ui.strings import Strings


def test_col_idx_to_letter():
    assert col_idx_to_letter(0) == "A"
    assert col_idx_to_letter(25) == "Z"
    assert col_idx_to_letter(26) == "AA"
    assert col_idx_to_letter(27) == "AB"


def test_duplicate_headers_rejected():
    # Valid unique headers
    assert validate_and_build_headers(["ID", "Name", "Amount"]) == ["ID", "Name", "Amount"]

    # Duplicates case-insensitive
    with pytest.raises(DuplicateHeaderError) as exc_info:
        validate_and_build_headers(["Amount", "Name", "amount"])
    msg = str(exc_info.value)
    assert "Amount" in msg
    assert "A열" in msg
    assert "C열" in msg


def test_updater_signature_fail_closed_on_powershell_error(tmp_path):
    # When PowerShell fails or returns non-zero, it must fail closed (return False)
    test_exe = tmp_path / "dummy.exe"
    test_exe.write_bytes(b"dummy")

    with patch("stepwise.services.updater.subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "PowerShell execution policy blocked script"
        mock_run.return_value = mock_proc

        valid, reason = verify_authenticode_signature(test_exe)
        assert valid is False
        assert "exit code 1" in reason or "verification error" in reason


def test_release_all_modifiers():
    with patch("stepwise.services.input_win.send_inputs", return_value=5) as mock_send:
        assert release_all_modifiers() is True
        mock_send.assert_called_once()
        inputs = mock_send.call_args[0][0]
        assert len(inputs) == 5  # Ctrl, Shift, Alt, LWin, RWin


def test_press_keys_handles_send_inputs_failure():
    released_keys = []
    with (
        patch("stepwise.services.input_win.send_inputs", return_value=1),  # Partial send
        patch("stepwise.services.input_win.release_keys", side_effect=lambda vk: released_keys.append(list(vk))) as mock_rel,
    ):
        result = press_keys("ctrl+s")
        assert result is False
        mock_rel.assert_called_once()
        # Verifies that both Ctrl and S were passed to release_keys!
        assert len(released_keys[0]) == 2


def test_release_keys_sends_keyup_for_all_keys_and_modifiers():
    with patch("stepwise.services.input_win.send_inputs") as mock_send:
        mock_send.side_effect = lambda inputs: len(inputs)
        # Combination: Ctrl (VK 17) + S (VK 83)
        release_keys([17, 83])
        # Two calls: 1 for [S-up, Ctrl-up], 1 for release_all_modifiers
        assert mock_send.call_count == 2
        combo_inputs = mock_send.call_args_list[0][0][0]
        assert len(combo_inputs) == 2
        assert combo_inputs[0].u.ki.wVk == 83  # S first (reverse order)
        assert combo_inputs[0].u.ki.dwFlags == 2  # KEYEVENTF_KEYUP
        assert combo_inputs[1].u.ki.wVk == 17  # Ctrl second
        assert combo_inputs[1].u.ki.dwFlags == 2  # KEYEVENTF_KEYUP


def test_press_keys_stops_immediately_on_abort():
    should_stop = MagicMock(side_effect=[False, True])  # Stop on 2nd iteration
    with (
        patch("stepwise.services.input_win.send_inputs", return_value=2),
        patch("stepwise.services.input_win.release_all_modifiers") as mock_clean,
    ):
        result = press_keys("enter", repeat=10, should_stop=should_stop)
        assert result is False
        mock_clean.assert_called_once()


def test_type_unicode_string_surrogate_pairs():
    # Text with emoji (e.g. 😊 = U+1F60A, requiring 2 UTF-16 code units: 0xD83D, 0xDE0A)
    emoji_text = "Hi 😊"
    with patch("stepwise.services.input_win.send_inputs") as mock_send:
        mock_send.side_effect = lambda inputs: len(inputs)
        result = type_unicode_string(emoji_text, char_delay=0.0)
        assert result is True
        mock_send.assert_called_once()
        inputs = mock_send.call_args[0][0]
        # 'H', 'i', ' ' = 3 characters (6 inputs) + emoji 2 code units (4 inputs) = 10 inputs
        assert len(inputs) == 10
        # Check that surrogate code units were sent
        scans = [inp.u.ki.wScan for inp in inputs[6:]]
        assert scans[0] == 0xD83D
        assert scans[2] == 0xDE0A


def test_actions_raises_step_failure_on_press_keys_failure():
    action = ActionItem(type="key", keys="ctrl+c")
    with patch("stepwise.engine.actions.press_keys", return_value=False):
        with pytest.raises(StepFailure) as exc_info:
            execute_action(action)
        assert "Failed to send key combination 'ctrl+c'" in str(exc_info.value)


def test_actions_raises_abort_requested_when_user_stopped():
    ctrl = ExecutionController()
    ctrl.stop()
    action = ActionItem(type="key", keys="enter", repeat=5)
    with patch("stepwise.engine.actions.press_keys", return_value=False):
        with pytest.raises(AbortRequested):
            execute_action(action, controller=ctrl)


def test_scoped_clipboard_session_prevents_per_action_restore():
    def fake_write(text, **kw):
        if not kw.get("is_restore"):
            record_stepwise_clipboard_write(100)
        return True, 100

    with (
        patch("stepwise.services.clipboard.snapshot_restorable_text", return_value="initial_clip"),
        patch("stepwise.services.clipboard.get_clipboard_sequence_number", return_value=100),
        patch("stepwise.services.clipboard.write_clipboard_text", side_effect=fake_write) as mock_write,
    ):
        assert not is_clipboard_session_active()

        with scoped_clipboard_session():
            assert is_clipboard_session_active()
            # Inside session: temporary_clipboard_text must NOT restore immediately on exit
            with temporary_clipboard_text("pasted_value", restore=True) as written:
                assert written is True

            # write_clipboard_text should have been called only for "pasted_value", not for restore yet
            assert mock_write.call_count == 1
            assert mock_write.call_args[0][0] == "pasted_value"

        # After session ends: original clipboard must be restored once
        assert not is_clipboard_session_active()
        assert mock_write.call_count == 2
        assert mock_write.call_args[0][0] == "initial_clip"


def test_scoped_clipboard_session_skips_restore_if_no_stepwise_write():
    with (
        patch("stepwise.services.clipboard.snapshot_restorable_text", return_value="initial_clip"),
        patch("stepwise.services.clipboard.get_clipboard_sequence_number", return_value=100),
        patch("stepwise.services.clipboard.write_clipboard_text", return_value=(True, 100)) as mock_write,
    ):
        with scoped_clipboard_session():
            pass  # No writes!

        # Zero write_clipboard_text calls! Original clipboard is untouched!
        assert mock_write.call_count == 0


def test_scoped_clipboard_session_skips_restore_if_sequence_changed():
    def fake_write(text, **kw):
        if not kw.get("is_restore"):
            record_stepwise_clipboard_write(100)
        return True, 100

    # If a macro step copied something (Ctrl+C) or user copied, sequence number increments
    seq_calls = [105]  # end=105 != 100
    with (
        patch("stepwise.services.clipboard.snapshot_restorable_text", return_value="initial_clip"),
        patch("stepwise.services.clipboard.get_clipboard_sequence_number", side_effect=seq_calls),
        patch("stepwise.services.clipboard.write_clipboard_text", side_effect=fake_write) as mock_write,
    ):
        with scoped_clipboard_session():
            with temporary_clipboard_text("pasted_value", restore=True):
                pass

        # mock_write called once for "pasted_value", but NOT restored at end because sequence changed!
        assert mock_write.call_count == 1
        assert mock_write.call_args[0][0] == "pasted_value"


def test_scoped_clipboard_session_skips_restore_for_non_text_clipboard():
    def fake_write(text, **kw):
        if not kw.get("is_restore"):
            record_stepwise_clipboard_write(100)
        return True, 100

    # Initial clipboard contains an image or file list (snapshot_restorable_text returns None)
    with (
        patch("stepwise.services.clipboard.snapshot_restorable_text", return_value=None),
        patch("stepwise.services.clipboard.get_clipboard_sequence_number", return_value=100),
        patch("stepwise.services.clipboard.write_clipboard_text", side_effect=fake_write) as mock_write,
    ):
        with scoped_clipboard_session():
            with temporary_clipboard_text("pasted_value", restore=True):
                pass

        # Only the pasted value was written; no restore attempting to overwrite with None/""
        assert mock_write.call_count == 1


def test_actions_with_real_execution_controller_success():
    ctrl = ExecutionController()
    action = ActionItem(type="key", keys="enter", repeat=3)
    with patch("stepwise.services.input_win.send_inputs", return_value=2):
        execute_action(action, controller=ctrl, default_wait_before=0.0)


def test_press_keys_repeats_with_real_controller_wait():
    ctrl = ExecutionController()
    with patch("stepwise.services.input_win.send_inputs", return_value=2) as mock_send:
        result = press_keys(
            "enter",
            repeat=3,
            interval=0.001,
            wait_fn=ctrl.wait,
            should_stop=ctrl.is_stopped,
        )
        assert result is True
        assert mock_send.call_count == 3


class FakeHotkeys:
    def __init__(self) -> None:
        self.stopped = False

    def start(self) -> None:
        pass

    def register_hotkey(self, _vk: int, _mod: int, callback: object = None) -> int:
        return 1

    def stop(self) -> None:
        self.stopped = True


class DeferredThread:
    def __init__(self, target: object, **_kwargs: object) -> None:
        self.target = target
        self.running = True

    def start(self) -> None:
        pass

    def is_alive(self) -> bool:
        return self.running


def test_main_window_range_selection_with_exclusions(qapp: QApplication):
    win = MainWindow()
    win._current_macro = Macro(name="TestMacro")
    win._data_rows = [{"val": "1"}, {"val": "2"}, {"val": "3"}, {"val": "4"}]
    win._data_row_nums = [1, 2, 3, 4]

    # Exclude row 1
    win.data_panel._row_numbers = [1, 2, 3, 4]
    win.data_panel._row_statuses = {1: "Skipped"}

    # User chooses to run start_row=2, end_row_index=3
    opts = {"start_row": 2, "end_row_index": 3}

    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch("stepwise.ui.main_window.run_macro"),
        patch("stepwise.ui.main_window.ExecutionSnapshot") as mock_snap,
    ):
        win._start_execution(opts)
        assert mock_snap.call_count == 1
        snap_kwargs = mock_snap.call_args[1]
        rows = snap_kwargs["rows"]
        nums = snap_kwargs["row_numbers"]
        # Sliced range [2, 3] -> filtered out 1 (not in slice) -> should contain exactly rows 2 and 3!
        assert len(rows) == 2
        assert nums == (2, 3)
        assert rows[0]["val"] == "2"
        assert rows[1]["val"] == "3"

    win._teardown_runner()
    win.close()


def test_main_window_aborts_when_all_rows_in_range_excluded(qapp: QApplication):
    win = MainWindow()
    win._current_macro = Macro(name="TestMacro")
    win._data_rows = [{"val": "1"}, {"val": "2"}]
    win._data_row_nums = [1, 2]

    # Mark both rows as Skipped/Done
    win.data_panel._row_numbers = [1, 2]
    win.data_panel._row_statuses = {1: "Skipped", 2: "Done"}

    opts = {"start_row": 1, "end_row_index": 2}

    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch.object(win, "_show_info_dialog") as mock_box,
        patch("stepwise.ui.main_window.ExecutionSnapshot") as mock_snap,
    ):
        win._start_execution(opts)
        assert mock_box.call_count == 1
        assert mock_snap.call_count == 0  # Execution cancelled before creating worker snapshot!
        assert not win._is_running

    win.close()


def test_updater_powershell_env_var_channel(tmp_path):
    test_exe = tmp_path / "My App (Special & Test).exe"
    test_exe.write_bytes(b"dummy_bytes")

    with patch("stepwise.services.updater.subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = '{"Status":"NotSigned","Thumbprint":"","Subject":"","HasTimestamp":false}'
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        valid, reason = verify_authenticode_signature(test_exe)
        assert valid is False
        assert mock_run.call_count == 1
        call_kwargs = mock_run.call_args[1]
        env = call_kwargs["env"]
        # Verify that the path was passed via STEPWISE_VERIFY_PATH environment variable, not cmdline!
        assert env.get("STEPWISE_VERIFY_PATH") == str(test_exe.resolve())


def test_main_window_excludes_skipped_and_done_rows_from_execution(qapp: QApplication):
    win = MainWindow()
    win._current_macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.01)])
    win._data_rows = [{"val": "1"}, {"val": "2"}, {"val": "3"}]
    win._data_row_nums = [1, 2, 3]
    win._data_headers = ["val"]

    # Mark row #2 as Skipped
    win.data_panel._row_numbers = [1, 2, 3]
    win.data_panel._row_statuses = {2: "Skipped"}

    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch("stepwise.ui.main_window.run_macro"),
        patch("stepwise.ui.main_window.ExecutionSnapshot") as mock_snap,
    ):
        win._start_execution({})
        assert mock_snap.call_count == 1
        snap_kwargs = mock_snap.call_args[1]
        rows = snap_kwargs["rows"]
        nums = snap_kwargs["row_numbers"]
        assert len(rows) == 2
        assert nums == (1, 3)
        assert rows[0]["val"] == "1"
        assert rows[1]["val"] == "3"

    win.close()


def test_preflight_dialog_ignores_blank_cells_in_excluded_rows(qapp: QApplication):
    macro = Macro(name="TestMacro", per_row=[ActionItem(type="type_text", text="{val}")])
    # Row 1 is valid, row 2 is blank, row 3 is valid
    rows = [{"val": "valid1"}, {"val": ""}, {"val": "valid3"}]
    nums = [1, 2, 3]

    # Without exclusion, row 2 triggers BLANK_CELLS error
    dlg_blocked = PreflightDialog(macro=macro, rows_data=rows, row_numbers=nums)
    assert any(i.code == "BLANK_CELLS" for i in dlg_blocked.issues)
    assert dlg_blocked._has_blocking_issues() is True
    dlg_blocked.close()

    # With row 2 excluded, BLANK_CELLS is NOT reported for row 2, and start is enabled!
    dlg_ok = PreflightDialog(macro=macro, rows_data=rows, row_numbers=nums, excluded_row_numbers={2})
    assert not any(i.code == "BLANK_CELLS" for i in dlg_ok.issues)
    assert dlg_ok._has_blocking_issues() is False
    assert dlg_ok.btn_start.isEnabled() is True
    dlg_ok.close()


def test_preflight_dialog_all_rows_excluded_shows_error(qapp: QApplication):
    macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.1)])
    rows = [{"val": "1"}, {"val": "2"}]
    nums = [1, 2]

    dlg = PreflightDialog(macro=macro, rows_data=rows, row_numbers=nums, excluded_row_numbers={1, 2})
    assert any(i.code == "ALL_ROWS_EXCLUDED" for i in dlg.issues)
    assert dlg._has_blocking_issues() is True
    assert dlg.btn_start.isEnabled() is False
    dlg.close()


def test_preflight_dialog_previews_first_non_excluded_row(qapp: QApplication):
    macro = Macro(name="TestMacro", per_row=[ActionItem(type="type_text", text="{val}")])
    rows = [{"val": "first_excluded"}, {"val": "second_active"}]
    nums = [1, 2]

    dlg = PreflightDialog(macro=macro, rows_data=rows, row_numbers=nums, excluded_row_numbers={1})
    preview_text = dlg.lbl_range_preview.text()
    assert "second_active" in preview_text
    assert "first_excluded" not in preview_text
    dlg.close()


def test_scoped_clipboard_session_no_deadlock_with_real_set_clipboard():
    # Tests that scoped_clipboard_session exit does not deadlock when set_clipboard_text is real
    import stepwise.services.clipboard as clip

    mock_u32 = MagicMock()
    mock_u32.OpenClipboard.return_value = 1
    mock_u32.CloseClipboard.return_value = 1
    mock_u32.EmptyClipboard.return_value = 1
    mock_u32.SetClipboardData.return_value = 1
    mock_u32.GetClipboardSequenceNumber.return_value = 100
    mock_u32.IsClipboardFormatAvailable.return_value = 1

    mock_k32 = MagicMock()
    mock_k32.GlobalAlloc.return_value = 1
    mock_k32.GlobalLock.return_value = 1
    mock_k32.GlobalUnlock.return_value = 1
    mock_k32.GlobalFree.return_value = 0

    with (
        patch.object(clip, "user32", mock_u32),
        patch.object(clip, "kernel32", mock_k32),
        patch.object(clip.ctypes, "memmove"),
        patch.object(clip, "snapshot_restorable_text", return_value="original"),
        patch.object(clip, "get_clipboard_sequence_number", return_value=100),
    ):
        with clip.scoped_clipboard_session():
            clip.set_clipboard_text("payload")
        # If there were a re-entrant deadlock on _session_lock, execution would freeze here!


def test_main_window_run_1_row_skips_excluded_row_and_runs_first_active(qapp: QApplication):
    win = MainWindow()
    win._current_macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.01)])
    win._data_rows = [{"val": "skipped1"}, {"val": "active2"}, {"val": "active3"}]
    win._data_row_nums = [1, 2, 3]

    # Row 1 is Skipped
    win.data_panel._row_numbers = [1, 2, 3]
    win.data_panel._row_statuses = {1: "Skipped"}

    opts = {"start_row": 1, "end_row_index": 3, "run_1_row": True}

    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch("stepwise.ui.main_window.run_macro"),
        patch("stepwise.ui.main_window.ExecutionSnapshot") as mock_snap,
    ):
        win._start_execution(opts)
        assert mock_snap.call_count == 1
        snap_kwargs = mock_snap.call_args[1]
        rows = snap_kwargs["rows"]
        nums = snap_kwargs["row_numbers"]
        # Must run exactly 1 row, and that row must be the active Row 2!
        assert len(rows) == 1
        assert nums == (2,)
        assert rows[0]["val"] == "active2"
        # opts must record custom_row_nums = [2] so retry can target the exact row
        assert win._last_run_opts["custom_row_nums"] == [2]

    win.close()


def test_main_window_retry_after_run_1_row_with_skipped_row_1(qapp: QApplication):
    win = MainWindow()
    win._current_macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.01)])
    win._data_rows = [{"val": "skipped1"}, {"val": "active2"}, {"val": "active3"}]
    win._data_row_nums = [1, 2, 3]

    # Row 1 is Skipped
    win.data_panel._row_numbers = [1, 2, 3]
    win.data_panel._row_statuses = {1: "Skipped"}

    opts = {"start_row": 1, "end_row_index": 3, "run_1_row": True}

    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch("stepwise.ui.main_window.run_macro"),
    ):
        win._start_execution(opts)
        assert win._last_run_opts["custom_row_nums"] == [2]

        # Simulate Row 2 failing, then user clicks retry failed rows
        with patch.object(win, "_start_execution") as mock_start:
            win._retry_failed_rows([2])
            mock_start.assert_called_once()
            retry_opts = mock_start.call_args[0][0]
            # Retry must target exactly Row 2, not break or fail to find rows
            assert retry_opts["custom_row_nums"] == [2]
            assert len(retry_opts["custom_rows"]) == 1
            assert retry_opts["custom_rows"][0]["val"] == "active2"

    win.close()


def test_clipboard_write_atomic_cas_inside_open_lock():
    import stepwise.services.clipboard as clip

    mock_u32 = MagicMock()
    mock_u32.OpenClipboard.return_value = 1
    mock_u32.EmptyClipboard.return_value = 1
    mock_u32.SetClipboardData.return_value = 12345
    mock_u32.CloseClipboard.return_value = 1
    mock_u32.GetClipboardSequenceNumber.return_value = 777

    mock_k32 = MagicMock()
    mock_k32.GlobalAlloc.return_value = 54321
    mock_k32.GlobalLock.return_value = 11111
    mock_k32.GlobalUnlock.return_value = 1

    with (
        patch.object(clip, "user32", mock_u32),
        patch.object(clip, "kernel32", mock_k32),
        patch.object(clip.ctypes, "memmove"),
    ):
        # 1. Write without expected_seq succeeds and returns (True, 777)
        ok, seq = write_clipboard_text("data")
        assert ok is True
        assert seq == 777
        assert mock_u32.SetClipboardData.call_count == 1

        # 2. Write with mismatching expected_seq fails CAS and returns (False, None)
        mock_u32.SetClipboardData.reset_mock()
        ok, seq = write_clipboard_text("data", expected_seq=555)
        assert ok is False
        assert seq is None
        # SetClipboardData must NOT be called when sequence does not match!
        assert mock_u32.SetClipboardData.call_count == 0

        # 3. Write with matching expected_seq succeeds
        mock_u32.SetClipboardData.reset_mock()
        ok, seq = write_clipboard_text("data", expected_seq=777)
        assert ok is True
        assert seq == 777
        assert mock_u32.SetClipboardData.call_count == 1


def test_clipboard_restore_aborts_if_sequence_mismatch_inside_lock():
    import stepwise.services.clipboard as clip

    mock_u32 = MagicMock()
    mock_u32.OpenClipboard.return_value = 1
    mock_u32.EmptyClipboard.return_value = 1
    mock_u32.SetClipboardData.return_value = 12345
    mock_u32.CloseClipboard.return_value = 1
    mock_u32.GetClipboardSequenceNumber.return_value = 888  # Different from expected 777

    mock_k32 = MagicMock()
    mock_k32.GlobalAlloc.return_value = 54321
    mock_k32.GlobalLock.return_value = 11111
    mock_k32.GlobalUnlock.return_value = 1

    with (
        patch.object(clip, "user32", mock_u32),
        patch.object(clip, "kernel32", mock_k32),
        patch.object(clip.ctypes, "memmove"),
    ):
        restored = restore_clipboard_if_sequence_matches("original", expected_seq=777)
        assert restored is False
        assert mock_u32.SetClipboardData.call_count == 0


def test_on_run_only_row_targets_exact_row_even_if_row_1_is_done_or_skipped(qapp: QApplication):
    """Codex Sol audit regression: Run-only Row 1 must NEVER slip to Row 2 when Row 1 is Done/Skipped."""
    win = MainWindow()
    win._current_macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.01)])
    win._data_rows = [{"val": "row1_done"}, {"val": "row2_pending"}]
    win._data_row_nums = [1, 2]

    # Row 1 is Done
    win.data_panel._row_numbers = [1, 2]
    win.data_panel._row_statuses = {1: "Done"}

    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch("stepwise.ui.main_window.run_macro"),
        patch("stepwise.ui.main_window.ExecutionSnapshot") as mock_snap,
    ):
        # User right clicks Row 1 and chooses "Run only this row"
        win._on_run_only_row(1)
        assert mock_snap.call_count == 1
        snap_kwargs = mock_snap.call_args[1]
        rows = snap_kwargs["rows"]
        nums = snap_kwargs["row_numbers"]

        # MUST execute Row 1, NEVER Row 2!
        assert len(rows) == 1
        assert nums == (1,)
        assert rows[0]["val"] == "row1_done"

    win.close()


def test_get_clipboard_text_returns_none_on_globallock_or_data_failure():
    """Codex Sol audit regression: read failures must return None, not empty string, to avoid overwriting."""
    import stepwise.services.clipboard as clip

    mock_u32 = MagicMock()
    mock_u32.OpenClipboard.return_value = 1
    mock_u32.CloseClipboard.return_value = 1
    mock_u32.IsClipboardFormatAvailable.return_value = 1

    # Scenario 1: GetClipboardData returns NULL
    mock_u32.GetClipboardData.return_value = 0
    with patch.object(clip, "user32", mock_u32):
        assert clip.get_clipboard_text() is None
        assert clip.snapshot_restorable_text() is None

    # Scenario 2: GlobalLock returns NULL
    mock_u32.GetClipboardData.return_value = 1234
    mock_k32 = MagicMock()
    mock_k32.GlobalLock.return_value = 0
    with patch.object(clip, "user32", mock_u32), patch.object(clip, "kernel32", mock_k32):
        assert clip.get_clipboard_text() is None
        assert clip.snapshot_restorable_text() is None


def test_temporary_clipboard_does_not_pollute_session_sequence_outside_lock():
    """Codex Sol audit regression: user copy outside lock must NOT be overwritten by CAS restore."""
    import stepwise.services.clipboard as clip

    # Stepwise writes sequence 100.
    # While running, user presses Ctrl+C, moving sequence to 105.
    seq_state = {"current": 100}

    def fake_get_seq():
        return seq_state["current"]

    def fake_write(text, **kwargs):
        # Emulate write_clipboard_text behavior by recording write sequence inside lock
        seq = seq_state["current"]
        if not kwargs.get("is_restore"):
            clip.record_stepwise_clipboard_write(seq)
        return True, seq

    with (
        patch.object(clip, "snapshot_restorable_text", return_value="initial_clip"),
        patch.object(clip, "write_clipboard_text", side_effect=fake_write),
        patch.object(clip, "get_clipboard_sequence_number", side_effect=fake_get_seq),
        patch.object(clip, "restore_clipboard_if_sequence_matches", wraps=clip.restore_clipboard_if_sequence_matches) as mock_restore,
    ):
        with clip.scoped_clipboard_session():
            with clip.temporary_clipboard_text("stepwise_text", restore=True):
                pass
            # Stepwise recorded sequence 100!
            assert clip._session_last_stepwise_seq == 100

            # External user copy occurs outside Stepwise lock (sequence becomes 105)
            seq_state["current"] = 105

        # At session end, current sequence is 105 != expected 100.
        # Restore is skipped because 105 != 100, protecting user's copy!
        assert mock_restore.call_count == 0


def test_scoped_clipboard_session_generation_prevents_cross_session_restoration():
    """Codex Sol audit regression: if Session 2 starts during Session 1's 50ms delay, Session 1 restore aborts."""
    import stepwise.services.clipboard as clip

    with (
        patch.object(clip, "snapshot_restorable_text", return_value="session1_clip"),
        patch.object(clip, "write_clipboard_text", return_value=(True, 200)),
        patch.object(clip, "restore_clipboard_if_sequence_matches") as mock_restore,
    ):
        # 1. Nesting scenario
        session1 = clip.scoped_clipboard_session()
        session1.__enter__()
        clip.record_stepwise_clipboard_write(200)

        session2 = clip.scoped_clipboard_session()
        session2.__enter__()

        session1.__exit__(None, None, None)
        assert mock_restore.call_count == 0
        session2.__exit__(None, None, None)

    # 2. Sequential scenario: Session 1 ends, but before its delayed restore executes, a new root Session 2 starts!
    with patch.object(clip, "snapshot_restorable_text", return_value="session1_clip"):
        gen1 = None
        with clip.scoped_clipboard_session():
            clip.record_stepwise_clipboard_write(300)
            gen1 = clip._session_generation

        # Start new root session immediately (generation increments)
        with clip.scoped_clipboard_session():
            gen2 = clip._session_generation
            assert gen2 > gen1
            # Verify that calling restore with old gen1 fails CAS inside lock!
            ok, _ = clip.write_clipboard_text("old", expected_gen=gen1, expected_seq=300, is_restore=True)
            assert ok is False


def test_generation_barrier_prevents_new_session_during_restoration():
    """Codex Sol audit regression: multi-threaded barrier proving _session_lock protects restore against new sessions."""
    import threading
    import time

    import stepwise.services.clipboard as clip

    restore_entered_lock = threading.Event()
    worker_started_attempt = threading.Event()
    restore_completed = threading.Event()
    new_session_entered = threading.Event()
    worker_errors = []

    def fake_open(_hwnd):
        restore_entered_lock.set()
        # Wait until worker thread is actively attempting to start a new session
        worker_started_attempt.wait(timeout=1.0)
        time.sleep(0.03)
        return 1

    def fake_close():
        # Marked inside the protected critical section before _session_lock release
        restore_completed.set()
        return 1

    def worker():
        try:
            # Wait until restore has acquired _session_lock and called OpenClipboard
            restore_entered_lock.wait(timeout=1.0)
            worker_started_attempt.set()
            # Attempt to start a new root session; MUST be blocked by _session_lock until restore finishes!
            with clip.scoped_clipboard_session():
                new_session_entered.set()
                assert restore_completed.is_set(), "Worker thread entered new session BEFORE restore completed!"
        except Exception as e:
            worker_errors.append(e)

    mock_set_data = MagicMock(return_value=12345)

    with (
        patch.object(clip, "snapshot_restorable_text", return_value="initial"),
        patch.object(clip.user32, "OpenClipboard", side_effect=fake_open),
        patch.object(clip.user32, "EmptyClipboard", return_value=1),
        patch.object(clip.user32, "SetClipboardData", mock_set_data),
        patch.object(clip.user32, "CloseClipboard", side_effect=fake_close),
        patch.object(clip.kernel32, "GlobalAlloc", return_value=1),
        patch.object(clip.kernel32, "GlobalLock", return_value=1),
        patch.object(clip.kernel32, "GlobalUnlock", return_value=1),
        patch.object(clip.ctypes, "memmove"),
        patch.object(clip.user32, "GetClipboardSequenceNumber", return_value=200),
        patch.object(clip, "get_clipboard_sequence_number", return_value=200),
    ):
        t = threading.Thread(target=worker)
        t.start()

        with clip.scoped_clipboard_session():
            clip.record_stepwise_clipboard_write(200)

        t.join(timeout=2.0)
        if worker_errors:
            raise worker_errors[0]
        assert new_session_entered.is_set()
        assert mock_set_data.call_count == 1


def test_temporary_clipboard_restore_guarded_against_interleaved_session():
    """Codex Sol audit regression: temporary restore aborted if a newer session started in between."""
    import stepwise.services.clipboard as clip

    mock_empty = MagicMock(return_value=1)
    mock_set_data = MagicMock(return_value=123)

    # 1. Temporary context writes seq 101 at generation G
    with patch.object(clip, "snapshot_restorable_text", return_value="temp_original"):
        with patch.object(clip, "write_clipboard_text", return_value=(True, 101)):
            ctx = clip.temporary_clipboard_text("temp_payload", restore=True)
            ctx.__enter__()

        # 2. Before temporary context exits, a new root session starts and writes at 102
        with clip.scoped_clipboard_session():
            clip.record_stepwise_clipboard_write(102)

            # 3. Temporary context attempts to restore its original text
            # Since a session is active (depth > 0 and generation incremented),
            # restore MUST be rejected without touching EmptyClipboard or SetClipboardData!
            with (
                patch.object(clip.user32, "EmptyClipboard", mock_empty),
                patch.object(clip.user32, "SetClipboardData", mock_set_data),
                patch.object(clip, "get_clipboard_sequence_number", return_value=101),
            ):
                ctx.__exit__(None, None, None)

            # Verify that the active session's tracking sequence remains 102!
            assert clip._session_last_stepwise_seq == 102
            # Verify that restore never mutated the clipboard!
            assert mock_empty.call_count == 0
            assert mock_set_data.call_count == 0


def test_type_unicode_step_by_step_atomic_surrogates_and_partial_cleanup():
    """Codex Sol audit regression: emojis must not be split across should_stop, partial sends must clean up."""
    # Text: "A😊B"
    text = "A😊B"
    checked_chars = []

    def mock_should_stop():
        checked_chars.append("stop_check")
        return False

    with patch("stepwise.services.input_win.send_inputs") as mock_send:
        mock_send.side_effect = lambda inputs: len(inputs)
        result = type_unicode_string(text, char_delay=0.001, should_stop=mock_should_stop)
        assert result is True
        # stop_check is called exactly 3 times (once before 'A', once before '😊', once before 'B')
        # NEVER between the two surrogate code units of '😊'!
        assert len(checked_chars) == 3

    # Partial send cleanup test:
    # If send_inputs returns 1 (odd number: down sent, up failed), it must send release for that wScan!
    with patch("stepwise.services.input_win.send_inputs") as mock_send:
        mock_send.side_effect = [1, 1]  # First call returns 1 (partial), second call cleans up with 1
        result = type_unicode_string("X", char_delay=0.001)
        assert result is False
        assert mock_send.call_count == 2
        cleanup_input = mock_send.call_args_list[1][0][0][0]
        assert cleanup_input.u.ki.dwFlags == 0x0004 | 0x0002  # KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        assert cleanup_input.u.ki.wScan == ord("X")


def test_toolbar_test_1_row_runs_even_if_row_marked_done(qapp: QApplication):
    """Toolbar 'Test 1 Row' must execute the selected row even if it was previously marked Done."""
    win = MainWindow()
    win._current_macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.01)])
    win._data_rows = [{"val": "done_row"}, {"val": "other_row"}]
    win._data_row_nums = [1, 2]
    win.data_panel._row_numbers = [1, 2]
    win.data_panel._row_statuses = {1: "Done"}

    # Select row 0 in table (row_num 1)
    win.data_panel.table.selectRow(0)

    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch("stepwise.ui.main_window.run_macro"),
        patch("stepwise.ui.main_window.ExecutionSnapshot") as mock_snap,
    ):
        win._on_test_1_row_clicked()
        assert mock_snap.call_count == 1
        snap_kwargs = mock_snap.call_args[1]
        assert len(snap_kwargs["rows"]) == 1
        assert snap_kwargs["row_numbers"] == (1,)
        assert snap_kwargs["rows"][0]["val"] == "done_row"


def test_main_window_all_done_prompts_and_resets(qapp: QApplication):
    """When all rows in range are Done, interactive execution prompts and resets statuses if confirmed."""
    from PySide6.QtWidgets import QMessageBox

    win = MainWindow()
    win._current_macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.01)])
    win._data_rows = [{"val": "r1"}, {"val": "r2"}]
    win._data_row_nums = [1, 2]
    win.data_panel._row_numbers = [1, 2]
    win.data_panel._row_statuses = {1: "Done", 2: "Done"}

    opts = {"start_row": 1, "end_row_index": 2}

    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch("stepwise.ui.main_window.run_macro"),
        patch("stepwise.ui.main_window.ExecutionSnapshot") as mock_snap,
        patch("stepwise.ui.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes) as mock_q,
    ):
        win._start_execution(opts)
        assert mock_q.call_count == 1
        # Data statuses must have been reset to empty
        assert win.data_panel._row_statuses == {}
        # Execution must have started for all 2 rows
        assert mock_snap.call_count == 1
        assert len(mock_snap.call_args[1]["rows"]) == 2


def test_preflight_dialog_breakdown_label(qapp: QApplication):
    """Preflight dialog displays excluded breakdown accurately scoped to range."""
    macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.1)])
    rows = [{"val": "1"}, {"val": "2"}, {"val": "3"}]
    nums = [1, 2, 3]
    statuses = {1: "Done", 2: "Skipped"}

    dlg = PreflightDialog(
        macro=macro,
        rows_data=rows,
        row_numbers=nums,
        excluded_row_numbers={1, 2},
        row_statuses=statuses,
    )
    preview_text = dlg.lbl_range_preview.text()
    assert "ℹ️" in preview_text
    dlg.close()


def test_main_window_scheduled_execution_all_excluded_no_modal(qapp: QApplication):
    """Scheduled execution with all rows excluded must not raise AttributeError or open modal QMessageBox."""
    win = MainWindow()
    win._current_macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.01)])
    win._data_rows = [{"val": "1"}, {"val": "2"}]
    win._data_row_nums = [1, 2]
    win.data_panel._row_numbers = [1, 2]
    win.data_panel._row_statuses = {1: "Skipped", 2: "Skipped"}

    opts = {"scheduled": True, "start_row": 1, "end_row_index": 2}

    with (
        patch("stepwise.ui.main_window.QMessageBox.warning") as mock_warn,
        patch("stepwise.ui.main_window.QMessageBox.information") as mock_info,
        patch("stepwise.ui.main_window.QMessageBox.question") as mock_quest,
    ):
        win._start_execution(opts)
        assert mock_warn.call_count == 0
        assert mock_info.call_count == 0
        assert mock_quest.call_count == 0
        assert win.status_bar.currentMessage() == Strings.ISSUE_ALL_ROWS_EXCLUDED


def test_preflight_dialog_all_done_activates_reset_and_run(qapp: QApplication):
    """When all rows in range are Done, PreflightDialog surfaces the Reset & Run button and runs countdown."""
    macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.1)])
    rows = [{"val": "1"}, {"val": "2"}]
    nums = [1, 2]
    statuses = {1: "Done", 2: "Done"}

    dlg = PreflightDialog(
        macro=macro,
        rows_data=rows,
        row_numbers=nums,
        excluded_row_numbers={1, 2},
        row_statuses=statuses,
        countdown_seconds=5,
    )
    # ALL_ROWS_DONE warning issue present, not an error
    assert any(i.code == "ALL_ROWS_DONE" for i in dlg.issues)
    assert dlg._has_blocking_issues() is False
    # Reset & Run button must be unhidden and enabled
    assert not dlg.btn_reset_and_run.isHidden()
    assert dlg.btn_reset_and_run.isEnabled() is True

    # Clicking Reset & Run initiates countdown
    dlg._on_reset_and_run_clicked()
    assert dlg._countdown_active is True
    assert dlg._pending_reset_statuses is True

    # Finish countdown
    dlg._countdown_remaining = 0
    dlg._countdown_tick()
    assert dlg.confirmed_opts.get("reset_statuses") is True
    assert dlg.result() == PreflightDialog.Accepted
    dlg.close()


def test_preflight_dialog_all_done_with_blocking_errors_blocks_reset_run(qapp: QApplication):
    """Even if all rows are Done, if the underlying data has blocking errors (e.g. blank cells), Reset & Run is blocked."""
    macro = Macro(name="TestMacro", per_row=[ActionItem(type="type_text", text="{val}")])
    rows = [{"val": "good"}, {"val": ""}]  # Row 2 has blank cell required for {val}
    nums = [1, 2]
    statuses = {1: "Done", 2: "Done"}

    dlg = PreflightDialog(
        macro=macro,
        rows_data=rows,
        row_numbers=nums,
        excluded_row_numbers={1, 2},
        row_statuses=statuses,
    )
    # Must report BLANK_CELLS error
    assert any(i.code == "BLANK_CELLS" for i in dlg.issues)
    assert dlg._has_blocking_issues() is True
    # Reset & Run must be disabled to prevent bypassing preflight checks
    assert dlg.btn_reset_and_run.isEnabled() is False
    dlg.close()


def test_retry_failed_rows_does_not_clear_completed_rows_after_reset_run(qapp: QApplication):
    """When retrying failed rows after an initial run that used reset_statuses, successful rows must stay Done."""
    win = MainWindow()
    win._current_macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.01)])
    win._data_rows = [{"val": "1"}, {"val": "2"}, {"val": "3"}]
    win._data_row_nums = [1, 2, 3]
    win.data_panel._row_numbers = [1, 2, 3]

    # Initial execution with reset_statuses=True
    opts = {"reset_statuses": True, "start_row": 1, "end_row_index": 3}
    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch("stepwise.ui.main_window.run_macro"),
    ):
        win._start_execution(opts)

    # In _last_run_opts, reset_statuses must have been popped/consumed!
    assert "reset_statuses" not in win._last_run_opts

    # Now simulate first run completed: reset running guards
    win._is_running = False
    win._execution_phase = "idle"
    win.data_panel.set_running(False)
    win._worker_thread = None

    # Now simulate row 1 succeeded (Done), row 2 failed (Failed), row 3 pending
    win.data_panel._row_statuses = {1: "Done", 2: "Failed", 3: "Pending"}

    # Retrying failed rows must spawn a new snapshot with rows 2 and 3
    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch("stepwise.ui.main_window.run_macro"),
        patch("stepwise.ui.main_window.ExecutionSnapshot") as mock_snap,
    ):
        win._retry_failed_rows()
        assert mock_snap.call_count == 1
        snap_kwargs = mock_snap.call_args[1]
        assert snap_kwargs["row_numbers"] == (2, 3)

    # Row 1 must remain "Done", NEVER wiped!
    assert win.data_panel._row_statuses.get(1) == "Done"


def test_preflight_dialog_cancel_stops_countdown(qapp: QApplication):
    """Calling reject() on PreflightDialog cancels any running countdown timer."""
    macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.1)])
    rows = [{"val": "1"}]
    nums = [1]

    dlg = PreflightDialog(
        macro=macro,
        rows_data=rows,
        row_numbers=nums,
        countdown_seconds=5,
    )
    dlg._start_countdown()
    assert dlg._countdown_active is True
    assert dlg._countdown_timer.isActive() is True

    # User cancels dialog
    dlg.reject()
    assert dlg._countdown_active is False
    assert dlg._countdown_timer.isActive() is False
    assert dlg.result() == PreflightDialog.Rejected


def test_scheduled_execution_hotkey_failure_no_modal(qapp: QApplication):
    """When scheduled=True, hotkey registration failure must not pop up QMessageBox."""
    win = MainWindow()
    win._current_macro = Macro(name="TestMacro", per_row=[ActionItem(type="wait", seconds=0.01)])
    win._data_rows = [{"val": "1"}]
    win._data_row_nums = [1]
    win.data_panel._row_numbers = [1]

    class FailingHotkeyManager:
        def start(self): pass
        def stop(self): pass
        def register_hotkey(self, *args, **kwargs): return False

    opts = {"scheduled": True, "start_row": 1, "end_row_index": 1}
    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FailingHotkeyManager),
        patch("stepwise.ui.main_window.QMessageBox.warning") as mock_warn,
    ):
        win._start_execution(opts)
        assert mock_warn.call_count == 0
        assert Strings.F12_ERROR.split("{")[0] in win.status_bar.currentMessage()
