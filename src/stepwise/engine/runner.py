"""Stepwise macro execution loop.

Coordinates Setup, Per-Row iteration, and Cleanup stages according to Section 9.1.
Enforces the strict safety-first stop-on-failure principle and saves failure screenshots.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import cv2

from stepwise.engine.actions import _get_val, execute_action
from stepwise.engine.errors import AbortRequested, StepFailure
from stepwise.engine.results import ResultsManager, RowResultRecord, compute_row_hash
from stepwise.engine.timing import ExecutionController, SpeedMode
from stepwise.services.power import prevent_screen_sleep
from stepwise.services.screen import capture_screen


@dataclass
class RunSummary:
    run_id: str
    macro_name: str
    started_at: str
    finished_at: str
    duration_sec: float
    total_rows: int
    done_count: int
    failed_count: int
    interrupted_count: int
    skipped_count: int
    failure: StepFailure | None = None
    interrupted: bool = False
    screenshot_path: str | None = None
    results_csv_path: str | None = None
    pending_results_path: str | None = None
    buffered_results: list[RowResultRecord] = field(default_factory=list)
    persistence_errors: list[str] = field(default_factory=list)


class ExecutionCallbacks:
    """Callback hooks for UI signals or CLI reporters."""

    def __init__(
        self,
        on_run_started: Callable[[str, int], None] | None = None,
        on_row_started: Callable[[int, dict[str, object]], None] | None = None,
        on_step_started: Callable[[str, str], None] | None = None,
        on_step_finished: Callable[[str, str], None] | None = None,
        on_row_finished: Callable[[int, str], None] | None = None,
        on_run_finished: Callable[[RunSummary], None] | None = None,
        on_run_failed: Callable[[StepFailure, str | None], None] | None = None,
    ) -> None:
        self.on_run_started = on_run_started
        self.on_row_started = on_row_started
        self.on_step_started = on_step_started
        self.on_step_finished = on_step_finished
        self.on_row_finished = on_row_finished
        self.on_run_finished = on_run_finished
        self.on_run_failed = on_run_failed


def save_failure_screenshot(
    results_dir: str,
    run_id: str,
    row_number: int | None,
    step_id: str | None,
) -> str | None:
    """Capture full screen and save failure snapshot in results_dir/screenshots/."""
    try:
        screenshots_dir = os.path.join(results_dir, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        row_str = f"row{row_number}" if row_number is not None else "norow"
        step_str = f"step{step_id}" if step_id else "nostep"
        filename = f"{run_id}_{row_str}_{step_str}.png"
        filepath = os.path.join(screenshots_dir, filename)

        frame = capture_screen(check_black_screen=False)
        ext = os.path.splitext(filepath)[1]
        ok, encoded = cv2.imencode(ext, frame)
        if ok:
            with open(filepath, "wb") as f:
                f.write(encoded)
            return filepath
    except Exception as e:
        print(f"Warning: Failed to save failure screenshot: {e}")
    return None


def _append_result(res_mgr: ResultsManager | None, record: RowResultRecord) -> None:
    """Append row result record to ResultsManager safely.

    The results CSV is often open in Excel (locked on Windows); a failed write
    must not abort the macro or turn a completed row into a failure.
    """
    if res_mgr is None:
        return
    try:
        res_mgr.append_record(record)
    except Exception as e:
        # Covers managers whose primary append method fails before its normal
        # fallback handler runs. Completed automation must remain completed.
        res_mgr.defer_record(record)
        print(f"Warning: Failed to write {record.status} record for row {record.row_number}: {e}")


def run_macro(
    macro: Any,
    rows_data: Sequence[dict[str, object]] | None = None,
    controller: ExecutionController | None = None,
    callbacks: ExecutionCallbacks | None = None,
    speed: SpeedMode = SpeedMode.NORMAL,
    skip_setup: bool = False,
    skip_cleanup: bool = False,
    run_1_row: bool = False,
    start_row_index: int = 0,
    end_row_index: int | None = None,
    results_dir: str = "results",
    package_dir: str | None = None,
    countdown_seconds: float = 0.0,
    data_filepath: str | None = None,
    row_numbers: Sequence[int] | None = None,
    results_manager: ResultsManager | None = None,
) -> RunSummary:
    """Execute complete macro workflow."""
    ctrl = controller or ExecutionController()
    cbs = callbacks or ExecutionCallbacks()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    macro_name = _get_val(macro, "name", "Unnamed Macro")
    settings = _get_val(macro, "settings") or {}
    default_wait_before = float(_get_val(settings, "default_wait_before", 0.2))
    default_confidence = float(_get_val(settings, "image_confidence", 0.95))

    setup_items = _get_val(macro, "setup") or []
    per_row_items = _get_val(macro, "per_row") or []
    cleanup_items = _get_val(macro, "cleanup") or []

    res_mgr = results_manager
    if res_mgr is None and (data_filepath or rows_data is not None):
        res_mgr = ResultsManager(
            macro_name=macro_name,
            data_filepath=data_filepath or "",
            results_dir=results_dir,
        )

    if rows_data is None or len(rows_data) == 0:
        effective_rows: list[dict[str, object]] = [{}]
    else:
        effective_rows = list(rows_data)

    total_available_rows = len(effective_rows)
    end_idx = (
        total_available_rows if end_row_index is None else min(end_row_index, total_available_rows)
    )
    start_idx = max(0, min(start_row_index, total_available_rows))

    if run_1_row:
        target_rows = effective_rows[start_idx : start_idx + 1]
    else:
        target_rows = effective_rows[start_idx:end_idx]

    if row_numbers is not None and len(row_numbers) > 0:
        if len(row_numbers) != len(effective_rows):
            raise ValueError("row_numbers must contain one entry for each data row")
        target_row_numbers = list(row_numbers[start_idx : start_idx + len(target_rows)])
    else:
        target_row_numbers = [start_idx + i + 1 for i in range(len(target_rows))]

    start_time = time.time()
    started_at_str = datetime.now().isoformat()

    if cbs.on_run_started:
        cbs.on_run_started(run_id, len(target_rows))

    if countdown_seconds > 0:
        ctrl.wait(countdown_seconds)

    done_count = 0
    failed_count = 0
    interrupted_count = 0
    skipped_count = 0
    failure: StepFailure | None = None
    is_interrupted = False
    screenshot_saved: str | None = None
    last_row_num: int | None = None
    current_row_started_at = ""
    current_row_start_time = 0.0
    current_row_hash = ""
    current_row_active = False

    with prevent_screen_sleep():
        try:
            # 1. SETUP SECTION (Runs once)
            if not skip_setup and setup_items:
                for item in setup_items:
                    ctrl.check_abort()
                    step_id = _get_val(item, "id", "")
                    step_note = _get_val(item, "note", "")
                    if cbs.on_step_started:
                        cbs.on_step_started(step_id, step_note)

                    execute_action(
                        item,
                        row_data={},
                        controller=ctrl,
                        speed=speed,
                        default_wait_before=default_wait_before,
                        default_confidence=default_confidence,
                        package_dir=package_dir,
                        row_number=None,
                    )

                    if cbs.on_step_finished:
                        cbs.on_step_finished(step_id, step_note)

            # 2. PER-ROW SECTION (Iterates through rows)
            for offset, row in enumerate(target_rows):
                ctrl.check_abort()
                row_num = target_row_numbers[offset]
                last_row_num = row_num
                current_row_started_at = datetime.now().isoformat()
                current_row_start_time = time.time()
                current_row_hash = compute_row_hash(row)
                current_row_active = True

                _append_result(
                    res_mgr,
                    RowResultRecord(
                        run_id=run_id,
                        row_number=row_num,
                        row_hash=current_row_hash,
                        status="Running",
                        started_at=current_row_started_at,
                        macro_name=macro_name,
                        speed=speed.value,
                    ),
                )

                if cbs.on_row_started:
                    cbs.on_row_started(row_num, row)

                for item in per_row_items:
                    ctrl.check_abort(row_num)
                    step_id = _get_val(item, "id", "")
                    step_note = _get_val(item, "note", "")
                    if cbs.on_step_started:
                        cbs.on_step_started(step_id, step_note)

                    execute_action(
                        item,
                        row_data=row,
                        controller=ctrl,
                        speed=speed,
                        default_wait_before=default_wait_before,
                        default_confidence=default_confidence,
                        package_dir=package_dir,
                        row_number=row_num,
                    )

                    if cbs.on_step_finished:
                        cbs.on_step_finished(step_id, step_note)

                done_count += 1
                current_row_active = False
                row_dur = round(time.time() - current_row_start_time, 2)
                _append_result(
                    res_mgr,
                    RowResultRecord(
                        run_id=run_id,
                        row_number=row_num,
                        row_hash=current_row_hash,
                        status="Done",
                        started_at=current_row_started_at,
                        finished_at=datetime.now().isoformat(),
                        duration_sec=str(row_dur),
                        macro_name=macro_name,
                        speed=speed.value,
                    ),
                )

                if cbs.on_row_finished:
                    cbs.on_row_finished(row_num, "Done")

                if run_1_row:
                    break

            # 3. CLEANUP SECTION (Runs once at the end if not run_1_row)
            if not run_1_row and not skip_cleanup and cleanup_items:
                for item in cleanup_items:
                    ctrl.check_abort()
                    step_id = _get_val(item, "id", "")
                    step_note = _get_val(item, "note", "")
                    if cbs.on_step_started:
                        cbs.on_step_started(step_id, step_note)

                    execute_action(
                        item,
                        row_data={},
                        controller=ctrl,
                        speed=speed,
                        default_wait_before=default_wait_before,
                        default_confidence=default_confidence,
                        package_dir=package_dir,
                        row_number=None,
                    )

                    if cbs.on_step_finished:
                        cbs.on_step_finished(step_id, step_note)

        except AbortRequested:
            is_interrupted = True
            interrupted_count += 1
            if current_row_active and last_row_num is not None:
                row_dur = (
                    round(time.time() - current_row_start_time, 2)
                    if current_row_start_time > 0
                    else 0.0
                )
                _append_result(
                    res_mgr,
                    RowResultRecord(
                        run_id=run_id,
                        row_number=last_row_num,
                        row_hash=current_row_hash,
                        status="Interrupted",
                        reason="Execution stopped by user",
                        started_at=current_row_started_at,
                        finished_at=datetime.now().isoformat(),
                        duration_sec=str(row_dur),
                        macro_name=macro_name,
                        speed=speed.value,
                    ),
                )
                if cbs.on_row_finished:
                    cbs.on_row_finished(last_row_num, "Interrupted")
                current_row_active = False

        except StepFailure as e:
            failure = e
            failed_count += 1
            target_fail_row = e.row_number
            if target_fail_row is None and current_row_active:
                target_fail_row = last_row_num
            screenshot_saved = save_failure_screenshot(
                results_dir=results_dir,
                run_id=run_id,
                row_number=target_fail_row,
                step_id=e.step_id,
            )
            if target_fail_row is not None:
                row_dur = (
                    round(time.time() - current_row_start_time, 2)
                    if current_row_start_time > 0
                    else 0.0
                )
                _append_result(
                    res_mgr,
                    RowResultRecord(
                        run_id=run_id,
                        row_number=target_fail_row,
                        row_hash=current_row_hash,
                        status="Failed",
                        failed_step_id=e.step_id or "",
                        failed_step_label=e.step_label or "",
                        reason=e.message,
                        screenshot=screenshot_saved or "",
                        started_at=current_row_started_at,
                        finished_at=datetime.now().isoformat(),
                        duration_sec=str(row_dur),
                        macro_name=macro_name,
                        speed=speed.value,
                    ),
                )
                if cbs.on_row_finished:
                    cbs.on_row_finished(target_fail_row, "Failed")
                current_row_active = False
            if cbs.on_run_failed:
                cbs.on_run_failed(e, screenshot_saved)

        except Exception as e:
            wrapped = StepFailure(
                message=f"Unexpected error: {e}",
                row_number=last_row_num,
                details=str(e),
            )
            failure = wrapped
            failed_count += 1
            screenshot_saved = save_failure_screenshot(
                results_dir=results_dir,
                run_id=run_id,
                row_number=last_row_num,
                step_id=None,
            )
            if current_row_active and last_row_num is not None:
                row_dur = (
                    round(time.time() - current_row_start_time, 2)
                    if current_row_start_time > 0
                    else 0.0
                )
                _append_result(
                    res_mgr,
                    RowResultRecord(
                        run_id=run_id,
                        row_number=last_row_num,
                        row_hash=current_row_hash,
                        status="Failed",
                        reason=str(e),
                        screenshot=screenshot_saved or "",
                        started_at=current_row_started_at,
                        finished_at=datetime.now().isoformat(),
                        duration_sec=str(row_dur),
                        macro_name=macro_name,
                        speed=speed.value,
                    ),
                )
                if cbs.on_row_finished:
                    cbs.on_row_finished(last_row_num, "Failed")
                current_row_active = False
            if cbs.on_run_failed:
                cbs.on_run_failed(wrapped, screenshot_saved)

    finished_at_str = datetime.now().isoformat()
    duration = time.time() - start_time

    summary = RunSummary(
        run_id=run_id,
        macro_name=macro_name,
        started_at=started_at_str,
        finished_at=finished_at_str,
        duration_sec=round(duration, 2),
        total_rows=len(target_rows),
        done_count=done_count,
        failed_count=failed_count,
        interrupted_count=interrupted_count,
        skipped_count=skipped_count,
        failure=failure,
        interrupted=is_interrupted,
        screenshot_path=screenshot_saved,
        results_csv_path=res_mgr.csv_path if res_mgr else None,
        pending_results_path=(
            res_mgr.pending_csv_path if res_mgr and res_mgr._use_pending else None
        ),
        buffered_results=list(res_mgr.pending_records) if res_mgr else [],
        persistence_errors=list(res_mgr.persistence_errors) if res_mgr else [],
    )

    if cbs.on_run_finished:
        cbs.on_run_finished(summary)

    return summary
