"""Unit tests for window positioning, sizing, and alignment actions."""

import sys
from unittest.mock import patch

import pytest

from stepwise.core.models import ActionItem, Macro
from stepwise.core.schema import validate_macro_dict
from stepwise.engine.actions import execute_action
from stepwise.engine.errors import StepFailure
from stepwise.services.window_win import (
    find_window_by_title,
    list_visible_windows,
)


def test_window_model_serialization_and_schema() -> None:
    act = ActionItem(
        type="window_set_bounds",
        window_title="SAP GUI",
        window_x=10,
        window_y=20,
        window_width=1600,
        window_height=900,
        window_maximize=False,
    )
    d = act.to_dict()
    assert d["type"] == "window_set_bounds"
    assert d["window_title"] == "SAP GUI"
    assert d["window_x"] == 10
    assert d["window_y"] == 20
    assert d["window_width"] == 1600
    assert d["window_height"] == 900
    assert d["window_maximize"] is False

    # Verify full macro validation passes schema check
    macro = Macro(name="Window Alignment Macro", setup=[act])
    macro_dict = macro.to_dict()
    validate_macro_dict(macro_dict)

    restored = ActionItem.from_dict(d)
    assert restored.type == "window_set_bounds"
    assert restored.window_title == "SAP GUI"
    assert restored.window_x == 10
    assert restored.window_y == 20
    assert restored.window_width == 1600
    assert restored.window_height == 900
    assert restored.window_maximize is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only Win32 API test")
def test_list_visible_windows_runs_without_crash() -> None:
    windows = list_visible_windows()
    assert isinstance(windows, list)
    for hwnd, title in windows:
        assert isinstance(hwnd, int)
        assert isinstance(title, str)


def test_window_set_bounds_execution_success() -> None:
    act = ActionItem(
        type="window_set_bounds",
        window_title="MockApp",
        window_x=0,
        window_y=0,
        window_width=1280,
        window_height=800,
        window_maximize=False,
    )

    with (
        patch("stepwise.services.window_win.find_window_by_title", return_value=12345),
        patch(
            "stepwise.services.window_win.set_window_bounds", return_value=(True, "")
        ) as mock_set,
    ):
        execute_action(act, default_wait_before=0.0)
        mock_set.assert_called_once_with(12345, x=0, y=0, width=1280, height=800, maximize=False)


def test_window_set_bounds_execution_maximize() -> None:
    act = ActionItem(
        type="window_set_bounds",
        window_title="MockApp",
        window_maximize=True,
    )

    with (
        patch("stepwise.services.window_win.find_window_by_title", return_value=12345),
        patch(
            "stepwise.services.window_win.set_window_bounds", return_value=(True, "")
        ) as mock_set,
    ):
        execute_action(act, default_wait_before=0.0)
        mock_set.assert_called_once_with(12345, x=0, y=0, width=1280, height=720, maximize=True)


def test_window_set_bounds_empty_title_raises_failure() -> None:
    act = ActionItem(
        type="window_set_bounds",
        window_title="   ",
    )
    with pytest.raises(StepFailure) as exc_info:
        execute_action(act, default_wait_before=0.0)
    assert "cannot be empty" in str(exc_info.value)


def test_window_set_bounds_variable_substitution() -> None:
    act = ActionItem(
        type="window_set_bounds",
        window_title="{AppTitle}",
    )
    row = {"AppTitle": "Excel"}

    with (
        patch("stepwise.services.window_win.find_window_by_title", return_value=9999) as mock_find,
        patch("stepwise.services.window_win.set_window_bounds", return_value=(True, "")),
    ):
        execute_action(act, row_data=row, default_wait_before=0.0)
        mock_find.assert_called_once_with("Excel")


def test_window_set_bounds_missing_window_raises_step_failure() -> None:
    act = ActionItem(
        type="window_set_bounds",
        window_title="NonExistentWindow_99999",
    )

    with patch("stepwise.services.window_win.find_window_by_title", return_value=None):
        with pytest.raises(StepFailure) as exc_info:
            execute_action(act, default_wait_before=0.0)
        assert "not found on screen" in str(exc_info.value)


def test_window_set_bounds_failure_reports_win32_error() -> None:
    act = ActionItem(
        type="window_set_bounds",
        window_title="ProtectedApp",
    )

    with (
        patch("stepwise.services.window_win.find_window_by_title", return_value=555),
        patch(
            "stepwise.services.window_win.set_window_bounds",
            return_value=(False, "Target window may be running as Administrator"),
        ),
    ):
        with pytest.raises(StepFailure) as exc_info:
            execute_action(act, default_wait_before=0.0)
        assert "running as Administrator" in str(exc_info.value)


def test_find_window_by_title_prioritizes_exact_match() -> None:
    mock_windows = [
        (101, "Google Chrome - Home"),
        (102, "Google"),
        (103, "My Google Note"),
    ]
    with patch("stepwise.services.window_win.list_visible_windows", return_value=mock_windows):
        # Exact match should pick 102 even though 101 contains "google"
        hwnd = find_window_by_title("Google")
        assert hwnd == 102

        # Substring match when no exact match exists
        hwnd_sub = find_window_by_title("Chrome")
        assert hwnd_sub == 101


def test_get_window_visual_bounds_and_frame_offsets() -> None:
    from stepwise.services.window_win import (
        get_frame_offsets,
        get_window_visual_bounds,
    )

    fake_hwnd = 4444

    # Simulate: Outer Win32 rect has (-7, 0, 1287, 727), DWM visual rect is (0, 0, 1280, 720)
    def fake_get_window_rect(h, rect_ptr):
        rect_ptr.contents.left = -7
        rect_ptr.contents.top = 0
        rect_ptr.contents.right = 1287
        rect_ptr.contents.bottom = 727
        return True

    def fake_dwm_attr(h, attr, rect_ptr, size):
        rect_ptr.contents.left = 0
        rect_ptr.contents.top = 0
        rect_ptr.contents.right = 1280
        rect_ptr.contents.bottom = 720
        return 0

    with (
        patch("stepwise.services.window_win.user32.IsWindow", return_value=True),
        patch("stepwise.services.window_win.user32.GetWindowRect", side_effect=fake_get_window_rect),
        patch("stepwise.services.window_win.dwmapi.DwmGetWindowAttribute", side_effect=fake_dwm_attr),
    ):
        bounds = get_window_visual_bounds(fake_hwnd)
        assert bounds == (0, 0, 1280, 720)

        offsets = get_frame_offsets(fake_hwnd)
        # l_off = 0 - (-7) = 7, t_off = 0, r_off = 1287 - 1280 = 7, b_off = 727 - 720 = 7
        assert offsets == (7, 0, 7, 7)


def test_set_window_bounds_restores_and_compensates() -> None:
    from stepwise.services.window_win import set_window_bounds

    fake_hwnd = 5555
    sw_calls = []

    with (
        patch("stepwise.services.window_win.user32.IsWindow", return_value=True),
        patch("stepwise.services.window_win.user32.IsIconic", return_value=True),
        patch("stepwise.services.window_win.user32.IsZoomed", return_value=False),
        patch("stepwise.services.window_win.user32.ShowWindow", side_effect=lambda h, cmd: sw_calls.append(cmd) or True),
        patch("stepwise.services.window_win.get_frame_offsets", return_value=(7, 0, 7, 7)),
        patch("stepwise.services.window_win.user32.SetWindowPos", return_value=True) as mock_pos,
        patch("stepwise.services.window_win.user32.SetForegroundWindow", return_value=True),
        patch("stepwise.services.window_win.user32.GetForegroundWindow", return_value=fake_hwnd),
        patch("stepwise.services.window_win.get_window_visual_bounds", return_value=(0, 0, 1280, 720)),
    ):
        ok, msg = set_window_bounds(fake_hwnd, x=0, y=0, width=1280, height=720, maximize=False, settle_seconds=0.0)
        assert ok is True
        assert msg == ""
        # Minimized window should be restored with SW_RESTORE (9)
        assert 9 in sw_calls
        # Target coords should be compensated: x = 0 - 7 = -7, width = 1280 + 7 + 7 = 1294, height = 720 + 7 = 727
        mock_pos.assert_called_once_with(fake_hwnd, 0, -7, 0, 1294, 727, 4)


def test_set_window_bounds_app_minimum_size_warning() -> None:
    from stepwise.services.window_win import set_window_bounds

    fake_hwnd = 6666

    with (
        patch("stepwise.services.window_win.user32.IsWindow", return_value=True),
        patch("stepwise.services.window_win.user32.IsIconic", return_value=False),
        patch("stepwise.services.window_win.user32.IsZoomed", return_value=False),
        patch("stepwise.services.window_win.get_frame_offsets", return_value=(0, 0, 0, 0)),
        patch("stepwise.services.window_win.user32.SetWindowPos", return_value=True),
        patch("stepwise.services.window_win.user32.SetForegroundWindow", return_value=True),
        patch("stepwise.services.window_win.user32.GetForegroundWindow", return_value=fake_hwnd),
        # Target app enforced min width 1400 instead of requested 1280
        patch("stepwise.services.window_win.get_window_visual_bounds", return_value=(0, 0, 1400, 720)),
    ):
        ok, msg = set_window_bounds(fake_hwnd, x=0, y=0, width=1280, height=720, maximize=False, settle_seconds=0.0)
        assert ok is True
        assert "Target window constrained to 1400x720" in msg


def test_properties_panel_window_set_bounds(qtbot) -> None:
    from stepwise.ui.properties_panel import PropertiesPanel

    act = ActionItem(
        type="window_set_bounds",
        window_title="Calc",
        window_x=0,
        window_y=0,
        window_width=1280,
        window_height=720,
        window_maximize=False,
    )

    panel = PropertiesPanel()
    qtbot.addWidget(panel)
    panel.set_action(act)

    assert panel.txt_win_title.text() == "Calc"
    assert panel.spin_win_x.value() == 0
    assert panel.spin_win_y.value() == 0
    assert panel.spin_win_w.value() == 1280
    assert panel.spin_win_h.value() == 720
    # Initial preset should be 1280x720 (index 0)
    assert panel.cbo_win_preset.currentIndex() == 0

    # Change preset to 1600x900 (index 1)
    panel.cbo_win_preset.setCurrentIndex(1)
    assert act.window_width == 1600
    assert act.window_height == 900
    assert panel.spin_win_w.value() == 1600
    assert panel.spin_win_h.value() == 900

    # Change custom width
    panel.spin_win_w.setValue(1440)
    assert act.window_width == 1440
    # Preset combo should switch to Custom (index 4)
    assert panel.cbo_win_preset.currentIndex() == 4

    # Toggle maximize
    panel.chk_win_max.setChecked(True)
    assert act.window_maximize is True
    assert panel.spin_win_w.isEnabled() is False
    assert panel.cbo_win_preset.isEnabled() is False

    # Un-maximize and test Snap (0, 0)
    panel.chk_win_max.setChecked(False)
    panel.spin_win_x.setValue(150)
    panel.spin_win_y.setValue(250)

    # Find Snap (0, 0) button
    from PySide6.QtWidgets import QPushButton
    buttons = panel.findChildren(QPushButton)
    snap_btn = next((b for b in buttons if "0, 0" in b.text()), None)
    assert snap_btn is not None
    snap_btn.click()
    assert panel.spin_win_x.value() == 0
    assert panel.spin_win_y.value() == 0

    # Test Get Current Bounds button
    get_btn = next((b for b in buttons if "Get Current" in b.text() or "현재 창" in b.text()), None)
    assert get_btn is not None
    with (
        patch("stepwise.services.window_win.find_window_by_title", return_value=8888),
        patch("stepwise.services.window_win.get_window_visual_bounds", return_value=(100, 50, 1600, 900)),
    ):
        get_btn.click()
        assert panel.spin_win_x.value() == 100
        assert panel.spin_win_y.value() == 50
        assert panel.spin_win_w.value() == 1600
        assert panel.spin_win_h.value() == 900

    # Test Align Now button
    align_btn = next((b for b in buttons if "Test Align" in b.text() or "정렬 테스트" in b.text()), None)
    assert align_btn is not None
    with (
        patch("stepwise.services.window_win.find_window_by_title", return_value=8888),
        patch("stepwise.services.window_win.set_window_bounds", return_value=(True, "")) as mock_align,
        patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
    ):
        align_btn.click()
        mock_align.assert_called_once_with(8888, x=100, y=50, width=1600, height=900, maximize=False)
        mock_info.assert_called_once()


def test_window_align_dialog_ui_and_signals(qtbot) -> None:
    from stepwise.ui.window_align_dialog import WindowAlignDialog

    mock_wins = [(101, "Google Chrome"), (102, "ERP Client")]
    with (
        patch("stepwise.ui.window_align_dialog.list_visible_windows", return_value=mock_wins),
        patch("stepwise.ui.window_align_dialog.find_window_by_title", return_value=102),
        patch("stepwise.ui.window_align_dialog.set_window_bounds", return_value=(True, "")) as mock_set,
    ):
        dlg = WindowAlignDialog(initial_title="ERP")
        qtbot.addWidget(dlg)

        # Initial selection should match "ERP"
        assert dlg.cbo_windows.currentText() == "ERP Client"

        # Change preset to 1600x900 (index 1)
        dlg.cbo_preset.setCurrentIndex(1)
        assert dlg.spin_w.value() == 1600
        assert dlg.spin_h.value() == 900

        # Apply alignment
        signal_received = []
        dlg.alignment_applied.connect(lambda *args: signal_received.append(args))

        dlg.btn_apply.click()
        mock_set.assert_called_once_with(102, x=0, y=0, width=1600, height=900, maximize=False)
        assert len(signal_received) == 1
        # title, x, y, w, h, max, inject
        assert signal_received[0][0] == "ERP Client"
        assert signal_received[0][3] == 1600
        assert signal_received[0][4] == 900
        assert signal_received[0][6] is True


def test_main_window_window_align_injection(qtbot) -> None:
    from stepwise.ui.main_window import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)

    # Empty setup initially
    assert len(win._current_macro.setup) == 0

    # 1. Inject new alignment action
    win._on_window_alignment_applied(
        title="SAP GUI",
        x=0,
        y=0,
        width=1280,
        height=720,
        maximize=False,
        inject_setup=True,
    )

    assert len(win._current_macro.setup) == 1
    act = win._current_macro.setup[0]
    assert act.type == "window_set_bounds"
    assert act.window_title == "SAP GUI"
    assert act.window_width == 1280
    assert act.window_height == 720

    # 2. Re-apply to update existing action
    win._on_window_alignment_applied(
        title="SAP GUI",
        x=0,
        y=0,
        width=1600,
        height=900,
        maximize=False,
        inject_setup=True,
    )

    # Length should still be 1 (updated in place)
    assert len(win._current_macro.setup) == 1
    assert win._current_macro.setup[0].window_width == 1600
    assert win._current_macro.setup[0].window_height == 900

    # 3. Apply without injection (inject_setup=False)
    win._on_window_alignment_applied(
        title="Chrome",
        x=10,
        y=20,
        width=1280,
        height=720,
        maximize=False,
        inject_setup=False,
    )
    # Setup unchanged
    assert len(win._current_macro.setup) == 1
    assert win._current_macro.setup[0].window_title == "SAP GUI"

    # 4. Apply alignment for a DIFFERENT window title -> should create a new action, not overwrite SAP GUI
    win._on_window_alignment_applied(
        title="Google Chrome",
        x=0,
        y=0,
        width=1280,
        height=720,
        maximize=False,
        inject_setup=True,
    )
    assert len(win._current_macro.setup) == 2
    titles = [a.window_title for a in win._current_macro.setup]
    assert "SAP GUI" in titles
    assert "Google Chrome" in titles


def test_window_align_dialog_custom_typing_ignores_old_hwnd(qtbot) -> None:
    from stepwise.ui.window_align_dialog import WindowAlignDialog

    mock_wins = [(101, "Google Chrome"), (102, "ERP Client")]
    with (
        patch("stepwise.ui.window_align_dialog.list_visible_windows", return_value=mock_wins),
        patch("stepwise.ui.window_align_dialog.find_window_by_title", return_value=999) as mock_find,
        patch("stepwise.ui.window_align_dialog.set_window_bounds", return_value=(True, "")) as mock_set,
    ):
        dlg = WindowAlignDialog()
        qtbot.addWidget(dlg)

        # Select first item (Chrome, HWND=101)
        dlg.cbo_windows.setCurrentIndex(0)
        # Now simulate user manually typing a different custom title in the editable combo box
        dlg.cbo_windows.setEditText("My Custom Calculator")

        dlg.btn_apply.click()
        # Should NOT use HWND 101; should look up "My Custom Calculator"
        mock_find.assert_called_with("My Custom Calculator")
        mock_set.assert_called_once_with(999, x=0, y=0, width=1280, height=720, maximize=False)


def test_properties_panel_sample_row_variable_resolution(qtbot) -> None:
    from stepwise.ui.properties_panel import PropertiesPanel

    act = ActionItem(
        type="window_set_bounds",
        window_title="{AppTitle}",
    )
    panel = PropertiesPanel()
    qtbot.addWidget(panel)
    panel.set_action(act)
    # Set sample row
    panel.set_sample_row({"AppTitle": "Excel"})

    from PySide6.QtWidgets import QPushButton
    buttons = panel.findChildren(QPushButton)
    get_btn = next((b for b in buttons if "Get Current" in b.text() or "현재 창" in b.text()), None)
    assert get_btn is not None

    with (
        patch("stepwise.services.window_win.find_window_by_title", return_value=777) as mock_find,
        patch("stepwise.services.window_win.get_window_visual_bounds", return_value=(10, 20, 1280, 720)),
    ):
        get_btn.click()
        # Should resolve {AppTitle} to "Excel"
        mock_find.assert_called_with("Excel")
        assert panel.spin_win_x.value() == 10
        assert panel.spin_win_y.value() == 20





