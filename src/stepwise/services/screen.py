"""Screen capture, DPI inquiry, and session availability detection.

Uses mss for high-performance grab and detects black screens/session lockouts.
"""

from __future__ import annotations

import ctypes
from collections.abc import Sequence
from ctypes import wintypes

import mss
import numpy as np

from stepwise.engine.errors import ScreenUnavailableError

user32 = ctypes.windll.user32
shcore = getattr(ctypes.windll, "shcore", None)


def get_screen_info() -> dict[str, int]:
    """Retrieve primary monitor resolution, scale percentage, and monitor count."""
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

    w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    mon_count = user32.GetSystemMetrics(80)  # SM_CMONITORS

    scale_percent = 100
    try:
        if hasattr(user32, "GetDpiForSystem"):
            dpi = user32.GetDpiForSystem()
            scale_percent = int(round((dpi / 96.0) * 100))
        elif shcore and hasattr(shcore, "GetDpiForMonitor"):
            point = wintypes.POINT(0, 0)
            h_mon = user32.MonitorFromPoint(point, 1)  # MONITOR_DEFAULTTOPRIMARY
            dpi_x = wintypes.UINT()
            dpi_y = wintypes.UINT()
            if shcore.GetDpiForMonitor(h_mon, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                scale_percent = int(round((dpi_x.value / 96.0) * 100))
    except Exception:
        pass

    return {
        "width": w if w > 0 else 1920,
        "height": h if h > 0 else 1080,
        "scale_percent": scale_percent,
        "monitor_count": mon_count if mon_count > 0 else 1,
    }


def capture_screen(
    region: Sequence[int] | None = None,
    check_black_screen: bool = True,
) -> np.ndarray:
    """Capture screen or region as numpy array (BGRA).

    - region: [x, y, w, h] in physical pixels. If None, primary monitor is captured.
    - Raises ScreenUnavailableError if capture fails or screen is pitch black.
    """
    try:
        mss_cls = getattr(mss, "MSS", mss.mss)
        with mss_cls() as sct:
            monitors = sct.monitors
            primary = monitors[1] if len(monitors) > 1 else monitors[0]

            if region is not None:
                rx, ry, rw, rh = region
                bbox = {
                    "left": primary["left"] + rx,
                    "top": primary["top"] + ry,
                    "width": max(1, rw),
                    "height": max(1, rh),
                }
            else:
                bbox = primary

            raw = sct.grab(bbox)
            frame = np.array(raw, dtype=np.uint8)

            if check_black_screen:
                # Detect pitch black / blank buffer (e.g. locked session)
                mean_lum = float(np.mean(frame))
                std_lum = float(np.std(frame))
                if mean_lum < 1.0 and std_lum < 0.5:
                    raise ScreenUnavailableError(
                        "Screen is pitch black (session may be locked, minimized, or disconnected)."
                    )

            return frame
    except ScreenUnavailableError:
        raise
    except Exception as e:
        raise ScreenUnavailableError(
            f"Screen capture failed (session may be disconnected or desktop is non-interactive): {e}"
        ) from e
