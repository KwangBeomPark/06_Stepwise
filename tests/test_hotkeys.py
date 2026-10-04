"""Unit tests for GlobalHotkeyManager."""

from __future__ import annotations

import sys
import threading
from unittest.mock import patch

import pytest

from stepwise.services import hotkeys
from stepwise.services.hotkeys import GlobalHotkeyManager


def test_hotkey_manager_lifecycle_mocked() -> None:
    register_threads: list[int] = []
    unregister_threads: list[int] = []

    def _register(*args: object) -> int:
        register_threads.append(threading.get_ident())
        return 1

    def _unregister(*args: object) -> int:
        unregister_threads.append(threading.get_ident())
        return 1

    with (
        patch.object(hotkeys.user32, "RegisterHotKey", side_effect=_register) as mock_reg,
        patch.object(hotkeys.user32, "UnregisterHotKey", side_effect=_unregister) as mock_unreg,
    ):
        mgr = GlobalHotkeyManager()
        mgr.start()
        assert mgr._running is True
        loop_thread_id = mgr._thread.ident

        called = False

        def _cb() -> None:
            nonlocal called
            called = True

        hid = mgr.register_hotkey(0x7B, 0, _cb)  # VK_F12
        assert hid >= 1
        assert mock_reg.called

        mgr.stop()
        assert mgr._running is False
        assert mock_unreg.called
        assert register_threads == [loop_thread_id]
        assert unregister_threads == [loop_thread_id]


def test_hotkey_manager_restart_releases_callbackless_registration() -> None:
    active_keys: set[tuple[int, int]] = set()

    def _register(_window: object, _hid: int, modifiers: int, vk_code: int) -> int:
        key = (modifiers, vk_code)
        if key in active_keys:
            return 0
        active_keys.add(key)
        return 1

    def _unregister(_window: object, hid: int) -> int:
        if hid in (1, 2):
            active_keys.clear()
        return 1

    with (
        patch.object(hotkeys.user32, "RegisterHotKey", side_effect=_register),
        patch.object(hotkeys.user32, "UnregisterHotKey", side_effect=_unregister),
    ):
        mgr = GlobalHotkeyManager()
        mgr.register_hotkey(0x7B)
        mgr.stop()
        assert not active_keys

        mgr.register_hotkey(0x7B)
        mgr.stop()
        assert not active_keys


def test_hotkey_manager_unregisters_on_message_loop_exit() -> None:
    with (
        patch.object(hotkeys.user32, "RegisterHotKey", return_value=1),
        patch.object(hotkeys.user32, "UnregisterHotKey", return_value=1) as mock_unreg,
    ):
        mgr = GlobalHotkeyManager()
        hid = mgr.register_hotkey(0x7B)
        assert mgr._thread_id is not None
        assert mgr._thread is not None

        hotkeys.user32.PostThreadMessageW(mgr._thread_id, hotkeys.WM_QUIT, 0, 0)
        mgr._thread.join(timeout=1.0)

        assert not mgr._thread.is_alive()
        mock_unreg.assert_called_once_with(None, hid)
        assert mgr._registered_keys == {}
        assert mgr._running is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_hotkey_manager_double_start_stop() -> None:
    """Ensure starting and stopping multiple times doesn't leave dangling resources."""
    mgr = GlobalHotkeyManager()
    mgr.start()
    mgr.start()  # Idempotent
    mgr.stop()
    mgr.stop()  # Idempotent
