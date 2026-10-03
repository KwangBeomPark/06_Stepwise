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

    # Sections
    SECTION_SETUP = "SETUP (runs once)"
    SECTION_PER_ROW = "PER ROW (runs for each data row)"
    SECTION_CLEANUP = "CLEANUP (runs once at the end)"

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
    SCREEN_MISMATCH = "Screen {w}x{h} @{scale}% ⚠ differs from macro ({rec_w}x{rec_h} @{rec_scale}%)"
    STATUS_READY = "Ready"

    # Dialogs & Prompts
    CONFIRM_DELETE = "Are you sure you want to delete this action?"
    CONFIRM_DISCARD_CHANGES = "You have unsaved changes. Discard them?"
    RECOVERY_FOUND_TITLE = "Auto-Recovery Available"
    RECOVERY_FOUND_MSG = "Stepwise recovered an unsaved macro from a previous session. Would you like to restore it?"
    PASSWORD_WARNING = "Never enter passwords or secrets into macro actions."
