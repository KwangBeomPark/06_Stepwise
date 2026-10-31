"""Pre-arm environment & policy diagnostics for Night-Shift Task Scheduler (Armed Mode).

Performs read-only, non-admin checks before arming an overnight schedule:
1. Macro preflight validation (missing variables, empty actions, invalid selectors).
2. Screen availability & resolution check (ensuring session is interactive and matches macro).
3. Windows Group Policy / Registry idle & reboot checks (read-only HKLM/HKCU inspection):
   - Remote Desktop Session Host MaxIdleTime / MaxDisconnectionTime
   - Local security policy InactivityTimeoutSecs
   - Pending Windows Update reboot flags
4. Disk space & results directory writeability.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows CI fallback
    winreg = None  # type: ignore[assignment]

from stepwise.core.models import Macro
from stepwise.engine.preflight import PreflightIssue, run_preflight_checks
from stepwise.services.screen import capture_screen, get_screen_info
from stepwise.ui.strings import get_current_language


@dataclass(frozen=True)
class ScheduleDiagItem:
    level: str  # "ok", "warn", "error"
    title: str
    detail: str = ""

    @property
    def is_blocking(self) -> bool:
        return self.level == "error"


def compute_next_occurrence(target_time: time, now: datetime | None = None) -> datetime:
    """Compute the next datetime occurrence for a given wall-clock time (today or tomorrow)."""
    ref = now or datetime.now()
    candidate = ref.replace(
        hour=target_time.hour,
        minute=target_time.minute,
        second=target_time.second,
        microsecond=0,
    )
    if candidate <= ref:
        candidate += timedelta(days=1)
    return candidate


def format_countdown(seconds_remaining: float) -> str:
    """Format remaining seconds as HH:MM:SS."""
    total = max(0, int(round(seconds_remaining)))
    hrs, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"


def _read_reg_dword(root: int, subkey: str, value_name: str) -> int | None:
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, value_name)
            if isinstance(val, int):
                return val
    except OSError:
        return None
    return None


def _reg_key_exists(root: int, subkey: str) -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ):
            return True
    except OSError:
        return False


def inspect_windows_overnight_policies() -> list[ScheduleDiagItem]:
    """Read-only inspection of Windows Registry keys that affect overnight Cloud PC runs."""
    items: list[ScheduleDiagItem] = []
    is_ko = get_current_language() == "ko"
    if winreg is None:
        return items

    # 1. Check RDS / Terminal Services Idle Timeout Policy (ms)
    ts_policy_keys = [
        r"SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services",
        r"SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp",
    ]
    max_idle_ms: int | None = None
    for subkey in ts_policy_keys:
        val = _read_reg_dword(winreg.HKEY_LOCAL_MACHINE, subkey, "MaxIdleTime")
        if val and val > 0:
            max_idle_ms = val if max_idle_ms is None else min(max_idle_ms, val)

    if max_idle_ms is not None and max_idle_ms > 0:
        idle_min = max(1, max_idle_ms // 60000)
        items.append(
            ScheduleDiagItem(
                level="warn",
                title=(
                    f"RDP 세션 유휴 시간 제한 정책 감지됨 ({idle_min}분)"
                    if is_ko
                    else f"RDP Session Idle Policy detected ({idle_min} min)"
                ),
                detail=(
                    "사내 그룹 정책(MaxIdleTime)이 설정되어 있습니다. SetThreadExecutionState는 "
                    "디스플레이 절전은 방지하지만 서버 측 RDP 유휴 입력 제한까지 우회하지는 못하므로 "
                    "예약 대기 시간이 유휴 제한 시간 이내인지 확인하고 원격 데스크톱 창을 열어 두세요."
                    if is_ko
                    else (
                        "Group Policy sets MaxIdleTime on this machine. SetThreadExecutionState "
                        "prevents display sleep, but does not reset server-side RDP input idle "
                        "cutoffs. Keep the RDP client window open and schedule within the policy limit."
                    )
                ),
            )
        )
    else:
        items.append(
            ScheduleDiagItem(
                level="ok",
                title=(
                    "RDP 세션 유휴 정책: 강제 세션 종료 정책 없음"
                    if is_ko
                    else "RDP Session Idle Policy: No forced idle cutoff detected"
                ),
            )
        )

    # 2. Check Machine Inactivity Limit (InactivityTimeoutSecs)
    inactivity_secs = _read_reg_dword(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
        "InactivityTimeoutSecs",
    )
    if inactivity_secs is not None and inactivity_secs > 0:
        mins = max(1, inactivity_secs // 60)
        items.append(
            ScheduleDiagItem(
                level="warn",
                title=(
                    f"시스템 비활성 화면 잠금 정책 감지됨 ({mins}분)"
                    if is_ko
                    else f"System Inactivity Lock Policy detected ({mins} min)"
                ),
                detail=(
                    "시스템 보안 정책(InactivityTimeoutSecs)이 활성화되어 있습니다. "
                    "SetThreadExecutionState는 절전을 방지하지만 보안 잠금 정책은 작동할 수 있으니 주의하세요."
                    if is_ko
                    else (
                        "System security policy defines InactivityTimeoutSecs. Note that "
                        "SetThreadExecutionState prevents display sleep but cannot bypass "
                        "mandatory security lock policies."
                    )
                ),
            )
        )

    # 3. Check Pending Windows Update Reboot
    reboot_pending = _reg_key_exists(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
    ) or _reg_key_exists(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
    )
    if reboot_pending:
        items.append(
            ScheduleDiagItem(
                level="warn",
                title=(
                    "Windows 업데이트 재부팅 대기 상태 감지됨"
                    if is_ko
                    else "Windows Update Reboot Pending"
                ),
                detail=(
                    "대기 중인 Windows 업데이트 재부팅이 있습니다. 야간에 자동 재부팅되지 않도록 "
                    "지금 먼저 재부팅한 뒤 예약하는 것을 권장합니다."
                    if is_ko
                    else (
                        "Windows has a pending update reboot. Consider rebooting now before "
                        "leaving the Cloud PC overnight."
                    )
                ),
            )
        )
    else:
        items.append(
            ScheduleDiagItem(
                level="ok",
                title=(
                    "Windows 업데이트 상태: 예정된 강제 재부팅 없음"
                    if is_ko
                    else "Windows Update State: No pending forced reboot detected"
                ),
            )
        )

    return items


def run_schedule_pre_arm_diagnostics(
    macro: Macro,
    rows_data: Sequence[dict[str, str]] | None = None,
    row_numbers: Sequence[int] | None = None,
    package_dir: str | None = None,
    data_file_path: str | None = None,
    results_dir: str = "results",
) -> list[ScheduleDiagItem]:
    """Run full pre-arm diagnostics combining macro preflight, screen state, and OS policies."""
    diagnostics: list[ScheduleDiagItem] = []
    is_ko = get_current_language() == "ko"

    # 1. Standard macro preflight checks
    preflight_issues: list[PreflightIssue] = run_preflight_checks(
        macro=macro,
        rows_data=rows_data,
        row_numbers=row_numbers,
        package_dir=package_dir,
        data_file_path=data_file_path,
        results_dir=results_dir,
    )
    if not preflight_issues:
        total_rows = len(rows_data) if rows_data else 1
        diagnostics.append(
            ScheduleDiagItem(
                level="ok",
                title=(
                    f'매크로 "{macro.name}" 사전 검증 통과 ({total_rows}개 행 준비됨)'
                    if is_ko
                    else f'Macro "{macro.name}" preflight passed ({total_rows} rows ready)'
                ),
            )
        )
    else:
        for issue in preflight_issues:
            diagnostics.append(
                ScheduleDiagItem(
                    level="error" if issue.is_error else "warn",
                    title=issue.message,
                    detail=issue.details,
                )
            )

    # 2. Live full-screen capture & resolution verification
    try:
        screen = get_screen_info()
        capture_screen(region=None, check_black_screen=True)
        diagnostics.append(
            ScheduleDiagItem(
                level="ok",
                title=(
                    f"대화형 화면 캡처 버퍼 정상 "
                    f"({screen['width']}x{screen['height']} @{screen['scale_percent']}%)"
                    if is_ko
                    else (
                        f"Interactive Desktop Buffer Active "
                        f"({screen['width']}x{screen['height']} @{screen['scale_percent']}%)"
                    )
                ),
            )
        )
    except Exception as exc:
        diagnostics.append(
            ScheduleDiagItem(
                level="error",
                title=(
                    "대화형 화면 캡처 불가 (세션 잠금 또는 최소화 상태)"
                    if is_ko
                    else "Interactive screen capture unavailable"
                ),
                detail=str(exc),
            )
        )

    # 3. Windows overnight policy checks
    diagnostics.extend(inspect_windows_overnight_policies())

    return diagnostics
