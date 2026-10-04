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
        mock_set.assert_called_once_with(12345, x=0, y=0, width=1280, height=800, maximize=True)


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
