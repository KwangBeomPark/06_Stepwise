"""Unit tests for beginner UX/UI nudges and micro-interactions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from stepwise.core.models import ActionItem, Macro
from stepwise.engine.runner import ExecutionCallbacks, RunSummary, run_macro
from stepwise.engine.timing import ExecutionController, SpeedMode
from stepwise.ui.action_tree import ActionTreeWidget
from stepwise.ui.data_panel import DataPanel
from stepwise.ui.main_window import MainWindow
from stepwise.ui.properties_panel import PropertiesPanel
from stepwise.ui.run_summary import RunSummaryDialog
from stepwise.ui.strings import apply_language


@pytest.fixture(autouse=True)
def reset_language() -> None:
    yield
    apply_language("en")


def test_properties_panel_column_chips_and_preview(qapp: QApplication) -> None:
    apply_language("ko")
    panel = PropertiesPanel()

    headers = ["거래처", "금액", "메모"]
    sample_row = {"거래처": "삼성전자", "금액": "50000", "메모": "세금계산서"}
    panel.update_variable_completions(headers, sample_row=sample_row)

    # Select a type_text action
    act = ActionItem(type="type_text", text="송금: {거래처}님께 {금액}원", mode="keystrokes")
    panel.set_action(act)

    # Verify chip buttons were created
    assert len(panel.chip_buttons) == 3
    chip_texts = [btn.text() for btn in panel.chip_buttons]
    assert "+ {거래처}" in chip_texts
    assert "+ {금액}" in chip_texts

    # Verify live row 1 preview resolves variables
    assert panel.lbl_row_preview is not None
    assert "삼성전자" in panel.lbl_row_preview.text()
    assert "50000" in panel.lbl_row_preview.text()

    # Verify Korean IME nudge is visible when mode is keystrokes
    assert panel.lbl_hangeul_hint is not None
    assert not panel.lbl_hangeul_hint.isHidden()

    # Switch mode to paste -> IME nudge should hide
    panel.cmb_mode.setCurrentIndex(0)  # Paste
    assert panel.lbl_hangeul_hint.isHidden()


def test_properties_panel_chips_dynamic_refresh_on_data_load(qapp: QApplication) -> None:
    """When an action editor is already open and data file is connected/switched, chips refresh dynamically."""
    panel = PropertiesPanel()
    act = ActionItem(type="type_text", text="입력: ", mode="paste")
    panel.set_action(act)

    # Initially no data -> nudge button is present
    nudge_btns = [b for b in panel.chips_widget.findChildren(QPushButton) if "연결" in b.text() or "Connect" in b.text()]
    assert len(nudge_btns) == 1
    assert len(panel.chip_buttons) == 0

    # User loads data while editor is already open
    headers = ["품목", "수량"]
    panel.update_variable_completions(headers, sample_row={"품목": "사과", "수량": "10"})

    # Chips must be dynamically refreshed without needing to re-select action
    assert len(panel.chip_buttons) == 2
    assert panel.chip_buttons[0].text() == "+ {품목}"
    assert panel.chip_buttons[1].text() == "+ {수량}"


def test_properties_panel_insert_column_chip(qapp: QApplication) -> None:
    panel = PropertiesPanel()
    headers = ["상호명"]
    panel.update_variable_completions(headers)

    act = ActionItem(type="type_text", text="고객: ", mode="paste")
    panel.set_action(act)

    # Click the chip
    assert len(panel.chip_buttons) == 1
    chip = panel.chip_buttons[0]
    chip.click()

    assert panel.txt_text.text() == "고객: {상호명}"
    assert act.text == "고객: {상호명}"


def test_data_panel_get_failed_row_numbers(qapp: QApplication) -> None:
    panel = DataPanel()
    panel._row_numbers = [1, 2, 3, 4]
    panel._row_statuses = {}

    panel.update_row_status(1, "Done")
    panel.update_row_status(2, "Failed")
    panel.update_row_status(3, "Done")
    panel.update_row_status(4, "Failed")

    failed = panel.get_failed_row_numbers()
    assert failed == [2, 4]


def test_run_summary_retry_failed_isolated_rows(qapp: QApplication) -> None:
    # Case 1: Run with row failures -> retry button present and emits specific row numbers
    summary = RunSummary(
        run_id="test-run",
        macro_name="Test Macro",
        started_at="2026-10-31 10:00:00",
        finished_at="2026-10-31 10:00:15",
        duration_sec=15.0,
        total_rows=10,
        done_count=8,
        failed_count=2,
        interrupted_count=0,
        skipped_count=0,
        failed_row_numbers=[3, 7],
    )

    dlg = RunSummaryDialog(summary)
    mock_receiver = MagicMock()
    dlg.retry_failed_requested.connect(mock_receiver)

    retry_btns = [b for b in dlg.findChildren(QPushButton) if "Resume" in b.text() or "이어서 실행" in b.text()]
    assert len(retry_btns) == 1

    dlg._on_retry_failed()
    mock_receiver.assert_called_once_with([3, 7])

    # Case 2: Run with setup failure (no row numbers) -> retry button should NOT appear
    summary_setup_fail = RunSummary(
        run_id="setup-fail",
        macro_name="Test Macro",
        started_at="2026-10-31 10:00:00",
        finished_at="2026-10-31 10:00:01",
        duration_sec=1.0,
        total_rows=10,
        done_count=0,
        failed_count=1,
        interrupted_count=0,
        skipped_count=0,
        failed_row_numbers=[],
    )
    dlg_setup = RunSummaryDialog(summary_setup_fail)
    setup_retry_btns = [b for b in dlg_setup.findChildren(QPushButton) if "Resume" in b.text() or "이어서 실행" in b.text()]
    assert len(setup_retry_btns) == 0


def test_main_window_retry_failed_resumes_to_end_and_cleans_options(qapp: QApplication, tmp_path: object) -> None:
    settings = {"auto_check_updates": False}
    with patch("stepwise.ui.main_window.load_user_settings", return_value=settings), patch("stepwise.ui.main_window.save_user_settings"):
        win = MainWindow(library_dir=str(tmp_path))
        win._data_rows = [{"col": "v1"}, {"col": "v2"}, {"col": "v3"}]
        win._data_row_nums = [1, 2, 3]
        win._last_run_opts = {
            "speed": SpeedMode.SLOW,
            "skip_setup": True,
            "skip_cleanup": False,
            "step_by_step": True,
            "run_1_row": False,
            "scheduled": True,
            "lock_after": True,
        }

        with patch.object(win, "_start_execution") as mock_start:
            win._retry_failed_rows([2])
            assert mock_start.call_count == 1
            passed_opts = mock_start.call_args.args[0]
            # Ensure previous options were preserved
            assert passed_opts["speed"] == SpeedMode.SLOW
            assert passed_opts["skip_setup"] is True
            assert passed_opts["step_by_step"] is True
            # Ensure scheduled and lock_after were removed so machine does not lock
            assert "scheduled" not in passed_opts
            assert "lock_after" not in passed_opts
            # Ensure target rows resume from row #2 to end (rows 2 and 3)
            assert passed_opts["custom_row_nums"] == [2, 3]
            assert passed_opts["custom_rows"] == [{"col": "v2"}, {"col": "v3"}]
            # Ensure safe 3s countdown for switching active window
            assert passed_opts["countdown_seconds"] == 3.0


def test_runner_cleanup_failure_does_not_mark_data_rows_as_failed() -> None:
    """When cleanup fails after all rows are Done, the data rows must not be recorded as failed."""
    macro = Macro(name="Test Cleanup Failure")
    macro.per_row.append(ActionItem(type="wait", seconds=0.01))
    # Cleanup action that raises an unexpected exception
    bad_cleanup = ActionItem(type="click", x=-999999, y=-999999)
    macro.cleanup.append(bad_cleanup)

    controller = ExecutionController()
    callbacks = ExecutionCallbacks()

    with patch("stepwise.engine.actions.execute_action") as mock_exec:
        def side_effect(act: ActionItem, *args: object, **kwargs: object) -> None:
            if act == bad_cleanup:
                raise RuntimeError("Cleanup window was already closed!")
        mock_exec.side_effect = side_effect

        summary = run_macro(
            macro=macro,
            rows_data=({"c": "1"}, {"c": "2"}),
            controller=controller,
            callbacks=callbacks,
            row_numbers=(1, 2),
        )

        assert summary.done_count == 2
        assert summary.failed_count == 1  # 1 failure (the cleanup step)
        # Crucial check: No data row was marked failed!
        assert summary.failed_row_numbers == []


def test_action_tree_data_row_count_header_nudge(qapp: QApplication) -> None:
    apply_language("ko")
    tree = ActionTreeWidget()
    macro = Macro(name="Demo")
    macro.per_row.append(ActionItem(type="click", x=100, y=200))
    macro.per_row.append(ActionItem(type="type_text", text="abc"))
    tree.load_macro(macro)

    # Before connecting data
    header_item = tree.tree.topLevelItem(1)
    assert header_item is not None
    assert "데이터 연결 전" in header_item.text(2)

    # After connecting 25 rows
    tree.set_data_row_count(25)
    header_after = tree.tree.topLevelItem(1)
    assert header_after is not None
    assert "25줄 × 2단계" in header_after.text(2)


def test_locate_target_signal_emission(qapp: QApplication) -> None:
    panel = PropertiesPanel()
    act = ActionItem(type="click", x=500, y=300)
    panel.set_action(act)

    mock_locate = MagicMock()
    panel.request_locate_target.connect(mock_locate)

    assert panel.btn_locate is not None
    panel.btn_locate.click()
    mock_locate.assert_called_once_with(act)
