# IT Security Whitelist Request — Stepwise Macro Automation

This document provides corporate IT and Cyber Security teams with technical specifications and security assurances for the deployment of **Stepwise** on employee workstations and Azure Cloud PCs.

---

## 1. Application Overview

| Item | Details |
|---|---|
| **Application Name** | Stepwise |
| **Version** | 0.1.0 |
| **Vendor / Developer** | Internal Operations Automation Team |
| **Purpose** | Automate repetitive data entry from Excel/CSV tables into internal ERP (e.g. SAP GUI) and internal web portals |
| **Runtime Architecture** | Standalone Python 3 (PyInstaller onedir bundle) compiled for Windows x64 |

---

## 2. Installation & Privilege Requirements

- **Privilege Level**: **Standard User (Non-Admin)**. Stepwise runs entirely in user-space and does **not** require elevation or local Administrator rights.
- **Installation Directory**: `%LOCALAPPDATA%\Programs\Stepwise\`
- **User Data & Settings**: `<writable app folder>\UserSetting\settings.json`; source/fallback uses `%LOCALAPPDATA%\Programs\Stepwise\UserSetting`.
- **Run Results**: `UserSetting\results` by default, or the configured results folder. Results CSV and failure screenshots are diagnostic records; no separate app log file is currently written.
- **Registry Changes**: Only creates `.swm` file association in `HKEY_CURRENT_USER\Software\Classes\` (No HKLM modifications).

---

## 3. Security & Compliance Safeguards

### 1) No Storage of Passwords or Credentials
- Stepwise strictly prohibits storing passwords or credentials in macro files.
- Session authentication (SAP/ERP login) is completed by the user prior to running data macros.

### 2) Non-Destructive Source Data Policy
- Stepwise **never** modifies or writes back to the source Excel (`.xlsx`) or CSV files.
- Execution logs and status tracking are stored in a dedicated local results folder (`%USERPROFILE%\Documents\Stepwise\Results\`).

### 3) System Interaction Boundaries
- **Mouse & Keyboard Simulation**: Uses standard Win32 `SendInput` APIs. Subject to Windows User Interface Privilege Isolation (UIPI).
- **Screen Reading**: Uses GDI `BitBlt` and OpenCV normalized cross-correlation for UI pattern verification.
- **Network Access**: Stepwise does **not** make outbound internet connections or upload telemetry to external cloud servers. All macro execution and matching occur 100% locally.

### 4) Emergency Control
- Global emergency stop shortcut (**F12**) registered via `RegisterHotKey` terminates automation instantly with zero latency.
- Image match timeouts halt execution immediately (no uncontrolled loops or double-clicks).

---

## 4. Antivirus & EDR Whitelist Information

For organizations with strict EDR/AppLocker/WDAC application control policies, please allow:

- **Folder Path**: `%LOCALAPPDATA%\Programs\Stepwise\*`
- **Main Executable**: `%LOCALAPPDATA%\Programs\Stepwise\Stepwise.exe`
- **File Extensions**: `.swm` (Stepwise Macro ZIP archive)
