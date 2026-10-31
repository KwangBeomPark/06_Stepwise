"""Comprehensive unit tests for Stepwise upgrade features:
1. Bilingual UI (Korean / English) & status token invariance
2. Dark Mode / Light Mode theme engine
3. UI Selector & Simulate Click (uia_win, schema, models, preflight, engine, PropertiesPanel)
4. Night-Shift Task Scheduler ("Armed Mode" pre-arm diagnostics, checklist gating, countdown)
"""

from __future__ import annotations

import re
from datetime import datetime, time
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from stepwise.core.models import ActionItem, ImageCondition, Macro
from stepwise.core.schema import validate_macro_dict
from stepwise.engine.actions import execute_action
from stepwise.engine.errors import MacroSyntaxError
from stepwise.engine.preflight import run_preflight_checks
from stepwise.services.schedule_diag import (
    ScheduleDiagItem,
    compute_next_occurrence,
    format_countdown,
)
from stepwise.services.uia_win import (
    UIElementInfo,
    make_lparam,
    resolve_selector,
    simulate_click_at_hwnd,
)
from stepwise.ui.main_window import MainWindow
from stepwise.ui.properties_panel import PropertiesPanel
from stepwise.ui.scheduler_dialog import SchedulerDialog
from stepwise.ui.strings import (
    _EN_STRINGS,
    _KO_STRINGS,
    Strings,
    apply_language,
    format_status_display,
    get_current_language,
    normalize_status_code,
)
from stepwise.ui.theme import (
    DARK_TOKENS,
    LIGHT_TOKENS,
    apply_theme,
    build_palette,
    build_stylesheet,
    get_current_theme,
    get_theme_tokens,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def restore_ui_globals(qapp: QApplication):
    """Ensure language and theme globals return to default test state after each test."""
    yield
    apply_language("en")
    apply_theme(qapp, "dark")


# =====================================================================
# 1. Bilingual UI & Placeholder / Status Code Invariance Tests
# =====================================================================


def test_bilingual_string_placeholder_parity() -> None:
    """Every lowercase {placeholder} used with .format(...) in _EN_STRINGS must match _KO_STRINGS."""
    placeholder_re = re.compile(r"\{[a-z][a-z0-9_]*\}")
    assert set(_EN_STRINGS.keys()) == set(_KO_STRINGS.keys())

    for key, en_val in _EN_STRINGS.items():
        ko_val = _KO_STRINGS[key]
        en_placeholders = set(placeholder_re.findall(en_val))
        ko_placeholders = set(placeholder_re.findall(ko_val))
        assert en_placeholders == ko_placeholders, f"Placeholder mismatch in {key}"


def test_language_switch_and_status_canonical_invariance() -> None:
    apply_language("ko")
    assert get_current_language() == "ko"
    assert Strings.RUN == "실행"
    assert format_status_display("Done") == "완료"
    assert normalize_status_code("완료") == "Done"
    assert normalize_status_code("실패") == "Failed"
    assert normalize_status_code("대기중") == "Pending"

    apply_language("en")
    assert get_current_language() == "en"
    assert Strings.RUN == "Run"
    assert format_status_display("Done") == "Done"
    assert normalize_status_code("Done") == "Done"


# =====================================================================
# 2. Dark & Light Theme Engine Tests
# =====================================================================


def test_theme_tokens_and_switching(qapp: QApplication) -> None:
    assert set(DARK_TOKENS.keys()) == set(LIGHT_TOKENS.keys())

    mode = apply_theme(qapp, "dark")
    assert mode == "dark"
    assert get_current_theme() == "dark"
    assert get_theme_tokens()["bg_window"] == DARK_TOKENS["bg_window"]
    assert DARK_TOKENS["bg_window"] in build_stylesheet("dark")
    assert build_palette("dark") is not None

    mode = apply_theme(qapp, "light")
    assert mode == "light"
    assert get_current_theme() == "light"
    assert get_theme_tokens()["bg_window"] == LIGHT_TOKENS["bg_window"]
    assert LIGHT_TOKENS["bg_window"] in build_stylesheet("light")


def test_main_window_live_language_and_theme_toggles(
    qapp: QApplication, tmp_path, monkeypatch
) -> None:
    from stepwise.core import app_paths

    folder = tmp_path / "UserSetting"
    folder.mkdir()
    monkeypatch.setattr(app_paths, "user_settings_directory", lambda: folder)
    monkeypatch.setattr(app_paths, "config_file_path", lambda: folder / "settings.json")

    apply_language("en")
    apply_theme(qapp, "dark")

    win = MainWindow(library_dir=str(tmp_path))
    assert "Run" in win.btn_run.text()

    # Toggle to Korean
    win._toggle_language()
    assert get_current_language() == "ko"
    assert "실행" in win.btn_run.text()
    assert "예약" in win.btn_schedule.text()

    # Toggle theme to Light
    win._toggle_theme()
    assert get_current_theme() == "light"
    win.close()


# =====================================================================
# 3. UI Selector & Simulate Click Tests
# =====================================================================


def test_action_item_selector_serialization_and_schema() -> None:
    selector = {
        "window_title": "*SAP*",
        "control_type": "Button",
        "automation_id": "1001",
        "name": "Save {DocType}",
        "class_name": "Button",
        "rel_x": 45,
        "rel_y": 18,
    }
    act = ActionItem(
        type="click",
        target_mode="selector",
        selector=selector,
        click_method="simulate",
        x=120,
        y=240,
    )
    d = act.to_dict()
    assert d["target_mode"] == "selector"
    assert d["click_method"] == "simulate"
    assert d["selector"]["automation_id"] == "1001"

    restored = ActionItem.from_dict(d)
    assert restored.target_mode == "selector"
    assert restored.click_method == "simulate"
    assert restored.selector == selector

    # Schema validation
    macro = Macro(name="Selector Macro", per_row=[restored])
    validate_macro_dict(macro.to_dict())

    # Invalid target_mode must fail schema validation
    bad_dict = macro.to_dict()
    bad_dict["per_row"][0]["target_mode"] = "invalid_mode"
    with pytest.raises(MacroSyntaxError):
        validate_macro_dict(bad_dict)


def test_resolve_selector_unique_wildcard_and_ambiguity() -> None:
    fake_windows = [(100, "ERP Invoice Entry - Main")]
    fake_children = [201, 202]

    def _fake_class(hwnd: int) -> str:
        return "MainFrame" if hwnd == 100 else "Button"

    def _fake_ctrl_id(hwnd: int) -> int:
        return 101 if hwnd == 201 else 102

    def _fake_text(hwnd: int) -> str:
        return "Post Document" if hwnd == 201 else "Post Draft"

    def _fake_rect(hwnd: int):
        if hwnd == 100:
            return (0, 0, 800, 600)
        if hwnd == 201:
            return (100, 200, 80, 30)
        return (200, 200, 80, 30)

    with (
        patch("stepwise.services.uia_win.list_visible_windows", return_value=fake_windows),
        patch("stepwise.services.uia_win._enumerate_child_hwnds", return_value=fake_children),
        patch("stepwise.services.uia_win.get_class_name", side_effect=_fake_class),
        patch("stepwise.services.uia_win.user32.GetDlgCtrlID", side_effect=_fake_ctrl_id),
        patch("stepwise.services.uia_win.get_control_text", side_effect=_fake_text),
        patch("stepwise.services.uia_win.get_window_rect", side_effect=_fake_rect),
        patch("stepwise.services.uia_win.infer_control_type", return_value="Button"),
    ):
        # 1. Exact match with variable substitution
        elem = resolve_selector(
            {
                "window_title": "*Invoice*",
                "control_type": "Button",
                "name": "Post {TargetKind}",
            },
            row_data={"TargetKind": "Document"},
        )
        assert elem.hwnd == 201
        assert elem.target_point() == (140, 215)

        # 2. Ambiguous match (>=2 elements match "Post*") must raise LookupError
        with pytest.raises(LookupError, match="Ambiguous UI selector"):
            resolve_selector(
                {
                    "window_title": "*Invoice*",
                    "control_type": "Button",
                    "name": "Post*",
                }
            )

        # 3. 0 match must raise LookupError
        with pytest.raises(LookupError, match="UI element not found"):
            resolve_selector(
                {
                    "window_title": "*Invoice*",
                    "automation_id": "9999",
                }
            )

    # 4. Child criteria when _enumerate_child_hwnds returns [] must NOT fall back to root window
    with (
        patch("stepwise.services.uia_win.list_visible_windows", return_value=fake_windows),
        patch("stepwise.services.uia_win._enumerate_child_hwnds", return_value=[]),
        patch("stepwise.services.uia_win.get_class_name", return_value="MainFrame"),
        patch("stepwise.services.uia_win.get_window_rect", return_value=(0, 0, 800, 600)),
    ):
        with pytest.raises(LookupError, match="UI element not found"):
            resolve_selector(
                {
                    "window_title": "*Invoice*",
                    "control_type": "Button",
                    "name": "Save",
                }
            )

        # Even if a captured child is a Pane with the same class as root, is_root_anchor=False
        # must force child enumeration and raise LookupError when child is absent
        with pytest.raises(LookupError, match="UI element not found"):
            resolve_selector(
                {
                    "window_title": "*Invoice*",
                    "window_class": "MainFrame",
                    "control_type": "Pane",
                    "class_name": "MainFrame",
                    "is_root_anchor": False,
                }
            )


def test_simulate_click_bm_click_and_postmessage() -> None:
    assert make_lparam(10, 20) == ((20 << 16) | 10)

    with (
        patch("stepwise.services.uia_win.user32.IsWindow", return_value=1),
        patch("stepwise.services.uia_win._resolve_deepest_child_at_screen_pt", return_value=201),
        patch("stepwise.services.uia_win.user32.SendMessageTimeoutW", return_value=1) as mock_smto,
    ):
        ok, msg = simulate_click_at_hwnd(
            hwnd=201, screen_x=140, screen_y=215, button="left", clicks=1, use_bm_click=True
        )
        assert ok is True
        assert msg == ""
        mock_smto.assert_called_once()

    # BM_CLICK timeout (ERROR_TIMEOUT=1460 from modal dialog) must NOT re-click via PostMessageW
    with (
        patch("stepwise.services.uia_win.user32.IsWindow", return_value=1),
        patch("stepwise.services.uia_win._resolve_deepest_child_at_screen_pt", return_value=201),
        patch("stepwise.services.uia_win.user32.SendMessageTimeoutW", return_value=0),
        patch("stepwise.services.uia_win.ctypes.get_last_error", return_value=1460),
        patch("stepwise.services.uia_win.user32.PostMessageW") as mock_post_timeout,
    ):
        ok, msg = simulate_click_at_hwnd(
            hwnd=201, screen_x=140, screen_y=215, button="left", clicks=1, use_bm_click=True
        )
        assert ok is True
        mock_post_timeout.assert_not_called()

    # Double click sends WM_LBUTTONDOWN, WM_LBUTTONUP, WM_LBUTTONDBLCLK (0x0203), WM_LBUTTONUP
    with (
        patch("stepwise.services.uia_win.user32.IsWindow", return_value=1),
        patch("stepwise.services.uia_win._resolve_deepest_child_at_screen_pt", return_value=201),
        patch("stepwise.services.uia_win.user32.ScreenToClient", return_value=1),
        patch("stepwise.services.uia_win.user32.PostMessageW", return_value=1) as mock_post,
    ):
        ok, msg = simulate_click_at_hwnd(
            hwnd=201, screen_x=140, screen_y=215, button="left", clicks=2, use_bm_click=False
        )
        assert ok is True
        assert mock_post.call_count == 4
        sent_msgs = [call.args[1] for call in mock_post.call_args_list]
        assert sent_msgs == [0x0201, 0x0202, 0x0203, 0x0202]


def test_execute_action_selector_and_preflight() -> None:
    act = ActionItem(
        type="click",
        target_mode="selector",
        click_method="simulate",
        selector={
            "window_title": "*ERP*",
            "control_type": "Button",
            "name": "Save {Dept}",
        },
    )
    macro = Macro(name="Preflight Selector Test", per_row=[act])

    # Preflight detects missing variable {Dept} inside selector
    issues = run_preflight_checks(
        macro=macro,
        rows_data=[{"OtherCol": "123"}],
        data_file_path="dummy.csv",
    )
    assert any("Dept" in i.message for i in issues)

    # Execute action with valid row_data and mocked selector resolution
    fake_elem = UIElementInfo(
        hwnd=301,
        root_hwnd=100,
        window_title="ERP System",
        window_class="MainWnd",
        control_type="Button",
        automation_id="10",
        name="Save Finance",
        class_name="Button",
        rect=(50, 50, 100, 40),
    )
    with (
        patch("stepwise.services.uia_win.resolve_selector", return_value=fake_elem),
        patch("stepwise.services.uia_win.simulate_click_at_hwnd", return_value=(True, "")) as sim,
    ):
        execute_action(act, row_data={"Dept": "Finance"}, default_wait_before=0.0)
        sim.assert_called_once()


def test_properties_panel_selector_and_guard_verify_editors(qapp: QApplication) -> None:
    panel = PropertiesPanel()
    act = ActionItem(
        type="click",
        x=100,
        y=200,
        guard=ImageCondition(image="images/g.png", confidence=0.9, timeout=5.0),
        verify=ImageCondition(image="images/v.png", confidence=0.85, timeout=8.0),
    )
    panel.set_action(act)

    assert panel.cmb_target_mode is not None
    assert panel.cmb_click_method is not None
    assert panel.txt_guard_image is not None and panel.txt_guard_image.text() == "images/g.png"
    assert panel.txt_verify_image is not None and panel.txt_verify_image.text() == "images/v.png"

    # Editing Guard/Verify image path preserves existing confidence and timeout settings
    panel.txt_guard_image.setText("images/g_new.png")
    assert act.guard is not None
    assert act.guard.image == "images/g_new.png"
    assert act.guard.confidence == 0.9
    assert act.guard.timeout == 5.0

    # Switch target mode to selector and click method to simulate
    panel.cmb_target_mode.setCurrentIndex(1)
    panel.cmb_click_method.setCurrentIndex(1)
    assert act.target_mode == "selector"
    assert act.click_method == "simulate"


# =====================================================================
# 4. Night-Shift Task Scheduler ("Armed Mode") Tests
# =====================================================================


def test_schedule_compute_next_occurrence_and_countdown() -> None:
    ref = datetime(2026, 10, 31, 23, 0, 0)
    # 02:00 AM is tomorrow relative to 23:00
    next_dt = compute_next_occurrence(time(2, 0, 0), now=ref)
    assert next_dt == datetime(2026, 11, 1, 2, 0, 0)
    assert format_countdown((next_dt - ref).total_seconds()) == "03:00:00"


def test_scheduler_dialog_checklist_gating_and_arming(qapp: QApplication) -> None:
    macro = Macro(
        name="Night Batch",
        per_row=[ActionItem(type="wait", seconds=0.1)],
    )
    ok_diags = [
        ScheduleDiagItem(level="ok", title="Macro preflight passed"),
        ScheduleDiagItem(level="ok", title="Screen buffer active"),
    ]
    with (
        patch(
            "stepwise.ui.scheduler_dialog.run_schedule_pre_arm_diagnostics",
            return_value=ok_diags,
        ),
        patch("stepwise.ui.scheduler_dialog.set_awake_state") as mock_awake,
    ):
        dlg = SchedulerDialog(
            macro=macro,
            rows_data=[{"A": "1"}],
            row_numbers=[1],
        )
        # Initially Arm button is disabled until all 3 safety checkboxes are checked
        assert dlg.btn_arm.isEnabled() is False

        dlg.chk_dont_close.setChecked(True)
        dlg.chk_power.setChecked(True)
        assert dlg.btn_arm.isEnabled() is False

        dlg.chk_erp_ready.setChecked(True)
        assert dlg.btn_arm.isEnabled() is True

        # Arm schedule
        dlg.arm_schedule(now=datetime(2026, 10, 31, 1, 59, 59))
        assert dlg.is_armed is True
        mock_awake.assert_called_with(True)

        # Pressing Esc (reject) while armed must disarm and release awake state
        dlg.reject()
        assert dlg.is_armed is False
        mock_awake.assert_called_with(False)

        # Re-arm and test stale wakeup (>15m overdue) safety abort
        dlg.arm_schedule(now=datetime(2026, 10, 31, 1, 59, 59))
        assert dlg.is_armed is True
        dlg._on_armed_tick(now=datetime(2026, 10, 31, 2, 20, 0))
        assert dlg.is_armed is False
        assert "15" in dlg.lbl_banner.text()
        dlg.close()
