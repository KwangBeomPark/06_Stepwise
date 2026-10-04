"""Spike 6: Win32 RegisterHotKey Verification.

Tests registration and deregistration of global hotkeys (e.g. F12 = 0x7B) without admin rights.
"""

from __future__ import annotations

import ctypes

user32 = ctypes.windll.user32
VK_F12 = 0x7B
VK_F11 = 0x7A
VK_F8 = 0x77
VK_F9 = 0x78


def test_hotkey_registration(vk_code: int = VK_F12, hotkey_id: int = 1) -> dict[str, object]:
    # RegisterHotKey(hWnd, id, fsModifiers, vk)
    # MOD_NOREPEAT = 0x4000
    res_reg = user32.RegisterHotKey(None, hotkey_id, 0x4000, vk_code)
    last_err = ctypes.get_last_error()

    unreg_ok = False
    if res_reg:
        unreg_res = user32.UnregisterHotKey(None, hotkey_id)
        unreg_ok = bool(unreg_res)

    return {
        "status": "OK" if res_reg and unreg_ok else "FAIL",
        "vk_code_hex": hex(vk_code),
        "registered": bool(res_reg),
        "unregistered": unreg_ok,
        "win32_last_error": last_err if not res_reg else 0,
        "note": "Registered and safely unregistered."
        if res_reg
        else "Could not register; key might be held by system/client",
    }


if __name__ == "__main__":
    res = test_hotkey_registration(VK_F12)
    print("--- Hotkey F12 Spike Results ---")
    for k, v in res.items():
        print(f"  {k}: {v}")
