"""Always-on-top Floating Run Panel (Section 11.3 & 12.6).

Specifications:
- Does NOT steal keyboard/mouse focus from the active target ERP window.
- Repositions automatically if clicking targets overlap panel coordinates.
- Applies WDA_EXCLUDEFROMCAPTURE to avoid polluting screenshots and template matching.
- Displays live progress, pause/resume, stop, and emergency hotkey guidance.
"""

from __future__ import annotations

import ctypes
import os
from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from stepwise.engine.timing import SpeedMode

# Win32 Constants
WDA_EXCLUDEFROMCAPTURE = 0x00000011
WS_EX_NOACTIVATE = 0x08000000
GWL_EXSTYLE = -20


class FloatingRunPanel(QWidget):
    pause_clicked = Signal()
    resume_clicked = Signal()
    stop_clicked = Signal()
    next_step_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        icon_path = os.path.join(os.path.dirname(__file__), "stepwise.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._drag_pos: QPoint | None = None
        self._is_paused = False

        self.resize(320, 200)
        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #f8fafc;
                border-radius: 8px;
                font-family: "Segoe UI", sans-serif;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Title Bar
        title_layout = QHBoxLayout()
        self.lbl_title = QLabel("Stepwise ▶ Running")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #38bdf8;")
        self.lbl_speed = QLabel("Speed: Normal")
        self.lbl_speed.setStyleSheet("color: #94a3b8; font-size: 11px;")
        title_layout.addWidget(self.lbl_title)
        title_layout.addStretch()
        title_layout.addWidget(self.lbl_speed)
        layout.addLayout(title_layout)

        # Row Progress & Bar
        self.lbl_row = QLabel("Row 1 / 1")
        self.lbl_row.setStyleSheet("font-size: 12px; font-weight: 600;")
        layout.addWidget(self.lbl_row)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(True)
        self.prog_bar.setStyleSheet("""
            QProgressBar {
                background-color: #334155;
                border-radius: 4px;
                text-align: center;
                height: 14px;
                color: white;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.prog_bar)

        # Current Step Label
        self.lbl_step = QLabel("Initializing...")
        self.lbl_step.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        layout.addWidget(self.lbl_step)

        # Stats
        self.lbl_stats = QLabel("OK: 0  |  Failed: 0")
        self.lbl_stats.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.lbl_stats)

        # Controls
        btn_layout = QHBoxLayout()
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setStyleSheet("background-color: #d97706; color: white; padding: 4px 8px; font-weight: bold; border-radius: 4px;")
        self.btn_pause.clicked.connect(self._toggle_pause)

        self.btn_stop = QPushButton("■ Stop")
        self.btn_stop.setStyleSheet("background-color: #dc2626; color: white; padding: 4px 8px; font-weight: bold; border-radius: 4px;")
        self.btn_stop.clicked.connect(self.stop_clicked.emit)

        self.btn_next = QPushButton("Next ⏭")
        self.btn_next.setStyleSheet("background-color: #2563eb; color: white; padding: 4px 8px; font-weight: bold; border-radius: 4px;")
        self.btn_next.setVisible(False)
        self.btn_next.clicked.connect(self.next_step_clicked.emit)

        btn_layout.addWidget(self.btn_pause)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_next)
        layout.addLayout(btn_layout)

        # Hotkey note
        lbl_hotkey = QLabel("Emergency stop: F12")
        lbl_hotkey.setStyleSheet("color: #ef4444; font-size: 10px; text-align: center;")
        lbl_hotkey.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_hotkey)

        # Place initially at top-right
        self._position_top_right()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        self._apply_win32_attributes()

    def _apply_win32_attributes(self) -> None:
        """Apply capture exclusion and prevent window activation."""
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            # 1. Capture exclusion
            if hasattr(user32, "SetWindowDisplayAffinity"):
                user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)

            # 2. WS_EX_NOACTIVATE style
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
        except Exception:
            pass

    def _position_top_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            self.move(geom.width() - self.width() - 30, 40)

    def _position_top_left(self) -> None:
        self.move(30, 40)

    def ensure_not_overlapping(self, target_x: int, target_y: int) -> None:
        """Move panel away if target coordinate is inside the panel area."""
        rect = self.geometry()
        # Add safety margin
        if rect.adjusted(-20, -20, 20, 20).contains(target_x, target_y):
            # If currently on the right half, move left, else move right
            screen = QApplication.primaryScreen()
            if screen and self.x() > (screen.geometry().width() // 2):
                self._position_top_left()
            else:
                self._position_top_right()

    def update_progress(self, row: int, total: int, step_desc: str, ok_cnt: int, failed_cnt: int) -> None:
        self.lbl_row.setText(f"Row {row} / {total}")
        pct = int((row / max(1, total)) * 100)
        self.prog_bar.setValue(pct)
        self.lbl_step.setText(step_desc)
        self.lbl_stats.setText(f"OK: {ok_cnt}  |  Failed: {failed_cnt}")

    def set_speed_text(self, speed: SpeedMode) -> None:
        extra = f" (+{speed.extra_seconds}s)" if speed.extra_seconds > 0 else ""
        self.lbl_speed.setText(f"Speed: {speed.value}{extra}")

    def set_step_by_step(self, enabled: bool) -> None:
        self.btn_next.setVisible(enabled)

    def _toggle_pause(self) -> None:
        if not self._is_paused:
            self._is_paused = True
            self.btn_pause.setText("▶ Resume")
            self.lbl_title.setText("Stepwise ⏸ Paused")
            self.lbl_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #f59e0b;")
            self.pause_clicked.emit()
        else:
            self._is_paused = False
            self.btn_pause.setText("⏸ Pause")
            self.lbl_title.setText("Stepwise ▶ Running")
            self.lbl_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #38bdf8;")
            self.resume_clicked.emit()

    # Drag to reposition
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
