"""Pre-flight validation checks before macro execution (Section 11.2).

Returns structured list of blocking errors (🔴) and informational warnings (🟡).
Pure engine service independent of Qt UI widgets.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from stepwise.core.models import ActionItem, Macro
from stepwise.core.schema import validate_macro_dict
from stepwise.core.variables import extract_variable_names
from stepwise.engine.results import ResultsManager
from stepwise.services.screen import get_screen_info


@dataclass
class PreflightIssue:
    level: str  # "ERROR" or "WARNING"
    message: str
    details: str = ""

    @property
    def is_error(self) -> bool:
        return self.level == "ERROR"

    @property
    def is_warning(self) -> bool:
        return self.level == "WARNING"


def collect_referenced_variables(macro: Macro) -> list[str]:
    """Collect all unique {variable} names across all TypeText actions."""
    var_names: list[str] = []

    def _scan(items: list[ActionItem]) -> None:
        for it in items:
            if it.type == "type_text" and it.text:
                for v in extract_variable_names(it.text):
                    if v not in var_names:
                        var_names.append(v)
            elif it.type == "window_set_bounds" and it.window_title:
                for v in extract_variable_names(it.window_title):
                    if v not in var_names:
                        var_names.append(v)
            elif it.type == "group" and it.items:
                _scan(it.items)

    _scan(macro.setup)
    _scan(macro.per_row)
    _scan(macro.cleanup)
    return var_names


def run_preflight_checks(
    macro: Macro,
    rows_data: Sequence[Mapping[str, Any]] | None = None,
    row_numbers: Sequence[int] | None = None,
    package_dir: str | None = None,
    data_file_path: str | None = None,
    results_dir: str = "results",
) -> list[PreflightIssue]:
    """Perform pre-flight checks and return list of errors and warnings."""
    issues: list[PreflightIssue] = []

    # 1. Macro Schema Validity (🔴 ERROR)
    try:
        validate_macro_dict(macro.to_dict())
    except Exception as e:
        issues.append(
            PreflightIssue(level="ERROR", message="Macro structure is invalid.", details=str(e))
        )

    # 2. Check Image Files Existence (🔴 ERROR)
    def _check_image(path: str | None, ctx: str) -> None:
        if not path:
            return
        resolved = (
            os.path.normpath(os.path.join(package_dir or "", path))
            if not os.path.isabs(path)
            else path
        )
        if not os.path.exists(resolved):
            issues.append(
                PreflightIssue(
                    level="ERROR",
                    message=f'Referenced image not found: "{os.path.basename(path)}"',
                    details=f"Context: {ctx} (searched: {resolved})",
                )
            )

    def _scan_images(items: list[ActionItem], sec_name: str) -> None:
        for it in items:
            if it.guard and it.guard.image:
                _check_image(it.guard.image, f"{sec_name} step {it.id} Guard")
            if it.verify and it.verify.image:
                _check_image(it.verify.image, f"{sec_name} step {it.id} Verify")
            if it.image:
                _check_image(it.image, f"{sec_name} step {it.id} {it.type}")
            if it.type == "group":
                _scan_images(it.items, f"{sec_name} Group '{it.name}'")

    _scan_images(macro.setup, "Setup")
    _scan_images(macro.per_row, "Per Row")
    _scan_images(macro.cleanup, "Cleanup")

    # 3. Data Variables & Column Mapping (🔴 ERROR)
    ref_vars = collect_referenced_variables(macro)
    if ref_vars:
        if not rows_data:
            issues.append(
                PreflightIssue(
                    level="ERROR",
                    message="Macro requires a data file, but no data is loaded.",
                    details=f"Required columns: {', '.join(ref_vars)}",
                )
            )
        else:
            available_cols = set(rows_data[0].keys())
            missing_cols = [v for v in ref_vars if v not in available_cols]
            if missing_cols:
                issues.append(
                    PreflightIssue(
                        level="ERROR",
                        message=f"Missing required columns in data file: {', '.join(missing_cols)}",
                        details=f"Available columns: {', '.join(sorted(available_cols))}",
                    )
                )

            # 4. Check for Empty Values in Required Columns (🔴 ERROR)
            blank_rows_by_col: dict[str, list[int]] = {
                v: [] for v in ref_vars if v in available_cols
            }
            effective_row_nums = row_numbers or list(range(1, len(rows_data) + 1))

            for idx, r in enumerate(rows_data):
                r_num = effective_row_nums[idx] if idx < len(effective_row_nums) else idx + 1
                for v in blank_rows_by_col:
                    val = r.get(v)
                    if val is None or str(val).strip() == "":
                        blank_rows_by_col[v].append(r_num)

            for col_name, blank_rows in blank_rows_by_col.items():
                if blank_rows:
                    preview_rows = [str(x) for x in blank_rows[:10]]
                    suffix = f" ... and {len(blank_rows) - 10} more" if len(blank_rows) > 10 else ""
                    issues.append(
                        PreflightIssue(
                            level="ERROR",
                            message=f'Column "{col_name}" contains empty values on {len(blank_rows)} row(s).',
                            details=f"Rows: {', '.join(preview_rows)}{suffix}",
                        )
                    )

    # 5. Screen Resolution & DPI Check (🟡 WARNING)
    screen_info = get_screen_info()
    rec = macro.recorded_screen
    if rec:
        diff_res = (screen_info["width"] != rec.width) or (screen_info["height"] != rec.height)
        diff_scale = screen_info["scale_percent"] != rec.scale_percent
        if diff_res or diff_scale:
            issues.append(
                PreflightIssue(
                    level="WARNING",
                    message=(
                        f"Screen mismatch: Recorded at {rec.width}x{rec.height} @ {rec.scale_percent}%, "
                        f"current screen is {screen_info['width']}x{screen_info['height']} @ {screen_info['scale_percent']}%."
                    ),
                    details="Click coordinates or image matches may fail due to display differences.",
                )
            )

    # 6. Multi-monitor Check (🟡 WARNING)
    if screen_info["monitor_count"] > 1:
        issues.append(
            PreflightIssue(
                level="WARNING",
                message=f"Multiple monitors detected ({screen_info['monitor_count']}).",
                details="Stepwise operates on the primary display. Ensure the target app is on the primary monitor.",
            )
        )

    # 7. Verify Image Recommendation (🟡 WARNING)
    # Check if Per Row has at least one verify condition
    def _has_verify(items: list[ActionItem]) -> bool:
        for it in items:
            if it.verify:
                return True
            if it.type == "wait_image":
                return True
            if it.type == "group" and _has_verify(it.items):
                return True
        return False

    if macro.per_row and not _has_verify(macro.per_row):
        issues.append(
            PreflightIssue(
                level="WARNING",
                message="No Verify images found in the Per Row section.",
                details="We strongly recommend adding a Verify image to critical steps (e.g. Save button) to avoid silent failures.",
            )
        )

    # 8. Data Change and Previous Failures Check (🟡 WARNING)
    if data_file_path and os.path.exists(data_file_path) and rows_data:
        res_mgr = ResultsManager(macro.name, data_file_path, results_dir=results_dir)
        effective_row_nums = row_numbers or list(range(1, len(rows_data) + 1))
        _, data_warnings = res_mgr.get_resume_suggestion(effective_row_nums, rows_data)
        for w in data_warnings:
            issues.append(PreflightIssue(level="WARNING", message=w))

        # Check for previous failed/interrupted rows
        past_statuses = res_mgr.load_latest_row_statuses()
        unresolved = [
            r_num for r_num, rec in past_statuses.items() if rec.status in ("Failed", "Interrupted")
        ]
        if unresolved:
            issues.append(
                PreflightIssue(
                    level="WARNING",
                    message=f"Previous run has {len(unresolved)} unresolved Failed or Interrupted row(s).",
                    details=f"Rows: {', '.join(str(x) for x in unresolved[:10])}",
                )
            )

    return issues
