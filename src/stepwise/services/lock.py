"""File-based collaborative editing lock for .swm archives (Section 13.2).

Prevents accidental concurrent overwrites on shared network drives.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

STALE_LOCK_TIMEOUT_SECONDS = 300  # 5 minutes


@dataclass
class LockInfo:
    user: str
    machine: str
    started_at: str
    heartbeat_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> LockInfo:
        return cls(
            user=data.get("user", "Unknown"),
            machine=data.get("machine", "Unknown"),
            started_at=data.get("started_at", ""),
            heartbeat_at=data.get("heartbeat_at", ""),
        )


def get_lock_file_path(swm_path: str) -> str:
    return f"{swm_path}.lock"


def check_lock_status(swm_path: str) -> tuple[bool, LockInfo | None, bool]:
    """Check if macro is locked.

    Returns: (is_locked, lock_info, is_stale)
    """
    lock_path = get_lock_file_path(swm_path)
    if not os.path.exists(lock_path):
        return False, None, False

    try:
        with open(lock_path, encoding="utf-8") as f:
            data = json.load(f)
        info = LockInfo.from_dict(data)

        # Parse heartbeat to check if stale
        is_stale = False
        if info.heartbeat_at:
            try:
                hb_dt = datetime.fromisoformat(info.heartbeat_at)
                now_dt = datetime.now()
                # Normalize timezone if present
                if hb_dt.tzinfo is not None:
                    now_dt = datetime.now(UTC)
                age_sec = (now_dt - hb_dt).total_seconds()
                if age_sec > STALE_LOCK_TIMEOUT_SECONDS:
                    is_stale = True
            except Exception:
                is_stale = True

        return True, info, is_stale
    except Exception:
        # Broken lock file
        return True, None, True


def acquire_lock(swm_path: str, force: bool = False) -> LockInfo:
    """Acquire edit lock for a macro file.

    Raises PermissionError if already locked by another user and not stale.
    """
    is_locked, info, is_stale = check_lock_status(swm_path)
    current_user = getpass.getuser()
    current_machine = platform.node()

    if is_locked and not force and not is_stale:
        if info and (info.user != current_user or info.machine != current_machine):
            raise PermissionError(
                f"Macro is currently being edited by '{info.user}' on '{info.machine}'."
            )

    lock_path = get_lock_file_path(swm_path)
    now_str = datetime.now().isoformat()
    lock_info = LockInfo(
        user=current_user,
        machine=current_machine,
        started_at=now_str,
        heartbeat_at=now_str,
    )

    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump(lock_info.to_dict(), f, indent=2)

    return lock_info


def heartbeat_lock(swm_path: str) -> bool:
    """Update heartbeat timestamp of current lock."""
    lock_path = get_lock_file_path(swm_path)
    if not os.path.exists(lock_path):
        return False

    try:
        with open(lock_path, encoding="utf-8") as f:
            data = json.load(f)
        data["heartbeat_at"] = datetime.now().isoformat()
        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def release_lock(swm_path: str) -> None:
    """Release and delete the edit lock file."""
    lock_path = get_lock_file_path(swm_path)
    if os.path.exists(lock_path):
        try:
            os.remove(lock_path)
        except OSError:
            pass
