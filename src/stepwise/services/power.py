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
    kernel32 = ctypes.windll.kernel32
    try:
        kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
        yield
    finally:
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)
