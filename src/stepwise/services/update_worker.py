"""Background download and verification worker for Stepwise auto-update."""

from __future__ import annotations

import logging
import time
import urllib.request
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Signal

from stepwise.core.app_paths import updates_directory
from stepwise.services.updater import (
    ReleaseInfo,
    verify_authenticode_signature,
    verify_file_sha256,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class UpdateWorker(QThread):
    """Background worker that streams installer download, computes SHA256, and verifies Authenticode."""

    progress = Signal(int, str, int, int)  # percent, speed_str, downloaded_bytes, total_bytes
    status = Signal(str)  # human-readable status message key
    finished = Signal(str)  # verified installer local path
    failed = Signal(str)  # error description

    def __init__(self, release_info: ReleaseInfo, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.release_info = release_info
        self._cancelled = False

    def cancel(self) -> None:
        """Cooperatively request download cancellation."""
        self._cancelled = True

    def run(self) -> None:
        """Download installer and verify cryptographic integrity."""
        dest_dir = updates_directory() / self.release_info.version
        dest_dir.mkdir(parents=True, exist_ok=True)

        final_path = dest_dir / self.release_info.installer_name
        part_path = dest_dir / f"{self.release_info.installer_name}.part"

        # If already downloaded and fully verified, skip download
        if final_path.is_file() and self.release_info.expected_sha256:
            if verify_file_sha256(final_path, self.release_info.expected_sha256):
                valid, _ = verify_authenticode_signature(final_path)
                if valid:
                    self.finished.emit(str(final_path))
                    return

        # Start streaming download
        self.status.emit("UPDATE_DOWNLOADING")
        req = urllib.request.Request(
            self.release_info.installer_url,
            headers={"User-Agent": "Stepwise-Updater"},
        )

        total_size = self.release_info.installer_size
        downloaded = 0
        start_time = time.time()
        last_update_time = start_time

        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp, open(part_path, "wb") as out:
                if total_size <= 0:
                    cl = resp.headers.get("Content-Length")
                    if cl and cl.isdigit():
                        total_size = int(cl)

                chunk_size = 65536
                while True:
                    if self._cancelled:
                        out.close()
                        if part_path.is_file():
                            try:
                                part_path.unlink()
                            except OSError:
                                pass
                        self.failed.emit("Download cancelled by user")
                        return

                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break

                    out.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_update_time >= 0.2 or downloaded == total_size:
                        elapsed = max(now - start_time, 0.001)
                        speed_bps = downloaded / elapsed
                        if speed_bps >= 1048576:
                            speed_str = f"{speed_bps / 1048576:.1f} MB/s"
                        else:
                            speed_str = f"{speed_bps / 1024:.0f} KB/s"

                        percent = int(downloaded / total_size * 100) if total_size > 0 else 0
                        self.progress.emit(percent, speed_str, downloaded, total_size)
                        last_update_time = now

            # Rename .part to final installer name
            if part_path.is_file():
                if final_path.is_file():
                    try:
                        final_path.unlink()
                    except OSError:
                        pass
                part_path.rename(final_path)

            # Verification Phase
            self.status.emit("UPDATE_VERIFYING")

            # 1. SHA-256 Checksum verification
            if self.release_info.expected_sha256:
                if not verify_file_sha256(final_path, self.release_info.expected_sha256):
                    try:
                        final_path.unlink()
                    except OSError:
                        pass
                    self.failed.emit("SHA-256 checksum mismatch (file may be corrupted)")
                    return

            # 2. Windows Authenticode Signature verification
            valid_sig, sig_reason = verify_authenticode_signature(final_path)
            if not valid_sig:
                try:
                    final_path.unlink()
                except OSError:
                    pass
                self.failed.emit(f"Authenticode signature invalid: {sig_reason}")
                return

            self.finished.emit(str(final_path))

        except Exception as exc:
            if part_path.is_file():
                try:
                    part_path.unlink()
                except OSError:
                    pass
            self.failed.emit(str(exc))
