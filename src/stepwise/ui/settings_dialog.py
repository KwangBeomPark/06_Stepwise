"""Application settings dialog implementing Section 12.8 specifications."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    def __init__(self, settings_dict: dict[str, object] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stepwise Settings")
        self.resize(520, 420)

        self._settings = dict(settings_dict or {})

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: General
        tab_gen = QWidget()
        layout_gen = QFormLayout(tab_gen)

        h_lib = QHBoxLayout()
        self.txt_lib_dir = QLineEdit(str(self._settings.get("library_dir", "macros")))
        btn_lib = QPushButton("Browse...")
        btn_lib.clicked.connect(lambda: self._browse_dir(self.txt_lib_dir))
        h_lib.addWidget(self.txt_lib_dir)
        h_lib.addWidget(btn_lib)
        layout_gen.addRow("Library Folder:", h_lib)

        h_res = QHBoxLayout()
        self.txt_res_dir = QLineEdit(str(self._settings.get("results_dir", "results")))
        btn_res = QPushButton("Browse...")
        btn_res.clicked.connect(lambda: self._browse_dir(self.txt_res_dir))
        h_res.addWidget(self.txt_res_dir)
        h_res.addWidget(btn_res)
        layout_gen.addRow("Results Folder:", h_res)

        self.spin_countdown = QSpinBox()
        self.spin_countdown.setRange(0, 30)
        self.spin_countdown.setValue(int(self._settings.get("countdown_seconds", 5)))
        layout_gen.addRow("Countdown (seconds):", self.spin_countdown)

        self.tabs.addTab(tab_gen, "General")

        # Tab 2: Hotkeys
        tab_keys = QWidget()
        layout_keys = QFormLayout(tab_keys)

        self.txt_hk_stop = QLineEdit("F12")
        self.txt_hk_pause = QLineEdit("F11")
        self.txt_hk_pick = QLineEdit("F8")
        self.txt_hk_capture = QLineEdit("F9")

        layout_keys.addRow("Emergency Stop:", self.txt_hk_stop)
        layout_keys.addRow("Pause / Resume:", self.txt_hk_pause)
        layout_keys.addRow("Pick Coordinates:", self.txt_hk_pick)
        layout_keys.addRow("Capture Image:", self.txt_hk_capture)

        self.tabs.addTab(tab_keys, "Hotkeys")

        # Tab 3: Timing & Image
        tab_timing = QWidget()
        layout_timing = QFormLayout(tab_timing)

        self.spin_wait_before = QDoubleSpinBox()
        self.spin_wait_before.setRange(0.0, 60.0)
        self.spin_wait_before.setValue(float(self._settings.get("default_wait_before", 0.2)))
        layout_timing.addRow("Default wait before (s):", self.spin_wait_before)

        self.spin_poll = QDoubleSpinBox()
        self.spin_poll.setRange(0.05, 5.0)
        self.spin_poll.setValue(float(self._settings.get("poll_interval", 0.25)))
        layout_timing.addRow("Image poll interval (s):", self.spin_poll)

        self.cmb_conf = QComboBox()
        self.cmb_conf.addItems(["Strict (0.95)", "Normal (0.90)", "Loose (0.85)"])
        self.cmb_conf.setCurrentIndex(0)
        layout_timing.addRow("Confidence Preset:", self.cmb_conf)

        self.tabs.addTab(tab_timing, "Timing & Image")

        # Tab 4: About
        tab_about = QWidget()
        layout_about = QVBoxLayout(tab_about)
        layout_about.setSpacing(10)
        lbl_about = QLabel("<b>Stepwise v0.1.0</b><br>Windows Data-Driven Macro Automation Tool.<br>Enterprise-ready, Non-admin execution.")
        lbl_about.setTextFormat(Qt.RichText)
        layout_about.addWidget(lbl_about)

        btn_logs = QPushButton("Open Logs Folder")
        btn_logs.clicked.connect(self._open_logs)
        layout_about.addWidget(btn_logs)
        layout_about.addStretch()

        self.tabs.addTab(tab_about, "About")

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self._on_save)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        main_layout.addLayout(btn_layout)

    def _browse_dir(self, line_edit: QLineEdit) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select Directory", line_edit.text())
        if d:
            line_edit.setText(d)

    def _open_logs(self) -> None:
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        try:
            os.startfile(log_dir)
        except Exception:
            pass

    def _on_save(self) -> None:
        self._settings["library_dir"] = self.txt_lib_dir.text().strip()
        self._settings["results_dir"] = self.txt_res_dir.text().strip()
        self._settings["countdown_seconds"] = self.spin_countdown.value()
        self._settings["default_wait_before"] = self.spin_wait_before.value()
        self._settings["poll_interval"] = self.spin_poll.value()
        self.accept()

    def get_settings(self) -> dict[str, object]:
        return self._settings
