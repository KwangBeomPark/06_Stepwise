"""Unit tests for variable parsing and substitution."""

import pytest

from stepwise.core.variables import extract_variable_names, substitute_variables


def test_extract_variables() -> None:
    template = "Invoice: {Vendor} on {Date} for amount {Total Amount} with {{literal_braces}}"
    vars_found = extract_variable_names(template)
    assert vars_found == ["Vendor", "Date", "Total Amount"]


def test_substitute_variables_basic() -> None:
    template = "Vendor: {Vendor}, Amount: {Amount}"
    row = {"Vendor": "ACME Corp", "Amount": "1200"}
    res = substitute_variables(template, row)
    assert res == "Vendor: ACME Corp, Amount: 1200"


def test_substitute_literal_braces() -> None:
    template = "Literal {{Vendor}} is not replaced, but {Amount} is."
    row = {"Vendor": "ACME", "Amount": "500"}
    res = substitute_variables(template, row)
    assert res == "Literal {Vendor} is not replaced, but 500 is."


def test_substitute_missing_column_strict() -> None:
    template = "Hello {MissingCol}"
    row = {"Present": "Yes"}
    with pytest.raises(KeyError, match="MissingCol"):
        substitute_variables(template, row, strict=True)


def test_substitute_missing_column_non_strict() -> None:
    template = "Hello {MissingCol}"
    row = {"Present": "Yes"}
    res = substitute_variables(template, row, strict=False)
    assert res == "Hello {MissingCol}"


def test_substitute_unicode_multilingual() -> None:
    template = "{한국어열} - {PolishCol}"
    row = {"한국어열": "거래처명", "PolishCol": "Zażółć gęślą jaźń"}
    res = substitute_variables(template, row)
    assert res == "거래처명 - Zażółć gęślą jaźń"


def test_substitute_empty_and_numeric_values() -> None:
    template = "{Empty} - {Num}"
    row = {"Empty": None, "Num": 1200}
    res = substitute_variables(template, row)
    assert res == " - 1200"
