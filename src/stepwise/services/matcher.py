"""Template matching service using OpenCV normalized cross-correlation.

Implements Section 8 specifications:
- Grayscale conversion (cv2.COLOR_BGRA2GRAY)
- cv2.TM_CCOEFF_NORMED
- Region clipping
- Precision center calculation and offset support
- Polling loops with interruptible controller and stable_for / appear_grace options.
"""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from stepwise.engine.errors import StepFailure
from stepwise.engine.timing import ExecutionController
from stepwise.services.screen import capture_screen


@dataclass
class MatchResult:
    found: bool
    confidence: float
    center_x: int
    center_y: int
    top_left_x: int
    top_left_y: int
    width: int
    height: int


def load_template_image(image_path: str) -> np.ndarray:
    """Load image from disk and return in grayscale."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Template image not found: {image_path}")

    stream = np.fromfile(image_path, dtype=np.uint8)
    img = cv2.imdecode(stream, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Failed to decode image: {image_path}")

    if len(img.shape) == 2:
        return img
    if img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def match_template_in_frame(
    frame: np.ndarray,
    template: np.ndarray,
    region: Sequence[int] | None = None,
    confidence_threshold: float = 0.95,
) -> MatchResult:
    """Match template in frame using TM_CCOEFF_NORMED.

    Returns MatchResult with physical screen coordinates.
    """
    if len(frame.shape) == 3:
        if frame.shape[2] == 4:
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        else:
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray_frame = frame

    if len(template.shape) == 3:
        if template.shape[2] == 4:
            gray_template = cv2.cvtColor(template, cv2.COLOR_BGRA2GRAY)
        else:
            gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    else:
        gray_template = template

    th, tw = gray_template.shape[:2]

    # Guard against uniform blank/solid templates where standard deviation is zero
    if np.std(gray_template) < 1e-4:
        return MatchResult(
            found=False,
            confidence=0.0,
            center_x=0,
            center_y=0,
            top_left_x=0,
            top_left_y=0,
            width=tw,
            height=th,
        )

    offset_x, offset_y = 0, 0
    if region is not None:
        rx, ry, rw, rh = region
        h_f, w_f = gray_frame.shape
        x1 = max(0, min(rx, w_f - 1))
        y1 = max(0, min(ry, h_f - 1))
        x2 = max(x1 + 1, min(rx + rw, w_f))
        y2 = max(y1 + 1, min(ry + rh, h_f))
        gray_frame = gray_frame[y1:y2, x1:x2]
        offset_x, offset_y = x1, y1

    fh, fw = gray_frame.shape[:2]

    if tw > fw or th > fh:
        # Template is larger than search area
        return MatchResult(
            found=False,
            confidence=0.0,
            center_x=0,
            center_y=0,
            top_left_x=0,
            top_left_y=0,
            width=tw,
            height=th,
        )

    res = cv2.matchTemplate(gray_frame, gray_template, cv2.TM_CCOEFF_NORMED)
    # Replace any NaNs with 0.0
    res = np.nan_to_num(res, nan=0.0)

    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    best_conf = float(max_val)
    best_x = max_loc[0] + offset_x
    best_y = max_loc[1] + offset_y
    center_x = best_x + tw // 2
    center_y = best_y + th // 2
    is_found = best_conf >= confidence_threshold

    return MatchResult(
        found=is_found,
        confidence=best_conf,
        center_x=center_x,
        center_y=center_y,
        top_left_x=best_x,
        top_left_y=best_y,
        width=tw,
        height=th,
    )


def poll_until_found(
    template_path: str,
    timeout: float = 10.0,
    confidence: float = 0.95,
    poll_interval: float = 0.25,
    controller: ExecutionController | None = None,
    after_found: float = 0.0,
    stable_for: float = 0.0,
    region: Sequence[int] | None = None,
    step_id: str | None = None,
    step_label: str | None = None,
    row_number: int | None = None,
) -> MatchResult:
    """Poll screen until template is found or timeout expires."""
    template = load_template_image(template_path)
    deadline = time.time() + timeout
    best_seen_match = 0.0
    last_res: MatchResult | None = None
    stable_since: float | None = None

    while True:
        if controller:
            controller.check_abort(row_number)

        frame = capture_screen(region=region)
        res = match_template_in_frame(frame, template, region=region, confidence_threshold=confidence)
        last_res = res
        if res.confidence > best_seen_match:
            best_seen_match = res.confidence

        now = time.time()
        if res.found:
            if stable_for > 0:
                if stable_since is None:
                    stable_since = now
                elif (now - stable_since) >= stable_for:
                    break
            else:
                break
        else:
            stable_since = None

        if now >= deadline:
            raise StepFailure(
                message=f'Image "{os.path.basename(template_path)}" not found within {int(timeout)} s',
                step_id=step_id,
                step_label=step_label,
                row_number=row_number,
                best_match=best_seen_match,
            )

        sleep_time = min(poll_interval, max(0.01, deadline - now))
        if controller:
            controller.wait(sleep_time, row_number)
        else:
            time.sleep(sleep_time)

    if after_found > 0:
        if controller:
            controller.wait(after_found, row_number)
        else:
            time.sleep(after_found)

    return last_res  # type: ignore


def poll_until_disappears(
    template_path: str,
    timeout: float = 30.0,
    confidence: float = 0.95,
    poll_interval: float = 0.25,
    controller: ExecutionController | None = None,
    appear_grace: float = 0.0,
    after_gone: float = 0.0,
    region: Sequence[int] | None = None,
    step_id: str | None = None,
    step_label: str | None = None,
    row_number: int | None = None,
) -> None:
    """Poll screen until template is no longer found."""
    template = load_template_image(template_path)
    now = time.time()
    grace_deadline = now + appear_grace
    has_appeared = False

    while time.time() <= grace_deadline:
        if controller:
            controller.check_abort(row_number)
        frame = capture_screen(region=region)
        res = match_template_in_frame(frame, template, region=region, confidence_threshold=confidence)
        if res.found:
            has_appeared = True
            break
        if controller:
            controller.wait(min(poll_interval, 0.1), row_number)
        else:
            time.sleep(min(poll_interval, 0.1))

    if appear_grace == 0.0 and not has_appeared:
        frame = capture_screen(region=region)
        res = match_template_in_frame(frame, template, region=region, confidence_threshold=confidence)
        if not res.found:
            if after_gone > 0:
                if controller:
                    controller.wait(after_gone, row_number)
                else:
                    time.sleep(after_gone)
            return

    deadline = time.time() + timeout
    best_seen_match = 1.0
    while True:
        if controller:
            controller.check_abort(row_number)
        frame = capture_screen(region=region)
        res = match_template_in_frame(frame, template, region=region, confidence_threshold=confidence)
        best_seen_match = res.confidence

        if not res.found:
            break

        now = time.time()
        if now >= deadline:
            raise StepFailure(
                message=f'Image "{os.path.basename(template_path)}" did not disappear within {int(timeout)} s',
                step_id=step_id,
                step_label=step_label,
                row_number=row_number,
                best_match=best_seen_match,
            )

        sleep_time = min(poll_interval, max(0.01, deadline - now))
        if controller:
            controller.wait(sleep_time, row_number)
        else:
            time.sleep(sleep_time)

    if after_gone > 0:
        if controller:
            controller.wait(after_gone, row_number)
        else:
            time.sleep(after_gone)
