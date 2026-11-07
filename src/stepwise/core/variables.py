"""Variable parsing, substitution, and safe filter pipeline for Stepwise templates.

Handles:
- {ColumnName} data column placeholders
- Safe whitelist filters: {ColumnName|clean}, {ColumnName|upper}, {ColumnName|date:%Y-%m-%d}, etc.
- Built-in system variables: {TODAY}, {NOW}, {ROW_NUM}
- Literal brace escapes {{literal}}
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Callable

# Regex to find unescaped {column_name} patterns while respecting {{ }} escapes
_VAR_REGEX = re.compile(r"\{\{([^{}]*)\}\}|\{([^{}]+)\}")

# Built-in system variable names (case-insensitive lookup supported)
BUILTIN_VARIABLES: frozenset[str] = frozenset({"TODAY", "NOW", "ROW_NUM", "DATE", "TIME"})


def filter_clean(val: str, *args: str) -> str:
    """Clean monetary, accounting or numeric string.

    - Removes currency symbols (₩, $, €, ¥, £), commas, spaces.
    - Preserves negative signs (-) and decimal points (.).
    - Converts accounting parenthesis (1,000) to -1000.
    - Converts accounting delta marks △1,000 / ▲1,000 to -1000.
    - Converts trailing SAP-style negative signs 1,000- to -1000.
    """
    s = val.strip()
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1]
    elif s.startswith(("△", "▲")):
        is_negative = True
        s = re.sub(r"^[△▲]\s*", "", s)
    elif s.endswith("-"):
        is_negative = True
        s = s[:-1]
    elif s.startswith("-"):
        is_negative = True
        s = s[1:]

    # Remove all characters except digits and decimal point
    cleaned = re.sub(r"[^\d.]", "", s)
    if not cleaned:
        return ""
    return f"-{cleaned}" if is_negative else cleaned


def filter_strip(val: str, *args: str) -> str:
    """Strip leading and trailing whitespace."""
    return val.strip()


def filter_upper(val: str, *args: str) -> str:
    """Convert to uppercase."""
    return val.upper()


def filter_lower(val: str, *args: str) -> str:
    """Convert to lowercase."""
    return val.lower()


def filter_int(val: str, *args: str) -> str:
    """Extract integer part without floating point precision loss on large numbers."""
    cleaned = filter_clean(val)
    if not cleaned:
        return ""
    int_part = cleaned.split(".")[0]
    if int_part in ("", "-", "-0"):
        return "0"
    return int_part


def filter_date(val: str, *args: str) -> str:
    """Reformat a date string to target format. Safe fallback to original string on failure.

    Usage:
    - {DateCol|date:%Y-%m-%d}
    - {DateCol|date:%Y-%m-%d %H:%M}
    """
    s = val.strip()
    if not s:
        return ""
    out_fmt = args[0] if args else "%Y-%m-%d"
    in_fmt = args[1] if len(args) > 1 else None

    if in_fmt:
        try:
            dt = datetime.datetime.strptime(s, in_fmt)
            return dt.strftime(out_fmt)
        except Exception:
            return s

    common_formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y%m%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y.%m.%d %H:%M",
    )
    for fmt in common_formats:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return dt.strftime(out_fmt)
        except Exception:
            continue
    return s


def filter_replace(val: str, *args: str) -> str:
    """Replace occurrences of substring: replace:old:new."""
    old = args[0] if len(args) > 0 else ""
    new = args[1] if len(args) > 1 else ""
    return val.replace(old, new)


def filter_slice(val: str, *args: str) -> str:
    """Slice string: slice:start:end or slice:start."""
    if not args:
        return val
    try:
        start = int(args[0]) if args[0] else 0
        end = int(args[1]) if len(args) > 1 and args[1] else len(val)
        return val[start:end]
    except ValueError:
        return val


def filter_default(val: str, *args: str) -> str:
    """Provide a fallback string if value is empty."""
    fallback = args[0] if args else ""
    return val if val else fallback


SAFE_FILTERS: dict[str, Callable[..., str]] = {
    "clean": filter_clean,
    "strip": filter_strip,
    "upper": filter_upper,
    "lower": filter_lower,
    "int": filter_int,
    "date": filter_date,
    "replace": filter_replace,
    "slice": filter_slice,
    "default": filter_default,
}


def apply_filter(val: str, filter_expr: str) -> str:
    """Apply a single filter expression (e.g. 'clean', 'date:%Y-%m-%d %H:%M')."""
    colon_idx = filter_expr.find(":")
    if colon_idx == -1:
        fname = filter_expr.strip().lower()
        fargs: list[str] = []
    else:
        fname = filter_expr[:colon_idx].strip().lower()
        arg_str = filter_expr[colon_idx + 1 :]
        if fname == "date":
            # Preserve full date format string even if it contains colons like %H:%M:%S
            fargs = [arg_str]
        elif fname == "replace":
            # Split into at most 2 parts (old, new)
            fargs = arg_str.split(":", 1)
        else:
            fargs = arg_str.split(":")

    fn = SAFE_FILTERS.get(fname)
    if fn is not None:
        try:
            return fn(val, *fargs)
        except Exception:
            return val
    return val


def get_builtin_variable_value(name: str, context: dict[str, object] | None = None) -> str | None:
    """Resolve built-in system variable names."""
    upper = name.strip().upper()
    if upper in ("TODAY", "DATE"):
        return datetime.date.today().isoformat()
    if upper in ("NOW", "TIME"):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if upper == "ROW_NUM":
        if context:
            for k in ("_ROW_NUM", "__row_num__", "row_number", "Row"):
                if k in context and context[k] is not None:
                    return str(context[k])
        return "1"
    return None


def extract_variable_names(template: str, include_builtins: bool = True) -> list[str]:
    """Extract all unique column names referenced in template.

    Handles filters ({Column|clean} -> 'Column') and optionally excludes built-in variables.
    """
    variables: list[str] = []
    for match in _VAR_REGEX.finditer(template):
        escaped_literal, var_expr = match.groups()
        if var_expr is not None:
            # Strip filter expressions: "Amount|clean|strip" -> "Amount"
            base_var = var_expr.split("|")[0].strip()
            if not include_builtins and base_var.upper() in BUILTIN_VARIABLES:
                continue
            if base_var and base_var not in variables:
                variables.append(base_var)
    return variables


def substitute_variables(
    template: str,
    row_data: dict[str, object],
    strict: bool = True,
    context: dict[str, object] | None = None,
) -> str:
    """Substitute {column_name} and {column_name|filter} in template with values.

    - {{ }} is replaced with literal { }
    - {Column} is replaced with row_data['Column']
    - Built-in {TODAY}, {NOW}, {ROW_NUM} are resolved automatically if not in row_data
    - Safe pipeline filters applied: {Amount|clean}, {Date|date:%Y%m%d}
    - If strict is True and a column is missing, KeyError is raised.
    """

    def _replacer(match: re.Match[str]) -> str:
        escaped_literal, var_expr = match.groups()
        if escaped_literal is not None:
            # Literal {{content}} -> {content}
            return f"{{{escaped_literal}}}"

        if var_expr is not None:
            parts = [p.strip() for p in var_expr.split("|")]
            base_var = parts[0]
            filter_chain = parts[1:]

            val: object | None = None
            if base_var in row_data:
                val = row_data[base_var]
            elif base_var.upper() in BUILTIN_VARIABLES:
                ctx = context if context is not None else row_data
                val = get_builtin_variable_value(base_var, ctx)
            else:
                if strict:
                    raise KeyError(f"Column '{base_var}' not found in data row.")
                return match.group(0)

            val_str = "" if val is None else str(val)

            # Apply filter pipeline
            for fexpr in filter_chain:
                val_str = apply_filter(val_str, fexpr)

            return val_str

        return match.group(0)

    return _VAR_REGEX.sub(_replacer, template)
