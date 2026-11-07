"""GitHub Releases Auto-Update Service for Stepwise.

Follows PL Suite Master Standard v2.0:
- Checks https://api.github.com/repos/KwangBeomPark/06_Stepwise/releases/latest
- Rate-limit aware (ETag, If-None-Match, 304 Not Modified, X-RateLimit-Reset)
- Cryptographic verification: SHA256 checksum + Authenticode Digital Signature
  (Certum Code Signing, Thumbprint: E9C72CF5090840A1805296525D56BE680622A7FD)
- Active-state safety gate: Blocks installation if macro is running or scheduler is armed
- Clean non-elevated Inno Setup handoff with UserSetting preservation
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import logging
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from stepwise import __version__
from stepwise.core.app_paths import (
    load_updater_state,
    save_updater_state,
)

logger = logging.getLogger(__name__)


def _get_powershell_executable() -> str:
    """Return the absolute path to system PowerShell executable, falling back to powershell.exe."""
    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    system32_ps = os.path.join(sys_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    if os.path.isfile(system32_ps):
        return system32_ps
    return "powershell.exe"

# Security & Authenticode Policy
EXPECTED_SIGNER_THUMBPRINT = "E9C72CF5090840A1805296525D56BE680622A7FD"
EXPECTED_SIGNER_SUBJECT = "CN=Open Source Developer KWANG BEOM PARK"
GITHUB_REPO = "KwangBeomPark/06_Stepwise"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

_SEMVER_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class UpdateError(Exception):
    """Base exception for auto-update operations."""


class RateLimitError(UpdateError):
    """GitHub API rate limit exceeded."""


class ActiveStateBlockedError(UpdateError):
    """Update install blocked because macro or scheduler is active."""


class VerificationError(UpdateError):
    """Checksum or digital signature verification failed."""


@dataclass(frozen=True)
class ReleaseInfo:
    """Parsed metadata for a GitHub release."""

    tag_name: str
    version: str
    html_url: str
    body: str
    published_at: str
    installer_name: str
    installer_url: str
    installer_size: int
    checksums_url: str
    expected_sha256: str | None = None


def parse_version(tag: str) -> tuple[int, int, int] | None:
    """Parse strict 'vX.Y.Z' or 'X.Y.Z' into a 3-tuple of ints."""
    m = _SEMVER_PATTERN.match(str(tag).strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def is_newer_version(remote_tag: str, current_ver: str = __version__) -> bool:
    """Return True if remote_tag is strictly newer than current_ver."""
    remote = parse_version(remote_tag)
    current = parse_version(current_ver)
    if not remote or not current:
        return False
    return remote > current


def fetch_latest_release(
    current_ver: str = __version__,
    timeout: float = 10.0,
    force: bool = False,
) -> tuple[ReleaseInfo | None, str]:
    """Query GitHub API for latest release with ETag caching and rate limit handling.

    Returns:
        tuple[ReleaseInfo | None, status_message]
        - If newer release found: (ReleaseInfo, "update_available")
        - If current or 304: (None, "up_to_date")
        - If rate limited: raises RateLimitError
    """
    state = load_updater_state()

    # Check cooldown if rate limited previously
    not_before = state.get("not_before_utc", 0)
    import time

    now_epoch = int(time.time())
    if not force and now_epoch < not_before:
        raise RateLimitError(f"Rate limited until epoch {not_before}")

    req = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "User-Agent": f"Stepwise/{current_ver} (+https://github.com/{GITHUB_REPO})",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    etag = state.get("etag")
    if etag and not force:
        req.add_header("If-None-Match", etag)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            new_etag = resp.headers.get("ETag")
            raw_data = resp.read()
            data = json.loads(raw_data.decode("utf-8"))

            if new_etag:
                state["etag"] = new_etag
                state["cached_release"] = data
            state["last_check_utc"] = now_epoch
            save_updater_state(state)

    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            # 304 Not Modified: use cached release if valid
            data = state.get("cached_release")
            state["last_check_utc"] = now_epoch
            save_updater_state(state)
            if not data:
                return None, "up_to_date"
        elif exc.code in (403, 429):
            reset_ts = exc.headers.get("X-RateLimit-Reset")
            if reset_ts and reset_ts.isdigit():
                state["not_before_utc"] = int(reset_ts)
            else:
                state["not_before_utc"] = now_epoch + 3600
            save_updater_state(state)
            raise RateLimitError("GitHub API rate limit exceeded") from exc
        else:
            raise UpdateError(f"HTTP error {exc.code}: {exc.reason}") from exc
    except Exception as exc:
        raise UpdateError(f"Failed to check updates: {exc}") from exc

    if not isinstance(data, dict):
        return None, "invalid_response"

    tag_name = data.get("tag_name", "")
    if not is_newer_version(tag_name, current_ver):
        return None, "up_to_date"

    clean_ver = tag_name.lstrip("v")
    expected_installer_name = f"App06_Stepwise_Setup_v{clean_ver}.exe"
    expected_checksums_name = f"SHA256SUMS.v{clean_ver}.txt"

    assets = data.get("assets", [])
    installer_url: str | None = None
    installer_size = 0
    checksums_url: str | None = None

    for asset in assets:
        name = asset.get("name", "")
        if name == expected_installer_name:
            installer_url = asset.get("browser_download_url")
            installer_size = int(asset.get("size", 0))
        elif name == expected_checksums_name:
            checksums_url = asset.get("browser_download_url")

    # If assets are still uploading on GitHub, release is not ready yet
    if not installer_url or not checksums_url:
        logger.info("Release %s found but required assets are incomplete.", tag_name)
        return None, "assets_incomplete"

    # Fetch SHA256SUMS to get expected hash for installer
    expected_sha256 = fetch_expected_sha256(checksums_url, expected_installer_name, timeout=timeout)

    release_info = ReleaseInfo(
        tag_name=tag_name,
        version=clean_ver,
        html_url=data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/tag/{tag_name}"),
        body=data.get("body", ""),
        published_at=data.get("published_at", ""),
        installer_name=expected_installer_name,
        installer_url=installer_url,
        installer_size=installer_size,
        checksums_url=checksums_url,
        expected_sha256=expected_sha256,
    )
    return release_info, "update_available"


def fetch_expected_sha256(
    checksums_url: str,
    installer_name: str,
    timeout: float = 10.0,
) -> str | None:
    """Download SHA256SUMS.vX.Y.Z.txt and extract target installer hash."""
    req = urllib.request.Request(
        checksums_url,
        headers={"User-Agent": f"Stepwise/{__version__}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            for line in content.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    h = parts[0].strip().lower()
                    fname = parts[1].lstrip("*").strip()
                    if fname == installer_name and len(h) == 64:
                        return h
    except Exception as exc:
        logger.warning("Failed to fetch or parse SHA256SUMS from %s: %s", checksums_url, exc)
    return None


def verify_file_sha256(file_path: Path | str, expected_hash: str) -> bool:
    """Compute SHA-256 of file in 64KB chunks and verify against expected_hash."""
    p = Path(file_path)
    if not p.is_file():
        return False
    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    actual = hasher.hexdigest().lower()
    return hmac.compare_digest(actual, expected_hash.strip().lower())


def verify_authenticode_signature(exe_path: Path | str) -> tuple[bool, str]:
    """Verify Windows Authenticode digital signature and thumbprint.

    Returns:
        tuple[bool, reason_or_subject]
    """
    p = Path(exe_path).resolve()
    if not p.is_file():
        return False, "File does not exist"

    # Primary verification via PowerShell Authenticode API using safe environment variable channel
    ps_script = (
        "$targetPath = $env:STEPWISE_VERIFY_PATH; "
        "if ([string]::IsNullOrWhiteSpace($targetPath) -or -not (Test-Path -LiteralPath $targetPath)) { "
        "  [PSCustomObject]@{Status='NotFound'; Thumbprint=''; Subject=''; HasTimestamp=$false} | ConvertTo-Json -Compress; exit 0 "
        "}; "
        "$sig = Get-AuthenticodeSignature -LiteralPath $targetPath; "
        "if ($null -eq $sig -or $null -eq $sig.SignerCertificate) { "
        "  [PSCustomObject]@{Status='NotSigned'; Thumbprint=''; Subject=''; HasTimestamp=$false} | ConvertTo-Json -Compress; exit 0 "
        "}; "
        "[PSCustomObject]@{"
        "Status=$sig.Status.ToString(); "
        "Thumbprint=$sig.SignerCertificate.Thumbprint; "
        "Subject=$sig.SignerCertificate.Subject; "
        "HasTimestamp=($null -ne $sig.TimeStamperCertificate)"
        "} | ConvertTo-Json -Compress"
    )

    env = dict(os.environ)
    env["STEPWISE_VERIFY_PATH"] = str(p)

    try:
        proc = subprocess.run(
            [
                _get_powershell_executable(),
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps_script,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout.strip())
            status = data.get("Status")
            thumbprint = str(data.get("Thumbprint", "")).strip().upper()
            has_timestamp = bool(data.get("HasTimestamp"))
            subject = str(data.get("Subject", ""))

            if status != "Valid":
                return False, f"Signature status is '{status}' (expected 'Valid')"

            if thumbprint != EXPECTED_SIGNER_THUMBPRINT:
                return False, f"Signer thumbprint mismatch: {thumbprint}"

            if not has_timestamp:
                return False, "Missing valid Authenticode timestamp responder"

            return True, subject

        stderr_msg = proc.stderr.strip() if proc.stderr else "Unknown PowerShell error"
        return False, f"PowerShell signature check returned exit code {proc.returncode}: {stderr_msg}"
    except Exception as exc:
        logger.error("PowerShell signature check failed: %s", exc)
        return False, f"Signature verification error: {exc}"


def acquire_exclusive_read_handle(file_path: Path | str) -> int:
    """Acquire a Win32 file handle denying write and delete (TOCTOU mitigation).

    FILE_SHARE_READ allows the Windows loader to read/execute while preventing
    any external process from rewriting, modifying, or replacing the binary.
    """
    if sys.platform != "win32":
        return 0

    generic_read = 0x80000000
    file_share_read = 0x00000001
    open_existing = 3
    file_attribute_normal = 0x00000080

    kernel32 = ctypes.windll.kernel32
    create_file_w = kernel32.CreateFileW
    create_file_w.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file_w.restype = wintypes.HANDLE

    handle = create_file_w(
        str(file_path),
        generic_read,
        file_share_read,
        None,
        open_existing,
        file_attribute_normal,
        None,
    )
    return handle if handle != -1 else 0


def close_win32_handle(handle: int) -> None:
    """Close Win32 file handle."""
    if sys.platform == "win32" and handle and handle != -1:
        ctypes.windll.kernel32.CloseHandle(handle)


def can_safely_update(is_macro_running: bool, is_scheduler_armed: bool) -> tuple[bool, str]:
    """Check if Stepwise is in a safe idle state to perform an update installation."""
    if is_macro_running:
        return False, "UPDATE_BLOCKED_RUNNING"
    if is_scheduler_armed:
        return False, "UPDATE_BLOCKED_ARMED"
    return True, "READY"


def execute_installer_handoff(
    installer_path: Path | str,
    language: str = "ko",
    is_macro_running: bool = False,
    is_scheduler_armed: bool = False,
) -> None:
    """Safely hand off execution to Inno Setup installer and terminate Stepwise.

    Inno Setup parameters:
    /SILENT /SP- /NORESTART /CLOSEAPPLICATIONS=no
    /LANG=korean or english
    """
    safe, reason = can_safely_update(is_macro_running, is_scheduler_armed)
    if not safe:
        raise ActiveStateBlockedError(f"Cannot update: {reason}")

    inst = Path(installer_path).resolve()
    if not inst.is_file():
        raise FileNotFoundError(f"Installer not found: {inst}")

    inno_lang = "korean" if language == "ko" else "english"

    # Build clean environment without PyInstaller internal hooks
    clean_env = dict(os.environ)
    for k in list(clean_env.keys()):
        if k.startswith("_PYI_") or k.startswith("_MEI"):
            clean_env.pop(k, None)

    # Spawn independent detached background launcher
    # The launcher waits 1.5 seconds for Stepwise.exe to close, executes the installer,
    # and then relaunches Stepwise.exe.
    current_exe = Path(sys.executable).resolve()
    relaunch_script = (
        f"Start-Sleep -Milliseconds 1500; "
        f"Start-Process -FilePath '{inst}' -ArgumentList '/SILENT /SP- /NORESTART /LANG={inno_lang}' -Wait; "
        f"if (Test-Path '{current_exe}') {{ Start-Process -FilePath '{current_exe}' }}"
    )

    cmd = [
        _get_powershell_executable(),
        "-NoProfile",
        "-NonInteractive",
        "-WindowStyle",
        "Hidden",
        "-Command",
        relaunch_script,
    ]

    subprocess.Popen(
        cmd,
        env=clean_env,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
