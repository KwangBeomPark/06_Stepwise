"""Global hotkey listener using Win32 RegisterHotKey without administrative rights.

Runs a dedicated background message loop to intercept hotkeys (default: F12 for Emergency Stop).
Ensures RegisterHotKey and UnregisterHotKey are invoked on the message loop thread to avoid thread-affinity bugs.
"""

from __future__ import annotations

import ctypes
import queue
import threading
from collections.abc import Callable
from ctypes import wintypes
from typing import Any

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_USER = 0x0400
WM_HOTKEY_CMD = WM_USER + 101


class GlobalHotkeyManager:
    """Manages global hotkey registration and message pumping on a dedicated thread."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._running = False
        self._registered_keys: dict[int, tuple[int, int, Callable[[], None] | None]] = {}
        self._next_id = 1
        self._init_event = threading.Event()
        self._init_error: str | None = None
        self._cmd_queue: queue.Queue[tuple[str, Any, threading.Event | None, list[Any]]] = (
            queue.Queue()
        )

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._init_event.clear()
        self._init_error = None
        self._thread = threading.Thread(
            target=self._msg_loop, daemon=True, name="StepwiseHotKeyLoop"
        )
        self._thread.start()
        if not self._init_event.wait(timeout=2.0):
            self._running = False
            if self._thread_id:
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread.join(timeout=1.0)
            raise RuntimeError("Timed out while starting the global hotkey message loop")
        if self._init_error:
            self._running = False
            raise RuntimeError(self._init_error)

    def stop(self) -> None:
        if not self._running and not (self._thread and self._thread.is_alive()):
            return
        self._running = False
        if self._thread_id:
            done_event = threading.Event()
            self._cmd_queue.put(("STOP", None, done_event, []))
            user32.PostThreadMessageW(self._thread_id, WM_HOTKEY_CMD, 0, 0)
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            done_event.wait(timeout=0.5)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if not self._thread or not self._thread.is_alive():
            self._thread = None
            self._thread_id = None
            self._registered_keys.clear()

    def register_hotkey(
        self,
        vk_code: int,
        modifiers: int = 0,
        callback: Callable[[], None] | None = None,
    ) -> int:
        """Register a hotkey with an optional callback on the message loop thread."""
        if not self._running:
            self.start()

        hotkey_id = self._next_id
        self._next_id += 1

        done_event = threading.Event()
        result_holder: list[Any] = [False, None]  # [success, error_str]
        self._cmd_queue.put(
            ("REGISTER", (hotkey_id, vk_code, modifiers, callback), done_event, result_holder)
        )
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_HOTKEY_CMD, 0, 0)

        if not done_event.wait(timeout=2.0):
            raise RuntimeError(f"Timed out while registering hotkey {hex(vk_code)}")
        ok, err_msg = result_holder
        if not ok:
            raise RuntimeError(err_msg or f"Failed to register hotkey {hex(vk_code)}")

        return hotkey_id

    def unregister_hotkey(self, hotkey_id: int) -> None:
        if not self._running or not self._thread_id:
            return
        done_event = threading.Event()
        self._cmd_queue.put(("UNREGISTER", hotkey_id, done_event, []))
        user32.PostThreadMessageW(self._thread_id, WM_HOTKEY_CMD, 0, 0)
        if not done_event.wait(timeout=1.0):
            raise RuntimeError(f"Timed out while unregistering hotkey ID {hotkey_id}")

    def unregister_all(self) -> None:
        for hid in list(self._registered_keys.keys()):
            self.unregister_hotkey(hid)

    def _msg_loop(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()

        # Force creation of message queue for this thread
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        self._init_event.set()

        try:
            while self._running:
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res <= 0 or msg.message == WM_QUIT:
                    break

                if msg.message == WM_HOTKEY_CMD:
                    self._process_commands()
                elif msg.message == WM_HOTKEY:
                    hotkey_id = msg.wParam
                    entry = self._registered_keys.get(hotkey_id)
                    if entry:
                        _, _, cb = entry
                        try:
                            if cb:
                                cb()
                        except Exception as e:
                            print(f"Error in hotkey callback: {e}")

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            # Clean up all registered hotkeys before the thread terminates
            for hid in list(self._registered_keys.keys()):
                user32.UnregisterHotKey(None, hid)
            self._registered_keys.clear()
            self._running = False
            self._thread_id = None

    def _process_commands(self) -> None:
        while True:
            try:
                cmd, payload, event, result_holder = self._cmd_queue.get_nowait()
            except queue.Empty:
                break

            if cmd == "REGISTER":
                hid, vk, mod, cb = payload
                res = user32.RegisterHotKey(None, hid, mod | MOD_NOREPEAT, vk)
                if res:
                    # Track every successful registration, including callback-less
                    # hotkeys, so stop/restart cannot leak the Win32 registration.
                    self._registered_keys[hid] = (mod, vk, cb)
                    if result_holder is not None:
                        result_holder[0] = True
                else:
                    err = kernel32.GetLastError()
                    if result_holder is not None:
                        result_holder[0] = False
                        result_holder[1] = (
                            f"Failed to register global hotkey (VK: {hex(vk)}). "
                            f"Key may already be in use by another application (Win32 Error: {err})."
                        )
                if event:
                    event.set()

            elif cmd == "UNREGISTER":
                hid = payload
                user32.UnregisterHotKey(None, hid)
                self._registered_keys.pop(hid, None)
                if event:
                    event.set()

            elif cmd == "STOP":
                for hid in list(self._registered_keys.keys()):
                    user32.UnregisterHotKey(None, hid)
                self._registered_keys.clear()
                self._running = False
                if event:
                    event.set()
