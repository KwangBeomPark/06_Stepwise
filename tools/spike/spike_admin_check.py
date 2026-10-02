"""Spike 9: Admin Privilege & UAC Execution Context.

Verifies if current process runs as standard user vs. elevated administrator.
"""

from __future__ import annotations

import ctypes


def check_process_privileges() -> dict[str, object]:
    shell32 = ctypes.windll.shell32
    is_admin = bool(shell32.IsUserAnAdmin())

    return {
        "status": "OK",
        "is_admin": is_admin,
        "execution_mode": "Elevated (Administrator)" if is_admin else "Standard User (Non-Admin)",
        "recommendation": (
            "Stepwise runs properly under Standard User. If target ERP runs as Admin, "
            "SendInput may be blocked by UIPI unless Stepwise is also elevated."
            if not is_admin
            else "Running as Administrator. SendInput will reach both elevated and non-elevated targets."
        ),
    }


if __name__ == "__main__":
    res = check_process_privileges()
    print("--- Admin Privilege Spike Results ---")
    for k, v in res.items():
        print(f"  {k}: {v}")
