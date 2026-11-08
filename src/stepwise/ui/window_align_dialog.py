"""Window Alignment & Normalization Dialog.

Provides a design-time utility to inspect, resize, and snap target windows
to (0, 0) and standard presets, with one-click injection into the Setup section.
"""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from stepwise.services.window_win import (
    find_window_by_title,
    get_window_visual_bounds,
    list_visible_windows,
    set_window_bounds,
    user32,
)
from stepwise.ui.strings import Strings
from stepwise.ui.theme import get_theme_tokens


class WindowAlignDialog(QDialog):
    """Design-time dialog to standardize target application window bounds."""

    # Emitted on successful alignment: (title, x, y, width, height, maximize, inject_setup)
    alignment_applied = Signal(str, int, int, int, int, bool, bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        initial_title: str = "",
        initial_x: int = 0,
        initial_y: int = 0,
        initial_w: int = 1280,
        initial_h: int = 720,
        initial_maximize: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(Strings.ALIGN_DIALOG_TITLE)
        self.resize(520, 380)
        self._initial_title = initial_title.strip()
        self._initial_x = initial_x
        self._initial_y = initial_y
        self._initial_w = initial_w
        self._initial_h = initial_h
        self._initial_maximize = initial_maximize
        self._setup_ui()
        self._refresh_window_list()

    def _setup_ui(self) -> None:
        t = get_theme_tokens()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        # 1. Target window selection
        h_win = QHBoxLayout()
        self.cbo_windows = QComboBox()
        self.cbo_windows.setEditable(True)
        self.cbo_windows.setInsertPolicy(QComboBox.NoInsert)
        self.cbo_windows.setPlaceholderText("Select active application window...")

        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(36)
        btn_refresh.setToolTip(Strings.ALIGN_DIALOG_REFRESH_TIP)
        btn_refresh.clicked.connect(self._refresh_window_list)

        h_win.addWidget(self.cbo_windows, 1)
        h_win.addWidget(btn_refresh)
        form.addRow(Strings.ALIGN_DIALOG_WINDOW_LABEL, h_win)

        # 2. Preset size
        self.presets = [
            (Strings.WINDOW_PRESET_1280_720, 1280, 720),
            (Strings.WINDOW_PRESET_1600_900, 1600, 900),
            (Strings.WINDOW_PRESET_1920_1040, 1920, 1040),
            (Strings.WINDOW_PRESET_1024_768, 1024, 768),
            (Strings.WINDOW_PRESET_CUSTOM, None, None),
        ]
        self.cbo_preset = QComboBox()
        for label, _, _ in self.presets:
            self.cbo_preset.addItem(label)
        self.cbo_preset.currentIndexChanged.connect(self._on_preset_changed)
        form.addRow(Strings.WINDOW_PRESET_LABEL, self.cbo_preset)

        # 3. Position (X, Y)
        h_pos = QHBoxLayout()
        self.spin_x = QSpinBox()
        self.spin_x.setRange(-9999, 9999)
        self.spin_x.setValue(self._initial_x)

        self.spin_y = QSpinBox()
        self.spin_y.setRange(-9999, 9999)
        self.spin_y.setValue(self._initial_y)

        btn_snap = QPushButton(Strings.WINDOW_SNAP_ORIGIN)
        btn_snap.setToolTip(Strings.WINDOW_SNAP_ORIGIN_TIP)
        btn_snap.clicked.connect(lambda: (self.spin_x.setValue(0), self.spin_y.setValue(0)))

        h_pos.addWidget(QLabel("X:"))
        h_pos.addWidget(self.spin_x)
        h_pos.addWidget(QLabel("Y:"))
        h_pos.addWidget(self.spin_y)
        h_pos.addWidget(btn_snap)
        form.addRow(Strings.WINDOW_POS_LABEL, h_pos)

        # 4. Size (Width, Height)
        h_size = QHBoxLayout()
        self.spin_w = QSpinBox()
        self.spin_w.setRange(100, 9999)
        self.spin_w.setValue(self._initial_w)

        self.spin_h = QSpinBox()
        self.spin_h.setRange(100, 9999)
        self.spin_h.setValue(self._initial_h)

        self.spin_w.valueChanged.connect(self._on_custom_size_changed)
        self.spin_h.valueChanged.connect(self._on_custom_size_changed)

        h_size.addWidget(QLabel("Width:"))
        h_size.addWidget(self.spin_w)
        h_size.addWidget(QLabel("Height:"))
        h_size.addWidget(self.spin_h)
        form.addRow(Strings.WINDOW_SIZE_LABEL, h_size)

        # Match initial preset
        matched_preset_idx = 4
        for i, (_, pw, ph) in enumerate(self.presets[:4]):
            if self._initial_w == pw and self._initial_h == ph:
                matched_preset_idx = i
                break
        self.cbo_preset.setCurrentIndex(matched_preset_idx)

        # 5. Mode
        self.chk_maximize = QCheckBox(Strings.WINDOW_MAXIMIZE_LABEL)
        self.chk_maximize.setChecked(self._initial_maximize)
        self.chk_maximize.toggled.connect(self._on_maximize_toggled)
        self._on_maximize_toggled(self._initial_maximize)
        form.addRow("Mode:", self.chk_maximize)

        # 6. Fetch current bounds helper
        btn_fetch_current = QPushButton(Strings.WINDOW_GET_CURRENT)
        btn_fetch_current.setToolTip(Strings.WINDOW_GET_CURRENT_TIP)
        btn_fetch_current.clicked.connect(self._on_fetch_current)
        form.addRow("", btn_fetch_current)

        layout.addLayout(form)

        # 7. Setup injection option
        self.chk_inject = QCheckBox(Strings.ALIGN_DIALOG_INJECT_SETUP)
        self.chk_inject.setChecked(True)
        self.chk_inject.setStyleSheet(f"font-weight: bold; color: {t['accent']}; margin-top: 6px;")
        layout.addWidget(self.chk_inject)

        layout.addStretch()

        # 8. Bottom buttons
        h_btn = QHBoxLayout()
        self.btn_apply = QPushButton(Strings.ALIGN_DIALOG_APPLY_BTN)
        self.btn_apply.setStyleSheet(
            f"background-color: {t['accent']}; color: {t.get('fg_selected', '#ffffff')}; font-weight: bold; padding: 6px 16px;"
        )
        self.btn_apply.clicked.connect(self._on_apply)

        btn_cancel = QPushButton(Strings.BTN_CLOSE)
        btn_cancel.clicked.connect(self.reject)

        h_btn.addStretch()
        h_btn.addWidget(self.btn_apply)
        h_btn.addWidget(btn_cancel)
        layout.addLayout(h_btn)

    def _refresh_window_list(self) -> None:
        current_text = self.cbo_windows.currentText().strip() or self._initial_title
        blocker = QSignalBlocker(self.cbo_windows)
        self.cbo_windows.clear()
        windows = list_visible_windows(exclude_self=True)
        matched_idx = -1
        for i, (hwnd, title) in enumerate(windows):
            self.cbo_windows.addItem(title, userData=hwnd)
            if current_text and current_text.lower() in title.lower() and matched_idx < 0:
                matched_idx = i

        if matched_idx >= 0:
            self.cbo_windows.setCurrentIndex(matched_idx)
            self.cbo_windows.setEditText(self.cbo_windows.itemText(matched_idx))
        elif current_text:
            self.cbo_windows.setEditText(current_text)
        del blocker

    def _on_preset_changed(self, idx: int) -> None:
        _, pw, ph = self.presets[idx]
        if pw is not None and ph is not None:
            b1 = QSignalBlocker(self.spin_w)
            b2 = QSignalBlocker(self.spin_h)
            self.spin_w.setValue(pw)
            self.spin_h.setValue(ph)
            del b1, b2

    def _on_custom_size_changed(self) -> None:
        w, h = self.spin_w.value(), self.spin_h.value()
        m_idx = 4
        for i, (_, pw, ph) in enumerate(self.presets[:4]):
            if w == pw and h == ph:
                m_idx = i
                break
        b = QSignalBlocker(self.cbo_preset)
        self.cbo_preset.setCurrentIndex(m_idx)
        del b

    def _on_maximize_toggled(self, v: bool) -> None:
        self.cbo_preset.setEnabled(not v)
        self.spin_x.setEnabled(not v)
        self.spin_y.setEnabled(not v)
        self.spin_w.setEnabled(not v)
        self.spin_h.setEnabled(not v)

    def _get_target_hwnd_and_title(self) -> tuple[int | None, str]:
        title = self.cbo_windows.currentText().strip()
        idx = self.cbo_windows.currentIndex()
        # Only use cached HWND if user has not typed a different custom title
        if idx >= 0 and self.cbo_windows.itemText(idx).strip().lower() == title.lower():
            hwnd = self.cbo_windows.itemData(idx)
            if hwnd and user32.IsWindow(hwnd):
                return hwnd, title
        if title:
            return find_window_by_title(title), title
        return None, ""

    def _on_fetch_current(self) -> None:
        hwnd, title = self._get_target_hwnd_and_title()
        if not title:
            QMessageBox.warning(self, Strings.WINDOW_TITLE_REQUIRED_TITLE, Strings.WINDOW_TITLE_REQUIRED_MSG)
            return
        if not hwnd:
            QMessageBox.warning(self, Strings.WINDOW_NOT_FOUND_TITLE, Strings.WINDOW_NOT_FOUND_MSG.format(title=title))
            return
        x, y, w, h = get_window_visual_bounds(hwnd)
        if w <= 0 or h <= 0:
            QMessageBox.warning(self, Strings.WINDOW_INSPECT_FAIL_TITLE, Strings.WINDOW_INSPECT_FAIL_MSG.format(title=title))
            return
        self.spin_x.setValue(x)
        self.spin_y.setValue(y)
        self.spin_w.setValue(w)
        self.spin_h.setValue(h)

    def _on_apply(self) -> None:
        hwnd, title = self._get_target_hwnd_and_title()
        if not title:
            QMessageBox.warning(self, Strings.WINDOW_TITLE_REQUIRED_TITLE, Strings.WINDOW_TITLE_REQUIRED_MSG)
            return
        if not hwnd:
            QMessageBox.warning(self, Strings.WINDOW_NOT_FOUND_TITLE, Strings.WINDOW_NOT_FOUND_MSG.format(title=title))
            return

        x = self.spin_x.value()
        y = self.spin_y.value()
        w = self.spin_w.value()
        h = self.spin_h.value()
        maximize = self.chk_maximize.isChecked()
        inject = self.chk_inject.isChecked()

        ok, msg = set_window_bounds(hwnd, x=x, y=y, width=w, height=h, maximize=maximize)
        if not ok:
            QMessageBox.critical(self, Strings.WINDOW_ALIGN_FAIL_TITLE, Strings.WINDOW_ALIGN_FAIL_MSG.format(error=msg))
            return

        # Emit signal to inform main window and inject action into Setup
        self.alignment_applied.emit(title, x, y, w, h, maximize, inject)

        if msg:
            QMessageBox.information(
                self,
                Strings.WINDOW_ALIGN_NOTICE_TITLE,
                Strings.WINDOW_ALIGN_NOTICE_MSG.format(notice=msg),
            )
        self.accept()
