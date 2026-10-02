"""Action execution handlers implementing Section 7 specifications.

Handles:
- Click, ClickImage, TypeText, KeyPress, Wait, WaitImage, WaitImageGone, Group
- Universal Guard (pre-action) and Verify (post-action) image checks
- Precise wait_before + speed_extra calculation
- Full variable substitution for data macros
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from typing import Any

from stepwise.core.variables import substitute_variables
from stepwise.engine.errors import StepFailure
from stepwise.engine.timing import ExecutionController, SpeedMode, calculate_action_delay
from stepwise.services.clipboard import temporary_clipboard_text
from stepwise.services.input_win import click_at, press_keys, type_unicode_string
from stepwise.services.matcher import poll_until_disappears, poll_until_found


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    """Retrieve attribute or dict key."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _resolve_image_path(base_dir: str | None, img_path: str) -> str:
    """Resolve image path relative to package base_dir if needed."""
    if not img_path:
        return ""
    if os.path.isabs(img_path) or not base_dir:
        return img_path
    return os.path.normpath(os.path.join(base_dir, img_path))


def execute_guard_or_verify(
    condition: Any,
    label: str,
    base_dir: str | None,
    controller: ExecutionController | None,
    default_confidence: float,
    step_id: str | None,
    step_label: str | None,
    row_number: int | None,
) -> None:
    """Execute Guard or Verify image polling."""
    if not condition:
        return

    img_rel = _get_val(condition, "image")
    if not img_rel:
        return
    img_path = _resolve_image_path(base_dir, img_rel)
    region = _get_val(condition, "region")
    confidence = _get_val(condition, "confidence") or default_confidence
    timeout = float(_get_val(condition, "timeout") or 10.0)
    after_found = float(_get_val(condition, "after_found") or 0.0)

    try:
        poll_until_found(
            template_path=img_path,
            timeout=timeout,
            confidence=confidence,
            controller=controller,
            after_found=after_found,
            region=region,
            step_id=step_id,
            step_label=f"{step_label or ''} [{label}]",
            row_number=row_number,
        )
    except StepFailure as e:
        raise StepFailure(
            message=f'{label} image "{os.path.basename(img_path)}" check failed: {e.message}',
            step_id=step_id,
            step_label=step_label,
            row_number=row_number,
            best_match=e.best_match,
        ) from e


def execute_action(
    action: Any,
    row_data: dict[str, object] | None = None,
    controller: ExecutionController | None = None,
    speed: SpeedMode = SpeedMode.NORMAL,
    default_wait_before: float = 0.2,
    default_confidence: float = 0.95,
    package_dir: str | None = None,
    row_number: int | None = None,
) -> None:
    """Execute a single action following Section 9.2 lifecycle."""
    enabled = _get_val(action, "enabled", True)
    if not enabled:
        return

    act_type = _get_val(action, "type")

    # Section 7.8: Groups are organization containers without timing or Guard/Verify
    if act_type == "group":
        items = _get_val(action, "items") or []
        for child in items:
            execute_action(
                child,
                row_data=row_data,
                controller=controller,
                speed=speed,
                default_wait_before=default_wait_before,
                default_confidence=default_confidence,
                package_dir=package_dir,
                row_number=row_number,
            )
        return

    step_id = _get_val(action, "id", "")
    note = _get_val(action, "note", "")
    step_label = note or f"{act_type} ({step_id})"

    # 1. Action boundary (Pause / Step-by-step)
    if controller:
        controller.wait_action_boundary(row_number)

    # 2. Timing: wait_before + speed_extra
    act_wait_before = _get_val(action, "wait_before")
    delay = calculate_action_delay(act_wait_before, default_wait_before, speed)
    if delay > 0:
        if controller:
            controller.wait(delay, row_number)
        else:
            time.sleep(delay)

    # 3. Guard (for non-image actions)
    guard = _get_val(action, "guard")
    if guard and act_type not in ("click_image", "wait_image", "wait_image_gone"):
        execute_guard_or_verify(
            guard, "Guard", package_dir, controller, default_confidence, step_id, step_label, row_number
        )

    # 4. Action Execution
    if act_type == "click":
        x = int(_get_val(action, "x", 0))
        y = int(_get_val(action, "y", 0))
        btn = _get_val(action, "button", "left")
        clicks = int(_get_val(action, "clicks", 1))
        click_at(x, y, button=btn, clicks=clicks)

    elif act_type == "click_image":
        img_rel = _get_val(action, "image")
        img_path = _resolve_image_path(package_dir, img_rel)
        region = _get_val(action, "region")
        confidence = _get_val(action, "confidence") or default_confidence
        timeout = float(_get_val(action, "timeout") or 10.0)
        after_found = float(_get_val(action, "after_found") or 0.0)
        offset_x = int(_get_val(action, "offset_x") or 0)
        offset_y = int(_get_val(action, "offset_y") or 0)
        btn = _get_val(action, "button", "left")
        clicks = int(_get_val(action, "clicks", 1))

        res = poll_until_found(
            template_path=img_path,
            timeout=timeout,
            confidence=confidence,
            controller=controller,
            after_found=after_found,
            region=region,
            step_id=step_id,
            step_label=step_label,
            row_number=row_number,
        )
        target_x = res.center_x + offset_x
        target_y = res.center_y + offset_y
        click_at(target_x, target_y, button=btn, clicks=clicks)

    elif act_type == "type_text":
        raw_text = str(_get_val(action, "text", ""))
        text_to_type = substitute_variables(raw_text, row_data or {}, strict=True)
        mode = _get_val(action, "mode", "paste").lower()
        select_all = bool(_get_val(action, "select_all_first", False))

        if select_all:
            press_keys("ctrl+a")
            if controller:
                controller.wait(0.04, row_number)
            else:
                time.sleep(0.04)

        if mode == "keystrokes":
            type_unicode_string(text_to_type)
        else:
            with temporary_clipboard_text(text_to_type, restore=True):
                press_keys("ctrl+v")
                if controller:
                    controller.wait(0.05, row_number)
                else:
                    time.sleep(0.05)

    elif act_type == "key":
        keys_str = str(_get_val(action, "keys", ""))
        repeat = int(_get_val(action, "repeat", 1))
        press_keys(keys_str, repeat=repeat)

    elif act_type == "wait":
        secs = float(_get_val(action, "seconds", 1.0))
        # Wait action explicit seconds is not affected by speed_extra
        if controller:
            controller.wait(secs, row_number)
        else:
            time.sleep(secs)

    elif act_type == "wait_image":
        img_rel = _get_val(action, "image")
        img_path = _resolve_image_path(package_dir, img_rel)
        region = _get_val(action, "region")
        confidence = _get_val(action, "confidence") or default_confidence
        timeout = float(_get_val(action, "timeout") or 10.0)
        after_found = float(_get_val(action, "after_found") or 0.0)
        stable_for = float(_get_val(action, "stable_for") or 0.0)

        poll_until_found(
            template_path=img_path,
            timeout=timeout,
            confidence=confidence,
            controller=controller,
            after_found=after_found,
            stable_for=stable_for,
            region=region,
            step_id=step_id,
            step_label=step_label,
            row_number=row_number,
        )

    elif act_type == "wait_image_gone":
        img_rel = _get_val(action, "image")
        img_path = _resolve_image_path(package_dir, img_rel)
        region = _get_val(action, "region")
        confidence = _get_val(action, "confidence") or default_confidence
        timeout = float(_get_val(action, "timeout") or 30.0)
        appear_grace = float(_get_val(action, "appear_grace") or 0.0)
        after_gone = float(_get_val(action, "after_gone") or 0.0)

        poll_until_disappears(
            template_path=img_path,
            timeout=timeout,
            confidence=confidence,
            controller=controller,
            appear_grace=appear_grace,
            after_gone=after_gone,
            region=region,
            step_id=step_id,
            step_label=step_label,
            row_number=row_number,
        )

    # 5. Verify (for non-image actions)
    verify = _get_val(action, "verify")
    if verify and act_type not in ("click_image", "wait_image", "wait_image_gone"):
        execute_guard_or_verify(
            verify, "Verify", package_dir, controller, default_confidence, step_id, step_label, row_number
        )
