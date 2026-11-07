"""Comprehensive unit tests for smart text filters and built-in system variables."""

from __future__ import annotations

import datetime
import re

import pytest

from stepwise.core.variables import (
    extract_variable_names,
    substitute_variables,
)


def test_extract_variables_with_filters() -> None:
    template = "Item: {Product|strip|upper}, Cost: {Amount|clean}, Due: {DueDate|date:%Y-%m-%d}"
    vars_found = extract_variable_names(template)
    assert vars_found == ["Product", "Amount", "DueDate"]


def test_extract_variables_exclude_builtins() -> None:
    template = "Processed row {ROW_NUM} for {Customer} on {TODAY} at {NOW}"
    all_vars = extract_variable_names(template, include_builtins=True)
    assert all_vars == ["ROW_NUM", "Customer", "TODAY", "NOW"]

    data_only_vars = extract_variable_names(template, include_builtins=False)
    assert data_only_vars == ["Customer"]


def test_filter_clean_monetary() -> None:
    template = "{Amount|clean}"

    # Korean Won with commas and spaces
    res1 = substitute_variables(template, {"Amount": " ₩ 1,234,567 "})
    assert res1 == "1234567"

    # US Dollars with decimal and negative
    res2 = substitute_variables(template, {"Amount": " -$3,450.75 "})
    assert res2 == "-3450.75"

    # Accounting negative with parenthesis
    res3 = substitute_variables(template, {"Amount": " (50,000) "})
    assert res3 == "-50000"

    # Euro symbol
    res4 = substitute_variables(template, {"Amount": " € 8,990.00 "})
    assert res4 == "8990.00"


def test_filter_strip_upper_lower() -> None:
    row = {"Text": "  Hello World  "}
    assert substitute_variables("{Text|strip}", row) == "Hello World"
    assert substitute_variables("{Text|strip|upper}", row) == "HELLO WORLD"
    assert substitute_variables("{Text|strip|lower}", row) == "hello world"


def test_filter_int() -> None:
    row1 = {"Val": " ₩ 1,500.00 "}
    assert substitute_variables("{Val|int}", row1) == "1500"

    row2 = {"Val": "2,500"}
    assert substitute_variables("{Val|int}", row2) == "2500"


def test_filter_date() -> None:
    # Slash to dash
    row1 = {"Date": "2026/11/07"}
    assert substitute_variables("{Date|date:%Y-%m-%d}", row1) == "2026-11-07"

    # Compact YYYYMMDD to formatted
    row2 = {"Date": "20261107"}
    assert substitute_variables("{Date|date:%Y.%m.%d}", row2) == "2026.11.07"

    # Fallback safety: invalid date returns raw string without exception
    row3 = {"Date": "not-a-date"}
    assert substitute_variables("{Date|date:%Y-%m-%d}", row3) == "not-a-date"


def test_filter_replace_slice_default() -> None:
    row = {"Code": "KR-1234-XYZ", "Empty": ""}

    # Replace hyphen with empty
    assert substitute_variables("{Code|replace:-:}", row) == "KR1234XYZ"

    # Slice start:end
    assert substitute_variables("{Code|slice:0:2}", row) == "KR"

    # Default fallback
    assert substitute_variables("{Empty|default:N/A}", row) == "N/A"
    assert substitute_variables("{Code|default:N/A}", row) == "KR-1234-XYZ"


def test_filter_chaining() -> None:
    # Strip + clean + int in pipeline
    row = {"Val": "  ₩ 9,876.54  "}
    assert substitute_variables("{Val|clean|int}", row) == "9876"


def test_builtin_system_variables() -> None:
    # TODAY: YYYY-MM-DD
    today_val = substitute_variables("Date: {TODAY}", {})
    expected_today = datetime.date.today().isoformat()
    assert today_val == f"Date: {expected_today}"

    # Filter on TODAY
    compact_today = substitute_variables("Date: {TODAY|date:%Y%m%d}", {})
    assert compact_today == f"Date: {datetime.date.today().strftime('%Y%m%d')}"

    # NOW: YYYY-MM-DD HH:MM:SS
    now_val = substitute_variables("Time: {NOW}", {})
    assert re.match(r"^Time: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", now_val)

    # ROW_NUM with context
    row_num_val = substitute_variables("Row: {ROW_NUM}", {}, context={"_ROW_NUM": 42})
    assert row_num_val == "Row: 42"

    # ROW_NUM default
    row_num_default = substitute_variables("Row: {ROW_NUM}", {})
    assert row_num_default == "Row: 1"


def test_row_data_overrides_builtin() -> None:
    # If the user explicitly has a column named TODAY in their data file, it takes precedence
    row = {"TODAY": "UserDefinedValue"}
    res = substitute_variables("Date: {TODAY}", row)
    assert res == "Date: UserDefinedValue"


def test_unknown_column_strict() -> None:
    with pytest.raises(KeyError, match="NoSuchCol"):
        substitute_variables("{NoSuchCol|clean}", {}, strict=True)

    non_strict = substitute_variables("{NoSuchCol|clean}", {}, strict=False)
    assert non_strict == "{NoSuchCol|clean}"


def test_filter_clean_korean_accounting_negatives() -> None:
    # Delta marks
    assert substitute_variables("{A|clean}", {"A": "△ 1,250,000"}) == "-1250000"
    assert substitute_variables("{A|clean}", {"A": "▲ 50,000"}) == "-50000"

    # Trailing SAP-style negative
    assert substitute_variables("{A|clean}", {"A": "3,400.50-"}) == "-3400.50"


def test_filter_int_large_numbers_no_precision_loss() -> None:
    # Numbers exceeding 2^53 (e.g. 16+ digit card/account numbers) must not lose precision
    large_num = "9007199254740993"
    assert substitute_variables("{A|int}", {"A": large_num}) == "9007199254740993"
    assert substitute_variables("{A|int}", {"A": f" ₩ {large_num}.75 "}) == "9007199254740993"


def test_filter_date_with_colons() -> None:
    row = {"TS": "2026-11-07 14:30:00"}
    res = substitute_variables("{TS|date:%Y-%m-%d %H:%M}", row)
    assert res == "2026-11-07 14:30"
