# Stepwise

**Data-Driven Macro Automation for Windows Enterprise Environments**

Stepwise is a reliable, enterprise-friendly Windows desktop tool designed to automate repetitive data entry into legacy ERP systems (e.g. SAP GUI), internal web portals, and desktop applications using Excel and CSV tables.

---

## Key Features

- **3-Section Structure**: Simple, sequential execution with **Setup**, **Per Row**, and **Cleanup**.
- **Data-Driven**: Automatically iterate rows from `.xlsx` and `.csv` files, substituting values with `{ColumnName}` variables.
- **Strict Safety First**: Stops immediately on failure—no blind automatic retries or destructive double-submits.
- **Image Guard & Verify**: Confirm prerequisite states before an action and verify expected results after.
- **Smart Speed Control**: Easily throttle execution globally (`Normal`, `Slow +0.5s`, `Very Slow +1.0s`) for laggy remote environments.
- **Non-Admin Installation**: Runs cleanly from user space without requiring administrator privileges.
- **Emergency Stop (F12)**: Instant, zero-latency abort at any time during execution or waiting.
- **Resume Capability**: Resume interrupted or failed runs starting from the exact pending row using a standalone results CSV.

---

## Installation & Requirements

### System Requirements
- Windows 10 / 11 (64-bit)
- Python 3.12+ (for development)

### Quick Start (Development)
```cmd
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run Stepwise
python -m stepwise
```

Or run via the convenient script:
```cmd
run_app.bat
```

---

## Testing
Run unit and integration tests with `pytest`:
```cmd
.venv\Scripts\pytest
```

---

## Documentation
- [stepwise-dev-guide.md](stepwise-dev-guide.md): Full technical specification and architectural standards.
- [AI_CODE_MAP.md](AI_CODE_MAP.md): High-level code map and execution flow.
- [myAGENT.md](myAGENT.md): Development guidelines and enterprise coding standards.
