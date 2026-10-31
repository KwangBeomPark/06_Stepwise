"""Action properties panel implementing Section 12.3 specifications.

Provides dynamic, type-specific property editors with:
- Pick (F8), Capture (F9), and Pick UI Element (Ctrl+F8) triggers
- UI Selector & Simulate Click configuration and live validation
- Universal Guard / Verify controls
- Variable autocomplete hint on '{'
- Real-time model synchronization & Dark/Light theme support
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QFormLayout,
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
from stepwise.ui.strings import Strings
from stepwise.ui.theme import get_theme_tokens


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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_action: ActionItem | None = None
        self._available_headers: list[str] = []
        self.txt_text: QLineEdit | None = None

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

        self.container_layout.addWidget(common_box)

        # 2. Type-Specific Settings
        act_box = QGroupBox(f"{action.type.capitalize()} Parameters")
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

            btn_test_click = QPushButton("⚡ " + Strings.TEST_THIS_STEP)
            btn_test_click.setToolTip(Strings.Tooltips.TEST_THIS_STEP)
            btn_test_click.clicked.connect(lambda: self.request_test_step.emit(action))

            h_helpers.addWidget(btn_show)
            h_helpers.addWidget(btn_test_click)
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
            self.txt_text.textChanged.connect(
                lambda v: setattr(action, "text", v) or self.property_changed.emit()
            )

            if self._available_headers:
                variables = [f"{{{h}}}" for h in self._available_headers]
                completer = QCompleter(variables, self.txt_text)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                self.txt_text.setCompleter(completer)

            act_layout.addRow(Strings.TEXT_TO_TYPE, self.txt_text)

            btn_test_type = QPushButton("⚡ " + Strings.TEST_THIS_STEP)
            btn_test_type.setToolTip(Strings.Tooltips.TEST_THIS_STEP)
            btn_test_type.clicked.connect(lambda: self.request_test_step.emit(action))
            act_layout.addRow(Strings.ACTION_TOOLS_LABEL, btn_test_type)

            self.cmb_mode = QComboBox()
            self.cmb_mode.addItems(["paste", "keystrokes"])
            self.cmb_mode.setCurrentText(action.mode)
            self.cmb_mode.currentTextChanged.connect(
                lambda v: setattr(action, "mode", v) or self.property_changed.emit()
            )
            act_layout.addRow(Strings.TYPE_MODE, self.cmb_mode)

            self.chk_select_all = QCheckBox(Strings.SELECT_ALL_FIRST)
            self.chk_select_all.setChecked(action.select_all_first)
            self.chk_select_all.toggled.connect(
                lambda v: setattr(action, "select_all_first", v) or self.property_changed.emit()
            )
            act_layout.addRow(self.chk_select_all)

        elif action.type == "key":
            self.txt_keys = QLineEdit(action.keys)
            self.txt_keys.setPlaceholderText("e.g. enter, tab, ctrl+s, esc")
            self.txt_keys.textChanged.connect(
                lambda v: setattr(action, "keys", v) or self.property_changed.emit()
            )
            act_layout.addRow(Strings.KEYS_TO_PRESS, self.txt_keys)

            btn_test_key = QPushButton("⚡ " + Strings.TEST_THIS_STEP)
            btn_test_key.setToolTip(Strings.Tooltips.TEST_THIS_STEP)
            btn_test_key.clicked.connect(lambda: self.request_test_step.emit(action))
            act_layout.addRow(Strings.ACTION_TOOLS_LABEL, btn_test_key)

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
            safety_box = QGroupBox("🛡️ Guard & Verify (Visual Safety)")
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

        # 4. Action Buttons (Test this step)
        btn_layout = QHBoxLayout()
        btn_test = QPushButton(Strings.TEST_THIS_STEP)
        btn_test.setToolTip(Strings.Tooltips.TEST_THIS_STEP)
        btn_test.clicked.connect(lambda: self.request_test_step.emit(action))
        btn_layout.addWidget(btn_test)
        self.container_layout.addLayout(btn_layout)

        self.container_layout.addStretch()

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

    def update_variable_completions(self, headers: list[str]) -> None:
        """Update available variable completions from loaded data columns."""
        self._available_headers = headers
        if hasattr(self, "txt_text") and self.txt_text is not None:
            variables = [f"{{{h}}}" for h in headers]
            completer = QCompleter(variables, self.txt_text)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.txt_text.setCompleter(completer)
