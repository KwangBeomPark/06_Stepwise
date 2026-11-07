"""Unit tests for multi-step selection, copy, cut, paste, and deletion in ActionTreeWidget."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QTreeWidget

from stepwise.core.models import ActionItem, Macro
from stepwise.ui.action_tree import ActionTreeWidget
from stepwise.ui.main_window import MainWindow


def test_action_tree_extended_selection_mode(qapp: QApplication) -> None:
    widget = ActionTreeWidget()
    assert widget.tree.selectionMode() == QTreeWidget.SelectionMode.ExtendedSelection


def test_action_tree_get_selected_actions_document_order(qapp: QApplication) -> None:
    widget = ActionTreeWidget()
    act1 = ActionItem(type="wait", seconds=1.0, note="Step 1")
    act2 = ActionItem(type="click", x=10, y=20, note="Step 2")
    act3 = ActionItem(type="key", keys="enter", note="Step 3")
    macro = Macro(per_row=[act1, act2, act3])
    widget.load_macro(macro)

    node1 = widget._find_node_by_step_id(act1.id)
    node2 = widget._find_node_by_step_id(act2.id)
    node3 = widget._find_node_by_step_id(act3.id)

    assert node1 is not None and node2 is not None and node3 is not None

    # Select node3 first, then node1 (out of visual order)
    node3.setSelected(True)
    node1.setSelected(True)

    selected = widget._get_selected_actions()
    # Must preserve macro document order: act1, then act3
    assert selected == [act1, act3]


def test_action_tree_selection_changed_emission(qapp: QApplication) -> None:
    widget = ActionTreeWidget()
    act1 = ActionItem(type="wait", seconds=1.0)
    act2 = ActionItem(type="click", x=10, y=20)
    macro = Macro(per_row=[act1, act2])
    widget.load_macro(macro)

    node1 = widget._find_node_by_step_id(act1.id)
    node2 = widget._find_node_by_step_id(act2.id)
    assert node1 is not None and node2 is not None

    emitted: list[object] = []
    widget.action_selected.connect(lambda obj: emitted.append(obj))

    # Single selection emits the ActionItem
    widget.tree.clearSelection()
    node1.setSelected(True)
    widget._on_selection_changed()
    assert len(emitted) > 0
    assert emitted[-1] is act1

    # Multiple selection emits None to guard properties panel
    node2.setSelected(True)
    widget._on_selection_changed()
    assert emitted[-1] is None


def test_main_window_multi_copy_and_paste(qapp: QApplication) -> None:
    window = MainWindow()
    act1 = ActionItem(type="wait", seconds=1.0, note="Wait step")
    act2 = ActionItem(type="type_text", text="hello", note="Type step")
    macro = Macro(per_row=[act1, act2])
    window._current_macro = macro
    window.action_tree.load_macro(macro)

    # Select both actions
    window._on_request_copy_actions([act1, act2])
    assert len(window._action_clipboard) == 2

    # Focus act2 and paste
    node2 = window.action_tree._find_node_by_step_id(act2.id)
    assert node2 is not None
    window.action_tree.tree.clearSelection()
    node2.setSelected(True)
    window.action_tree.tree.setCurrentItem(node2)

    window._on_request_paste_actions()

    # per_row should now contain 4 items
    assert len(window._current_macro.per_row) == 4
    pasted1 = window._current_macro.per_row[2]
    pasted2 = window._current_macro.per_row[3]

    assert pasted1.type == "wait"
    assert pasted1.seconds == 1.0
    assert pasted2.type == "type_text"
    assert pasted2.text == "hello"

    # UUIDs must be fresh and unique
    assert pasted1.id not in (act1.id, act2.id)
    assert pasted2.id not in (act1.id, act2.id, pasted1.id)


def test_main_window_multi_cut_and_paste(qapp: QApplication) -> None:
    window = MainWindow()
    act1 = ActionItem(type="wait", seconds=1.0, note="Step 1")
    act2 = ActionItem(type="click", x=100, y=200, note="Step 2")
    act3 = ActionItem(type="key", keys="esc", note="Step 3")
    macro = Macro(per_row=[act1, act2, act3])
    window._current_macro = macro
    window.action_tree.load_macro(macro)

    # Cut act1 and act2
    window._on_request_cut_actions([act1, act2])

    # per_row now has only act3
    assert len(window._current_macro.per_row) == 1
    assert window._current_macro.per_row[0].id == act3.id
    assert len(window._action_clipboard) == 2

    # Paste into setup section
    setup_node = window.action_tree.tree.topLevelItem(0)
    window.action_tree.tree.clearSelection()
    setup_node.setSelected(True)
    window.action_tree.tree.setCurrentItem(setup_node)

    window._on_request_paste_actions()

    assert len(window._current_macro.setup) == 2
    assert window._current_macro.setup[0].type == "wait"
    assert window._current_macro.setup[1].type == "click"


def test_main_window_multi_delete_across_sections(qapp: QApplication) -> None:
    window = MainWindow()
    act_s1 = ActionItem(type="wait", seconds=1.0)
    act_s2 = ActionItem(type="key", keys="enter")
    act_p1 = ActionItem(type="click", x=10, y=20)
    act_p2 = ActionItem(type="type_text", text="abc")
    act_p3 = ActionItem(type="wait", seconds=2.0)

    macro = Macro(setup=[act_s1, act_s2], per_row=[act_p1, act_p2, act_p3])
    window._current_macro = macro
    window.action_tree.load_macro(macro)

    # Delete act_s1, act_p1, and act_p3 in one batch
    window._on_request_delete_actions([act_s1, act_p1, act_p3])

    assert len(window._current_macro.setup) == 1
    assert window._current_macro.setup[0].id == act_s2.id

    assert len(window._current_macro.per_row) == 1
    assert window._current_macro.per_row[0].id == act_p2.id


def test_copy_parent_group_and_child_no_duplicate(qapp: QApplication) -> None:
    tree = ActionTreeWidget()
    child1 = ActionItem(type="wait", seconds=1.0)
    child2 = ActionItem(type="click", x=5, y=10)
    parent_group = ActionItem(type="group", note="MyGroup", items=[child1, child2])

    macro = Macro(per_row=[parent_group])
    tree.load_macro(macro)

    # Find group node and child1 node in tree
    per_row_root = tree.tree.topLevelItem(1)
    group_node = per_row_root.child(0)
    child1_node = group_node.child(0)

    # Select both parent group AND child1 simultaneously
    tree.tree.clearSelection()
    group_node.setSelected(True)
    child1_node.setSelected(True)

    selected = tree._get_selected_actions()
    # Must only contain the parent group, child1 should NOT be duplicated
    assert len(selected) == 1
    assert selected[0].id == parent_group.id
    assert len(selected[0].items) == 2
