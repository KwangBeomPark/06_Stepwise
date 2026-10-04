"""Application entry point and Qt initialization."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from stepwise.ui.main_window import MainWindow


def main() -> None:
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Stepwise")
    app.setOrganizationName("Stepwise")

    # Enforce clean, predictable Fusion style and consistent light palette
    # to avoid half-dark/half-light rendering on Windows 11 Dark Mode
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1e293b"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#94a3b8"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#dc2626"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))

    # Explicit Disabled palette roles to prevent OS dark mode bleed
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#94a3b8"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#94a3b8"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#94a3b8"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor("#e2e8f0"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor("#94a3b8"))
    app.setPalette(palette)

    # Load custom QSS stylesheet
    qss_path = os.path.join(os.path.dirname(__file__), "ui", "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
