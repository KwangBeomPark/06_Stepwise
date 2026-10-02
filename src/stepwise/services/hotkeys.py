"""Global hotkey listener using Win32 RegisterHotKey without administrative rights.

Runs a dedicated background message loop to intercept hotkeys (default: F12 for Emergency Stop).
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes

user32 = ctypes.windll.user32

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012


class GlobalHotkeyManager:
    """Manages global hotkey registration and message pumping."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._running = False
        self._registered_keys: dict[int, tuple[int, int, Callable[[], None]]] = {}
        self._next_id = 1
        self._init_event = threading.Event()
        self._init_error: str | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._init_event.clear()
        self._init_error = None
        self._thread = threading.Thread(target=self._msg_loop, daemon=True, name="StepwiseHotKeyLoop")
        self._thread.start()
        self._init_event.wait(timeout=2.0)
        if self._init_error:
            raise RuntimeError(self._init_error)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._thread_id = None

    def register_hotkey(
        self,
        vk_code: int,
        modifiers: int = 0,
        callback: Callable[[], None] | None = None,
    ) -> int:
        """Register a hotkey with an optional callback."""
        hotkey_id = self._next_id
        self._next_id += 1

        # Register immediately if loop is running on thread
        res = user32.RegisterHotKey(None, hotkey_id, modifiers | MOD_NOREPEAT, vk_code)
        if not res:
            err = ctypes.get_last_error()
            raise RuntimeError(
                f"Failed to register global hotkey (VK: {hex(vk_code)}). "
                f"Key may already be in use by another application (Error: {err})."
            )

        if callback:
            self._registered_keys[hotkey_id] = (modifiers, vk_code, callback)

        return hotkey_id

    def unregister_hotkey(self, hotkey_id: int) -> None:
        user32.UnregisterHotKey(None, hotkey_id)
        self._registered_keys.pop(hotkey_id, None)

    def unregister_all(self) -> None:
        for hid in list(self._registered_keys.keys()):
            self.unregister_hotkey(hid)

    def _msg_loop(self) -> None:
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        self._init_event.set()

        msg = wintypes.MSG()
        while self._running:
            # GetMessage blocks until a message is available
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res <= 0:
                break

            if msg.message == WM_HOTKEY:
                hotkey_id = msg.wParam
                entry = self._registered_keys.get(hotkey_id)
                if entry:
                    _, _, cb = entry
                    try:
                        cb()
                    except Exception as e:
                        print(f"Error in hotkey callback: {e}")

            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
