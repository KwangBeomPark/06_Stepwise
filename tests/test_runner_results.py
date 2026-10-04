"""Tests for runner execution logging into ResultsManager."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from stepwise.core.models import ActionItem, Macro
from stepwise.engine.errors import AbortRequested, StepFailure
from stepwise.engine.results import ResultsManager
from stepwise.engine.runner import ExecutionCallbacks, run_macro
from stepwise.engine.timing import ExecutionController


def _manager(tmp_path: Path, macro_name: str) -> ResultsManager:
    return ResultsManager(
        macro_name,
        os.path.join(tmp_path, "sample.xlsx"),
        results_dir=os.path.join(tmp_path, "results"),
    )


def _records(manager: ResultsManager) -> list[dict[str, str]]:
    with open(manager.csv_path, encoding="utf-8-sig", newline="") as results_file:
        return list(csv.DictReader(results_file))


def test_runner_flushes_running_and_done_with_source_row_numbers(tmp_path: Path) -> None:
    manager = _manager(tmp_path, "TestResultsMacro")
    macro = Macro(
        name="TestResultsMacro",
        per_row=[ActionItem(type="wait", seconds=0.01)],
    )
    rows = [
        {"Name": "Alice", "Value": "100"},
        {"Name": "Bob", "Value": "200"},
    ]

    with patch("stepwise.engine.results.os.fsync", wraps=os.fsync) as fsync:
        summary = run_macro(
            macro=macro,
            rows_data=rows,
            row_numbers=[10, 20],
            data_filepath=manager.data_filepath,
            results_dir=manager.results_dir,
        )

    assert summary.done_count == 2
    assert summary.failed_count == 0
    assert [(record["row_number"], record["status"]) for record in _records(manager)] == [
        ("10", "Running"),
        ("10", "Done"),
        ("20", "Running"),
        ("20", "Done"),
    ]
    assert fsync.call_count == 4

    statuses = manager.load_latest_row_statuses()
    assert statuses[10].status == "Done"
    assert statuses[20].status == "Done"
    assert float(statuses[10].duration_sec) >= 0.0


def test_runner_flushes_failed_row_details(tmp_path: Path) -> None:
    manager = _manager(tmp_path, "FailureMacro")
    macro = Macro(name="FailureMacro", per_row=[ActionItem(type="wait", seconds=0.0)])
    failure = StepFailure(
        "target missing",
        step_id="step-1",
        step_label="Find target",
        row_number=42,
    )

    with (
        patch("stepwise.engine.runner.execute_action", side_effect=failure),
        patch("stepwise.engine.runner.save_failure_screenshot", return_value="failure.png"),
    ):
        summary = run_macro(
            macro=macro,
            rows_data=[{"Name": "Alice"}],
            row_numbers=[42],
            results_manager=manager,
        )

    records = _records(manager)
    assert [record["status"] for record in records] == ["Running", "Failed"]
    assert records[-1]["row_number"] == "42"
    assert records[-1]["failed_step_id"] == "step-1"
    assert records[-1]["failed_step_label"] == "Find target"
    assert records[-1]["reason"] == "target missing"
    assert records[-1]["screenshot"] == "failure.png"
    assert summary.failed_count == 1


def test_runner_flushes_interrupted_row(tmp_path: Path) -> None:
    manager = _manager(tmp_path, "InterruptedMacro")
    macro = Macro(name="InterruptedMacro", per_row=[ActionItem(type="wait", seconds=0.0)])

    with patch(
        "stepwise.engine.runner.execute_action",
        side_effect=AbortRequested(row_number=77),
    ):
        summary = run_macro(
            macro=macro,
            rows_data=[{"Name": "Alice"}],
            row_numbers=[77],
            results_manager=manager,
        )

    records = _records(manager)
    assert [record["status"] for record in records] == ["Running", "Interrupted"]
    assert records[-1]["row_number"] == "77"
    assert records[-1]["reason"] == "Execution stopped by user"
    assert summary.interrupted is True
    assert summary.interrupted_count == 1


def test_abort_between_rows_does_not_overwrite_completed_row(tmp_path: Path) -> None:
    manager = _manager(tmp_path, "BetweenRowsMacro")
    controller = ExecutionController()
    callbacks = ExecutionCallbacks(on_row_finished=lambda _row, _status: controller.stop())
    macro = Macro(name="BetweenRowsMacro", per_row=[ActionItem(type="wait", seconds=0.0)])

    summary = run_macro(
        macro=macro,
        rows_data=[{"Name": "Alice"}, {"Name": "Bob"}],
        row_numbers=[10, 20],
        controller=controller,
        callbacks=callbacks,
        results_manager=manager,
    )

    assert [(record["row_number"], record["status"]) for record in _records(manager)] == [
        ("10", "Running"),
        ("10", "Done"),
    ]
    assert summary.done_count == 1
    assert summary.interrupted_count == 1


def test_runner_rejects_misaligned_source_row_numbers(tmp_path: Path) -> None:
    manager = _manager(tmp_path, "BadRowsMacro")

    with pytest.raises(ValueError, match="one entry for each data row"):
        run_macro(
            macro=Macro(name="BadRowsMacro"),
            rows_data=[{"Name": "Alice"}, {"Name": "Bob"}],
            row_numbers=[10],
            results_manager=manager,
        )


def test_runner_handles_results_manager_write_failure_gracefully(tmp_path: Path) -> None:
    """Ensure locked results CSV (e.g. open in Excel) does not abort run or turn Done into Failed."""
    manager = _manager(tmp_path, "LockedResultsMacro")
    macro = Macro(name="LockedResultsMacro", per_row=[ActionItem(type="wait", seconds=0.0)])

    with patch.object(
        manager, "append_record", side_effect=PermissionError("File locked by Excel")
    ):
        summary = run_macro(
            macro=macro,
            rows_data=[{"Name": "Alice"}],
            row_numbers=[1],
            results_manager=manager,
        )

    assert summary.done_count == 1
    assert summary.failed_count == 0
