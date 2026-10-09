"""Regression coverage for run isolation, image ownership and persistence failures."""

from __future__ import annotations

import builtins
import csv
import threading
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QRect
from PySide6.QtWidgets import QApplication, QPushButton

from stepwise.core.models import ActionItem, ImageCondition, Macro
from stepwise.core.package import load_package, save_package
from stepwise.engine.actions import execute_action
from stepwise.engine.errors import AbortRequested, StepFailure
from stepwise.engine.results import ResultsManager, RowResultRecord
from stepwise.engine.runner import RunSummary, run_macro
from stepwise.services import clipboard, input_win
from stepwise.ui.main_window import MainWindow
from stepwise.ui.properties_panel import PropertiesPanel
from stepwise.ui.run_summary import RunSummaryDialog
from stepwise.ui.strings import Strings


class FakeHotkeys:
    def __init__(self) -> None:
        self.stopped = False
        self.callback = None

    def start(self) -> None:
        pass

    def register_hotkey(self, _vk: int, _mod: int, callback: object = None) -> int:
        self.callback = callback
        return 1

    def stop(self) -> None:
        self.stopped = True


class DeferredThread:
    """Hold the worker until the test deliberately mutates live UI state."""

    def __init__(self, target: object, **_kwargs: object) -> None:
        self.target = target
        self.running = False

    def start(self) -> None:
        self.running = True

    def is_alive(self) -> bool:
        return self.running

    def finish(self) -> None:
        try:
            self.target()
        finally:
            self.running = False


def test_run_guard_and_snapshot_isolation(qapp: QApplication, qtbot: object) -> None:
    win = MainWindow()
    child = ActionItem(type="type_text", text="original")
    win._current_macro.per_row = [ActionItem(type="group", items=[child])]
    win._data_rows = [{"Name": "Alice"}]
    win._data_row_nums = [7]
    win._data_filepath = "original.xlsx"
    win._user_settings["results_dir"] = "original results"
    package_dir = win._package_dir
    opts = {"skip_setup": True}
    calls = []

    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch("stepwise.ui.main_window.run_macro", side_effect=lambda **kw: calls.append(kw)),
        patch("stepwise.ui.main_window.PreflightDialog") as preflight,
    ):
        win._start_execution(opts)
        worker = win._worker_thread
        token = win._run_token
        controller = win._controller
        win._on_run_clicked()  # F5 and Run share this handler.
        win._on_run_only_row(7)
        win._start_execution({})
        assert win._worker_thread is worker
        assert win._run_token == token
        preflight.assert_not_called()

        child.text = "edited"
        win._data_rows[0]["Name"] = "Bob"
        win._data_row_nums[0] = 99
        win._data_filepath = "edited.xlsx"
        win._user_settings["results_dir"] = "edited results"
        opts["skip_setup"] = False
        win._on_runner_event("stale-token", "worker_finished", ())
        assert win._is_running
        worker.finish()
        qtbot.waitUntil(lambda: not win._is_running, timeout=2000)

    assert len(calls) == 1
    assert calls[0]["macro"].per_row[0].items[0].text == "original"
    assert calls[0]["rows_data"] == ({"Name": "Alice"},)
    assert calls[0]["row_numbers"] == (7,)
    assert calls[0]["data_filepath"] == "original.xlsx"
    assert calls[0]["results_dir"] == "original results"
    assert calls[0]["package_dir"] == package_dir
    assert calls[0]["controller"] is controller
    assert calls[0]["skip_setup"] is True
    win.close()


def test_snapshots_are_taken_on_ui_thread(qapp: QApplication, qtbot: object) -> None:
    import copy

    deepcopy = copy.deepcopy
    thread_ids = []

    def snapshot(value: object) -> object:
        thread_ids.append(threading.get_ident())
        return deepcopy(value)

    win = MainWindow()
    with (
        patch("stepwise.ui.main_window.copy.deepcopy", side_effect=snapshot),
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.run_macro"),
    ):
        win._start_execution({})
        qtbot.waitUntil(lambda: not win._is_running, timeout=2000)
    assert len(thread_ids) == 4
    assert set(thread_ids) == {threading.get_ident()}
    win.close()


@pytest.mark.parametrize("result", [0, RuntimeError("F12 already registered")])
def test_f12_failure_cancels_run(qapp: QApplication, result: object) -> None:
    manager = FakeHotkeys()
    win = MainWindow()
    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", return_value=manager),
        patch.object(
            manager,
            "register_hotkey",
            side_effect=result if isinstance(result, Exception) else None,
            return_value=0,
        ),
        patch("stepwise.ui.main_window.QMessageBox.warning") as warning,
        patch("stepwise.ui.main_window.run_macro") as runner,
    ):
        win._start_execution({})
    runner.assert_not_called()
    warning.assert_called_once()
    assert "F12" in warning.call_args.args[2]
    assert manager.stopped
    assert not win._is_running
    assert win._controller is None
    assert win._worker_thread is None
    assert win.btn_run.isEnabled()
    win.close()


def test_preflight_guard_blocks_reentrant_runs(qapp: QApplication) -> None:
    win = MainWindow()

    def rejected_preflight() -> None:
        assert win._is_running
        assert win._execution_phase == "preflight"
        win._on_run_clicked()
        win._on_run_only_row(1)
        win._start_execution({})

    with (
        patch.object(win, "_show_preflight", side_effect=rejected_preflight) as preflight,
        patch("stepwise.ui.main_window.GlobalHotkeyManager") as manager,
    ):
        win._on_run_clicked()
    preflight.assert_called_once()
    manager.assert_not_called()
    assert win._execution_phase == "idle"
    win.close()


def test_closing_active_window_waits_for_worker_before_cleaning_images(
    qapp: QApplication, qtbot: object
) -> None:
    win = MainWindow()
    package_dir = Path(win._package_dir)
    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", DeferredThread),
        patch("stepwise.ui.main_window.run_macro"),
    ):
        win._start_execution({})
        worker = win._worker_thread
        controller = win._controller
        win.close()
        assert win._close_requested
        assert package_dir.exists()
        with pytest.raises(AbortRequested):
            controller.check_abort()
        worker.finish()
        qtbot.waitUntil(lambda: not package_dir.exists(), timeout=2000)
    assert not win._is_running


def test_worker_failure_restores_ui_despite_hotkey_cleanup_error(
    qapp: QApplication, qtbot: object
) -> None:
    win = MainWindow()
    manager = FakeHotkeys()
    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", return_value=manager),
        patch.object(manager, "stop", side_effect=RuntimeError("cleanup failed")) as stop,
        patch("stepwise.ui.main_window.run_macro", side_effect=RuntimeError("worker failed")),
        patch("stepwise.ui.main_window.RunSummaryDialog.exec", return_value=0),
    ):
        win._start_execution({})
        qtbot.waitUntil(lambda: not win._is_running, timeout=2000)
    stop.assert_called_once()
    assert win._hotkey_mgr is None
    assert win._controller is None
    assert win.btn_run.isEnabled()
    assert not win.btn_stop.isEnabled()
    assert "worker failed" in win._pending_summary.failure.message
    win.close()


def test_capture_save_reload_preserves_nested_images(qapp: QApplication, tmp_path: Path) -> None:
    win = MainWindow()
    capture_action = ActionItem(type="click_image")
    win._current_macro = Macro(per_row=[ActionItem(type="group", items=[capture_action])])
    win.action_tree.load_macro(win._current_macro)
    win.prop_panel.set_action(capture_action)
    frame = np.zeros((100, 100, 4), dtype=np.uint8)
    with patch("stepwise.ui.capture_overlay.capture_screen", return_value=frame):
        win._trigger_capture_overlay()
    win.overlay._dpr = 1.0
    win.overlay._save_region(QRect(10, 10, 20, 20))
    reference = capture_action.image
    assert reference and Path(win._package_dir, reference).is_file()
    for name in ("guard.png", "verify.png", "disabled.png"):
        Path(win._package_dir, "images", name).write_bytes(b"template")
    win._current_macro.per_row[0].items.append(
        ActionItem(
            type="click",
            guard=ImageCondition("images/guard.png"),
            verify=ImageCondition("images/verify.png"),
        )
    )
    win._current_macro.setup = [
        ActionItem(type="wait_image", image="images/disabled.png", enabled=False)
    ]
    destination = tmp_path / "portable.swm"
    win._current_macro_path = str(destination)
    with patch("stepwise.ui.main_window.QMessageBox.warning") as save_warning:
        win.save_current_macro()
    assert not save_warning.called, save_warning.call_args
    with zipfile.ZipFile(destination) as package:
        assert {reference, "images/guard.png", "images/verify.png", "images/disabled.png"} <= set(
            package.namelist()
        )
    with patch("stepwise.ui.main_window.QMessageBox.critical") as load_error:
        win.load_macro_file(str(destination))
    assert not load_error.called, load_error.call_args
    unpacked = Path(win._package_dir)
    assert unpacked != destination.parent
    assert (unpacked / reference).is_file()
    saved_child = win._current_macro.per_row[0].items[0]
    with patch("stepwise.engine.actions.execute_action") as execute:
        win._test_single_action(saved_child)
    assert execute.call_args.kwargs["package_dir"] == str(unpacked)
    with (
        patch("stepwise.services.matcher.find_image_on_screen", return_value=None) as matcher,
        patch("stepwise.ui.main_window.QMessageBox.information"),
    ):
        win._test_image_match(saved_child)
    assert Path(matcher.call_args.args[0]) == unpacked / reference
    win.close()
    assert not unpacked.exists()


def test_missing_image_does_not_replace_saved_package(qapp: QApplication, tmp_path: Path) -> None:
    destination = tmp_path / "keep.swm"
    save_package(Macro(name="Original"), str(destination))
    original = destination.read_bytes()
    win = MainWindow()
    win._current_macro_path = str(destination)
    win._current_macro.per_row = [ActionItem(type="wait_image", image="images/missing.png")]
    with patch("stepwise.ui.main_window.QMessageBox.warning") as warning:
        win.save_current_macro()
    warning.assert_called_once()
    assert destination.read_bytes() == original
    win.close()


def test_external_package_directory_is_not_deleted(qapp: QApplication, tmp_path: Path) -> None:
    source = tmp_path / "macro.json"
    import json

    source.write_text(json.dumps(Macro().to_dict()), encoding="utf-8")
    win = MainWindow()
    initial_temp = Path(win._package_dir)
    win.load_macro_file(str(source))
    assert win._package_dir == str(tmp_path)
    assert not initial_temp.exists()
    win.close()
    assert source.exists()


def test_save_new_macro_normalizes_legacy_and_external_image_references(
    qapp: QApplication, tmp_path: Path
) -> None:
    win = MainWindow()
    Path(win._package_dir, "legacy.png").write_bytes(b"legacy")
    external = tmp_path / "external.png"
    external.write_bytes(b"external")
    win._current_macro.per_row = [ActionItem(type="wait_image", image="legacy.png")]
    win._current_macro.cleanup = [ActionItem(type="click", verify=ImageCondition(str(external)))]
    destination = tmp_path / "new.swm"
    with patch(
        "stepwise.ui.main_window.QFileDialog.getSaveFileName", return_value=(str(destination), "")
    ):
        win.save_current_macro()
    macro, directory = load_package(str(destination), extract_dir=str(tmp_path / "unpacked"))
    assert win._current_macro_path == str(destination)
    assert macro.per_row[0].image == "images/legacy.png"
    assert Path(directory, macro.per_row[0].image).read_bytes() == b"legacy"
    assert Path(directory, macro.cleanup[0].verify.image).read_bytes() == b"external"
    win.close()


def test_preflight_uses_owned_package_directory(qapp: QApplication) -> None:
    win = MainWindow()
    with patch("stepwise.ui.main_window.PreflightDialog") as preflight:
        preflight.Accepted = 1
        preflight.return_value.exec.return_value = 0
        win._on_run_clicked()
    assert preflight.call_args.kwargs["package_dir"] == win._package_dir
    assert not win._is_running
    win.close()


def test_capture_failure_warns_without_changing_image(qapp: QApplication) -> None:
    win = MainWindow()
    action = ActionItem(type="click_image", image="images/original.png")
    win.prop_panel.set_action(action)
    with patch(
        "stepwise.ui.capture_overlay.capture_screen",
        return_value=np.zeros((100, 100, 4), dtype=np.uint8),
    ):
        win._trigger_capture_overlay()
    win.overlay._dpr = 1.0
    with (
        patch("stepwise.ui.capture_overlay.cv2.imencode", return_value=(False, None)),
        patch("stepwise.ui.main_window.QMessageBox.warning") as warning,
    ):
        win.overlay._save_region(QRect(0, 0, 20, 20))
    assert action.image == "images/original.png"
    warning.assert_called_once()
    win.close()


def test_properties_widgets_are_replaced_and_refs_cleared(qapp: QApplication) -> None:
    panel = PropertiesPanel()
    for _ in range(5):
        panel.set_action(ActionItem(type="type_text"))
        old_editor = panel.txt_text
        panel.set_action(ActionItem(type="click", x=-1920, y=-50))
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        assert panel.txt_text is None
        panel.update_variable_completions(["Name"])
        assert panel.spin_x.value() == -1920
        assert panel.spin_y.value() == -50
        buttons = panel.container.findChildren(QPushButton)
        assert sum(button.text() == Strings.TEST_THIS_STEP for button in buttons) == 1
        with pytest.raises(RuntimeError, match="already deleted"):
            old_editor.text()
    panel.set_action(None)
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    panel.update_variable_completions([])
    assert panel.txt_text is None
    assert not panel.container.findChildren(QPushButton)
    panel.close()


def test_nested_clones_have_distinct_ids_and_tree_highlights_survive_rebuild(
    qapp: QApplication,
) -> None:
    win = MainWindow()
    leaf = ActionItem(type="click")
    nested = ActionItem(type="group", items=[leaf])
    group = ActionItem(type="group", items=[nested])
    win._current_macro.per_row = [group]
    win.action_tree.load_macro(win._current_macro)
    win.action_tree.highlight_step(leaf.id)
    win._on_request_duplicate_action(group)
    clone = win._current_macro.per_row[1]
    original_ids = {group.id, nested.id, leaf.id}
    cloned_ids = {clone.id, clone.items[0].id, clone.items[0].items[0].id}
    assert len(original_ids | cloned_ids) == 6
    win._on_request_duplicate_action(leaf)
    assert len(nested.items) == 2
    assert nested.items[1].id not in original_ids | cloned_ids
    win.action_tree.highlight_step(nested.items[1].id)
    assert win.action_tree._highlighted_item is not None
    win.close()


@pytest.mark.parametrize(
    "x,y,expected", [(-1920, -200, (0, 0)), (1919, 1079, (65535, 65535)), (0, 0, (32776, 10247))]
)
def test_mouse_normalizes_against_virtual_desktop(
    x: int, y: int, expected: tuple[int, int]
) -> None:
    metrics = {76: -1920, 77: -200, 78: 3840, 79: 1280}
    os_api = MagicMock()
    os_api.GetSystemMetrics.side_effect = metrics.__getitem__
    with (
        patch.object(input_win, "user32", os_api),
        patch.object(input_win, "send_inputs", return_value=1) as send,
    ):
        assert input_win.move_mouse(x, y)
    event = send.call_args.args[0][0].u.mi
    assert (event.dx, event.dy) == expected
    assert event.dwFlags & input_win.MOUSEEVENTF_VIRTUALDESK


def test_failed_mouse_move_never_clicks() -> None:
    with (
        patch.object(input_win, "move_mouse", return_value=False),
        patch.object(input_win, "send_inputs") as send,
    ):
        assert not input_win.click_at(-500, 100)
    send.assert_not_called()


def test_engine_reports_failed_mouse_input() -> None:
    with patch("stepwise.engine.actions.click_at", return_value=False):
        with pytest.raises(StepFailure, match="mouse"):
            execute_action(ActionItem(type="click", x=-100, y=100), default_wait_before=0)


@pytest.mark.parametrize("stage", ["alloc", "lock", "empty", "set", "success"])
def test_clipboard_ownership_and_errors(stage: str) -> None:
    os_api = MagicMock()
    memory_api = MagicMock()
    memory_api.GlobalAlloc.return_value = 0 if stage == "alloc" else 123
    memory_api.GlobalLock.return_value = 0 if stage == "lock" else 456
    os_api.EmptyClipboard.return_value = stage != "empty"
    os_api.SetClipboardData.return_value = 0 if stage == "set" else 123
    with (
        patch.object(clipboard, "user32", os_api),
        patch.object(clipboard, "kernel32", memory_api),
        patch.object(clipboard.ctypes, "memmove") as write,
    ):
        assert clipboard.set_clipboard_text("한글 Łódź") is (stage == "success")
    os_api.CloseClipboard.assert_called_once()
    if stage in ("lock", "empty", "set"):
        memory_api.GlobalFree.assert_called_once_with(123)
    else:
        memory_api.GlobalFree.assert_not_called()
    if stage not in ("alloc", "lock"):
        assert write.call_args.args[1] == "한글 Łódź".encode("utf-16le") + b"\x00\x00"


def test_clipboard_failure_cannot_select_or_paste_stale_text() -> None:
    with (
        patch.object(clipboard, "get_clipboard_text", return_value=None),
        patch.object(clipboard, "set_clipboard_text", return_value=False),
        patch("stepwise.engine.actions.press_keys") as keys,
    ):
        with pytest.raises(StepFailure, match="clipboard") as failure:
            execute_action(
                ActionItem(id="paste", type="type_text", text="new", select_all_first=True),
                default_wait_before=0,
                row_number=17,
            )
    keys.assert_not_called()
    assert failure.value.step_id == "paste"
    assert failure.value.row_number == 17


def test_clipboard_write_precedes_selection_and_restoration() -> None:
    events = []
    with (
        patch.object(clipboard, "get_clipboard_text", return_value="original"),
        patch.object(
            clipboard, "set_clipboard_text", side_effect=lambda text: events.append(text) or True
        ),
        patch("stepwise.engine.actions.press_keys", side_effect=events.append),
    ):
        execute_action(
            ActionItem(type="type_text", text="new", select_all_first=True), default_wait_before=0
        )
    assert events == ["new", "ctrl+a", "ctrl+v", "original"]


def test_locked_results_survive_in_journal_and_resume(tmp_path: Path) -> None:
    manager = ResultsManager("Locked", "source.xlsx", str(tmp_path))
    real_open = builtins.open

    def locked_open(path: str, mode: str = "r", **kwargs: object) -> object:
        if path == manager.csv_path and mode == "a":
            raise PermissionError("Excel lock")
        return real_open(path, mode, **kwargs)

    with patch("builtins.open", side_effect=locked_open):
        summary = run_macro(
            Macro(name="Locked"),
            rows_data=[{"Name": "Alice"}],
            row_numbers=[7],
            results_manager=manager,
        )
    assert summary.done_count == 1 and summary.failed_count == 0
    assert [record.status for record in summary.buffered_results] == ["Running", "Done"]
    assert summary.pending_results_path == manager.pending_csv_path
    with real_open(manager.pending_csv_path, encoding="utf-8-sig") as journal:
        assert [record["status"] for record in csv.DictReader(journal)] == ["Running", "Done"]
    reloaded = ResultsManager("Locked", "source.xlsx", str(tmp_path))
    assert reloaded.load_latest_row_statuses()[7].status == "Done"
    assert reloaded.get_resume_suggestion([7], [{"Name": "Alice"}])[0] is None
    # Keep order even when the primary CSV becomes writable again.
    reloaded.append_record(RowResultRecord("next", 7, "", "Failed"))
    assert reloaded.load_latest_row_statuses()[7].status == "Failed"


def test_both_result_paths_unavailable_retain_memory_and_recover(tmp_path: Path) -> None:
    manager = ResultsManager("Buffer", "source.xlsx", str(tmp_path))
    with patch.object(manager, "_write_record", side_effect=PermissionError("locked")):
        summary = run_macro(
            Macro(name="Buffer"), rows_data=[{"Name": "Alice"}], results_manager=manager
        )
    assert summary.done_count == 1 and summary.failed_count == 0
    assert [record.status for record in summary.buffered_results] == ["Running", "Done"]
    assert summary.persistence_errors
    assert manager.load_latest_row_statuses()[1].status == "Done"
    manager.append_record(RowResultRecord("next", 2, "", "Done"))
    with open(manager.pending_csv_path, encoding="utf-8-sig") as journal:
        assert [record["status"] for record in csv.DictReader(journal)] == [
            "Running",
            "Done",
            "Done",
        ]
    assert not manager.persistence_errors


def test_runner_append_failure_still_journals_completed_rows(tmp_path: Path) -> None:
    manager = ResultsManager("AppendFailure", "source.xlsx", str(tmp_path))
    with patch.object(manager, "append_record", side_effect=PermissionError("locked")):
        summary = run_macro(Macro(), rows_data=[{}], results_manager=manager)
    assert summary.done_count == 1
    assert Path(manager.pending_csv_path).is_file()
    assert manager.load_latest_row_statuses()[1].status == "Done"


def test_buffered_results_can_be_exported(qapp: QApplication, tmp_path: Path) -> None:
    summary = RunSummary(
        run_id="buffered",
        macro_name="Buffer",
        started_at="",
        finished_at="",
        duration_sec=0,
        total_rows=1,
        done_count=1,
        failed_count=0,
        interrupted_count=0,
        skipped_count=0,
        pending_results_path=str(tmp_path / "unavailable.pending.csv"),
        buffered_results=[RowResultRecord("buffered", 3, "hash", "Done")],
        persistence_errors=["locked"],
    )
    dialog = RunSummaryDialog(summary)
    destination = tmp_path / "recovered.csv"
    with patch(
        "stepwise.ui.run_summary.QFileDialog.getSaveFileName", return_value=(str(destination), "")
    ):
        dialog._export_buffered_results()
    with destination.open(encoding="utf-8-sig") as recovered:
        records = list(csv.DictReader(recovered))
    assert records[0]["row_number"] == "3"
    assert records[0]["status"] == "Done"
    assert summary.buffered_results[0].status == "Done"
    dialog.close()
