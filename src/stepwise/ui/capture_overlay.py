"""Full-screen capture overlay for Pick (F8) and Region Capture (F9) (Section 12.4).

Displays a frozen snapshot of the screen to allow precise coordinate picking or region dragging.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import cv2
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from stepwise.services.screen import capture_screen


class CaptureOverlay(QWidget):
    coords_picked = Signal(int, int)  # (x, y)
    region_captured = Signal(str, list)  # (saved_image_path, [x, y, w, h])
    cancelled = Signal()

    def __init__(self, mode: str = "pick", images_dir: str = "images", parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self.mode = mode  # "pick" or "region"
        self.images_dir = images_dir
        os.makedirs(self.images_dir, exist_ok=True)

        self._freeze_pixmap: QPixmap | None = None
        self._start_pos: QPoint | None = None
        self._curr_pos: QPoint | None = None
        self._is_selecting = False

        self._capture_screen_freeze()

        # Fill primary screen
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

        self.setCursor(Qt.CrossCursor)

    def _capture_screen_freeze(self) -> None:
        """Capture live screen before overlay appears so user works on a static image."""
        try:
            frame_bgra = capture_screen(check_black_screen=False)
            h, w, ch = frame_bgra.shape
            bytes_per_line = ch * w
            qimg = QImage(frame_bgra.data, w, h, bytes_per_line, QImage.Format_ARGB32)
            self._freeze_pixmap = QPixmap.fromImage(qimg)
            self._frame = frame_bgra
        except Exception:
            self._freeze_pixmap = None
            self._frame = None

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        if self._freeze_pixmap:
            painter.drawPixmap(0, 0, self._freeze_pixmap)

        # Dim overlay mask
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

        # Draw drag selection rectangle
        if self.mode == "region" and self._start_pos and self._curr_pos:
            rect = QRect(self._start_pos, self._curr_pos).normalized()
            # Clear dimmed area inside rectangle
            if self._freeze_pixmap:
                painter.drawPixmap(rect, self._freeze_pixmap, rect)

            pen = QPen(QColor("#3b82f6"), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Draw coordinate badge
            info_text = f"{rect.width()} x {rect.height()} at ({rect.x()}, {rect.y()})"
            painter.setPen(Qt.white)
            painter.drawText(rect.x() + 5, max(15, rect.y() - 5), info_text)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.LeftButton:
            if self.mode == "pick":
                x = int(event.globalPosition().x())
                y = int(event.globalPosition().y())
                self.coords_picked.emit(x, y)
                self.close()
            elif self.mode == "region":
                self._start_pos = event.pos()
                self._curr_pos = event.pos()
                self._is_selecting = True
                self.update()

    def mouseMoveEvent(self, event: Any) -> None:
        if self.mode == "region" and self._is_selecting:
            self._curr_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: Any) -> None:
        if self.mode == "region" and self._is_selecting:
            self._is_selecting = False
            if self._start_pos and self._curr_pos:
                rect = QRect(self._start_pos, self._curr_pos).normalized()
                if rect.width() > 5 and rect.height() > 5:
                    self._save_region(rect)
            self.close()

    def keyPressEvent(self, event: Any) -> None:
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.close()

    def _save_region(self, rect: QRect) -> None:
        if self._frame is None:
            return
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        patch = self._frame[y : y + h, x : x + w]

        img_id = str(uuid.uuid4())[:8]
        filename = f"img_{img_id}.png"
        filepath = os.path.join(self.images_dir, filename)

        # Save patch
        ext = os.path.splitext(filepath)[1]
        ok, encoded = cv2.imencode(ext, patch)
        if ok:
            with open(filepath, "wb") as f:
                f.write(encoded)
            rel_path = f"images/{filename}"
            self.region_captured.emit(rel_path, [x, y, w, h])
