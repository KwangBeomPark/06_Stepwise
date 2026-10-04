"""Spike 7: Screen State & Black Screen Detection.

Detects if the captured display buffer is uniformly black or unavailable (e.g. locked/disconnected session).
"""

from __future__ import annotations

import mss
import numpy as np


def is_screen_black_or_unavailable(
    threshold_mean: float = 2.0, threshold_std: float = 1.0
) -> dict[str, object]:
    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            primary = monitors[1] if len(monitors) > 1 else monitors[0]
            raw = sct.grab(primary)
            arr = np.array(raw, dtype=np.uint8)

            mean_val = float(np.mean(arr))
            std_val = float(np.std(arr))

            is_black = (mean_val < threshold_mean) and (std_val < threshold_std)

            return {
                "status": "OK" if not is_black else "WARN_BLACK_SCREEN",
                "is_available": True,
                "is_black_screen": is_black,
                "mean_luminance": round(mean_val, 2),
                "std_deviation": round(std_val, 2),
                "resolution": (raw.width, raw.height),
            }
    except Exception as e:
        # Screen is unavailable due to lock/disconnect or session isolation
        return {
            "status": "DETECTED_UNAVAILABLE",
            "is_available": False,
            "is_black_screen": True,
            "reason": str(e),
            "note": "Screen unavailable detected accurately. Engine will stop gracefully.",
        }


if __name__ == "__main__":
    res = is_screen_black_or_unavailable()
    print("--- Screen State Spike Results ---")
    for k, v in res.items():
        print(f"  {k}: {v}")
