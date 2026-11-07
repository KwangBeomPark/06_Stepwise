"""Pre-flight check and run confirmation dialog (Section 11.2).

Displays:
- Diagnostics summary (blocking errors 🔴 and warnings 🟡)
- Speed selection (Normal / Slow +0.5s / Very slow +1s)
- Resume / Start from row selector
- Skip Setup, Skip Cleanup, Step-by-step checkboxes
- [Run 1 row], [Start], [Cancel]
"""

from __future__ import annotations

import os
from collections.abc import Collection, Sequence
from typing import Any

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from stepwise.core.models import Macro
from stepwise.engine.preflight import PreflightIssue, preview_row_range, run_preflight_checks
from stepwise.engine.timing import SpeedMode
from stepwise.ui.strings import Strings, get_current_language, normalize_status_code
from stepwise.ui.theme import get_theme_tokens

_ISSUE_SECTION_KEYS = {
    "Setup": "ISSUE_SECTION_SETUP",
    "Per Row": "ISSUE_SECTION_PER_ROW",
    "Cleanup": "ISSUE_SECTION_CLEANUP",
}


def localize_issue(issue: PreflightIssue) -> tuple[str, str]:
    """(message, details) in the UI language; falls back to the engine's English text."""
    if get_current_language() != "ko" or not issue.code:
        return issue.message, issue.details
    params = dict(issue.params)
    section_key = _ISSUE_SECTION_KEYS.get(str(params.get("section", "")))
    if section_key:
        params["section"] = getattr(Strings, section_key)

    def _format(key: str, fallback: str) -> str:
        template = getattr(Strings, key, None)
        if not isinstance(template, str):
            return fallback
        try:
            return template.format(**params)
        except (KeyError, IndexError, ValueError):
            return fallback

    message = _format(f"ISSUE_{issue.code}", issue.message)
    details = _format(f"ISSUE_{issue.code}_DETAILS", issue.details) if issue.details else ""
    return message, details


class PreflightDialog(QDialog):
    run_confirmed = Signal(dict)

    def __init__(
        self,
        macro: Macro,
        rows_data: Sequence[dict[str, str]] | None = None,
        row_numbers: Sequence[int] | None = None,
        headers: Sequence[str] | None = None,
        package_dir: str | None = None,
        data_file_path: str | None = None,
        initial_speed: SpeedMode = SpeedMode.NORMAL,
        suggested_start_row: int | None = None,
        parent: QWidget | None = None,
        results_dir: str = "results",
        countdown_seconds: float = 3,
        excluded_count: int = 0,
        excluded_row_numbers: Collection[int] | None = None,
        row_statuses: dict[int, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(Strings.PREFLIGHT_TITLE.format(name=macro.name))
        self.resize(620, 560)

        self.macro = macro
        self.rows_data = rows_data
        self.row_numbers = row_numbers or []
        self._excluded_row_numbers = frozenset(excluded_row_numbers or ())
        self._excluded_count = max(0, int(excluded_count), len(self._excluded_row_numbers))
        self._row_statuses = dict(row_statuses or {})
        self._check_args: dict[str, Any] = {
            "package_dir": package_dir,
            "data_file_path": data_file_path,
            "results_dir": results_dir,
            "headers": headers,
        }
        self.btn_start: QPushButton | None = None
        self.btn_reset_and_run: QPushButton | None = None
        self.confirmed_opts: dict[str, Any] = {}
        self._countdown_seconds = max(0, int(countdown_seconds))
        self._countdown_remaining = 5
        self._countdown_active = False
        self._pending_reset_statuses = False
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Title & Meta
        total_rows = len(rows_data) if rows_data else 1
        if data_file_path:
            data_name = f'"{os.path.basename(data_file_path)}"'
        elif macro.data_source and macro.data_source.file_hint:
            data_name = f'"{macro.data_source.file_hint}"'
        else:
            data_name = Strings.PREFLIGHT_NO_DATA
        info_text = Strings.PREFLIGHT_INFO.format(name=macro.name, data=data_name, rows=total_rows)
        if self._excluded_count > 0:
            done_total = sum(
                1
                for n in self._excluded_row_numbers
                if normalize_status_code(self._row_statuses.get(n, "")) == "Done"
            )
            skip_total = len(self._excluded_row_numbers) - done_total
            breakdown = Strings.PREFLIGHT_EXCLUDED_BREAKDOWN.format(
                count=self._excluded_count, done=done_total, skipped=skip_total
            )
            info_text += f"  ({breakdown})"
        info_lbl = QLabel(info_text)
        main_layout.addWidget(info_lbl)

        # 2. Preflight Checks List
        issues_box = QGroupBox(Strings.PREFLIGHT_DIAGNOSTICS)
        issues_layout = QVBoxLayout(issues_box)
        self.list_issues = QListWidget()
        issues_layout.addWidget(self.list_issues)
        main_layout.addWidget(issues_box)

        # Diagnostics run for the selected row range (see _refresh_issues).
        self.issues: list[PreflightIssue] = []

        # 3. Execution Options
        opts_box = QGroupBox(Strings.PREFLIGHT_OPTIONS)
        opts_layout = QFormLayout(opts_box)

        # Start from row
        self.spin_start_row = QSpinBox()
        self.spin_start_row.setRange(1, max(1, total_rows))
        if suggested_start_row:
            self.spin_start_row.setValue(suggested_start_row)

        # End at row (1-based inclusive ordinal, passed to run_macro as end_row_index)
        self.spin_end_row = QSpinBox()
        self.spin_end_row.setRange(self.spin_start_row.value(), max(1, total_rows))
        self.spin_end_row.setValue(max(1, total_rows))
        self.spin_start_row.valueChanged.connect(self._on_start_row_changed)
        self.spin_end_row.valueChanged.connect(self._update_range_preview)

        h_range = QHBoxLayout()
        h_range.addWidget(self.spin_start_row)
        h_range.addWidget(QLabel(Strings.PREFLIGHT_END_ROW))
        h_range.addWidget(self.spin_end_row)
        h_range.addStretch()
        opts_layout.addRow(Strings.PREFLIGHT_START_ROW, h_range)

        self.lbl_range_preview = QLabel()
        self.lbl_range_preview.setWordWrap(True)
        opts_layout.addRow("", self.lbl_range_preview)

        # Speed Mode
        h_speed = QHBoxLayout()
        self.btn_grp_speed = QButtonGroup(self)
        self.rad_normal = QRadioButton(Strings.PREFLIGHT_SPEED_NORMAL)
        self.rad_slow = QRadioButton(Strings.PREFLIGHT_SPEED_SLOW)
        self.rad_veryslow = QRadioButton(Strings.PREFLIGHT_SPEED_VERY_SLOW)
        self.btn_grp_speed.addButton(self.rad_normal)
        self.btn_grp_speed.addButton(self.rad_slow)
        self.btn_grp_speed.addButton(self.rad_veryslow)

        if initial_speed == SpeedMode.SLOW:
            self.rad_slow.setChecked(True)
        elif initial_speed == SpeedMode.VERY_SLOW:
            self.rad_veryslow.setChecked(True)
        else:
            self.rad_normal.setChecked(True)

        h_speed.addWidget(self.rad_normal)
        h_speed.addWidget(self.rad_slow)
        h_speed.addWidget(self.rad_veryslow)
        h_speed.addStretch()
        opts_layout.addRow(Strings.PREFLIGHT_SPEED, h_speed)

        # Section skips & Step-by-step
        h_flags = QHBoxLayout()
        self.chk_skip_setup = QCheckBox(Strings.PREFLIGHT_SKIP_SETUP)
        self.chk_skip_cleanup = QCheckBox(Strings.PREFLIGHT_SKIP_CLEANUP)
        self.chk_step_by_step = QCheckBox(Strings.STEP_BY_STEP)
        h_flags.addWidget(self.chk_skip_setup)
        h_flags.addWidget(self.chk_skip_cleanup)
        h_flags.addWidget(self.chk_step_by_step)
        h_flags.addStretch()
        opts_layout.addRow(Strings.PREFLIGHT_WORKFLOW, h_flags)

        main_layout.addWidget(opts_box)

        t = get_theme_tokens()

        # 4. Countdown Banner
        self.lbl_countdown = QLabel()
        main_layout.addWidget(self.lbl_countdown)

        # Gentle Safety Reminder Nudge
        self.lbl_f12_reminder = QLabel(f"💡 {Strings.F12_GENTLE_REMINDER}")
        self.lbl_f12_reminder.setWordWrap(True)
        self.lbl_f12_reminder.setStyleSheet(f"color: {t['text_secondary']}; font-size: 11px;")
        main_layout.addWidget(self.lbl_f12_reminder)

        # 5. Buttons
        btn_layout = QHBoxLayout()
        self.btn_run_1_row = QPushButton(Strings.PREFLIGHT_RUN_1_ROW)
        self.btn_run_1_row.setToolTip(Strings.PREFLIGHT_RUN_1_ROW_TOOLTIP)
        self.btn_run_1_row.setStyleSheet(
            f"border: 1px solid {t['accent_primary']}; color: {t['accent_primary']}; "
            f"font-weight: bold; padding: 7px 14px; border-radius: 4px;"
        )
        self.btn_run_1_row.clicked.connect(self._on_run_1_row)

        self.btn_reset_and_run = QPushButton(Strings.RESET_AND_RUN)
        self.btn_reset_and_run.setStyleSheet(
            f"background-color: {t['status_ok']}; color: white; font-weight: bold; padding: 8px 18px;"
        )
        self.btn_reset_and_run.clicked.connect(self._on_reset_and_run_clicked)
        self.btn_reset_and_run.hide()

        self.btn_start = QPushButton(Strings.PREFLIGHT_START)
        self.btn_start.setStyleSheet(
            f"background-color: {t['status_ok']}; color: white; font-weight: bold; padding: 8px 20px;"
        )
        self.btn_start.clicked.connect(self._start_countdown)

        self.btn_cancel = QPushButton(Strings.CANCEL)
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_run_1_row)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_reset_and_run)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_start)
        main_layout.addLayout(btn_layout)

        # Diagnostics, range preview and Start / Run 1 Row state for the initial range
        self._update_range_preview()

    def _selected_range(self) -> tuple[Sequence[dict[str, str]] | None, Sequence[int] | None]:
        """Rows (and source row numbers) inside the chosen start/end range, excluding Skipped/Done rows."""
        if not self.rows_data:
            return self.rows_data, self.row_numbers or None
        start = self.spin_start_row.value()
        end = self.spin_end_row.value()
        raw_rows = list(self.rows_data)[start - 1 : end]
        raw_nums = (
            list(self.row_numbers)[start - 1 : end]
            if self.row_numbers
            else list(range(start, start + len(raw_rows)))
        )
        if self._excluded_row_numbers:
            filtered_pairs = [
                (r, n)
                for r, n in zip(raw_rows, raw_nums, strict=True)
                if n not in self._excluded_row_numbers
            ]
            rows = [r for r, _ in filtered_pairs]
            nums = [n for _, n in filtered_pairs]
            return rows, nums
        return raw_rows, raw_nums

    def _on_reset_and_run_clicked(self) -> None:
        if self._has_blocking_issues():
            return
        self._pending_reset_statuses = True
        self._start_countdown()

    def _refresh_issues(self) -> None:
        """Re-run diagnostics so blank cells outside the chosen range or in excluded rows don't block it."""
        rows, nums = self._selected_range()
        start = self.spin_start_row.value()
        end = self.spin_end_row.value()
        raw_rows = list(self.rows_data)[start - 1 : end] if self.rows_data else []
        raw_nums = (
            list(self.row_numbers)[start - 1 : end]
            if self.row_numbers
            else list(range(start, start + len(raw_rows)))
        )
        has_original_rows = bool(self.rows_data and len(self.rows_data) > 0)
        all_excluded = False
        if has_original_rows and self._excluded_row_numbers and not rows:
            all_excluded = True

        all_done = False
        if all_excluded and raw_nums:
            all_done = all(
                normalize_status_code(self._row_statuses.get(n, "")) == "Done"
                for n in raw_nums
            )

        if all_excluded:
            if all_done:
                raw_diagnostics = run_preflight_checks(
                    macro=self.macro, rows_data=raw_rows, row_numbers=raw_nums, **self._check_args
                )
                raw_errors = [i for i in raw_diagnostics if i.is_error]
                if raw_errors:
                    self.issues = raw_errors
                else:
                    self.issues = [
                        PreflightIssue(
                            level="WARNING",
                            code="ALL_ROWS_DONE",
                            message=Strings.PREFLIGHT_ALL_DONE_TITLE,
                            details=Strings.PREFLIGHT_ALL_DONE_MSG,
                        )
                    ] + [i for i in raw_diagnostics if not i.is_error]
            else:
                self.issues = [
                    PreflightIssue(
                        level="ERROR",
                        code="ALL_ROWS_EXCLUDED",
                        message=Strings.ISSUE_ALL_ROWS_EXCLUDED,
                        details=Strings.ISSUE_ALL_ROWS_EXCLUDED_DETAILS,
                    )
                ]
        else:
            self.issues = run_preflight_checks(
                macro=self.macro, rows_data=rows, row_numbers=nums, **self._check_args
            )
        self.list_issues.clear()
        self._populate_issues()
        if self.btn_start is None:
            return
        # A range change invalidates the confirmed range: abort any running countdown.
        self._cancel_countdown()
        t = get_theme_tokens()
        has_errors = self._has_blocking_issues()
        self.btn_start.setEnabled(not has_errors and not all_done)
        self.btn_run_1_row.setEnabled(not has_errors)

        if all_done:
            self.btn_reset_and_run.show()
            self.btn_reset_and_run.setEnabled(not has_errors)
            if has_errors:
                self.lbl_countdown.setText(Strings.PREFLIGHT_BLOCKED)
                self.lbl_countdown.setStyleSheet(f"color: {t['status_fail']}; font-weight: bold;")
            else:
                self.lbl_countdown.setText(Strings.PREFLIGHT_ALL_DONE_TITLE)
                self.lbl_countdown.setStyleSheet(f"color: {t['status_warn']}; font-weight: bold;")
        else:
            self.btn_reset_and_run.hide()
            if has_errors:
                self.lbl_countdown.setText(Strings.PREFLIGHT_BLOCKED)
                self.lbl_countdown.setStyleSheet(f"color: {t['status_fail']}; font-weight: bold;")
            else:
                self.lbl_countdown.setText(Strings.PREFLIGHT_CLICK_START)
                self.lbl_countdown.setStyleSheet(
                    f"color: {t['accent_primary']}; font-weight: bold; font-size: 13px;"
                )

    def _populate_issues(self) -> None:
        t = get_theme_tokens()
        if not self.issues:
            it = QListWidgetItem(Strings.PREFLIGHT_ALL_PASSED)
            it.setForeground(QColor(t["status_ok"]))
            self.list_issues.addItem(it)
            return

        for issue in self.issues:
            prefix = (
                Strings.PREFLIGHT_ERROR_PREFIX if issue.is_error else Strings.PREFLIGHT_WARNING_PREFIX
            )
            message, details = localize_issue(issue)
            text = f"{prefix}{message}"
            if details:
                text += f"\n   ↳ {details}"
            item = QListWidgetItem(text)
            if issue.is_error:
                item.setForeground(QColor(t["status_fail"]))
            else:
                item.setForeground(QColor(t["status_warn"]))
            self.list_issues.addItem(item)

    def _on_start_row_changed(self, value: int) -> None:
        self.spin_end_row.setMinimum(value)
        self._update_range_preview()

    def _update_range_preview(self) -> None:
        self._refresh_issues()
        active_rows, active_nums = self._selected_range()
        start = self.spin_start_row.value()
        end = self.spin_end_row.value()
        raw_nums = (
            list(self.row_numbers)[start - 1 : end]
            if self.row_numbers
            else list(range(start, start + len(list(self.rows_data or [])[start - 1 : end])))
        )
        excluded_in_range = [n for n in raw_nums if n in self._excluded_row_numbers]

        if not active_rows or not active_nums:
            if raw_nums and excluded_in_range:
                done_cnt = sum(
                    1
                    for n in excluded_in_range
                    if normalize_status_code(self._row_statuses.get(n, "")) == "Done"
                )
                skip_cnt = len(excluded_in_range) - done_cnt
                breakdown = Strings.PREFLIGHT_EXCLUDED_BREAKDOWN.format(
                    count=len(excluded_in_range), done=done_cnt, skipped=skip_cnt
                )
                self.lbl_range_preview.setText(f"ℹ️ {breakdown}")
                self.lbl_range_preview.show()
            else:
                self.lbl_range_preview.hide()
            return
        preview = preview_row_range(
            active_rows,
            active_nums,
            1,
            len(active_rows),
        )
        if preview is None:
            self.lbl_range_preview.hide()
            return
        preview_text = Strings.PREFLIGHT_RANGE_PREVIEW.format(
            first=preview.first_row_number,
            last=preview.last_row_number,
            count=preview.count,
            sample=preview.sample or "-",
        )
        sample_row = active_rows[0]
        typing_samples: list[str] = []
        for item in getattr(self.macro, "per_row", []) or []:
            act_type = getattr(item, "type", None) or (
                item.get("type") if isinstance(item, dict) else None
            )
            if act_type == "type_text":
                raw_text = getattr(item, "text", "") or (
                    item.get("text", "") if isinstance(item, dict) else ""
                )
                if "{" in raw_text and "}" in raw_text:
                    from stepwise.core.variables import substitute_variables

                    try:
                        resolved = substitute_variables(raw_text, sample_row, strict=False)
                        if resolved != raw_text:
                            typing_samples.append(f"{raw_text} ➔ '{resolved}'")
                    except Exception:
                        pass
        if excluded_in_range:
            done_cnt = sum(
                1
                for n in excluded_in_range
                if normalize_status_code(self._row_statuses.get(n, "")) == "Done"
            )
            skip_cnt = len(excluded_in_range) - done_cnt
            breakdown = Strings.PREFLIGHT_EXCLUDED_BREAKDOWN.format(
                count=len(excluded_in_range), done=done_cnt, skipped=skip_cnt
            )
            preview_text += f"\n   ↳ ℹ️ {breakdown}"

        if typing_samples:
            preview_text += f"\n   ↳ {Strings.PREFLIGHT_FIRST_ROW_SAMPLE} {', '.join(typing_samples[:2])}"

        self.lbl_range_preview.setText(preview_text)
        self.lbl_range_preview.show()

    def _on_run_1_row(self) -> None:
        # This button skips the dialog countdown; the engine waits instead.
        self._confirm(run_1_row=True)

    def _has_blocking_issues(self) -> bool:
        return any(i.is_error for i in self.issues)

    def _cancel_countdown(self) -> None:
        self._countdown_timer.stop()
        self._countdown_active = False
        self._pending_reset_statuses = False

    def _start_countdown(self) -> None:
        if self._has_blocking_issues():
            return
        self.btn_start.setEnabled(False)
        self.btn_run_1_row.setEnabled(False)
        if getattr(self, "btn_reset_and_run", None):
            self.btn_reset_and_run.setEnabled(False)
        self._countdown_active = True
        self._countdown_remaining = self._countdown_seconds
        self._countdown_tick()
        if self._countdown_active:
            self._countdown_timer.start(1000)

    def _countdown_tick(self) -> None:
        if not self._countdown_active:
            return
        if self._countdown_remaining > 0:
            self.lbl_countdown.setText(
                Strings.PREFLIGHT_COUNTDOWN.format(seconds=self._countdown_remaining)
            )
            self._countdown_remaining -= 1
        else:
            reset = self._pending_reset_statuses
            self._cancel_countdown()
            self._confirm(run_1_row=False, reset_statuses=reset)

    def _on_countdown_tick(self) -> None:
        self._countdown_tick()

    def _confirm(self, run_1_row: bool, reset_statuses: bool = False) -> None:
        self._cancel_countdown()
        # Last line of defence: never accept a range that still has blocking errors.
        if self._has_blocking_issues():
            return
        if self.rad_slow.isChecked():
            selected_speed = SpeedMode.SLOW
        elif self.rad_veryslow.isChecked():
            selected_speed = SpeedMode.VERY_SLOW
        else:
            selected_speed = SpeedMode.NORMAL

        opts = {
            "start_row": self.spin_start_row.value(),
            "speed": selected_speed,
            "skip_setup": self.chk_skip_setup.isChecked(),
            "skip_cleanup": self.chk_cleanup_checked(),
            "step_by_step": self.chk_step_by_step.isChecked(),
            "run_1_row": run_1_row,
            "end_row_index": self.spin_end_row.value(),
            # Start Run already counted down in this dialog; Run 1 Row has not.
            "countdown_seconds": float(self._countdown_seconds) if run_1_row else 0.0,
            "reset_statuses": reset_statuses,
        }
        self.confirmed_opts = opts
        self.run_confirmed.emit(opts)
        self.accept()

    def chk_cleanup_checked(self) -> bool:
        return self.chk_skip_cleanup.isChecked()

    def reject(self) -> None:
        self._cancel_countdown()
        super().reject()

    def closeEvent(self, event: Any) -> None:
        self._cancel_countdown()
        super().closeEvent(event)
