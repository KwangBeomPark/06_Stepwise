"""Spike 2: DPI, Resolution, and Scaling Detection.

Verifies Win32 APIs for physical resolution, virtual screen metrics, and DPI scale factors.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SM_CMONITORS = 80
MONITOR_DEFAULTTOPRIMARY = 1


def check_dpi_and_resolution() -> dict[str, object]:
    user32 = ctypes.windll.user32
    shcore = getattr(ctypes.windll, "shcore", None)

    # Set DPI awareness (Per-Monitor V2 if available)
    dpi_aware_mode = "PerMonitorV2"
    try:
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        elif shcore and hasattr(shcore, "SetProcessDpiAwareness"):
            # PROCESS_PER_MONITOR_DPI_AWARE = 2
            shcore.SetProcessDpiAwareness(2)
            dpi_aware_mode = "PerMonitor"
        else:
            user32.SetProcessDPIAware()
            dpi_aware_mode = "SystemDPIAware"
    except Exception as e:
        dpi_aware_mode = f"Fallback error: {e}"

    # Query metrics

    primary_width = user32.GetSystemMetrics(SM_CXSCREEN)
    primary_height = user32.GetSystemMetrics(SM_CYSCREEN)
    virtual_width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    virtual_height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    monitor_count = user32.GetSystemMetrics(SM_CMONITORS)

    # DPI query
    dpi_x = 96
    dpi_y = 96
    scale_percent = 100

    try:
        # Try GetDpiForSystem (Win10 1607+)
        if hasattr(user32, "GetDpiForSystem"):
            system_dpi = user32.GetDpiForSystem()
            dpi_x = dpi_y = system_dpi
            scale_percent = int(round((system_dpi / 96.0) * 100))
        elif shcore and hasattr(shcore, "GetDpiForMonitor"):
            # Primary monitor at (0, 0)
            point = wintypes.POINT(0, 0)
            h_mon = user32.MonitorFromPoint(point, MONITOR_DEFAULTTOPRIMARY)
            dpi_x_val = wintypes.UINT()
            dpi_y_val = wintypes.UINT()
            # MDT_EFFECTIVE_DPI = 0
            res = shcore.GetDpiForMonitor(
                h_mon, 0, ctypes.byref(dpi_x_val), ctypes.byref(dpi_y_val)
            )
            if res == 0:
                dpi_x = dpi_x_val.value
                dpi_y = dpi_y_val.value
                scale_percent = int(round((dpi_x / 96.0) * 100))
    except Exception as e:
        print(f"DPI query warning: {e}")

    return {
        "status": "OK" if primary_width > 0 and primary_height > 0 else "FAIL",
        "dpi_aware_mode": dpi_aware_mode,
        "primary_width": primary_width,
        "primary_height": primary_height,
        "virtual_width": virtual_width,
        "virtual_height": virtual_height,
        "monitor_count": monitor_count,
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
        "scale_percent": scale_percent,
    }


if __name__ == "__main__":
    res = check_dpi_and_resolution()
    print("--- DPI & Resolution Spike Results ---")
    for k, v in res.items():
        print(f"  {k}: {v}")
