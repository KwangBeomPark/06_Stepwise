"""UX Round 2 — Stage 1 (packages A, B, C) regression coverage."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QAbstractItemView, QApplication, QMessageBox

from stepwise.core.models import ActionItem, Macro
from stepwise.core.package import save_package
from stepwise.engine.preflight import preview_row_range
from stepwise.ui.data_panel import DataPanel
from stepwise.ui.macro_library import MacroLibraryPanel
from stepwise.ui.main_window import MainWindow
from stepwise.ui.preflight_dialog import PreflightDialog
from stepwise.ui.strings import Strings, apply_language

Button = QMessageBox.StandardButton


@pytest.fixture
def settings() -> dict:
    return {"auto_check_updates": False, "countdown_seconds": 3}


@pytest.fixture
def win(qapp: QApplication, tmp_path: Path, settings: dict) -> Iterator[MainWindow]:
    library = tmp_path / "library"
    with (
        patch("stepwise.ui.main_window.load_user_settings", return_value=settings),
        patch("stepwise.ui.main_window.save_user_settings"),
    ):
        window = MainWindow(library_dir=str(library))
        yield window
        window._prompt_unsaved_changes = lambda: Button.Discard
        window.close()


def _write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


# --- Package A ------------------------------------------------------------------


def test_open_results_folder_uses_settings_and_creates_folder(
    win: MainWindow, tmp_path: Path
) -> None:
    target = tmp_path / "my results"
    win._user_settings["results_dir"] = str(target)
    with patch("stepwise.ui.main_window.os.startfile", create=True) as startfile:
        win._open_results_folder()
    assert target.is_dir()
    startfile.assert_called_once_with(str(target))


def test_new_macro_refuses_to_overwrite_existing_file(qapp: QApplication, tmp_path: Path) -> None:
    existing = tmp_path / "Invoice.swm"
    save_package(Macro(name="Original", per_row=[ActionItem(type="wait")]), str(existing))
    original = existing.read_bytes()
    panel = MacroLibraryPanel(str(tmp_path))
    created: list[str] = []
    panel.macro_created.connect(created.append)
    with (
        patch("stepwise.ui.macro_library.QInputDialog.getText", return_value=("Invoice", True)),
        patch("stepwise.ui.macro_library.QMessageBox.warning") as warning,
    ):
        panel._on_new_macro()
    warning.assert_called_once()
    assert existing.read_bytes() == original
    assert created == []
    panel.close()


def test_new_macro_is_opened_once_after_creation(win: MainWindow) -> None:
    with (
        patch("stepwise.ui.macro_library.QInputDialog.getText", return_value=("Fresh", True)),
        patch.object(win, "load_macro_file", wraps=win.load_macro_file) as load,
    ):
        win.lib_panel._on_new_macro()
    assert load.call_count == 1
    assert win._current_macro.name == "Fresh"
    assert win._current_macro_path.endswith("Fresh.swm")
    assert not win.is_dirty()


def test_data_preview_table_is_read_only(qapp: QApplication) -> None:
    panel = DataPanel()
    assert panel.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    panel.close()


def test_f8_f9_shortcuts_are_registered(win: MainWindow) -> None:
    assert win.act_pick_coords.shortcut().toString() == "F8"
    assert win.act_capture_image.shortcut().toString() == "F9"


def test_f8_f9_only_act_on_supported_idle_steps(win: MainWindow) -> None:
    with (
        patch.object(win, "_trigger_pick_overlay") as pick,
        patch.object(win, "_trigger_capture_overlay") as capture,
    ):
        win.prop_panel.set_action(ActionItem(type="wait"))
        win._on_pick_shortcut()
        assert win.status_bar.currentMessage() == Strings.SHORTCUT_PICK_UNSUPPORTED
        win._on_capture_shortcut()
        assert win.status_bar.currentMessage() == Strings.SHORTCUT_CAPTURE_UNSUPPORTED

        win.prop_panel.set_action(ActionItem(type="click"))
        win._is_running = True
        win._on_pick_shortcut()
        assert win.status_bar.currentMessage() == Strings.SHORTCUT_BLOCKED_RUNNING
        win._is_running = False
        pick.assert_not_called()

        win._on_pick_shortcut()
        pick.assert_called_once()

        win.prop_panel.set_action(ActionItem(type="click_image"))
        win._on_capture_shortcut()
        capture.assert_called_once()


def test_column_click_inserts_at_cursor_without_rebuilding_editor(win: MainWindow) -> None:
    action = ActionItem(type="type_text", text="Hello world")
    win._current_macro.per_row = [action]
    win.action_tree.load_macro(win._current_macro)
    win.action_tree.rebuild_tree(select_id=action.id)
    assert win.prop_panel._current_action is action
    editor = win.prop_panel.txt_text
    editor.setCursorPosition(6)
    win._insert_variable_into_current_action("{Name}")
    assert action.text == "Hello {Name}world"
    assert win.prop_panel.txt_text is editor


def test_column_click_without_type_text_shows_hint(win: MainWindow) -> None:
    action = ActionItem(type="click")
    win.prop_panel.set_action(action)
    win._insert_variable_into_current_action("{Name}")
    assert win.status_bar.currentMessage() == Strings.SELECT_TYPE_TEXT_FIRST


# --- Package B ------------------------------------------------------------------


def test_fresh_window_is_clean_and_edits_mark_title_dirty(win: MainWindow) -> None:
    assert not win.is_dirty()
    assert win.windowTitle() == Strings.APP_TITLE
    win._add_quick_action("click")
    assert win.is_dirty()
    assert win.windowTitle().endswith(" *")


def test_rebuilding_property_widgets_does_not_mark_dirty(win: MainWindow, tmp_path: Path) -> None:
    path = tmp_path / "clean.swm"
    action = ActionItem(type="type_text", text="abc")
    save_package(Macro(name="Clean", per_row=[action]), str(path))
    win.load_macro_file(str(path))
    loaded = win._current_macro.per_row[0]
    for _ in range(3):
        win.prop_panel.set_action(loaded)
        win.prop_panel.set_action(None)
    assert not win.is_dirty()
    assert win.windowTitle() == f"{Strings.APP_TITLE} - Clean"


def test_save_clears_dirty_marker(win: MainWindow, tmp_path: Path) -> None:
    win._current_macro_path = str(tmp_path / "saved.swm")
    win._add_quick_action("wait")
    assert win.is_dirty()
    assert win.save_current_macro() is True
    assert not win.is_dirty()
    assert not win.windowTitle().endswith("*")


@pytest.mark.parametrize(
    "choice,save_ok,expected",
    [
        (Button.Cancel, True, False),
        (Button.Discard, True, True),
        (Button.Save, True, True),
        (Button.Save, False, False),
    ],
)
def test_confirm_discard_changes_choices(
    win: MainWindow, choice: Button, save_ok: bool, expected: bool
) -> None:
    win._add_quick_action("wait")
    win._prompt_unsaved_changes = lambda: choice
    with patch.object(win, "save_current_macro", return_value=save_ok) as save:
        assert win._confirm_discard_changes() is expected
    assert save.called == (choice == Button.Save)


def test_confirm_skips_prompt_when_clean(win: MainWindow) -> None:
    prompt = MagicMock()
    win._prompt_unsaved_changes = prompt
    assert win._confirm_discard_changes() is True
    prompt.assert_not_called()


def test_cancelled_library_switch_restores_previous_selection(
    win: MainWindow, tmp_path: Path
) -> None:
    library = Path(win._library_dir)
    first, second = library / "First.swm", library / "Second.swm"
    save_package(Macro(name="First"), str(first))
    save_package(Macro(name="Second"), str(second))
    win.lib_panel.refresh_list()
    win.lib_panel.select_path(str(first))
    assert win._current_macro.name == "First"

    win._add_quick_action("wait")
    win._prompt_unsaved_changes = lambda: Button.Cancel
    win.lib_panel.select_path(str(second))

    assert win._current_macro.name == "First"
    assert win.is_dirty()
    selected = win.lib_panel.list_widget.selectedItems()
    assert [Path(item.data(256)).name for item in selected] == ["First.swm"]


def test_close_is_cancelled_when_user_cancels_unsaved_prompt(win: MainWindow) -> None:
    win._add_quick_action("wait")
    win._prompt_unsaved_changes = lambda: Button.Cancel
    assert win.close() is False
    assert win._package_temp is not None  # nothing was torn down


def test_preflight_countdowns_for_test_and_start_runs(qapp: QApplication) -> None:
    rows = [{"Name": "A"}, {"Name": "B"}]
    dlg = PreflightDialog(Macro(), rows_data=rows, row_numbers=[2, 3])
    dlg._on_run_1_row()
    assert dlg.confirmed_opts["run_1_row"] is True
    assert dlg.confirmed_opts["countdown_seconds"] == 3.0

    dlg = PreflightDialog(Macro(), rows_data=rows, row_numbers=[2, 3], countdown_seconds=5)
    dlg._confirm(run_1_row=False)
    assert dlg.confirmed_opts["countdown_seconds"] == 0.0
    dlg._on_run_1_row()
    assert dlg.confirmed_opts["countdown_seconds"] == 5.0


def test_preflight_start_countdown_uses_configured_seconds(qapp: QApplication) -> None:
    dlg = PreflightDialog(Macro(), countdown_seconds=2)
    with patch.object(dlg._countdown_timer, "start"):
        dlg._start_countdown()
    assert "2" in dlg.lbl_countdown.text()
    dlg._countdown_tick()
    dlg._countdown_tick()
    assert dlg.result() == PreflightDialog.Accepted
    assert dlg.confirmed_opts["run_1_row"] is False


def test_run_only_row_requests_engine_countdown(win: MainWindow, settings: dict) -> None:
    settings["countdown_seconds"] = 4
    win._data_row_nums = [2, 5]
    with patch.object(win, "_start_execution") as start:
        win._on_run_only_row(5)
    opts = start.call_args.args[0]
    assert opts["start_row"] == 2
    assert opts["countdown_seconds"] == 4.0


def test_step_test_counts_down_before_executing(win: MainWindow) -> None:
    action = ActionItem(type="click", x=10, y=10)
    win._current_macro.per_row = [action]  # only steps still in the macro may run
    win.prop_panel.set_action(action)
    with (
        patch.object(win._step_test_timer, "start"),
        patch("stepwise.engine.actions.execute_action") as execute,
    ):
        win._request_step_test(action)
        assert win._step_test_pending
        execute.assert_not_called()
        assert "3" in win.status_bar.currentMessage()

        # A second request and F8 are ignored while counting down.
        win._request_step_test(action)
        with patch.object(win, "_trigger_pick_overlay") as pick:
            win._on_pick_shortcut()
        pick.assert_not_called()

        win._on_step_test_tick()
        win._on_step_test_tick()
        execute.assert_not_called()
        win._on_step_test_tick()
    execute.assert_called_once()
    assert execute.call_args.args[0] is action
    assert not win._step_test_pending


def test_step_test_without_countdown_runs_immediately(win: MainWindow, settings: dict) -> None:
    settings["countdown_seconds"] = 0
    action = ActionItem(type="wait", seconds=0)
    with patch("stepwise.engine.actions.execute_action") as execute:
        win._request_step_test(action)
    execute.assert_called_once()
    assert not win._step_test_pending


def test_test_step_button_routes_through_countdown(win: MainWindow) -> None:
    action = ActionItem(type="click")
    with patch.object(win, "_request_step_test") as request:
        win.prop_panel.request_test_step.emit(action)
    request.assert_called_once_with(action)


# --- Package C ------------------------------------------------------------------


def test_empty_state_hint_then_summary_after_load(qapp: QApplication, tmp_path: Path) -> None:
    panel = DataPanel()
    assert panel.stack.currentWidget() is panel.lbl_empty
    assert panel.lbl_empty.text() == Strings.DATA_DROP_HINT
    csv_path = _write_csv(tmp_path / "people.csv", ["Name,Amount", "Kim,1", "Lee,2", "Park,3"])
    assert panel.load_file(str(csv_path)) is True
    assert panel.stack.currentWidget() is panel.table
    assert panel.lbl_info.text() == Strings.DATA_LOADED_SUMMARY.format(
        file="people.csv", rows=3, cols=2
    )
    panel.close()


def test_permission_error_keeps_previous_connection(qapp: QApplication, tmp_path: Path) -> None:
    panel = DataPanel()
    good = _write_csv(tmp_path / "good.csv", ["Name", "Kim"])
    panel.load_file(str(good))
    emitted: list[str] = []
    panel.data_loaded.connect(lambda path, *_: emitted.append(path))
    with (
        patch("stepwise.ui.data_panel.read_data_file", side_effect=PermissionError("locked")),
        patch("stepwise.ui.data_panel.QMessageBox.warning") as warning,
    ):
        assert panel.load_file(str(tmp_path / "locked.xlsx")) is False
    message = warning.call_args.args[2]
    assert message == Strings.DATA_LOAD_PERMISSION_ERROR.format(file="locked.xlsx")
    assert Strings.DATA_KEEP_PREVIOUS.format(file="good.csv") in panel.lbl_info.text()
    assert panel._current_filepath == str(good)
    assert panel._rows == [{"Name": "Kim"}]
    assert emitted == []
    panel.close()


def _drop_event(paths: list[str]) -> MagicMock:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
    event = MagicMock()
    event.mimeData.return_value = mime
    return event


def test_drag_and_drop_accepts_single_data_file(qapp: QApplication, tmp_path: Path) -> None:
    panel = DataPanel()
    csv_path = str(_write_csv(tmp_path / "drop.csv", ["Name", "Kim"]))

    enter = _drop_event([csv_path])
    panel.dragEnterEvent(enter)
    enter.acceptProposedAction.assert_called_once()

    for bad in ([str(tmp_path / "notes.txt")], [csv_path, csv_path]):
        rejected = _drop_event(bad)
        panel.dragEnterEvent(rejected)
        rejected.ignore.assert_called_once()

    with patch.object(panel, "load_file") as load:
        panel.dropEvent(_drop_event([csv_path]))
    load.assert_called_once_with(os.path.normpath(csv_path).replace("\\", "/"))
    panel.close()


def test_data_load_records_file_hint_and_offers_reconnect(
    win: MainWindow, tmp_path: Path
) -> None:
    macro_path = Path(win._library_dir) / "Linked.swm"
    save_package(Macro(name="Linked"), str(macro_path))
    win.load_macro_file(str(macro_path))
    assert win.data_panel.btn_reconnect.isHidden()

    data = _write_csv(tmp_path / "orders.csv", ["Order", "A-1", "A-2"])
    win.data_panel.load_file(str(data))
    assert win._current_macro.data_source.file_hint == "orders.csv"
    assert win.is_dirty()  # file_hint is part of the macro
    assert win.save_current_macro()

    # Simulate reopening the macro in a fresh session without data loaded.
    win._data_filepath = None
    win.data_panel._current_filepath = None
    win.load_macro_file(str(macro_path))
    assert not win.data_panel.btn_reconnect.isHidden()
    assert "orders.csv" in win.data_panel.btn_reconnect.text()
    assert win._data_rows == [{"Order": "A-1"}, {"Order": "A-2"}]  # no silent reload happened

    win._data_rows = []
    win.data_panel.btn_reconnect.click()
    assert win._data_filepath == str(data)
    assert len(win._data_rows) == 2
    assert win.data_panel.btn_reconnect.isHidden()


def test_reconnect_hidden_when_remembered_file_is_gone(qapp: QApplication, tmp_path: Path) -> None:
    panel = DataPanel()
    panel.set_reconnect_hint(str(tmp_path / "missing.xlsx"))
    assert panel.btn_reconnect.isHidden()
    panel.close()


def test_preflight_shows_connected_file_name(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QLabel

    macro = Macro()
    dlg = PreflightDialog(macro, rows_data=[{"A": "1"}], data_file_path="C:/data/sales.xlsx")
    texts = [label.text() for label in dlg.findChildren(QLabel)]
    assert any('"sales.xlsx"' in text for text in texts)


def test_preview_row_range_reports_source_rows_and_sample() -> None:
    rows = [{"Name": "Hong", "N": "1"}, {"Name": "Kim", "N": "2"}, {"Name": "Lee", "N": "3"}]
    preview = preview_row_range(rows, [5, 6, 9], 2, 3)
    assert (preview.first_row_number, preview.last_row_number, preview.count) == (6, 9, 2)
    assert preview.sample == "Kim"
    assert preview_row_range([], None, 1, 1) is None
    clamped = preview_row_range(rows, None, 3, 1)
    assert (clamped.first_row_number, clamped.last_row_number) == (3, 3)


def test_preflight_end_row_follows_start_row_and_preview(qapp: QApplication) -> None:
    rows = [{"Name": n} for n in ("Hong", "Kim", "Lee", "Park")]
    dlg = PreflightDialog(Macro(), rows_data=rows, row_numbers=[2, 3, 4, 5])
    assert dlg.spin_end_row.value() == 4
    assert dlg.spin_end_row.maximum() == 4
    dlg.spin_end_row.setValue(2)
    dlg.spin_start_row.setValue(3)
    assert dlg.spin_end_row.minimum() == 3
    assert dlg.spin_end_row.value() == 3
    assert dlg.lbl_range_preview.text() == Strings.PREFLIGHT_RANGE_PREVIEW.format(
        first=4, last=4, count=1, sample="Lee"
    )
    dlg._confirm(run_1_row=False)
    assert dlg.confirmed_opts["start_row"] == 3
    assert dlg.confirmed_opts["end_row_index"] == 3


class _ImmediateThread:
    def __init__(self, target: object, **_kwargs: object) -> None:
        self.target = target

    def start(self) -> None:
        pass

    def is_alive(self) -> bool:
        return False


class _FakeHotkeys:
    def start(self) -> None:
        pass

    def register_hotkey(self, *_args: object, **_kwargs: object) -> int:
        return 1

    def stop(self) -> None:
        pass


@pytest.mark.parametrize(
    "opts,expected_end",
    [
        ({"start_row": 2, "end_row_index": 3}, 3),
        ({"start_row": 1}, None),
        (
            {
                "start_row": 1,
                "end_row_index": 1,
                "custom_rows": [{"A": "2"}, {"A": "3"}],
                "custom_row_nums": [2, 3],
            },
            None,
        ),
    ],
)
def test_end_row_reaches_runner_except_for_retry_rows(
    win: MainWindow, opts: dict, expected_end: int | None
) -> None:
    win._data_rows = [{"A": "1"}, {"A": "2"}, {"A": "3"}, {"A": "4"}]
    win._data_row_nums = [1, 2, 3, 4]
    calls: list[dict] = []
    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", _FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", _ImmediateThread),
        patch("stepwise.ui.main_window.run_macro", side_effect=lambda **kw: calls.append(kw)),
    ):
        win._start_execution(opts)
        win._worker_thread.target()
    assert calls[0]["end_row_index"] == expected_end
    win._teardown_runner()


def test_retry_drops_previous_end_row(win: MainWindow) -> None:
    win._data_rows = [{"A": "1"}, {"A": "2"}, {"A": "3"}]
    win._data_row_nums = [1, 2, 3]
    win._last_run_opts = {"start_row": 1, "end_row_index": 2}
    with patch.object(win, "_start_execution") as start:
        win._retry_failed_rows([2])
    opts = start.call_args.args[0]
    assert "end_row_index" not in opts
    # The retry stays inside the user's range: row 2 is retried, row 3 is not.
    assert opts["custom_row_nums"] == [2]
    assert opts["custom_rows"] == [{"A": "2"}]


# --- Stage 1 review fixes ---------------------------------------------------------


@pytest.fixture
def korean() -> Iterator[None]:
    apply_language("ko")
    try:
        yield
    finally:
        apply_language("en")


def test_retry_keeps_previous_retry_row_set(win: MainWindow) -> None:
    win._data_rows = [{"A": str(n)} for n in range(1, 6)]
    win._data_row_nums = [1, 2, 3, 4, 5]
    win._last_run_opts = {"custom_rows": [{"A": "2"}, {"A": "4"}], "custom_row_nums": [2, 4]}
    with patch.object(win, "_start_execution") as start:
        win._retry_failed_rows([2])
    assert start.call_args.args[0]["custom_row_nums"] == [2, 4]


def test_retry_after_run_1_row_retries_only_that_row(win: MainWindow) -> None:
    win._data_rows = [{"A": "1"}, {"A": "2"}, {"A": "3"}]
    win._data_row_nums = [1, 2, 3]
    win._last_run_opts = {"start_row": 2, "run_1_row": True}
    with patch.object(win, "_start_execution") as start:
        win._retry_failed_rows([2])
    assert start.call_args.args[0]["custom_row_nums"] == [2]


def _start_pending_step_test(win: MainWindow) -> ActionItem:
    action = ActionItem(type="click", x=1, y=1)
    win._current_macro.per_row.append(action)
    with patch.object(win._step_test_timer, "start"):
        win._request_step_test(action)
    assert win._step_test_pending
    return action


def _record_pending_prompt(win: MainWindow, answer: Button) -> list[bool]:
    seen: list[bool] = []

    def prompt() -> Button:
        seen.append(win._step_test_pending)
        return answer

    win._prompt_unsaved_changes = prompt
    return seen


def test_step_test_cancelled_before_close_prompt(win: MainWindow) -> None:
    _start_pending_step_test(win)
    seen = _record_pending_prompt(win, Button.Cancel)
    assert win.close() is False
    assert seen == [False]
    assert not win._step_test_timer.isActive()


def test_step_test_cancelled_before_library_switch_prompt(win: MainWindow) -> None:
    other = Path(win._library_dir) / "Other.swm"
    save_package(Macro(name="Other"), str(other))
    win.lib_panel.refresh_list()
    _start_pending_step_test(win)
    seen = _record_pending_prompt(win, Button.Cancel)
    win.lib_panel.select_path(str(other))
    assert seen == [False]
    assert not win._step_test_pending


def test_step_test_cancelled_by_delete_and_load(win: MainWindow, tmp_path: Path) -> None:
    action = _start_pending_step_test(win)
    win._on_request_delete_action(action)
    assert not win._step_test_pending

    _start_pending_step_test(win)
    path = tmp_path / "x.swm"
    save_package(Macro(name="X"), str(path))
    win.load_macro_file(str(path))
    assert not win._step_test_pending


def test_step_test_skips_step_removed_during_countdown(win: MainWindow) -> None:
    action = _start_pending_step_test(win)
    win._current_macro.per_row.remove(action)
    with patch("stepwise.engine.actions.execute_action") as execute:
        for _ in range(3):
            win._on_step_test_tick()
    execute.assert_not_called()
    assert win.status_bar.currentMessage() == Strings.STEP_TEST_CANCELLED


def test_step_test_runs_step_nested_in_group(win: MainWindow) -> None:
    inner = ActionItem(type="click", x=1, y=1)
    win._current_macro.per_row = [ActionItem(type="group", name="G", items=[inner])]
    with patch.object(win._step_test_timer, "start"):
        win._request_step_test(inner)
    with patch("stepwise.engine.actions.execute_action") as execute:
        for _ in range(3):
            win._on_step_test_tick()
    execute.assert_called_once()


def test_data_panel_locked_while_running(qapp: QApplication, tmp_path: Path) -> None:
    panel = DataPanel()
    csv_path = str(_write_csv(tmp_path / "d.csv", ["Name", "Kim"]))
    panel.set_running(True)
    assert not panel.btn_select_file.isEnabled()

    enter = _drop_event([csv_path])
    panel.dragEnterEvent(enter)
    enter.acceptProposedAction.assert_not_called()
    enter.ignore.assert_called_once()

    panel._reconnect_path = csv_path
    with (
        patch.object(panel, "load_file") as load,
        patch("stepwise.ui.data_panel.QFileDialog.getOpenFileName") as chooser,
    ):
        panel.dropEvent(_drop_event([csv_path]))
        panel._on_choose_file()
        panel._on_reconnect_clicked()
    load.assert_not_called()
    chooser.assert_not_called()
    assert panel.lbl_info.text() == Strings.DATA_LOCKED_RUNNING

    panel.set_running(False)
    assert panel.btn_select_file.isEnabled()
    with patch.object(panel, "load_file") as load:
        panel.dropEvent(_drop_event([csv_path]))
    load.assert_called_once()
    panel.close()


def test_run_locks_and_teardown_unlocks_data_panel(win: MainWindow) -> None:
    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", _FakeHotkeys),
        patch("stepwise.ui.main_window.threading.Thread", _ImmediateThread),
    ):
        win._start_execution({"start_row": 1})
    assert win.data_panel._running
    assert not win.btn_test_1_row.isEnabled()
    win._teardown_runner()
    assert not win.data_panel._running
    assert win.btn_test_1_row.isEnabled()


def test_preflight_rechecks_blank_cells_for_selected_range(qapp: QApplication) -> None:
    macro = Macro(per_row=[ActionItem(type="type_text", text="{Name}")])
    rows = [{"Name": "Kim"}, {"Name": ""}]
    dlg = PreflightDialog(macro, rows_data=rows, row_numbers=[2, 3])
    assert not dlg.btn_start.isEnabled()
    assert not dlg.btn_run_1_row.isEnabled()
    assert dlg.lbl_countdown.text() == Strings.PREFLIGHT_BLOCKED

    dlg.spin_end_row.setValue(1)
    assert not any(issue.is_error for issue in dlg.issues)
    assert dlg.btn_start.isEnabled()
    assert dlg.btn_run_1_row.isEnabled()
    assert dlg.lbl_countdown.text() == Strings.PREFLIGHT_CLICK_START

    dlg.spin_end_row.setValue(2)
    assert not dlg.btn_start.isEnabled()
    issue_texts = [dlg.list_issues.item(i).text() for i in range(dlg.list_issues.count())]
    assert any("Rows: 3" in text for text in issue_texts)


def test_new_macro_cancel_writes_no_file(win: MainWindow) -> None:
    win._add_quick_action("wait")
    win._prompt_unsaved_changes = lambda: Button.Cancel
    created: list[str] = []
    win.lib_panel.macro_created.connect(created.append)
    with patch("stepwise.ui.macro_library.QInputDialog.getText", return_value=("Fresh", True)):
        win.lib_panel._on_new_macro()
    assert not (Path(win._library_dir) / "Fresh.swm").exists()
    assert created == []
    assert win.is_dirty()
    assert win._current_macro_path is None


def test_new_macro_prompts_only_once_when_discarding(win: MainWindow) -> None:
    win._add_quick_action("wait")
    prompts: list[int] = []

    def prompt() -> Button:
        prompts.append(1)
        return Button.Discard

    win._prompt_unsaved_changes = prompt
    with patch("stepwise.ui.macro_library.QInputDialog.getText", return_value=("Fresh", True)):
        win.lib_panel._on_new_macro()
    assert prompts == [1]
    assert win._current_macro.name == "Fresh"
    assert not win.is_dirty()


def test_save_while_switching_keeps_list_on_loaded_macro(win: MainWindow) -> None:
    library = Path(win._library_dir)
    first, second = library / "A.swm", library / "B.swm"
    save_package(Macro(name="A"), str(first))
    save_package(Macro(name="B"), str(second))
    win.lib_panel.refresh_list()
    win.lib_panel.select_path(str(first))
    win._add_quick_action("wait")
    win._prompt_unsaved_changes = lambda: Button.Save

    win.lib_panel.select_path(str(second))

    assert win._current_macro.name == "B"
    selected = win.lib_panel.list_widget.selectedItems()
    assert [Path(item.data(256)).name for item in selected] == ["B.swm"]


def test_previewing_data_in_blank_macro_is_not_dirty(win: MainWindow, tmp_path: Path) -> None:
    data = _write_csv(tmp_path / "peek.csv", ["Name", "Kim"])
    win.data_panel.load_file(str(data))
    assert not win.is_dirty()
    prompt = MagicMock()
    win._prompt_unsaved_changes = prompt
    assert win.close() is True
    prompt.assert_not_called()


def test_data_change_marks_macro_with_steps_dirty(win: MainWindow, tmp_path: Path) -> None:
    win._current_macro.per_row = [ActionItem(type="wait")]
    win._mark_saved()
    win.data_panel.load_file(str(_write_csv(tmp_path / "d.csv", ["Name", "Kim"])))
    assert win.is_dirty()


def test_open_results_folder_reports_path_errors(win: MainWindow) -> None:
    with (
        patch(
            "stepwise.ui.main_window.default_results_directory", side_effect=OSError("no home")
        ),
        patch("stepwise.ui.main_window.QMessageBox.warning") as warning,
    ):
        win._user_settings.pop("results_dir", None)
        win._open_results_folder()
    warning.assert_called_once()


def test_en_and_ko_strings_share_format_placeholders() -> None:
    import string

    from stepwise.ui import strings as strings_module

    formatter = string.Formatter()

    def fields(value: str) -> set[str]:
        return {name for _, name, _, _ in formatter.parse(value) if name is not None}

    pairs = [
        (strings_module._EN_STRINGS, strings_module._KO_STRINGS),
        (strings_module._EN_TOOLTIPS, strings_module._KO_TOOLTIPS),
    ]
    mismatched = [
        key
        for english, korean in pairs
        for key, value in korean.items()
        if key not in english or fields(english[key]) != fields(value)
    ]
    assert mismatched == []


# --- Stage 2 (package D) ----------------------------------------------------------


def test_tree_summaries_in_korean_with_missing_input_hints(korean: None) -> None:
    from stepwise.ui.action_tree import format_action_target

    image_hint = "⚠ 찾을 이미지를 캡처해주세요"
    assert format_action_target(ActionItem(type="type_text", text="")) == "⚠ 입력할 글자를 적어주세요"
    assert format_action_target(ActionItem(type="key", keys="")) == "⚠ 누를 키를 정해주세요"
    for kind in ("click_image", "wait_image", "wait_image_gone"):
        assert format_action_target(ActionItem(type=kind, image="")) == image_hint
    # (0, 0) may be a real coordinate: shown, not flagged.
    assert format_action_target(ActionItem(type="click", x=0, y=0)) == "클릭 (0, 0)"
    assert format_action_target(ActionItem(type="wait", seconds=2)) == "2초 기다리기"
    assert format_action_target(ActionItem(type="key", keys="enter", repeat=2)) == (
        '"enter" 키 누르기 (2회)'
    )


def test_tree_summaries_keep_english_format() -> None:
    from stepwise.ui.action_tree import format_action_target

    assert format_action_target(ActionItem(type="type_text", text="")) == 'Type ""'
    assert format_action_target(ActionItem(type="key", keys="enter", repeat=2)) == 'Key "enter" x2'
    double = ActionItem(type="click", x=0, y=0, clicks=2)
    assert format_action_target(double) == "Double Click (0, 0)"
    assert format_action_target(ActionItem(type="wait_image", image="a.png", timeout=5)) == (
        'Wait for "a.png" (max 5s)'
    )


def test_tree_action_column_localized(win: MainWindow, korean: None) -> None:
    action = ActionItem(type="type_text", text="hi")
    win._current_macro.per_row = [action]
    win.retranslate_ui()
    node = win.action_tree._find_node_by_step_id(action.id)
    assert node.text(2) == Strings.TYPE_TYPE_TEXT == "텍스트 입력"
    assert win.action_tree._target_display("per_row", None) == "② 반복"


def test_tree_action_column_keeps_type_id_in_english(win: MainWindow) -> None:
    action = ActionItem(type="type_text", text="hi")
    win._current_macro.per_row = [action]
    win.action_tree.rebuild_tree()
    assert win.action_tree._find_node_by_step_id(action.id).text(2) == "type_text"


def test_floating_panel_korean_and_back(qapp: QApplication, korean: None) -> None:
    from stepwise.engine.timing import SpeedMode
    from stepwise.ui.run_panel import FloatingRunPanel

    panel = FloatingRunPanel()
    panel.update_progress(row=5, total=20, step_desc="x", ok_cnt=1, failed_cnt=0)
    panel.set_speed_text(SpeedMode.VERY_SLOW)
    assert panel.lbl_row.text() == "20줄 중 5번째"
    assert "매우 느리게" in panel.lbl_speed.text()
    assert panel.lbl_hotkey.text() == "⛔ 멈추려면 F12"
    assert panel.btn_pause.text() == "⏸ 일시정지"

    apply_language("en")
    panel.retranslate_ui()
    assert panel.lbl_row.text() == "Row 5 / 20"
    assert "Very slow" in panel.lbl_speed.text()
    assert "F12" in panel.lbl_hotkey.text()
    panel.close()


def test_preflight_dialog_korean_labels(qapp: QApplication, korean: None) -> None:
    dlg = PreflightDialog(Macro(name="M"))
    assert dlg.btn_start.text() == "실행 시작"
    assert dlg.btn_run_1_row.text() == "1줄만 테스트"
    assert dlg.btn_cancel.text() == "취소"
    assert dlg.windowTitle() == '"M" 실행 준비'


def test_key_chips_and_unknown_key_hint(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QPushButton

    from stepwise.ui.properties_panel import PropertiesPanel

    panel = PropertiesPanel()
    action = ActionItem(type="key", keys="")
    panel.set_action(action)
    assert panel.lbl_key_warning.isHidden()

    chips = {b.text(): b for b in panel.key_chips.findChildren(QPushButton)}
    assert set(chips) == {"[Enter]", "[Tab]", "[Esc]", "[Ctrl+S]", "[Ctrl+V]", "[Ctrl+A]"}
    chips["[Ctrl+S]"].click()
    assert action.keys == "ctrl+s"
    assert panel.lbl_key_warning.isHidden()

    panel.txt_keys.setText("entr")
    assert not panel.lbl_key_warning.isHidden()
    panel.txt_keys.setText("ctrl+shift+end")
    assert panel.lbl_key_warning.isHidden()
    panel.close()


def test_wait_chips_set_seconds_and_wait_before(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QPushButton

    from stepwise.ui.properties_panel import PropertiesPanel

    panel = PropertiesPanel()
    action = ActionItem(type="wait", seconds=5)
    panel.set_action(action)
    chips = {b.text(): b for b in panel.wait_chips.findChildren(QPushButton)}
    assert list(chips) == ["[0.5s]", "[1s]", "[2s]", "[3s]"]
    chips["[0.5s]"].click()
    assert action.seconds == 0.5
    before = {b.text(): b for b in panel.wait_before_chips.findChildren(QPushButton)}
    before["[2s]"].click()
    assert action.wait_before == 2.0
    panel.close()


def test_single_test_button_and_folded_guard_verify(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QPushButton

    from stepwise.core.models import ImageCondition
    from stepwise.ui.properties_panel import PropertiesPanel

    panel = PropertiesPanel()
    for kind in ("click", "type_text", "key"):
        panel.set_action(ActionItem(type=kind))
        texts = [b.text() for b in panel.container.findChildren(QPushButton)]
        assert texts.count(Strings.TEST_THIS_STEP) == 1
        assert not any(Strings.TEST_THIS_STEP in t and t != Strings.TEST_THIS_STEP for t in texts)
        assert panel.safety_box.isHidden()

    guarded = ActionItem(type="click", guard=ImageCondition(image="images/g.png"))
    panel.set_action(guarded)
    assert not panel.safety_box.isHidden()
    panel.btn_safety_toggle.click()  # fold
    assert panel.safety_box.isHidden()
    assert guarded.guard is not None and guarded.guard.image == "images/g.png"
    panel.close()


def test_toolbar_run_label_counts_rows(win: MainWindow, tmp_path: Path) -> None:
    assert win.btn_run.text() == "▶ Run"
    win.data_panel.load_file(str(_write_csv(tmp_path / "d.csv", ["N", "1", "2", "3"])))
    assert win.btn_run.text() == "▶ Run (3)"
    apply_language("ko")
    try:
        win.retranslate_ui()
        assert win.btn_run.text() == "▶ 실행 (3줄)"
        assert win.btn_test_1_row.text() == "🧪 1줄 테스트"
    finally:
        apply_language("en")
        win.retranslate_ui()
    assert win.btn_test_1_row.text() == "🧪 Test 1 Row"


def test_toolbar_test_1_row_uses_selected_row(win: MainWindow, tmp_path: Path) -> None:
    win.data_panel.load_file(str(_write_csv(tmp_path / "d.csv", ["N", "a", "b", "c"])))
    win.data_panel.table.setCurrentCell(1, 2)
    with patch.object(win, "_start_execution") as start:
        win.btn_test_1_row.click()
    opts = start.call_args.args[0]
    assert opts["run_1_row"] is True
    assert opts["start_row"] == 2
    assert opts["countdown_seconds"] == 3.0


def test_toolbar_test_1_row_blocked_by_preflight_errors(win: MainWindow, tmp_path: Path) -> None:
    win._current_macro.per_row = [ActionItem(type="type_text", text="{Missing}")]
    win.data_panel.load_file(str(_write_csv(tmp_path / "d.csv", ["N", "a"])))
    with (
        patch.object(win, "_start_execution") as start,
        patch("stepwise.ui.main_window.QMessageBox.warning") as warning,
    ):
        win._on_test_1_row_clicked()
    start.assert_not_called()
    warning.assert_called_once()


def test_capture_banner_is_not_saved_into_capture(
    qapp: QApplication, tmp_path: Path, korean: None
) -> None:
    import cv2
    import numpy as np
    from PySide6.QtCore import QRect

    from stepwise.ui.capture_overlay import CaptureOverlay

    frame = np.full((60, 80, 4), 7, dtype=np.uint8)
    with patch("stepwise.ui.capture_overlay.capture_screen", return_value=frame):
        overlay = CaptureOverlay(mode="region", images_dir=str(tmp_path))
    assert overlay.banner_text() == "캡처할 영역을 드래그하세요 · Esc 취소"
    overlay.resize(80, 60)
    overlay.grab()  # paints the banner over the frozen screenshot

    saved: list[str] = []
    overlay.region_captured.connect(lambda rel, _region: saved.append(rel))
    overlay._dpr = 1.0
    overlay._save_region(QRect(0, 0, 40, 30))
    image = cv2.imread(str(tmp_path / Path(saved[0]).name), cv2.IMREAD_UNCHANGED)
    assert image.shape[:2] == (30, 40)
    assert (image == 7).all()
    overlay.close()

    banners = {"pick": Strings.CAPTURE_BANNER_PICK, "element": Strings.CAPTURE_BANNER_ELEMENT}
    for mode, text in banners.items():
        with patch("stepwise.ui.capture_overlay.capture_screen", return_value=frame):
            other = CaptureOverlay(mode=mode, images_dir=str(tmp_path))
        assert other.banner_text() == text
        other.close()


def test_preflight_warns_about_unknown_text_variables() -> None:
    from stepwise.engine.preflight import run_preflight_checks

    macro = Macro(
        per_row=[
            ActionItem(type="type_text", text="{Nmae}"),
            ActionItem(type="type_text", text="{Other}", enabled=False),
            ActionItem(type="type_text", text="{Name}"),
        ]
    )
    rows = [{"Name": "Kim"}]
    issues = run_preflight_checks(macro, rows_data=rows, headers=["Name"])
    unknown = [i for i in issues if i.is_warning and "no column" in i.message]
    assert len(unknown) == 1
    assert "Step #1" in unknown[0].message and "{Nmae}" in unknown[0].message
    assert unknown[0].details == 'Did you mean "{Name}"?'

    # Without connected data there is nothing to compare against.
    assert not [i for i in run_preflight_checks(macro) if "no column" in i.message]


def test_preflight_dialog_lists_unknown_variable_warning(qapp: QApplication) -> None:
    macro = Macro(per_row=[ActionItem(type="type_text", text="{Nmae}")])
    dlg = PreflightDialog(macro, rows_data=[{"Name": "Kim"}], headers=["Name"])
    texts = [dlg.list_issues.item(i).text() for i in range(dlg.list_issues.count())]
    assert any(Strings.PREFLIGHT_WARNING_PREFIX in t and "{Nmae}" in t for t in texts)


# --- Stage 3 (second audit fixes) ---------------------------------------------------


def test_new_macro_prompt_cancels_pending_step_test(win: MainWindow) -> None:
    action = ActionItem(type="click", x=1, y=1)
    win._current_macro.per_row.append(action)
    win._request_step_test(action)
    assert win._step_test_pending and win._step_test_timer.isActive()
    seen: list[tuple[bool, bool]] = []

    def fake_get_text(*_args: object, **_kwargs: object) -> tuple[str, bool]:
        seen.append((win._step_test_pending, win._step_test_timer.isActive()))
        return "", False

    with patch("stepwise.ui.macro_library.QInputDialog.getText", side_effect=fake_get_text):
        win.lib_panel._on_new_macro()
    assert seen == [(False, False)]


def test_modal_entry_points_cancel_pending_step_test(win: MainWindow) -> None:
    seen: list[bool] = []

    def record(*_args: object, **_kwargs: object) -> tuple[str, str]:
        seen.append(win._step_test_pending)
        return "", ""

    _start_pending_step_test(win)
    with patch("stepwise.ui.data_panel.QFileDialog.getOpenFileName", side_effect=record):
        win.data_panel._on_choose_file()

    _start_pending_step_test(win)
    with patch("stepwise.ui.main_window.SettingsDialog") as dialog_cls:
        dialog_cls.return_value.exec.side_effect = lambda: seen.append(win._step_test_pending)
        win._open_settings()

    _start_pending_step_test(win)
    with patch("stepwise.ui.main_window.PreflightDialog") as dialog_cls:
        dialog_cls.return_value.exec.side_effect = lambda: seen.append(win._step_test_pending)
        win._on_run_clicked()
    assert seen == [False, False, False]


def _blank_cell_preflight() -> PreflightDialog:
    macro = Macro(per_row=[ActionItem(type="type_text", text="{Name}")])
    rows = [{"Name": "Kim"}, {"Name": ""}]
    dlg = PreflightDialog(macro, rows_data=rows, row_numbers=[2, 3], countdown_seconds=2)
    dlg.spin_end_row.setValue(1)
    assert dlg.btn_start.isEnabled()
    return dlg


def test_preflight_range_change_cancels_countdown(qapp: QApplication) -> None:
    dlg = _blank_cell_preflight()
    with patch.object(dlg._countdown_timer, "start"):
        dlg._start_countdown()
    assert not dlg.btn_start.isEnabled()

    # Widening the range onto a blank required cell must abort the countdown.
    dlg.spin_end_row.setValue(2)
    assert not dlg._countdown_timer.isActive()
    assert dlg.lbl_countdown.text() == Strings.PREFLIGHT_BLOCKED
    assert not dlg.btn_start.isEnabled()
    for _ in range(5):
        dlg._countdown_tick()
    assert dlg.result() != PreflightDialog.Accepted
    assert dlg.confirmed_opts == {}

    # Back to a clean range: buttons come back, but nothing starts on its own.
    dlg.spin_end_row.setValue(1)
    assert dlg.btn_start.isEnabled()
    assert dlg.lbl_countdown.text() == Strings.PREFLIGHT_CLICK_START
    dlg._countdown_tick()
    assert dlg.result() != PreflightDialog.Accepted


def test_preflight_confirm_refuses_blocking_range(qapp: QApplication) -> None:
    dlg = _blank_cell_preflight()
    dlg.spin_end_row.setValue(2)
    assert any(issue.is_error for issue in dlg.issues)
    dlg._confirm(run_1_row=False)
    dlg._on_run_1_row()
    dlg._start_countdown()
    assert dlg.result() != PreflightDialog.Accepted
    assert dlg.confirmed_opts == {}
    assert not dlg._countdown_timer.isActive()


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_key_and_wait_chips_fit_320px_panel(qapp: QApplication, lang: str) -> None:
    from PySide6.QtCore import QPoint

    from stepwise.ui.properties_panel import PropertiesPanel

    apply_language(lang)
    try:
        panel = PropertiesPanel()
        panel.resize(320, 700)
        panel.show()
        qapp.processEvents()
        limit = panel.scroll.viewport().width()
        for kind, attr in (("key", "key_chips"), ("wait", "wait_chips")):
            panel.set_action(ActionItem(type=kind))
            qapp.processEvents()
            chips = getattr(panel, attr)
            for widget in (chips, panel.wait_before_chips, panel.btn_safety_toggle):
                assert widget.sizeHint().width() <= limit
            # Chip rows span the form instead of sitting in the field column.
            assert chips.mapTo(panel.container, QPoint(0, 0)).x() < 60
        panel.close()
    finally:
        apply_language("en")


def test_localize_issue_keeps_english_and_falls_back() -> None:
    from stepwise.engine.preflight import PreflightIssue, run_preflight_checks
    from stepwise.ui.preflight_dialog import localize_issue

    macro = Macro(per_row=[ActionItem(type="type_text", text="{Nmae}")])
    issues = run_preflight_checks(macro, rows_data=[{"Name": "Kim"}], headers=["Name"])
    coded = [issue for issue in issues if issue.code]
    assert {"MISSING_COLUMNS", "UNKNOWN_VARIABLE"} <= {issue.code for issue in coded}
    for issue in coded:
        # English templates mirror the engine text exactly.
        assert getattr(Strings, f"ISSUE_{issue.code}").format(**issue.params) == issue.message
        assert localize_issue(issue) == (issue.message, issue.details)

    apply_language("ko")
    try:
        legacy = PreflightIssue(level="WARNING", message="Data changed.", details="x")
        assert localize_issue(legacy) == ("Data changed.", "x")
    finally:
        apply_language("en")


def test_preflight_dialog_diagnostics_in_korean(qapp: QApplication, korean: None) -> None:
    macro = Macro(per_row=[ActionItem(type="type_text", text="{Nmae}")])
    dlg = PreflightDialog(macro, rows_data=[{"Name": "Kim"}], headers=["Name"])
    joined = "\n".join(dlg.list_issues.item(i).text() for i in range(dlg.list_issues.count()))
    assert "🔴 오류: 데이터 파일에 필요한 열이 없습니다: Nmae" in joined
    assert '1번 단계(② 반복)에서 "{Nmae}"' in joined
    assert '"{Name}"을(를) 쓰려던 것인가요?' in joined
    assert "Missing required columns" not in joined
    assert "Did you mean" not in joined


def test_toolbar_test_1_row_blocked_warning_in_korean(
    win: MainWindow, tmp_path: Path, korean: None
) -> None:
    win._current_macro.per_row = [ActionItem(type="type_text", text="{Missing}")]
    win.data_panel.load_file(str(_write_csv(tmp_path / "d.csv", ["N", "a"])))
    with (
        patch.object(win, "_start_execution"),
        patch("stepwise.ui.main_window.QMessageBox.warning") as warning,
    ):
        win._on_test_1_row_clicked()
    body = warning.call_args.args[2]
    assert "데이터 파일에 필요한 열이 없습니다: Missing" in body
    assert "Missing required columns" not in body


def test_retry_status_message_and_countdown_follow_settings(win: MainWindow) -> None:
    win._data_rows = [{"A": "1"}, {"A": "2"}, {"A": "3"}]
    win._data_row_nums = [1, 2, 3]
    win._last_run_opts = {"start_row": 1, "end_row_index": 2}
    win._user_settings["countdown_seconds"] = 0
    with patch.object(win, "_start_execution") as start:
        win._retry_failed_rows([2])
    assert start.call_args.args[0]["countdown_seconds"] == 0.0
    assert win.status_bar.currentMessage() == Strings.RETRY_FAILED_STATUS.format(
        count=1, row=2, sec="0"
    )
    assert "to end" not in win.status_bar.currentMessage()


# --- Stage 4: no step-test input into dialogs ------------------------------------


@pytest.mark.parametrize("getter", ["activeModalWidget", "activePopupWidget"])
def test_step_test_cancelled_when_dialog_or_menu_is_open(win: MainWindow, getter: str) -> None:
    _start_pending_step_test(win)
    with (
        patch.object(QApplication, getter, return_value=MagicMock()),
        patch("stepwise.engine.actions.execute_action") as execute,
    ):
        for _ in range(3):
            win._on_step_test_tick()
    execute.assert_not_called()
    assert not win._step_test_pending
    assert not win._step_test_timer.isActive()
    assert win.status_bar.currentMessage() == Strings.STEP_TEST_CANCELLED_DIALOG


def test_no_modal_or_popup_by_default(qapp: QApplication) -> None:
    assert QApplication.activeModalWidget() is None
    assert QApplication.activePopupWidget() is None


def _pending_when_called(win: MainWindow) -> tuple[list[bool], object]:
    seen: list[bool] = []

    def record(*_args: object, **_kwargs: object) -> object:
        seen.append(win._step_test_pending)
        return QMessageBox.StandardButton.Ok

    return seen, record


def test_save_with_existing_path_cancels_step_test(win: MainWindow, tmp_path: Path) -> None:
    win._current_macro_path = str(tmp_path / "m.swm")
    _start_pending_step_test(win)
    seen, record = _pending_when_called(win)
    with (
        patch("stepwise.ui.main_window.save_package", side_effect=OSError("disk full")),
        patch("stepwise.ui.main_window.QMessageBox.warning", side_effect=record),
    ):
        assert win.save_current_macro() is False
    assert seen == [False]


def test_image_match_test_cancels_step_test(win: MainWindow) -> None:
    _start_pending_step_test(win)
    seen, record = _pending_when_called(win)
    with patch("stepwise.ui.main_window.QMessageBox.warning", side_effect=record):
        win._test_image_match(ActionItem(type="wait_image"))
    assert seen == [False]


def test_selector_validation_cancels_step_test(win: MainWindow) -> None:
    _start_pending_step_test(win)
    seen, record = _pending_when_called(win)
    with patch("stepwise.ui.main_window.QMessageBox.information", side_effect=record):
        win._validate_and_highlight_selector(ActionItem(type="click"))
    assert seen == [False]


def test_window_picker_cancels_step_test(win: MainWindow) -> None:
    from PySide6.QtWidgets import QPushButton

    win.prop_panel.set_action(ActionItem(type="window_set_bounds"))
    _start_pending_step_test(win)
    seen, record = _pending_when_called(win)
    pick = next(
        b
        for b in win.prop_panel.findChildren(QPushButton)
        if b.text() == Strings.WINDOW_PICK_BUTTON
    )
    with (
        patch("stepwise.services.window_win.list_visible_windows", return_value=[]),
        patch("PySide6.QtWidgets.QMessageBox.information", side_effect=record),
    ):
        pick.click()
    assert seen == [False]


def test_data_load_failure_cancels_step_test(win: MainWindow, tmp_path: Path) -> None:
    _start_pending_step_test(win)
    seen, record = _pending_when_called(win)
    with patch("stepwise.ui.data_panel.QMessageBox.warning", side_effect=record):
        assert win.data_panel.load_file(str(tmp_path / "missing.csv")) is False
    assert seen == [False]
