"""Unit tests for action execution and lifecycle handlers."""

from stepwise.engine.actions import execute_action
from stepwise.engine.timing import ExecutionController


def test_execute_disabled_action() -> None:
    action = {"type": "click", "x": 100, "y": 100, "enabled": False}
    execute_action(action, default_wait_before=0.0)


def test_execute_wait_action() -> None:
    ctrl = ExecutionController()
    action = {"type": "wait", "seconds": 0.005, "enabled": True}
    execute_action(action, controller=ctrl, default_wait_before=0.0)


def test_execute_group_action() -> None:
    ctrl = ExecutionController()
    action = {
        "type": "group",
        "name": "Test Group",
        "enabled": True,
        "items": [
            {"type": "wait", "seconds": 0.005, "enabled": True},
            {"type": "wait", "seconds": 0.005, "enabled": False},
        ],
    }
    execute_action(action, controller=ctrl, default_wait_before=0.0)
