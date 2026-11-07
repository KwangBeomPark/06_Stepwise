"""Windows Clipboard services with automatic backup and restore.

Supports full Unicode text (CF_UNICODETEXT) with retry loops for contention safety.
"""

from __future__ import annotations

import ctypes
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from ctypes import wintypes

# Win32 Constants
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

_active_session_depth = 0
_session_generation = 0
_session_original_clipboard: str | None = None
_session_last_stepwise_seq: int | None = None
_last_write_seq: int | None = None
_session_lock = threading.RLock()

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
user32.GetClipboardSequenceNumber.argtypes = []
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
user32.IsClipboardFormatAvailable.restype = wintypes.BOOL

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL


def get_clipboard_sequence_number() -> int:
    """Return the current Windows clipboard sequence number."""
    return int(user32.GetClipboardSequenceNumber())


def snapshot_restorable_text(retries: int = 5, retry_delay: float = 0.03) -> str | None:
    """Snapshot Unicode text from clipboard if present.

    Returns:
        str: Unicode string if CF_UNICODETEXT is available.
        None: If CF_UNICODETEXT is NOT present (e.g. image, file, or clipboard empty).
              This guarantees we do not overwrite non-text clipboard formats with an empty string.
    """
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return None
    return get_clipboard_text(retries=retries, retry_delay=retry_delay)


def get_clipboard_text(retries: int = 5, retry_delay: float = 0.03) -> str | None:
    """Retrieve current text from Windows clipboard. Returns None if empty, unavailable or read failed."""
    for _ in range(retries):
        if user32.OpenClipboard(None):
            try:
                h_data = user32.GetClipboardData(CF_UNICODETEXT)
                if not h_data:
                    return None
                ptr = kernel32.GlobalLock(h_data)
                if not ptr:
                    return None
                try:
                    return ctypes.wstring_at(ptr)
                finally:
                    kernel32.GlobalUnlock(h_data)
            finally:
                user32.CloseClipboard()
        time.sleep(retry_delay)
    return None


def get_last_stepwise_seq() -> int | None:
    """Return the clipboard sequence number of the most recent Stepwise write."""
    with _session_lock:
        return _session_last_stepwise_seq if _active_session_depth > 0 else _last_write_seq


def record_stepwise_clipboard_write(seq: int | None = None) -> None:
    """Record that Stepwise updated the clipboard."""
    global _session_last_stepwise_seq, _last_write_seq
    if seq is None:
        try:
            seq = get_clipboard_sequence_number()
        except Exception:
            seq = None
    _last_write_seq = seq
    with _session_lock:
        if _active_session_depth > 0:
            _session_last_stepwise_seq = seq


def write_clipboard_text(
    text: str,
    retries: int = 5,
    retry_delay: float = 0.03,
    expected_seq: int | None = None,
    expected_gen: int | None = None,
    is_restore: bool = False,
) -> tuple[bool, int | None]:
    """Write text to Windows clipboard as Unicode.

    Lock hierarchy is strictly: _session_lock -> OpenClipboard(None).
    If expected_gen is provided, verifies that generation still matches and active session
    depth is 0 (no new session started).
    If expected_seq is provided, verifies that sequence number inside OpenClipboard matches expected_seq.
    The entire validation, OpenClipboard, allocation, mutation, and bookkeeping happen within _session_lock.
    Returns (success, new_sequence_number).
    """
    raw_bytes = text.encode("utf-16le") + b"\x00\x00"
    with _session_lock:
        if expected_gen is not None:
            if _active_session_depth > 0 or _session_generation != expected_gen:
                return False, None

        for _ in range(retries):
            if user32.OpenClipboard(None):
                h_mem = None
                try:
                    if expected_gen is not None:
                        if _active_session_depth > 0 or _session_generation != expected_gen:
                            return False, None
                    if expected_seq is not None:
                        current_seq = user32.GetClipboardSequenceNumber()
                        if current_seq != expected_seq:
                            return False, None
                    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw_bytes))
                    if not h_mem:
                        return False, None
                    ptr = kernel32.GlobalLock(h_mem)
                    if not ptr:
                        return False, None
                    try:
                        ctypes.memmove(ptr, raw_bytes, len(raw_bytes))
                    finally:
                        kernel32.GlobalUnlock(h_mem)
                    if not user32.EmptyClipboard():
                        return False, None
                    res = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                    if res:
                        h_mem = None  # Ownership transferred to Windows.
                        new_seq = user32.GetClipboardSequenceNumber()
                        if not is_restore:
                            record_stepwise_clipboard_write(new_seq)
                        return True, new_seq
                    return False, None
                finally:
                    if h_mem:
                        kernel32.GlobalFree(h_mem)
                    user32.CloseClipboard()
            time.sleep(retry_delay)
    return False, None


def set_clipboard_text(text: str, retries: int = 5, retry_delay: float = 0.03) -> bool:
    """Write text to Windows clipboard as Unicode."""
    ok, _ = write_clipboard_text(text, retries=retries, retry_delay=retry_delay)
    return ok


def restore_clipboard_if_sequence_matches(
    text: str,
    expected_seq: int,
    retries: int = 5,
    retry_delay: float = 0.03,
    expected_gen: int | None = None,
) -> bool:
    """Atomically restore clipboard text only if sequence number and generation match."""
    ok, _ = write_clipboard_text(
        text,
        retries=retries,
        retry_delay=retry_delay,
        expected_seq=expected_seq,
        expected_gen=expected_gen,
        is_restore=True,
    )
    return ok


def is_clipboard_session_active() -> bool:
    """Return True if a scoped_clipboard_session is currently managing clipboard lifecycle."""
    with _session_lock:
        return _active_session_depth > 0


@contextmanager
def scoped_clipboard_session() -> Generator[None, None, None]:
    """Capture clipboard text once at start of run and restore once at end of run.

    Only restores if:
    1. Stepwise actually wrote to the clipboard during this session.
    2. The original clipboard contained restorable Unicode text (not image/file).
    3. The clipboard sequence number at session end still matches Stepwise's last write
       (i.e. no user copy or external application updated the clipboard in the meantime).
    4. No newer session has started in the meantime (generation check).
    """
    global _active_session_depth, _session_generation, _session_original_clipboard, _session_last_stepwise_seq
    with _session_lock:
        if _active_session_depth == 0:
            _session_generation += 1
            _session_original_clipboard = snapshot_restorable_text()
            _session_last_stepwise_seq = None
        current_gen = _session_generation
        _active_session_depth += 1

    try:
        yield
    finally:
        orig_to_restore: str | None = None
        expected_seq: int | None = None
        with _session_lock:
            _active_session_depth -= 1
            if _active_session_depth == 0:
                orig = _session_original_clipboard
                last_seq = _session_last_stepwise_seq
                _session_original_clipboard = None
                _session_last_stepwise_seq = None
                if orig is not None and last_seq is not None:
                    orig_to_restore = orig
                    expected_seq = last_seq

        # Perform stabilization wait and atomic restore OUTSIDE the lock to prevent deadlock
        if orig_to_restore is not None and expected_seq is not None:
            time.sleep(0.05)
            if get_clipboard_sequence_number() == expected_seq:
                restore_clipboard_if_sequence_matches(
                    orig_to_restore,
                    expected_seq=expected_seq,
                    expected_gen=current_gen,
                )


@contextmanager
def temporary_clipboard_text(text: str, restore: bool = True) -> Generator[bool, None, None]:
    """Context manager that puts text on clipboard and optionally restores previous content.

    If a scoped_clipboard_session is active, per-action restore is skipped to avoid
    pasting race conditions in slow apps. Outside a session, restores previous content
    only if restorable text existed and clipboard wasn't overwritten by another app.
    """
    with _session_lock:
        session_active = _active_session_depth > 0
        current_gen = _session_generation
    should_restore = restore and not session_active
    original_text = snapshot_restorable_text() if should_restore else None
    write_seq: int | None = None
    try:
        ok, write_seq = write_clipboard_text(text)
        yield ok
    finally:
        if should_restore and original_text is not None and write_seq is not None:
            time.sleep(0.05)
            if get_clipboard_sequence_number() == write_seq:
                restore_clipboard_if_sequence_matches(
                    original_text,
                    expected_seq=write_seq,
                    expected_gen=current_gen,
                )
