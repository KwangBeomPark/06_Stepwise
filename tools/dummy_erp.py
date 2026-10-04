"""Dummy ERP Desktop Application for End-to-End Testing (Section 16.2).

Features:
- Three input fields (Vendor, Amount, Note)
- Save button and visual "Saved OK" badge
- Real-time row log of submitted records
- Simulation toggles: network lag, error simulation
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class DummyErpApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Dummy ERP - Invoice Entry Test Bench")
        self.resize(550, 480)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # Title
        title_lbl = QLabel("ERP Vendor Invoice Entry Form")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        main_layout.addWidget(title_lbl)

        # Form
        form_layout = QFormLayout()
        form_layout.setSpacing(8)

        self.txt_vendor = QLineEdit()
        self.txt_vendor.setPlaceholderText("Enter vendor name (e.g. ACME Corp)")
        form_layout.addRow("Vendor Name:", self.txt_vendor)

        self.txt_amount = QLineEdit()
        self.txt_amount.setPlaceholderText("Enter amount (e.g. 1200)")
        form_layout.addRow("Invoice Amount:", self.txt_amount)

        self.txt_note = QLineEdit()
        self.txt_note.setPlaceholderText("Internal reference / notes")
        form_layout.addRow("Reference Note:", self.txt_note)

        main_layout.addLayout(form_layout)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Invoice")
        self.btn_save.setStyleSheet(
            "background-color: #2563eb; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px;"
        )
        self.btn_save.clicked.connect(self.on_save_clicked)

        self.btn_clear = QPushButton("Clear Fields")
        self.btn_clear.clicked.connect(self.clear_fields)

        self.chk_simulate_lag = QCheckBox("Simulate Slow Server (+0.5s)")

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(self.chk_simulate_lag)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # Status badge ("Saved OK")
        self.lbl_status = QLabel("Ready for entry")
        self.lbl_status.setStyleSheet("color: #64748b; font-style: italic;")
        main_layout.addWidget(self.lbl_status)

        # Saved records table
        lbl_history = QLabel("Submitted Records:")
        lbl_history.setStyleSheet("font-weight: bold; color: #334155; margin-top: 10px;")
        main_layout.addWidget(lbl_history)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Vendor", "Amount", "Note"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.table)

    def clear_fields(self) -> None:
        self.txt_vendor.clear()
        self.txt_amount.clear()
        self.txt_note.clear()
        self.txt_vendor.setFocus()
        self.lbl_status.setText("Fields cleared.")
        self.lbl_status.setStyleSheet("color: #64748b;")

    def on_save_clicked(self) -> None:
        vendor = self.txt_vendor.text().strip()
        amount = self.txt_amount.text().strip()
        note = self.txt_note.text().strip()

        if not vendor or not amount:
            self.lbl_status.setText("Error: Vendor and Amount cannot be empty!")
            self.lbl_status.setStyleSheet("color: #dc2626; font-weight: bold;")
            return

        delay_ms = 500 if self.chk_simulate_lag.isChecked() else 50
        self.lbl_status.setText("Saving to database...")
        self.lbl_status.setStyleSheet("color: #d97706;")

        QTimer.singleShot(delay_ms, lambda: self._complete_save(vendor, amount, note))

    def _complete_save(self, vendor: str, amount: str, note: str) -> None:
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)
        self.table.setItem(row_idx, 0, QTableWidgetItem(vendor))
        self.table.setItem(row_idx, 1, QTableWidgetItem(amount))
        self.table.setItem(row_idx, 2, QTableWidgetItem(note))

        # Show distinct "Saved OK" badge that can be targeted by image verify
        self.lbl_status.setText("Saved OK")
        self.lbl_status.setStyleSheet("color: #16a34a; font-weight: bold; font-size: 14px;")

        self.clear_fields()
        self.lbl_status.setText("Saved OK")
        self.lbl_status.setStyleSheet("color: #16a34a; font-weight: bold; font-size: 14px;")


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = DummyErpApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
