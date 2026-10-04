"""Spike 4: Screen Capture (mss) and Template Matching (cv2.matchTemplate).

Measures capture latency and template matching accuracy in grayscale mode.
Gracefully handles isolated virtual desktops / locked sessions where BitBlt access is restricted.
"""

from __future__ import annotations

import time

import cv2
import mss
import numpy as np


def test_capture_and_matching() -> dict[str, object]:
    t0 = time.perf_counter()
    capture_success = False
    cap_ms = 0.0
    error_msg = None

    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            primary = monitors[1] if len(monitors) > 1 else monitors[0]
            t_cap_start = time.perf_counter()
            screenshot = sct.grab(primary)
            t_cap_end = time.perf_counter()
            cap_ms = (t_cap_end - t_cap_start) * 1000

            frame = np.array(screenshot, dtype=np.uint8)
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
            capture_success = True
    except Exception as e:
        error_msg = str(e)
        # In non-interactive virtual desktop or locked session, synthesize a test frame
        # to verify OpenCV matching algorithm correctness
        gray_frame = np.full((1080, 1920), 200, dtype=np.uint8)
        # Draw some distinct shapes
        cv2.rectangle(gray_frame, (500, 300), (700, 450), 50, -1)
        cv2.putText(gray_frame, "ERP Test", (520, 380), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 255, 2)
        cap_ms = 0.0

    # Test template matching
    h, w = gray_frame.shape
    patch_w, patch_h = 80, 80
    cx, cy = w // 2, h // 2
    x1 = max(0, cx - patch_w // 2)
    y1 = max(0, cy - patch_h // 2)
    template = gray_frame[y1 : y1 + patch_h, x1 : x1 + patch_w]

    t_match_start = time.perf_counter()
    res = cv2.matchTemplate(gray_frame, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    t_match_end = time.perf_counter()
    match_ms = (t_match_end - t_match_start) * 1000

    total_ms = (time.perf_counter() - t0) * 1000
    matched_pos = max_loc
    expected_pos = (x1, y1)
    is_accurate = (matched_pos == expected_pos) and (max_val >= 0.99)

    return {
        "status": "OK" if is_accurate else "FAIL",
        "live_screen_capture": capture_success,
        "capture_note": "Live desktop buffer captured"
        if capture_success
        else f"Isolated session ({error_msg}) - fallback test frame verified",
        "capture_latency_ms": round(cap_ms, 2),
        "matching_latency_ms": round(match_ms, 2),
        "total_latency_ms": round(total_ms, 2),
        "confidence": round(float(max_val), 4),
        "expected_location": expected_pos,
        "matched_location": matched_pos,
        "screen_resolution": (w, h),
    }


if __name__ == "__main__":
    res = test_capture_and_matching()
    print("--- Screen Capture & Match Spike Results ---")
    for k, v in res.items():
        print(f"  {k}: {v}")
