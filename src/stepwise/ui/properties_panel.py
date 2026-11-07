"""Action properties panel implementing Section 12.3 specifications.

Provides dynamic, type-specific property editors with:
- Pick (F8), Capture (F9), and Pick UI Element (Ctrl+F8) triggers
- UI Selector & Simulate Click configuration and live validation
- Universal Guard / Verify controls
- Variable autocomplete hint on '{'
- Real-time model synchronization & Dark/Light theme support
"""

from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from stepwise.core.models import ActionItem, ImageCondition
from stepwise.core.variables import substitute_variables
from stepwise.services.input_win import parse_key_combination
from stepwise.ui.strings import Strings, action_type_label, get_current_language
from stepwise.ui.theme import get_theme_tokens

# (label, value) one-click presets; labels are key names, identical in every language.
KEY_PRESETS: tuple[tuple[str, str], ...] = (
    ("Enter", "enter"),
    ("Tab", "tab"),
    ("Esc", "esc"),
    ("Ctrl+S", "ctrl+s"),
    ("Ctrl+V", "ctrl+v"),
    ("Ctrl+A", "ctrl+a"),
)
WAIT_PRESETS: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0)
CHIPS_PER_ROW = 3  # keeps the 320px minimum panel width


def is_valid_key_combination(keys: str) -> bool:
    """True when every token of a key combination is a known key name."""
    try:
        return bool(parse_key_combination(keys))
    except ValueError:
        return False


class PropertiesPanel(QWidget):
    property_changed = Signal()
    request_pick = Signal()
    request_pick_element = Signal()
    request_validate_selector = Signal(object)
    request_capture = Signal()
    request_capture_guard = Signal()
    request_capture_verify = Signal()
    request_test_step = Signal(object)
    request_test_match = Signal(object)
    request_show_crosshair = Signal(int, int)
    request_locate_target = Signal(object)
    request_open_data_file = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_action: ActionItem | None = None
        self._available_headers: list[str] = []
        self._sample_row: dict[str, str] = {}
        self.txt_text: QLineEdit | None = None
        self.lbl_row_preview: QLabel | None = None
        self.lbl_hangeul_hint: QLabel | None = None
        self.chips_widget: QWidget | None = None
        self.chip_buttons: list[QPushButton] = []
        self.btn_locate: QPushButton | None = None
        # Optional hook run before a modal opens (e.g. to cancel pending input).
        self.before_prompt: Callable[[], None] | None = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Header Title
        self.title_lbl = QLabel(Strings.PROPERTIES_TITLE)
        main_layout.addWidget(self.title_lbl)

        # Scroll Area for dynamic properties
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(10)
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        self._apply_theme_styles()
        self._build_empty_state()

    def _apply_theme_styles(self) -> None:
        t = get_theme_tokens()
        self.title_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {t['text_heading']};"
        )

    def retranslate_ui(self) -> None:
        """Rebuild properties panel with active language and theme tokens."""
        self.title_lbl.setText(Strings.PROPERTIES_TITLE)
        self._apply_theme_styles()
        self.set_action(self._current_action)

    def _build_empty_state(self) -> None:
        t = get_theme_tokens()
        self._clear_container()
        guide_widget = QWidget()
        guide_layout = QVBoxLayout(guide_widget)
        guide_layout.setContentsMargins(12, 12, 12, 12)
        guide_layout.setSpacing(10)

        lbl = QLabel(Strings.PROPERTIES_GUIDE)
        lbl.setStyleSheet(
            f"background-color: {t['guide_bg']}; color: {t['guide_fg']}; padding: 18px; "
            f"border: 1px solid {t['border']}; border-radius: 8px; line-height: 150%; font-size: 13px;"
        )
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        guide_layout.addWidget(lbl)
        guide_layout.addStretch()

        self.container_layout.addWidget(guide_widget)
        self.container_layout.addStretch()

    def _clear_container(self) -> None:
        old_container = self.scroll.takeWidget()
        if old_container:
            old_container.hide()
            for widget in old_container.findChildren(QWidget):
                widget.blockSignals(True)
            for name, value in list(vars(self).items()):
                if isinstance(value, QWidget) and old_container.isAncestorOf(value):
                    setattr(self, name, None)
            old_container.deleteLater()
        self.txt_text = None
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(10)
        self.scroll.setWidget(self.container)

    def set_action(self, action: ActionItem | None) -> None:
        """Bind an ActionItem to the editor."""
        self._current_action = action
        if not action:
            self._build_empty_state()
            return
        self._clear_container()

        # 1. Common Settings
        common_box = QGroupBox(Strings.GENERAL_OPTIONS)
        common_layout = QFormLayout(common_box)

        self.chk_enabled = QCheckBox(Strings.ACTION_ENABLED)
        self.chk_enabled.setChecked(action.enabled)
        self.chk_enabled.toggled.connect(self._on_enabled_toggled)
        common_layout.addRow(self.chk_enabled)

        self.txt_note = QLineEdit(action.note)
        self.txt_note.setPlaceholderText("User description or intent")
        self.txt_note.textChanged.connect(self._on_note_changed)
        common_layout.addRow(Strings.NOTE_LABEL, self.txt_note)

        self.spin_wait_before = QDoubleSpinBox()
        self.spin_wait_before.setRange(0.0, 60.0)
        self.spin_wait_before.setSingleStep(0.1)
        self.spin_wait_before.setValue(
            action.wait_before if action.wait_before is not None else 0.2
        )
        self.spin_wait_before.valueChanged.connect(self._on_wait_before_changed)
        common_layout.addRow(Strings.WAIT_BEFORE, self.spin_wait_before)
        self.wait_before_chips = self._create_wait_chips(self.spin_wait_before)
        common_layout.addRow(self.wait_before_chips)

        self.container_layout.addWidget(common_box)

        # 2. Type-Specific Settings
        type_name = (
            action_type_label(action.type)
            if get_current_language() == "ko"
            else action.type.capitalize()
        )
        act_box = QGroupBox(Strings.PARAMETERS_TITLE.format(type=type_name))
        act_layout = QFormLayout(act_box)

        if action.type == "click":
            # Target Mode (Coordinates vs UI Selector)
            self.cmb_target_mode = QComboBox()
            self.cmb_target_mode.addItem(Strings.TARGET_MODE_COORDS, "coordinates")
            self.cmb_target_mode.addItem(Strings.TARGET_MODE_SELECTOR, "selector")
            idx_tmode = 1 if action.target_mode == "selector" else 0
            self.cmb_target_mode.setCurrentIndex(idx_tmode)
            act_layout.addRow(Strings.TARGET_MODE_LABEL, self.cmb_target_mode)

            # Click Method (Hardware SendInput vs Simulate Click)
            self.cmb_click_method = QComboBox()
            self.cmb_click_method.addItem(Strings.CLICK_METHOD_HARDWARE, "hardware")
            self.cmb_click_method.addItem(Strings.CLICK_METHOD_SIMULATE, "simulate")
            idx_cmethod = 1 if action.click_method == "simulate" else 0
            self.cmb_click_method.setCurrentIndex(idx_cmethod)
            act_layout.addRow(Strings.CLICK_METHOD_LABEL, self.cmb_click_method)

            # UI Selector Configuration Group
            self.selector_box = QGroupBox("🎯 UI Element Selector")
            sel_layout = QFormLayout(self.selector_box)

            h_sel_btns = QHBoxLayout()
            btn_pick_elem = QPushButton(Strings.PICK_UI_ELEMENT)
            btn_pick_elem.setToolTip(Strings.Tooltips.PICK_UI_ELEMENT)
            btn_pick_elem.clicked.connect(self.request_pick_element.emit)

            btn_val_sel = QPushButton(Strings.VALIDATE_SELECTOR)
            btn_val_sel.clicked.connect(lambda: self.request_validate_selector.emit(action))
            h_sel_btns.addWidget(btn_pick_elem)
            h_sel_btns.addWidget(btn_val_sel)
            sel_layout.addRow(h_sel_btns)

            sel_dict = action.selector or {}
            self.txt_sel_win = QLineEdit(str(sel_dict.get("window_title") or ""))
            self.txt_sel_win.setPlaceholderText("e.g. SAP*, Order Entry*")
            self.txt_sel_type = QLineEdit(str(sel_dict.get("control_type") or ""))
            self.txt_sel_type.setPlaceholderText("e.g. Button, Edit")
            self.txt_sel_aid = QLineEdit(str(sel_dict.get("automation_id") or ""))
            self.txt_sel_aid.setPlaceholderText("Control / Automation ID")
            self.txt_sel_name = QLineEdit(str(sel_dict.get("name") or ""))
            self.txt_sel_name.setPlaceholderText("Button text or {Column}")
            self.txt_sel_cls = QLineEdit(str(sel_dict.get("class_name") or ""))
            self.txt_sel_cls.setPlaceholderText("Win32 Class Name")

            def _sync_selector() -> None:
                if action.selector is None:
                    action.selector = {}
                action.selector["window_title"] = self.txt_sel_win.text().strip()
                action.selector["control_type"] = self.txt_sel_type.text().strip()
                action.selector["automation_id"] = self.txt_sel_aid.text().strip()
                action.selector["name"] = self.txt_sel_name.text().strip()
                action.selector["class_name"] = self.txt_sel_cls.text().strip()
                if any(action.selector.get(k) for k in ("window_title", "name", "automation_id", "class_name")):
                    action.target_mode = "selector"
                    if self.cmb_target_mode.currentIndex() != 1:
                        self.cmb_target_mode.blockSignals(True)
                        self.cmb_target_mode.setCurrentIndex(1)
                        self.cmb_target_mode.blockSignals(False)
                self.property_changed.emit()

            self.txt_sel_win.textChanged.connect(lambda _: _sync_selector())
            self.txt_sel_type.textChanged.connect(lambda _: _sync_selector())
            self.txt_sel_aid.textChanged.connect(lambda _: _sync_selector())
            self.txt_sel_name.textChanged.connect(lambda _: _sync_selector())
            self.txt_sel_cls.textChanged.connect(lambda _: _sync_selector())

            sel_layout.addRow(Strings.SELECTOR_WINDOW_TITLE, self.txt_sel_win)
            sel_layout.addRow(Strings.SELECTOR_CONTROL_TYPE, self.txt_sel_type)
            sel_layout.addRow(Strings.SELECTOR_AUTOMATION_ID, self.txt_sel_aid)
            sel_layout.addRow(Strings.SELECTOR_NAME, self.txt_sel_name)
            sel_layout.addRow(Strings.SELECTOR_CLASS_NAME, self.txt_sel_cls)

            self.selector_box.setVisible(action.target_mode == "selector")

            def _on_tmode_changed(_idx: int) -> None:
                mode_val = self.cmb_target_mode.currentData()
                action.target_mode = mode_val
                if self.selector_box:
                    self.selector_box.setVisible(mode_val == "selector")
                self.property_changed.emit()

            def _on_cmethod_changed(_idx: int) -> None:
                action.click_method = self.cmb_click_method.currentData()
                self.property_changed.emit()

            self.cmb_target_mode.currentIndexChanged.connect(_on_tmode_changed)
            self.cmb_click_method.currentIndexChanged.connect(_on_cmethod_changed)

            # Coordinates row
            h_coords = QHBoxLayout()
            self.spin_x = QSpinBox()
            self.spin_x.setRange(-99999, 99999)
            self.spin_x.setValue(action.x)
            self.spin_x.valueChanged.connect(
                lambda v: setattr(action, "x", v) or self.property_changed.emit()
            )

            self.spin_y = QSpinBox()
            self.spin_y.setRange(-99999, 99999)
            self.spin_y.setValue(action.y)
            self.spin_y.valueChanged.connect(
                lambda v: setattr(action, "y", v) or self.property_changed.emit()
            )

            btn_pick = QPushButton(Strings.PICK_COORDS)
            btn_pick.setToolTip(Strings.Tooltips.PICK_COORDS)
            btn_pick.clicked.connect(self.request_pick.emit)

            h_coords.addWidget(QLabel("X:"))
            h_coords.addWidget(self.spin_x)
            h_coords.addWidget(QLabel("Y:"))
            h_coords.addWidget(self.spin_y)
            h_coords.addWidget(btn_pick)
            act_layout.addRow(Strings.COORDINATES_LABEL, h_coords)

            h_helpers = QHBoxLayout()
            btn_show = QPushButton("📍 " + Strings.SHOW_ON_SCREEN)
            btn_show.setToolTip(Strings.Tooltips.SHOW_ON_SCREEN)
            btn_show.clicked.connect(lambda: self.request_show_crosshair.emit(action.x, action.y))

            btn_locate = QPushButton(Strings.BTN_LOCATE_TARGET)
            btn_locate.setToolTip(Strings.LOCATE_TOOLTIP)
            btn_locate.clicked.connect(lambda: self.request_locate_target.emit(action))
            self.btn_locate = btn_locate

            h_helpers.addWidget(btn_show)
            h_helpers.addWidget(btn_locate)
            act_layout.addRow(Strings.ACTION_TOOLS_LABEL, h_helpers)

            self.cmb_button = QComboBox()
            self.cmb_button.addItems(["left", "right", "middle"])
            self.cmb_button.setCurrentText(action.button)
            self.cmb_button.currentTextChanged.connect(
                lambda v: setattr(action, "button", v) or self.property_changed.emit()
            )
            act_layout.addRow(Strings.BUTTON, self.cmb_button)

            self.spin_clicks = QSpinBox()
            self.spin_clicks.setRange(1, 2)
            self.spin_clicks.setValue(action.clicks)
            self.spin_clicks.valueChanged.connect(
                lambda v: setattr(action, "clicks", v) or self.property_changed.emit()
            )
            act_layout.addRow(Strings.CLICKS, self.spin_clicks)

            act_layout.addRow(self.selector_box)

        elif action.type == "type_text":
            self.txt_text = QLineEdit(action.text)
            self.txt_text.setPlaceholderText("Enter text or {ColumnName}")

            system_vars = ["{TODAY}", "{NOW}", "{ROW_NUM}"]
            all_vars = [f"{{{h}}}" for h in self._available_headers] + system_vars
            completer = QCompleter(all_vars, self.txt_text)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.txt_text.setCompleter(completer)

            act_layout.addRow(Strings.TEXT_TO_TYPE, self.txt_text)

            # Column insertion chips
            self.chips_widget = self._create_column_chips_widget(action)
            act_layout.addRow(Strings.DATA_CHIP_LABEL, self.chips_widget)

            # Live 1st-row preview & Korean typing nudge
            t = get_theme_tokens()
            self.lbl_row_preview = QLabel()
            self.lbl_row_preview.setWordWrap(True)
            self.lbl_row_preview.setStyleSheet(
                f"QLabel {{ background-color: {t['bg_alt']}; color: {t['text']}; "
                f"border: 1px solid {t['border']}; border-radius: 4px; padding: 4px 8px; font-size: 11px; }}"
            )
            act_layout.addRow(Strings.ROW_PREVIEW_PREFIX, self.lbl_row_preview)

            self.lbl_hangeul_hint = QLabel(Strings.KOREAN_IME_NUDGE)
            self.lbl_hangeul_hint.setWordWrap(True)
            self.lbl_hangeul_hint.setStyleSheet(f"font-size: 11px; color: {t['accent']}; font-weight: 500;")
            act_layout.addRow("", self.lbl_hangeul_hint)

            def _on_txt_changed(v: str) -> None:
                action.text = v
                self._update_text_preview(action)
                self.property_changed.emit()

            self.txt_text.textChanged.connect(_on_txt_changed)

            self.cmb_mode = QComboBox()
            self.cmb_mode.addItem(Strings.MODE_PASTE, "paste")
            self.cmb_mode.addItem(Strings.MODE_KEYSTROKES, "keystrokes")
            self.cmb_mode.setCurrentIndex(0 if action.mode == "paste" else 1)

            def _on_mode_changed(_idx: int) -> None:
                action.mode = str(self.cmb_mode.currentData() or "paste")
                self._update_text_preview(action)
                self.property_changed.emit()

            self.cmb_mode.currentIndexChanged.connect(_on_mode_changed)
            act_layout.addRow(Strings.TYPE_MODE, self.cmb_mode)

            self.chk_select_all = QCheckBox(Strings.SELECT_ALL_FIRST)
            self.chk_select_all.setChecked(action.select_all_first)
            self.chk_select_all.toggled.connect(
                lambda v: setattr(action, "select_all_first", v) or self.property_changed.emit()
            )
            act_layout.addRow(self.chk_select_all)

            self._update_text_preview(action)

        elif action.type == "key":
            self.txt_keys = QLineEdit(action.keys)
            self.txt_keys.setPlaceholderText("e.g. enter, tab, ctrl+s, esc")
            act_layout.addRow(Strings.KEYS_TO_PRESS, self.txt_keys)

            t = get_theme_tokens()
            self.lbl_key_warning = QLabel(Strings.KEY_UNKNOWN_WARNING)
            self.lbl_key_warning.setWordWrap(True)
            self.lbl_key_warning.setStyleSheet(
                f"font-size: 11px; color: {t['status_fail']}; font-weight: 500;"
            )
            act_layout.addRow("", self.lbl_key_warning)

            self.key_chips = QWidget()
            key_grid = QGridLayout(self.key_chips)
            key_grid.setContentsMargins(0, 0, 0, 0)
            key_grid.setSpacing(4)
            for idx, (label, value) in enumerate(KEY_PRESETS):
                chip = self._make_chip(f"[{label}]")
                chip.clicked.connect(lambda _checked=False, v=value: self.txt_keys.setText(v))
                key_grid.addWidget(chip, idx // CHIPS_PER_ROW, idx % CHIPS_PER_ROW)
            act_layout.addRow(self.key_chips)

            def _on_keys_changed(v: str) -> None:
                action.keys = v
                self._update_key_warning(v)
                self.property_changed.emit()

            self.txt_keys.textChanged.connect(_on_keys_changed)
            self._update_key_warning(action.keys)

            self.spin_repeat = QSpinBox()
            self.spin_repeat.setRange(1, 100)
            self.spin_repeat.setValue(action.repeat)
            self.spin_repeat.valueChanged.connect(
                lambda v: setattr(action, "repeat", v) or self.property_changed.emit()
            )
            act_layout.addRow(Strings.REPEAT_COUNT, self.spin_repeat)

        elif action.type == "wait":
            self.spin_wait = QDoubleSpinBox()
            self.spin_wait.setRange(0.01, 3600.0)
            self.spin_wait.setValue(action.seconds)
            self.spin_wait.valueChanged.connect(
                lambda v: setattr(action, "seconds", v) or self.property_changed.emit()
            )
            act_layout.addRow(Strings.WAIT_SECONDS, self.spin_wait)
            self.wait_chips = self._create_wait_chips(self.spin_wait)
            act_layout.addRow(self.wait_chips)

        elif action.type in ("click_image", "wait_image", "wait_image_gone"):
            h_img = QHBoxLayout()
            self.txt_image = QLineEdit(action.image or "")
            self.txt_image.textChanged.connect(
                lambda v: setattr(action, "image", v) or self.property_changed.emit()
            )
            btn_cap = QPushButton(Strings.CAPTURE_IMAGE)
            btn_cap.setToolTip(Strings.Tooltips.CAPTURE_IMAGE)
            btn_cap.clicked.connect(self.request_capture.emit)
            h_img.addWidget(self.txt_image)
            h_img.addWidget(btn_cap)
            act_layout.addRow(Strings.IMAGE_PATH, h_img)

            self.spin_timeout = QDoubleSpinBox()
            self.spin_timeout.setRange(0.1, 300.0)
            self.spin_timeout.setValue(action.timeout)
            self.spin_timeout.valueChanged.connect(
                lambda v: setattr(action, "timeout", v) or self.property_changed.emit()
            )
            act_layout.addRow(Strings.TIMEOUT_SEC, self.spin_timeout)

            btn_test_match = QPushButton(Strings.TEST_MATCH)
            btn_test_match.setToolTip(Strings.Tooltips.TEST_MATCH)
            btn_test_match.clicked.connect(lambda: self.request_test_match.emit(action))
            act_layout.addRow(btn_test_match)

        elif action.type == "group":
            self.txt_group_name = QLineEdit(action.name)
            self.txt_group_name.textChanged.connect(
                lambda v: setattr(action, "name", v) or self.property_changed.emit()
            )
            act_layout.addRow(Strings.GROUP_NAME, self.txt_group_name)

        elif action.type == "window_set_bounds":
            h_title = QHBoxLayout()
            self.txt_win_title = QLineEdit(action.window_title)
            self.txt_win_title.setPlaceholderText("Target window title (e.g. SAP, Excel, Chrome)")
            self.txt_win_title.textChanged.connect(
                lambda v: setattr(action, "window_title", v) or self.property_changed.emit()
            )

            btn_refresh_wins = QPushButton(Strings.WINDOW_PICK_BUTTON)
            btn_refresh_wins.setToolTip(Strings.WINDOW_PICK_TOOLTIP)

            def _pick_win_dialog() -> None:
                from PySide6.QtWidgets import QInputDialog, QMessageBox

                from stepwise.services.window_win import list_visible_windows

                if self.before_prompt is not None:
                    self.before_prompt()
                wins = list_visible_windows(exclude_self=True)
                titles = [t for _, t in wins if t.strip()]
                if not titles:
                    QMessageBox.information(
                        self,
                        "No Windows Found",
                        "No other visible application windows were detected.",
                    )
                    return
                chosen, ok = QInputDialog.getItem(
                    self, "Select Window", "Choose active application window:", titles, 0, False
                )
                if ok and chosen:
                    self.txt_win_title.setText(chosen)

            btn_refresh_wins.clicked.connect(_pick_win_dialog)
            h_title.addWidget(self.txt_win_title)
            h_title.addWidget(btn_refresh_wins)
            act_layout.addRow(Strings.WINDOW_TITLE_LABEL, h_title)

            h_pos = QHBoxLayout()
            self.spin_win_x = QSpinBox()
            self.spin_win_x.setRange(-9999, 9999)
            self.spin_win_x.setValue(action.window_x)
            self.spin_win_x.valueChanged.connect(
                lambda v: setattr(action, "window_x", v) or self.property_changed.emit()
            )

            self.spin_win_y = QSpinBox()
            self.spin_win_y.setRange(-9999, 9999)
            self.spin_win_y.setValue(action.window_y)
            self.spin_win_y.valueChanged.connect(
                lambda v: setattr(action, "window_y", v) or self.property_changed.emit()
            )

            h_pos.addWidget(QLabel("X:"))
            h_pos.addWidget(self.spin_win_x)
            h_pos.addWidget(QLabel("Y:"))
            h_pos.addWidget(self.spin_win_y)
            act_layout.addRow(Strings.WINDOW_POS_LABEL, h_pos)

            h_size = QHBoxLayout()
            self.spin_win_w = QSpinBox()
            self.spin_win_w.setRange(100, 9999)
            self.spin_win_w.setValue(action.window_width)
            self.spin_win_w.valueChanged.connect(
                lambda v: setattr(action, "window_width", v) or self.property_changed.emit()
            )

            self.spin_win_h = QSpinBox()
            self.spin_win_h.setRange(100, 9999)
            self.spin_win_h.setValue(action.window_height)
            self.spin_win_h.valueChanged.connect(
                lambda v: setattr(action, "window_height", v) or self.property_changed.emit()
            )

            h_size.addWidget(QLabel("Width:"))
            h_size.addWidget(self.spin_win_w)
            h_size.addWidget(QLabel("Height:"))
            h_size.addWidget(self.spin_win_h)
            act_layout.addRow(Strings.WINDOW_SIZE_LABEL, h_size)

            self.chk_win_max = QCheckBox(Strings.WINDOW_MAXIMIZE_LABEL)
            self.chk_win_max.setChecked(action.window_maximize)
            self.chk_win_max.toggled.connect(
                lambda v: setattr(action, "window_maximize", v) or self.property_changed.emit()
            )
            act_layout.addRow("Mode:", self.chk_win_max)

        self.container_layout.addWidget(act_box)

        # 3. Guard & Verify Visual Safety Checks (for non-image, non-group actions)
        if action.type not in ("click_image", "wait_image", "wait_image_gone", "group"):
            # Advanced: folded unless this step already uses Guard/Verify. Folding only
            # hides the editors; action.guard / action.verify are left untouched.
            expanded = action.guard is not None or action.verify is not None
            self.btn_safety_toggle = QPushButton()
            self.btn_safety_toggle.setCheckable(True)
            self.btn_safety_toggle.setChecked(expanded)
            self.btn_safety_toggle.setStyleSheet("text-align: left; padding: 4px 8px;")
            self.btn_safety_toggle.setToolTip(Strings.ADVANCED_SAFETY_TOGGLE_TIP)
            self.container_layout.addWidget(self.btn_safety_toggle)

            safety_box = QGroupBox(Strings.SAFETY_BOX_TITLE)
            self.safety_box = safety_box
            safety_layout = QFormLayout(safety_box)

            self.txt_guard_image = QLineEdit(action.guard.image if action.guard else "")
            self.txt_guard_image.setPlaceholderText(Strings.GUARD_PLACEHOLDER)

            def _on_guard_text(val: str) -> None:
                v = val.strip()
                if not v:
                    action.guard = None
                elif action.guard is not None:
                    action.guard.image = v
                else:
                    action.guard = ImageCondition(image=v)
                self.property_changed.emit()

            self.txt_guard_image.textChanged.connect(_on_guard_text)
            safety_layout.addRow(Strings.GUARD_SECTION, self.txt_guard_image)

            self.txt_verify_image = QLineEdit(action.verify.image if action.verify else "")
            self.txt_verify_image.setPlaceholderText(Strings.VERIFY_PLACEHOLDER)

            def _on_verify_text(val: str) -> None:
                v = val.strip()
                if not v:
                    action.verify = None
                elif action.verify is not None:
                    action.verify.image = v
                else:
                    action.verify = ImageCondition(image=v)
                self.property_changed.emit()

            self.txt_verify_image.textChanged.connect(_on_verify_text)
            safety_layout.addRow(Strings.VERIFY_SECTION, self.txt_verify_image)

            self.container_layout.addWidget(safety_box)

            def _set_safety_expanded(checked: bool) -> None:
                arrow = "▾" if checked else "▸"
                self.btn_safety_toggle.setText(f"{arrow} {Strings.ADVANCED_SAFETY_TOGGLE}")
                safety_box.setVisible(checked)

            self.btn_safety_toggle.toggled.connect(_set_safety_expanded)
            _set_safety_expanded(expanded)

        # 4. Action Buttons (Test this step)
        btn_layout = QHBoxLayout()
        btn_test = QPushButton(Strings.TEST_THIS_STEP)
        btn_test.setToolTip(Strings.Tooltips.TEST_THIS_STEP)
        btn_test.clicked.connect(lambda: self.request_test_step.emit(action))
        btn_layout.addWidget(btn_test)
        self.container_layout.addLayout(btn_layout)

        self.container_layout.addStretch()

    def _make_chip(self, text: str) -> QPushButton:
        t = get_theme_tokens()
        chip = QPushButton(text)
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.setMinimumWidth(0)
        chip.setStyleSheet(
            f"QPushButton {{ background-color: {t['chip_bg']}; color: {t['chip_fg']}; "
            f"border: 1px solid {t['chip_border']}; border-radius: 10px; padding: 1px 3px; font-size: 11px; }} "
            f"QPushButton:hover {{ background-color: {t['bg_hover']}; }}"
        )
        return chip

    def _create_wait_chips(self, spin: QDoubleSpinBox) -> QWidget:
        """One-click [0.5s] [1s] [2s] [3s] presets that set the given spin box."""
        widget = QWidget()
        grid = QGridLayout(widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        for idx, seconds in enumerate(WAIT_PRESETS):
            label = Strings.WAIT_CHIP.format(seconds=f"{seconds:g}")
            chip = self._make_chip(f"[{label}]")
            chip.clicked.connect(lambda _checked=False, v=seconds: spin.setValue(v))
            grid.addWidget(chip, 0, idx)
        return widget

    def _update_key_warning(self, keys: str) -> None:
        label = getattr(self, "lbl_key_warning", None)
        if label is not None:
            label.setVisible(bool(keys.strip()) and not is_valid_key_combination(keys))

    def _on_enabled_toggled(self, checked: bool) -> None:
        if self._current_action:
            self._current_action.enabled = checked
            self.property_changed.emit()

    def _on_note_changed(self, text: str) -> None:
        if self._current_action:
            self._current_action.note = text.strip()
            self.property_changed.emit()

    def _on_wait_before_changed(self, val: float) -> None:
        if self._current_action:
            self._current_action.wait_before = val
            self.property_changed.emit()

    def _create_column_chips_widget(self, action: ActionItem) -> QWidget:
        """Create container of clickable pill chips for inserting column variables."""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._populate_column_chips(widget, action)
        return widget

    def _populate_column_chips(self, container: QWidget, action: ActionItem) -> None:
        """Populate column pill chips in a multi-row grid so panel width does not expand."""
        layout = container.layout()
        if not isinstance(layout, QGridLayout):
            return

        # Clear existing items
        while layout.count() > 0:
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.chip_buttons = []
        t = get_theme_tokens()

        if self._available_headers:
            # Multi-row grid layout: up to 3 columns per row to strictly fit 320px panel
            cols_per_row = 3
            for idx, h in enumerate(self._available_headers[:9]):
                btn = QPushButton(f"+ {{{h}}}")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {t['chip_bg']}; color: {t['chip_fg']}; "
                    f"border: 1px solid {t['chip_border']}; border-radius: 10px; padding: 2px 6px; font-size: 11px; }} "
                    f"QPushButton:hover {{ background-color: {t['bg_hover']}; }}"
                )
                btn.clicked.connect(lambda _checked=False, col=h: self._insert_column_token(col))
                self.chip_buttons.append(btn)
                r = idx // cols_per_row
                c = idx % cols_per_row
                layout.addWidget(btn, r, c)
        else:
            nudge_btn = QPushButton(Strings.DATA_NO_FILE_NUDGE)
            nudge_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {t['accent']}; "
                f"border: none; text-align: left; font-size: 11px; text-decoration: underline; }}"
            )
            nudge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            nudge_btn.clicked.connect(self.request_open_data_file.emit)
            layout.addWidget(nudge_btn, 0, 0, 1, 3)

    def _insert_column_token(self, column_name: str) -> None:
        """Insert {column_name} at current cursor position in txt_text."""
        editor = getattr(self, "txt_text", None)
        if editor is not None:
            editor.insert(f"{{{column_name}}}")
            # The textChanged handler may rebuild the editor; only focus a live one.
            if self.txt_text is editor:
                editor.setFocus()

    def _update_text_preview(self, action: ActionItem) -> None:
        """Update live sample preview and Korean IME recommendations."""
        if not hasattr(self, "lbl_row_preview") or self.lbl_row_preview is None:
            return

        raw_text = self.txt_text.text() if self.txt_text is not None else action.text
        if not raw_text:
            self.lbl_row_preview.setText(Strings.PREVIEW_EMPTY_TEXT)
            if self.lbl_hangeul_hint is not None:
                self.lbl_hangeul_hint.hide()
            return

        # Resolve variables against sample row
        try:
            resolved = substitute_variables(raw_text, self._sample_row, strict=False)
        except Exception:
            resolved = raw_text

        if self._sample_row:
            self.lbl_row_preview.setText(f"{resolved}")
        else:
            self.lbl_row_preview.setText(Strings.PREVIEW_NO_DATA_TEXT.format(text=raw_text))

        # Korean IME nudge check
        has_korean = bool(re.search(r"[\uac00-\ud7a3]", raw_text + resolved))
        if self.lbl_hangeul_hint is not None:
            self.lbl_hangeul_hint.setVisible(has_korean and action.mode == "keystrokes")

    def update_variable_completions(
        self, headers: list[str], sample_row: dict[str, str] | None = None
    ) -> None:
        """Update available variable completions, column pill chips, and sample preview."""
        self._available_headers = headers
        if sample_row is not None:
            self._sample_row = sample_row

        # Dynamically rebuild chip pills if editor is currently open on a type_text action
        if self.chips_widget and self._current_action and self._current_action.type == "type_text":
            self._populate_column_chips(self.chips_widget, self._current_action)

        if hasattr(self, "txt_text") and self.txt_text is not None:
            system_vars = ["{TODAY}", "{NOW}", "{ROW_NUM}"]
            all_vars = [f"{{{h}}}" for h in headers] + system_vars
            completer = QCompleter(all_vars, self.txt_text)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.txt_text.setCompleter(completer)

            if self._current_action and self._current_action.type == "type_text":
                self._update_text_preview(self._current_action)
