"""Action tree model and view implementing Section 12.2 specifications.

Displays 3 sections (Setup / Per Row / Cleanup) in a unified tree view with:
- Sibling reordering with buttons and tree-scoped shortcuts
- Enabled checkboxes
- Sentence-style Target summaries (including UI Selector & Simulate Click badges)
- Live running highlight and auto-scroll
- Search & filter capabilities
- Theme-token aware rendering (Dark / Light)
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stepwise.core.models import ActionItem, Macro
from stepwise.ui.strings import Strings, action_type_label, get_current_language
from stepwise.ui.theme import get_theme_tokens


def _missing_input_warning(action: ActionItem) -> str | None:
    """Friendly hint for a step that cannot run yet (Korean UI only)."""
    if action.type == "type_text" and not action.text:
        return Strings.STEP_WARN_EMPTY_TEXT
    if action.type == "key" and not action.keys.strip():
        return Strings.STEP_WARN_EMPTY_KEYS
    if action.type in ("click_image", "wait_image", "wait_image_gone") and not action.image:
        return Strings.STEP_WARN_EMPTY_IMAGE
    return None


def format_action_target(action: ActionItem) -> str:
    """Generate human-readable sentence-style target string.

    English output keeps its long-standing wording; Korean adds hints for
    steps that are not configured yet.
    """
    if get_current_language() == "ko":
        warning = _missing_input_warning(action)
        if warning:
            return warning
    if action.type == "click":
        mouse = {
            "left": Strings.MOUSE_LEFT,
            "right": Strings.MOUSE_RIGHT,
            "middle": Strings.MOUSE_MIDDLE,
        }.get(action.button, action.button)
        button = Strings.SUMMARY_BUTTON.format(button=mouse) if action.button != "left" else ""
        double = Strings.SUMMARY_DOUBLE if action.clicks == 2 else ""
        sim = Strings.SUMMARY_SIM_BADGE if action.click_method == "simulate" else ""
        if action.target_mode == "selector" and action.selector:
            sel = action.selector
            ident = (
                sel.get("name")
                or sel.get("automation_id")
                or sel.get("class_name")
                or sel.get("window_title")
                or Strings.SUMMARY_TARGET
            )
            return Strings.SUMMARY_CLICK_SELECTOR.format(
                sim=sim,
                double=double,
                control=sel.get("control_type") or Strings.SUMMARY_ELEMENT,
                ident=ident,
                button=button,
            )
        return Strings.SUMMARY_CLICK_XY.format(
            sim=sim, double=double, x=action.x, y=action.y, button=button
        )
    if action.type == "click_image":
        return Strings.SUMMARY_CLICK_IMAGE.format(image=action.image or "")
    if action.type == "type_text":
        preview = action.text if len(action.text) <= 25 else action.text[:22] + "..."
        mode = Strings.SUMMARY_TYPE_KEYSTROKES if action.mode == "keystrokes" else ""
        return Strings.SUMMARY_TYPE.format(text=preview, mode=mode)
    if action.type == "key":
        repeat = (
            Strings.SUMMARY_KEY_REPEAT.format(count=action.repeat) if action.repeat > 1 else ""
        )
        return Strings.SUMMARY_KEY.format(keys=action.keys, repeat=repeat)
    if action.type == "wait":
        return Strings.SUMMARY_WAIT.format(seconds=action.seconds)
    if action.type == "wait_image":
        return Strings.SUMMARY_WAIT_IMAGE.format(
            image=action.image or "", timeout=int(action.timeout)
        )
    if action.type == "wait_image_gone":
        return Strings.SUMMARY_WAIT_IMAGE_GONE.format(image=action.image or "")
    if action.type == "window_set_bounds":
        title = action.window_title if action.window_title.strip() else Strings.SUMMARY_NO_WINDOW
        if action.window_maximize:
            return Strings.SUMMARY_WINDOW_MAXIMIZE.format(title=title)
        return Strings.SUMMARY_WINDOW_BOUNDS.format(
            title=title,
            x=action.window_x,
            y=action.window_y,
            width=action.window_width,
            height=action.window_height,
        )
    if action.type == "group":
        return Strings.SUMMARY_GROUP.format(name=action.name, count=len(action.items))
    return action.type


class ActionTreeWidget(QWidget):
    action_selected = Signal(object)  # ActionItem | None
    macro_modified = Signal()
    request_add_action = Signal(str, str, int, object)  # type, section, index, parent group
    request_move_section = Signal(object, str)  # (action_item, target_section_name)
    request_delete_action = Signal(object)  # (action_item)
    request_delete_actions = Signal(list)  # list[ActionItem]
    request_duplicate_action = Signal(object)  # (action_item)
    request_copy_actions = Signal(list)  # list[ActionItem]
    request_cut_actions = Signal(list)  # list[ActionItem]
    request_paste_actions = Signal()
    request_move_up = Signal(object)  # (action_item)
    request_move_down = Signal(object)  # (action_item)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._macro: Macro | None = None
        self._is_compact = False
        self._search_query = ""
        self._filter_mode = "all"
        self._data_row_count = 0
        self._highlighted_item: QTreeWidgetItem | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Search and Compact bar
        bar_layout = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(Strings.SEARCH_ACTIONS)
        self.txt_search.textChanged.connect(self._on_search_changed)

        self.chk_compact = QCheckBox(Strings.COMPACT_VIEW)
        self.chk_compact.toggled.connect(self._on_compact_toggled)

        bar_layout.addWidget(self.txt_search)
        bar_layout.addWidget(self.chk_compact)
        layout.addLayout(bar_layout)

        # Real-time insertion target indicator banner
        self.lbl_target = QLabel()
        self.lbl_target.setTextFormat(Qt.TextFormat.PlainText)
        self._apply_banner_style()
        layout.addWidget(self.lbl_target)

        # Tree Widget
        self.tree = QTreeWidget()
        self._update_headers()
        self.tree.setDragDropMode(QTreeWidget.NoDragDrop)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.setAlternatingRowColors(True)

        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree)

        # Keyboard shortcuts
        self.act_move_up = QAction("Move Up", self)
        self.act_move_up.setShortcut(Qt.Key.Key_Up | Qt.KeyboardModifier.AltModifier)
        self.act_move_up.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.act_move_up.triggered.connect(self._on_shortcut_move_up)
        self.tree.addAction(self.act_move_up)

        self.act_move_down = QAction("Move Down", self)
        self.act_move_down.setShortcut(Qt.Key.Key_Down | Qt.KeyboardModifier.AltModifier)
        self.act_move_down.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.act_move_down.triggered.connect(self._on_shortcut_move_down)
        self.tree.addAction(self.act_move_down)

        self.act_copy = QAction("Copy", self)
        self.act_copy.setShortcut(Qt.Key.Key_C | Qt.KeyboardModifier.ControlModifier)
        self.act_copy.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.act_copy.triggered.connect(self._on_shortcut_copy)
        self.tree.addAction(self.act_copy)

        self.act_cut = QAction("Cut", self)
        self.act_cut.setShortcut(Qt.Key.Key_X | Qt.KeyboardModifier.ControlModifier)
        self.act_cut.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.act_cut.triggered.connect(self._on_shortcut_cut)
        self.tree.addAction(self.act_cut)

        self.act_paste = QAction("Paste", self)
        self.act_paste.setShortcut(Qt.Key.Key_V | Qt.KeyboardModifier.ControlModifier)
        self.act_paste.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.act_paste.triggered.connect(self._on_shortcut_paste)
        self.tree.addAction(self.act_paste)

        self.act_dup = QAction("Duplicate", self)
        self.act_dup.setShortcut(Qt.Key.Key_D | Qt.KeyboardModifier.ControlModifier)
        self.act_dup.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.act_dup.triggered.connect(self._on_shortcut_duplicate)
        self.tree.addAction(self.act_dup)

        self.act_del = QAction("Delete", self)
        self.act_del.setShortcut(Qt.Key.Key_Delete)
        self.act_del.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.act_del.triggered.connect(self._on_shortcut_delete)
        self.tree.addAction(self.act_del)
        self._update_target_label()

    def _apply_banner_style(self) -> None:
        t = get_theme_tokens()
        self.lbl_target.setStyleSheet(
            f"QLabel {{ background-color: {t['banner_bg']}; color: {t['banner_fg']}; "
            f"border: 1px solid {t['border']}; border-radius: 4px; padding: 3px 8px; "
            f"font-weight: 500; font-size: 11px; }}"
        )

    def _update_headers(self) -> None:
        self.tree.setHeaderLabels(
            [
                Strings.COL_NUM,
                Strings.COL_ENABLED,
                Strings.COL_ACTION,
                Strings.COL_TARGET,
                Strings.COL_WAIT,
                Strings.COL_CHECK,
                Strings.COL_NOTE,
            ]
        )

    def retranslate_ui(self) -> None:
        """Refresh strings and theme colors on language or theme switch."""
        self.txt_search.setPlaceholderText(Strings.SEARCH_ACTIONS)
        self.chk_compact.setText(Strings.COMPACT_VIEW)
        self._apply_banner_style()
        self._update_headers()
        self._on_compact_toggled(self._is_compact)
        self.rebuild_tree()

    def _get_selected_action(self) -> ActionItem | None:
        selected = self.tree.selectedItems()
        if not selected:
            curr = self.tree.currentItem()
            if curr:
                data = curr.data(0, Qt.ItemDataRole.UserRole)
                return data if isinstance(data, ActionItem) else None
            return None
        data = selected[0].data(0, Qt.ItemDataRole.UserRole)
        return data if isinstance(data, ActionItem) else None

    def _get_selected_actions(self) -> list[ActionItem]:
        """Return all selected ActionItems in document order."""
        selected_ids = {
            item.data(0, Qt.ItemDataRole.UserRole).id
            for item in self.tree.selectedItems()
            if isinstance(item.data(0, Qt.ItemDataRole.UserRole), ActionItem)
        }
        if not selected_ids:
            curr = self.tree.currentItem()
            if curr and isinstance(curr.data(0, Qt.ItemDataRole.UserRole), ActionItem):
                selected_ids = {curr.data(0, Qt.ItemDataRole.UserRole).id}
            else:
                return []
        if not self._macro:
            return []

        ordered: list[ActionItem] = []

        def walk(items: list[ActionItem]) -> None:
            for act in items:
                if act.id in selected_ids:
                    ordered.append(act)
                    # When a group is selected, its children are already included within it;
                    # do not collect descendants separately to prevent duplicate pasting/deleting.
                else:
                    walk(act.items)

        walk(self._macro.setup)
        walk(self._macro.per_row)
        walk(self._macro.cleanup)
        return ordered

    def _on_shortcut_move_up(self) -> None:
        act = self._get_selected_action()
        if act:
            self.request_move_up.emit(act)

    def _on_shortcut_move_down(self) -> None:
        act = self._get_selected_action()
        if act:
            self.request_move_down.emit(act)

    def _on_shortcut_copy(self) -> None:
        acts = self._get_selected_actions()
        if acts:
            self.request_copy_actions.emit(acts)

    def _on_shortcut_cut(self) -> None:
        acts = self._get_selected_actions()
        if acts:
            self.request_cut_actions.emit(acts)

    def _on_shortcut_paste(self) -> None:
        self.request_paste_actions.emit()

    def _on_shortcut_duplicate(self) -> None:
        act = self._get_selected_action()
        if act:
            self.request_duplicate_action.emit(act)

    def _on_shortcut_delete(self) -> None:
        acts = self._get_selected_actions()
        if len(acts) > 1:
            self.request_delete_actions.emit(acts)
        elif len(acts) == 1:
            self.request_delete_action.emit(acts[0])

    def get_current_target_section(self) -> tuple[str, int]:
        """Return the section and index within the selected item's owning list."""
        section, _, index = self.get_current_insertion_target()
        return section, index

    def get_current_insertion_target(self) -> tuple[str, ActionItem | None, int]:
        """Insert after the selection within its section or immediate parent group."""
        if not self._macro:
            return ("per_row", None, 0)

        selected = self.tree.selectedItems()
        item = selected[0] if selected else self.tree.currentItem()
        if not item:
            return ("per_row", None, len(self._macro.per_row))
        data = item.data(0, Qt.ItemDataRole.UserRole)

        # Header or empty placeholder selected -> insert at index 0 (top of section)
        for section in ("setup", "per_row", "cleanup"):
            if data in (f"header_{section}", f"empty_{section}"):
                return (section, None, 0)

        if isinstance(data, str) and data.startswith("empty_group_"):
            group = item.parent().data(0, Qt.ItemDataRole.UserRole)
            location = self._macro.find_action_location(group)
            if location is not None:
                return (location.section, group, 0)

        if isinstance(data, ActionItem):
            location = self._macro.find_action_location(data)
            if location is not None:
                return (location.section, location.parent, location.index + 1)

        return ("per_row", None, len(self._macro.per_row))

    def _target_display(self, section: str, parent: ActionItem | None) -> str:
        names = []
        while parent is not None and self._macro is not None:
            names.append(parent.name or Strings.TYPE_GROUP)
            location = self._macro.find_action_location(parent)
            parent = location.parent if location is not None else None
        section_display = {
            "setup": Strings.TARGET_SECTION_SETUP,
            "per_row": Strings.TARGET_SECTION_PER_ROW,
            "cleanup": Strings.TARGET_SECTION_CLEANUP,
        }.get(section, section.upper())
        return " / ".join([section_display, *reversed(names)])

    def _update_target_label(self) -> None:
        if not self._macro:
            self.lbl_target.setText(Strings.NO_MACRO_LOADED)
            return

        total_actions = len(self._macro.setup) + len(self._macro.per_row) + len(self._macro.cleanup)
        if total_actions == 0:
            self.lbl_target.setText(Strings.QUICK_START_BANNER)
            return

        sec_name, parent, ins_idx = self.get_current_insertion_target()
        sec_display = self._target_display(sec_name, parent)
        selected = self.tree.selectedItems()
        action = self._get_selected_action()

        if ins_idx == 0:
            target_str = Strings.INSERT_TARGET_TOP.format(section=sec_display)
        elif action is not None and action.type == "group":
            target_str = Strings.INSERT_TARGET_GROUP.format(
                section=sec_display, group=action.name or Strings.TYPE_GROUP
            )
        elif action is not None:
            node = selected[0] if selected else self.tree.currentItem()
            step_text = node.text(0) if node else ""
            target_str = Strings.INSERT_TARGET_AFTER.format(
                section=sec_display, step=step_text
            )
        else:
            target_str = Strings.INSERT_TARGET_END.format(section=sec_display)
        self.lbl_target.setText(f"🎯 {target_str}")

    def _show_context_menu(self, pos: QPoint) -> None:
        item = self.tree.itemAt(pos)
        selected_items = self.tree.selectedItems()
        if item:
            if item not in selected_items:
                self.tree.clearSelection()
                item.setSelected(True)
                self.tree.setCurrentItem(item)
        menu = QMenu(self)

        sec_name, parent, ins_idx = self.get_current_insertion_target()
        selected_acts = self._get_selected_actions()

        # 1. Quick Add Actions
        menu_add = menu.addMenu(
            Strings.CTX_ADD_TO.format(target=self._target_display(sec_name, parent))
        )
        act_add_click = menu_add.addAction(Strings.CTX_ADD_CLICK)
        act_add_click.triggered.connect(
            lambda: self.request_add_action.emit("click", sec_name, ins_idx, parent)
        )

        act_add_type = menu_add.addAction(Strings.CTX_ADD_TYPE)
        act_add_type.triggered.connect(
            lambda: self.request_add_action.emit("type_text", sec_name, ins_idx, parent)
        )

        act_add_key = menu_add.addAction(Strings.CTX_ADD_KEY)
        act_add_key.triggered.connect(
            lambda: self.request_add_action.emit("key", sec_name, ins_idx, parent)
        )

        act_add_wait = menu_add.addAction(Strings.CTX_ADD_WAIT)
        act_add_wait.triggered.connect(
            lambda: self.request_add_action.emit("wait", sec_name, ins_idx, parent)
        )

        menu_add.addSeparator()
        act_add_img = menu_add.addAction(Strings.CTX_ADD_IMAGE)
        act_add_img.triggered.connect(
            lambda: self.request_add_action.emit("click_image", sec_name, ins_idx, parent)
        )

        act_add_win = menu_add.addAction(Strings.CTX_ADD_WINDOW)
        act_add_win.triggered.connect(
            lambda: self.request_add_action.emit("window_set_bounds", sec_name, ins_idx, parent)
        )

        menu.addSeparator()

        # Copy & Cut (enabled if actions selected)
        act_copy = menu.addAction(f"📋 {Strings.COPY}")
        act_copy.setEnabled(bool(selected_acts))
        act_copy.triggered.connect(self._on_shortcut_copy)

        act_cut = menu.addAction(f"✂️ {Strings.CUT}")
        act_cut.setEnabled(bool(selected_acts))
        act_cut.triggered.connect(self._on_shortcut_cut)

        # Paste
        act_paste = menu.addAction(f"📥 {Strings.PASTE}")
        act_paste.triggered.connect(self._on_shortcut_paste)

        if selected_acts:
            menu.addSeparator()
            if len(selected_acts) == 1:
                data = selected_acts[0]
                act_up = menu.addAction(Strings.MOVE_UP)
                act_up.triggered.connect(lambda: self.request_move_up.emit(data))

                act_down = menu.addAction(Strings.MOVE_DOWN)
                act_down.triggered.connect(lambda: self.request_move_down.emit(data))

                menu.addSeparator()
                menu_move_sec = menu.addMenu(Strings.CTX_MOVE_TO_SECTION)
                act_m_setup = menu_move_sec.addAction(Strings.CTX_MOVE_TO_SETUP)
                act_m_setup.triggered.connect(lambda: self.request_move_section.emit(data, "setup"))

                act_m_per = menu_move_sec.addAction(Strings.CTX_MOVE_TO_PER_ROW)
                act_m_per.triggered.connect(lambda: self.request_move_section.emit(data, "per_row"))

                act_m_clean = menu_move_sec.addAction(Strings.CTX_MOVE_TO_CLEANUP)
                act_m_clean.triggered.connect(
                    lambda: self.request_move_section.emit(data, "cleanup")
                )

                menu.addSeparator()
                act_dup = menu.addAction(f"📋 {Strings.DUPLICATE}")
                act_dup.triggered.connect(lambda: self.request_duplicate_action.emit(data))

            act_del = menu.addAction(f"🗑 {Strings.DELETE}")
            act_del.triggered.connect(self._on_shortcut_delete)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def load_macro(self, macro: Macro) -> None:
        """Load and display a macro in the tree."""
        self._macro = macro
        self.rebuild_tree()

    def set_data_row_count(self, count: int) -> None:
        """Update data row count to display loop repetition numbers in PER ROW header."""
        self._data_row_count = max(0, count)
        if self._macro:
            self.rebuild_tree()

    def _add_empty_placeholder(self, parent: QTreeWidgetItem, sec_name: str) -> None:
        t = get_theme_tokens()
        if sec_name == "setup":
            text = Strings.SECTION_SETUP_EMPTY
        elif sec_name == "per_row":
            text = Strings.SECTION_PER_ROW_EMPTY
        elif sec_name == "cleanup":
            text = Strings.SECTION_CLEANUP_EMPTY
        else:
            text = Strings.SECTION_EMPTY_PLACEHOLDER

        placeholder = QTreeWidgetItem(["", "", text, "", "", "", ""])
        placeholder.setData(0, Qt.ItemDataRole.UserRole, f"empty_{sec_name}")
        placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        p_font = QFont()
        p_font.setItalic(True)
        placeholder.setFont(2, p_font)
        for col in range(7):
            placeholder.setForeground(col, QBrush(QColor(t["text_muted"])))
        parent.addChild(placeholder)

    def rebuild_tree(self, select_id: str | list[str] | None = None) -> None:
        """Reconstruct tree nodes from self._macro and restore selection."""
        t = get_theme_tokens()
        target_restore_key: str | list[str] | None = select_id
        if not target_restore_key:
            curr_selected = self.tree.selectedItems()
            if len(curr_selected) > 1:
                keys = []
                for it in curr_selected:
                    d = it.data(0, Qt.ItemDataRole.UserRole)
                    if isinstance(d, ActionItem):
                        keys.append(d.id)
                if keys:
                    target_restore_key = keys
            elif len(curr_selected) == 1:
                d = curr_selected[0].data(0, Qt.ItemDataRole.UserRole)
                if isinstance(d, ActionItem):
                    target_restore_key = d.id
                elif isinstance(d, str):
                    target_restore_key = d

        self.tree.blockSignals(True)
        self._highlighted_item = None
        self.tree.clear()
        if not self._macro:
            self.tree.blockSignals(False)
            self._on_selection_changed()
            return

        step_counter = 1
        sec_bg = QBrush(QColor(t["bg_section"]))
        sec_fg = QBrush(QColor(t["accent"]))

        # Section 1: SETUP
        setup_header = QTreeWidgetItem(["", "", Strings.SECTION_SETUP, "", "", "", ""])
        setup_header.setData(0, Qt.ItemDataRole.UserRole, "header_setup")
        setup_header.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        setup_font = QFont()
        setup_font.setBold(True)
        setup_header.setFont(2, setup_font)
        for col in range(7):
            setup_header.setBackground(col, sec_bg)
            setup_header.setForeground(col, sec_fg)
            setup_header.setToolTip(col, Strings.Tooltips.SECTION_SETUP)
        self.tree.addTopLevelItem(setup_header)

        if not self._macro.setup:
            self._add_empty_placeholder(setup_header, "setup")
        else:
            for act in self._macro.setup:
                step_counter = self._add_action_node(setup_header, act, step_counter)
        setup_header.setExpanded(True)

        # Section 2: PER ROW
        per_row_text = Strings.SECTION_PER_ROW
        per_row_count = len(self._macro.per_row)
        if getattr(self, "_data_row_count", 0) > 0:
            per_row_text += Strings.LOOP_REPETITION_LABEL.format(
                rows=self._data_row_count, steps=per_row_count
            )
        else:
            per_row_text += Strings.BEFORE_DATA_CONNECTED
        per_row_header = QTreeWidgetItem(["", "", per_row_text, "", "", "", ""])
        per_row_header.setData(0, Qt.ItemDataRole.UserRole, "header_per_row")
        per_row_header.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        per_row_header.setFont(2, setup_font)
        for col in range(7):
            per_row_header.setBackground(col, sec_bg)
            per_row_header.setForeground(col, sec_fg)
            per_row_header.setToolTip(col, Strings.Tooltips.SECTION_PER_ROW)
        self.tree.addTopLevelItem(per_row_header)

        if not self._macro.per_row:
            self._add_empty_placeholder(per_row_header, "per_row")
        else:
            for act in self._macro.per_row:
                step_counter = self._add_action_node(per_row_header, act, step_counter)
        per_row_header.setExpanded(True)

        # Section 3: CLEANUP
        cleanup_header = QTreeWidgetItem(["", "", Strings.SECTION_CLEANUP, "", "", "", ""])
        cleanup_header.setData(0, Qt.ItemDataRole.UserRole, "header_cleanup")
        cleanup_header.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        cleanup_header.setFont(2, setup_font)
        for col in range(7):
            cleanup_header.setBackground(col, sec_bg)
            cleanup_header.setForeground(col, sec_fg)
            cleanup_header.setToolTip(col, Strings.Tooltips.SECTION_CLEANUP)
        self.tree.addTopLevelItem(cleanup_header)

        if not self._macro.cleanup:
            self._add_empty_placeholder(cleanup_header, "cleanup")
        else:
            for act in self._macro.cleanup:
                step_counter = self._add_action_node(cleanup_header, act, step_counter)
        cleanup_header.setExpanded(True)

        self._apply_filter()

        # Selection restoration
        nodes_to_select: list[QTreeWidgetItem] = []
        if isinstance(target_restore_key, (list, tuple)):
            for key in target_restore_key:
                node = self._find_node_by_step_id(str(key))
                if node:
                    nodes_to_select.append(node)
        elif target_restore_key:
            if isinstance(target_restore_key, str) and (
                target_restore_key.startswith("header_") or target_restore_key.startswith("empty_")
            ):

                def find_marker(node: QTreeWidgetItem) -> QTreeWidgetItem | None:
                    if node.data(0, Qt.ItemDataRole.UserRole) == target_restore_key:
                        return node
                    for index in range(node.childCount()):
                        found = find_marker(node.child(index))
                        if found is not None:
                            return found
                    return None

                node = find_marker(self.tree.invisibleRootItem())
                if node:
                    nodes_to_select.append(node)
            else:
                node = self._find_node_by_step_id(str(target_restore_key))
                if node:
                    nodes_to_select.append(node)

        if nodes_to_select:
            self.tree.setCurrentItem(nodes_to_select[0])
            for node in nodes_to_select:
                if select_id and node.isHidden():
                    self.txt_search.clear()
                ancestor = node.parent()
                while ancestor is not None:
                    ancestor.setExpanded(True)
                    ancestor = ancestor.parent()
                node.setSelected(True)
            self.tree.scrollToItem(nodes_to_select[0])

        self.tree.blockSignals(False)
        self._on_selection_changed()

    def _add_action_node(self, parent: QTreeWidgetItem, act: ActionItem, counter: int) -> int:
        t = get_theme_tokens()
        text_color = QColor(t["text"]) if act.enabled else QColor(t["text_disabled"])
        if act.type == "group":
            group_item = QTreeWidgetItem(
                [
                    "",
                    "",
                    Strings.TYPE_GROUP,
                    format_action_target(act),
                    "",
                    "",
                    act.note,
                ]
            )
            group_item.setData(0, Qt.UserRole, act)
            group_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            group_item.setCheckState(1, Qt.Checked if act.enabled else Qt.Unchecked)
            for col in range(7):
                group_item.setForeground(col, QBrush(text_color))
            parent.addChild(group_item)
            group_item.setExpanded(not act.collapsed)

            for child in act.items:
                counter = self._add_action_node(group_item, child, counter)
            if not act.items:
                self._add_empty_placeholder(group_item, f"group_{act.id}")
            return counter
        else:
            checks: list[str] = []
            if act.guard:
                checks.append("🛡 Guard")
            if act.verify:
                checks.append("🖼 Verify")
            check_str = " | ".join(checks)

            wait_str = f"{act.wait_before}s" if act.wait_before is not None else ""

            node = QTreeWidgetItem(
                [
                    str(counter),
                    "",
                    action_type_label(act.type),
                    format_action_target(act),
                    wait_str,
                    check_str,
                    act.note,
                ]
            )
            node.setData(0, Qt.UserRole, act)
            node.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            node.setCheckState(1, Qt.Checked if act.enabled else Qt.Unchecked)
            for col in range(7):
                node.setForeground(col, QBrush(text_color))
            parent.addChild(node)
            return counter + 1

    def _on_selection_changed(self) -> None:
        self._update_target_label()
        selected_items = self.tree.selectedItems()
        if not selected_items:
            curr = self.tree.currentItem()
            if curr and curr is not self.tree.invisibleRootItem():
                data = curr.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(data, ActionItem):
                    self.action_selected.emit(data)
                    return
            self.action_selected.emit(None)
            return

        if len(selected_items) == 1:
            data = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, ActionItem):
                self.action_selected.emit(data)
                return
        self.action_selected.emit(None)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column == 1:
            t = get_theme_tokens()
            data = item.data(0, Qt.UserRole)
            if isinstance(data, ActionItem):
                is_checked = item.checkState(1) == Qt.Checked
                data.enabled = is_checked
                text_color = QColor(t["text"]) if is_checked else QColor(t["text_disabled"])
                for col in range(7):
                    item.setForeground(col, QBrush(text_color))
                self.macro_modified.emit()

    def _on_search_changed(self, text: str) -> None:
        self._search_query = text.strip().lower()
        self._apply_filter()

    def _on_compact_toggled(self, checked: bool) -> None:
        self._is_compact = checked
        t = get_theme_tokens()
        padding = "2px" if checked else "5px"
        self.tree.setStyleSheet(
            f"QTreeWidget {{ background-color: {t['bg_base']}; color: {t['text']}; }} "
            f"QTreeWidget::item {{ padding: {padding} 8px; color: {t['text']}; }}"
        )

    def _apply_filter(self) -> None:
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            sec_header = root.child(i)
            self._filter_node(sec_header)

    def _filter_node(self, node: QTreeWidgetItem) -> bool:
        data = node.data(0, Qt.UserRole)
        is_sec_header = isinstance(data, str) and data.startswith("header_")

        child_matches = False
        for c_idx in range(node.childCount()):
            child = node.child(c_idx)
            if self._filter_node(child):
                child_matches = True

        if is_sec_header:
            node.setHidden(not child_matches and node.childCount() > 0)
            return child_matches

        text_matches = True
        if self._search_query:
            combined = f"{node.text(2)} {node.text(3)} {node.text(6)}".lower()
            text_matches = self._search_query in combined

        should_show = text_matches or child_matches
        node.setHidden(not should_show)
        return should_show

    def highlight_step(
        self, step_id: str, is_running: bool = True, is_failed: bool = False
    ) -> None:
        """Highlight current executing or failed step and auto-scroll to center."""
        t = get_theme_tokens()
        if self._highlighted_item:
            self._highlighted_item.setBackground(0, QBrush())
            self._highlighted_item.setBackground(2, QBrush())
            self._highlighted_item.setBackground(3, QBrush())

        node = self._find_node_by_step_id(step_id)
        if node:
            self._highlighted_item = node
            bg_color = (
                QColor(t["highlight_fail_bg"])
                if is_failed
                else QColor(t["highlight_run_bg"])
            )
            node.setBackground(0, QBrush(bg_color))
            node.setBackground(2, QBrush(bg_color))
            node.setBackground(3, QBrush(bg_color))
            self.tree.scrollToItem(node, QTreeWidget.PositionAtCenter)

    def _find_node_by_step_id(self, step_id: str) -> QTreeWidgetItem | None:
        def _search(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            data = item.data(0, Qt.UserRole)
            if isinstance(data, ActionItem) and data.id == step_id:
                return item
            for i in range(item.childCount()):
                res = _search(item.child(i))
                if res:
                    return res
            return None

        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            found = _search(root.child(i))
            if found:
                return found
        return None
