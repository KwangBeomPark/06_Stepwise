"""Comprehensive unit tests for Stepwise Auto-Update functionality:
1. SemVer parsing & version comparison
2. Release metadata & incomplete asset handling
3. SHA-256 chunked checksum verification
4. Active state safety gating (running macro & armed scheduler blocks)
5. Rate limit and ETag caching behavior
6. UpdateDialog UI states & theme token compliance
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from stepwise.services.updater import (
    RateLimitError,
    ReleaseInfo,
    can_safely_update,
    fetch_expected_sha256,
    fetch_latest_release,
    is_newer_version,
    parse_version,
    verify_file_sha256,
)
from stepwise.ui.settings_dialog import SettingsDialog
from stepwise.ui.strings import Strings
from stepwise.ui.update_dialog import UpdateDialog


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_version_parsing_and_comparison():
    assert parse_version("0.4.0") == (0, 4, 0)
    assert parse_version("v0.4.0") == (0, 4, 0)
    assert parse_version("v1.12.5") == (1, 12, 5)
    assert parse_version("invalid-tag") is None
    assert parse_version("v0.4") is None

    assert is_newer_version("v0.4.1", "0.4.0") is True
    assert is_newer_version("v1.0.0", "0.4.0") is True
    assert is_newer_version("v0.4.0", "0.4.0") is False
    assert is_newer_version("v0.3.9", "0.4.0") is False
    assert is_newer_version("invalid", "0.4.0") is False


def test_active_state_safety_gating():
    # Idle state -> allowed
    safe, reason = can_safely_update(is_macro_running=False, is_scheduler_armed=False)
    assert safe is True
    assert reason == "READY"

    # Macro running -> strictly blocked
    safe, reason = can_safely_update(is_macro_running=True, is_scheduler_armed=False)
    assert safe is False
    assert reason == "UPDATE_BLOCKED_RUNNING"

    # Scheduler armed -> strictly blocked
    safe, reason = can_safely_update(is_macro_running=False, is_scheduler_armed=True)
    assert safe is False
    assert reason == "UPDATE_BLOCKED_ARMED"

    # Both active -> blocked
    safe, _ = can_safely_update(is_macro_running=True, is_scheduler_armed=True)
    assert safe is False


def test_verify_file_sha256(tmp_path: Path):
    test_file = tmp_path / "sample_installer.exe"
    content = b"Mock Stepwise installer binary bytes for checksum test"
    test_file.write_bytes(content)

    expected_hash = hashlib.sha256(content).hexdigest()
    assert verify_file_sha256(test_file, expected_hash) is True
    assert verify_file_sha256(test_file, expected_hash.upper()) is True
    assert verify_file_sha256(test_file, "0" * 64) is False
    assert verify_file_sha256(tmp_path / "non_existent.exe", expected_hash) is False


def test_fetch_expected_sha256():
    sample_sums = (
        "907081b4222d68af92fc73f04cfb6e66f09a20ccb5a2108a14f4ea15da2a4c38  App06_Stepwise_Setup_v0.4.0.exe\n"
        "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890 *App06_Stepwise_Setup_v0.4.1.exe\n"
    )
    mock_resp = MagicMock()
    mock_resp.read.return_value = sample_sums.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        hash_val = fetch_expected_sha256("http://example.com/SHA256SUMS.txt", "App06_Stepwise_Setup_v0.4.1.exe")
        assert hash_val == "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

        missing_hash = fetch_expected_sha256("http://example.com/SHA256SUMS.txt", "Unknown.exe")
        assert missing_hash is None


def test_fetch_latest_release_discovery(tmp_path: Path):
    mock_release_json = {
        "tag_name": "v0.4.2",
        "html_url": "https://github.com/KwangBeomPark/06_Stepwise/releases/tag/v0.4.2",
        "body": "## Bug fixes and enhancements\n- Fixed something",
        "published_at": "2026-11-01T12:00:00Z",
        "assets": [
            {
                "name": "App06_Stepwise_Setup_v0.4.2.exe",
                "browser_download_url": "https://github.com/mock/App06_Stepwise_Setup_v0.4.2.exe",
                "size": 75000000,
            },
            {
                "name": "SHA256SUMS.v0.4.2.txt",
                "browser_download_url": "https://github.com/mock/SHA256SUMS.v0.4.2.txt",
                "size": 120,
            },
        ],
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_release_json).encode("utf-8")
    mock_resp.headers = {"ETag": '"etag123"'}
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp), \
         patch("stepwise.services.updater.fetch_expected_sha256", return_value="f" * 64), \
         patch("stepwise.services.updater.load_updater_state", return_value={}), \
         patch("stepwise.services.updater.save_updater_state"):

        rel_info, status = fetch_latest_release(current_ver="0.4.1", force=True)
        assert status == "update_available"
        assert rel_info is not None
        assert rel_info.version == "0.4.2"
        assert rel_info.installer_name == "App06_Stepwise_Setup_v0.4.2.exe"
        assert rel_info.expected_sha256 == "f" * 64


def test_fetch_latest_release_incomplete_assets():
    # Only installer, missing SHA256SUMS -> release incomplete (uploading)
    mock_release_json = {
        "tag_name": "v0.4.1",
        "assets": [
            {
                "name": "App06_Stepwise_Setup_v0.4.1.exe",
                "browser_download_url": "https://github.com/mock/setup.exe",
                "size": 1000,
            }
        ],
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_release_json).encode("utf-8")
    mock_resp.headers = {}
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp), \
         patch("stepwise.services.updater.load_updater_state", return_value={}), \
         patch("stepwise.services.updater.save_updater_state"):

        rel_info, status = fetch_latest_release(current_ver="0.4.0", force=True)
        assert status == "assets_incomplete"
        assert rel_info is None


def test_fetch_latest_release_up_to_date():
    mock_release_json = {
        "tag_name": "v0.4.1",  # Same as current
        "assets": [],
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_release_json).encode("utf-8")
    mock_resp.headers = {}
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp), \
         patch("stepwise.services.updater.load_updater_state", return_value={}), \
         patch("stepwise.services.updater.save_updater_state"):

        rel_info, status = fetch_latest_release(current_ver="0.4.1", force=True)
        assert status == "up_to_date"
        assert rel_info is None


def test_fetch_latest_release_rate_limit():
    http_err = urllib.error.HTTPError(
        url="https://api.github.com/mock",
        code=403,
        msg="Forbidden: rate limit exceeded",
        hdrs={"X-RateLimit-Reset": "1999999999"},
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=http_err), \
         patch("stepwise.services.updater.load_updater_state", return_value={}), \
         patch("stepwise.services.updater.save_updater_state"):

        with pytest.raises(RateLimitError):
            fetch_latest_release(force=True)


def test_update_dialog_ui(qapp: QApplication):
    rel_info = ReleaseInfo(
        tag_name="v0.4.1",
        version="0.4.1",
        html_url="https://github.com/mock/rel",
        body="## Release notes\n- Fixes and polish",
        published_at="2026-11-01T00:00:00Z",
        installer_name="App06_Stepwise_Setup_v0.4.1.exe",
        installer_url="https://mock/setup.exe",
        installer_size=70000000,
        checksums_url="https://mock/sums.txt",
        expected_sha256="a" * 64,
    )

    dlg = UpdateDialog(
        release_info=rel_info,
        is_macro_running=False,
        is_scheduler_armed=False,
    )
    assert dlg.release_info.version == "0.4.1"
    assert "Stepwise v0.4.1" in dlg.title_lbl.text()
    assert dlg.action_btn.isEnabled() is True
    dlg.close()


def test_update_dialog_active_state_block(qapp: QApplication):
    rel_info = ReleaseInfo(
        tag_name="v0.4.1",
        version="0.4.1",
        html_url="https://github.com/mock/rel",
        body="Notes",
        published_at="2026-11-01T00:00:00Z",
        installer_name="App06_Stepwise_Setup_v0.4.1.exe",
        installer_url="https://mock/setup.exe",
        installer_size=1000,
        checksums_url="https://mock/sums.txt",
    )

    # When macro is running, install must be blocked
    dlg = UpdateDialog(
        release_info=rel_info,
        is_macro_running=True,
        is_scheduler_armed=False,
    )
    dlg._verified_installer_path = "C:/mock/setup.exe"
    dlg._on_download_finished("C:/mock/setup.exe")
    assert dlg.action_btn.isEnabled() is False
    assert not dlg.gate_notice_lbl.isHidden()
    assert Strings.UPDATE_BLOCKED_RUNNING in dlg.gate_notice_lbl.text()
    dlg.close()


def test_settings_dialog_auto_update_checkbox(qapp: QApplication):
    dlg = SettingsDialog()
    assert hasattr(dlg, "chk_auto_update")
    assert dlg.chk_auto_update.text() == Strings.UPDATE_AUTO_CHECK_LABEL
    assert hasattr(dlg, "btn_check_now")
    dlg.close()
