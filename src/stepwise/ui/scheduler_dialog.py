"""Night-Shift Task Scheduler Dialog ("Armed Mode").

Allows users on Cloud PCs or workstations to:
1. Run Pre-Arm Diagnostics (Macro Preflight + Screen Buffer + Windows Idle/Update Policies).
2. Complete the mandatory 3-point Cloud PC Overnight Safety Checklist.
3. Arm a scheduled start time while holding `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)`
   to prevent display sleep.
4. Re-validate desktop/preflight readiness and automatically trigger execution when the wall-clock reaches the target time.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, time
from typing import Any

from PySide6.QtCore import QTime, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from stepwise.core.models import Macro
from stepwise.engine.timing import SpeedMode
from stepwise.services.jiggler import Jiggler, safe_jiggler_interval
from stepwise.services.power import set_awake_state
from stepwise.services.schedule_diag import (
    ScheduleDiagItem,
    compute_next_occurrence,
    format_countdown,
    run_schedule_pre_arm_diagnostics,
)
from stepwise.ui.strings import Strings
from stepwise.ui.theme import get_theme_tokens

# Maximum grace window (15 minutes) if system was suspended across the scheduled target time
MAX_OVERDUE_SECONDS = 900.0


class SchedulerDialog(QDialog):
    """Armed Night-Shift Task Scheduler dialog."""

    schedule_triggered = Signal(dict)

    def __init__(
        self,
        macro: Macro,
        rows_data: Sequence[dict[str, str]] | None = None,
        row_numbers: Sequence[int] | None = None,
        package_dir: str | None = None,
        data_file_path: str | None = None,
        results_dir: str = "results",
        jiggler_enabled: bool = False,
        jiggler_interval: float = 45.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(Strings.SCHEDULER_TITLE)
        self.resize(640, 620)

        self.macro = macro
        self.rows_data = rows_data
        self.row_numbers = row_numbers or []
        self.package_dir = package_dir
        self.data_file_path = data_file_path
        self.results_dir = results_dir
        self._jiggler_interval = safe_jiggler_interval(jiggler_interval, default=45.0, min_val=5.0)

        self._is_armed = False
        self._jiggler: Jiggler | None = None
        self._target_dt: datetime | None = None
        self.confirmed_opts: dict[str, Any] = {}

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._on_armed_tick)

        t = get_theme_tokens()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        lbl_sub = QLabel(Strings.SCHEDULER_SUBTITLE)
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"color: {t['text_secondary']}; font-size: 12px;")
        layout.addWidget(lbl_sub)

        # 1. Schedule Configuration
        self.cfg_box = QGroupBox(Strings.SCHEDULER_TITLE)
        cfg_form = QFormLayout(self.cfg_box)

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm:ss")
        # Default to 02:00:00 AM for overnight runs
        self.time_edit.setTime(QTime(2, 0, 0))
        cfg_form.addRow(Strings.SCHEDULER_TARGET_TIME, self.time_edit)

        total_rows = len(rows_data) if rows_data else 1
        self.spin_start_row = QSpinBox()
        self.spin_start_row.setRange(1, max(1, total_rows))
        self.spin_start_row.setValue(1)
        cfg_form.addRow(Strings.SCHEDULER_START_ROW, self.spin_start_row)

        self.cmb_speed = QComboBox()
        self.cmb_speed.addItem(Strings.SCHEDULER_SPEED_NORMAL, SpeedMode.NORMAL)
        self.cmb_speed.addItem(Strings.SCHEDULER_SPEED_SLOW, SpeedMode.SLOW)
        self.cmb_speed.addItem(Strings.SCHEDULER_SPEED_VERY_SLOW, SpeedMode.VERY_SLOW)
        cfg_form.addRow(Strings.SCHEDULER_SPEED_PROFILE, self.cmb_speed)

        self.cmb_on_fail = QComboBox()
        self.cmb_on_fail.addItem(Strings.SCHEDULER_STOP_QUEUE, "stop")
        self.cmb_on_fail.setEnabled(False)
        cfg_form.addRow(Strings.SCHEDULER_ON_FAIL, self.cmb_on_fail)

        self.chk_lock_after = QCheckBox(Strings.SCHEDULER_LOCK_AFTER)
        self.chk_lock_after.setChecked(False)
        cfg_form.addRow("", self.chk_lock_after)

        self.chk_anti_lock = QCheckBox(Strings.SCHEDULER_ANTI_LOCK_JIGGLER)
        self.chk_anti_lock.setChecked(bool(jiggler_enabled))
        tip_text = Strings.SCHEDULER_ANTI_LOCK_JIGGLER_TIP.format(seconds=int(self._jiggler_interval))
        self.chk_anti_lock.setToolTip(tip_text)
        cfg_form.addRow("", self.chk_anti_lock)

        layout.addWidget(self.cfg_box)

        # 2. Pre-Arm Diagnostics
        diag_box = QGroupBox(Strings.SCHEDULER_PRE_ARM_TITLE)
        diag_layout = QVBoxLayout(diag_box)
        self.list_diag = QListWidget()
        diag_layout.addWidget(self.list_diag)
        layout.addWidget(diag_box)

        self.diagnostics: list[ScheduleDiagItem] = run_schedule_pre_arm_diagnostics(
            macro=macro,
            rows_data=rows_data,
            row_numbers=row_numbers,
            package_dir=package_dir,
            data_file_path=data_file_path,
            results_dir=results_dir,
        )
        self._populate_diagnostics()

        # 3. Mandatory Overnight Cloud PC Safety Checklist
        self.chk_box = QGroupBox(Strings.SCHEDULER_CHECKLIST_TITLE)
        chk_layout = QVBoxLayout(self.chk_box)
        self.chk_dont_close = QCheckBox(Strings.SCHEDULER_CHK_DONT_CLOSE)
        self.chk_power = QCheckBox(Strings.SCHEDULER_CHK_POWER)
        self.chk_erp_ready = QCheckBox(Strings.SCHEDULER_CHK_ERP_READY)

        for chk in (self.chk_dont_close, self.chk_power, self.chk_erp_ready):
            chk.toggled.connect(self._update_arm_button_state)
            chk_layout.addWidget(chk)

        layout.addWidget(self.chk_box)

        # 4. Armed Status Banner
        self.lbl_banner = QLabel("")
        self.lbl_banner.setWordWrap(True)
        self.lbl_banner.setStyleSheet(
            f"color: {t['accent_primary']}; font-weight: bold; font-size: 13px; padding: 4px;"
        )
        layout.addWidget(self.lbl_banner)

        # 5. Buttons
        btn_layout = QHBoxLayout()
        self.btn_run_now = QPushButton(Strings.SCHEDULER_BTN_RUN_NOW)
        self.btn_run_now.clicked.connect(lambda: self._trigger_now(is_scheduled=False))
        btn_layout.addWidget(self.btn_run_now)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton(Strings.SCHEDULER_BTN_DISARM)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_arm = QPushButton(Strings.SCHEDULER_BTN_ARM)
        self.btn_arm.setObjectName("btn_run")
        self.btn_arm.clicked.connect(self._on_arm_clicked)
        btn_layout.addWidget(self.btn_arm)

        layout.addLayout(btn_layout)

        self._update_arm_button_state()

    @property
    def is_armed(self) -> bool:
        return self._is_armed

    @property
    def target_datetime(self) -> datetime | None:
        return self._target_dt

    def _populate_diagnostics(self) -> None:
        t = get_theme_tokens()
        self.list_diag.clear()
        for item in self.diagnostics:
            if item.level == "error":
                prefix = Strings.SCHEDULER_TAG_BLOCKING
                color = QColor(t["status_fail"])
            elif item.level == "warn":
                prefix = Strings.SCHEDULER_TAG_WARN
                color = QColor(t["status_warn"])
            else:
                prefix = Strings.SCHEDULER_TAG_READY
                color = QColor(t["status_ok"])

            text = f"{prefix}{item.title}"
            if item.detail:
                text += f"\n   ↳ {item.detail}"
            lw_item = QListWidgetItem(text)
            lw_item.setForeground(color)
            self.list_diag.addItem(lw_item)

    def has_blocking_errors(self) -> bool:
        return any(d.is_blocking for d in self.diagnostics)

    def all_checklist_checked(self) -> bool:
        return (
            self.chk_dont_close.isChecked()
            and self.chk_power.isChecked()
            and self.chk_erp_ready.isChecked()
        )

    def _update_arm_button_state(self) -> None:
        t = get_theme_tokens()
        if self._is_armed:
            self.btn_arm.setEnabled(False)
            self.btn_run_now.setEnabled(False)
            return

        if self.has_blocking_errors():
            self.btn_arm.setEnabled(False)
            self.btn_run_now.setEnabled(False)
            self.lbl_banner.setText(Strings.SCHEDULER_BANNER_BLOCKING)
            self.lbl_banner.setStyleSheet(f"color: {t['status_fail']}; font-weight: bold;")
            return

        self.btn_run_now.setEnabled(True)
        can_arm = self.all_checklist_checked()
        self.btn_arm.setEnabled(can_arm)
        if can_arm:
            self.lbl_banner.setText(Strings.SCHEDULER_BANNER_READY)
            self.lbl_banner.setStyleSheet(f"color: {t['status_ok']}; font-weight: bold;")
        else:
            self.lbl_banner.setText(Strings.SCHEDULER_BANNER_CHECKLIST)
            self.lbl_banner.setStyleSheet(f"color: {t['text_secondary']};")

    def arm_schedule(self, now: datetime | None = None) -> datetime:
        """Enter Armed Mode, compute target datetime, and hold system awake state."""
        qt_time = self.time_edit.time()
        target_t = time(qt_time.hour(), qt_time.minute(), qt_time.second())
        self._target_dt = compute_next_occurrence(target_t, now=now)
        self._is_armed = True

        self.cfg_box.setEnabled(False)
        self.chk_box.setEnabled(False)
        self._update_arm_button_state()

        set_awake_state(True)
        if self.chk_anti_lock.isChecked():
            if self._jiggler is None:
                self._jiggler = Jiggler(interval_seconds=self._jiggler_interval)
            self._jiggler.start()
        self._update_armed_banner(now=now)
        self._tick_timer.start(1000)
        return self._target_dt

    def disarm_schedule(self) -> None:
        """Cancel Armed Mode and release awake state."""
        self._tick_timer.stop()
        if self._jiggler:
            self._jiggler.stop()
            self._jiggler = None
        if self._is_armed:
            set_awake_state(False)
        self._is_armed = False
        self._target_dt = None
        self.cfg_box.setEnabled(True)
        self.chk_box.setEnabled(True)
        self._update_arm_button_state()

    def _on_arm_clicked(self) -> None:
        if self.has_blocking_errors() or not self.all_checklist_checked():
            return
        self.arm_schedule()

    def _on_cancel_clicked(self) -> None:
        if self._is_armed:
            self.disarm_schedule()
        else:
            self.reject()

    def _update_armed_banner(self, now: datetime | None = None) -> float:
        if not self._target_dt:
            return 0.0
        ref = now or datetime.now()
        remaining_sec = (self._target_dt - ref).total_seconds()
        time_str = self._target_dt.strftime("%Y-%m-%d %H:%M:%S")
        rem_str = format_countdown(remaining_sec)
        self.lbl_banner.setText(
            Strings.SCHEDULER_ARMED_BANNER.format(time=time_str, remaining=rem_str)
        )
        return remaining_sec

    def _on_armed_tick(self, now: datetime | None = None) -> None:
        if not self._is_armed or not self._target_dt:
            return
        remaining = self._update_armed_banner(now=now)
        if remaining <= 0:
            # Guard against stale wake-ups (>15 min overdue)
            if remaining < -MAX_OVERDUE_SECONDS:
                t = get_theme_tokens()
                self.disarm_schedule()
                self.lbl_banner.setText(f"⚠ {Strings.SCHEDULER_STALE_ABORT}")
                self.lbl_banner.setStyleSheet(f"color: {t['status_fail']}; font-weight: bold;")
                return

            # Re-verify pre-arm diagnostics right before unattended launch
            try:
                self.diagnostics = run_schedule_pre_arm_diagnostics(
                    macro=self.macro,
                    rows_data=self.rows_data,
                    row_numbers=self.row_numbers,
                    package_dir=self.package_dir,
                    data_file_path=self.data_file_path,
                    results_dir=self.results_dir,
                )
            except Exception as exc:
                self.diagnostics = [
                    ScheduleDiagItem(level="error", title="Pre-run diagnostic error", detail=str(exc))
                ]
            self._populate_diagnostics()
            if self.has_blocking_errors():
                self.disarm_schedule()
                return

            self._trigger_now(is_scheduled=True)

    def _trigger_now(self, is_scheduled: bool = False) -> None:
        self._tick_timer.stop()
        if self._jiggler:
            self._jiggler.stop()
            self._jiggler = None
        if self._is_armed:
            set_awake_state(False)
            self._is_armed = False

        speed = self.cmb_speed.currentData() or SpeedMode.NORMAL
        opts = {
            "start_row": self.spin_start_row.value(),
            "speed": speed,
            "skip_setup": False,
            "skip_cleanup": False,
            "step_by_step": False,
            "run_1_row": False,
            "scheduled": is_scheduled,
            "on_fail": str(self.cmb_on_fail.currentData() or "stop"),
            "lock_after": bool(is_scheduled and self.chk_lock_after.isChecked()),
            "anti_lock_jiggler": self.chk_anti_lock.isChecked(),
            "jiggler_interval_seconds": self._jiggler_interval,
        }
        self.confirmed_opts = opts
        self.schedule_triggered.emit(opts)
        self.accept()

    def reject(self) -> None:
        """Ensure Esc key or Cancel button cleanly disarms timers and awake state."""
        self.disarm_schedule()
        super().reject()

    def done(self, result: int) -> None:
        """Ensure any dialog dismissal path releases timers and awake state."""
        self._tick_timer.stop()
        if self._jiggler:
            self._jiggler.stop()
            self._jiggler = None
        if self._is_armed:
            set_awake_state(False)
            self._is_armed = False
        super().done(result)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._is_armed:
            ans = QMessageBox.question(
                self,
                Strings.SCHEDULER_TITLE,
                f"{Strings.SCHEDULER_BTN_DISARM}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.disarm_schedule()
        super().closeEvent(event)
