"""Spike 8: Window Display Affinity (WDA_EXCLUDEFROMCAPTURE) Spike.

Verifies if SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE) is supported on this Windows build.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011


def check_display_affinity_support() -> dict[str, object]:
    has_api = hasattr(user32, "SetWindowDisplayAffinity")
    if not has_api:
        return {
            "status": "NOT_SUPPORTED",
            "has_api": False,
            "fallback_required": True,
            "fallback_strategy": "Hide floating window briefly during mss.grab()",
        }

    h_instance = ctypes.windll.kernel32.GetModuleHandleW(None)
    wnd_class = "StepwiseDummyAffinityTest"

    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("style", wintypes.UINT),
            ("lpfnWndProc", ctypes.c_void_p),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HANDLE),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
            ("hIconSm", wintypes.HANDLE),
        ]

    w_proc = user32.DefWindowProcW

    wc = WNDCLASSEX()
    wc.cbSize = ctypes.sizeof(WNDCLASSEX)
    wc.style = 0
    wc.lpfnWndProc = ctypes.cast(w_proc, ctypes.c_void_p)
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = h_instance
    wc.hIcon = None
    wc.hCursor = None
    wc.hbrBackground = None
    wc.lpszMenuName = None
    wc.lpszClassName = wnd_class
    wc.hIconSm = None

    user32.RegisterClassExW(ctypes.byref(wc))

    hwnd = user32.CreateWindowExW(
        0x00080000,  # WS_EX_LAYERED
        wnd_class,
        "StepwiseAffinityTest",
        0x80000000,  # WS_POPUP
        0, 0, 100, 100,
        None, None, h_instance, None,
    )

    affinity_applied = False
    last_err = 0
    if hwnd:
        affinity_res = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        affinity_applied = bool(affinity_res)
        last_err = ctypes.get_last_error()
        user32.DestroyWindow(hwnd)

    user32.UnregisterClassW(wnd_class, h_instance)

    return {
        "status": "OK" if affinity_applied else "FALLBACK_NEEDED",
        "has_api": True,
        "affinity_applied": affinity_applied,
        "win32_last_error": last_err,
        "recommended_approach": "WDA_EXCLUDEFROMCAPTURE" if affinity_applied else "Hide-before-capture fallback",
    }


if __name__ == "__main__":
    res = check_display_affinity_support()
    print("--- Window Display Affinity Spike Results ---")
    for k, v in res.items():
        print(f"  {k}: {v}")
