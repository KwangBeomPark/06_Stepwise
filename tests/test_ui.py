"""UI widget tests using pytest-qt."""

import pytest
from PySide6.QtWidgets import QApplication

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
    overlay = ScreenCrosshairOverlay(x=200, y=300, duration_ms=100)
    assert overlay.x() == 150
    assert overlay.y() == 250
    overlay.close()
