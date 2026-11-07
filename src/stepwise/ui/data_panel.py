"""Data integration and preview panel with Status column (Section 10.3 & 12.5).

Features:
- Excel (.xlsx) and CSV table viewer
- Real-time row Status updates (Pending / Done / Failed / Interrupted / Skipped)
- Canonical status code decoupling from localized display text
- Row context menu (Retry, Skip, Mark as Done, Run only this row)
- Header click emits variable placeholder for text input
- Drag & drop of a single .xlsx/.csv file, empty-state hint and reconnect button
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stepwise.services.data_source import export_execution_results_xlsx, read_data_file
from stepwise.ui.strings import Strings, format_status_display, normalize_status_code
from stepwise.ui.theme import get_theme_tokens

DATA_FILE_EXTENSIONS = (".xlsx", ".csv")


class DataPanel(QWidget):
    data_loaded = Signal(str, list, list, list)  # (file_path, headers, rows, row_numbers)
    insert_variable_requested = Signal(str)  # "{ColumnName}"
    row_status_override = Signal(int, str)  # (row_number, new_status)
    run_only_row_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_filepath: str | None = None
        self._headers: list[str] = []
        self._rows: list[dict[str, str]] = []
        self._row_numbers: list[int] = []
        # Stores canonical status code ('Pending', 'Done', 'Failed', 'Running', 'Interrupted', 'Skipped')
        self._row_statuses: dict[int, str] = {}
        # Stores detail metadata per row: {"timestamp": "...", "reason": "..."}
        self._row_details: dict[int, dict[str, str]] = {}
        self._reconnect_path: str | None = None
        self._running = False
        # Optional hook run before the file dialog opens (e.g. to cancel pending input).
        self.before_prompt: Callable[[], None] | None = None
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header controls
        top_layout = QHBoxLayout()
        self.btn_select_file = QPushButton(Strings.SELECT_DATA_FILE)
        self.btn_select_file.setToolTip(Strings.Tooltips.CHOOSE_DATA_FILE)
        self.btn_select_file.clicked.connect(self._on_choose_file)
        self.btn_reconnect = QPushButton()
        self.btn_reconnect.clicked.connect(self._on_reconnect_clicked)
        self.btn_reconnect.hide()
        self.btn_export = QPushButton(f"📊 {Strings.EXPORT_RESULTS}")
        self.btn_export.setToolTip(Strings.EXPORT_RESULTS)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._on_export_clicked)
        self.lbl_info = QLabel(Strings.NO_DATA)

        top_layout.addWidget(self.btn_select_file)
        top_layout.addWidget(self.btn_reconnect)
        top_layout.addWidget(self.btn_export)
        top_layout.addWidget(self.lbl_info)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Chips container for quick column variable insertion
        self.chips_widget = QWidget()
        self.chips_layout = QHBoxLayout(self.chips_widget)
        self.chips_layout.setContentsMargins(0, 2, 0, 2)
        self.chips_layout.setSpacing(6)
        self.lbl_chips_title = QLabel(Strings.INSERT_VARIABLE_LABEL)
        self.chips_layout.addWidget(self.lbl_chips_title)
        self.chips_widget.hide()
        layout.addWidget(self.chips_widget)

        # Empty-state hint (page 0) and table (page 1)
        self.stack = QStackedWidget()
        self.lbl_empty = QLabel(Strings.DATA_DROP_HINT)
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setWordWrap(True)
        self.stack.addWidget(self.lbl_empty)

        # Table (read-only preview: the source file is never modified)
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.stack.addWidget(self.table)
        layout.addWidget(self.stack)

        self._apply_theme_styles()

    def _apply_theme_styles(self) -> None:
        t = get_theme_tokens()
        self.lbl_info.setStyleSheet(f"color: {t['text_muted']}; font-weight: 500;")
        self.lbl_chips_title.setStyleSheet(f"font-weight: bold; color: {t['text_muted']};")
        self.lbl_empty.setStyleSheet(
            f"color: {t['text_secondary']}; font-size: 14px; padding: 16px; "
            f"border: 2px dashed {t['chip_border']}; border-radius: 8px;"
        )

    def retranslate_ui(self) -> None:
        """Update labels, chips, and table status strings on language/theme switch."""
        self.btn_select_file.setText(Strings.SELECT_DATA_FILE)
        self.btn_select_file.setToolTip(Strings.Tooltips.CHOOSE_DATA_FILE)
        self.btn_export.setText(f"📊 {Strings.EXPORT_RESULTS}")
        self.btn_export.setToolTip(Strings.EXPORT_RESULTS)
        self.lbl_chips_title.setText(Strings.INSERT_VARIABLE_LABEL)
        self.lbl_empty.setText(Strings.DATA_DROP_HINT)
        self._apply_theme_styles()
        self.set_reconnect_hint(self._reconnect_path)
        if not self._current_filepath:
            self.lbl_info.setText(Strings.NO_DATA)
        else:
            self.lbl_info.setText(self._loaded_summary())
        if self._headers:
            self._rebuild_chips()
            self._rebuild_table()

    def set_running(self, running: bool) -> None:
        """Lock the data source while a run uses it (drop, choose and reconnect)."""
        self._running = running
        self.btn_select_file.setEnabled(not running)
        self.btn_reconnect.setEnabled(not running)
        if not running and self._current_filepath:
            self.lbl_info.setText(self._loaded_summary())

    def _on_choose_file(self) -> None:
        if self._running:
            self.lbl_info.setText(Strings.DATA_LOCKED_RUNNING)
            return
        if self.before_prompt is not None:
            self.before_prompt()
        path, _ = QFileDialog.getOpenFileName(
            self,
            Strings.SELECT_DATA_FILE,
            "",
            "Data Files (*.xlsx *.csv);;Excel Files (*.xlsx);;CSV Files (*.csv)",
        )
        if path:
            self.load_file(path)

    def load_file(self, filepath: str) -> bool:
        """Load xlsx or csv file into table. A failure keeps the previous data."""
        name = os.path.basename(filepath)
        try:
            headers, rows, row_nums = read_data_file(filepath)
        except Exception as e:
            if isinstance(e, PermissionError):
                message = Strings.DATA_LOAD_PERMISSION_ERROR.format(file=name)
            else:
                message = Strings.DATA_LOAD_ERROR.format(file=name, error=e)
            status = Strings.DATA_LOAD_FAILED_STATUS.format(file=name)
            if self._current_filepath:
                status += "  " + Strings.DATA_KEEP_PREVIOUS.format(
                    file=os.path.basename(self._current_filepath)
                )
            self.lbl_info.setText(status)
            if self.before_prompt is not None:
                self.before_prompt()
            QMessageBox.warning(self, Strings.DATA_LOAD_ERROR_TITLE, message)
            return False

        self._current_filepath = filepath
        self._headers = headers
        self._rows = rows
        self._row_numbers = row_nums
        self._row_statuses.clear()
        self._row_details.clear()
        self.btn_export.setEnabled(len(rows) > 0)

        self._rebuild_table()
        self._rebuild_chips()
        self.set_reconnect_hint(None)
        self.lbl_info.setText(self._loaded_summary())
        self.data_loaded.emit(filepath, headers, rows, self._row_numbers)
        return True

    def _loaded_summary(self) -> str:
        return Strings.DATA_LOADED_SUMMARY.format(
            file=os.path.basename(self._current_filepath or ""),
            rows=len(self._rows),
            cols=len(self._headers),
        )

    def set_reconnect_hint(self, filepath: str | None) -> None:
        """Offer a one-click reconnect to the last data file; never loads silently."""
        self._reconnect_path = filepath
        if filepath and not self._current_filepath and os.path.isfile(filepath):
            self.btn_reconnect.setText(
                Strings.DATA_RECONNECT.format(file=os.path.basename(filepath))
            )
            self.btn_reconnect.setToolTip(filepath)
            self.btn_reconnect.show()
        else:
            self.btn_reconnect.hide()

    def _on_reconnect_clicked(self) -> None:
        if self._running:
            return
        if self._reconnect_path:
            self.load_file(self._reconnect_path)

    @staticmethod
    def _dropped_data_file(event: QDragEnterEvent | QDropEvent) -> str | None:
        mime = event.mimeData()
        urls = mime.urls() if mime.hasUrls() else []
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = urls[0].toLocalFile()
        if not path.lower().endswith(DATA_FILE_EXTENSIONS):
            return None
        return path

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if not self._running and self._dropped_data_file(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if self._running:
            self.lbl_info.setText(Strings.DATA_LOCKED_RUNNING)
            event.ignore()
            return
        path = self._dropped_data_file(event)
        if not path:
            self.lbl_info.setText(Strings.DATA_DROP_UNSUPPORTED)
            event.ignore()
            return
        event.acceptProposedAction()
        self.load_file(path)

    def _rebuild_chips(self) -> None:
        """Create clickable chip buttons for each column header."""
        t = get_theme_tokens()
        while self.chips_layout.count() > 1:
            item = self.chips_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        for header in self._headers:
            btn = QPushButton(f"+ {{{header}}}")
            btn.setStyleSheet(
                f"background-color: {t['chip_bg']}; color: {t['chip_fg']}; "
                f"border: 1px solid {t['chip_border']}; "
                "border-radius: 4px; padding: 2px 8px; font-weight: 600;"
            )
            btn.setToolTip(
                Strings.Tooltips.card(
                    f"{{{header}}}",
                    f"Click to insert {{{header}}} variable into the active text field.",
                )
            )
            btn.clicked.connect(lambda _, h=header: self.insert_variable_requested.emit(f"{{{h}}}"))
            self.chips_layout.addWidget(btn)

        self.chips_layout.addStretch()
        self.chips_widget.show()

    def _rebuild_table(self) -> None:
        self.table.clear()
        col_names = ["Row", "Status"] + self._headers
        self.table.setColumnCount(len(col_names))
        self.table.setHorizontalHeaderLabels(col_names)
        self.table.setRowCount(len(self._rows))

        for idx, row in enumerate(self._rows):
            r_num = self._row_numbers[idx]
            # Col 0: Row number
            self.table.setItem(idx, 0, QTableWidgetItem(str(r_num)))

            # Col 1: Status (display localized label, style by canonical status code)
            canonical_status = self._row_statuses.get(r_num, "Pending")
            display_text = format_status_display(canonical_status)
            item_status = QTableWidgetItem(display_text)
            item_status.setData(Qt.ItemDataRole.UserRole, canonical_status)
            self._apply_status_style(item_status, canonical_status)
            self.table.setItem(idx, 1, item_status)

            # Rest of data columns
            for col_idx, col_name in enumerate(self._headers):
                val = row.get(col_name, "")
                self.table.setItem(idx, col_idx + 2, QTableWidgetItem(val))

        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.stack.setCurrentWidget(self.table)

    def get_failed_row_numbers(self) -> list[int]:
        """Return list of row numbers whose current canonical status is 'Failed'."""
        return [
            r_num
            for r_num, status in self._row_statuses.items()
            if normalize_status_code(status) == "Failed"
        ]

    def get_excluded_row_numbers(self) -> set[int]:
        """Return set of row numbers that are marked Skipped or Done and should not be executed."""
        return {
            r_num
            for r_num, status in self._row_statuses.items()
            if normalize_status_code(status) in ("Skipped", "Done")
        }

    def get_row_statuses(self) -> dict[int, str]:
        """Return shallow copy of all tracked row statuses."""
        return dict(self._row_statuses)

    def update_row_status(
        self,
        row_number: int,
        status: str,
        reason: str = "",
        timestamp: str = "",
    ) -> None:
        """Update live status for a row using canonical status code while showing localized text."""
        canonical = normalize_status_code(status)
        self._row_statuses[row_number] = canonical

        # Record completion timestamp and failure reason when row reaches terminal or execution state
        if canonical in ("Done", "Failed", "Interrupted", "Skipped") or reason or timestamp:
            dt = self._row_details.setdefault(row_number, {})
            dt["timestamp"] = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if reason:
                dt["reason"] = reason
            elif canonical == "Done":
                dt["reason"] = ""

        display_text = format_status_display(canonical)
        for idx, r_num in enumerate(self._row_numbers):
            if r_num == row_number:
                item = self.table.item(idx, 1)
                if item:
                    item.setText(display_text)
                    item.setData(Qt.ItemDataRole.UserRole, canonical)
                    self._apply_status_style(item, canonical)
                break

    def record_row_detail(
        self,
        row_number: int,
        reason: str = "",
        timestamp: str = "",
    ) -> None:
        """Record or update execution detail metadata (e.g. error message) for a row."""
        dt = self._row_details.setdefault(row_number, {})
        if timestamp:
            dt["timestamp"] = timestamp
        if reason:
            dt["reason"] = reason

    def get_row_details(self) -> dict[int, dict[str, str]]:
        """Return shallow copy of all tracked row detail metadata."""
        return {k: dict(v) for k, v in self._row_details.items()}

    def _apply_status_style(self, item: QTableWidgetItem, status: str) -> None:
        t = get_theme_tokens()
        canonical = normalize_status_code(status)
        if canonical == "Done":
            item.setForeground(QColor(t["status_ok"]))
        elif canonical == "Failed":
            item.setForeground(QColor(t["status_fail"]))
        elif canonical == "Running":
            item.setForeground(QColor(t["status_run"]))
        elif canonical == "Interrupted":
            item.setForeground(QColor(t["status_warn"]))
        else:
            item.setForeground(QColor(t["text_muted"]))

    def _on_header_clicked(self, logical_index: int) -> None:
        if logical_index >= 2:
            col_name = self._headers[logical_index - 2]
            self.insert_variable_requested.emit(f"{{{col_name}}}")

    def reset_all_statuses(self) -> None:
        """Reset all row statuses back to blank / Pending."""
        self._row_statuses.clear()
        self._row_details.clear()
        for idx in range(len(self._row_numbers)):
            item = self.table.item(idx, 1)
            if item:
                item.setText("")
                item.setData(Qt.ItemDataRole.UserRole, "Pending")

    def export_results(self, output_filepath: str | None = None) -> str:
        """Export current execution results to a new Excel file. Returns saved path."""
        if not self._rows:
            return ""
        return export_execution_results_xlsx(
            headers=self._headers,
            rows=self._rows,
            row_numbers=self._row_numbers,
            row_statuses=self._row_statuses,
            source_filepath=self._current_filepath,
            output_filepath=output_filepath,
            row_details=self._row_details,
        )

    def _on_export_clicked(self) -> None:
        if not self._rows:
            QMessageBox.information(self, Strings.EXPORT_RESULTS, Strings.EXPORT_NO_DATA)
            return

        source_stem = os.path.splitext(os.path.basename(self._current_filepath or "data"))[0]
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{source_stem}_결과_{now_str}.xlsx"
        base_dir = os.path.dirname(self._current_filepath) if self._current_filepath else ""
        default_path = os.path.join(base_dir, default_filename) if base_dir else default_filename

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            Strings.EXPORT_RESULTS,
            default_path,
            "Excel Files (*.xlsx);;All Files (*)",
        )
        if not file_path:
            return

        try:
            saved_path = self.export_results(output_filepath=file_path)
            QMessageBox.information(
                self,
                Strings.EXPORT_SUCCESS_TITLE,
                Strings.EXPORT_SUCCESS_MSG.format(path=saved_path),
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                Strings.EXPORT_ERROR_TITLE,
                Strings.EXPORT_ERROR_MSG.format(error=e),
            )

    def _show_context_menu(self, pos: QPoint) -> None:
        item = self.table.itemAt(pos)
        if not item:
            return
        table_row = item.row()
        row_num = self._row_numbers[table_row]

        menu = QMenu(self)
        act_retry = menu.addAction(Strings.RETRY_ROW)
        act_skip = menu.addAction(Strings.SKIP_ROW)
        act_done = menu.addAction(Strings.MARK_DONE)
        menu.addSeparator()
        act_run_only = menu.addAction(Strings.RUN_ONLY_THIS_ROW)
        menu.addSeparator()
        act_reset_all = menu.addAction(Strings.RESET_ALL_STATUSES)
        menu.addSeparator()
        act_export = menu.addAction(f"📊 {Strings.EXPORT_RESULTS}")

        action = menu.exec(self.table.mapToGlobal(pos))
        if action == act_retry:
            self.update_row_status(row_num, "Pending")
            self.row_status_override.emit(row_num, "Pending")
        elif action == act_skip:
            self.update_row_status(row_num, "Skipped")
            self.row_status_override.emit(row_num, "Skipped")
        elif action == act_done:
            self.update_row_status(row_num, "Done")
            self.row_status_override.emit(row_num, "Done")
        elif action == act_run_only:
            self.run_only_row_requested.emit(row_num)
        elif action == act_export:
            self._on_export_clicked()
        elif action == act_reset_all:
            reply = QMessageBox.question(
                self,
                Strings.RESET_ALL_STATUSES_CONFIRM_TITLE,
                Strings.RESET_ALL_STATUSES_CONFIRM_MSG,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.reset_all_statuses()
                self.row_status_override.emit(-1, "ResetAll")
