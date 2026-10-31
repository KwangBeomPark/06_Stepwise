"""Windows power and screensaver inhibition service.

Uses SetThreadExecutionState to prevent display sleep during macro runs.
"""

from __future__ import annotations

import ctypes
from collections.abc import Generator
from contextlib import contextmanager

# SetThreadExecutionState Flags
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_CONTINUOUS = 0x80000000


@contextmanager
def prevent_screen_sleep() -> Generator[None, None, None]:
    """Context manager to prevent display sleep and screensaver while executing."""
    set_awake_state(True)
    try:
        yield
    finally:
        set_awake_state(False)


def set_awake_state(awake: bool) -> None:
    """Explicitly enable or disable continuous system/display awake state on the calling thread."""
    try:
        kernel32 = ctypes.windll.kernel32
        if awake:
            kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
        else:
            kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass


def lock_workstation() -> bool:
    """Lock the interactive Windows session (LockWorkStation) after unattended completion."""
    try:
        user32 = ctypes.windll.user32
        return bool(user32.LockWorkStation())
    except Exception:
        return False
