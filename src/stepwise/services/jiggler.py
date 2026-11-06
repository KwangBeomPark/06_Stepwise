"""Anti-Lock Jiggler Service.

Periodically sends an invisible virtual key pulse (VK_F15) via SendInput to reset
the Windows OS idle timer (GetLastInputInfo) without disturbing user input,
mouse focus, or open windows. Helps prevent Corporate GPO inactivity screen lock
and RDP session idle disconnection during long automation runs and overnight scheduling.
"""

from __future__ import annotations

import ctypes
import math
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from ctypes import wintypes

VK_F15 = 0x7E  # Extended unassigned function key (no character, ignored by apps)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


def safe_jiggler_interval(
    val: object,
    default: float = 45.0,
    min_val: float = 10.0,
    max_val: float = 3600.0,
) -> float:
    """Safely parse interval setting to float, falling back to default on invalid/null/overflow input."""
    try:
        if val is None:
            return default
        f_val = float(val)  # type: ignore[arg-type]
        if not math.isfinite(f_val):
            return default
        return min(max_val, max(min_val, f_val))
    except (ValueError, TypeError, OverflowError):
        return default


def get_idle_duration_seconds() -> float | None:
    """Return time in seconds since the last physical or simulated user input.

    Returns None if GetLastInputInfo fails or on non-Windows environments (fail-safe).
    """
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if user32.GetLastInputInfo(ctypes.byref(lii)):
            # Handle 32-bit tick count wrapping gracefully
            tick_diff = (kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF
            return max(0.0, float(tick_diff) / 1000.0)
    except Exception:
        pass
    return None  # On failure or non-Windows, do not assume idle


def send_jiggle_pulse() -> bool:
    """Send an unassigned virtual key pulse (VK_F15) to reset Windows idle timer."""
    try:
        from stepwise.services.input_win import (
            INPUT,
            INPUT_KEYBOARD,
            KEYEVENTF_KEYUP,
            send_inputs,
        )

        inp_down = INPUT(type=INPUT_KEYBOARD)
        inp_down.u.ki.wVk = VK_F15
        inp_down.u.ki.dwFlags = 0

        inp_up = INPUT(type=INPUT_KEYBOARD)
        inp_up.u.ki.wVk = VK_F15
        inp_up.u.ki.dwFlags = KEYEVENTF_KEYUP

        return send_inputs([inp_down, inp_up]) == 2
    except Exception:
        return False


class Jiggler:
    """Background thread that periodically sends an invisible key pulse to prevent Windows idle lock."""

    def __init__(
        self,
        interval_seconds: float = 45.0,
        should_pulse: Callable[[], bool] | None = None,
        min_interval: float = 10.0,
    ) -> None:
        self.interval = safe_jiggler_interval(interval_seconds, default=45.0, min_val=min_interval)
        self.should_pulse = should_pulse
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background jiggler thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            args=(self._stop_event,),
            name="StepwiseJigglerThread",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background jiggler thread cleanly."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            if thread.is_alive():
                thread.join(timeout=2.0)
            if not thread.is_alive():
                self._thread = None

    def is_running(self) -> bool:
        """Return True if the jiggler background thread is active."""
        return self._thread is not None and self._thread.is_alive()

    def _run(self, stop_event: threading.Event) -> None:
        check_step = min(1.0, max(0.1, self.interval / 2.0))
        last_pulse_at = time.monotonic()

        while not stop_event.is_set():
            if stop_event.wait(timeout=check_step):
                break

            now = time.monotonic()
            if now - last_pulse_at < self.interval:
                continue

            # Respect caller gating (e.g. paused/stopped execution)
            if self.should_pulse is not None and not self.should_pulse():
                continue

            # Check if OS is actually idle (at least 80% of interval elapsed with no input).
            # If GetLastInputInfo fails (None) or system is active, skip pulse to avoid interference.
            idle_sec = get_idle_duration_seconds()
            if idle_sec is None or idle_sec < self.interval * 0.8:
                continue

            # Final check before sending pulse in case stop or pause just occurred
            if stop_event.is_set():
                break
            if self.should_pulse is not None and not self.should_pulse():
                continue

            if send_jiggle_pulse():
                last_pulse_at = time.monotonic()


@contextmanager
def active_jiggler(
    enabled: bool = True,
    interval_seconds: float = 45.0,
    should_pulse: Callable[[], bool] | None = None,
    min_interval: float = 10.0,
) -> Generator[Jiggler | None, None, None]:
    """Context manager to hold an active jiggler while running a code block."""
    if not enabled:
        yield None
        return
    jiggler = Jiggler(
        interval_seconds=interval_seconds,
        should_pulse=should_pulse,
        min_interval=min_interval,
    )
    jiggler.start()
    try:
        yield jiggler
    finally:
        jiggler.stop()
