"""UI widget tests using pytest-qt."""

import threading
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication, QMenu

from stepwise.core.models import ActionItem, Macro
from stepwise.ui.action_tree import ActionTreeWidget
from stepwise.ui.data_panel import DataPanel
from stepwise.ui.properties_panel import PropertiesPanel
from stepwise.ui.strings import Strings


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_action_tree_widget_building(qapp: QApplication) -> None:
    tree_widget = ActionTreeWidget()
    macro = Macro(
        name="UI Test Macro",
        setup=[ActionItem(type="wait", seconds=1.0, note="Setup note")],
        per_row=[
            ActionItem(type="click", x=100, y=200, note="Click 1"),
            ActionItem(type="type_text", text="{Vendor}", note="Type vendor"),
        ],
        cleanup=[ActionItem(type="key", keys="esc")],
    )

    tree_widget.load_macro(macro)
    assert tree_widget.tree.topLevelItemCount() == 3

    # Check setup node
    setup_node = tree_widget.tree.topLevelItem(0)
    assert setup_node.childCount() == 1
    assert setup_node.child(0).text(6) == "Setup note"

    # Check per_row node
    per_row_node = tree_widget.tree.topLevelItem(1)
    assert per_row_node.childCount() == 2


def test_properties_panel_binding(qapp: QApplication) -> None:
    prop_panel = PropertiesPanel()
    act = ActionItem(type="click", x=300, y=400, button="right", clicks=2, note="My Click")

    prop_panel.set_action(act)
    assert prop_panel.spin_x.value() == 300
    assert prop_panel.spin_y.value() == 400
    assert prop_panel.cmb_button.currentText() == "right"
    assert prop_panel.spin_clicks.value() == 2

    # Change property
    prop_panel.spin_x.setValue(550)
    assert act.x == 550


def test_data_panel_status_update(qapp: QApplication) -> None:
    panel = DataPanel()
    panel._headers = ["Name", "Amount"]
    panel._rows = [{"Name": "ACME", "Amount": "100"}]
    panel._row_numbers = [1]
    panel._rebuild_table()

    assert panel.table.rowCount() == 1
    assert panel.table.item(0, 1).text() == Strings.STATUS_PENDING

    # Update status
    panel.update_row_status(1, "Done")
    assert panel.table.item(0, 1).text() == "Done"


def test_action_tree_target_section(qapp: QApplication) -> None:
    tree_widget = ActionTreeWidget()
    macro = Macro(
        setup=[ActionItem(type="wait", seconds=1.0)],
        per_row=[ActionItem(type="click", x=50, y=50)],
        cleanup=[],
    )
    tree_widget.load_macro(macro)

    # When nothing selected, defaults to per_row at end
    sec, idx = tree_widget.get_current_target_section()
    assert sec == "per_row"
    assert idx == 1


def test_properties_panel_variable_completions(qapp: QApplication) -> None:
    prop_panel = PropertiesPanel()
    act = ActionItem(type="type_text", text="Initial")
    prop_panel.set_action(act)

    prop_panel.update_variable_completions(["VendorCode", "InvoiceAmount"])
    assert prop_panel._available_headers == ["VendorCode", "InvoiceAmount"]
    assert prop_panel.txt_text is not None


def test_screen_crosshair_overlay(qapp: QApplication) -> None:
    from stepwise.ui.screen_crosshair import ScreenCrosshairOverlay

    class _FakeScreen:
        @staticmethod
        def devicePixelRatio() -> float:
            return 2.0

        @staticmethod
        def geometry() -> QRect:
            return QRect(100, 200, 800, 600)

    with patch(
        "stepwise.ui.screen_crosshair.QApplication.primaryScreen", return_value=_FakeScreen()
    ):
        overlay = ScreenCrosshairOverlay(x=200, y=300, duration_ms=100)

    assert overlay.x() == 150
    assert overlay.y() == 300
    overlay.close()


def test_capture_overlay_maps_logical_selection_to_physical_pixels(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    from stepwise.ui.capture_overlay import CaptureOverlay

    frame = np.zeros((100, 100, 4), dtype=np.uint8)
    with patch("stepwise.ui.capture_overlay.capture_screen", return_value=frame):
        overlay = CaptureOverlay(mode="region", images_dir=str(tmp_path))

    overlay._dpr = 1.5
    rect = QRect(1, 2, 3, 4)
    assert overlay._physical_rect(rect).getRect() == (1, 3, 5, 6)

    captured: list[tuple[str, list[int]]] = []
    overlay.region_captured.connect(lambda path, region: captured.append((path, region)))
    overlay._save_region(rect)

    assert captured[0][1] == [1, 3, 5, 6]
    overlay.close()


def test_capture_overlay_emits_physical_pick_coordinates(
    qapp: QApplication,
    qtbot: object,
    tmp_path: Path,
) -> None:
    from stepwise.ui.capture_overlay import CaptureOverlay

    frame = np.zeros((100, 100, 4), dtype=np.uint8)
    with patch("stepwise.ui.capture_overlay.capture_screen", return_value=frame):
        overlay = CaptureOverlay(mode="pick", images_dir=str(tmp_path))

    overlay._dpr = 1.5
    overlay.setGeometry(0, 0, 100, 100)
    picked: list[tuple[int, int]] = []
    overlay.coords_picked.connect(lambda x, y: picked.append((x, y)))
    overlay.show()
    qtbot.mouseClick(overlay, Qt.LeftButton, pos=QPoint(10, 20))  # type: ignore[attr-defined]

    assert picked == [(15, 30)]


def test_main_window_3_column_layout(qapp: QApplication) -> None:
    from stepwise.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    qapp.processEvents()
    main_splitter = win.centralWidget()
    assert main_splitter.count() == 3
    assert main_splitter.childrenCollapsible() is False
    # Left: Library, Center: Tree + Data, Right: Properties
    assert main_splitter.widget(0) == win.lib_panel
    center = main_splitter.widget(1)
    assert center.count() == 2
    assert center.childrenCollapsible() is False
    assert center.widget(1) == win.data_panel
    assert main_splitter.widget(2) == win.prop_panel

    main_sizes = main_splitter.sizes()
    center_sizes = center.sizes()
    assert main_sizes[0] >= 180
    assert main_sizes[1] > main_sizes[0]
    assert main_sizes[2] >= 320
    assert center_sizes[0] > center_sizes[1] >= 150

    # Exercise the data_loaded connection established by the three-column setup.
    win.data_panel.data_loaded.emit("data.csv", ["Name"], [{"Name": "ACME"}], [7])
    assert win._data_filepath == "data.csv"
    assert win._data_headers == ["Name"]
    assert win._data_rows == [{"Name": "ACME"}]
    assert win._data_row_nums == [7]
    win.close()


def test_runner_snapshot_failure_always_tears_down_ui(qapp: QApplication, qtbot: object) -> None:
    from stepwise.ui.main_window import MainWindow

    snapshot_thread_ids: list[int] = []
    hotkey_stops: list[bool] = []

    class _FakeHotkeyManager:
        def start(self) -> None:
            pass

        def register_hotkey(self, *args: object, **kwargs: object) -> int:
            return 1

        def stop(self) -> None:
            hotkey_stops.append(True)
            raise RuntimeError("hotkey stop failed")

    def _failed_deepcopy(value: object) -> object:
        snapshot_thread_ids.append(threading.get_ident())
        raise RuntimeError("snapshot failed")

    win = MainWindow()
    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", _FakeHotkeyManager),
        patch("stepwise.ui.main_window.copy.deepcopy", side_effect=_failed_deepcopy),
        patch("stepwise.ui.main_window.QMessageBox.warning") as warning,
    ):
        win._start_execution({})
        qtbot.waitUntil(lambda: win.btn_run.isEnabled(), timeout=2000)  # type: ignore[attr-defined]

    assert snapshot_thread_ids == [threading.get_ident()]
    assert hotkey_stops == []  # Snapshot preparation precedes hotkey registration.
    warning.assert_called_once()
    assert win._worker_thread is None
    assert win._is_running is False
    assert win._hotkey_mgr is None
    assert win.btn_pause.isEnabled() is False
    assert win.btn_stop.isEnabled() is False
    win.close()


def test_main_window_passes_data_identity_to_runner(qapp: QApplication, qtbot: object) -> None:
    from stepwise.ui.main_window import MainWindow

    calls: list[dict[str, object]] = []

    class _FakeHotkeyManager:
        def start(self) -> None:
            pass

        def register_hotkey(self, *args: object, **kwargs: object) -> int:
            return 1

        def stop(self) -> None:
            pass

    def _capture_run(**kwargs: object) -> None:
        calls.append(kwargs)

    win = MainWindow()
    win._data_filepath = "source.xlsx"
    win._data_rows = [{"Name": "Alice"}, {"Name": "Bob"}]
    win._data_row_nums = [2, 5]

    with (
        patch("stepwise.ui.main_window.GlobalHotkeyManager", _FakeHotkeyManager),
        patch("stepwise.ui.main_window.run_macro", side_effect=_capture_run),
    ):
        win._start_execution({})
        qtbot.waitUntil(lambda: bool(calls) and win.btn_run.isEnabled(), timeout=2000)  # type: ignore[attr-defined]

    assert calls[0]["data_filepath"] == "source.xlsx"
    assert calls[0]["row_numbers"] == (2, 5)
    win.close()


def test_run_only_source_row_uses_data_index(qapp: QApplication) -> None:
    from stepwise.ui.main_window import MainWindow

    win = MainWindow()
    win._data_row_nums = [2, 5]

    with patch.object(win, "_start_execution") as start_execution:
        win._on_run_only_row(5)

    assert start_execution.call_args.args[0]["start_row"] == 2
    win.close()


def test_action_tree_target_and_insertion_after_selected(qapp: QApplication) -> None:
    from stepwise.core.models import ActionItem, Macro
    from stepwise.ui.main_window import MainWindow

    win = MainWindow()
    macro = Macro(
        name="Test Macro",
        setup=[],
        per_row=[ActionItem(type="click", x=10, y=10)],
        cleanup=[],
    )
    win._current_macro = macro
    win.action_tree.load_macro(macro)

    # 1. Target setup header when setup is empty
    win.action_tree.tree.setCurrentItem(win.action_tree.tree.topLevelItem(0))
    sec_name, idx = win.action_tree.get_current_target_section()
    assert sec_name == "setup"
    assert idx == 0

    # Add click to setup -> should be placed at setup[0]
    win._on_request_add_action("click", sec_name, idx)
    assert len(macro.setup) == 1
    added_setup_act = macro.setup[0]

    # Added action must be automatically selected
    assert win.action_tree._get_selected_action() is added_setup_act

    # Adding another action while added_setup_act is selected should insert right after it (idx=1)
    sec_name, idx = win.action_tree.get_current_target_section()
    assert sec_name == "setup"
    assert idx == 1
    win._on_request_add_action("type_text", sec_name, idx)
    assert len(macro.setup) == 2
    assert macro.setup[1].type == "type_text"

    # 2. Test Move Up and Move Down within section
    act1 = macro.setup[0]
    act2 = macro.setup[1]
    assert act1.type == "click"
    assert act2.type == "type_text"

    # Move act2 up -> should become setup[0]
    win._on_request_move_up(act2)
    assert macro.setup[0] is act2
    assert macro.setup[1] is act1

    # Moving act2 up again when already at index 0 should NOT cross section boundaries
    win._on_request_move_up(act2)
    assert macro.setup[0] is act2

    # Move act2 down -> should return to setup[1]
    win._on_request_move_down(act2)
    assert macro.setup[1] is act2

    win.close()


@pytest.fixture
def editing_window(qapp: QApplication, qtbot: object, tmp_path: Path):
    from stepwise.ui.main_window import MainWindow

    win = MainWindow(library_dir=str(tmp_path))
    qtbot.addWidget(win)
    return win


@pytest.mark.parametrize("section", ["setup", "per_row", "cleanup"])
def test_nested_group_add_move_duplicate_delete(editing_window, section: str) -> None:
    win = editing_window
    first, second = ActionItem(type="wait"), ActionItem(type="key")
    inner = ActionItem(type="group", name="Inner", items=[first, second], collapsed=True)
    outer = ActionItem(type="group", name="Outer", items=[inner], collapsed=True)
    macro = Macro()
    getattr(macro, section).append(outer)
    win._current_macro = macro
    win.action_tree.load_macro(macro)
    win.action_tree.rebuild_tree(select_id=first.id)

    assert win.action_tree.get_current_insertion_target() == (section, inner, 1)
    assert "Outer / Inner" in win.action_tree.lbl_target.text()
    win._add_quick_action("type_text")
    added = inner.items[1]
    assert [item.id for item in inner.items] == [first.id, added.id, second.id]
    assert win.action_tree._get_selected_action() is added
    assert win.prop_panel._current_action is added
    node = win.action_tree.tree.currentItem()
    assert node.parent().isExpanded()
    assert node.parent().parent().isExpanded()
    editor = win.prop_panel.txt_text
    editor.setText("inside group")
    assert win.prop_panel.txt_text is editor
    assert win.action_tree.tree.currentItem().parent().isExpanded()
    assert win.action_tree.tree.currentItem().parent().parent().isExpanded()

    win._on_request_move_up(added)
    win._on_request_move_up(added)  # At group boundary: keep it inside Inner.
    assert [item.id for item in inner.items] == [added.id, first.id, second.id]
    win._on_request_move_down(added)
    win._on_request_move_down(second)  # Bottom boundary.
    assert [item.id for item in inner.items] == [first.id, added.id, second.id]

    win._on_request_duplicate_action(added)
    clone = inner.items[2]
    assert clone is not added and clone.id != added.id
    assert clone.type == added.type
    assert win.action_tree._get_selected_action() is clone
    win._on_request_delete_action(clone)
    assert win.action_tree._get_selected_action() is second
    assert win.prop_panel._current_action is second


@pytest.mark.parametrize("target_section", ["setup", "cleanup"])
def test_nested_group_move_section_removes_original(editing_window, target_section: str) -> None:
    win = editing_window
    child = ActionItem(type="wait")
    group = ActionItem(type="group", items=[child])
    macro = Macro(setup=[ActionItem(type="group", items=[group])])
    win._current_macro = macro
    win.action_tree.load_macro(macro)
    win._on_request_move_section(child, target_section)

    assert group.items == []
    assert getattr(macro, target_section)[-1] is child
    location = macro.find_action_location(child)
    assert location.parent is None
    assert location.section == target_section
    assert win.action_tree._get_selected_action() is child
    assert win.prop_panel._current_action is child
    # A stale context-menu action must not append an absent object to the macro.
    orphan = ActionItem(type="wait")
    win._on_request_move_section(orphan, "per_row")
    assert macro.per_row == []


@pytest.mark.parametrize("section", ["setup", "per_row", "cleanup"])
def test_delete_last_action_keeps_empty_section_target(editing_window, section: str) -> None:
    win = editing_window
    action = ActionItem(type="type_text", text="Old")
    macro = Macro()
    getattr(macro, section).append(action)
    win._current_macro = macro
    win.action_tree.load_macro(macro)
    win.action_tree.rebuild_tree(select_id=action.id)
    changes = []
    win.action_tree.action_selected.connect(changes.append)
    win._on_request_delete_action(action)

    assert getattr(macro, section) == []
    assert win.action_tree._get_selected_action() is None
    assert win.prop_panel._current_action is None
    assert win.prop_panel.txt_text is None
    assert changes == [None]
    assert win.action_tree.get_current_insertion_target() == (section, None, 0)
    assert win.action_tree.tree.currentItem().data(0, Qt.UserRole) == f"empty_{section}"
    win._add_quick_action("wait")
    assert len(getattr(macro, section)) == 1


def test_delete_last_group_child_and_add_to_empty_group(editing_window) -> None:
    win = editing_window
    child = ActionItem(type="wait")
    inner = ActionItem(type="group", name="Inner", items=[child])
    macro = Macro(cleanup=[ActionItem(type="group", name="Outer", items=[inner])])
    win._current_macro = macro
    win.action_tree.load_macro(macro)
    win.action_tree.rebuild_tree(select_id=child.id)
    win._on_request_delete_action(child)

    assert inner.items == []
    assert win.prop_panel._current_action is None
    assert win.action_tree.get_current_insertion_target() == ("cleanup", inner, 0)
    assert win.action_tree.tree.currentItem().data(0, Qt.UserRole) == f"empty_group_{inner.id}"
    win.action_tree.rebuild_tree()  # Restore a placeholder at arbitrary nesting depth.
    assert win.action_tree.get_current_insertion_target() == ("cleanup", inner, 0)
    win._add_quick_action("key")
    assert len(inner.items) == 1 and inner.items[0].type == "key"
    assert win.action_tree._get_selected_action() is inner.items[0]


def test_target_banner_uses_displayed_step_number_and_group_name(qapp: QApplication) -> None:
    tree = ActionTreeWidget()
    group = ActionItem(type="group", name="Batch", items=[ActionItem(), ActionItem()])
    selected, following = ActionItem(type="wait"), ActionItem(type="key")
    tree.load_macro(Macro(setup=[ActionItem()], per_row=[group, selected, following]))
    tree.rebuild_tree(select_id=selected.id)
    assert tree.tree.currentItem().text(0) == "4"
    assert "[PER ROW] after Step #4" in tree.lbl_target.text()
    tree.rebuild_tree(select_id=group.id)
    assert '[PER ROW] after group "Batch"' in tree.lbl_target.text()


def test_rebuild_selection_sync_and_property_typing_preserves_editor(editing_window, qtbot) -> None:
    win = editing_window
    action = ActionItem(type="type_text", text="")
    macro = Macro(per_row=[action])
    win._current_macro = macro
    win.action_tree.load_macro(macro)
    win.action_tree.rebuild_tree(select_id=action.id)
    editor = win.prop_panel.txt_text
    win.show()
    editor.setFocus()
    qtbot.keyClicks(editor, "abcdef")
    assert action.text == "abcdef"
    assert win.prop_panel.txt_text is editor
    assert editor.cursorPosition() == 6
    macro.per_row.clear()
    win.action_tree.rebuild_tree()
    assert win.action_tree._get_selected_action() is None
    assert win.prop_panel._current_action is None


def test_add_with_search_reveals_new_selection(editing_window) -> None:
    win = editing_window
    action = ActionItem(type="wait", note="needle")
    macro = Macro(per_row=[action])
    win._current_macro = macro
    win.action_tree.load_macro(macro)
    win.action_tree.rebuild_tree(select_id=action.id)
    win.action_tree.txt_search.setText("needle")
    win._add_quick_action("key")
    assert win.action_tree.txt_search.text() == ""
    assert not win.action_tree.tree.currentItem().isHidden()
    assert win.action_tree._get_selected_action() is macro.per_row[1]


def test_tree_shortcuts_and_text_field_focus(editing_window, qtbot) -> None:
    win = editing_window
    action, other = ActionItem(type="type_text", text="abc"), ActionItem(type="wait")
    macro = Macro(per_row=[action, other])
    win._current_macro = macro
    win.action_tree.load_macro(macro)
    win.action_tree.rebuild_tree(select_id=action.id)
    win.show()
    win.activateWindow()
    tree = win.action_tree.tree
    tree.setFocus()
    qtbot.waitUntil(tree.hasFocus)
    qtbot.keyClick(tree, Qt.Key_Down, Qt.AltModifier)
    assert macro.per_row[1] is action
    qtbot.keyClick(tree, Qt.Key_Up, Qt.AltModifier)
    assert macro.per_row[0] is action
    qtbot.keyClick(tree, Qt.Key_D, Qt.ControlModifier)
    assert len(macro.per_row) == 3
    clone = macro.per_row[1]
    assert win.action_tree._get_selected_action() is clone

    search = win.action_tree.txt_search
    search.setFocus()
    qtbot.waitUntil(search.hasFocus)
    qtbot.keyClick(search, Qt.Key_Up, Qt.AltModifier)
    qtbot.keyClick(search, Qt.Key_D, Qt.ControlModifier)
    assert [item.id for item in macro.per_row] == [action.id, clone.id, other.id]
    search.setText("abc")
    search.setCursorPosition(0)
    qtbot.keyClick(search, Qt.Key_Delete)
    assert search.text() == "bc"
    assert len(macro.per_row) == 3
    search.clear()

    editor = win.prop_panel.txt_text
    editor.setFocus()
    qtbot.waitUntil(editor.hasFocus)
    editor.setCursorPosition(0)
    qtbot.keyClick(editor, Qt.Key_Delete)
    qtbot.keyClick(editor, Qt.Key_D, Qt.ControlModifier)
    qtbot.keyClick(editor, Qt.Key_Up, Qt.AltModifier)
    assert clone.text == "bc" and len(macro.per_row) == 3
    assert win.prop_panel.txt_text is editor

    tree.setFocus()
    qtbot.waitUntil(tree.hasFocus)
    qtbot.keyClick(tree, Qt.Key_Delete)
    assert [item.id for item in macro.per_row] == [action.id, other.id]
    assert win.prop_panel._current_action is other


def test_context_add_uses_right_clicked_nested_parent(editing_window) -> None:
    win = editing_window
    first, child = ActionItem(type="wait"), ActionItem(type="key")
    inner = ActionItem(type="group", name="Inner", items=[child])
    macro = Macro(setup=[first, ActionItem(type="group", items=[inner])])
    win._current_macro = macro
    win.action_tree.load_macro(macro)
    win.action_tree.rebuild_tree(select_id=child.id)
    win.show()
    node = win.action_tree.tree.currentItem()
    position = win.action_tree.tree.visualItemRect(node).center()
    win.action_tree.tree.setCurrentItem(win.action_tree._find_node_by_step_id(first.id))

    class AutoAddMenu(QMenu):
        def exec(self, position):
            submenu = self.actions()[0].menu()
            assert "SETUP" in submenu.title() and "Inner" in submenu.title()
            submenu.actions()[0].trigger()

    with patch("stepwise.ui.action_tree.QMenu", AutoAddMenu):
        win.action_tree._show_context_menu(position)
    assert len(inner.items) == 2 and inner.items[1].type == "click"
    assert win.action_tree._get_selected_action() is inner.items[1]
