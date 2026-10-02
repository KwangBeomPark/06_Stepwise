"""Unit tests for timing, speed delays, and interruptible waits."""

import time

import pytest

from stepwise.engine.errors import AbortRequested
from stepwise.engine.timing import (
    ExecutionController,
    SpeedMode,
    calculate_action_delay,
)


def test_speed_mode_parsing() -> None:
    assert SpeedMode.from_string("Normal") == SpeedMode.NORMAL
    assert SpeedMode.from_string("Slow") == SpeedMode.SLOW
    assert SpeedMode.from_string("Slow +0.5s") == SpeedMode.SLOW
    assert SpeedMode.from_string("Very slow") == SpeedMode.VERY_SLOW
    assert SpeedMode.from_string("unknown") == SpeedMode.NORMAL


def test_speed_extra_delays() -> None:
    assert SpeedMode.NORMAL.extra_seconds == 0.0
    assert SpeedMode.SLOW.extra_seconds == 0.5
    assert SpeedMode.VERY_SLOW.extra_seconds == 1.0


def test_calculate_action_delay() -> None:
    # 1. Defaults
    assert calculate_action_delay(None, default_wait_before=0.2, speed=SpeedMode.NORMAL) == 0.2
    # 2. Overridden action wait_before
    assert calculate_action_delay(0.5, default_wait_before=0.2, speed=SpeedMode.NORMAL) == 0.5
    # 3. Slow speed adds +0.5s
    assert calculate_action_delay(0.2, default_wait_before=0.2, speed=SpeedMode.SLOW) == 0.7
    # 4. Very slow adds +1.0s
    assert calculate_action_delay(None, default_wait_before=0.2, speed=SpeedMode.VERY_SLOW) == 1.2


def test_interruptible_wait_normal() -> None:
    ctrl = ExecutionController()
    t0 = time.time()
    ctrl.wait(0.05)
    elapsed = time.time() - t0
    assert elapsed >= 0.04


def test_interruptible_wait_abort() -> None:
    ctrl = ExecutionController()
    ctrl.stop()
    with pytest.raises(AbortRequested):
        ctrl.wait(5.0)


def test_pause_and_resume() -> None:
    ctrl = ExecutionController()
    ctrl.pause()
    assert ctrl.is_paused()
    ctrl.resume()
    assert not ctrl.is_paused()
