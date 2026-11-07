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
from stepwise.engine.errors import AbortRequested, StepFailure
from stepwise.engine.timing import ExecutionController, SpeedMode, calculate_action_delay
from stepwise.services.clipboard import temporary_clipboard_text
from stepwise.services.input_win import (
    click_at,
    press_keys,
    release_all_modifiers,
    type_unicode_string,
)
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
            guard,
            "Guard",
            package_dir,
            controller,
            default_confidence,
            step_id,
            step_label,
            row_number,
        )

    # 4. Action Execution
    if act_type == "click":
        x = int(_get_val(action, "x", 0))
        y = int(_get_val(action, "y", 0))
        btn = _get_val(action, "button", "left")
        clicks = int(_get_val(action, "clicks", 1))
        selector = _get_val(action, "selector")
        target_mode = str(
            _get_val(action, "target_mode") or ("selector" if selector else "coordinates")
        )
        click_method = str(_get_val(action, "click_method", "hardware") or "hardware")

        target_hwnd = 0
        use_bm_click = False
        if target_mode == "selector":
            if not selector or not isinstance(selector, Mapping):
                raise StepFailure(
                    message="Target mode is UI Selector, but no valid selector is configured.",
                    step_id=step_id,
                    step_label=step_label,
                    row_number=row_number,
                )
            from stepwise.services.uia_win import resolve_selector

            try:
                elem = resolve_selector(dict(selector), row_data=row_data or {}, exclude_self=True)
            except Exception as e:
                raise StepFailure(
                    message=f"UI Selector resolution failed: {e}",
                    step_id=step_id,
                    step_label=step_label,
                    row_number=row_number,
                ) from e
            x, y = elem.target_point()
            target_hwnd = elem.hwnd
            use_bm_click = elem.control_type == "Button" and elem.hwnd != elem.root_hwnd

        if click_method == "simulate":
            from stepwise.services.uia_win import (
                get_class_name,
                infer_control_type,
                simulate_click_at_hwnd,
                user32,
                wintypes,
            )

            if not target_hwnd:
                pt = wintypes.POINT(x, y)
                target_hwnd = int(user32.WindowFromPoint(pt) or 0)
                if not target_hwnd:
                    raise StepFailure(
                        message=f"No target window found at ({x}, {y}) for Simulate Click.",
                        step_id=step_id,
                        step_label=step_label,
                        row_number=row_number,
                    )
                use_bm_click = infer_control_type(target_hwnd, get_class_name(target_hwnd)) == "Button"

            ok_sim, sim_err = simulate_click_at_hwnd(
                hwnd=target_hwnd,
                screen_x=x,
                screen_y=y,
                button=btn,
                clicks=clicks,
                use_bm_click=use_bm_click,
            )
            if not ok_sim:
                raise StepFailure(
                    message=f"Simulate Click failed: {sim_err}",
                    step_id=step_id,
                    step_label=step_label,
                    row_number=row_number,
                )
        else:
            if not click_at(x, y, button=btn, clicks=clicks):
                raise StepFailure(
                    message="The mouse could not reach or click the target. Check the screen coordinates and application permissions.",
                    step_id=step_id,
                    step_label=step_label,
                    row_number=row_number,
                )

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
        if not click_at(target_x, target_y, button=btn, clicks=clicks):
            raise StepFailure(
                message="The mouse could not reach or click the matched image. Check the screen coordinates and application permissions.",
                step_id=step_id,
                step_label=step_label,
                row_number=row_number,
            )

    elif act_type == "type_text":
        raw_text = str(_get_val(action, "text", ""))
        text_to_type = substitute_variables(
            raw_text,
            row_data or {},
            strict=True,
            context={"_ROW_NUM": row_number} if row_number is not None else None,
        )
        mode = _get_val(action, "mode", "paste").lower()
        select_all = bool(_get_val(action, "select_all_first", False))

        def select_all_if_requested() -> None:
            if select_all:
                if controller:
                    ok = press_keys(
                        "ctrl+a",
                        wait_fn=controller.wait,
                        should_stop=controller.is_stopped,
                    )
                else:
                    ok = press_keys("ctrl+a")
                if not ok:
                    release_all_modifiers()
                    if controller and controller.is_stopped():
                        raise AbortRequested("Execution stopped by user during select all.")
                    raise StepFailure(
                        message="Failed to send 'Ctrl+A' select-all keystroke. Check application permissions.",
                        step_id=step_id,
                        step_label=step_label,
                        row_number=row_number,
                    )
                if controller:
                    controller.wait(0.04, row_number)
                else:
                    time.sleep(0.04)

        if mode == "keystrokes":
            select_all_if_requested()
            if controller:
                ok = type_unicode_string(
                    text_to_type,
                    wait_fn=controller.wait,
                    should_stop=controller.is_stopped,
                )
            else:
                ok = type_unicode_string(text_to_type)
            if not ok:
                release_all_modifiers()
                if controller and controller.is_stopped():
                    raise AbortRequested("Execution stopped by user during typing.")
                raise StepFailure(
                    message="Failed to type unicode text. Target application may be unresponsive or running with elevated permissions.",
                    step_id=step_id,
                    step_label=step_label,
                    row_number=row_number,
                )
        else:
            with temporary_clipboard_text(text_to_type, restore=True) as written:
                if not written:
                    raise StepFailure(
                        message="Could not write text to the clipboard. Close other clipboard tools and try again.",
                        step_id=step_id,
                        step_label=step_label,
                        row_number=row_number,
                    )
                select_all_if_requested()
                if controller:
                    ok = press_keys(
                        "ctrl+v",
                        wait_fn=controller.wait,
                        should_stop=controller.is_stopped,
                    )
                else:
                    ok = press_keys("ctrl+v")
                if not ok:
                    release_all_modifiers()
                    if controller and controller.is_stopped():
                        raise AbortRequested("Execution stopped by user during paste.")
                    raise StepFailure(
                        message="Failed to send 'Ctrl+V' paste keystroke. Target application may be blocked by UIPI or running as Administrator.",
                        step_id=step_id,
                        step_label=step_label,
                        row_number=row_number,
                    )
                if controller:
                    controller.wait(0.05, row_number)
                else:
                    time.sleep(0.05)

    elif act_type == "key":
        keys_str = str(_get_val(action, "keys", ""))
        repeat = max(1, int(_get_val(action, "repeat", 1)))
        if controller:
            ok = press_keys(
                keys_str,
                repeat=repeat,
                wait_fn=controller.wait,
                should_stop=controller.is_stopped,
            )
        else:
            ok = press_keys(keys_str, repeat=repeat)
        if not ok:
            release_all_modifiers()
            if controller and controller.is_stopped():
                raise AbortRequested("Execution stopped by user during key action.")
            raise StepFailure(
                message=f"Failed to send key combination '{keys_str}'. Target window may be unresponsive or running as Administrator.",
                step_id=step_id,
                step_label=step_label,
                row_number=row_number,
            )

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

    elif act_type == "window_set_bounds":
        title_raw = str(_get_val(action, "window_title", "")).strip()
        if not title_raw:
            raise StepFailure(
                "Target window title cannot be empty. Please specify the window title to align.",
                step_id=step_id,
                step_label=step_label,
                row_number=row_number,
            )

        try:
            title = substitute_variables(
                title_raw,
                row_data or {},
                strict=True,
                context={"_ROW_NUM": row_number} if row_number is not None else None,
            )
        except Exception as e:
            raise StepFailure(
                f"Variable substitution failed in window title '{title_raw}': {e}",
                step_id=step_id,
                step_label=step_label,
                row_number=row_number,
            ) from e

        x = int(_get_val(action, "window_x", 0))
        y = int(_get_val(action, "window_y", 0))
        width = int(_get_val(action, "window_width", 1280))
        height = int(_get_val(action, "window_height", 800))
        maximize = bool(_get_val(action, "window_maximize", False))

        from stepwise.services.window_win import find_window_by_title, set_window_bounds

        hwnd = find_window_by_title(title)
        if not hwnd:
            raise StepFailure(
                f"Target window matching '{title}' was not found on screen.",
                step_id=step_id,
                step_label=step_label,
                row_number=row_number,
            )

        ok, err_msg = set_window_bounds(
            hwnd, x=x, y=y, width=width, height=height, maximize=maximize
        )
        if not ok:
            raise StepFailure(
                f"Failed to set bounds for window '{title}': {err_msg}",
                step_id=step_id,
                step_label=step_label,
                row_number=row_number,
            )

    # 5. Verify (for non-image actions)
    verify = _get_val(action, "verify")
    if verify and act_type not in ("click_image", "wait_image", "wait_image_gone"):
        execute_guard_or_verify(
            verify,
            "Verify",
            package_dir,
            controller,
            default_confidence,
            step_id,
            step_label,
            row_number,
        )
