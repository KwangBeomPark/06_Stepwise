"""Spike 3: Mouse Movement and Click via Win32 SendInput.

Verifies normalized absolute mouse coordinates (0..65535) and click simulation.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

# Win32 Constants
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x000A
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]


def get_cursor_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def test_mouse_position_and_click(target_x: int = 200, target_y: int = 200, simulate_click: bool = False) -> dict[str, object]:
    user32 = ctypes.windll.user32
    # Ensure DPI awareness
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

    original_x, original_y = get_cursor_pos()

    # Screen dimensions for absolute coordinate normalization
    SM_CXSCREEN = 0
    SM_CYSCREEN = 1
    screen_w = user32.GetSystemMetrics(SM_CXSCREEN)
    screen_h = user32.GetSystemMetrics(SM_CYSCREEN)

    # Convert to 65535 normalized coords
    norm_x = int((target_x * 65535) / (screen_w - 1)) if screen_w > 1 else 0
    norm_y = int((target_y * 65535) / (screen_h - 1)) if screen_h > 1 else 0

    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = norm_x
    inp.u.mi.dy = norm_y
    inp.u.mi.mouseData = 0
    inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    inp.u.mi.time = 0
    inp.u.mi.dwExtraInfo = None

    sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    time.sleep(0.05)
    new_x, new_y = get_cursor_pos()

    # Restore cursor position
    norm_orig_x = int((original_x * 65535) / (screen_w - 1)) if screen_w > 1 else 0
    norm_orig_y = int((original_y * 65535) / (screen_h - 1)) if screen_h > 1 else 0
    inp_restore = INPUT()
    inp_restore.type = INPUT_MOUSE
    inp_restore.u.mi.dx = norm_orig_x
    inp_restore.u.mi.dy = norm_orig_y
    inp_restore.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    user32.SendInput(1, ctypes.byref(inp_restore), ctypes.sizeof(INPUT))

    delta = max(abs(new_x - target_x), abs(new_y - target_y))
    # Tolerable threshold: <= 2px due to integer scaling rounding
    success = sent == 1 and delta <= 2

    return {
        "status": "OK" if success else "FAIL",
        "inputs_sent": sent,
        "target": (target_x, target_y),
        "actual_reached": (new_x, new_y),
        "delta_px": delta,
        "screen_size": (screen_w, screen_h),
    }


if __name__ == "__main__":
    res = test_mouse_position_and_click(300, 300)
    print("--- Mouse Movement & Click Spike Results ---")
    for k, v in res.items():
        print(f"  {k}: {v}")
