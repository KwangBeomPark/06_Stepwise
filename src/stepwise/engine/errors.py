"""Stepwise exception hierarchy."""

from __future__ import annotations


class StepwiseError(Exception):
    """Base exception for all Stepwise runtime errors."""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or ""

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} ({self.details})"
        return self.message


class StepFailure(StepwiseError):
    """Raised when an action step fails (e.g. timeout, Guard/Verify failure)."""

    def __init__(
        self,
        message: str,
        step_id: str | None = None,
        step_label: str | None = None,
        row_number: int | None = None,
        best_match: float | None = None,
        details: str | None = None,
    ) -> None:
        super().__init__(message, details)
        self.step_id = step_id
        self.step_label = step_label or ""
        self.row_number = row_number
        self.best_match = best_match

    def formatted_reason(self) -> str:
        parts: list[str] = []
        if self.row_number is not None:
            parts.append(f"Row {self.row_number}")
        if self.step_label:
            parts.append(f'step "{self.step_label}"')
        elif self.step_id:
            parts.append(f"step {self.step_id}")
        prefix = ", ".join(parts)
        match_str = (
            f" (best match {int(self.best_match * 100)}%)" if self.best_match is not None else ""
        )
        if prefix:
            return f"{prefix} — {self.message}{match_str}"
        return f"{self.message}{match_str}"


class AbortRequested(StepwiseError):
    """Raised when execution is aborted by user (F12 or Stop button)."""

    def __init__(
        self, message: str = "Execution aborted by user.", row_number: int | None = None
    ) -> None:
        super().__init__(message)
        self.row_number = row_number


class ScreenUnavailableError(StepwiseError):
    """Raised when display is locked, minimized, disconnected, or black."""

    def __init__(
        self, message: str = "Screen unavailable (session locked or disconnected?)."
    ) -> None:
        super().__init__(message)


class MacroSyntaxError(StepwiseError):
    """Raised when macro schema or action parameters are invalid."""


class PreflightError(StepwiseError):
    """Raised when preflight validation fails with blocking errors."""
