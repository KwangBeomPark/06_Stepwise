"""Temporary visual crosshair and UI element highlight overlays (Section 12.3).

Displays a non-intrusive high-visibility red crosshair at (x, y) or a glowing
bounding box around a resolved UI Element for 1.5s without stealing focus.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QApplication, QWidget


class ScreenCrosshairOverlay(QWidget):
    """Flashes a target crosshair over target screen coordinates."""

    def __init__(
        self, x: int, y: int, duration_ms: int = 1500, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._target_x = x
        self._target_y = y
        self._box_radius = 50

        # Adjust physical coordinates to Qt logical coordinates
        screen = QApplication.primaryScreen()
        dpr = float(screen.devicePixelRatio()) if screen else 1.0
        if dpr <= 0:
            dpr = 1.0
        screen_origin = screen.geometry().topLeft() if screen else None
        log_x = int(round(x / dpr)) + (screen_origin.x() if screen_origin else 0)
        log_y = int(round(y / dpr)) + (screen_origin.y() if screen_origin else 0)

        # Position overlay centered on target coordinate
        self.setGeometry(
            log_x - self._box_radius,
            log_y - self._box_radius,
            self._box_radius * 2,
            self._box_radius * 2 + 25,
        )

        QTimer.singleShot(duration_ms, self.close)
        self.show()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self._box_radius
        cy = self._box_radius

        # 1. Outer halo ring
        pen_glow = QPen(QColor(239, 68, 68, 90), 8)
        painter.setPen(pen_glow)
        painter.drawEllipse(cx - 20, cy - 20, 40, 40)

        # 2. Main target ring
        pen_ring = QPen(QColor(220, 38, 38), 3)
        painter.setPen(pen_ring)
        painter.drawEllipse(cx - 20, cy - 20, 40, 40)

        # 3. Center bullseye
        painter.setBrush(QColor(220, 38, 38))
        painter.drawEllipse(cx - 3, cy - 3, 6, 6)

        # 4. Crosshair ticks
        pen_tick = QPen(QColor(220, 38, 38), 2)
        painter.setPen(pen_tick)
        painter.drawLine(cx - 32, cy, cx - 10, cy)
        painter.drawLine(cx + 10, cy, cx + 32, cy)
        painter.drawLine(cx, cy - 32, cx, cy - 10)
        painter.drawLine(cx, cy + 10, cx, cy + 32)

        # 5. Coordinate label pill
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        text = f"({self._target_x}, {self._target_y})"

        # Background badge for text
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 23, 42, 220))
        painter.drawRoundedRect(cx - 40, cy + 26, 80, 20, 4, 4)

        # White coordinate text
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(cx - 40, cy + 26, 80, 20, Qt.AlignmentFlag.AlignCenter, text)


class ElementHighlightOverlay(QWidget):
    """Flashes a glowing bounding box around a target UI element rectangle."""

    def __init__(
        self,
        rect: tuple[int, int, int, int],
        label: str = "",
        duration_ms: int = 1800,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._label = label
        screen = QApplication.primaryScreen()
        dpr = float(screen.devicePixelRatio()) if screen else 1.0
        if dpr <= 0:
            dpr = 1.0

        left, top, width, height = rect
        screen_origin = screen.geometry().topLeft() if screen else None
        ox = screen_origin.x() if screen_origin else 0
        oy = screen_origin.y() if screen_origin else 0
        log_x = int(round(left / dpr)) + ox
        log_y = int(round(top / dpr)) + oy
        log_w = max(24, int(round(width / dpr)))
        log_h = max(24, int(round(height / dpr)))

        self._pad = 8
        self._badge_h = 24
        self._box_w = log_w
        self._box_h = log_h

        win_x = log_x - self._pad
        win_y = log_y - self._pad - self._badge_h
        self._box_y = log_y - win_y

        self.setGeometry(
            win_x,
            win_y,
            max(220, log_w + self._pad * 2),
            log_h + self._pad * 2 + self._badge_h,
        )

        QTimer.singleShot(duration_ms, self.close)
        self.show()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bx = self._pad
        by = getattr(self, "_box_y", self._pad + self._badge_h)

        # Outer glow
        painter.setPen(QPen(QColor(56, 189, 248, 100), 6))
        painter.setBrush(QColor(56, 189, 248, 30))
        painter.drawRoundedRect(bx, by, self._box_w, self._box_h, 4, 4)

        # Crisp inner border
        painter.setPen(QPen(QColor(14, 165, 233), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(bx, by, self._box_w, self._box_h, 4, 4)

        if self._label:
            painter.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(15, 23, 42, 235))
            badge_w = min(self.width() - 8, max(140, len(self._label) * 8 + 20))
            painter.drawRoundedRect(bx, 2, badge_w, 20, 4, 4)
            painter.setPen(QColor(56, 189, 248))
            painter.drawText(
                bx + 6,
                2,
                badge_w - 12,
                20,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self._label,
            )
