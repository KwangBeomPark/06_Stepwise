"""Action properties panel implementing Section 12.3 specifications.

Provides dynamic, type-specific property editors with:
- Pick (F8) and Capture (F9) triggers
- Universal Guard / Verify collapsible controls
- Variable autocomplete hint on '{'
- Real-time model synchronization
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from stepwise.core.models import ActionItem
from stepwise.ui.strings import Strings


class PropertiesPanel(QWidget):
    property_changed = Signal()
    request_pick = Signal()
    request_capture = Signal()
    request_test_step = Signal(object)
    request_test_match = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_action: ActionItem | None = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Header Title
        title_lbl = QLabel(Strings.PROPERTIES_TITLE)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #1e293b;")
        main_layout.addWidget(title_lbl)

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

        self._build_empty_state()

    def _build_empty_state(self) -> None:
        self._clear_container()
        lbl = QLabel(Strings.NO_ACTION_SELECTED)
        lbl.setStyleSheet("color: #94a3b8; font-style: italic; padding: 20px;")
        lbl.setAlignment(Qt.AlignCenter)
        self.container_layout.addWidget(lbl)
        self.container_layout.addStretch()

    def _clear_container(self) -> None:
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_action(self, action: ActionItem | None) -> None:
        """Bind an ActionItem to the editor."""
        self._current_action = action
        self._clear_container()
        if not action:
            self._build_empty_state()
            return

        # 1. Common Settings
        common_box = QGroupBox("General Options")
        common_layout = QFormLayout(common_box)

        self.chk_enabled = QCheckBox("Action Enabled")
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
        self.spin_wait_before.setValue(action.wait_before if action.wait_before is not None else 0.2)
        self.spin_wait_before.valueChanged.connect(self._on_wait_before_changed)
        common_layout.addRow(Strings.WAIT_BEFORE, self.spin_wait_before)

        self.container_layout.addWidget(common_box)

        # 2. Type-Specific Settings
        act_box = QGroupBox(f"{action.type.capitalize()} Parameters")
        act_layout = QFormLayout(act_box)

        if action.type == "click":
            h_coords = QHBoxLayout()
            self.spin_x = QSpinBox()
            self.spin_x.setRange(0, 9999)
            self.spin_x.setValue(action.x)
            self.spin_x.valueChanged.connect(lambda v: setattr(action, "x", v) or self.property_changed.emit())

            self.spin_y = QSpinBox()
            self.spin_y.setRange(0, 9999)
            self.spin_y.setValue(action.y)
            self.spin_y.valueChanged.connect(lambda v: setattr(action, "y", v) or self.property_changed.emit())

            btn_pick = QPushButton(Strings.PICK_COORDS)
            btn_pick.clicked.connect(self.request_pick.emit)

            h_coords.addWidget(QLabel("X:"))
            h_coords.addWidget(self.spin_x)
            h_coords.addWidget(QLabel("Y:"))
            h_coords.addWidget(self.spin_y)
            h_coords.addWidget(btn_pick)
            act_layout.addRow("Coordinates:", h_coords)

            self.cmb_button = QComboBox()
            self.cmb_button.addItems(["left", "right", "middle"])
            self.cmb_button.setCurrentText(action.button)
            self.cmb_button.currentTextChanged.connect(lambda v: setattr(action, "button", v) or self.property_changed.emit())
            act_layout.addRow(Strings.BUTTON, self.cmb_button)

            self.spin_clicks = QSpinBox()
            self.spin_clicks.setRange(1, 2)
            self.spin_clicks.setValue(action.clicks)
            self.spin_clicks.valueChanged.connect(lambda v: setattr(action, "clicks", v) or self.property_changed.emit())
            act_layout.addRow(Strings.CLICKS, self.spin_clicks)

        elif action.type == "type_text":
            self.txt_text = QLineEdit(action.text)
            self.txt_text.setPlaceholderText("Enter text or {ColumnName}")
            self.txt_text.textChanged.connect(lambda v: setattr(action, "text", v) or self.property_changed.emit())
            act_layout.addRow(Strings.TEXT_TO_TYPE, self.txt_text)

            self.cmb_mode = QComboBox()
            self.cmb_mode.addItems(["paste", "keystrokes"])
            self.cmb_mode.setCurrentText(action.mode)
            self.cmb_mode.currentTextChanged.connect(lambda v: setattr(action, "mode", v) or self.property_changed.emit())
            act_layout.addRow(Strings.TYPE_MODE, self.cmb_mode)

            self.chk_select_all = QCheckBox(Strings.SELECT_ALL_FIRST)
            self.chk_select_all.setChecked(action.select_all_first)
            self.chk_select_all.toggled.connect(lambda v: setattr(action, "select_all_first", v) or self.property_changed.emit())
            act_layout.addRow(self.chk_select_all)

        elif action.type == "key":
            self.txt_keys = QLineEdit(action.keys)
            self.txt_keys.setPlaceholderText("e.g. enter, tab, ctrl+s, esc")
            self.txt_keys.textChanged.connect(lambda v: setattr(action, "keys", v) or self.property_changed.emit())
            act_layout.addRow(Strings.KEYS_TO_PRESS, self.txt_keys)

            self.spin_repeat = QSpinBox()
            self.spin_repeat.setRange(1, 100)
            self.spin_repeat.setValue(action.repeat)
            self.spin_repeat.valueChanged.connect(lambda v: setattr(action, "repeat", v) or self.property_changed.emit())
            act_layout.addRow(Strings.REPEAT_COUNT, self.spin_repeat)

        elif action.type == "wait":
            self.spin_wait = QDoubleSpinBox()
            self.spin_wait.setRange(0.01, 3600.0)
            self.spin_wait.setValue(action.seconds)
            self.spin_wait.valueChanged.connect(lambda v: setattr(action, "seconds", v) or self.property_changed.emit())
            act_layout.addRow(Strings.WAIT_SECONDS, self.spin_wait)

        elif action.type in ("click_image", "wait_image", "wait_image_gone"):
            h_img = QHBoxLayout()
            self.txt_image = QLineEdit(action.image or "")
            self.txt_image.textChanged.connect(lambda v: setattr(action, "image", v) or self.property_changed.emit())
            btn_cap = QPushButton(Strings.CAPTURE_IMAGE)
            btn_cap.clicked.connect(self.request_capture.emit)
            h_img.addWidget(self.txt_image)
            h_img.addWidget(btn_cap)
            act_layout.addRow(Strings.IMAGE_PATH, h_img)

            self.spin_timeout = QDoubleSpinBox()
            self.spin_timeout.setRange(0.1, 300.0)
            self.spin_timeout.setValue(action.timeout)
            self.spin_timeout.valueChanged.connect(lambda v: setattr(action, "timeout", v) or self.property_changed.emit())
            act_layout.addRow(Strings.TIMEOUT_SEC, self.spin_timeout)

            btn_test_match = QPushButton(Strings.TEST_MATCH)
            btn_test_match.clicked.connect(lambda: self.request_test_match.emit(action))
            act_layout.addRow(btn_test_match)

        elif action.type == "group":
            self.txt_group_name = QLineEdit(action.name)
            self.txt_group_name.textChanged.connect(lambda v: setattr(action, "name", v) or self.property_changed.emit())
            act_layout.addRow(Strings.GROUP_NAME, self.txt_group_name)

        self.container_layout.addWidget(act_box)

        # 3. Action Buttons (Test this step)
        btn_layout = QHBoxLayout()
        btn_test = QPushButton(Strings.TEST_THIS_STEP)
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
