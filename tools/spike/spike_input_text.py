"""Spike 5: Clipboard Paste vs. SendInput Unicode Keystrokes.

Verifies handling of Korean ("테스트"), Polish ("Zażółć gęślą jaźń"), and special symbols.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

# Win32 Constants
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Configure Win32 signatures
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


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]


def get_clipboard_text() -> str | None:
    for _ in range(5):
        if user32.OpenClipboard(None):
            try:
                h_data = user32.GetClipboardData(CF_UNICODETEXT)
                if not h_data:
                    return ""
                ptr = kernel32.GlobalLock(h_data)
                if not ptr:
                    return ""
                try:
                    text = ctypes.wstring_at(ptr)
                    return text
                finally:
                    kernel32.GlobalUnlock(h_data)
            finally:
                user32.CloseClipboard()
        time.sleep(0.02)
    return None


def set_clipboard_text(text: str) -> bool:
    for _ in range(5):
        if user32.OpenClipboard(None):
            try:
                user32.EmptyClipboard()
                raw_bytes = text.encode("utf-16le") + b"\x00\x00"
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
        time.sleep(0.02)
    return False


def simulate_unicode_char(char: str) -> bool:
    code = ord(char)
    inp_down = INPUT()
    inp_down.type = INPUT_KEYBOARD
    inp_down.u.ki.wVk = 0
    inp_down.u.ki.wScan = code
    inp_down.u.ki.dwFlags = KEYEVENTF_UNICODE

    inp_up = INPUT()
    inp_up.type = INPUT_KEYBOARD
    inp_up.u.ki.wVk = 0
    inp_up.u.ki.wScan = code
    inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP

    arr = (INPUT * 2)(inp_down, inp_up)
    sent = user32.SendInput(2, ctypes.byref(arr), ctypes.sizeof(INPUT))
    return sent == 2


def test_clipboard_and_keystrokes() -> dict[str, object]:
    test_str = "Stepwise 123 테스트 Zażółć gęślą jaźń €$#!"

    # 1. Test Clipboard Backup and Restore
    orig = get_clipboard_text()
    set_ok = set_clipboard_text(test_str)
    read_back = get_clipboard_text()
    # Restore original
    if orig is not None:
        set_clipboard_text(orig)

    clipboard_verified = set_ok and (read_back == test_str)

    # 2. Test Unicode Key Simulation (synthesize test without active target window)
    keystroke_verified = True
    for ch in "Test 123 한글":
        if not simulate_unicode_char(ch):
            keystroke_verified = False
            break

    return {
        "status": "OK" if clipboard_verified and keystroke_verified else "FAIL",
        "clipboard_set_ok": set_ok,
        "clipboard_readback_match": read_back == test_str,
        "clipboard_read_len": len(read_back) if read_back else 0,
        "unicode_keystroke_api_ok": keystroke_verified,
        "test_payload_sample": test_str[:25] + "...",
    }


if __name__ == "__main__":
    res = test_clipboard_and_keystrokes()
    print("--- Text Input & Clipboard Spike Results ---")
    for k, v in res.items():
        print(f"  {k}: {v}")
