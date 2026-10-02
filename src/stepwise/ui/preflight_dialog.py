"""Pre-flight check and run confirmation dialog (Section 11.2).

Displays:
- Diagnostics summary (blocking errors 🔴 and warnings 🟡)
- Speed selection (Normal / Slow +0.5s / Very slow +1s)
- Resume / Start from row selector
- Skip Setup, Skip Cleanup, Step-by-step checkboxes
- [Run 1 row], [Start], [Cancel]
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from stepwise.core.models import Macro
from stepwise.engine.preflight import run_preflight_checks
from stepwise.engine.timing import SpeedMode


class PreflightDialog(QDialog):
    run_confirmed = Signal(dict)

    def __init__(
        self,
        macro: Macro,
        rows_data: Sequence[dict[str, str]] | None = None,
        row_numbers: Sequence[int] | None = None,
        package_dir: str | None = None,
        data_file_path: str | None = None,
        initial_speed: SpeedMode = SpeedMode.NORMAL,
        suggested_start_row: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f'Ready to run "{macro.name}"')
        self.resize(620, 560)

        self.macro = macro
        self.rows_data = rows_data
        self.row_numbers = row_numbers or []
        self._countdown_remaining = 5
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Title & Meta
        total_rows = len(rows_data) if rows_data else 1
        data_name = f'"{macro.data_source.file_hint}"' if macro.data_source and macro.data_source.file_hint else "No Data"
        info_lbl = QLabel(f"<b>Macro:</b> {macro.name} &nbsp;|&nbsp; <b>Data:</b> {data_name} ({total_rows} rows)")
        main_layout.addWidget(info_lbl)

        # 2. Preflight Checks List
        issues_box = QGroupBox("Pre-flight Diagnostics")
        issues_layout = QVBoxLayout(issues_box)
        self.list_issues = QListWidget()
        issues_layout.addWidget(self.list_issues)
        main_layout.addWidget(issues_box)

        # Run diagnostics
        self.issues = run_preflight_checks(
            macro=macro,
            rows_data=rows_data,
            row_numbers=row_numbers,
            package_dir=package_dir,
            data_file_path=data_file_path,
        )
        self._populate_issues()

        # 3. Execution Options
        opts_box = QGroupBox("Execution Options")
        opts_layout = QFormLayout(opts_box)

        # Start from row
        self.spin_start_row = QSpinBox()
        self.spin_start_row.setRange(1, max(1, total_rows))
        if suggested_start_row:
            self.spin_start_row.setValue(suggested_start_row)
        opts_layout.addRow("Start from row:", self.spin_start_row)

        # Speed Mode
        h_speed = QHBoxLayout()
        self.btn_grp_speed = QButtonGroup(self)
        self.rad_normal = QRadioButton("Normal")
        self.rad_slow = QRadioButton("Slow (+0.5s)")
        self.rad_veryslow = QRadioButton("Very slow (+1s)")
        self.btn_grp_speed.addButton(self.rad_normal)
        self.btn_grp_speed.addButton(self.rad_slow)
        self.btn_grp_speed.addButton(self.rad_veryslow)

        if initial_speed == SpeedMode.SLOW:
            self.rad_slow.setChecked(True)
        elif initial_speed == SpeedMode.VERY_SLOW:
            self.rad_veryslow.setChecked(True)
        else:
            self.rad_normal.setChecked(True)

        h_speed.addWidget(self.rad_normal)
        h_speed.addWidget(self.rad_slow)
        h_speed.addWidget(self.rad_veryslow)
        h_speed.addStretch()
        opts_layout.addRow("Speed Delay:", h_speed)

        # Section skips & Step-by-step
        h_flags = QHBoxLayout()
        self.chk_skip_setup = QCheckBox("Skip Setup")
        self.chk_skip_cleanup = QCheckBox("Skip Cleanup")
        self.chk_step_by_step = QCheckBox("Step-by-step")
        h_flags.addWidget(self.chk_skip_setup)
        h_flags.addWidget(self.chk_skip_cleanup)
        h_flags.addWidget(self.chk_step_by_step)
        h_flags.addStretch()
        opts_layout.addRow("Workflow:", h_flags)

        main_layout.addWidget(opts_box)

        # 4. Countdown Banner
        self.lbl_countdown = QLabel("Click [Start] to begin execution.")
        self.lbl_countdown.setStyleSheet("color: #2563eb; font-weight: bold; font-size: 13px;")
        main_layout.addWidget(self.lbl_countdown)

        # 5. Buttons
        btn_layout = QHBoxLayout()
        self.btn_run_1_row = QPushButton("Run 1 Row (Test)")
        self.btn_run_1_row.clicked.connect(lambda: self._confirm(run_1_row=True))

        self.btn_start = QPushButton("Start Run")
        self.btn_start.setStyleSheet("background-color: #16a34a; color: white; font-weight: bold; padding: 8px 20px;")
        self.btn_start.clicked.connect(self._start_countdown)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        # Block start if there are errors
        has_errors = any(i.is_error for i in self.issues)
        if has_errors:
            self.btn_start.setEnabled(False)
            self.btn_run_1_row.setEnabled(False)
            self.lbl_countdown.setText("⚠ Please resolve blocking errors above before running.")
            self.lbl_countdown.setStyleSheet("color: #dc2626; font-weight: bold;")

        btn_layout.addWidget(self.btn_run_1_row)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_start)
        main_layout.addLayout(btn_layout)

    def _populate_issues(self) -> None:
        if not self.issues:
            it = QListWidgetItem("✅ All pre-flight checks passed.")
            it.setForeground(Qt.darkGreen)
            self.list_issues.addItem(it)
            return

        for issue in self.issues:
            prefix = "🔴 Error: " if issue.is_error else "🟡 Warning: "
            text = f"{prefix}{issue.message}"
            if issue.details:
                text += f"\n   ↳ {issue.details}"
            item = QListWidgetItem(text)
            if issue.is_error:
                item.setForeground(Qt.red)
            else:
                item.setForeground(Qt.darkYellow)
            self.list_issues.addItem(item)

    def _start_countdown(self) -> None:
        self.btn_start.setEnabled(False)
        self.btn_run_1_row.setEnabled(False)
        self._countdown_remaining = 3
        self._countdown_tick()
        self._countdown_timer.start(1000)

    def _countdown_tick(self) -> None:
        if self._countdown_remaining > 0:
            self.lbl_countdown.setText(
                f"Starting in {self._countdown_remaining}... (switch to your target window now)"
            )
            self._countdown_remaining -= 1
        else:
            self._countdown_timer.stop()
            self._confirm(run_1_row=False)

    def _on_countdown_tick(self) -> None:
        self._countdown_tick()

    def _confirm(self, run_1_row: bool) -> None:
        self._countdown_timer.stop()
        if self.rad_slow.isChecked():
            selected_speed = SpeedMode.SLOW
        elif self.rad_veryslow.isChecked():
            selected_speed = SpeedMode.VERY_SLOW
        else:
            selected_speed = SpeedMode.NORMAL

        opts = {
            "start_row": self.spin_start_row.value(),
            "speed": selected_speed,
            "skip_setup": self.chk_skip_setup.isChecked(),
            "skip_cleanup": self.chk_cleanup_checked(),
            "step_by_step": self.chk_step_by_step.isChecked(),
            "run_1_row": run_1_row,
        }
        self.run_confirmed.emit(opts)
        self.accept()

    def chk_cleanup_checked(self) -> bool:
        return self.chk_skip_cleanup.isChecked()
