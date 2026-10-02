"""Unit tests for macro runner execution loop."""

from stepwise.engine.runner import ExecutionCallbacks, run_macro
from stepwise.engine.timing import ExecutionController


def test_runner_3_sections_sequence() -> None:
    events: list[str] = []

    macro = {
        "name": "Sequence Test",
        "settings": {"default_wait_before": 0.0},
        "setup": [{"type": "wait", "seconds": 0.01, "note": "Setup Step"}],
        "per_row": [{"type": "wait", "seconds": 0.01, "note": "Row Step"}],
        "cleanup": [{"type": "wait", "seconds": 0.01, "note": "Cleanup Step"}],
    }

    callbacks = ExecutionCallbacks(
        on_step_started=lambda step_id, note: events.append(f"start:{note}"),
        on_row_finished=lambda row_num, status: events.append(f"row:{row_num}:{status}"),
    )

    data = [{"Vendor": "A"}, {"Vendor": "B"}]
    summary = run_macro(macro, rows_data=data, callbacks=callbacks, countdown_seconds=0.0)

    assert summary.done_count == 2
    assert summary.failed_count == 0
    assert "start:Setup Step" in events
    assert "row:1:Done" in events
    assert "row:2:Done" in events
    assert "start:Cleanup Step" in events


def test_runner_run_1_row() -> None:
    macro = {
        "name": "Run 1 Row Test",
        "settings": {"default_wait_before": 0.0},
        "setup": [{"type": "wait", "seconds": 0.01, "note": "Setup"}],
        "per_row": [{"type": "wait", "seconds": 0.01, "note": "Row"}],
        "cleanup": [{"type": "wait", "seconds": 0.01, "note": "Cleanup"}],
    }

    data = [{"ID": "1"}, {"ID": "2"}, {"ID": "3"}]
    summary = run_macro(macro, rows_data=data, run_1_row=True, countdown_seconds=0.0)

    # Should only run 1 row and skip cleanup
    assert summary.done_count == 1
    assert summary.total_rows == 1


def test_runner_stop_abort() -> None:
    ctrl = ExecutionController()

    macro = {
        "name": "Abort Test",
        "settings": {"default_wait_before": 0.0},
        "setup": [],
        "per_row": [{"type": "wait", "seconds": 2.0, "note": "Long wait"}],
        "cleanup": [],
    }

    # Signal stop before or during wait
    ctrl.stop()
    summary = run_macro(macro, rows_data=[{"x": 1}], controller=ctrl, countdown_seconds=0.0)

    assert summary.interrupted is True
    assert summary.interrupted_count == 1
    assert summary.done_count == 0
