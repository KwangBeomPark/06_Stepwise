"""Data integration and preview panel with Status column (Section 10.3 & 12.5).

Features:
- Excel (.xlsx) and CSV table viewer
- Real-time row Status updates (Pending / Done / Failed / Interrupted / Skipped)
- Row context menu (Retry, Skip, Mark as Done, Run only this row)
- Header click emits variable placeholder for text input
"""

from __future__ import annotations

import os

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stepwise.services.data_source import read_data_file
from stepwise.ui.strings import Strings


class DataPanel(QWidget):
    data_loaded = Signal(str, list, list)  # (file_path, headers, rows)
    insert_variable_requested = Signal(str)  # "{ColumnName}"
    row_status_override = Signal(int, str)  # (row_number, new_status)
    run_only_row_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_filepath: str | None = None
        self._headers: list[str] = []
        self._rows: list[dict[str, str]] = []
        self._row_numbers: list[int] = []
        self._row_statuses: dict[int, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header controls
        top_layout = QHBoxLayout()
        self.btn_select_file = QPushButton(Strings.SELECT_DATA_FILE)
        self.btn_select_file.clicked.connect(self._on_choose_file)
        self.lbl_info = QLabel(Strings.NO_DATA)
        self.lbl_info.setStyleSheet("color: #64748b; font-weight: 500;")

        top_layout.addWidget(self.btn_select_file)
        top_layout.addWidget(self.lbl_info)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Chips container for quick column variable insertion
        self.chips_widget = QWidget()
        self.chips_layout = QHBoxLayout(self.chips_widget)
        self.chips_layout.setContentsMargins(0, 2, 0, 2)
        self.chips_layout.setSpacing(6)
        self.lbl_chips_title = QLabel("Insert Column Variable:")
        self.lbl_chips_title.setStyleSheet("font-weight: bold; color: #475569;")
        self.chips_layout.addWidget(self.lbl_chips_title)
        self.chips_widget.hide()
        layout.addWidget(self.chips_widget)

        # Table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        layout.addWidget(self.table)

    def _on_choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Data File", "", "Data Files (*.xlsx *.csv);;Excel Files (*.xlsx);;CSV Files (*.csv)"
        )
        if path:
            self.load_file(path)

    def load_file(self, filepath: str) -> None:
        """Load xlsx or csv file into table."""
        try:
            headers, rows, row_nums = read_data_file(filepath)
            self._current_filepath = filepath
            self._headers = headers
            self._rows = rows
            self._row_numbers = row_nums
            self._row_statuses.clear()

            self._rebuild_table()
            self._rebuild_chips()
            self.lbl_info.setText(f"{os.path.basename(filepath)} ({len(rows)} rows)")
            self.data_loaded.emit(filepath, headers, rows)
        except Exception as e:
            self.lbl_info.setText(f"Error loading file: {e}")

    def _rebuild_chips(self) -> None:
        """Create clickable chip buttons for each column header."""
        # Clear existing chips except the title label
        while self.chips_layout.count() > 1:
            item = self.chips_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        for header in self._headers:
            btn = QPushButton(f"+ {{{header}}}")
            btn.setStyleSheet(
                "background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; "
                "border-radius: 4px; padding: 2px 8px; font-weight: 500;"
            )
            btn.setToolTip(f"Click to insert {{{header}}} into the current text field")
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

            # Col 1: Status
            status_text = self._row_statuses.get(r_num, Strings.STATUS_PENDING)
            item_status = QTableWidgetItem(status_text)
            self._apply_status_style(item_status, status_text)
            self.table.setItem(idx, 1, item_status)

            # Rest of data columns
            for col_idx, col_name in enumerate(self._headers):
                val = row.get(col_name, "")
                self.table.setItem(idx, col_idx + 2, QTableWidgetItem(val))

        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

    def update_row_status(self, row_number: int, status: str) -> None:
        """Update live status for a row."""
        self._row_statuses[row_number] = status
        # Find table row
        for idx, r_num in enumerate(self._row_numbers):
            if r_num == row_number:
                item = self.table.item(idx, 1)
                if item:
                    item.setText(status)
                    self._apply_status_style(item, status)
                break

    def _apply_status_style(self, item: QTableWidgetItem, status: str) -> None:
        if status == Strings.STATUS_DONE or "Done" in status:
            item.setForeground(QColor("#16a34a"))  # Green
        elif status == Strings.STATUS_FAILED or "Failed" in status:
            item.setForeground(QColor("#dc2626"))  # Red
        elif status == Strings.STATUS_RUNNING or "Running" in status:
            item.setForeground(QColor("#2563eb"))  # Blue
        elif status == Strings.STATUS_INTERRUPTED or "Interrupted" in status:
            item.setForeground(QColor("#d97706"))  # Amber
        else:
            item.setForeground(QColor("#64748b"))  # Gray

    def _on_header_clicked(self, logical_index: int) -> None:
        if logical_index >= 2:
            col_name = self._headers[logical_index - 2]
            self.insert_variable_requested.emit(f"{{{col_name}}}")

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

        action = menu.exec(self.table.mapToGlobal(pos))
        if action == act_retry:
            self.update_row_status(row_num, Strings.STATUS_PENDING)
            self.row_status_override.emit(row_num, "Pending")
        elif action == act_skip:
            self.update_row_status(row_num, Strings.STATUS_SKIPPED)
            self.row_status_override.emit(row_num, "Skipped")
        elif action == act_done:
            self.update_row_status(row_num, Strings.STATUS_DONE)
            self.row_status_override.emit(row_num, "Done")
        elif action == act_run_only:
            self.run_only_row_requested.emit(row_num)
