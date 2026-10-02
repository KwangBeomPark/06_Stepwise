"""Unit and integration tests for Milestone 2: Models, Packaging, Data, Results, Preflight, and Locks."""

import os

import openpyxl
import pytest

from stepwise.core.models import ActionItem, DataSourceConfig, Macro, MacroSettings, RecordedScreen
from stepwise.core.package import load_package, save_package
from stepwise.core.schema import CURRENT_SCHEMA_VERSION, validate_macro_dict
from stepwise.engine.errors import MacroSyntaxError
from stepwise.engine.preflight import run_preflight_checks
from stepwise.engine.results import ResultsManager, RowResultRecord
from stepwise.services.data_source import read_data_file
from stepwise.services.lock import acquire_lock, check_lock_status, release_lock


def test_models_to_dict_roundtrip() -> None:
    macro = Macro(
        name="Test Invoice Macro",
        recorded_screen=RecordedScreen(width=1920, height=1080, scale_percent=125, monitor_count=1),
        settings=MacroSettings(default_wait_before=0.3, image_confidence=0.92),
        data_source=DataSourceConfig(type="xlsx", file_hint="invoices.xlsx"),
        setup=[ActionItem(type="wait", seconds=0.5, note="Wait init")],
        per_row=[
            ActionItem(
                type="group",
                name="Fill Info",
                items=[
                    ActionItem(type="type_text", text="{Vendor}", mode="paste"),
                    ActionItem(type="key", keys="tab"),
                ],
            )
        ],
        cleanup=[ActionItem(type="key", keys="esc")],
    )

    d = macro.to_dict()
    reconstructed = Macro.from_dict(d)

    assert reconstructed.name == macro.name
    assert reconstructed.recorded_screen.scale_percent == 125
    assert reconstructed.settings.default_wait_before == 0.3
    assert len(reconstructed.setup) == 1
    assert len(reconstructed.per_row) == 1
    assert reconstructed.per_row[0].type == "group"
    assert len(reconstructed.per_row[0].items) == 2
    assert reconstructed.per_row[0].items[0].text == "{Vendor}"


def test_schema_rejects_newer_version() -> None:
    data = {"schema_version": CURRENT_SCHEMA_VERSION + 1, "setup": [], "per_row": [], "cleanup": []}
    with pytest.raises(MacroSyntaxError, match="newer version"):
        validate_macro_dict(data)


def test_schema_rejects_nested_groups() -> None:
    data = {
        "schema_version": 1,
        "per_row": [
            {
                "type": "group",
                "name": "Outer",
                "items": [
                    {"type": "group", "name": "Inner", "items": []}
                ],
            }
        ],
    }
    with pytest.raises(MacroSyntaxError, match="Nested groups"):
        validate_macro_dict(data)


def test_package_atomic_save_and_load(tmp_path: os.PathLike[str]) -> None:
    pkg_file = os.path.join(tmp_path, "sample.swm")
    macro = Macro(
        name="Packaging Test",
        per_row=[ActionItem(type="click", x=100, y=200, note="Click point")],
    )
    dummy_img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

    save_package(macro, pkg_file, image_files={"test_btn.png": dummy_img_bytes})
    assert os.path.exists(pkg_file)

    loaded_macro, extracted_dir = load_package(pkg_file)
    assert loaded_macro.name == "Packaging Test"
    assert len(loaded_macro.per_row) == 1
    assert loaded_macro.per_row[0].x == 100
    assert os.path.exists(os.path.join(extracted_dir, "images", "test_btn.png"))


def test_data_source_csv_multilingual_and_semicolon(tmp_path: os.PathLike[str]) -> None:
    csv_file = os.path.join(tmp_path, "polish_data.csv")
    content = "Vendor;Amount;City\nZażółć;1200.0;Warszawa\n한글업체;850;서울\n"
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write(content)

    headers, rows, row_nums = read_data_file(csv_file)
    assert headers == ["Vendor", "Amount", "City"]
    assert len(rows) == 2
    # Verify .0 normalization
    assert rows[0]["Amount"] == "1200"
    assert rows[0]["Vendor"] == "Zażółć"
    assert rows[1]["Vendor"] == "한글업체"
    assert row_nums == [2, 3]


def test_data_source_xlsx_reading(tmp_path: os.PathLike[str]) -> None:
    xlsx_file = os.path.join(tmp_path, "test.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "Name", "Total"])
    ws.append([1, "Item A", 50.0])
    ws.append([2, "Item B", 123.45])
    wb.save(xlsx_file)
    wb.close()

    headers, rows, row_nums = read_data_file(xlsx_file)
    assert headers == ["ID", "Name", "Total"]
    assert len(rows) == 2
    assert rows[0]["Total"] == "50"
    assert rows[1]["Total"] == "123.45"
    assert row_nums == [2, 3]


def test_results_csv_flush_and_resume(tmp_path: os.PathLike[str]) -> None:
    res_mgr = ResultsManager("TestMacro", os.path.join(tmp_path, "data.csv"), results_dir=str(tmp_path))

    # Append first row Done
    r1 = RowResultRecord(run_id="run1", row_number=1, row_hash="hash1", status="Done")
    res_mgr.append_record(r1)

    # Append second row Running (simulating crash before completion)
    r2 = RowResultRecord(run_id="run1", row_number=2, row_hash="hash2", status="Running")
    res_mgr.append_record(r2)

    statuses = res_mgr.load_latest_row_statuses()
    assert statuses[1].status == "Done"
    # Unfinished Running row must be interpreted as Interrupted
    assert statuses[2].status == "Interrupted"

    # Suggestion should start from next row
    source_rows = [{"col": "a"}, {"col": "b"}, {"col": "c"}]
    suggestion, warnings = res_mgr.get_resume_suggestion([1, 2, 3], source_rows)
    # Row 3 is first Pending row
    assert suggestion == 3


def test_preflight_checks_diagnostics(tmp_path: os.PathLike[str]) -> None:
    macro = Macro(
        name="Preflight Test",
        recorded_screen=RecordedScreen(width=1600, height=900, scale_percent=100),
        per_row=[
            ActionItem(type="type_text", text="{Vendor} {Amount}"),
            # Non-existent image reference
            ActionItem(type="click_image", image="images/missing.png"),
        ],
    )

    rows = [
        {"Vendor": "ACME", "Amount": "100"},
        {"Vendor": "", "Amount": "200"},  # Empty Vendor!
    ]

    issues = run_preflight_checks(
        macro=macro,
        rows_data=rows,
        package_dir=str(tmp_path),
        data_file_path=os.path.join(tmp_path, "dummy.csv"),
        results_dir=str(tmp_path),
    )

    errors = [i for i in issues if i.is_error]
    warnings = [i for i in issues if i.is_warning]

    # Should detect: missing image, empty Vendor on row 2
    err_msgs = [e.message for e in errors]
    assert any("missing.png" in m for m in err_msgs)
    assert any('contains empty values' in m for m in err_msgs)

    # Warnings should include screen mismatch (1600x900 vs actual screen)
    warn_msgs = [w.message for w in warnings]
    assert any("Screen mismatch" in m for m in warn_msgs)


def test_lock_lifecycle(tmp_path: os.PathLike[str]) -> None:
    swm_path = os.path.join(tmp_path, "shared_macro.swm")
    open(swm_path, "w").close()

    # Initial lock status
    is_locked, info, is_stale = check_lock_status(swm_path)
    assert not is_locked

    # Acquire lock
    lock_info = acquire_lock(swm_path)
    assert lock_info.user is not None

    is_locked, info, is_stale = check_lock_status(swm_path)
    assert is_locked
    assert not is_stale

    # Release lock
    release_lock(swm_path)
    is_locked, info, is_stale = check_lock_status(swm_path)
    assert not is_locked
