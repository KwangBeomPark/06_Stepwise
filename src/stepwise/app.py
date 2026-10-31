"""Application entry point and Qt initialization."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from stepwise.core.app_paths import load_user_settings
from stepwise.ui.main_window import MainWindow
from stepwise.ui.strings import apply_language
from stepwise.ui.theme import apply_theme


def get_app_icon_path() -> str:
    """Find the path to the Stepwise application icon."""
    if hasattr(sys, "_MEIPASS"):
        p = os.path.join(sys._MEIPASS, "assets", "icons", "stepwise.ico")
        if os.path.exists(p):
            return p
    exe_dir = os.path.dirname(sys.executable)
    p_exe = os.path.join(exe_dir, "assets", "icons", "stepwise.ico")
    if os.path.exists(p_exe):
        return p_exe
    mod_dir = os.path.dirname(__file__)
    candidates = [
        os.path.join(mod_dir, "ui", "stepwise.ico"),
        os.path.join(mod_dir, "..", "..", "assets", "icons", "stepwise.ico"),
        os.path.join(mod_dir, "assets", "icons", "stepwise.ico"),
        os.path.join(mod_dir, "ui", "stepwise.png"),
        os.path.join(mod_dir, "..", "..", "assets", "icons", "stepwise.png"),
    ]
    for c in candidates:
        full = os.path.abspath(c)
        if os.path.exists(full):
            return full
    return ""


def main() -> None:
    # Ensure Windows taskbar displays custom icon and Per-Monitor V2 DPI awareness
    if sys.platform == "win32":
        try:
            import ctypes

            app_id = "stepwise.desktop.macro.automation.0.4.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            if hasattr(ctypes.windll.user32, "SetProcessDpiAwarenessContext"):
                ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            pass

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Stepwise")
    app.setOrganizationName("Stepwise")

    # Set application icon for taskbar and windows
    icon_path = get_app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    # Load user preferences (defaults: language='ko', theme='dark')
    settings = load_user_settings()
    apply_language(str(settings.get("language", "ko")))
    apply_theme(app, str(settings.get("theme", "dark")))

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
