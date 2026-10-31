"""Execution Summary Dialog (Section 12.7).

Displays:
- Done, Failed, Interrupted, and Skipped counts
- Elapsed execution time and row rate
- Failure details with direct buttons to open screenshot and results CSV
"""

from __future__ import annotations

import csv
import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from stepwise.engine.results import RESULTS_COLUMNS
from stepwise.engine.runner import RunSummary
from stepwise.ui.strings import Strings
from stepwise.ui.theme import get_theme_tokens


class RunSummaryDialog(QDialog):
    jump_to_step_requested = Signal(str)

    def __init__(
        self,
        summary: RunSummary,
        results_csv_path: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stepwise — Execution Summary")
        self.resize(480, 440)

        self.summary = summary
        results_csv_path = (
            results_csv_path or summary.pending_results_path or summary.results_csv_path
        )
        self.results_csv_path = results_csv_path
        t = get_theme_tokens()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header Title
        title_text = (
            "Run Completed Successfully"
            if summary.failed_count == 0 and not summary.interrupted
            else "Run Stopped"
        )
        title_color = (
            t["status_ok"]
            if summary.failed_count == 0 and not summary.interrupted
            else t["status_fail"]
        )
        lbl_title = QLabel(title_text)
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {title_color};")
        layout.addWidget(lbl_title)

        # Stats Group
        box_stats = QGroupBox("Execution Statistics")
        form_stats = QFormLayout(box_stats)
        form_stats.addRow("Macro Name:", QLabel(summary.macro_name))
        form_stats.addRow("Duration:", QLabel(f"{summary.duration_sec} seconds"))
        form_stats.addRow("Total Rows:", QLabel(str(summary.total_rows)))
        form_stats.addRow("Done Rows:", QLabel(f"<b>{summary.done_count}</b>"))
        form_stats.addRow(
            "Failed Rows:",
            QLabel(f'<span style="color:{t["status_fail"]};"><b>{summary.failed_count}</b></span>'),
        )
        form_stats.addRow("Interrupted Rows:", QLabel(str(summary.interrupted_count)))
        layout.addWidget(box_stats)

        if summary.pending_results_path:
            warning = QLabel(
                Strings.RESULTS_MEMORY_WARNING
                if summary.persistence_errors
                else Strings.RESULTS_WARNING
            )
            warning.setWordWrap(True)
            layout.addWidget(warning)

        # Failure Details (if any)
        if summary.failure:
            box_fail = QGroupBox("Failure Incident")
            layout_fail = QVBoxLayout(box_fail)

            lbl_reason = QLabel(summary.failure.formatted_reason())
            lbl_reason.setWordWrap(True)
            lbl_reason.setStyleSheet(f"color: {t['status_fail']}; font-weight: 500;")
            layout_fail.addWidget(lbl_reason)

            h_fail_btns = QHBoxLayout()
            if summary.failure.step_id:
                btn_jump = QPushButton("🎯 Jump to Failed Step")
                btn_jump.clicked.connect(lambda: self._on_jump_to_step(summary.failure.step_id))
                h_fail_btns.addWidget(btn_jump)

            if summary.screenshot_path and os.path.exists(summary.screenshot_path):
                btn_shot = QPushButton("📷 Open Failure Screenshot")
                btn_shot.clicked.connect(lambda: self._open_file(summary.screenshot_path))
                h_fail_btns.addWidget(btn_shot)

            if h_fail_btns.count() > 0:
                layout_fail.addLayout(h_fail_btns)

            layout.addWidget(box_fail)

        # Buttons
        btn_layout = QHBoxLayout()
        if summary.buffered_results:
            btn_export = QPushButton(Strings.EXPORT_BUFFERED_RESULTS)
            btn_export.clicked.connect(self._export_buffered_results)
            btn_layout.addWidget(btn_export)
        if results_csv_path and os.path.exists(results_csv_path):
            btn_csv = QPushButton("Open Results CSV")
            btn_csv.clicked.connect(lambda: self._open_file(results_csv_path))
            btn_layout.addWidget(btn_csv)

        btn_layout.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _export_buffered_results(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, Strings.EXPORT_BUFFERED_RESULTS, "", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=RESULTS_COLUMNS)
                writer.writeheader()
                writer.writerows(record.to_dict() for record in self.summary.buffered_results)
                output.flush()
                os.fsync(output.fileno())
        except OSError as e:
            QMessageBox.warning(self, Strings.SAVE_ERROR_TITLE, str(e))

    def _on_jump_to_step(self, step_id: str | None) -> None:
        if step_id:
            self.jump_to_step_requested.emit(step_id)
            self.accept()

    def _open_file(self, filepath: str) -> None:
        try:
            os.startfile(filepath)
        except Exception as e:
            print(f"Error opening file {filepath}: {e}")
