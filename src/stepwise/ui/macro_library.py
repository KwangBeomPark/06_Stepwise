"""Macro library panel for managing local and shared .swm files (Section 13.1).

Features:
- Folder-based macro listing with search filter
- Collaborative edit lock status indicators
- Create, duplicate, rename, and delete actions
"""

from __future__ import annotations

import os
import shutil

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from stepwise.core.models import Macro
from stepwise.core.package import save_package
from stepwise.services.lock import check_lock_status
from stepwise.ui.strings import Strings


class MacroLibraryPanel(QWidget):
    macro_selected = Signal(str)  # swm_path
    macro_created = Signal(str)

    def __init__(self, library_dir: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.library_dir = library_dir
        os.makedirs(self.library_dir, exist_ok=True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Title
        title_lbl = QLabel(Strings.LIBRARY_TITLE)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #1e293b;")
        layout.addWidget(title_lbl)

        # Search bar
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(Strings.SEARCH_MACROS)
        self.txt_search.textChanged.connect(self._filter_list)
        layout.addWidget(self.txt_search)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_new = QPushButton(Strings.NEW_MACRO)
        self.btn_new.clicked.connect(self._on_new_macro)
        btn_layout.addWidget(self.btn_new)

        self.btn_duplicate = QPushButton(Strings.DUPLICATE_MACRO)
        self.btn_duplicate.clicked.connect(self._on_duplicate_macro)
        btn_layout.addWidget(self.btn_duplicate)

        layout.addLayout(btn_layout)

        self.refresh_list()

    def set_library_dir(self, new_dir: str) -> None:
        """Update the library directory and refresh."""
        self.library_dir = new_dir
        os.makedirs(self.library_dir, exist_ok=True)
        self.refresh_list()

    def refresh_list(self) -> None:
        """Scan library folder and populate list."""
        self.list_widget.clear()
        if not os.path.exists(self.library_dir):
            return

        for fname in sorted(os.listdir(self.library_dir)):
            if fname.lower().endswith(".swm") or fname.lower().endswith(".json"):
                full_path = os.path.join(self.library_dir, fname)
                is_locked, lock_info, is_stale = check_lock_status(full_path)

                item = QListWidgetItem(fname)
                item.setData(Qt.UserRole, full_path)
                item.setForeground(QBrush(QColor("#0f172a")))

                if is_locked:
                    lock_desc = f"🔒 Locked by {lock_info.user}" if lock_info else "🔒 Locked"
                    item.setText(f"{fname} ({lock_desc})")
                    item.setForeground(QBrush(QColor("#dc2626")))

                self.list_widget.addItem(item)

    def _filter_list(self, query: str) -> None:
        q = query.strip().lower()
        for idx in range(self.list_widget.count()):
            it = self.list_widget.item(idx)
            it.setHidden(q not in it.text().lower())

    def _on_selection_changed(self) -> None:
        items = self.list_widget.selectedItems()
        if items:
            swm_path = items[0].data(Qt.UserRole)
            self.macro_selected.emit(swm_path)

    def _on_new_macro(self) -> None:
        name, ok = QInputDialog.getText(self, "New Macro", "Enter macro name:")
        if ok and name.strip():
            safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name.strip())
            swm_path = os.path.join(self.library_dir, f"{safe_name}.swm")
            macro = Macro(name=name.strip())
            save_package(macro, swm_path)
            self.refresh_list()
            self.macro_created.emit(swm_path)

    def _on_duplicate_macro(self) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            return
        orig_path = items[0].data(Qt.UserRole)
        base, ext = os.path.splitext(orig_path)
        new_path = f"{base}_Copy{ext}"
        shutil.copy2(orig_path, new_path)
        self.refresh_list()
