"""Win32 SendInput wrapper for precision mouse and keyboard simulation.

Pure ctypes implementation with zero heavy external dependencies.
Fully supports 64-bit Windows alignment, multi-key shortcuts, and Unicode keystrokes.
"""

from __future__ import annotations

import ctypes
import struct
import time
from collections.abc import Callable, Sequence
from ctypes import wintypes

user32 = ctypes.windll.user32

# Input Types
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

# Mouse flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# Keyboard flags
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# Virtual Key Codes
VK_MAP: dict[str, int] = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "windows": 0x5B,
    "capslock": 0x14,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "f13": 0x7C,
    "f14": 0x7D,
    "f15": 0x7E,
    "f16": 0x7F,
    "f17": 0x80,
    "f18": 0x81,
    "f19": 0x82,
    "f20": 0x83,
    "f21": 0x84,
    "f22": 0x85,
    "f23": 0x86,
    "f24": 0x87,
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def get_screen_size() -> tuple[int, int]:
    """Return width and height of the primary screen in physical pixels."""
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass
    w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return (w, h) if w > 0 and h > 0 else (1920, 1080)


def send_inputs(inputs: Sequence[INPUT]) -> int:
    """Send an array of INPUT structures to the OS."""
    if not inputs:
        return 0
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    return user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(INPUT))


def move_mouse(x: int, y: int) -> bool:
    """Move mouse cursor to absolute physical screen coordinates (x, y)."""
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass
    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    screen_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    screen_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    if screen_w <= 0 or screen_h <= 0:
        return False
    if not (left <= x < left + screen_w and top <= y < top + screen_h):
        return False
    norm_x = int(((x - left) * 65535) / (screen_w - 1)) if screen_w > 1 else 0
    norm_y = int(((y - top) * 65535) / (screen_h - 1)) if screen_h > 1 else 0

    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = norm_x
    inp.u.mi.dy = norm_y
    inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    return send_inputs([inp]) > 0


def click_at(
    x: int,
    y: int,
    button: str = "left",
    clicks: int = 1,
    settle_delay: float = 0.04,
) -> bool:
    """Move cursor to (x, y), wait settle_delay (30-50ms), and click 1 or 2 times."""
    if not move_mouse(x, y):
        return False
    time.sleep(settle_delay)

    btn = button.lower()
    if btn == "right":
        down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
    elif btn == "middle":
        down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
    else:
        down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

    inputs: list[INPUT] = []
    for _ in range(clicks):
        inp_down = INPUT(type=INPUT_MOUSE)
        inp_down.u.mi.dwFlags = down_flag
        inp_up = INPUT(type=INPUT_MOUSE)
        inp_up.u.mi.dwFlags = up_flag
        inputs.extend([inp_down, inp_up])

    return bool(inputs) and send_inputs(inputs) == len(inputs)


def parse_key_combination(keys_str: str) -> list[int]:
    """Parse key string like 'ctrl+s' or 'Ctrl + Shift + End' into list of VK codes."""
    tokens = [t.strip().lower() for t in keys_str.split("+") if t.strip()]
    vk_codes: list[int] = []
    for token in tokens:
        if token in VK_MAP:
            vk_codes.append(VK_MAP[token])
        elif len(token) == 1:
            # Single alphanumeric character
            char = token.upper()
            vk_codes.append(ord(char))
        else:
            raise ValueError(f"Unknown key: '{token}'")
    return vk_codes


def release_all_modifiers() -> bool:
    """Safely release common modifier keys (Ctrl, Shift, Alt, Win) to prevent stuck keys."""
    modifiers = [
        0x11,  # VK_CONTROL
        0x10,  # VK_SHIFT
        0x12,  # VK_MENU (Alt)
        0x5B,  # VK_LWIN
        0x5C,  # VK_RWIN
    ]
    inputs: list[INPUT] = []
    for vk in modifiers:
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki.wVk = vk
        inp.u.ki.dwFlags = KEYEVENTF_KEYUP
        inputs.append(inp)
    return send_inputs(inputs) == len(inputs)


def release_keys(vk_codes: Sequence[int]) -> None:
    """Send Key-Up for all keys in the combination (in reverse order), followed by release_all_modifiers."""
    if vk_codes:
        cleanup_inputs: list[INPUT] = []
        for vk in reversed(vk_codes):
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.u.ki.wVk = vk
            inp.u.ki.dwFlags = KEYEVENTF_KEYUP
            cleanup_inputs.append(inp)
        send_inputs(cleanup_inputs)
    release_all_modifiers()


def press_keys(
    keys_str: str,
    repeat: int = 1,
    interval: float = 0.05,
    wait_fn: Callable[[float], object] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> bool:
    """Press and release a key or key combination with atomic verification and cancellation check.

    Preserves forward order for down, reverse order for up.
    """
    vk_codes = parse_key_combination(keys_str)
    if not vk_codes:
        return False

    for i in range(repeat):
        if should_stop is not None and should_stop():
            release_keys(vk_codes)
            return False

        inputs: list[INPUT] = []
        # Press down in order
        for vk in vk_codes:
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.u.ki.wVk = vk
            inp.u.ki.dwFlags = 0
            inputs.append(inp)

        # Release in reverse order
        for vk in reversed(vk_codes):
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.u.ki.wVk = vk
            inp.u.ki.dwFlags = KEYEVENTF_KEYUP
            inputs.append(inp)

        sent = send_inputs(inputs)
        if sent != len(inputs):
            release_keys(vk_codes)
            return False

        if i < repeat - 1:
            if wait_fn is not None:
                try:
                    res = wait_fn(interval)
                    if res is False:
                        release_keys(vk_codes)
                        return False
                except Exception:
                    release_keys(vk_codes)
                    return False
            else:
                time.sleep(interval)

    return True


def type_unicode_string(
    text: str,
    char_delay: float = 0.005,
    wait_fn: Callable[[float], object] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> bool:
    """Type text character-by-character using KEYEVENTF_UNICODE with UTF-16 surrogate support."""
    if not text:
        return True

    # Encode character-by-character to preserve surrogate pair atomicity (e.g. emojis)
    # A single codepoint may generate 1 or 2 UTF-16 code units (WORDs).
    char_batches: list[list[INPUT]] = []
    for ch in text:
        raw_bytes = ch.encode("utf-16le")
        num_words = len(raw_bytes) // 2
        words: tuple[int, ...] = struct.unpack(f"<{num_words}H", raw_bytes)
        ch_inputs: list[INPUT] = []
        for code in words:
            inp_down = INPUT(type=INPUT_KEYBOARD)
            inp_down.u.ki.wVk = 0
            inp_down.u.ki.wScan = code
            inp_down.u.ki.dwFlags = KEYEVENTF_UNICODE
            inp_up = INPUT(type=INPUT_KEYBOARD)
            inp_up.u.ki.wVk = 0
            inp_up.u.ki.wScan = code
            inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            ch_inputs.extend([inp_down, inp_up])
        char_batches.append(ch_inputs)

    def _cleanup_partial_send(sent_count: int, input_list: list[INPUT]) -> None:
        """If an odd number of events sent, the last down event has no up; send matching keyup."""
        if sent_count > 0 and sent_count % 2 == 1:
            last_down = input_list[sent_count - 1]
            release_inp = INPUT(type=INPUT_KEYBOARD)
            release_inp.u.ki.wVk = 0
            release_inp.u.ki.wScan = last_down.u.ki.wScan
            release_inp.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            send_inputs([release_inp])

    if char_delay <= 0 and wait_fn is None and should_stop is None:
        # Fast batch mode: flatten all character inputs
        all_inputs = [inp for batch in char_batches for inp in batch]
        sent = send_inputs(all_inputs)
        if sent != len(all_inputs):
            _cleanup_partial_send(sent, all_inputs)
            return False
        return True

    # Step-by-step mode with inter-character delay and cancellation check
    # cancellation and delay are checked strictly between full Unicode characters
    for ch_inputs in char_batches:
        if should_stop is not None and should_stop():
            return False

        sent = send_inputs(ch_inputs)
        if sent != len(ch_inputs):
            _cleanup_partial_send(sent, ch_inputs)
            return False

        if char_delay > 0:
            if wait_fn is not None:
                try:
                    res = wait_fn(char_delay)
                    if res is False:
                        return False
                except Exception:
                    return False
            else:
                time.sleep(char_delay)

    return True
