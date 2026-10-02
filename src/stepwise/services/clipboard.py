"""Windows Clipboard services with automatic backup and restore.

Supports full Unicode text (CF_UNICODETEXT) with retry loops for contention safety.
"""

from __future__ import annotations

import ctypes
import time
from collections.abc import Generator
from contextlib import contextmanager
from ctypes import wintypes

# Win32 Constants
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL


def get_clipboard_text(retries: int = 5, retry_delay: float = 0.03) -> str | None:
    """Retrieve current text from Windows clipboard. Returns None if empty or non-text."""
    for _ in range(retries):
        if user32.OpenClipboard(None):
            try:
                h_data = user32.GetClipboardData(CF_UNICODETEXT)
                if not h_data:
                    return ""
                ptr = kernel32.GlobalLock(h_data)
                if not ptr:
                    return ""
                try:
                    return ctypes.wstring_at(ptr)
                finally:
                    kernel32.GlobalUnlock(h_data)
            finally:
                user32.CloseClipboard()
        time.sleep(retry_delay)
    return None


def set_clipboard_text(text: str, retries: int = 5, retry_delay: float = 0.03) -> bool:
    """Write text to Windows clipboard as Unicode."""
    raw_bytes = text.encode("utf-16le") + b"\x00\x00"
    for _ in range(retries):
        if user32.OpenClipboard(None):
            try:
                user32.EmptyClipboard()
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw_bytes))
                if not h_mem:
                    return False
                ptr = kernel32.GlobalLock(h_mem)
                if not ptr:
                    return False
                ctypes.memmove(ptr, raw_bytes, len(raw_bytes))
                kernel32.GlobalUnlock(h_mem)
                res = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                return bool(res)
            finally:
                user32.CloseClipboard()
        time.sleep(retry_delay)
    return False


@contextmanager
def temporary_clipboard_text(text: str, restore: bool = True) -> Generator[None, None, None]:
    """Context manager that puts text on clipboard and restores the previous content on exit."""
    original_text = get_clipboard_text() if restore else None
    set_clipboard_text(text)
    try:
        yield
    finally:
        if restore and original_text is not None:
            # Short stabilization before restoring so paste has time to complete
            time.sleep(0.05)
            set_clipboard_text(original_text)
