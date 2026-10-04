"""Win32 Window positioning, resizing, and alignment services.

Provides robust window discovery and bounds enforcement via user32 APIs.
Supports restoring minimized/maximized windows, positioning to (0,0), and custom sizing.
"""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

# Win32 Constants
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOW = 5
SW_RESTORE = 9

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

GW_OWNER = 4
GWL_STYLE = -16
WS_CHILD = 0x40000000

# Explicit ctypes function prototypes for 64-bit safe interop
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL

user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL

user32.IsZoomed.argtypes = [wintypes.HWND]
user32.IsZoomed.restype = wintypes.BOOL

user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND

user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int

user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL

user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

if hasattr(user32, "GetWindowLongPtrW"):
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    _get_window_long = user32.GetWindowLongPtrW
else:
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
    _get_window_long = user32.GetWindowLongW


def get_window_title(hwnd: int) -> str:
    """Retrieve window title text for given HWND."""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def is_alt_tab_window(hwnd: int, exclude_pid: int | None = None) -> bool:
    """Check if window is a valid, visible top-level interactive application window."""
    if not user32.IsWindowVisible(hwnd):
        return False

    # Filter out current process's own windows (e.g. Stepwise main window)
    if exclude_pid is not None:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == exclude_pid:
            return False

    # Must not have an owner window (top-level only)
    if user32.GetWindow(hwnd, GW_OWNER) != 0:
        return False

    title = get_window_title(hwnd).strip()
    if not title:
        return False

    # Check that it is not a child window
    style = _get_window_long(hwnd, GWL_STYLE)
    if style & WS_CHILD:
        return False

    return True


def list_visible_windows(exclude_self: bool = True) -> list[tuple[int, str]]:
    """Enumerate all visible interactive top-level application windows with titles."""
    windows: list[tuple[int, str]] = []
    own_pid = os.getpid() if exclude_self else None

    def _enum_proc(hwnd: int, lparam: int) -> bool:
        if is_alt_tab_window(hwnd, exclude_pid=own_pid):
            title = get_window_title(hwnd)
            windows.append((hwnd, title))
        return True

    cb = WNDENUMPROC(_enum_proc)
    user32.EnumWindows(cb, 0)
    return windows


def find_window_by_title(
    title_pattern: str, exact: bool = False, exclude_self: bool = True
) -> int | None:
    """Find the best matching visible top-level application window handle.

    - Prioritizes exact title match before falling back to substring match.
    - Excludes windows belonging to the current process (Stepwise).
    - Only matches visible windows to prevent activating hidden/system helper windows.
    """
    pattern = title_pattern.strip().lower()
    if not pattern:
        return None

    visible = list_visible_windows(exclude_self=exclude_self)

    # Pass 1: Exact case-insensitive match
    for hwnd, title in visible:
        if title.lower() == pattern:
            return hwnd

    if exact:
        return None

    # Pass 2: Substring match
    for hwnd, title in visible:
        if pattern in title.lower():
            return hwnd

    return None


def set_window_bounds(
    hwnd: int,
    x: int = 0,
    y: int = 0,
    width: int = 1280,
    height: int = 800,
    maximize: bool = False,
    settle_seconds: float = 0.2,
) -> tuple[bool, str]:
    """Position and size window. Restores minimized windows and brings to front.

    Returns (success: bool, error_message: str).
    """
    if not user32.IsWindow(hwnd):
        return False, "Invalid window handle (window may have closed)."

    # 1. Restore if minimized
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.1)

    # 2. Handle maximize or custom bounds
    if maximize:
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
    else:
        # If currently maximized, un-maximize (restore) first to allow custom sizing
        if user32.IsZoomed(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.1)

        # Do not force SWP_SHOWWINDOW if window is already visible; avoid unhiding hidden windows
        flags = SWP_NOZORDER
        ok = user32.SetWindowPos(
            hwnd,
            0,
            int(x),
            int(y),
            max(100, int(width)),
            max(100, int(height)),
            flags,
        )
        if not ok:
            err = ctypes.get_last_error()
            msg = f"SetWindowPos failed (Win32 error {err})."
            if err == 5:  # ERROR_ACCESS_DENIED
                msg += " Target window may be running as Administrator (UIPI blocked)."
            return False, msg

    # 3. Bring to front and activate
    user32.SetForegroundWindow(hwnd)

    if settle_seconds > 0:
        time.sleep(settle_seconds)

    return True, ""
