"""Pre-flight validation checks before macro execution (Section 11.2).

Returns structured list of blocking errors (🔴) and informational warnings (🟡).
Pure engine service independent of Qt UI widgets.
"""

from __future__ import annotations

import difflib
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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
    # Optional stable id + format params so the UI can localize message/details.
    code: str = ""
    params: dict[str, Any] = field(default_factory=dict)

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
                for v in extract_variable_names(it.text, include_builtins=False):
                    if v not in var_names:
                        var_names.append(v)
            elif it.type == "window_set_bounds" and it.window_title:
                for v in extract_variable_names(it.window_title, include_builtins=False):
                    if v not in var_names:
                        var_names.append(v)
            elif (
                it.type == "click"
                and it.enabled
                and it.target_mode == "selector"
                and it.selector
                and isinstance(it.selector, Mapping)
            ):
                for key in ("window_title", "name"):
                    raw_val = str(it.selector.get(key) or "")
                    for v in extract_variable_names(raw_val, include_builtins=False):
                        if v not in var_names:
                            var_names.append(v)
            elif it.type == "group" and it.items:
                _scan(it.items)

    _scan(macro.setup)
    _scan(macro.per_row)
    _scan(macro.cleanup)
    return var_names


def find_unknown_text_variables(macro: Macro, columns: Sequence[str]) -> list[PreflightIssue]:
    """Warn per enabled Type Text step about {Variable}s missing from the data columns."""
    available = [str(c) for c in columns]
    issues: list[PreflightIssue] = []
    step_no = 0

    def _scan(items: list[ActionItem], sec_name: str, enabled: bool) -> None:
        nonlocal step_no
        for it in items:
            if it.type == "group":
                _scan(it.items, sec_name, enabled and it.enabled)
                continue
            step_no += 1
            if it.type != "type_text" or not (enabled and it.enabled) or not it.text:
                continue
            for var in extract_variable_names(it.text, include_builtins=False):
                if var in available:
                    continue
                close = difflib.get_close_matches(var, available, n=1, cutoff=0.6)
                folded = [c for c in available if c.strip().casefold() == var.strip().casefold()]
                hint = folded or close
                details = (
                    f'Did you mean "{{{hint[0]}}}"?'
                    if hint
                    else f"Available columns: {', '.join(available)}"
                )
                issues.append(
                    PreflightIssue(
                        level="WARNING",
                        message=(
                            f'Step #{step_no} ({sec_name}) types "{{{var}}}", '
                            f'but the connected data has no column "{var}".'
                        ),
                        details=details,
                        code="UNKNOWN_VARIABLE" if hint else "UNKNOWN_VARIABLE_NO_MATCH",
                        params={
                            "step": step_no,
                            "section": sec_name,
                            "var": var,
                            "hint": hint[0] if hint else "",
                            "available": ", ".join(available),
                        },
                    )
                )

    _scan(macro.setup, "Setup", True)
    _scan(macro.per_row, "Per Row", True)
    _scan(macro.cleanup, "Cleanup", True)
    return issues


def run_preflight_checks(
    macro: Macro,
    rows_data: Sequence[Mapping[str, Any]] | None = None,
    row_numbers: Sequence[int] | None = None,
    package_dir: str | None = None,
    data_file_path: str | None = None,
    results_dir: str = "results",
    headers: Sequence[str] | None = None,
) -> list[PreflightIssue]:
    """Perform pre-flight checks and return list of errors and warnings.

    ``headers`` are the connected data's column names; when omitted they are
    taken from the first data row.
    """
    issues: list[PreflightIssue] = []

    # 1. Macro Schema Validity (🔴 ERROR)
    try:
        validate_macro_dict(macro.to_dict())
    except Exception as e:
        issues.append(
            PreflightIssue(
                level="ERROR",
                message="Macro structure is invalid.",
                details=str(e),
                code="INVALID_MACRO",
            )
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
                    code="IMAGE_MISSING",
                    params={"name": os.path.basename(path), "context": ctx, "path": resolved},
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
            if it.type == "click" and it.enabled and it.target_mode == "selector":
                if not it.selector or not any(
                    str(it.selector.get(k) or "").strip()
                    for k in ("window_title", "name", "automation_id", "class_name")
                ):
                    issues.append(
                        PreflightIssue(
                            level="ERROR",
                            message=f'Step "{it.note or it.id}" uses UI Selector mode, but no target element is configured.',
                            details=f"Section: {sec_name}",
                            code="SELECTOR_MISSING",
                            params={"step": it.note or it.id, "section": sec_name},
                        )
                    )
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
                    code="NO_DATA",
                    params={"columns": ", ".join(ref_vars)},
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
                        code="MISSING_COLUMNS",
                        params={
                            "columns": ", ".join(missing_cols),
                            "available": ", ".join(sorted(available_cols)),
                        },
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
                            code="BLANK_CELLS",
                            params={
                                "column": col_name,
                                "count": len(blank_rows),
                                "rows": ", ".join(preview_rows) + ("…" if suffix else ""),
                            },
                        )
                    )

    # 4b. Pinpoint enabled Type Text steps whose {Variable} is not a data column (🟡 WARNING)
    columns = list(headers) if headers else (list(rows_data[0].keys()) if rows_data else [])
    if columns:
        issues.extend(find_unknown_text_variables(macro, columns))

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
                    code="SCREEN_MISMATCH",
                    params={
                        "recorded": f"{rec.width}x{rec.height} @ {rec.scale_percent}%",
                        "current": (
                            f"{screen_info['width']}x{screen_info['height']} "
                            f"@ {screen_info['scale_percent']}%"
                        ),
                    },
                )
            )

    # 6. Multi-monitor Check (🟡 WARNING)
    if screen_info["monitor_count"] > 1:
        issues.append(
            PreflightIssue(
                level="WARNING",
                message=f"Multiple monitors detected ({screen_info['monitor_count']}).",
                details="Stepwise operates on the primary display. Ensure the target app is on the primary monitor.",
                code="MULTI_MONITOR",
                params={"count": screen_info["monitor_count"]},
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
                code="NO_VERIFY",
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
                    code="PREVIOUS_FAILURES",
                    params={
                        "count": len(unresolved),
                        "rows": ", ".join(str(x) for x in unresolved[:10]),
                    },
                )
            )

    return issues


@dataclass(frozen=True)
class RowRangePreview:
    first_row_number: int
    last_row_number: int
    count: int
    sample: str


def preview_row_range(
    rows_data: Sequence[Mapping[str, Any]] | None,
    row_numbers: Sequence[int] | None,
    start: int,
    end: int,
) -> RowRangePreview | None:
    """Describe a 1-based inclusive data range in source-file row numbers.

    ``start``/``end`` are the same 1-based ordinals passed to ``run_macro`` as
    ``start_row_index + 1`` and ``end_row_index``. Returns None without data.
    """
    if not rows_data:
        return None
    total = len(rows_data)
    start = max(1, min(start, total))
    end = max(start, min(end, total))
    nums = list(row_numbers) if row_numbers and len(row_numbers) == total else None
    first_row = rows_data[start - 1]
    sample = str(next(iter(first_row.values()), "") or "")
    return RowRangePreview(
        first_row_number=nums[start - 1] if nums else start,
        last_row_number=nums[end - 1] if nums else end,
        count=end - start + 1,
        sample=sample,
    )
