"""Full-screen capture overlay for Pick (F8) and Region Capture (F9) (Section 12.4).

Displays a frozen snapshot of the screen to allow precise coordinate picking or region dragging.
"""

from __future__ import annotations

import os
import uuid
from math import ceil, floor
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
    capture_failed = Signal(str)

    def __init__(
        self, mode: str = "pick", images_dir: str = "images", parent: QWidget | None = None
    ) -> None:
        super().__init__(
            parent,
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self.mode = mode  # "pick" or "region"
        self.images_dir = images_dir
        if self.mode == "region":
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
            screen = QApplication.primaryScreen()
            self._dpr = float(screen.devicePixelRatio()) if screen else 1.0
            if self._dpr <= 0:
                self._dpr = 1.0
            frame_bgra = capture_screen(check_black_screen=False)
            h, w, ch = frame_bgra.shape
            bytes_per_line = ch * w
            qimg = QImage(frame_bgra.data, w, h, bytes_per_line, QImage.Format_ARGB32)
            qimg.setDevicePixelRatio(self._dpr)
            self._freeze_pixmap = QPixmap.fromImage(qimg)
            self._frame = frame_bgra
        except Exception:
            self._dpr = 1.0
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
                painter.drawPixmap(rect, self._freeze_pixmap, self._physical_rect(rect))

            pen = QPen(QColor("#3b82f6"), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Draw coordinate badge in physical pixels
            phys_x, phys_y, phys_w, phys_h = self._physical_rect(rect).getRect()
            info_text = f"{phys_w} x {phys_h} at ({phys_x}, {phys_y})"
            painter.setPen(Qt.white)
            painter.drawText(rect.x() + 5, max(15, rect.y() - 5), info_text)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.LeftButton:
            dpr = getattr(self, "_dpr", 1.0)
            if self.mode == "pick":
                x = int(round(event.position().x() * dpr))
                y = int(round(event.position().y() * dpr))
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
        physical_rect = self._physical_rect(rect)
        x, y, w, h = physical_rect.getRect()
        if w <= 0 or h <= 0:
            return

        patch = self._frame[y : y + h, x : x + w]

        img_id = uuid.uuid4().hex
        filename = f"img_{img_id}.png"
        filepath = os.path.join(self.images_dir, filename)

        # Save patch
        ext = os.path.splitext(filepath)[1]
        try:
            ok, encoded = cv2.imencode(ext, patch)
            if not ok:
                raise OSError("The captured image could not be encoded.")
            with open(filepath, "wb") as f:
                f.write(encoded)
        except (OSError, cv2.error) as e:
            self.capture_failed.emit(str(e))
            return
        rel_path = f"images/{filename}"
        self.region_captured.emit(rel_path, [x, y, w, h])

    def _physical_rect(self, rect: QRect) -> QRect:
        """Map a logical Qt rectangle to the captured frame's physical pixels."""
        if self._frame is None:
            return QRect()

        dpr = getattr(self, "_dpr", 1.0)
        frame_height, frame_width = self._frame.shape[:2]
        left = max(0, min(floor(rect.x() * dpr), frame_width))
        top = max(0, min(floor(rect.y() * dpr), frame_height))
        right = max(left, min(ceil((rect.x() + rect.width()) * dpr), frame_width))
        bottom = max(top, min(ceil((rect.y() + rect.height()) * dpr), frame_height))
        return QRect(left, top, right - left, bottom - top)
