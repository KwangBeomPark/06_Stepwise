"""Centralized English UI strings for Stepwise (Section 0.1 Rule 4).

All user-facing strings must be defined here rather than hardcoded in widgets.
"""

from __future__ import annotations


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
    STEP_BY_STEP = "Step-by-step"
    DATA_FILE = "Data:"
    NO_DATA = "No data connected"
    SETTINGS = "Settings"
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
    SECTION_SETUP = "SETUP (runs once)"
    SECTION_PER_ROW = "PER ROW (runs for each data row)"
    SECTION_CLEANUP = "CLEANUP (runs once at the end)"
    SECTION_EMPTY_PLACEHOLDER = "(Empty — select to add action here)"
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
    ADD_ACTION = "+ Add action"
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
    NO_ACTION_SELECTED = "Select an action in the tree to view and edit its properties."
    PROPERTIES_GUIDE = (
        "<b>💡 Quick Start Guide:</b><br><br>"
        "1. Click <b>[+ Click]</b> or <b>[+ Type]</b> below the Action Tree.<br>"
        "2. Select the added step in the tree to configure coordinates or text.<br>"
        "3. Use <b>[Pick (F8)]</b> to capture screen coordinates directly by clicking.<br>"
        "4. Switch to <b>Data Preview</b> tab to load an Excel/CSV file and use <code>{Variables}</code>."
    )
    COORD_X = "X coordinate:"
    COORD_Y = "Y coordinate:"
    BUTTON = "Mouse button:"
    CLICKS = "Clicks:"
    TEXT_TO_TYPE = "Text to type:"
    TYPE_MODE = "Typing mode:"
    MODE_PASTE = "Paste (Clipboard)"
    MODE_KEYSTROKES = "Keystrokes (Unicode)"
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
    ENABLE_GUARD = "Enable Guard"
    ENABLE_VERIFY = "Enable Verify"

    # Data Panel
    DATA_PANEL_TITLE = "Data Preview"
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

    # Status Bar
    SCREEN_MATCH = "Screen {w}x{h} @{scale}% ✅ matches macro"
    SCREEN_MISMATCH = (
        "Screen {w}x{h} @{scale}% ⚠ differs from macro ({rec_w}x{rec_h} @{rec_scale}%)"
    )
    STATUS_READY = "Ready"

    # Dialogs & Prompts
    CONFIRM_DELETE = "Are you sure you want to delete this action?"
    CONFIRM_DISCARD_CHANGES = "You have unsaved changes. Discard them?"
    RECOVERY_FOUND_TITLE = "Auto-Recovery Available"
    RECOVERY_FOUND_MSG = (
        "Stepwise recovered an unsaved macro from a previous session. Would you like to restore it?"
    )
    PASSWORD_WARNING = "Never enter passwords or secrets into macro actions."

    class Tooltips:
        """Centralized rich HTML tooltips (SuperTips) for key UI interactions."""

        @staticmethod
        def card(title: str, desc: str, shortcut: str | None = None, tip: str | None = None) -> str:
            """Generate a sleek, enterprise-grade rich HTML tooltip (SuperTip)."""
            html = (
                "<div style=\"font-family: 'Segoe UI', -apple-system, sans-serif; "
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
        STEP_BY_STEP = card(
            "Step-by-step Execution",
            "Runs the workflow one action at a time with manual approval for each step.",
            tip="Perfect for debugging and verifying new macros safely.",
        )
        SAVE_MACRO = card(
            "Save Macro Package",
            "Saves the current macro steps and embedded image assets into a .swm file.",
            shortcut="Ctrl+S",
        )
        SETTINGS = card(
            "Application Settings",
            "Configure speed profiles, screen capture preferences, and safety timeouts.",
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
            tip="Insert {Column} variables here to automatically type spreadsheet values.",
        )
        SECTION_CLEANUP = card(
            "CLEANUP Section (Runs Once at End)",
            "Actions placed here run once after all spreadsheet rows have finished processing.",
            tip="Use for closing screens, committing batch notes, or cleanup.",
        )

        # Quick Action Buttons
        ADD_CLICK = card(
            "Add Mouse Click",
            "Appends a mouse click step to the active section.",
            tip="Use F8 in Properties to pick screen coordinates directly by clicking.",
        )
        ADD_TYPE = card(
            "Add Text Input",
            "Appends a text typing action to the active section.",
            tip="Supports plain text as well as dynamic {Column} variables.",
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
            "Turns cursor into a red crosshair so you can click any point on your screen.",
            shortcut="F8",
            tip="Coordinates are captured based on your physical display resolution.",
        )
        CAPTURE_IMAGE = card(
            "Screen Freeze & Capture",
            "Freezes the display and lets you drag a box around a button, icon, or text.",
            shortcut="F9",
            tip="Used for visual template matching (Guard, Verify, Wait for Image).",
        )
        SHOW_ON_SCREEN = card(
            "Show Target on Screen",
            "Briefly flashes a high-visibility crosshair at the configured coordinates.",
            tip="Quickly verify target position without clicking it.",
        )
        TEST_THIS_STEP = card(
            "Test This Step",
            "Executes only this single action immediately on your active screen.",
            tip="Validate click position or typing mode safely.",
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
