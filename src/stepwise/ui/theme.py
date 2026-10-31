"""Centralized Dark and Light theme tokens and QPalette/QSS applier for Stepwise."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

DARK_TOKENS: dict[str, str] = {
    "bg_window": "#0f172a",
    "bg_surface": "#1e293b",
    "bg_base": "#0b1120",
    "bg_alt": "#131c31",
    "bg_section": "#1e293b",
    "bg_hover": "#334155",
    "bg_pressed": "#475569",
    "bg_selected": "#1d4ed8",
    "fg_selected": "#f8fafc",
    "border": "#334155",
    "border_subtle": "#1e293b",
    "text": "#f1f5f9",
    "text_heading": "#f8fafc",
    "text_muted": "#94a3b8",
    "text_secondary": "#94a3b8",
    "text_disabled": "#64748b",
    "accent": "#38bdf8",
    "accent_primary": "#38bdf8",
    "accent_border": "#0284c7",
    "status_ok": "#4ade80",
    "status_fail": "#f87171",
    "status_warn": "#fbbf24",
    "status_run": "#38bdf8",
    "highlight_run_bg": "#1e3a8a",
    "highlight_fail_bg": "#7f1d1d",
    "chip_bg": "#1e3a8a",
    "chip_fg": "#7dd3fc",
    "chip_border": "#0284c7",
    "banner_bg": "#1e293b",
    "banner_fg": "#e2e8f0",
    "guide_bg": "#1e293b",
    "guide_fg": "#f1f5f9",
}

LIGHT_TOKENS: dict[str, str] = {
    "bg_window": "#f8fafc",
    "bg_surface": "#ffffff",
    "bg_base": "#ffffff",
    "bg_alt": "#f1f5f9",
    "bg_section": "#f1f5f9",
    "bg_hover": "#f1f5f9",
    "bg_pressed": "#e2e8f0",
    "bg_selected": "#dbeafe",
    "fg_selected": "#1e40af",
    "border": "#cbd5e1",
    "border_subtle": "#e2e8f0",
    "text": "#0f172a",
    "text_heading": "#1e293b",
    "text_muted": "#64748b",
    "text_secondary": "#64748b",
    "text_disabled": "#94a3b8",
    "accent": "#2563eb",
    "accent_primary": "#2563eb",
    "accent_border": "#2563eb",
    "status_ok": "#16a34a",
    "status_fail": "#dc2626",
    "status_warn": "#d97706",
    "status_run": "#2563eb",
    "highlight_run_bg": "#fef08a",
    "highlight_fail_bg": "#fecaca",
    "chip_bg": "#e0f2fe",
    "chip_fg": "#0369a1",
    "chip_border": "#bae6fd",
    "banner_bg": "#f1f5f9",
    "banner_fg": "#334155",
    "guide_bg": "#f8fafc",
    "guide_fg": "#1e293b",
}

_CURRENT_THEME: str = "dark"


def get_current_theme() -> str:
    """Return active theme name ('dark' or 'light')."""
    return _CURRENT_THEME


def get_theme_tokens(theme: str | None = None) -> dict[str, str]:
    """Return semantic color token dictionary for the given or current theme."""
    target = (theme or _CURRENT_THEME).lower()
    return DARK_TOKENS if target == "dark" else LIGHT_TOKENS


def build_stylesheet(theme: str = "dark") -> str:
    """Build dynamic QSS stylesheet using semantic tokens."""
    t = get_theme_tokens(theme)
    return f"""
/* Stepwise Enterprise Theme ({theme.upper()}) */

* {{
    font-family: "Malgun Gothic", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
    color: {t["text"]};
}}

QMainWindow, QDialog {{
    background-color: {t["bg_window"]};
    color: {t["text"]};
}}

QToolTip {{
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px;
}}

QToolTip * {{
    color: #f8fafc;
}}

/* Toolbar */
QToolBar {{
    background-color: {t["bg_surface"]};
    border-bottom: 1px solid {t["border"]};
    padding: 6px 12px;
    spacing: 8px;
}}

QToolBar QLabel {{
    color: {t["text_muted"]};
    font-weight: 600;
}}

QToolBar QPushButton {{
    background-color: {t["bg_surface"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
    min-height: 22px;
}}

QToolBar QPushButton:hover {{
    background-color: {t["bg_hover"]};
    border-color: {t["text_muted"]};
    color: {t["text_heading"]};
}}

/* General Buttons */
QPushButton {{
    background-color: {t["bg_surface"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {t["bg_hover"]};
    border-color: {t["text_muted"]};
    color: {t["text_heading"]};
}}

QPushButton:pressed {{
    background-color: {t["bg_pressed"]};
    color: {t["text_heading"]};
}}

QPushButton:disabled {{
    background-color: {t["bg_window"]};
    color: {t["text_disabled"]};
    border-color: {t["border_subtle"]};
}}

/* Primary Execution Buttons */
QPushButton#btn_run {{
    background-color: #16a34a;
    color: #ffffff;
    font-weight: bold;
    border-radius: 6px;
    padding: 6px 18px;
    border: 1px solid #15803d;
}}

QPushButton#btn_run:hover {{
    background-color: #15803d;
    color: #ffffff;
}}

QPushButton#btn_run:disabled {{
    background-color: {t["bg_surface"]};
    color: {t["text_disabled"]};
    border-color: {t["border"]};
}}

QPushButton#btn_pause {{
    background-color: #d97706;
    color: #ffffff;
    font-weight: bold;
    border-radius: 6px;
    padding: 6px 16px;
    border: 1px solid #b45309;
}}

QPushButton#btn_pause:hover {{
    background-color: #b45309;
    color: #ffffff;
}}

QPushButton#btn_pause:disabled {{
    background-color: {t["bg_surface"]};
    color: {t["text_disabled"]};
    border-color: {t["border"]};
}}

QPushButton#btn_stop {{
    background-color: #dc2626;
    color: #ffffff;
    font-weight: bold;
    border-radius: 6px;
    padding: 6px 16px;
    border: 1px solid #b91c1c;
}}

QPushButton#btn_stop:hover {{
    background-color: #b91c1c;
    color: #ffffff;
}}

QPushButton#btn_stop:disabled {{
    background-color: {t["bg_surface"]};
    color: {t["text_disabled"]};
    border-color: {t["border"]};
}}

QPushButton#btn_schedule {{
    background-color: #4f46e5;
    color: #ffffff;
    font-weight: bold;
    border-radius: 6px;
    padding: 6px 14px;
    border: 1px solid #4338ca;
}}

QPushButton#btn_schedule:hover {{
    background-color: #4338ca;
    color: #ffffff;
}}

/* Tree, Lists & Tables */
QTreeView, QTreeWidget, QListView, QListWidget, QTableView, QTableWidget {{
    background-color: {t["bg_base"]};
    alternate-background-color: {t["bg_alt"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    gridline-color: {t["border_subtle"]};
    selection-background-color: {t["bg_selected"]};
    selection-color: {t["fg_selected"]};
    outline: none;
}}

QTreeView::item, QListWidget::item, QTableWidget::item {{
    padding: 5px 8px;
    border-bottom: 1px solid {t["border_subtle"]};
}}

QTreeView::item:hover, QListWidget::item:hover, QTableWidget::item:hover {{
    background-color: {t["bg_hover"]};
}}

QTreeView::item:selected, QListWidget::item:selected, QTableWidget::item:selected {{
    background-color: {t["bg_selected"]};
    color: {t["fg_selected"]};
    font-weight: 600;
}}

/* Table and Tree Headers */
QHeaderView::section {{
    background-color: {t["bg_surface"]};
    color: {t["text_heading"]};
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid {t["border"]};
    border-right: 1px solid {t["border"]};
    font-weight: bold;
}}

QTableCornerButton::section {{
    background-color: {t["bg_surface"]};
    border: 1px solid {t["border"]};
}}

/* Tabs */
QTabWidget {{
    background-color: {t["bg_window"]};
}}

QTabWidget::pane {{
    border: 1px solid {t["border"]};
    background-color: {t["bg_surface"]};
    border-radius: 6px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: {t["bg_window"]};
    color: {t["text_muted"]};
    padding: 8px 16px;
    border: 1px solid {t["border"]};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 3px;
    font-weight: 600;
}}

QTabBar::tab:selected {{
    background-color: {t["bg_surface"]};
    color: {t["accent"]};
    border-bottom: 1px solid {t["bg_surface"]};
    font-weight: bold;
}}

QTabBar::tab:hover:!selected {{
    background-color: {t["bg_hover"]};
    color: {t["text"]};
}}

/* Scroll Areas & Containers */
QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollArea > QWidget {{
    background-color: transparent;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

/* Group Boxes / Panels */
QGroupBox {{
    background-color: {t["bg_surface"]};
    border: 1px solid {t["border"]};
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px;
    font-weight: 600;
    color: {t["text_heading"]};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    background-color: {t["bg_surface"]};
    color: {t["accent"]};
    font-weight: bold;
}}

/* Inputs */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit, QTimeEdit {{
    background-color: {t["bg_base"]};
    border: 1px solid {t["border"]};
    border-radius: 5px;
    padding: 5px 10px;
    color: {t["text"]};
    selection-background-color: {t["bg_selected"]};
    selection-color: {t["fg_selected"]};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus, QTimeEdit:focus {{
    border-color: {t["accent_border"]};
    outline: none;
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {t["bg_surface"]};
    color: {t["text"]};
    selection-background-color: {t["bg_selected"]};
    selection-color: {t["fg_selected"]};
    border: 1px solid {t["border"]};
}}

/* Checkboxes & Radio Buttons */
QCheckBox, QRadioButton {{
    color: {t["text"]};
    spacing: 6px;
}}

QCheckBox:disabled, QRadioButton:disabled {{
    color: {t["text_disabled"]};
}}

/* Status Bar */
QStatusBar {{
    background-color: {t["bg_surface"]};
    border-top: 1px solid {t["border"]};
    color: {t["text_muted"]};
    padding: 4px 12px;
    font-weight: 500;
}}

QStatusBar QLabel {{
    color: {t["text_muted"]};
    font-weight: 500;
}}

/* Context Menus */
QMenu {{
    background-color: {t["bg_surface"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 24px;
    border-radius: 4px;
    color: {t["text"]};
}}

QMenu::item:selected {{
    background-color: {t["bg_selected"]};
    color: {t["fg_selected"]};
}}

QMenu::separator {{
    height: 1px;
    background-color: {t["border"]};
    margin: 4px 8px;
}}

/* Splitters */
QSplitter::handle {{
    background-color: {t["border"]};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

QSplitter::handle:hover {{
    background-color: {t["accent"]};
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {t["bg_window"]};
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background: {t["border"]};
    min-height: 24px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background: {t["text_muted"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {t["bg_window"]};
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal {{
    background: {t["border"]};
    min-width: 24px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {t["text_muted"]};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
"""


def build_palette(theme: str = "dark") -> QPalette:
    """Create a Fusion-compatible QPalette for the specified theme."""
    t = get_theme_tokens(theme)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t["bg_window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(t["bg_base"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t["bg_alt"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1e293b"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(t["text_muted"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(t["bg_surface"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(t["status_fail"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t["bg_selected"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t["fg_selected"]))

    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(t["text_disabled"])
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(t["text_disabled"])
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(t["text_disabled"])
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(t["border"])
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor(t["text_disabled"])
    )
    return palette


def apply_theme(app: QApplication | Any = None, theme: str = "dark") -> str:
    """Apply QPalette and QSS stylesheet to the QApplication instance."""
    global _CURRENT_THEME
    normalized = "light" if str(theme).lower() == "light" else "dark"
    _CURRENT_THEME = normalized

    target_app = app or QApplication.instance()
    if target_app is not None:
        target_app.setStyle("Fusion")
        target_app.setPalette(build_palette(normalized))
        target_app.setStyleSheet(build_stylesheet(normalized))
    return normalized
