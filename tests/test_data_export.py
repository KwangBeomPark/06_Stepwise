import hashlib
import os

import openpyxl
import pytest
from PySide6.QtWidgets import QApplication

from stepwise.services.data_source import export_execution_results_xlsx
from stepwise.ui.data_panel import DataPanel


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_export_execution_results_xlsx_basic(tmp_path):
    headers = ["Name", "Amount", "Account"]
    rows = [
        {"Name": "Alice", "Amount": "1000", "Account": "111-222"},
        {"Name": "Bob", "Amount": "2500", "Account": "333-444"},
        {"Name": "Charlie", "Amount": "3000", "Account": "555-666"},
    ]
    row_numbers = [2, 3, 4]
    row_statuses = {2: "Done", 3: "Failed", 4: "Skipped"}
    row_details = {
        2: {"timestamp": "2026-11-07 10:00:00", "reason": ""},
        3: {"timestamp": "2026-11-07 10:01:15", "reason": "Element not found on screen"},
        4: {"timestamp": "2026-11-07 10:01:20", "reason": "User skipped"},
    }

    out_file = str(tmp_path / "output_test.xlsx")
    saved_path = export_execution_results_xlsx(
        headers=headers,
        rows=rows,
        row_numbers=row_numbers,
        row_statuses=row_statuses,
        source_filepath=None,
        output_filepath=out_file,
        row_details=row_details,
    )

    assert os.path.isfile(saved_path)
    assert saved_path == out_file

    wb = openpyxl.load_workbook(saved_path)
    ws = wb.active
    assert ws is not None

    # Verify headers
    header_vals = [cell.value for cell in ws[1]]
    expected_headers = ["Name", "Amount", "Account", "Stepwise_상태", "Stepwise_완료일시", "Stepwise_오류내용"]
    assert header_vals == expected_headers

    # Row 2 (Alice - Done)
    row2_vals = [cell.value for cell in ws[2]]
    assert row2_vals[0] == "Alice"
    assert row2_vals[1] == "1000"
    assert row2_vals[3] == "Done"
    assert row2_vals[4] == "2026-11-07 10:00:00"
    assert (row2_vals[5] or "") == ""

    # Row 3 (Bob - Failed)
    row3_vals = [cell.value for cell in ws[3]]
    assert row3_vals[0] == "Bob"
    assert row3_vals[3] == "Failed"
    assert row3_vals[4] == "2026-11-07 10:01:15"
    assert row3_vals[5] == "Element not found on screen"

    wb.close()


def test_export_execution_results_xlsx_source_immutability(tmp_path):
    # Create original source excel file
    source_wb = openpyxl.Workbook()
    source_ws = source_wb.active
    source_ws.title = "SourceData"
    source_ws.append(["ColA", "ColB"])
    source_ws.append(["Value1", "Value2"])
    source_path = str(tmp_path / "original_source.xlsx")
    source_wb.save(source_path)
    source_wb.close()

    with open(source_path, "rb") as f:
        original_hash = hashlib.sha256(f.read()).hexdigest()

    original_mtime = os.path.getmtime(source_path)

    # Perform export with source_filepath provided but no output_filepath
    saved_path = export_execution_results_xlsx(
        headers=["ColA", "ColB"],
        rows=[{"ColA": "Value1", "ColB": "Value2"}],
        row_numbers=[2],
        row_statuses={2: "Done"},
        source_filepath=source_path,
        output_filepath=None,
    )

    # Source file must be completely untouched
    assert os.path.exists(source_path)
    with open(source_path, "rb") as f:
        new_hash = hashlib.sha256(f.read()).hexdigest()
    assert new_hash == original_hash
    assert os.path.getmtime(source_path) == original_mtime

    # Saved path must be a separate file
    assert saved_path != source_path
    assert os.path.isfile(saved_path)
    assert "_결과_" in os.path.basename(saved_path)


def test_export_execution_results_xlsx_color_styling(tmp_path):
    out_file = str(tmp_path / "style_test.xlsx")
    export_execution_results_xlsx(
        headers=["Item"],
        rows=[
            {"Item": "A"},
            {"Item": "B"},
            {"Item": "C"},
            {"Item": "D"},
        ],
        row_numbers=[2, 3, 4, 5],
        row_statuses={2: "Done", 3: "Failed", 4: "Interrupted", 5: "Skipped"},
        output_filepath=out_file,
    )

    wb = openpyxl.load_workbook(out_file)
    ws = wb.active

    # Done (row 2, col 2 -> Stepwise_상태)
    cell_done = ws.cell(row=2, column=2)
    assert cell_done.value == "Done"
    assert str(cell_done.fill.start_color.rgb).endswith("E6F4EA")
    assert str(cell_done.font.color.rgb).endswith("137333")

    # Failed (row 3, col 2)
    cell_failed = ws.cell(row=3, column=2)
    assert cell_failed.value == "Failed"
    assert str(cell_failed.fill.start_color.rgb).endswith("FCE8E6")
    assert str(cell_failed.font.color.rgb).endswith("C5221F")

    wb.close()


def test_data_panel_export_integration(qapp, tmp_path):
    panel = DataPanel()
    assert panel.btn_export.isEnabled() is False
    assert panel.export_results() == ""

    # Prepare a test CSV
    csv_path = str(tmp_path / "sample.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("ID,Product\n1,Apple\n2,Banana\n")

    loaded = panel.load_file(csv_path)
    assert loaded is True
    assert panel.btn_export.isEnabled() is True

    # Update statuses and error details
    panel.update_row_status(2, "Done")
    panel.update_row_status(3, "Failed", reason="Network timeout")

    out_xlsx = str(tmp_path / "exported_results.xlsx")
    result_path = panel.export_results(output_filepath=out_xlsx)

    assert result_path == out_xlsx
    assert os.path.isfile(out_xlsx)

    wb = openpyxl.load_workbook(out_xlsx)
    ws = wb.active
    assert ws.cell(row=1, column=1).value == "ID"
    assert ws.cell(row=1, column=2).value == "Product"
    assert ws.cell(row=1, column=3).value == "Stepwise_상태"
    assert ws.cell(row=2, column=3).value == "Done"
    assert ws.cell(row=3, column=3).value == "Failed"
    assert ws.cell(row=3, column=5).value == "Network timeout"
    wb.close()


def test_export_source_path_protection(tmp_path):
    source_path = str(tmp_path / "protected_source.xlsx")
    wb = openpyxl.Workbook()
    wb.save(source_path)
    wb.close()

    # Attempting to overwrite the exact source path must raise ValueError
    with pytest.raises(ValueError, match="cannot be identical"):
        export_execution_results_xlsx(
            headers=["A"],
            rows=[{"A": "1"}],
            row_numbers=[1],
            row_statuses={1: "Done"},
            source_filepath=source_path,
            output_filepath=source_path,
        )


def test_export_formula_injection_guard(tmp_path):
    out_xlsx = str(tmp_path / "formula_guard.xlsx")
    export_execution_results_xlsx(
        headers=["Code", "Amount"],
        rows=[
            {"Code": "=1+1", "Amount": "+500"},
            {"Code": "-CMD|' /C calc'!A0", "Amount": "@SUM(1,2)"},
        ],
        row_numbers=[1, 2],
        row_statuses={1: "Done", 2: "Failed"},
        output_filepath=out_xlsx,
    )

    wb = openpyxl.load_workbook(out_xlsx)
    ws = wb.active
    # In openpyxl, cells forced with data_type="s" are stored as string literals
    cell1 = ws.cell(row=2, column=1)
    assert cell1.data_type == "s"
    assert cell1.value == "=1+1"

    cell2 = ws.cell(row=3, column=1)
    assert cell2.data_type == "s"
    wb.close()
