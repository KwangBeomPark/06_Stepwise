"""Variable parsing, substitution, and escaping for Stepwise templates.

Handles {ColumnName} placeholders, {{literal}} braces, and missing column detection.
"""

from __future__ import annotations

import re

# Regex to find unescaped {column_name} patterns while respecting {{ }} escapes
_VAR_REGEX = re.compile(r"\{\{([^{}]*)\}\}|\{([^{}]+)\}")


def extract_variable_names(template: str) -> list[str]:
    """Extract all unique column names referenced as {column_name} in template."""
    variables: list[str] = []
    for match in _VAR_REGEX.finditer(template):
        escaped_literal, var_name = match.groups()
        if var_name is not None:
            if var_name not in variables:
                variables.append(var_name)
    return variables


def substitute_variables(
    template: str,
    row_data: dict[str, object],
    strict: bool = True,
) -> str:
    """Substitute {column_name} in template with values from row_data.

    - {{ }} is replaced with { }
    - {Column} is replaced with str(row_data['Column'])
    - If strict is True and a column is missing, KeyError is raised.
    """
    def _replacer(match: re.Match[str]) -> str:
        escaped_literal, var_name = match.groups()
        if escaped_literal is not None:
            # Literal {{content}} -> {content}
            return f"{{{escaped_literal}}}"

        if var_name is not None:
            if var_name not in row_data:
                if strict:
                    raise KeyError(f"Column '{var_name}' not found in data row.")
                return match.group(0)

            val = row_data[var_name]
            return "" if val is None else str(val)

        return match.group(0)

    return _VAR_REGEX.sub(_replacer, template)
