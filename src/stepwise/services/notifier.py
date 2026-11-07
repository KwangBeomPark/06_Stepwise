"""Webhook notification service for unattended runs (Slack / Teams / Generic Webhook).

Security & Privacy Guarantee:
- Sends text summary metrics ONLY (Macro name, status, duration, counts, failed row numbers).
- Never transmits screenshots or sensitive spreadsheet cell contents.
- Executes asynchronously on a background daemon thread to never block UI or execution.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


def build_webhook_payload(
    macro_name: str,
    status: str,
    duration_sec: float,
    total_rows: int,
    done_rows: int,
    failed_rows: list[int] | None = None,
    error_details: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Build a unified JSON payload compatible with Slack Incoming Webhooks and Microsoft Teams."""
    fails = failed_rows or []
    fail_count = len(fails)
    status_emoji = "✅" if status == "Done" else ("⚠️" if status == "Interrupted" else "❌")
    theme_color = "137333" if status == "Done" else ("EA8600" if status == "Interrupted" else "C5221F")

    # Safe summary lines (No sensitive cell data, only metrics and row numbers)
    lines = [
        f"[{status_emoji} Stepwise] 매크로 실행 {status}: *{macro_name}*",
        f"• 상태: {status}",
        f"• 소요 시간: {duration_sec:.1f}초",
        f"• 실행 결과: 총 {total_rows}행 중 완료 {done_rows}건, 실패 {fail_count}건",
    ]

    if fails:
        fail_summary = ", ".join(f"행 {r}" for r in fails[:10])
        if len(fails) > 10:
            fail_summary += f" 외 {len(fails) - 10}건"
        lines.append(f"• 실패 행 목록: {fail_summary}")

        if error_details:
            # Include at most 3 top error samples
            sample_errors = []
            for r in fails[:3]:
                if r in error_details and error_details[r]:
                    sample_errors.append(f"  - 행 {r}: {error_details[r]}")
            if sample_errors:
                lines.append("• 주요 오류 내용:\n" + "\n".join(sample_errors))

    text_body = "\n".join(lines)

    # Multi-platform hybrid structure:
    # - Slack reads 'text' and 'attachments'
    # - Teams / Power Automate reads '@type', 'themeColor', 'title', 'text'
    # - Generic webhooks read top-level fields
    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": theme_color,
        "title": f"{status_emoji} Stepwise 실행 {status}: {macro_name}",
        "text": text_body,
        "attachments": [
            {
                "color": f"#{theme_color}",
                "fields": [
                    {"title": "매크로", "value": macro_name, "short": True},
                    {"title": "상태", "value": status, "short": True},
                    {"title": "소요 시간", "value": f"{duration_sec:.1f}초", "short": True},
                    {
                        "title": "처리 요약",
                        "value": f"총 {total_rows}행 (완료: {done_rows}, 실패: {fail_count})",
                        "short": True,
                    },
                ],
            }
        ],
        "stepwise_metadata": {
            "macro_name": macro_name,
            "status": status,
            "duration_sec": round(duration_sec, 2),
            "total_rows": total_rows,
            "done_rows": done_rows,
            "failed_row_numbers": fails,
        },
    }


def send_webhook(webhook_url: str, payload: dict[str, Any], timeout: float = 10.0) -> tuple[bool, str]:
    """Send JSON payload to webhook URL using urllib.request. Returns (success, message)."""
    clean_url = (webhook_url or "").strip()
    if not clean_url:
        return False, "Webhook URL is empty."
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        return False, "Invalid Webhook URL scheme (must start with http:// or https://)."

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            clean_url,
            data=data,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "Stepwise-Notifier/0.5.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            if 200 <= status_code < 300:
                return True, f"HTTP {status_code}: OK"
            return False, f"HTTP {status_code}: Unexpected response status"
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        return False, f"HTTP {e.code} Error: {e.reason} ({err_body})"
    except urllib.error.URLError as e:
        return False, f"Connection Error: {e.reason}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def send_run_summary_webhook(
    webhook_url: str,
    condition: str,
    macro_name: str,
    status: str,
    duration_sec: float,
    total_rows: int,
    done_rows: int,
    failed_rows: list[int] | None = None,
    error_details: dict[int, str] | None = None,
    timeout: float = 10.0,
) -> tuple[bool, str]:
    """Check notification condition ('always' vs 'failure_only') and send summary webhook."""
    norm_status = status.capitalize()
    # If condition is failure_only and run completed successfully without errors
    if condition == "failure_only":
        has_failure = norm_status in ("Failed", "Interrupted") or bool(failed_rows)
        if not has_failure:
            return True, "Skipped: Run completed without failures."

    payload = build_webhook_payload(
        macro_name=macro_name,
        status=norm_status,
        duration_sec=duration_sec,
        total_rows=total_rows,
        done_rows=done_rows,
        failed_rows=failed_rows,
        error_details=error_details,
    )
    return send_webhook(webhook_url, payload, timeout=timeout)


def send_run_summary_webhook_async(
    webhook_url: str,
    condition: str,
    macro_name: str,
    status: str,
    duration_sec: float,
    total_rows: int,
    done_rows: int,
    failed_rows: list[int] | None = None,
    error_details: dict[int, str] | None = None,
) -> threading.Thread:
    """Send webhook on an isolated background daemon thread to guarantee zero UI lag."""

    def _worker() -> None:
        try:
            ok, msg = send_run_summary_webhook(
                webhook_url=webhook_url,
                condition=condition,
                macro_name=macro_name,
                status=status,
                duration_sec=duration_sec,
                total_rows=total_rows,
                done_rows=done_rows,
                failed_rows=failed_rows,
                error_details=error_details,
            )
            if not ok:
                logger.warning("Stepwise Webhook notification failed: %s", msg)
            else:
                logger.info("Stepwise Webhook notification sent: %s", msg)
        except Exception as e:
            logger.error("Stepwise Webhook notification thread exception: %s", e)

    t = threading.Thread(target=_worker, name="StepwiseWebhookNotifier", daemon=True)
    t.start()
    return t


def send_test_webhook(webhook_url: str) -> tuple[bool, str]:
    """Send a test notification card to verify the webhook URL."""
    payload = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": "137333",
        "title": "🔔 Stepwise 웹훅 연동 테스트 성공",
        "text": (
            "[🔔 Stepwise] 웹훅 알림이 정상적으로 연동되었습니다.\n"
            "• 시스템: Stepwise RPA Automation Engine\n"
            "• 상태: 준비 완료 (Ready)\n"
            "• 안내: 향후 매크로 실행 완료 시 이 채널로 결과 요약이 자동 전송됩니다."
        ),
    }
    return send_webhook(webhook_url, payload, timeout=10.0)
