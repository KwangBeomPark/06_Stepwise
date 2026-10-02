"""Tests for Milestone 4: Execution UI components (PreflightDialog, FloatingRunPanel, RunSummary)."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from stepwise.core.models import ActionItem, Macro, RecordedScreen
from stepwise.engine.errors import StepFailure
from stepwise.engine.runner import RunSummary
from stepwise.engine.timing import SpeedMode
from stepwise.ui.preflight_dialog import PreflightDialog
from stepwise.ui.run_panel import FloatingRunPanel
from stepwise.ui.run_summary import RunSummaryDialog


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_preflight_dialog_diagnostics(qapp: QApplication) -> None:
    macro = Macro(
        name="Preflight UI Test",
        recorded_screen=RecordedScreen(width=1920, height=1080, scale_percent=100),
        per_row=[ActionItem(type="wait", seconds=0.1)],
    )

    dlg = PreflightDialog(macro=macro)
    assert dlg.list_issues.count() >= 1

    # Check Speed radio group
    dlg.rad_slow.setChecked(True)
    assert dlg.rad_slow.isChecked()
    dlg.close()


def test_floating_run_panel_properties(qapp: QApplication) -> None:
    panel = FloatingRunPanel()
    # Confirm WindowDoesNotAcceptFocus is set
    assert bool(panel.windowFlags() & Qt.WindowDoesNotAcceptFocus)

    # Test progress update
    panel.update_progress(row=5, total=20, step_desc="Click Save", ok_cnt=4, failed_cnt=0)
    assert panel.lbl_row.text() == "Row 5 / 20"
    assert panel.prog_bar.value() == 25
    assert panel.lbl_step.text() == "Click Save"

    # Test speed text
    panel.set_speed_text(SpeedMode.VERY_SLOW)
    assert "Very slow" in panel.lbl_speed.text()

    # Test overlap avoidance
    panel.ensure_not_overlapping(panel.x() + 10, panel.y() + 10)
    panel.close()


def test_run_summary_dialog(qapp: QApplication) -> None:
    summary = RunSummary(
        run_id="test_run",
        macro_name="Test Macro",
        started_at="2026-10-03T10:00:00",
        finished_at="2026-10-03T10:01:00",
        duration_sec=60.0,
        total_rows=10,
        done_count=9,
        failed_count=1,
        interrupted_count=0,
        skipped_count=0,
        failure=StepFailure("Image save.png not found", row_number=10, step_id="s5"),
    )

    dlg = RunSummaryDialog(summary=summary)
    assert dlg.windowTitle() == "Stepwise — Execution Summary"
    dlg.close()
