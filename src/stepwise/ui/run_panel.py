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
from stepwise.ui.strings import Strings

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
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        icon_path = os.path.join(os.path.dirname(__file__), "stepwise.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._drag_pos: QPoint | None = None
        self._is_paused = False
        self._speed: SpeedMode = SpeedMode.NORMAL
        self._progress: tuple[int, int, int, int] = (1, 1, 0, 0)  # row, total, ok, failed

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
        self.lbl_title = QLabel(Strings.RUN_PANEL_RUNNING)
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #38bdf8;")
        self.lbl_speed = QLabel()
        self.lbl_speed.setStyleSheet("color: #94a3b8; font-size: 11px;")
        title_layout.addWidget(self.lbl_title)
        title_layout.addStretch()
        title_layout.addWidget(self.lbl_speed)
        layout.addLayout(title_layout)

        # Row Progress & Bar
        self.lbl_row = QLabel()
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
        self.lbl_step = QLabel(Strings.RUN_PANEL_INIT)
        self.lbl_step.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        layout.addWidget(self.lbl_step)

        # Stats
        self.lbl_stats = QLabel()
        self.lbl_stats.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.lbl_stats)

        # Controls
        btn_layout = QHBoxLayout()
        self.btn_pause = QPushButton()
        self.btn_pause.setStyleSheet(
            "background-color: #d97706; color: white; padding: 4px 8px; font-weight: bold; border-radius: 4px;"
        )
        self.btn_pause.clicked.connect(self._toggle_pause)

        self.btn_stop = QPushButton()
        self.btn_stop.setStyleSheet(
            "background-color: #dc2626; color: white; padding: 4px 8px; font-weight: bold; border-radius: 4px;"
        )
        self.btn_stop.clicked.connect(self.stop_clicked.emit)

        self.btn_next = QPushButton()
        self.btn_next.setStyleSheet(
            "background-color: #2563eb; color: white; padding: 4px 8px; font-weight: bold; border-radius: 4px;"
        )
        self.btn_next.setVisible(False)
        self.btn_next.clicked.connect(self.next_step_clicked.emit)

        btn_layout.addWidget(self.btn_pause)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_next)
        layout.addLayout(btn_layout)

        # Emergency stop badge: the one thing a user must find instantly.
        self.lbl_hotkey = QLabel()
        self.lbl_hotkey.setObjectName("f12_badge")
        self.lbl_hotkey.setStyleSheet(
            "background-color: #dc2626; color: white; font-size: 13px; font-weight: bold; "
            "border: 2px solid #fca5a5; border-radius: 6px; padding: 5px 10px;"
        )
        self.lbl_hotkey.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_hotkey)

        self.retranslate_ui()

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

    def retranslate_ui(self) -> None:
        """Re-apply labels in the active language (also used at construction)."""
        self.lbl_title.setText(
            Strings.RUN_PANEL_PAUSED if self._is_paused else Strings.RUN_PANEL_RUNNING
        )
        self.btn_pause.setText(f"▶ {Strings.RESUME}" if self._is_paused else f"⏸ {Strings.PAUSE}")
        self.btn_pause.setToolTip(Strings.Tooltips.PAUSE)
        self.btn_stop.setText(f"■ {Strings.STOP}")
        self.btn_stop.setToolTip(Strings.Tooltips.STOP)
        self.btn_next.setText(Strings.RUN_PANEL_NEXT)
        self.btn_next.setToolTip(Strings.Tooltips.STEP_BY_STEP)
        self.lbl_hotkey.setText(Strings.RUN_PANEL_F12)
        self.set_speed_text(self._speed)
        self._show_counts()

    def _show_counts(self) -> None:
        row, total, ok_cnt, failed_cnt = self._progress
        self.lbl_row.setText(Strings.RUN_PANEL_ROW.format(row=row, total=total))
        self.lbl_stats.setText(Strings.RUN_PANEL_STATS.format(ok=ok_cnt, failed=failed_cnt))

    def update_progress(
        self, row: int, total: int, step_desc: str, ok_cnt: int, failed_cnt: int
    ) -> None:
        self._progress = (row, total, ok_cnt, failed_cnt)
        self._show_counts()
        pct = int((row / max(1, total)) * 100)
        self.prog_bar.setValue(pct)
        self.lbl_step.setText(step_desc)

    def set_speed_text(self, speed: SpeedMode) -> None:
        self._speed = speed
        name = {
            SpeedMode.NORMAL: Strings.SPEED_NORMAL,
            SpeedMode.SLOW: Strings.SPEED_SLOW,
            SpeedMode.VERY_SLOW: Strings.SPEED_VERY_SLOW,
        }.get(speed, speed.value)
        extra = f" (+{speed.extra_seconds}s)" if speed.extra_seconds > 0 else ""
        self.lbl_speed.setText(Strings.RUN_PANEL_SPEED.format(speed=f"{name}{extra}"))

    def set_step_by_step(self, enabled: bool) -> None:
        self.btn_next.setVisible(enabled)

    def _toggle_pause(self) -> None:
        if not self._is_paused:
            self._is_paused = True
            self.btn_pause.setText(f"▶ {Strings.RESUME}")
            self.lbl_title.setText(Strings.RUN_PANEL_PAUSED)
            self.lbl_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #f59e0b;")
            self.pause_clicked.emit()
        else:
            self._is_paused = False
            self.btn_pause.setText(f"⏸ {Strings.PAUSE}")
            self.lbl_title.setText(Strings.RUN_PANEL_RUNNING)
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
