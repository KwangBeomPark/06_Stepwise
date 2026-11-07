"""Centralized bilingual (English / Korean) UI strings for Stepwise.

All user-facing strings must be defined here rather than hardcoded in widgets.
Internal engine/schema/CSV tokens ('Done', 'Failed', 'Pending', 'Skipped', 'Interrupted')
remain strictly invariant regardless of UI display language.
"""

from __future__ import annotations

_CURRENT_LANG = "en"


class Strings:
    # Application Info
    APP_TITLE = "Stepwise"
    APP_SUBTITLE = "Data-Driven Macro Automation"

    # Toolbar
    SAVE_MACRO = "Save"
    RUN = "Run"
    PAUSE = "Pause"
    RESUME = "Resume"
    STOP = "Stop"
    SCHEDULE = "Schedule"
    STEP_BY_STEP = "Step-by-step"
    DATA_FILE = "Data:"
    NO_DATA = "No data connected"
    SETTINGS = "Settings"
    THEME_DARK = "🌙 Dark"
    THEME_LIGHT = "☀️ Light"
    LANG_KO = "🇰🇷 한국어"
    LANG_EN = "🇺🇸 EN"
    SETTINGS_SAVE_FAILED = "Settings were not saved. Check folder permissions and available disk space, then try again."
    OPEN_SETTINGS_FOLDER = "Open Settings Folder"
    OPEN_RESULTS_FOLDER = "Open Results Folder"
    BACKUP_SCOPE = "Back up the settings folder and your macro library. Include results if needed. Custom folders and source data must be backed up separately."
    FOLDER_OPEN_FAILED = "The folder could not be opened. Check that it exists and you have permission to access it."

    RUN_ERROR_TITLE = "Run Cancelled"
    SNAPSHOT_ERROR = "The run could not be prepared. Try again.\n{error}"
    F12_ERROR = (
        "The run was cancelled because the F12 emergency stop key is unavailable. "
        "Close any application using F12 and try again.\n{error}"
    )
    RUN_START_ERROR = "The run could not be started. Try again.\n{error}"
    SAVE_ERROR_TITLE = "Save Failed"
    CAPTURE_ERROR_TITLE = "Capture Failed"
    CAPTURE_ERROR = (
        "The captured image could not be saved. Check available disk space and try again.\n{error}"
    )
    SAVE_ERROR = (
        "The macro could not be saved. Check the destination and referenced images.\n{error}"
    )
    RESULTS_WARNING = (
        "Some results were saved to a pending journal because the results CSV was unavailable."
    )
    EXPORT_BUFFERED_RESULTS = "Export Buffered Results"
    RESULTS_MEMORY_WARNING = (
        "Some results could not be saved to disk and are retained in memory. "
        "Keep this window open and export the buffered results."
    )

    # Sections
    SECTION_SETUP = "① SETUP (runs once at start)"
    SECTION_PER_ROW = "② PER ROW (repeats for each row)"
    SECTION_CLEANUP = "③ CLEANUP (runs once at end, optional)"
    SECTION_EMPTY_PLACEHOLDER = "(Empty — select to add action here)"
    SECTION_SETUP_EMPTY = "(Empty — window alignment, login, etc. Optional)"
    SECTION_PER_ROW_EMPTY = "(Empty — click, type a [Column] value, save for each data row)"
    SECTION_CLEANUP_EMPTY = "(Empty — close screen, logout, etc. Optional)"
    INSERT_TARGET_TOP = "Add target: [{section}] at beginning"
    INSERT_TARGET_AFTER = "Add target: [{section}] after Step #{step}"
    INSERT_TARGET_GROUP = 'Add target: [{section}] after group "{group}"'
    INSERT_TARGET_END = "Add target: [{section}] at end"
    MOVE_BOUNDARY_TOP = (
        "Already at top of section or group. Use 'Move to Section' to change section."
    )
    MOVE_BOUNDARY_BOTTOM = (
        "Already at bottom of section or group. Use 'Move to Section' to change section."
    )

    # Action Types
    TYPE_CLICK = "Click"
    TYPE_CLICK_IMAGE = "Click image"
    TYPE_TYPE_TEXT = "Type text"
    TYPE_KEY = "Key press"
    TYPE_WAIT = "Wait"
    TYPE_WAIT_IMAGE = "Wait for image"
    TYPE_WAIT_IMAGE_GONE = "Wait until image disappears"
    TYPE_GROUP = "Group"

    # Tree Headers
    COL_NUM = "#"
    COL_ENABLED = "✓"
    COL_ACTION = "Action"
    COL_TARGET = "Target"
    COL_WAIT = "Wait"
    COL_CHECK = "Check"
    COL_NOTE = "Note"

    # Action Buttons
    ADD_ACTION_LABEL = "Add Action:"
    ADD_ACTION = "+ Add action"
    BTN_ADD_CLICK = "👆 + Click"
    BTN_ADD_TYPE = "⌨ + Type"
    BTN_ADD_KEY = "↵ + Key"
    BTN_ADD_WAIT = "⏱ + Wait"
    BTN_ADD_WIN = "🪟 + Window"
    MOVE_UP = "↑ Move Up"
    MOVE_DOWN = "↓ Move Down"
    DUPLICATE = "Duplicate"
    DELETE = "Delete"
    GROUP = "Group"
    UNGROUP = "Ungroup"

    # Search & Filter
    SEARCH_ACTIONS = "Search actions..."
    FILTER_ALL = "All actions"
    FILTER_GUARD_VERIFY_ONLY = "With Guard/Verify only"
    FILTER_DISABLED_ONLY = "Disabled actions only"
    FILTER_VARIABLES_ONLY = "Using variables only"
    COMPACT_VIEW = "Compact view"

    # Properties Panel
    PROPERTIES_TITLE = "Properties"
    GENERAL_OPTIONS = "General Options"
    ACTION_ENABLED = "Action Enabled"
    NO_ACTION_SELECTED = "Select an action in the tree to view and edit its properties."
    PROPERTIES_GUIDE = (
        "<b>💡 Quick Start Guide:</b><br><br>"
        "1. Click <b>[+ Click]</b> or <b>[+ Type]</b> below the Action Tree.<br>"
        "2. Select the added step in the tree to configure coordinates, UI Selector, or text.<br>"
        "3. Use <b>[Pick (F8)]</b> to capture screen coordinates or <b>[🎯 Pick UI Element]</b> for UI Selector.<br>"
        "4. Load an Excel/CSV file in <b>Data Preview</b>, then click a <b>[Column]</b> chip to insert its value."
    )
    COORD_X = "X coordinate:"
    COORD_Y = "Y coordinate:"
    COORDINATES_LABEL = "Coordinates:"
    ACTION_TOOLS_LABEL = "Action Tools:"
    BUTTON = "Mouse button:"
    CLICKS = "Clicks:"
    TEXT_TO_TYPE = "Text to type:"
    TYPE_MODE = "Typing mode:"
    MODE_PASTE = "Paste (Clipboard, Recommended for Korean)"
    MODE_KEYSTROKES = "Keystrokes (English/Numbers)"
    SELECT_ALL_FIRST = "Select all first (Ctrl+A)"
    KEYS_TO_PRESS = "Keys to press:"
    REPEAT_COUNT = "Repeat count:"
    WAIT_SECONDS = "Wait (seconds):"
    WAIT_BEFORE = "Wait before (seconds):"
    IMAGE_PATH = "Image:"
    SEARCH_REGION = "Search region:"
    CONFIDENCE = "Confidence:"
    TIMEOUT_SEC = "Timeout (seconds):"
    AFTER_FOUND_SEC = "After found delay (seconds):"
    STABLE_FOR_SEC = "Stable for (seconds):"
    APPEAR_GRACE_SEC = "Appear grace (seconds):"
    AFTER_GONE_SEC = "After gone delay (seconds):"
    OFFSET_X = "Offset X:"
    OFFSET_Y = "Offset Y:"
    GROUP_NAME = "Group name:"
    NOTE_LABEL = "User note / memo:"

    # UI Selector & Simulate Click
    TARGET_MODE_LABEL = "Target mode:"
    TARGET_MODE_COORDS = "Screen Coordinates (X, Y)"
    TARGET_MODE_SELECTOR = "UI Element Selector (UIA / HWND)"
    CLICK_METHOD_LABEL = "Click method:"
    CLICK_METHOD_HARDWARE = "Hardware Input (SendInput)"
    CLICK_METHOD_SIMULATE = "Simulate Click (Background Invoke)"
    PICK_UI_ELEMENT = "🎯 Pick UI Element (Ctrl+F8)"
    VALIDATE_SELECTOR = "🔍 Validate & Highlight Element"
    CLEAR_SELECTOR = "Clear Selector"
    SELECTOR_SUMMARY_EMPTY = "No UI element selected. Click 'Pick UI Element' to inspect target."
    SELECTOR_WINDOW_TITLE = "Window Title:"
    SELECTOR_CONTROL_TYPE = "Control Type:"
    SELECTOR_AUTOMATION_ID = "Automation ID:"
    SELECTOR_NAME = "Element Name:"
    SELECTOR_CLASS_NAME = "Class Name:"

    # UX Nudges & Micro-interactions
    DATA_CHIP_LABEL = "Insert Column:"
    DATA_NO_FILE_NUDGE = "To insert column variables: [📂 Connect Excel / CSV File]"
    ROW_PREVIEW_PREFIX = "Row 1 Preview:"
    KOREAN_IME_NUDGE = "💡 Clipboard paste is recommended for Korean text to avoid composition glitches."
    BTN_LOCATE_TARGET = "🔍 Locate Only"
    BTN_TEST_STEP = "▶ Test Step"
    LOCATE_TARGET_ACTIVE = "Highlighting target for 1 second (no clicks will be sent)..."
    RETRY_FAILED_ROWS = "Retry Failed {count} Rows Only"
    RESUME_FROM_FAILED_ROW = "Resume from Row #{row} to End"
    F12_GENTLE_REMINDER = "You can stop safely at any time by pressing F12."
    LOOP_REPETITION_LABEL = " — {rows} rows × {steps} steps"
    BEFORE_DATA_CONNECTED = " — Before Data Connected"
    PREVIEW_EMPTY_TEXT = "(Type text in properties panel)"
    PREVIEW_NO_DATA_TEXT = "{text} (Fixed string without connected data)"
    QUICK_START_BANNER = "💡 Quick Start: ① Connect Excel data ➜ ② Add actions below ➜ ③ [▶ Run]"
    LOCATE_TOOLTIP = "Highlight target area on screen for 1.5 seconds without sending clicks."
    SUMMARY_TITLE_SUCCESS = "✓ Completed all {count} rows ({duration}s)"
    SUMMARY_TITLE_INTERRUPTED = "⚠️ Interrupted — {done} done, row #{row} stopped"
    SUMMARY_TITLE_FAILED = "⚠️ Failed at row #{row} — {done} completed"

    # Window Bounds Properties
    WINDOW_TITLE_LABEL = "Window Title:"
    WINDOW_PICK_BUTTON = "🔍 Pick Window"
    WINDOW_PICK_TOOLTIP = "Select from currently visible application windows"
    WINDOW_POS_LABEL = "Top-Left Position:"
    WINDOW_SIZE_LABEL = "Window Size:"
    WINDOW_MAXIMIZE_LABEL = "Maximize window instead of resizing"

    # Image Helper Buttons
    PICK_COORDS = "Pick (F8)"
    CAPTURE_IMAGE = "Capture (F9)"
    SHOW_ON_SCREEN = "Show on screen"
    TEST_THIS_STEP = "Test this step"
    TEST_MATCH = "Test match"
    GUARD_SECTION = "Guard (Check before action)"
    VERIFY_SECTION = "Verify (Check after action)"
    GUARD_PLACEHOLDER = "Optional Guard template image (e.g. images/form.png)"
    VERIFY_PLACEHOLDER = "Optional Verify template image (e.g. images/saved.png)"
    ENABLE_GUARD = "Enable Guard"
    ENABLE_VERIFY = "Enable Verify"

    # Data Panel
    DATA_PANEL_TITLE = "Data Preview"
    INSERT_VARIABLE_LABEL = "Insert Column Variable:"
    ROWS_LOADED = "{count} rows loaded"
    SELECT_DATA_FILE = "Choose Data File..."
    SHEET = "Sheet:"
    HEADER_ROW = "Header row:"
    ENCODING = "Encoding:"
    DELIMITER = "Delimiter:"
    STATUS_PENDING = "Pending"
    STATUS_RUNNING = "Running"
    STATUS_DONE = "Done"
    STATUS_FAILED = "Failed"
    STATUS_INTERRUPTED = "Interrupted"
    STATUS_SKIPPED = "Skipped"

    # Row Context Menu
    RETRY_ROW = "Retry this row"
    SKIP_ROW = "Skip this row"
    MARK_DONE = "Mark as Done"
    RUN_ONLY_THIS_ROW = "Run only this row"
    RESET_ALL_STATUSES = "Reset all row statuses"
    RESET_ALL_STATUSES_CONFIRM_TITLE = "Reset Row Statuses"
    RESET_ALL_STATUSES_CONFIRM_MSG = "Reset all rows back to Pending?\n(Completed rows can be executed again)"
    PREFLIGHT_EXCLUDED_BREAKDOWN = "Excluded: {count} ({done} done, {skipped} skipped)"
    PREFLIGHT_ALL_DONE_TITLE = "All Rows Completed"
    PREFLIGHT_ALL_DONE_MSG = "All rows in the selected range are already completed (Done).\nWould you like to reset row statuses and run from the beginning?"
    RESET_AND_RUN = "Reset Statuses & Run"
    PREFLIGHT_FIRST_ROW_SAMPLE = "[First row typing sample]"
    PREFLIGHT_RUN_1_ROW_TOOLTIP = "Test run only the first row to verify screen actions and results."

    # Macro Library
    LIBRARY_TITLE = "Macro Library"
    SEARCH_MACROS = "Search macros..."
    NEW_MACRO = "+ New Macro"
    DUPLICATE_MACRO = "Duplicate Macro"
    RENAME_MACRO = "Rename"
    DELETE_MACRO = "Delete"
    OPEN_FOLDER = "Open Library Folder"
    LOCKED_BY_USER = "Being edited by {user} on {machine}"
    STALE_LOCK = "Stale lock by {user} (Take over?)"

    # Task Scheduler (Armed Night-Shift Mode)
    SCHEDULER_TITLE = "Night-Shift Task Scheduler (Armed Mode)"
    SCHEDULER_SUBTITLE = "Keep Cloud PC awake and execute the macro automatically at the scheduled time."
    SCHEDULER_TARGET_TIME = "Scheduled Start Time:"
    SCHEDULER_START_ROW = "Start from row:"
    SCHEDULER_SPEED_PROFILE = "Speed Profile:"
    SCHEDULER_SPEED_NORMAL = "Normal"
    SCHEDULER_SPEED_SLOW = "Slow (+0.5s)"
    SCHEDULER_SPEED_VERY_SLOW = "Very slow (+1.0s)"
    SCHEDULER_ON_FAIL = "On Macro Failure:"
    SCHEDULER_STOP_QUEUE = "Stop immediately and save failure screenshot (Fail-Fast)"
    SCHEDULER_CONTINUE_NEXT = "Stop immediately (Fail-Fast)"
    SCHEDULER_LOCK_AFTER = "Lock Windows screen (LockWorkStation) after scheduled completion"
    SCHEDULER_RESET_STATUSES = "Reset completed rows back to Pending before execution"
    SCHEDULER_ANTI_LOCK_JIGGLER = "Hold Anti-Lock Jiggler while armed (prevents sleep & lock)"
    SCHEDULER_ANTI_LOCK_JIGGLER_TIP = "Sends an unassigned virtual key pulse every {seconds}s while waiting for scheduled launch to prevent Corporate GPO inactivity lock."
    SETTINGS_JIGGLER_GROUP = "Screen Lock Prevention (Anti-Lock Jiggler)"
    SETTINGS_JIGGLER_ENABLE = "Prevent Windows screen lock during execution & scheduling"
    SETTINGS_JIGGLER_TIP = "Periodically sends an invisible virtual key pulse (VK_F15) to keep the Windows idle timer reset, preventing GPO inactivity screen lock and RDP session disconnects."
    SETTINGS_JIGGLER_INTERVAL = "Jiggle Interval:"
    SECONDS_UNIT = "sec"
    SCHEDULER_PRE_ARM_TITLE = "Environment & Session Readiness Diagnostics"
    SCHEDULER_CHECKLIST_TITLE = "Overnight Cloud PC Safety Checklist (Required)"
    SCHEDULER_CHK_DONT_CLOSE = "I will NOT close or minimize the Cloud PC / RDP window (covering with other windows is OK)"
    SCHEDULER_CHK_POWER = "My local PC is plugged into power with sleep mode disabled"
    SCHEDULER_CHK_ERP_READY = "Target ERP/Web application is logged in and positioned on the initial screen"
    SCHEDULER_BTN_RUN_NOW = "▶ Run Immediately (Test)"
    SCHEDULER_BTN_ARM = "🛡️ Arm Night-Shift Schedule"
    SCHEDULER_BTN_DISARM = "Cancel / Disarm"
    SCHEDULER_ARMED_BANNER = "⏳ ARMED — Waiting for {time} ({remaining} remaining). Keep this window open!"
    SCHEDULER_BANNER_BLOCKING = "⚠ Resolve blocking errors above before arming."
    SCHEDULER_BANNER_READY = "✅ Ready to arm night-shift schedule."
    SCHEDULER_BANNER_CHECKLIST = "ℹ Check all 3 safety checklist items above to enable Arm."
    SCHEDULER_TAG_BLOCKING = "🔴 [BLOCKING] "
    SCHEDULER_TAG_WARN = "🟡 [WARNING] "
    SCHEDULER_TAG_READY = "🟢 [READY] "
    SCHEDULER_STALE_ABORT = "Scheduled time passed by more than 15 minutes (system may have been suspended). Execution was aborted for safety."
    SCHEDULER_REPORT_TITLE = "Overnight Schedule Execution Report"

    # Status Bar
    SCREEN_MATCH = "Screen {w}x{h} @{scale}% ✅ matches macro"
    SCREEN_MISMATCH = (
        "Screen {w}x{h} @{scale}% ⚠ differs from macro ({rec_w}x{rec_h} @{rec_scale}%)"
    )
    STATUS_READY = "Ready"

    # Auto-Update
    UPDATE_CHECK_MENU = "Check for Updates..."
    UPDATE_AUTO_CHECK_LABEL = "Check for updates automatically on startup"
    UPDATE_LAST_CHECKED = "Last checked: {time}"
    UPDATE_NEVER_CHECKED = "Never"
    UPDATE_CHECK_NOW = "Check Now"
    UPDATE_CHECKING = "Checking for updates..."
    UPDATE_UP_TO_DATE_TITLE = "Up to Date"
    UPDATE_UP_TO_DATE_MSG = "Stepwise is up to date (v{version})."
    UPDATE_AVAILABLE_TITLE = "Update Available"
    UPDATE_AVAILABLE_MSG = "A new version of Stepwise (v{version}) is available."
    UPDATE_DOWNLOAD_BTN = "Download Update"
    UPDATE_DOWNLOADING = "Downloading... {progress}% ({speed})"
    UPDATE_VERIFYING = "Verifying Authenticode signature and integrity..."
    UPDATE_READY_INSTALL_BTN = "Install and Restart"
    UPDATE_LATER_BTN = "Later"
    UPDATE_VIEW_RELEASE = "View on GitHub"
    UPDATE_BLOCKED_RUNNING = "Cannot install while macro is running. Stop macro first."
    UPDATE_BLOCKED_ARMED = "Cannot install while night scheduler is armed. Disarm scheduler first."
    UPDATE_VERIFY_FAILED = "Verification failed: {error}"
    UPDATE_DOWNLOAD_FAILED = "Download failed: {error}"
    UPDATE_RATE_LIMITED = "GitHub rate limit exceeded. Please try again later."
    UPDATE_DEV_MODE_NOTICE = "Running in development or portable mode. Direct in-place install is disabled; download the installer from GitHub."

    # Dialogs & Prompts
    CONFIRM_DELETE = "Are you sure you want to delete this action?"
    CONFIRM_DISCARD_CHANGES = "You have unsaved changes. Discard them?"
    RECOVERY_FOUND_TITLE = "Auto-Recovery Available"
    RECOVERY_FOUND_MSG = (
        "Stepwise recovered an unsaved macro from a previous session. Would you like to restore it?"
    )
    PASSWORD_WARNING = "Never enter passwords or secrets into macro actions."

    # UX Round 2 — Stage 1
    UNSAVED_CHANGES_TITLE = "Unsaved Changes"
    UNSAVED_CHANGES_MSG = '"{name}" has unsaved changes. Save before continuing?'
    MACRO_EXISTS_TITLE = "Macro Already Exists"
    MACRO_EXISTS_MSG = 'A macro named "{name}" already exists. Choose a different name.'
    SELECT_TYPE_TEXT_FIRST = "Select a Type Text step first, then click a column to insert it."
    SHORTCUT_BLOCKED_RUNNING = "Shortcut ignored while a run or step test is in progress."
    SHORTCUT_PICK_UNSUPPORTED = "F8 (Pick) works on a selected Click step."
    SHORTCUT_CAPTURE_UNSUPPORTED = "F9 (Capture) works on a selected image step."
    STEP_TEST_COUNTDOWN = "Testing step in {seconds}s... switch to your target window now."
    STEP_TEST_BUSY = "A step test is already counting down."
    DATA_DROP_HINT = "📂 Drag an Excel (.xlsx) or CSV file here, or click [Choose Data File]."
    DATA_DROP_UNSUPPORTED = "Only a single .xlsx or .csv file can be dropped here."
    DATA_LOADED_SUMMARY = "{file} · {rows} rows · {cols} columns"
    DATA_LOAD_ERROR_TITLE = "Data File Not Loaded"
    DATA_LOAD_PERMISSION_ERROR = (
        "{file} could not be opened. It may be open in another program such as Excel. "
        "Close it there and try again."
    )
    DATA_LOAD_ERROR = "{file} could not be loaded.\n{error}"
    DATA_LOAD_FAILED_STATUS = "Could not load {file}."
    DATA_KEEP_PREVIOUS = "Still connected: {file}"
    DATA_RECONNECT = "🔗 Reconnect: {file}"
    PREFLIGHT_END_ROW = "to row:"
    PREFLIGHT_RANGE_PREVIEW = "→ Source rows {first} ~ {last} ({count} rows, first row e.g. {sample})"
    STEP_TEST_CANCELLED = "Step test cancelled: the step no longer exists."
    STEP_TEST_CANCELLED_DIALOG = "Step test cancelled because a dialog or menu was opened."
    DATA_LOCKED_RUNNING = "The data file cannot be changed while a run is in progress."
    NEW_MACRO_PROMPT = "Enter macro name:"

    # UX Round 2 — Stage 2: toolbar
    TEST_1_ROW = "🧪 Test 1 Row"
    RUN_ROW_COUNT = "{n}"
    TEST_1_ROW_BLOCKED_TITLE = "Cannot Test Yet"
    TEST_1_ROW_BLOCKED = "Fix these problems before testing:\n{issues}"
    RETRY_FAILED_STATUS = "Retrying {count} row(s) from #{row}, starting in {sec}s..."

    # Pre-flight diagnostics, keyed by PreflightIssue.code (mirror engine/preflight.py)
    ISSUE_INVALID_MACRO = "Macro structure is invalid."
    ISSUE_IMAGE_MISSING = 'Referenced image not found: "{name}"'
    ISSUE_IMAGE_MISSING_DETAILS = "Context: {context} (searched: {path})"
    ISSUE_SELECTOR_MISSING = (
        'Step "{step}" uses UI Selector mode, but no target element is configured.'
    )
    ISSUE_SELECTOR_MISSING_DETAILS = "Section: {section}"
    ISSUE_NO_DATA = "Macro requires a data file, but no data is loaded."
    ISSUE_NO_DATA_DETAILS = "Required columns: {columns}"
    ISSUE_ALL_ROWS_EXCLUDED = "All rows in the selected range are Skipped or Done."
    ISSUE_ALL_ROWS_EXCLUDED_DETAILS = "There are no data rows to execute in this range."
    ISSUE_MISSING_COLUMNS = "Missing required columns in data file: {columns}"
    ISSUE_MISSING_COLUMNS_DETAILS = "Available columns: {available}"
    ISSUE_BLANK_CELLS = 'Column "{column}" contains empty values on {count} row(s).'
    ISSUE_BLANK_CELLS_DETAILS = "Rows: {rows}"
    ISSUE_UNKNOWN_VARIABLE = (
        'Step #{step} ({section}) types "{{{var}}}", but the connected data has no column "{var}".'
    )
    ISSUE_UNKNOWN_VARIABLE_DETAILS = 'Did you mean "{{{hint}}}"?'
    ISSUE_UNKNOWN_VARIABLE_NO_MATCH = ISSUE_UNKNOWN_VARIABLE
    ISSUE_UNKNOWN_VARIABLE_NO_MATCH_DETAILS = "Available columns: {available}"
    ISSUE_SCREEN_MISMATCH = "Screen mismatch: Recorded at {recorded}, current screen is {current}."
    ISSUE_SCREEN_MISMATCH_DETAILS = (
        "Click coordinates or image matches may fail due to display differences."
    )
    ISSUE_MULTI_MONITOR = "Multiple monitors detected ({count})."
    ISSUE_MULTI_MONITOR_DETAILS = (
        "Stepwise operates on the primary display. Ensure the target app is on the primary monitor."
    )
    ISSUE_NO_VERIFY = "No Verify images found in the Per Row section."
    ISSUE_NO_VERIFY_DETAILS = (
        "We strongly recommend adding a Verify image to critical steps "
        "(e.g. Save button) to avoid silent failures."
    )
    ISSUE_PREVIOUS_FAILURES = "Previous run has {count} unresolved Failed or Interrupted row(s)."
    ISSUE_PREVIOUS_FAILURES_DETAILS = "Rows: {rows}"
    ISSUE_SECTION_SETUP = "Setup"
    ISSUE_SECTION_PER_ROW = "Per Row"
    ISSUE_SECTION_CLEANUP = "Cleanup"

    # Floating run panel
    RUN_PANEL_RUNNING = "Stepwise ▶ Running"
    RUN_PANEL_PAUSED = "Stepwise ⏸ Paused"
    RUN_PANEL_SPEED = "Speed: {speed}"
    RUN_PANEL_ROW = "Row {row} / {total}"
    RUN_PANEL_STATS = "OK: {ok}  |  Failed: {failed}"
    RUN_PANEL_INIT = "Initializing..."
    RUN_PANEL_STARTING = "Starting run..."
    RUN_PANEL_EXECUTING_ROW = "Executing row {row}"
    RUN_PANEL_NEXT = "Next ⏭"
    RUN_PANEL_F12 = "⛔ Press F12 to stop"
    SPEED_NORMAL = "Normal"
    SPEED_SLOW = "Slow"
    SPEED_VERY_SLOW = "Very slow"

    # Pre-flight dialog
    PREFLIGHT_TITLE = 'Ready to run "{name}"'
    PREFLIGHT_INFO = (
        "<b>Macro:</b> {name} &nbsp;|&nbsp; <b>Data:</b> {data} ({rows} rows)"
    )
    PREFLIGHT_NO_DATA = "No Data"
    PREFLIGHT_DIAGNOSTICS = "Pre-flight Diagnostics"
    PREFLIGHT_OPTIONS = "Execution Options"
    PREFLIGHT_START_ROW = "Start from row:"
    PREFLIGHT_SPEED = "Speed Delay:"
    PREFLIGHT_SPEED_NORMAL = "Normal"
    PREFLIGHT_SPEED_SLOW = "Slow (+0.5s)"
    PREFLIGHT_SPEED_VERY_SLOW = "Very slow (+1s)"
    PREFLIGHT_SKIP_SETUP = "Skip Setup"
    PREFLIGHT_SKIP_CLEANUP = "Skip Cleanup"
    PREFLIGHT_WORKFLOW = "Workflow:"
    PREFLIGHT_CLICK_START = "Click [Start Run] to begin execution."
    PREFLIGHT_BLOCKED = "⚠ Please resolve blocking errors above before running."
    PREFLIGHT_RUN_1_ROW = "Run 1 Row (Test)"
    PREFLIGHT_START = "Start Run"
    PREFLIGHT_COUNTDOWN = "Starting in {seconds}... (switch to your target window now)"
    PREFLIGHT_ALL_PASSED = "✅ All pre-flight checks passed."
    PREFLIGHT_ERROR_PREFIX = "🔴 Error: "
    PREFLIGHT_WARNING_PREFIX = "🟡 Warning: "
    CANCEL = "Cancel"

    # Properties panel input helpers
    KEY_UNKNOWN_WARNING = "⚠ Unknown key name. Try one of the buttons below."
    WAIT_CHIP = "{seconds}s"
    ADVANCED_SAFETY_TOGGLE = "Advanced checks"
    ADVANCED_SAFETY_TOGGLE_TIP = "Optional screen checks before (Guard) and after (Verify) this step."
    SAFETY_BOX_TITLE = "🛡️ Guard & Verify (Visual Safety)"
    PARAMETERS_TITLE = "{type} Parameters"

    # Capture overlay banners
    CAPTURE_BANNER_PICK = "Click the target position once · Esc to cancel"
    CAPTURE_BANNER_REGION = "Drag around the area to capture · Esc to cancel"
    CAPTURE_BANNER_ELEMENT = "Check the blue outline, then click · Esc to cancel"

    # Action tree: step summaries (English wording is the long-standing format)
    TYPE_WINDOW_SET_BOUNDS = "Window bounds"
    SUMMARY_CLICK_XY = "{sim}{double}Click ({x}, {y}){button}"
    SUMMARY_CLICK_SELECTOR = '{sim}🎯 {double}Click [{control}] "{ident}"{button}'
    SUMMARY_SIM_BADGE = "⚡Sim "
    SUMMARY_DOUBLE = "Double "
    SUMMARY_BUTTON = " ({button})"
    SUMMARY_ELEMENT = "Element"
    SUMMARY_TARGET = "Target"
    SUMMARY_CLICK_IMAGE = 'Click image "{image}"'
    SUMMARY_TYPE = 'Type "{text}"{mode}'
    SUMMARY_TYPE_KEYSTROKES = " [keys]"
    SUMMARY_KEY = 'Key "{keys}"{repeat}'
    SUMMARY_KEY_REPEAT = " x{count}"
    SUMMARY_WAIT = "Wait {seconds}s"
    SUMMARY_WAIT_IMAGE = 'Wait for "{image}" (max {timeout}s)'
    SUMMARY_WAIT_IMAGE_GONE = 'Wait disappear "{image}"'
    SUMMARY_WINDOW_MAXIMIZE = 'Window "{title}" -> Maximize'
    SUMMARY_WINDOW_BOUNDS = 'Window "{title}" -> ({x}, {y}) {width}x{height}'
    SUMMARY_NO_WINDOW = "(No Window Specified)"
    SUMMARY_GROUP = "Group: {name} ({count} steps)"
    MOUSE_LEFT = "left"
    MOUSE_RIGHT = "right"
    MOUSE_MIDDLE = "middle"
    STEP_WARN_EMPTY_TEXT = "⚠ Enter the text to type"
    STEP_WARN_EMPTY_KEYS = "⚠ Choose the key to press"
    STEP_WARN_EMPTY_IMAGE = "⚠ Capture the image to find"

    # Action tree: context menu & insertion banner
    CTX_ADD_TO = "+ Add Action to {target}"
    CTX_ADD_CLICK = "👆 Add Click"
    CTX_ADD_TYPE = "⌨ Add Type text"
    CTX_ADD_KEY = "↵ Add Key press"
    CTX_ADD_WAIT = "⏱ Add Wait"
    CTX_ADD_IMAGE = "🖼 Add Click image"
    CTX_ADD_WINDOW = "🪟 Add Window Bounds"
    CTX_MOVE_TO_SECTION = "Move to Section"
    CTX_MOVE_TO_SETUP = "Move to SETUP"
    CTX_MOVE_TO_PER_ROW = "Move to PER ROW"
    CTX_MOVE_TO_CLEANUP = "Move to CLEANUP"
    TARGET_SECTION_SETUP = "SETUP"
    TARGET_SECTION_PER_ROW = "PER ROW"
    TARGET_SECTION_CLEANUP = "CLEANUP"
    NO_MACRO_LOADED = "🎯 No macro loaded"

    class Tooltips:
        """Centralized rich HTML tooltips (SuperTips) for key UI interactions."""

        @staticmethod
        def card(title: str, desc: str, shortcut: str | None = None, tip: str | None = None) -> str:
            """Generate a sleek, enterprise-grade rich HTML tooltip (SuperTip)."""
            html = (
                "<div style=\"font-family: 'Malgun Gothic', 'Segoe UI', -apple-system, sans-serif; "
                "font-size: 12px; line-height: 1.45; color: #f8fafc; background-color: #1e293b; "
                'border: 1px solid #334155; border-radius: 6px; max-width: 290px; padding: 8px 10px;">'
                f'<b style="color: #38bdf8; font-size: 13px;">{title}</b><br>'
                f'<div style="margin: 5px 0 4px 0; color: #f1f5f9;">{desc}</div>'
            )
            extra = []
            if shortcut:
                extra.append(
                    f'<span style="color: #94a3b8;">Shortcut:</span> <b style="color: #fbbf24;">{shortcut}</b>'
                )
            if tip:
                extra.append(
                    f'<span style="color: #38bdf8;">💡</span> <span style="color: #cbd5e1;">{tip}</span>'
                )
            if extra:
                html += (
                    '<div style="font-size: 11px; border-top: 1px solid #334155; '
                    f'margin-top: 6px; padding-top: 5px;">{"<br>".join(extra)}</div>'
                )
            html += "</div>"
            return html

        # Main Toolbar
        RUN = card(
            "Run Macro",
            "Executes the entire workflow sequentially across all rows loaded in Data Preview.",
            shortcut="F5",
            tip="Press F12 at any time for instant Emergency Stop.",
        )
        PAUSE = card(
            "Pause / Resume",
            "Temporarily pauses the running macro after the current step finishes.",
            tip="Inspect your target application or screen, then click Resume.",
        )
        STOP = card(
            "Stop Execution",
            "Safely halts the running automation immediately and flushes the result CSV.",
            shortcut="F12",
            tip="You can resume later starting from the stopped row.",
        )
        SCHEDULE = card(
            "Night-Shift Scheduler (Armed Mode)",
            "Schedule macros to run automatically overnight while preventing display sleep.",
            tip="Ideal for leaving your Cloud PC open overnight so work is finished by morning.",
        )
        STEP_BY_STEP = card(
            "Step-by-step Execution",
            "Runs the workflow one action at a time with manual approval for each step.",
            tip="Perfect for debugging and verifying new macros safely.",
        )
        TEST_1_ROW = card(
            "Test 1 Row",
            "Runs the whole macro for just one data row (the selected row, or the first).",
            tip="Starts after a short countdown so you can switch to the target window.",
        )
        SAVE_MACRO = card(
            "Save Macro Package",
            "Saves the current macro steps and embedded image assets into a .swm file.",
            shortcut="Ctrl+S",
        )
        SETTINGS = card(
            "Application Settings",
            "Configure language, theme, speed profiles, folders, and safety timeouts.",
        )

        # 3-Section Pipeline Headers
        SECTION_SETUP = card(
            "SETUP Section (Runs Once)",
            "Actions placed here run exactly once at the beginning to initialize the application.",
            tip="Use for opening ERP, logging in, or navigating to the initial screen.",
        )
        SECTION_PER_ROW = card(
            "PER ROW Section (Repeats for Every Row)",
            "The core processing loop. These steps run sequentially for each record in your data file.",
            tip="Insert [Column] variables here to automatically type spreadsheet values.",
        )
        SECTION_CLEANUP = card(
            "CLEANUP Section (Runs Once at End)",
            "Actions placed here run once after all spreadsheet rows have finished processing.",
            tip="Use for closing screens, committing batch notes, or cleanup.",
        )

        # Quick Action Buttons
        ADD_CLICK = card(
            "Add Mouse / UI Element Click",
            "Appends a click step (Coordinate, UI Selector, or Simulate Click) to the active section.",
            tip="Use F8 for coordinates or Pick UI Element for button/field targeting.",
        )
        ADD_TYPE = card(
            "Add Text Input",
            "Appends a text typing action to the active section.",
            tip="Supports plain text as well as dynamic [Column] variables.",
        )
        ADD_KEY = card(
            "Add Key Press",
            "Appends a keyboard keystroke (Enter, Tab, Esc, shortcuts) to the active section.",
            tip="Use to navigate between fields or confirm dialogs.",
        )
        ADD_WAIT = card(
            "Add Fixed Delay",
            "Appends a pause in seconds to allow slow UI animations or server calls to settle.",
        )
        ADD_WINDOW = card(
            "Add Window Bounds",
            "Enforces target application window position and size (e.g. Align to 0,0 at 1280x800).",
            tip="Essential in SETUP to ensure consistent coordinates across different monitors.",
        )
        DELETE_ACTION = card(
            "Delete Action",
            "Removes the selected action or group from the workflow.",
            shortcut="Del",
        )

        # Properties Panel Helpers
        PICK_COORDS = card(
            "Pick Screen Coordinates",
            "Turns cursor into a crosshair so you can click any point on your screen.",
            shortcut="F8",
            tip="Coordinates are captured based on your physical display resolution.",
        )
        PICK_UI_ELEMENT = card(
            "Pick UI Element (UI Selector)",
            "Hover over any button or input field and click to capture its Windows UI Automation selector.",
            shortcut="Ctrl+F8",
            tip="Works even if the window moves or supports Simulate Click.",
        )
        CAPTURE_IMAGE = card(
            "Screen Freeze & Capture",
            "Freezes the display and lets you drag a box around a button, icon, or text.",
            shortcut="F9",
            tip="Used for visual template matching (Guard, Verify, Wait for Image).",
        )
        SHOW_ON_SCREEN = card(
            "Show Target on Screen",
            "Briefly flashes a high-visibility crosshair or highlight box at the target.",
            tip="Quickly verify target position without clicking it.",
        )
        TEST_THIS_STEP = card(
            "Test This Step",
            "Executes only this single action immediately on your active screen.",
            tip="Validate click position, UI Selector, or typing mode safely.",
        )
        TEST_MATCH = card(
            "Test Template Match",
            "Searches the active screen right now to verify if the template image can be found.",
            tip="Displays the match confidence score.",
        )
        GUARD_CHECK = card(
            "Visual Pre-Check (Guard)",
            "Ensures a specific window, icon, or field is visible on screen before this step executes.",
            tip="Prevents misclicking during network delays or screen loading.",
        )
        VERIFY_CHECK = card(
            "Visual Post-Verification (Verify)",
            "Confirms that a success toast, saved confirmation, or expected state appeared after this step.",
            tip="Guarantees data was committed before proceeding to the next row.",
        )

        # Data Panel
        CHOOSE_DATA_FILE = card(
            "Choose Data File",
            "Load an Excel (.xlsx) or CSV spreadsheet to drive the PER ROW automation loop.",
            tip="Original files are strictly read-only and never modified.",
        )
        VARIABLE_BUTTON = card(
            "Insert Variable",
            "Inserts this column's variable into the selected text typing field.",
            tip="Stepwise substitutes this with each row's actual data at runtime.",
        )


# Snapshot default English dictionaries at import time
_EN_STRINGS: dict[str, str] = {
    k: v
    for k, v in vars(Strings).items()
    if not k.startswith("_") and isinstance(v, str)
}
_EN_TOOLTIPS: dict[str, str] = {
    k: v
    for k, v in vars(Strings.Tooltips).items()
    if not k.startswith("_") and isinstance(v, str)
}

_KO_STRINGS: dict[str, str] = {
    "APP_TITLE": "Stepwise",
    "APP_SUBTITLE": "데이터 기반 매크로 자동화 도구",
    "SAVE_MACRO": "저장",
    "RUN": "실행",
    "PAUSE": "일시정지",
    "RESUME": "재개",
    "STOP": "정지",
    "SCHEDULE": "예약 실행",
    "STEP_BY_STEP": "단계별 실행",
    "DATA_FILE": "데이터:",
    "NO_DATA": "연결된 데이터 파일 없음",
    "SETTINGS": "설정",
    "THEME_DARK": "🌙 다크",
    "THEME_LIGHT": "☀️ 라이트",
    "LANG_KO": "🇰🇷 한국어",
    "LANG_EN": "🇺🇸 EN",
    "SETTINGS_SAVE_FAILED": "설정을 저장하지 못했습니다. 폴더 권한과 디스크 여유 공간을 확인한 후 다시 시도하세요.",
    "OPEN_SETTINGS_FOLDER": "설정 폴더 열기",
    "OPEN_RESULTS_FOLDER": "결과 폴더 열기",
    "BACKUP_SCOPE": "설정 폴더와 매크로 라이브러리를 백업하세요. 필요시 결과 폴더도 포함하세요. 외부 폴더 및 원본 데이터는 별도로 백업해야 합니다.",
    "FOLDER_OPEN_FAILED": "폴더를 열 수 없습니다. 폴더가 존재하는지, 접근 권한이 있는지 확인하세요.",
    "RUN_ERROR_TITLE": "실행 취소됨",
    "SNAPSHOT_ERROR": "실행 준비 중 오류가 발생했습니다. 다시 시도해 주세요.\n{error}",
    "F12_ERROR": (
        "비상 정지 단축키(F12)를 등록할 수 없어 실행이 취소되었습니다. "
        "F12를 점유 중인 다른 프로그램을 닫고 다시 시도하세요.\n{error}"
    ),
    "RUN_START_ERROR": "매크로 실행을 시작할 수 없습니다. 다시 시도해 주세요.\n{error}",
    "SAVE_ERROR_TITLE": "저장 실패",
    "CAPTURE_ERROR_TITLE": "캡처 실패",
    "CAPTURE_ERROR": "캡처한 이미지를 저장할 수 없습니다. 디스크 여유 공간을 확인하고 다시 시도하세요.\n{error}",
    "SAVE_ERROR": "매크로를 저장할 수 없습니다. 저장 경로와 참조된 이미지 파일을 확인하세요.\n{error}",
    "RESULTS_WARNING": "결과 CSV 파일이 잠겨 있어 일부 결과가 임시 저널 파일에 기록되었습니다.",
    "EXPORT_BUFFERED_RESULTS": "임시 보관된 결과 내보내기",
    "RESULTS_MEMORY_WARNING": (
        "일부 결과를 디스크에 저장할 수 없어 메모리에 보관 중입니다. "
        "창을 닫지 마시고 결과를 파일로 내보내 주세요."
    ),
    "SECTION_SETUP": "① 시작할 때 1번 (창 열기·로그인)",
    "SECTION_PER_ROW": "② 엑셀 각 줄마다 반복 (핵심 입력 루프)",
    "SECTION_CLEANUP": "③ 끝날 때 1번 (창 닫기, 없어도 됨)",
    "SECTION_EMPTY_PLACEHOLDER": "(비어 있음 — 여기를 선택한 뒤 동작을 추가하세요)",
    "SECTION_SETUP_EMPTY": "(비어 있음 — 창 위치 맞추기, 로그인 등. 비워두셔도 됩니다)",
    "SECTION_PER_ROW_EMPTY": "(비어 있음 — 입력 칸 클릭 ➜ [열 이름] 값 입력 ➜ 저장 등 반복 동작 추가)",
    "SECTION_CLEANUP_EMPTY": "(비어 있음 — 완료 후 창 닫기, 로그아웃 등. 비워두셔도 됩니다)",
    "INSERT_TARGET_TOP": "추가 위치: [{section}] 맨 앞",
    "INSERT_TARGET_AFTER": "추가 위치: [{section}] Step #{step} 다음",
    "INSERT_TARGET_GROUP": '추가 위치: [{section}] 그룹 "{group}" 다음',
    "INSERT_TARGET_END": "추가 위치: [{section}] 맨 끝",
    "MOVE_BOUNDARY_TOP": "이미 섹션 또는 그룹의 맨 위입니다. 다른 섹션으로 옮기려면 우클릭 '섹션 이동'을 사용하세요.",
    "MOVE_BOUNDARY_BOTTOM": "이미 섹션 또는 그룹의 맨 아래입니다. 다른 섹션으로 옮기려면 우클릭 '섹션 이동'을 사용하세요.",
    "TYPE_CLICK": "클릭",
    "TYPE_CLICK_IMAGE": "이미지 클릭",
    "TYPE_TYPE_TEXT": "텍스트 입력",
    "TYPE_KEY": "키 입력",
    "TYPE_WAIT": "대기",
    "TYPE_WAIT_IMAGE": "이미지 출현 대기",
    "TYPE_WAIT_IMAGE_GONE": "이미지 사라짐 대기",
    "TYPE_GROUP": "그룹",
    "COL_NUM": "#",
    "COL_ENABLED": "✓",
    "COL_ACTION": "동작",
    "COL_TARGET": "대상 요약",
    "COL_WAIT": "대기",
    "COL_CHECK": "검증",
    "COL_NOTE": "메모",
    "ADD_ACTION_LABEL": "동작 추가:",
    "ADD_ACTION": "+ 동작 추가",
    "BTN_ADD_CLICK": "👆 + 클릭",
    "BTN_ADD_TYPE": "⌨ + 텍스트",
    "BTN_ADD_KEY": "↵ + 키입력",
    "BTN_ADD_WAIT": "⏱ + 대기",
    "BTN_ADD_WIN": "🪟 + 창정렬",
    "MOVE_UP": "↑ 위로",
    "MOVE_DOWN": "↓ 아래로",
    "DUPLICATE": "복제",
    "DELETE": "삭제",
    "GROUP": "그룹화",
    "UNGROUP": "그룹 해제",
    "SEARCH_ACTIONS": "동작 검색...",
    "FILTER_ALL": "모든 동작",
    "FILTER_GUARD_VERIFY_ONLY": "Guard/Verify 포함만",
    "FILTER_DISABLED_ONLY": "비활성 동작만",
    "FILTER_VARIABLES_ONLY": "변수 사용 동작만",
    "COMPACT_VIEW": "컴팩트 보기",
    "PROPERTIES_TITLE": "속성 (Properties)",
    "GENERAL_OPTIONS": "기본 옵션",
    "ACTION_ENABLED": "이 동작 활성화",
    "NO_ACTION_SELECTED": "트리에서 동작을 선택하면 상세 속성을 확인하고 편집할 수 있습니다.",
    "PROPERTIES_GUIDE": (
        "<b>💡 빠른 시작 가이드:</b><br><br>"
        "1. 동작 트리 아래의 <b>[+ 클릭]</b> 또는 <b>[+ 텍스트]</b> 버튼을 눌러 스텝을 추가하세요.<br>"
        "2. 추가된 스텝을 선택해 좌표, <b>UI 요소 Selector</b>, 또는 입력할 텍스트를 설정하세요.<br>"
        "3. <b>[좌표 지정 (F8)]</b> 또는 <b>[🎯 UI 요소 선택]</b>으로 대상을 마우스로 바로 지정할 수 있습니다.<br>"
        "4. 하단 <b>데이터 미리보기</b>에서 엑셀/CSV 파일을 불러온 뒤 <b>[열 이름]</b> 버튼을 누르면 값을 자동 입력할 수 있습니다."
    ),
    "COORD_X": "X 좌표:",
    "COORD_Y": "Y 좌표:",
    "COORDINATES_LABEL": "화면 좌표:",
    "ACTION_TOOLS_LABEL": "동작 테스트 도구:",
    "BUTTON": "마우스 버튼:",
    "CLICKS": "클릭 횟수:",
    "TEXT_TO_TYPE": "입력할 텍스트:",
    "TYPE_MODE": "입력 방식:",
    "MODE_PASTE": "클립보드 붙여넣기 (한글 추천)",
    "MODE_KEYSTROKES": "직접 타이핑 (영문/숫자)",
    "SELECT_ALL_FIRST": "입력 전 전체 선택 (Ctrl+A)",
    "KEYS_TO_PRESS": "누를 키 조합:",
    "REPEAT_COUNT": "반복 횟수:",
    "WAIT_SECONDS": "대기 시간 (초):",
    "WAIT_BEFORE": "실행 전 대기 (초):",
    "IMAGE_PATH": "이미지 파일:",
    "SEARCH_REGION": "탐색 영역:",
    "CONFIDENCE": "일치 정확도:",
    "TIMEOUT_SEC": "제한 시간 (초):",
    "AFTER_FOUND_SEC": "발견 후 추가 대기 (초):",
    "STABLE_FOR_SEC": "안정화 유지 시간 (초):",
    "APPEAR_GRACE_SEC": "출현 유예 시간 (초):",
    "AFTER_GONE_SEC": "사라진 후 추가 대기 (초):",
    "OFFSET_X": "오프셋 X:",
    "OFFSET_Y": "오프셋 Y:",
    "GROUP_NAME": "그룹 이름:",
    "NOTE_LABEL": "메모 / 설명:",
    "TARGET_MODE_LABEL": "타겟 지정 방식:",
    "TARGET_MODE_COORDS": "화면 절대 좌표 (X, Y)",
    "TARGET_MODE_SELECTOR": "UI 요소 셀렉터 (UIA / 버튼·필드 직접 지정)",
    "CLICK_METHOD_LABEL": "클릭 실행 방식:",
    "CLICK_METHOD_HARDWARE": "일반 마우스 클릭 (SendInput)",
    "CLICK_METHOD_SIMULATE": "Simulate Click (백그라운드 클릭 / 커서 미사용)",
    "PICK_UI_ELEMENT": "🎯 UI 요소 선택 (Ctrl+F8)",
    "VALIDATE_SELECTOR": "🔍 요소 찾기 & 하이라이트 검증",
    "CLEAR_SELECTOR": "셀렉터 초기화",
    "SELECTOR_SUMMARY_EMPTY": "선택된 UI 요소가 없습니다. [🎯 UI 요소 선택]을 눌러 대상 버튼/입력창을 클릭하세요.",
    "SELECTOR_WINDOW_TITLE": "대상 창 제목:",
    "SELECTOR_CONTROL_TYPE": "컨트롤 유형:",
    "SELECTOR_AUTOMATION_ID": "Automation ID:",
    "SELECTOR_NAME": "요소 이름(Name):",
    "SELECTOR_CLASS_NAME": "클래스명(Class):",
    "DATA_CHIP_LABEL": "엑셀 열 넣기:",
    "DATA_NO_FILE_NUDGE": "행마다 다른 값을 넣으려면: [📂 엑셀 / CSV 파일 연결]",
    "ROW_PREVIEW_PREFIX": "첫 데이터 행 미리보기:",
    "KOREAN_IME_NUDGE": "💡 한글 입력은 조합 깨짐 방지를 위해 '클립보드 붙여넣기' 방식을 권장합니다.",
    "BTN_LOCATE_TARGET": "🔍 위치만 확인",
    "BTN_TEST_STEP": "▶ 1회 테스트",
    "LOCATE_TARGET_ACTIVE": "대상 위치를 1초간 빨간 테두리로 표시합니다 (클릭/입력 없음)...",
    "RETRY_FAILED_ROWS": "실패한 {count}개 행만 다시 실행",
    "RESUME_FROM_FAILED_ROW": "실패한 {row}번째 줄부터 끝까지 이어서 실행",
    "F12_GENTLE_REMINDER": "실행 중 언제든 F12를 누르면 안전하게 즉시 멈출 수 있습니다.",
    "LOOP_REPETITION_LABEL": " — {rows}줄 × {steps}단계",
    "BEFORE_DATA_CONNECTED": " — 데이터 연결 전",
    "PREVIEW_EMPTY_TEXT": "(텍스트를 입력하세요)",
    "PREVIEW_NO_DATA_TEXT": "{text} (데이터 파일 미연결 시 고정 문자열)",
    "QUICK_START_BANNER": "💡 빠른 시작: ① 엑셀 데이터 연결 ➜ ② 아래 버튼으로 동작 추가 ➜ ③ [▶ 실행]",
    "LOCATE_TOOLTIP": "클릭하지 않고 대상 위치에 빨간 테두리만 1.5초간 표시하여 안전하게 확인합니다.",
    "SUMMARY_TITLE_SUCCESS": "✓ 전체 {count}개 행 입력 완료 ({duration}초)",
    "SUMMARY_TITLE_INTERRUPTED": "⚠️ 실행 중단됨 — {done}개 완료, {row}번째 행에서 멈춤",
    "SUMMARY_TITLE_FAILED": "⚠️ {row}번째 행에서 오류 발생 — {done}개 완료",
    "WINDOW_TITLE_LABEL": "대상 창 제목:",
    "WINDOW_PICK_BUTTON": "🔍 실행 중인 창 선택",
    "WINDOW_PICK_TOOLTIP": "현재 열려 있는 프로그램 창 목록에서 선택합니다",
    "WINDOW_POS_LABEL": "창 좌측 상단 위치:",
    "WINDOW_SIZE_LABEL": "창 크기:",
    "WINDOW_MAXIMIZE_LABEL": "크기 지정 대신 창 최대화(Maximize)",
    "PICK_COORDS": "좌표 지정 (F8)",
    "CAPTURE_IMAGE": "화면 캡처 (F9)",
    "SHOW_ON_SCREEN": "위치 표시",
    "TEST_THIS_STEP": "이 스텝 즉시 테스트",
    "TEST_MATCH": "이미지 매칭 테스트",
    "GUARD_SECTION": "Guard (실행 전 화면 확인)",
    "VERIFY_SECTION": "Verify (실행 후 결과 확인)",
    "GUARD_PLACEHOLDER": "선택사항: 사전 확인 템플릿 이미지 (예: images/form.png)",
    "VERIFY_PLACEHOLDER": "선택사항: 사후 확인 템플릿 이미지 (예: images/saved.png)",
    "ENABLE_GUARD": "Guard(사전 화면 확인) 사용",
    "ENABLE_VERIFY": "Verify(사후 화면 확인) 사용",
    "DATA_PANEL_TITLE": "데이터 미리보기",
    "INSERT_VARIABLE_LABEL": "컬럼 변수 클릭 삽입:",
    "ROWS_LOADED": "{count}개 행 로드됨",
    "SELECT_DATA_FILE": "📂 데이터 파일 선택...",
    "SHEET": "시트:",
    "HEADER_ROW": "헤더 행:",
    "ENCODING": "인코딩:",
    "DELIMITER": "구분자:",
    "STATUS_PENDING": "대기중",
    "STATUS_RUNNING": "실행중",
    "STATUS_DONE": "완료",
    "STATUS_FAILED": "실패",
    "STATUS_INTERRUPTED": "중단됨",
    "STATUS_SKIPPED": "건너뜀",
    "RETRY_ROW": "이 행 다시 실행 대기(Pending)",
    "SKIP_ROW": "이 행 건너뛰기(Skip)",
    "MARK_DONE": "완료(Done)로 표시",
    "RUN_ONLY_THIS_ROW": "이 행만 단독 실행",
    "RESET_ALL_STATUSES": "모든 행 상태 초기화",
    "RESET_ALL_STATUSES_CONFIRM_TITLE": "행 상태 초기화",
    "RESET_ALL_STATUSES_CONFIRM_MSG": "모든 행의 상태를 '대기(Pending)'로 초기화하시겠습니까?\n(완료된 행을 처음부터 다시 실행할 수 있습니다)",
    "PREFLIGHT_EXCLUDED_BREAKDOWN": "제외 행: {count}개 (완료: {done}개, 건너뛰기: {skipped}개)",
    "PREFLIGHT_ALL_DONE_TITLE": "모든 행 완료됨",
    "PREFLIGHT_ALL_DONE_MSG": "선택한 범위의 모든 행이 이미 완료(Done) 상태입니다.\n행 상태를 초기화하고 처음부터 다시 실행하시겠습니까?",
    "RESET_AND_RUN": "상태 초기화 후 실행",
    "PREFLIGHT_FIRST_ROW_SAMPLE": "[첫 행 입력 예시]",
    "PREFLIGHT_RUN_1_ROW_TOOLTIP": "첫 1개 행만 먼저 실행해보고 결과와 화면 동작을 검증합니다.",
    "LIBRARY_TITLE": "매크로 라이브러리",
    "SEARCH_MACROS": "매크로 검색...",
    "NEW_MACRO": "+ 새 매크로",
    "DUPLICATE_MACRO": "매크로 복제",
    "RENAME_MACRO": "이름 변경",
    "DELETE_MACRO": "삭제",
    "OPEN_FOLDER": "라이브러리 폴더 열기",
    "LOCKED_BY_USER": "{machine}의 {user}님이 편집 중",
    "STALE_LOCK": "{user}님의 오래된 잠금 (인수하시겠습니까?)",
    "SCHEDULER_TITLE": "야간 무인 예약 실행기 (Armed Mode)",
    "SCHEDULER_SUBTITLE": "Cloud PC 디스플레이 절전을 방지하며 지정된 시각에 매크로를 자동 실행합니다.",
    "SCHEDULER_TARGET_TIME": "예약 시작 시각:",
    "SCHEDULER_START_ROW": "시작 행 번호:",
    "SCHEDULER_SPEED_PROFILE": "실행 속도 프로필:",
    "SCHEDULER_SPEED_NORMAL": "보통 (Normal)",
    "SCHEDULER_SPEED_SLOW": "느리게 (+0.5초 안전 여유)",
    "SCHEDULER_SPEED_VERY_SLOW": "매우 느리게 (+1.0초 안전 여유)",
    "SCHEDULER_ON_FAIL": "오류 발생 시 정책:",
    "SCHEDULER_STOP_QUEUE": "즉시 중단 및 실패 스크린샷 기록 (Fail-Fast 안전 우선)",
    "SCHEDULER_CONTINUE_NEXT": "즉시 중단 (Fail-Fast)",
    "SCHEDULER_LOCK_AFTER": "예약 실행 정상 완료 후 Windows 화면 잠금(LockWorkStation)",
    "SCHEDULER_RESET_STATUSES": "실행 전 완료(Done)된 행을 '대기(Pending)'로 자동 초기화",
    "SCHEDULER_ANTI_LOCK_JIGGLER": "예약 대기 중 화면 잠금 방지 (Anti-Lock Jiggler)",
    "SCHEDULER_ANTI_LOCK_JIGGLER_TIP": "예약 시각까지 대기하는 동안 {seconds}초마다 보이지 않는 무영향 신호를 전송하여 사내 보안 잠금으로 화면이 꺼지는 것을 방지합니다.",
    "SETTINGS_JIGGLER_GROUP": "화면 자동 잠금 방지 (Anti-Lock Jiggler)",
    "SETTINGS_JIGGLER_ENABLE": "실행 및 예약 대기 중 화면 자동 잠금 방지",
    "SETTINGS_JIGGLER_TIP": "Windows 유휴 타이머를 주기적으로 초기화하는 무영향 가상 키(F15) 신호를 보내 사내 보안 정책(GPO)으로 인한 화면 잠금 및 원격 데스크톱 세션 끊김을 방지합니다.",
    "SETTINGS_JIGGLER_INTERVAL": "방지 신호 주기:",
    "SECONDS_UNIT": "초",
    "SCHEDULER_PRE_ARM_TITLE": "야간 무인 실행 환경 & 정책 사전 진단",
    "SCHEDULER_CHECKLIST_TITLE": "야간 Cloud PC 필수 안전 수칙 확인 (체크 필수)",
    "SCHEDULER_CHK_DONT_CLOSE": "Cloud PC(원격 데스크톱) 창을 닫거나 최소화하지 않겠습니다 (다른 창 뒤에 두는 것은 가능)",
    "SCHEDULER_CHK_POWER": "현재 로컬 PC(노트북)의 전원이 연결되어 있고 절전 모드가 꺼져 있습니다",
    "SCHEDULER_CHK_ERP_READY": "대상 ERP/웹 프로그램이 로그인되어 있고 초기 실행 화면이 준비되어 있습니다",
    "SCHEDULER_BTN_RUN_NOW": "▶ 즉시 테스트 실행",
    "SCHEDULER_BTN_ARM": "🛡️ 야간 예약 대기 시작 (Arm)",
    "SCHEDULER_BTN_DISARM": "예약 취소 / 대기 해제",
    "SCHEDULER_ARMED_BANNER": "⏳ 예약 대기 중 — {time} 실행 예정 (남은 시간: {remaining}). 이 창과 Cloud PC를 닫지 마세요!",
    "SCHEDULER_BANNER_BLOCKING": "⚠ 위의 차단 오류(BLOCKING)를 먼저 해결해 주세요.",
    "SCHEDULER_BANNER_READY": "✅ 야간 무인 예약을 시작할 준비가 완료되었습니다.",
    "SCHEDULER_BANNER_CHECKLIST": "ℹ 위의 안전 수칙 체크리스트 3개 항목을 모두 체크하면 예약 버튼이 활성화됩니다.",
    "SCHEDULER_TAG_BLOCKING": "🔴 [차단 오류] ",
    "SCHEDULER_TAG_WARN": "🟡 [주의 권장] ",
    "SCHEDULER_TAG_READY": "🟢 [정상 준비] ",
    "SCHEDULER_STALE_ABORT": "예약 시각으로부터 15분 이상 경과하여(시스템 절전/일시중단 추정) 안전을 위해 자동 실행을 취소했습니다.",
    "SCHEDULER_REPORT_TITLE": "야간 예약 작업 실행 리포트",
    "SCREEN_MATCH": "화면 {w}x{h} @{scale}% ✅ 매크로 기준과 일치",
    "SCREEN_MISMATCH": "화면 {w}x{h} @{scale}% ⚠ 매크로 기록 환경({rec_w}x{rec_h} @{rec_scale}%)과 다름",
    "STATUS_READY": "준비 완료",
    "UPDATE_CHECK_MENU": "업데이트 확인...",
    "UPDATE_AUTO_CHECK_LABEL": "시작 시 업데이트 자동 확인",
    "UPDATE_LAST_CHECKED": "마지막 확인: {time}",
    "UPDATE_NEVER_CHECKED": "확인한 적 없음",
    "UPDATE_CHECK_NOW": "지금 확인",
    "UPDATE_CHECKING": "업데이트 확인 중...",
    "UPDATE_UP_TO_DATE_TITLE": "최신 버전",
    "UPDATE_UP_TO_DATE_MSG": "현재 최신 버전(v{version})을 사용 중입니다.",
    "UPDATE_AVAILABLE_TITLE": "새 버전 업데이트",
    "UPDATE_AVAILABLE_MSG": "Stepwise 새 버전(v{version})이 출시되었습니다.",
    "UPDATE_DOWNLOAD_BTN": "업데이트 다운로드",
    "UPDATE_DOWNLOADING": "다운로드 중... {progress}% ({speed})",
    "UPDATE_VERIFYING": "디지털 서명 및 무결성 검증 중...",
    "UPDATE_READY_INSTALL_BTN": "지금 설치 및 재시작",
    "UPDATE_LATER_BTN": "나중에",
    "UPDATE_VIEW_RELEASE": "GitHub 릴리즈 보기",
    "UPDATE_BLOCKED_RUNNING": "매크로가 실행 중일 때는 업데이트를 설치할 수 없습니다. 매크로를 먼저 중지하세요.",
    "UPDATE_BLOCKED_ARMED": "야간 예약 실행(Armed 모드) 대기 중에는 업데이트를 설치할 수 없습니다. 예약을 먼저 해제하세요.",
    "UPDATE_VERIFY_FAILED": "무결성/디지털 서명 검증 실패: {error}",
    "UPDATE_DOWNLOAD_FAILED": "다운로드 실패: {error}",
    "UPDATE_RATE_LIMITED": "GitHub API 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.",
    "UPDATE_DEV_MODE_NOTICE": "소스코드 또는 포터블 모드로 실행 중입니다. git pull 또는 GitHub에서 인스톨러를 다운로드하여 업데이트하세요.",
    "CONFIRM_DELETE": "선택한 동작을 삭제하시겠습니까?",
    "CONFIRM_DISCARD_CHANGES": "저장하지 않은 변경 사항이 있습니다. 변경 사항을 버리시겠습니까?",
    "RECOVERY_FOUND_TITLE": "자동 복구 가능",
    "RECOVERY_FOUND_MSG": "이전 세션에서 저장되지 않은 매크로를 발견했습니다. 복구하시겠습니까?",
    "PASSWORD_WARNING": "보안을 위해 비밀번호나 민감한 인증정보는 매크로에 직접 입력하지 마세요.",
    "UNSAVED_CHANGES_TITLE": "저장하지 않은 변경 사항",
    "UNSAVED_CHANGES_MSG": '"{name}"에 저장하지 않은 변경 사항이 있습니다. 계속하기 전에 저장할까요?',
    "MACRO_EXISTS_TITLE": "같은 이름의 매크로가 있습니다",
    "MACRO_EXISTS_MSG": '"{name}" 매크로가 이미 있습니다. 다른 이름을 입력하세요.',
    "SELECT_TYPE_TEXT_FIRST": "먼저 '텍스트 입력' 단계를 선택한 뒤 열 이름을 누르세요.",
    "SHORTCUT_BLOCKED_RUNNING": "실행 또는 단계 테스트 중에는 단축키가 동작하지 않습니다.",
    "SHORTCUT_PICK_UNSUPPORTED": "F8(좌표 지정)은 '클릭' 단계를 선택했을 때 사용할 수 있습니다.",
    "SHORTCUT_CAPTURE_UNSUPPORTED": "F9(화면 캡처)는 이미지 단계를 선택했을 때 사용할 수 있습니다.",
    "STEP_TEST_COUNTDOWN": "{seconds}초 후 단계를 테스트합니다... 지금 대상 창으로 전환하세요.",
    "STEP_TEST_BUSY": "단계 테스트 카운트다운이 이미 진행 중입니다.",
    "DATA_DROP_HINT": "📂 엑셀(.xlsx) 또는 CSV 파일을 여기로 끌어다 놓거나 [파일 선택]을 누르세요",
    "DATA_DROP_UNSUPPORTED": ".xlsx 또는 .csv 파일 하나만 끌어다 놓을 수 있습니다.",
    "DATA_LOADED_SUMMARY": "{file} · 데이터 {rows}건 · {cols}개 열",
    "DATA_LOAD_ERROR_TITLE": "데이터 파일을 불러오지 못했습니다",
    "DATA_LOAD_PERMISSION_ERROR": "{file} 파일을 열 수 없습니다. 엑셀 등 다른 프로그램에서 열려 있는지 확인하고, 닫은 뒤 다시 시도하세요.",
    "DATA_LOAD_ERROR": "{file} 파일을 불러오지 못했습니다.\n{error}",
    "DATA_LOAD_FAILED_STATUS": "{file} 불러오기 실패.",
    "DATA_KEEP_PREVIOUS": "기존 연결 유지: {file}",
    "DATA_RECONNECT": "🔗 다시 연결: {file}",
    "PREFLIGHT_END_ROW": "끝 순번:",
    "PREFLIGHT_RANGE_PREVIEW": "→ 원본 엑셀 {first}행 ~ {last}행 ({count}건, 첫 줄 예시: {sample})",
    "STEP_TEST_CANCELLED": "테스트할 단계가 삭제되어 단계 테스트를 취소했습니다.",
    "STEP_TEST_CANCELLED_DIALOG": "대화상자나 메뉴가 열려 단계 테스트를 취소했습니다.",
    "DATA_LOCKED_RUNNING": "실행 중에는 데이터 파일을 바꿀 수 없습니다.",
    "NEW_MACRO_PROMPT": "새 매크로 이름을 입력하세요:",
    "TEST_1_ROW": "🧪 1줄 테스트",
    "RUN_ROW_COUNT": "{n}줄",
    "TEST_1_ROW_BLOCKED_TITLE": "아직 테스트할 수 없습니다",
    "TEST_1_ROW_BLOCKED": "테스트 전에 아래 문제를 먼저 해결해 주세요:\n{issues}",
    "RETRY_FAILED_STATUS": "#{row}행부터 {count}줄을 다시 실행합니다. {sec}초 후 시작...",
    "ISSUE_INVALID_MACRO": "매크로 구조가 올바르지 않습니다.",
    "ISSUE_IMAGE_MISSING": '참조한 이미지 파일을 찾을 수 없습니다: "{name}"',
    "ISSUE_IMAGE_MISSING_DETAILS": "위치: {context} (찾은 경로: {path})",
    "ISSUE_SELECTOR_MISSING": '단계 "{step}"은(는) UI 요소 선택 방식인데 대상 요소가 지정되지 않았습니다.',
    "ISSUE_SELECTOR_MISSING_DETAILS": "구간: {section}",
    "ISSUE_NO_DATA": "이 매크로는 데이터 파일이 필요하지만 아직 연결되지 않았습니다.",
    "ISSUE_NO_DATA_DETAILS": "필요한 열: {columns}",
    "ISSUE_ALL_ROWS_EXCLUDED": "선택한 범위의 모든 행이 건너뛰기(Skipped) 또는 완료(Done) 상태입니다.",
    "ISSUE_ALL_ROWS_EXCLUDED_DETAILS": "해당 범위에 실행할 데이터 행이 없습니다.",
    "ISSUE_MISSING_COLUMNS": "데이터 파일에 필요한 열이 없습니다: {columns}",
    "ISSUE_MISSING_COLUMNS_DETAILS": "현재 열: {available}",
    "ISSUE_BLANK_CELLS": '"{column}" 열에 빈 칸이 {count}줄 있습니다.',
    "ISSUE_BLANK_CELLS_DETAILS": "행: {rows}",
    "ISSUE_UNKNOWN_VARIABLE": (
        '{step}번 단계({section})에서 "{{{var}}}"를 입력하지만, 연결된 데이터에 "{var}" 열이 없습니다.'
    ),
    "ISSUE_UNKNOWN_VARIABLE_DETAILS": '"{{{hint}}}"을(를) 쓰려던 것인가요?',
    "ISSUE_UNKNOWN_VARIABLE_NO_MATCH": (
        '{step}번 단계({section})에서 "{{{var}}}"를 입력하지만, 연결된 데이터에 "{var}" 열이 없습니다.'
    ),
    "ISSUE_UNKNOWN_VARIABLE_NO_MATCH_DETAILS": "현재 열: {available}",
    "ISSUE_SCREEN_MISMATCH": "화면이 녹화 당시와 다릅니다: 녹화 {recorded}, 현재 {current}.",
    "ISSUE_SCREEN_MISMATCH_DETAILS": "화면 차이로 좌표 클릭이나 이미지 찾기가 실패할 수 있습니다.",
    "ISSUE_MULTI_MONITOR": "모니터가 {count}대 연결되어 있습니다.",
    "ISSUE_MULTI_MONITOR_DETAILS": "Stepwise는 주 모니터에서 동작합니다. 대상 프로그램을 주 모니터에 두세요.",
    "ISSUE_NO_VERIFY": "② 반복 구간에 Verify(결과 확인) 이미지가 없습니다.",
    "ISSUE_NO_VERIFY_DETAILS": "저장 버튼 등 중요한 단계에 Verify 이미지를 추가하면 조용한 실패를 막을 수 있습니다.",
    "ISSUE_PREVIOUS_FAILURES": "이전 실행에서 실패/중단된 줄이 {count}개 남아 있습니다.",
    "ISSUE_PREVIOUS_FAILURES_DETAILS": "행: {rows}",
    "ISSUE_SECTION_SETUP": "① 시작",
    "ISSUE_SECTION_PER_ROW": "② 반복",
    "ISSUE_SECTION_CLEANUP": "③ 마무리",
    "RUN_PANEL_RUNNING": "Stepwise ▶ 실행 중",
    "RUN_PANEL_PAUSED": "Stepwise ⏸ 일시정지됨",
    "RUN_PANEL_SPEED": "속도: {speed}",
    "RUN_PANEL_ROW": "{total}줄 중 {row}번째",
    "RUN_PANEL_STATS": "성공: {ok}  |  실패: {failed}",
    "RUN_PANEL_INIT": "준비 중...",
    "RUN_PANEL_STARTING": "실행을 시작합니다...",
    "RUN_PANEL_EXECUTING_ROW": "엑셀 {row}행 처리 중",
    "RUN_PANEL_NEXT": "다음 ⏭",
    "RUN_PANEL_F12": "⛔ 멈추려면 F12",
    "SPEED_NORMAL": "보통",
    "SPEED_SLOW": "느리게",
    "SPEED_VERY_SLOW": "매우 느리게",
    "PREFLIGHT_TITLE": '"{name}" 실행 준비',
    "PREFLIGHT_INFO": "<b>매크로:</b> {name} &nbsp;|&nbsp; <b>데이터:</b> {data} ({rows}줄)",
    "PREFLIGHT_NO_DATA": "데이터 없음",
    "PREFLIGHT_DIAGNOSTICS": "실행 전 점검 결과",
    "PREFLIGHT_OPTIONS": "실행 옵션",
    "PREFLIGHT_START_ROW": "시작 순번:",
    "PREFLIGHT_SPEED": "실행 속도:",
    "PREFLIGHT_SPEED_NORMAL": "보통",
    "PREFLIGHT_SPEED_SLOW": "느리게 (+0.5초)",
    "PREFLIGHT_SPEED_VERY_SLOW": "매우 느리게 (+1초)",
    "PREFLIGHT_SKIP_SETUP": "① 시작 단계 건너뛰기",
    "PREFLIGHT_SKIP_CLEANUP": "③ 마무리 단계 건너뛰기",
    "PREFLIGHT_WORKFLOW": "실행 방식:",
    "PREFLIGHT_CLICK_START": "[실행 시작]을 누르면 카운트다운 후 실행됩니다.",
    "PREFLIGHT_BLOCKED": "⚠ 위의 오류를 먼저 해결해야 실행할 수 있습니다.",
    "PREFLIGHT_RUN_1_ROW": "1줄만 테스트",
    "PREFLIGHT_START": "실행 시작",
    "PREFLIGHT_COUNTDOWN": "{seconds}초 후 시작합니다... 지금 대상 창으로 전환하세요.",
    "PREFLIGHT_ALL_PASSED": "✅ 모든 점검을 통과했습니다.",
    "PREFLIGHT_ERROR_PREFIX": "🔴 오류: ",
    "PREFLIGHT_WARNING_PREFIX": "🟡 주의: ",
    "CANCEL": "취소",
    "KEY_UNKNOWN_WARNING": "⚠ 알 수 없는 키 이름입니다. 아래 버튼을 눌러보세요.",
    "WAIT_CHIP": "{seconds}초",
    "ADVANCED_SAFETY_TOGGLE": "고급: 화면 확인",
    "ADVANCED_SAFETY_TOGGLE_TIP": "이 단계 전(Guard)·후(Verify)에 화면을 확인하는 선택 기능입니다.",
    "SAFETY_BOX_TITLE": "🛡️ 화면 확인 (Guard / Verify)",
    "PARAMETERS_TITLE": "{type} 설정",
    "CAPTURE_BANNER_PICK": "위치를 한 번 클릭하세요 · Esc 취소",
    "CAPTURE_BANNER_REGION": "캡처할 영역을 드래그하세요 · Esc 취소",
    "CAPTURE_BANNER_ELEMENT": "파란 테두리를 확인하고 클릭하세요 · Esc 취소",
    "TYPE_WINDOW_SET_BOUNDS": "창 위치·크기",
    "SUMMARY_CLICK_XY": "{sim}{double}클릭 ({x}, {y}){button}",
    "SUMMARY_CLICK_SELECTOR": '{sim}🎯 [{control}] "{ident}" {double}클릭{button}',
    "SUMMARY_SIM_BADGE": "⚡백그라운드 ",
    "SUMMARY_DOUBLE": "더블",
    "SUMMARY_BUTTON": " ({button} 버튼)",
    "SUMMARY_ELEMENT": "요소",
    "SUMMARY_TARGET": "대상",
    "SUMMARY_CLICK_IMAGE": '"{image}" 이미지 클릭',
    "SUMMARY_TYPE": '"{text}" 입력{mode}',
    "SUMMARY_TYPE_KEYSTROKES": " [직접 타이핑]",
    "SUMMARY_KEY": '"{keys}" 키 누르기{repeat}',
    "SUMMARY_KEY_REPEAT": " ({count}회)",
    "SUMMARY_WAIT": "{seconds}초 기다리기",
    "SUMMARY_WAIT_IMAGE": '"{image}" 나타날 때까지 기다리기 (최대 {timeout}초)',
    "SUMMARY_WAIT_IMAGE_GONE": '"{image}" 사라질 때까지 기다리기',
    "SUMMARY_WINDOW_MAXIMIZE": '"{title}" 창 최대화',
    "SUMMARY_WINDOW_BOUNDS": '"{title}" 창을 ({x}, {y}) 위치, {width}x{height} 크기로',
    "SUMMARY_NO_WINDOW": "(창 미지정)",
    "SUMMARY_GROUP": "그룹: {name} ({count}단계)",
    "MOUSE_LEFT": "왼쪽",
    "MOUSE_RIGHT": "오른쪽",
    "MOUSE_MIDDLE": "가운데",
    "STEP_WARN_EMPTY_TEXT": "⚠ 입력할 글자를 적어주세요",
    "STEP_WARN_EMPTY_KEYS": "⚠ 누를 키를 정해주세요",
    "STEP_WARN_EMPTY_IMAGE": "⚠ 찾을 이미지를 캡처해주세요",
    "CTX_ADD_TO": "+ {target}에 동작 추가",
    "CTX_ADD_CLICK": "👆 클릭 추가",
    "CTX_ADD_TYPE": "⌨ 텍스트 입력 추가",
    "CTX_ADD_KEY": "↵ 키 입력 추가",
    "CTX_ADD_WAIT": "⏱ 대기 추가",
    "CTX_ADD_IMAGE": "🖼 이미지 클릭 추가",
    "CTX_ADD_WINDOW": "🪟 창 위치·크기 맞추기 추가",
    "CTX_MOVE_TO_SECTION": "다른 구역으로 이동",
    "CTX_MOVE_TO_SETUP": "① 시작할 때 1번 구역으로",
    "CTX_MOVE_TO_PER_ROW": "② 각 줄마다 반복 구역으로",
    "CTX_MOVE_TO_CLEANUP": "③ 끝날 때 1번 구역으로",
    "TARGET_SECTION_SETUP": "① 시작",
    "TARGET_SECTION_PER_ROW": "② 반복",
    "TARGET_SECTION_CLEANUP": "③ 마무리",
    "NO_MACRO_LOADED": "🎯 열린 매크로가 없습니다",
}

_KO_TOOLTIPS: dict[str, str] = {
    "RUN": Strings.Tooltips.card(
        "매크로 실행",
        "불러온 데이터의 모든 행에 대해 매크로 워크플로우를 순차적으로 실행합니다.",
        shortcut="F5",
        tip="실행 중 언제든 F12를 누르면 0.01초 내 즉시 비상 정지됩니다.",
    ),
    "PAUSE": Strings.Tooltips.card(
        "일시정지 / 재개",
        "현재 실행 중인 스텝이 끝난 직후 매크로를 잠시 멈춥니다.",
        tip="대상 화면을 점검한 후 다시 이어서 실행할 수 있습니다.",
    ),
    "STOP": Strings.Tooltips.card(
        "실행 정지",
        "실행 중인 자동화를 즉시 안전하게 중단하고 결과 CSV를 저장합니다.",
        shortcut="F12",
        tip="나중에 멈춘 행부터 이어서 실행(Resume)할 수 있습니다.",
    ),
    "SCHEDULE": Strings.Tooltips.card(
        "야간 무인 예약 실행 (Armed Mode)",
        "Cloud PC가 잠들지 않게 유지하면서 지정한 야간/새벽 시각에 매크로를 자동 실행합니다.",
        tip="퇴근 전 켜두고 주무시면 아침 출근 시 결과 리포트를 확인할 수 있습니다.",
    ),
    "STEP_BY_STEP": Strings.Tooltips.card(
        "단계별 실행",
        "한 번에 한 스텝씩 실행하며 사용자의 확인을 거쳐 진행합니다.",
        tip="새로 만든 매크로를 안전하게 디버깅할 때 유용합니다.",
    ),
    "TEST_1_ROW": Strings.Tooltips.card(
        "1줄 테스트",
        "선택한 데이터 행(없으면 첫 번째 행) 1줄에 대해서만 매크로 전체를 실행해 봅니다.",
        tip="짧은 카운트다운 동안 대상 창으로 전환하세요.",
    ),
    "SAVE_MACRO": Strings.Tooltips.card(
        "매크로 패키지 저장",
        "현재 매크로 스텝과 캡처된 이미지 에셋을 .swm 파일 하나로 묶어 저장합니다.",
        shortcut="Ctrl+S",
    ),
    "SETTINGS": Strings.Tooltips.card(
        "환경 설정",
        "언어(한/영), 테마(다크/라이트), 기본 대기 시간, 저장 폴더 등을 설정합니다.",
    ),
    "SECTION_SETUP": Strings.Tooltips.card(
        "SETUP 구역 (최초 1회 실행)",
        "매크로 시작 시 맨 처음 딱 한 번만 실행되는 초기화 구역입니다.",
        tip="ERP 창 정렬, 메뉴 진입, 초기 조회 화면 열기 등에 사용하세요.",
    ),
    "SECTION_PER_ROW": Strings.Tooltips.card(
        "PER ROW 구역 (데이터 행별 반복)",
        "엑셀/CSV 파일의 각 행마다 반복 실행되는 핵심 전표/데이터 입력 루프입니다.",
        tip="[열 이름] 변수를 사용해 행별 데이터를 자동으로 타이핑하세요.",
    ),
    "SECTION_CLEANUP": Strings.Tooltips.card(
        "CLEANUP 구역 (종료 전 1회 실행)",
        "모든 데이터 행 처리가 끝난 후 마지막에 한 번 실행되는 마무리 구역입니다.",
        tip="트랜잭션 닫기나 초기 화면 복귀 등에 사용하세요.",
    ),
    "ADD_CLICK": Strings.Tooltips.card(
        "클릭 스텝 추가 (좌표 / UI Selector / Simulate)",
        "화면 좌표 클릭 또는 UI 요소(버튼/입력창) 클릭 동작을 추가합니다.",
        tip="속성창에서 UI Selector와 Simulate Click(백그라운드 클릭)을 설정할 수 있습니다.",
    ),
    "ADD_TYPE": Strings.Tooltips.card(
        "텍스트 입력 스텝 추가",
        "고정 문자열이나 엑셀 데이터의 [열 이름] 변수를 입력하는 동작을 추가합니다.",
        tip="클립보드 붙여넣기 또는 유니코드 타이핑 방식을 선택할 수 있습니다.",
    ),
    "ADD_KEY": Strings.Tooltips.card(
        "키 입력 스텝 추가",
        "Enter, Tab, Esc 또는 단축키(Ctrl+S 등)를 누르는 동작을 추가합니다.",
        tip="입력 칸 이동이나 팝업 확인에 사용하세요.",
    ),
    "ADD_WAIT": Strings.Tooltips.card(
        "대기(Wait) 스텝 추가",
        "화면 로딩이나 서버 응답을 기다리기 위해 지정한 초(s)만큼 대기합니다.",
    ),
    "ADD_WINDOW": Strings.Tooltips.card(
        "창 위치/크기 고정 추가",
        "대상 프로그램 창을 지정한 위치(예: 0,0)와 크기로 자동 정렬합니다.",
        tip="SETUP 구역 첫 스텝으로 넣으면 모니터가 바뀌어도 좌표가 어긋나지 않습니다.",
    ),
    "DELETE_ACTION": Strings.Tooltips.card(
        "동작 삭제",
        "선택한 동작이나 그룹을 트리에서 삭제합니다.",
        shortcut="Del",
    ),
    "PICK_COORDS": Strings.Tooltips.card(
        "화면 좌표 지정 (F8)",
        "화면을 클릭하여 물리 픽셀 기준 (X, Y) 좌표를 즉시 가져옵니다.",
        shortcut="F8",
        tip="해상도 및 DPI 배율이 자동 보정됩니다.",
    ),
    "PICK_UI_ELEMENT": Strings.Tooltips.card(
        "UI 요소 선택 (UI Selector)",
        "마우스를 버튼이나 입력창 위에 올리고 클릭하여 Windows UI Automation 식별자를 추출합니다.",
        shortcut="Ctrl+F8",
        tip="창 위치가 조금 이동해도 요소를 정확히 찾으며 Simulate Click을 지원합니다.",
    ),
    "CAPTURE_IMAGE": Strings.Tooltips.card(
        "화면 정지 후 영역 캡처 (F9)",
        "화면을 일시 정지시킨 뒤 마우스 드래그로 버튼이나 아이콘 이미지를 캡처합니다.",
        shortcut="F9",
        tip="Guard(사전 확인), Verify(사후 확인), 이미지 클릭에 사용됩니다.",
    ),
    "SHOW_ON_SCREEN": Strings.Tooltips.card(
        "화면에서 타겟 위치 보기",
        "실제로 클릭하지 않고 대상 좌표나 UI 요소 위치에 십자선/하이라이트만 표시합니다.",
        tip="실행 전 타겟이 정확한지 안전하게 확인하세요.",
    ),
    "TEST_THIS_STEP": Strings.Tooltips.card(
        "이 스텝만 즉시 실행 테스트",
        "현재 선택한 단일 스텝만 실제 화면에 즉시 실행해 봅니다.",
        tip="주의: 실제 클릭이나 텍스트 입력이 수행됩니다.",
    ),
    "TEST_MATCH": Strings.Tooltips.card(
        "이미지 매칭 테스트",
        "현재 화면에서 캡처된 템플릿 이미지를 찾을 수 있는지 즉시 검사하고 정확도 점수를 표시합니다.",
    ),
    "GUARD_CHECK": Strings.Tooltips.card(
        "사전 화면 확인 (Guard)",
        "이 동작을 실행하기 전에 특정 창이나 아이콘이 화면에 떠 있는지 먼저 확인합니다.",
        tip="네트워크 지연이나 로딩 중 엉뚱한 곳을 클릭하는 사고를 예방합니다.",
    ),
    "VERIFY_CHECK": Strings.Tooltips.card(
        "사후 결과 검증 (Verify)",
        "동작 실행 후 '저장 완료' 메시지나 예상 화면이 정상적으로 떴는지 검증합니다.",
        tip="전표가 확실히 저장된 것을 확인한 뒤 다음 행으로 넘어갑니다.",
    ),
    "CHOOSE_DATA_FILE": Strings.Tooltips.card(
        "데이터 파일 불러오기",
        "반복 입력에 사용할 Excel(.xlsx) 또는 CSV 파일을 연결합니다.",
        tip="원본 파일은 읽기 전용으로만 열리며 절대 수정되지 않습니다.",
    ),
    "VARIABLE_BUTTON": Strings.Tooltips.card(
        "컬럼 변수 삽입",
        "현재 선택된 텍스트 입력 칸에 해당 열의 변수를 삽입합니다.",
        tip="실행 시 각 행의 실제 셀 값으로 자동 치환됩니다.",
    ),
}


def get_current_language() -> str:
    """Return active language code ('ko' or 'en')."""
    return _CURRENT_LANG


def apply_language(lang: str = "en") -> str:
    """Switch Strings and Strings.Tooltips attributes between English ('en') and Korean ('ko')."""
    global _CURRENT_LANG
    normalized = "ko" if str(lang).lower().startswith("ko") else "en"
    _CURRENT_LANG = normalized

    target_strings = _KO_STRINGS if normalized == "ko" else _EN_STRINGS
    target_tooltips = _KO_TOOLTIPS if normalized == "ko" else _EN_TOOLTIPS

    for key, val in _EN_STRINGS.items():
        setattr(Strings, key, target_strings.get(key, val))

    for key, val in _EN_TOOLTIPS.items():
        setattr(Strings.Tooltips, key, target_tooltips.get(key, val))

    return normalized


_ACTION_TYPE_KEYS = {
    "click": "TYPE_CLICK",
    "click_image": "TYPE_CLICK_IMAGE",
    "type_text": "TYPE_TYPE_TEXT",
    "key": "TYPE_KEY",
    "wait": "TYPE_WAIT",
    "wait_image": "TYPE_WAIT_IMAGE",
    "wait_image_gone": "TYPE_WAIT_IMAGE_GONE",
    "group": "TYPE_GROUP",
    "window_set_bounds": "TYPE_WINDOW_SET_BOUNDS",
}


def action_type_label(action_type: str) -> str:
    """Friendly action type name in Korean; English keeps the raw type id."""
    if _CURRENT_LANG != "ko":
        return action_type
    key = _ACTION_TYPE_KEYS.get(action_type)
    return getattr(Strings, key) if key else action_type


# Canonical internal status codes -> localized display text helper
STATUS_CANONICAL_CODES = ("Pending", "Running", "Done", "Failed", "Interrupted", "Skipped")


def normalize_status_code(status: str) -> str:
    """Normalize either a canonical status code or localized status label back to canonical English."""
    s = str(status).strip()
    mapping = {
        "Pending": "Pending",
        Strings.STATUS_PENDING: "Pending",
        "대기중": "Pending",
        "Running": "Running",
        Strings.STATUS_RUNNING: "Running",
        "실행중": "Running",
        "Done": "Done",
        Strings.STATUS_DONE: "Done",
        "완료": "Done",
        "Failed": "Failed",
        Strings.STATUS_FAILED: "Failed",
        "실패": "Failed",
        "Interrupted": "Interrupted",
        Strings.STATUS_INTERRUPTED: "Interrupted",
        "중단됨": "Interrupted",
        "Skipped": "Skipped",
        Strings.STATUS_SKIPPED: "Skipped",
        "건너뜀": "Skipped",
    }
    if s in mapping:
        return mapping[s]
    for code in STATUS_CANONICAL_CODES:
        if code.lower() in s.lower():
            return code
    return s


def format_status_display(status_code: str) -> str:
    """Return display string for a status code while keeping canonical codes in EN mode."""
    canonical = normalize_status_code(status_code)
    if _CURRENT_LANG != "ko":
        return canonical
    display_map = {
        "Pending": Strings.STATUS_PENDING,
        "Running": Strings.STATUS_RUNNING,
        "Done": Strings.STATUS_DONE,
        "Failed": Strings.STATUS_FAILED,
        "Interrupted": Strings.STATUS_INTERRUPTED,
        "Skipped": Strings.STATUS_SKIPPED,
    }
    return display_map.get(canonical, status_code)
