# Stepwise M0 Environment Spike Tools

This directory contains standalone spike scripts to verify key Windows system capabilities before running the full Stepwise application, specifically designed for testing on Azure Cloud PCs and local enterprise environments.

---

## Quick Execution

To run all spikes and generate the Markdown report in `docs/m0-report.md`:

```cmd
.venv\Scripts\python -m tools.spike.run_all_spikes
```

Or run individual scripts:

```cmd
# 1. DPI and resolution scaling
.venv\Scripts\python -m tools.spike.spike_dpi

# 2. Mouse SendInput coordinate movement
.venv\Scripts\python -m tools.spike.spike_click

# 3. mss capture and OpenCV matchTemplate latency
.venv\Scripts\python -m tools.spike.spike_capture_match

# 4. Clipboard paste and SendInput Unicode keystrokes
.venv\Scripts\python -m tools.spike.spike_input_text

# 5. Global Hotkey (F12) registration
.venv\Scripts\python -m tools.spike.spike_hotkey

# 6. Black screen / session disconnect detection
.venv\Scripts\python -m tools.spike.spike_screen_state

# 7. Window Display Affinity (capture exclusion)
.venv\Scripts\python -m tools.spike.spike_display_affinity

# 8. User execution context (standard vs. admin)
.venv\Scripts\python -m tools.spike.spike_admin_check
```

---

## Cloud PC Manual Test Checklist
When testing on a new remote Cloud PC (Azure Virtual Desktop / RDP):
1. **Resolution & Scaling**: Confirm scale percentage matches Windows Settings display scale.
2. **Clipboard Redirection**: Check if clipboard copy/paste works across the remote session. If blocked by Group Policy, ensure `type_mode` is set to `keystrokes`.
3. **F12 Key Forwarding**: Confirm F12 hotkey is passed directly to the remote session and not swallowed by the client shell.
