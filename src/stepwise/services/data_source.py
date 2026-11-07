"""Data file loader for Excel (.xlsx) and CSV files (Section 10.1).

Features:
- openpyxl with read_only=True and data_only=True
- Auto-detect CSV encoding (utf-8-sig, cp949, cp1250, etc.) via charset-normalizer
- Auto-detect CSV delimiter (comma, semicolon, tab)
- Strict value normalization (strip unnecessary '.0' on integers, ISO date format)
- Skips completely blank rows and returns original 1-indexed row numbers
"""

from __future__ import annotations

import csv
import datetime
import os
import re
from typing import Any

import charset_normalizer
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side


class DuplicateHeaderError(ValueError):
    """Raised when a data file contains duplicate column headers."""

    pass


def col_idx_to_letter(idx: int) -> str:
    """Convert 0-based column index to Excel column name (0 -> A, 25 -> Z, 26 -> AA)."""
    result = ""
    idx += 1
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def validate_and_build_headers(row_vals: list[str]) -> list[str]:
    """Build clean header names and reject files with duplicate column headers."""
    seen: dict[str, list[str]] = {}
    headers: list[str] = []

    for i, val in enumerate(row_vals):
        col_letter = col_idx_to_letter(i)
        stripped = (val or "").strip()
        name = stripped or f"Column_{i + 1}"
        headers.append(name)
        norm_key = name.lower()
        seen.setdefault(norm_key, []).append(f"'{name}' ({col_letter}열)")

    duplicates = [items for items in seen.values() if len(items) > 1]
    if duplicates:
        dup_details = "\n  • ".join(", ".join(items) for items in duplicates)
        raise DuplicateHeaderError(
            f"데이터 파일에 중복된 열 이름이 있습니다:\n  • {dup_details}\n\n"
            "열 이름이 중복되면 변수 매핑 시 데이터가 덮어씌워질 수 있습니다. "
            "엑셀 또는 CSV 파일에서 중복된 열 이름을 고유하게 변경한 후 다시 불러와 주세요."
        )

    return headers


def normalize_cell_value(val: Any) -> str:
    """Normalize cell values to clean strings following Section 10.1."""
    if val is None:
        return ""

    if isinstance(val, (datetime.date, datetime.datetime)):
        # Default date format YYYY-MM-DD
        return val.strftime("%Y-%m-%d")

    if isinstance(val, float):
        # Remove redundant '.0' for integer values
        if val.is_integer():
            return str(int(val))
        return str(val)

    if isinstance(val, int):
        return str(val)

    text = str(val).strip()
    # Check if text looks like "1200.0"
    if text.endswith(".0"):
        try:
            f = float(text)
            if f.is_integer():
                return str(int(f))
        except ValueError:
            pass

    return text


def detect_csv_encoding_and_delimiter(
    filepath: str,
    override_encoding: str | None = None,
    override_delimiter: str | None = None,
) -> tuple[str, str]:
    """Detect text encoding and delimiter for a CSV file."""
    encoding = override_encoding
    if not encoding:
        with open(filepath, "rb") as f:
            raw_sample = f.read(32768)
        # Check BOM first
        if raw_sample.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            matches = charset_normalizer.from_bytes(raw_sample)
            best = matches.best()
            encoding = best.encoding if best else "utf-8"

    # Detect delimiter
    delimiter = override_delimiter
    if not delimiter:
        try:
            with open(filepath, encoding=encoding, errors="replace") as f:
                sample_lines = [f.readline() for _ in range(5)]
            sample_text = "".join(sample_lines)

            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample_text, delimiters=";,\t|")
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ","

    return encoding, delimiter


def read_data_file(
    filepath: str,
    sheet: str | None = None,
    header_row: int = 1,
    encoding: str | None = None,
    delimiter: str | None = None,
) -> tuple[list[str], list[dict[str, str]], list[int]]:
    """Read .xlsx or .csv data file.

    Returns:
    - headers: list of column name strings
    - rows: list of row dicts {column_name: string_value}
    - row_numbers: list of 1-indexed source row numbers
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Data file not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".xlsx":
        return _read_xlsx(filepath, sheet=sheet, header_row=header_row)
    else:
        return _read_csv(
            filepath,
            header_row=header_row,
            override_encoding=encoding,
            override_delimiter=delimiter,
        )


def _read_xlsx(
    filepath: str,
    sheet: str | None,
    header_row: int,
) -> tuple[list[str], list[dict[str, str]], list[int]]:
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    try:
        ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb.active
        if ws is None:
            raise ValueError(f"No active sheet in workbook {filepath}")

        headers: list[str] = []
        rows: list[dict[str, str]] = []
        row_numbers: list[int] = []

        curr_row_idx = 0
        for raw_row in ws.iter_rows(values_only=True):
            curr_row_idx += 1
            if curr_row_idx < header_row:
                continue

            row_vals = [normalize_cell_value(cell) for cell in raw_row]

            if curr_row_idx == header_row:
                # Header row
                headers = validate_and_build_headers(row_vals)
                continue

            # Check if entire row is blank
            if not any(row_vals):
                continue

            row_dict: dict[str, str] = {}
            for col_idx, col_name in enumerate(headers):
                row_dict[col_name] = row_vals[col_idx] if col_idx < len(row_vals) else ""

            rows.append(row_dict)
            row_numbers.append(curr_row_idx)

        return headers, rows, row_numbers
    finally:
        wb.close()


def _read_csv(
    filepath: str,
    header_row: int,
    override_encoding: str | None,
    override_delimiter: str | None,
) -> tuple[list[str], list[dict[str, str]], list[int]]:
    enc, delim = detect_csv_encoding_and_delimiter(
        filepath, override_encoding=override_encoding, override_delimiter=override_delimiter
    )

    headers: list[str] = []
    rows: list[dict[str, str]] = []
    row_numbers: list[int] = []

    with open(filepath, encoding=enc, errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=delim)
        curr_row_idx = 0
        for raw_row in reader:
            curr_row_idx += 1
            if curr_row_idx < header_row:
                continue

            row_vals = [normalize_cell_value(cell) for cell in raw_row]

            if curr_row_idx == header_row:
                headers = validate_and_build_headers(row_vals)
                continue

            if not any(row_vals):
                continue

            row_dict: dict[str, str] = {}
            for col_idx, col_name in enumerate(headers):
                row_dict[col_name] = row_vals[col_idx] if col_idx < len(row_vals) else ""

            rows.append(row_dict)
            row_numbers.append(curr_row_idx)

    return headers, rows, row_numbers


def export_execution_results_xlsx(
    headers: list[str],
    rows: list[dict[str, str]],
    row_numbers: list[int],
    row_statuses: dict[int, str],
    source_filepath: str | None = None,
    output_filepath: str | None = None,
    row_details: dict[int, dict[str, str]] | None = None,
) -> str:
    """Export original data rows with appended execution result columns to a new .xlsx file.

    Columns appended:
    - Stepwise_상태 (Status: Done, Failed, Interrupted, Needs Verification, Skipped, Pending)
    - Stepwise_완료일시 (Completed At / Execution Time)
    - Stepwise_오류내용 (Error reason / failure detail if any)

    Returns the absolute path of the generated .xlsx file.
    Original source file is never modified.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    if ws is None:
        ws = wb.create_sheet(title="Stepwise Results")
    else:
        ws.title = "Stepwise Results"

    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    data_header_fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
    result_header_fill = PatternFill(start_color="0284C7", end_color="0284C7", fill_type="solid")

    status_styles = {
        "Done": {
            "fill": PatternFill(start_color="E6F4EA", end_color="E6F4EA", fill_type="solid"),
            "font": Font(name="Segoe UI", size=10, bold=True, color="137333"),
        },
        "Failed": {
            "fill": PatternFill(start_color="FCE8E6", end_color="FCE8E6", fill_type="solid"),
            "font": Font(name="Segoe UI", size=10, bold=True, color="C5221F"),
        },
        "Interrupted": {
            "fill": PatternFill(start_color="FEF7E0", end_color="FEF7E0", fill_type="solid"),
            "font": Font(name="Segoe UI", size=10, bold=True, color="B06000"),
        },
        "Needs Verification": {
            "fill": PatternFill(start_color="FEF7E0", end_color="FEF7E0", fill_type="solid"),
            "font": Font(name="Segoe UI", size=10, bold=True, color="B06000"),
        },
        "Skipped": {
            "fill": PatternFill(start_color="F1F3F4", end_color="F1F3F4", fill_type="solid"),
            "font": Font(name="Segoe UI", size=10, color="5F6368"),
        },
        "Pending": {
            "fill": PatternFill(fill_type=None),
            "font": Font(name="Segoe UI", size=10, color="64748B"),
        },
    }

    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    result_columns = ["Stepwise_상태", "Stepwise_완료일시", "Stepwise_오류내용"]
    all_headers = list(headers) + result_columns

    # 1. Header row
    ws.append(all_headers)
    for col_idx in range(1, len(all_headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        if col_idx <= len(headers):
            cell.fill = data_header_fill
        else:
            cell.fill = result_header_fill

    # Check source immutability against explicit output_filepath
    if source_filepath and output_filepath:
        if os.path.abspath(source_filepath).lower() == os.path.abspath(output_filepath).lower():
            raise ValueError(
                "Output file path cannot be identical to the source data file. "
                "Stepwise strictly enforces source data immutability."
            )

    # 2. Data rows
    def _sanitize(val: object) -> str:
        if val is None:
            return ""
        s = str(val)
        # Strip ASCII control characters incompatible with XML/OpenPyXL
        return re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", s)

    for idx, row in enumerate(rows):
        row_num = row_numbers[idx] if idx < len(row_numbers) else (idx + 1)
        raw_status = str(row_statuses.get(row_num, "Pending")).strip()
        canonical_status = "Pending"
        for code in ("Done", "Failed", "Interrupted", "Needs Verification", "Skipped", "Pending"):
            if code.lower() == raw_status.lower() or (raw_status and code.lower() in raw_status.lower()):
                canonical_status = code
                break

        detail = (row_details or {}).get(row_num, {})
        timestamp = detail.get("timestamp", "")

        reason = detail.get("reason", "")
        if not reason and canonical_status in ("Interrupted", "Needs Verification"):
            reason = "작업 중단됨 (ERP 확인 필요)"

        excel_row_idx = idx + 2
        # Write source data cells with formula-injection guard
        for c_idx, h in enumerate(headers):
            cell = ws.cell(row=excel_row_idx, column=c_idx + 1)
            raw_v = _sanitize(row.get(h, ""))
            cell.value = raw_v
            # Force string data type if starting with formula triggers
            if raw_v.startswith(("=", "+", "-", "@")):
                cell.data_type = "s"
            cell.border = thin_border

        # Result columns: Status, FinishedAt, Reason
        status_col = len(headers) + 1
        st_cell = ws.cell(row=excel_row_idx, column=status_col)
        st_cell.value = canonical_status
        st_cell.data_type = "s"
        st_cell.alignment = Alignment(horizontal="center", vertical="center")
        style_info = status_styles.get(canonical_status, status_styles["Pending"])
        if style_info.get("fill"):
            st_cell.fill = style_info["fill"]
        if style_info.get("font"):
            st_cell.font = style_info["font"]
        st_cell.border = thin_border

        ts_cell = ws.cell(row=excel_row_idx, column=status_col + 1)
        ts_cell.value = _sanitize(timestamp)
        ts_cell.data_type = "s"
        ts_cell.alignment = Alignment(horizontal="center", vertical="center")
        ts_cell.border = thin_border

        rs_cell = ws.cell(row=excel_row_idx, column=status_col + 2)
        clean_reason = _sanitize(reason)
        rs_cell.value = clean_reason
        if clean_reason.startswith(("=", "+", "-", "@")):
            rs_cell.data_type = "s"
        rs_cell.border = thin_border

    # 3. Column widths
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            val_str = str(cell.value or "")
            val_first_line = val_str.split("\n")[0] if val_str else ""
            max_len = max(max_len, len(val_first_line))
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 60)

    # 4. Resolve output path
    if not output_filepath:
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if source_filepath and os.path.exists(source_filepath):
            dir_name = os.path.dirname(os.path.abspath(source_filepath))
            stem = os.path.splitext(os.path.basename(source_filepath))[0]
            output_filepath = os.path.join(dir_name, f"{stem}_결과_{now_str}.xlsx")
        else:
            output_filepath = os.path.abspath(f"Stepwise_결과_{now_str}.xlsx")

    # Prevent accidental overwrite of source file even if generated output lands on same path
    if source_filepath and os.path.abspath(source_filepath).lower() == os.path.abspath(output_filepath).lower():
        base, ext = os.path.splitext(output_filepath)
        output_filepath = f"{base}_결과{ext}"

    os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)
    wb.save(output_filepath)
    return os.path.abspath(output_filepath)
