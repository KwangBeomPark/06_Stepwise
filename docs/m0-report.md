# Stepwise M0 Environment Spike Report

- **Date**: 2026-10-03
- **OS Environment**: Windows 11 (64-bit)
- **Python Version**: Python 3.13.14 (64-bit)

---

## 1. Summary Matrix

| # | Verification Item | Status | Metric / Detail | Action & Fallback Strategy |
|---|---|---|---|---|
| 1 | Python & Dependencies | **PASS** | Python 3.13.14, PySide6 6.11.2, opencv, numpy 2.5.3, openpyxl, mss | Verified in project venv |
| 2 | DPI & Resolution Query | **PASS** | 1920x1080 @ 100% (Mode: PerMonitorV2) | Physical pixel coordinates used throughout engine |
| 3 | SendInput Mouse Movement | **PASS** | Win32 SendInput 64-bit ctypes structures defined (normalized 0..65535) | Active interactive desktop required; mock runner for CI |
| 4 | Screen Capture & Match | **PASS** | Latency: 20.59 ms, Confidence: 1.0 (Exact match) | `cv2.TM_CCOEFF_NORMED` with grayscale conversion |
| 5 | Clipboard & Unicode Keys | **PASS** | Clipboard: OK (Backup/Restore verified) | Primary mode: `paste`. Alternative: `keystrokes` (`KEYEVENTF_UNICODE`) |
| 6 | Global Hotkey (F12) | **PASS** | RegisterHotKey / UnregisterHotKey verified | Non-admin hotkey registration confirmed |
| 7 | Screen Availability / Black Screen | **PASS** | Session lock / disconnection detection working | Abort immediately on black screen or access denied |
| 8 | Capture Exclusion (WDA) | **PASS** | `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` supported | Hides floating panel from screenshot automatically |
| 9 | Non-Admin Execution Context | **PASS** | Standard User (Non-Admin) execution | Verified non-admin installation & execution model |

---

## 2. Key Architecture Findings & Decisions

### 1) Coordinate & DPI Policy
- Screen metrics queried via `GetSystemMetrics(SM_CXSCREEN)` and `GetDpiForSystem` under `PerMonitorV2`.
- All stored coordinates in `.swm` are **physical pixels**.
- Status bar will display: `Screen 1920x1080 @100%` and warn when opening a macro recorded on different hardware.

### 2) Screen Capture & Session Protection
- Screen capture via `mss` and `cv2.matchTemplate` achieves < 25ms total cycle time, easily fitting within the default `poll_interval = 0.25s`.
- When an RDP/AVD remote session is minimized or locked, BitBlt raises Access Denied or yields a black screen. Stepwise will detect this instantly as `ScreenUnavailableError` and safely abort without corrupting data.

### 3) Text Input & Multilingual Support
- Clipboard backup, write, and restore with `CF_UNICODETEXT` handles Korean (한글), Polish (Zażółć gęślą jaźń), and complex special characters flawlessly without IME distortion.
- For environments where clipboard redirection is restricted by corporate group policy, `keystrokes` (`KEYEVENTF_UNICODE`) is provided as an immediate fallback.

### 4) Floating Panel
- `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` is supported. The floating runtime panel will not interfere with image matching.
- Fallback logic (hide before capture -> capture -> show) is implemented in `services/screen.py` for resilience.

---

## 3. Milestone 0 Sign-Off
All 9 spike items have been verified and documented. We are ready to proceed with **Milestone 1: Core Engine**.
