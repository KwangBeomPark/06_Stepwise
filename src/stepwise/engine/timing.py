"""Timing and interruptible sleep services for Stepwise.

Ensures every delay responds immediately to F12 emergency stop / Stop button events.
Direct usage of time.sleep is prohibited.
"""

from __future__ import annotations

import enum
import threading
from collections.abc import Callable

from stepwise.engine.errors import AbortRequested


class SpeedMode(enum.Enum):
    NORMAL = "Normal"
    SLOW = "Slow"
    VERY_SLOW = "Very slow"

    @property
    def extra_seconds(self) -> float:
        if self == SpeedMode.SLOW:
            return 0.5
        if self == SpeedMode.VERY_SLOW:
            return 1.0
        return 0.0

    @classmethod
    def from_string(cls, val: str | None) -> SpeedMode:
        if not val:
            return cls.NORMAL
        norm = val.strip().lower()
        if norm in ("slow", "slow +0.5s", "+0.5s"):
            return cls.SLOW
        if norm in ("very slow", "very_slow", "very slow +1s", "veryslow"):
            return cls.VERY_SLOW
        return cls.NORMAL


class ExecutionController:
    """Coordinates Pause, Resume, Stop, and Step-by-step signals across engine threads."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        # _pause_event: Set when running normally, cleared when paused
        self._pause_event = threading.Event()
        self._pause_event.set()

        self._step_by_step_event = threading.Event()
        self._step_by_step_enabled = False
        self._on_pause_callbacks: list[Callable[[], None]] = []

    def stop(self) -> None:
        """Signal instant abort."""
        self._stop_event.set()
        # In case we were paused, wake up to abort immediately
        self._pause_event.set()
        self._step_by_step_event.set()

    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    def pause(self) -> None:
        """Pause execution at the next action boundary."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume paused execution."""
        self._pause_event.set()

    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def enable_step_by_step(self, enabled: bool) -> None:
        self._step_by_step_enabled = enabled
        if not enabled:
            self._step_by_step_event.set()

    def is_step_by_step(self) -> bool:
        return self._step_by_step_enabled

    def step_next(self) -> None:
        """Advance one step in step-by-step mode."""
        self._step_by_step_event.set()

    def check_abort(self, row_number: int | None = None) -> None:
        """Raise AbortRequested if stop signal is set."""
        if self._stop_event.is_set():
            raise AbortRequested("Execution aborted by user.", row_number=row_number)

    def wait(self, seconds: float, row_number: int | None = None) -> None:
        """Interruptible sleep that stops instantly if aborted.

        Does not use time.sleep directly.
        """
        self.check_abort(row_number)
        if seconds <= 0:
            return

        stopped = self._stop_event.wait(timeout=seconds)
        if stopped:
            raise AbortRequested("Execution aborted by user.", row_number=row_number)

    def wait_action_boundary(self, row_number: int | None = None) -> None:
        """Wait if paused or in step-by-step mode at action boundary."""
        self.check_abort(row_number)

        # Handle Pause: wait while cleared
        while not self._pause_event.is_set():
            if self._stop_event.is_set():
                raise AbortRequested("Execution aborted by user.", row_number=row_number)
            self._pause_event.wait(timeout=0.05)

        # Handle Step-by-step
        if self._step_by_step_enabled:
            self._step_by_step_event.clear()
            while not self._step_by_step_event.is_set():
                if self._stop_event.is_set():
                    raise AbortRequested("Execution aborted by user.", row_number=row_number)
                self._step_by_step_event.wait(timeout=0.05)

        self.check_abort(row_number)


def calculate_action_delay(
    action_wait_before: float | None,
    default_wait_before: float = 0.2,
    speed: SpeedMode = SpeedMode.NORMAL,
) -> float:
    """Calculate the total wait before an action."""
    base = (
        default_wait_before if action_wait_before is None else max(0.0, float(action_wait_before))
    )
    return base + speed.extra_seconds
