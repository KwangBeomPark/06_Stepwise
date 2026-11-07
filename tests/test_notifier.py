"""Unit tests for Webhook Notification service (Slack / Teams / Generic)."""

from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from stepwise.services.notifier import (
    build_webhook_payload,
    send_run_summary_webhook,
    send_run_summary_webhook_async,
    send_test_webhook,
    send_webhook,
)
from stepwise.ui.settings_dialog import SettingsDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_build_webhook_payload_success():
    payload = build_webhook_payload(
        macro_name="ERP Invoice Registration",
        status="Done",
        duration_sec=45.67,
        total_rows=10,
        done_rows=10,
        failed_rows=[],
    )

    assert "ERP Invoice Registration" in payload["text"]
    assert "Done" in payload["text"]
    assert "45.7초" in payload["text"]
    assert "완료 10건, 실패 0건" in payload["text"]
    assert payload["themeColor"] == "137333"
    assert "screenshot" not in str(payload).lower()


def test_build_webhook_payload_failure():
    payload = build_webhook_payload(
        macro_name="Tax Filing Batch",
        status="Failed",
        duration_sec=12.34,
        total_rows=5,
        done_rows=3,
        failed_rows=[4, 5],
        error_details={4: "Target button not found", 5: "Invalid account number"},
    )

    assert "Tax Filing Batch" in payload["text"]
    assert "Failed" in payload["text"]
    assert "행 4, 행 5" in payload["text"]
    assert "Target button not found" in payload["text"]
    assert payload["themeColor"] == "C5221F"


def test_send_webhook_validation():
    # Empty url
    ok, msg = send_webhook("", {"text": "hello"})
    assert ok is False
    assert "empty" in msg.lower()

    # Invalid scheme
    ok, msg = send_webhook("ftp://invalid.url", {"text": "hello"})
    assert ok is False
    assert "scheme" in msg.lower()


def test_send_webhook_http_mock():
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        ok, msg = send_webhook("https://hooks.slack.com/services/test", {"text": "test"})
        assert ok is True
        assert "200" in msg

    # HTTP 500 error mock
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError(
            url="https://hooks.slack.com",
            code=500,
            msg="Internal Error",
            hdrs={},
            fp=None,
        ),
    ):
        ok, msg = send_webhook("https://hooks.slack.com/services/test", {"text": "test"})
        assert ok is False
        assert "500" in msg


def test_send_run_summary_condition():
    # When condition is failure_only and status is Done -> skipped without network call
    with patch("stepwise.services.notifier.send_webhook") as mock_send:
        ok, msg = send_run_summary_webhook(
            webhook_url="https://example.com/webhook",
            condition="failure_only",
            macro_name="TestMacro",
            status="Done",
            duration_sec=10.0,
            total_rows=5,
            done_rows=5,
            failed_rows=[],
        )
        assert ok is True
        assert "Skipped" in msg
        mock_send.assert_not_called()

    # When condition is failure_only and status is Failed -> calls webhook
    with patch("stepwise.services.notifier.send_webhook", return_value=(True, "OK")) as mock_send:
        ok, msg = send_run_summary_webhook(
            webhook_url="https://example.com/webhook",
            condition="failure_only",
            macro_name="TestMacro",
            status="Failed",
            duration_sec=10.0,
            total_rows=5,
            done_rows=3,
            failed_rows=[4, 5],
        )
        assert ok is True
        mock_send.assert_called_once()


def test_send_run_summary_async():
    with patch("stepwise.services.notifier.send_run_summary_webhook", return_value=(True, "OK")) as mock_send:
        thread = send_run_summary_webhook_async(
            webhook_url="https://example.com/webhook",
            condition="always",
            macro_name="TestMacro",
            status="Done",
            duration_sec=5.0,
            total_rows=2,
            done_rows=2,
        )
        assert thread.daemon is True
        thread.join(timeout=3.0)
        assert not thread.is_alive()
        mock_send.assert_called_once()


def test_send_test_webhook():
    with patch("stepwise.services.notifier.send_webhook", return_value=(True, "HTTP 200: OK")) as mock_send:
        ok, msg = send_test_webhook("https://example.com/test")
        assert ok is True
        mock_send.assert_called_once()


def test_settings_dialog_notifications_tab(qapp):
    initial_settings = {
        "webhook_enabled": True,
        "webhook_url": "https://hooks.slack.com/services/sample",
        "webhook_condition": "failure_only",
    }
    dlg = SettingsDialog(initial_settings)
    assert dlg.chk_webhook_enable.isChecked() is True
    assert dlg.txt_webhook_url.text() == "https://hooks.slack.com/services/sample"
    assert dlg.cmb_webhook_condition.currentData() == "failure_only"
    assert hasattr(dlg, "btn_test_webhook")
    dlg.close()


def test_main_window_dispatch_run_webhook_integration(qapp):
    from stepwise.engine.runner import RunSummary
    from stepwise.ui.main_window import MainWindow

    win = MainWindow()

    # Mock user settings
    with (
        patch("stepwise.ui.main_window.load_user_settings") as mock_settings,
        patch("stepwise.services.notifier.send_run_summary_webhook_async") as mock_async,
    ):
        mock_settings.return_value = {
            "webhook_enabled": True,
            "webhook_url": "https://example.com/webhook",
            "webhook_condition": "always",
        }

        # Real RunSummary object with duration_sec, done_count
        summary = RunSummary(
            run_id="run-123",
            macro_name="Test Macro",
            started_at="2026-11-07 10:00:00",
            finished_at="2026-11-07 10:00:15",
            duration_sec=15.2,
            total_rows=10,
            done_count=9,
            failed_count=1,
            interrupted_count=0,
            skipped_count=0,
            failed_row_numbers=[3],
        )

        win.data_panel.record_row_detail(3, reason="Test error message")
        win._dispatch_run_webhook(summary)

        mock_async.assert_called_once()
        kwargs = mock_async.call_args[1]
        assert kwargs["duration_sec"] == 15.2
        assert kwargs["total_rows"] == 10
        assert kwargs["done_rows"] == 9
        assert kwargs["status"] == "Failed"
        assert kwargs["failed_rows"] == [3]
        assert kwargs["error_details"].get(3) == "Test error message"


def test_main_window_close_joins_webhook_thread(qapp):
    from unittest.mock import MagicMock

    from stepwise.ui.main_window import MainWindow

    win = MainWindow()
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = True
    win._webhook_thread = mock_thread

    # When close requested while finishing worker
    win._close_requested = True
    win._finish_worker("fake_token")  # token mismatch, returns early

    # Directly verify join call on closeEvent or worker finish
    mock_summary = MagicMock()
    mock_summary.persistence_errors = []
    win._pending_summary = mock_summary
    win._run_token = "valid_token"

    with patch.object(win, "_dispatch_run_webhook", return_value=mock_thread):
        with patch.object(win, "close"):
            win._finish_worker("valid_token")
            mock_thread.join.assert_called_with(timeout=3.0)
