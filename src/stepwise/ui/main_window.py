"""Main Application Window implementing Section 12.1 specifications.

Assembles:
- Macro Library panel (left)
- 3-Section Action Tree and manipulation tools (center)
- Properties editor and Data preview panels (bottom/tabs)
- Primary Toolbar ([Run], [Pause], [Stop], [Settings])
- In-App Shortcuts (Ctrl+S, Ctrl+O, F5, Del)
- Pick (F8) and Capture (F9) overlay integration
- Runner thread with FloatingRunPanel, PreflightDialog, and RunSummaryDialog
"""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from stepwise.core.app_paths import (
    default_library_directory,
    default_results_directory,
    load_user_settings,
    save_user_settings,
)
from stepwise.core.models import ActionItem, DataSourceConfig, Macro
from stepwise.core.package import load_package, save_package
from stepwise.engine.errors import StepFailure
from stepwise.engine.preflight import run_preflight_checks
from stepwise.engine.runner import ExecutionCallbacks, RunSummary, run_macro
from stepwise.engine.timing import ExecutionController, SpeedMode
from stepwise.services.hotkeys import GlobalHotkeyManager
from stepwise.services.input_win import VK_MAP
from stepwise.services.jiggler import safe_jiggler_interval
from stepwise.services.screen import get_screen_info
from stepwise.ui.action_tree import ActionTreeWidget
from stepwise.ui.capture_overlay import CaptureOverlay
from stepwise.ui.data_panel import DataPanel
from stepwise.ui.macro_library import MacroLibraryPanel
from stepwise.ui.preflight_dialog import PreflightDialog, localize_issue
from stepwise.ui.properties_panel import PropertiesPanel
from stepwise.ui.run_panel import FloatingRunPanel
from stepwise.ui.run_summary import RunSummaryDialog
from stepwise.ui.scheduler_dialog import SchedulerDialog
from stepwise.ui.screen_crosshair import ElementHighlightOverlay, ScreenCrosshairOverlay
from stepwise.ui.settings_dialog import SettingsDialog
from stepwise.ui.strings import Strings, apply_language, get_current_language, normalize_status_code
from stepwise.ui.theme import apply_theme, get_current_theme, get_theme_tokens


class RunnerBridge(QObject):
    event = Signal(str, str, object)  # run token, event name, arguments


@dataclass(frozen=True)
class ExecutionSnapshot:
    macro: Macro
    rows: tuple[dict[str, str], ...]
    row_numbers: tuple[int, ...]
    package_dir: str
    data_filepath: str | None
    results_dir: str
    speed: SpeedMode
    start_row_index: int
    end_row_index: int | None
    skip_setup: bool
    skip_cleanup: bool
    run_1_row: bool
    countdown_seconds: float = 0.0
    anti_lock_jiggler: bool = False
    jiggler_interval_seconds: float = 45.0


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, library_dir: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(Strings.APP_TITLE)
        self.resize(1200, 800)

        # Persistent user settings
        self._user_settings = load_user_settings()
        if library_dir:
            self._library_dir = library_dir
        else:
            self._library_dir = self._user_settings.get("library_dir") or str(
                default_library_directory()
            )

        self._current_macro: Macro = Macro()
        self._current_macro_path: str | None = None
        self._package_temp = tempfile.TemporaryDirectory(prefix="stepwise_pkg_")
        self._package_dir = self._package_temp.name
        self._data_filepath: str | None = None
        self._data_headers: list[str] = []
        self._data_rows: list[dict[str, str]] = []
        self._data_row_nums: list[int] = []
        self._row_status_overrides: dict[int, str] = {}
        self._run_total_rows = 0
        self._run_row_index = 0

        self._controller: ExecutionController | None = None
        self._hotkey_mgr: GlobalHotkeyManager | None = None
        self._worker_thread: threading.Thread | None = None
        self._is_running = False
        self._execution_phase = "idle"
        self._run_token: str | None = None
        self._pending_summary: RunSummary | None = None
        self._retained_summaries: list[RunSummary] = []
        self._close_requested = False
        self._last_run_opts: dict[str, Any] = {}
        self._saved_snapshot = self._macro_snapshot_json()

        # "Test this step" countdown so the click/typing does not land on Stepwise itself
        self._step_test_pending = False
        self._step_test_action: ActionItem | None = None
        self._step_test_remaining = 0
        self._step_test_timer = QTimer(self)
        self._step_test_timer.setInterval(1000)
        self._step_test_timer.timeout.connect(self._on_step_test_tick)

        self._bridge = RunnerBridge()
        self._bridge.event.connect(self._on_runner_event, Qt.QueuedConnection)

        self.floating_panel = FloatingRunPanel()
        self.floating_panel.pause_clicked.connect(self._pause_run)
        self.floating_panel.resume_clicked.connect(self._resume_run)
        self.floating_panel.stop_clicked.connect(self._stop_run)
        self.floating_panel.next_step_clicked.connect(self._next_step)

        self._setup_ui()
        self._setup_shortcuts()
        self._update_status_bar_screen_info()

        # Restore saved window geometry if present
        if self._user_settings.get("window_geometry"):
            try:
                self.restoreGeometry(bytes.fromhex(self._user_settings["window_geometry"]))
                # Guard against disconnected monitors (off-screen prevention)
                screen = self.screen()
                if screen:
                    avail = screen.availableGeometry()
                    if not avail.intersects(self.geometry()):
                        self.setGeometry(avail.adjusted(50, 50, -50, -50))
            except Exception:
                pass

        # Set window icon
        icon_path = os.path.join(os.path.dirname(__file__), "stepwise.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Check for updates in background 15s after launch if enabled
        if self._user_settings.get("auto_check_updates", True):
            QTimer.singleShot(15000, self._check_updates_background)

    def _setup_ui(self) -> None:
        self._setup_menu_bar()

        # Toolbar
        self.toolbar = QToolBar("Main Controls")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self.btn_run = QPushButton(f"▶ {Strings.RUN}")
        self.btn_run.setObjectName("btn_run")
        self.btn_run.setToolTip(Strings.Tooltips.RUN)
        self.btn_run.clicked.connect(self._on_run_clicked)
        self.toolbar.addWidget(self.btn_run)

        self.btn_test_1_row = QPushButton(Strings.TEST_1_ROW)
        self.btn_test_1_row.setObjectName("btn_test_1_row")
        self.btn_test_1_row.setToolTip(Strings.Tooltips.TEST_1_ROW)
        self.btn_test_1_row.clicked.connect(self._on_test_1_row_clicked)
        self.toolbar.addWidget(self.btn_test_1_row)

        self.btn_pause = QPushButton(f"⏸ {Strings.PAUSE}")
        self.btn_pause.setObjectName("btn_pause")
        self.btn_pause.setToolTip(Strings.Tooltips.PAUSE)
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._pause_run)
        self.toolbar.addWidget(self.btn_pause)

        self.btn_stop = QPushButton(f"■ {Strings.STOP}")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setToolTip(Strings.Tooltips.STOP)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_run)
        self.toolbar.addWidget(self.btn_stop)

        self.toolbar.addSeparator()

        self.btn_save = QPushButton(f"💾 {Strings.SAVE_MACRO}")
        self.btn_save.setToolTip(Strings.Tooltips.SAVE_MACRO)
        self.btn_save.clicked.connect(self.save_current_macro)
        self.toolbar.addWidget(self.btn_save)

        self.btn_schedule = QPushButton(f"⏰ {Strings.SCHEDULE}")
        self.btn_schedule.setObjectName("btn_schedule")
        self.btn_schedule.setToolTip(Strings.Tooltips.SCHEDULE)
        self.btn_schedule.clicked.connect(self._open_scheduler)
        self.toolbar.addWidget(self.btn_schedule)

        self.toolbar.addSeparator()

        self.btn_theme = QPushButton(
            Strings.THEME_DARK if get_current_theme() == "dark" else Strings.THEME_LIGHT
        )
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.clicked.connect(self._toggle_theme)
        self.toolbar.addWidget(self.btn_theme)

        self.btn_lang = QPushButton(
            Strings.LANG_KO if get_current_language() == "ko" else Strings.LANG_EN
        )
        self.btn_lang.setObjectName("btn_lang")
        self.btn_lang.clicked.connect(self._toggle_language)
        self.toolbar.addWidget(self.btn_lang)

        self.btn_settings = QPushButton(f"⚙ {Strings.SETTINGS}")
        self.btn_settings.setToolTip(Strings.Tooltips.SETTINGS)
        self.btn_settings.clicked.connect(self._open_settings)
        self.toolbar.addWidget(self.btn_settings)

        # Splitters
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.setCentralWidget(self.main_splitter)

        self.lib_panel = MacroLibraryPanel(self._library_dir)
        self.lib_panel.setMinimumWidth(180)
        self.lib_panel.macro_selected.connect(self._on_library_macro_selected)
        self.lib_panel.macro_created.connect(self._on_macro_created)
        self.lib_panel.before_create = self._confirm_new_macro
        self.lib_panel.before_prompt = self._cancel_step_test
        self.main_splitter.addWidget(self.lib_panel)

        self.center_splitter = QSplitter(Qt.Vertical)
        self.center_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.center_splitter)

        tree_container = QWidget()
        tree_container.setMinimumHeight(200)
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(8, 8, 8, 8)
        tree_layout.setSpacing(6)

        self.action_tree = ActionTreeWidget()
        self.action_tree.action_selected.connect(self._on_action_selected)
        self.action_tree.request_add_action.connect(self._on_request_add_action)
        self.action_tree.request_move_section.connect(self._on_request_move_section)
        self.action_tree.request_delete_action.connect(self._on_request_delete_action)
        self.action_tree.request_duplicate_action.connect(self._on_request_duplicate_action)
        self.action_tree.request_move_up.connect(self._on_request_move_up)
        self.action_tree.request_move_down.connect(self._on_request_move_down)
        self.action_tree.macro_modified.connect(self._update_window_title)
        tree_layout.addWidget(self.action_tree)

        action_btn_layout = QHBoxLayout()
        action_btn_layout.setSpacing(8)

        t = get_theme_tokens()
        self.lbl_add_action = QLabel(Strings.ADD_ACTION_LABEL)
        self.lbl_add_action.setStyleSheet(f"font-weight: bold; color: {t['text_secondary']};")
        action_btn_layout.addWidget(self.lbl_add_action)

        self.btn_add_click = QPushButton(Strings.BTN_ADD_CLICK)
        self.btn_add_click.setToolTip(Strings.Tooltips.ADD_CLICK)
        self.btn_add_click.clicked.connect(lambda: self._add_quick_action("click"))

        self.btn_add_type = QPushButton(Strings.BTN_ADD_TYPE)
        self.btn_add_type.setToolTip(Strings.Tooltips.ADD_TYPE)
        self.btn_add_type.clicked.connect(lambda: self._add_quick_action("type_text"))

        self.btn_add_key = QPushButton(Strings.BTN_ADD_KEY)
        self.btn_add_key.setToolTip(Strings.Tooltips.ADD_KEY)
        self.btn_add_key.clicked.connect(lambda: self._add_quick_action("key"))

        self.btn_add_wait = QPushButton(Strings.BTN_ADD_WAIT)
        self.btn_add_wait.setToolTip(Strings.Tooltips.ADD_WAIT)
        self.btn_add_wait.clicked.connect(lambda: self._add_quick_action("wait"))

        self.btn_add_win = QPushButton(Strings.BTN_ADD_WIN)
        self.btn_add_win.setToolTip(Strings.Tooltips.ADD_WINDOW)
        self.btn_add_win.clicked.connect(lambda: self._add_quick_action("window_set_bounds"))

        self.btn_move_up = QPushButton(Strings.MOVE_UP)
        self.btn_move_up.setToolTip("Move selected step up within section (Alt+Up)")
        self.btn_move_up.clicked.connect(self._on_move_up_clicked)

        self.btn_move_down = QPushButton(Strings.MOVE_DOWN)
        self.btn_move_down.setToolTip("Move selected step down within section (Alt+Down)")
        self.btn_move_down.clicked.connect(self._on_move_down_clicked)

        self.btn_delete = QPushButton(f"🗑 {Strings.DELETE}")
        self.btn_delete.setToolTip(Strings.Tooltips.DELETE_ACTION)
        self.btn_delete.clicked.connect(self._on_delete_action)

        action_btn_layout.addWidget(self.btn_add_click)
        action_btn_layout.addWidget(self.btn_add_type)
        action_btn_layout.addWidget(self.btn_add_key)
        action_btn_layout.addWidget(self.btn_add_wait)
        action_btn_layout.addWidget(self.btn_add_win)
        action_btn_layout.addSpacing(8)
        action_btn_layout.addWidget(self.btn_move_up)
        action_btn_layout.addWidget(self.btn_move_down)
        action_btn_layout.addSpacing(8)
        action_btn_layout.addWidget(self.btn_delete)
        action_btn_layout.addStretch()
        tree_layout.addLayout(action_btn_layout)

        self.center_splitter.addWidget(tree_container)

        # Center Bottom: Data Preview (Wide horizontal table)
        self.data_panel = DataPanel()
        self.data_panel.setMinimumHeight(150)
        self.data_panel.data_loaded.connect(self._on_data_loaded)
        self.data_panel.before_prompt = self._cancel_step_test
        self.data_panel.insert_variable_requested.connect(self._insert_variable_into_current_action)
        self.data_panel.row_status_override.connect(self._on_row_status_override)
        self.data_panel.run_only_row_requested.connect(self._on_run_only_row)
        self.center_splitter.addWidget(self.data_panel)

        # Right Column: Properties Panel (Full-height vertical inspector)
        self.prop_panel = PropertiesPanel()
        self.prop_panel.before_prompt = self._cancel_step_test
        self.prop_panel.property_changed.connect(self._on_property_changed)
        self.prop_panel.request_pick.connect(self._trigger_pick_overlay)
        self.prop_panel.request_pick_element.connect(self._trigger_element_pick_overlay)
        self.prop_panel.request_validate_selector.connect(self._validate_and_highlight_selector)
        self.prop_panel.request_locate_target.connect(self._locate_target_only)
        self.prop_panel.request_open_data_file.connect(self.data_panel._on_choose_file)
        self.prop_panel.request_capture.connect(self._trigger_capture_overlay)
        self.prop_panel.request_show_crosshair.connect(self._show_screen_crosshair)
        self.prop_panel.request_test_step.connect(self._request_step_test)
        self.prop_panel.request_test_match.connect(self._test_image_match)
        self.prop_panel.setMinimumWidth(320)
        self.main_splitter.addWidget(self.prop_panel)

        # Layout Stretch Factors & Initial Sizes
        # main_splitter: [Left Library: 1] : [Center Tree & Data: 4] : [Right Properties: 2]
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 4)
        self.main_splitter.setStretchFactor(2, 2)
        self.main_splitter.setSizes([200, 750, 320])

        # center_splitter: [Upper Action Tree: 3] : [Lower Data Preview: 2]
        self.center_splitter.setStretchFactor(0, 3)
        self.center_splitter.setStretchFactor(1, 2)
        self.center_splitter.setSizes([450, 250])

        # Restore saved splitter states if present
        if self._user_settings.get("main_splitter_state"):
            try:
                self.main_splitter.restoreState(
                    bytes.fromhex(self._user_settings["main_splitter_state"])
                )
            except Exception:
                pass
        if self._user_settings.get("center_splitter_state"):
            try:
                self.center_splitter.restoreState(
                    bytes.fromhex(self._user_settings["center_splitter_state"])
                )
            except Exception:
                pass

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_screen_info = QLabel()
        self.status_bar.addPermanentWidget(self.lbl_screen_info)
        self.status_bar.showMessage(Strings.STATUS_READY)

        self.action_tree.load_macro(self._current_macro)
        self._update_run_button_text()

    def _setup_shortcuts(self) -> None:
        # Ctrl+S Save
        act_save = QAction("Save", self)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self.save_current_macro)
        self.addAction(act_save)

        # F5 Run
        act_run = QAction("Run", self)
        act_run.setShortcut(QKeySequence("F5"))
        act_run.triggered.connect(self._on_run_clicked)
        self.addAction(act_run)

        # Ctrl+F8 Pick UI Element
        act_pick_elem = QAction("Pick UI Element", self)
        act_pick_elem.setShortcut(QKeySequence("Ctrl+F8"))
        act_pick_elem.triggered.connect(self._trigger_element_pick_overlay)
        self.addAction(act_pick_elem)

        # F8 Pick coordinates / F9 Capture image (labels on the property buttons)
        self.act_pick_coords = QAction("Pick Coordinates", self)
        self.act_pick_coords.setShortcut(QKeySequence("F8"))
        self.act_pick_coords.triggered.connect(self._on_pick_shortcut)
        self.addAction(self.act_pick_coords)

        self.act_capture_image = QAction("Capture Image", self)
        self.act_capture_image.setShortcut(QKeySequence("F9"))
        self.act_capture_image.triggered.connect(self._on_capture_shortcut)
        self.addAction(self.act_capture_image)

    def _shortcut_target(self, supported_types: tuple[str, ...], hint: str) -> bool:
        if self._is_running or self._step_test_pending:
            self.status_bar.showMessage(Strings.SHORTCUT_BLOCKED_RUNNING, 3000)
            return False
        act = self.prop_panel._current_action
        if act is None or act.type not in supported_types:
            self.status_bar.showMessage(hint, 3000)
            return False
        return True

    def _on_pick_shortcut(self) -> None:
        if self._shortcut_target(("click",), Strings.SHORTCUT_PICK_UNSUPPORTED):
            self._trigger_pick_overlay()

    def _on_capture_shortcut(self) -> None:
        if self._shortcut_target(
            ("click_image", "wait_image", "wait_image_gone"),
            Strings.SHORTCUT_CAPTURE_UNSUPPORTED,
        ):
            self._trigger_capture_overlay()

    # --- Unsaved changes tracking -------------------------------------------------

    def _macro_snapshot_json(self) -> str:
        return json.dumps(self._current_macro.to_dict(), sort_keys=True)

    def _mark_saved(self) -> None:
        self._saved_snapshot = self._macro_snapshot_json()
        self._update_window_title()

    def is_dirty(self) -> bool:
        return self._macro_snapshot_json() != self._saved_snapshot

    def _is_pristine_macro(self) -> bool:
        """True for the untouched, never-saved macro Stepwise starts with."""
        macro = self._current_macro
        return (
            self._current_macro_path is None
            and not (macro.setup or macro.per_row or macro.cleanup)
            and macro.name == Macro().name
        )

    def _update_window_title(self) -> None:
        dirty = self.is_dirty()
        if self._current_macro_path is None and not dirty:
            self.setWindowTitle(Strings.APP_TITLE)
            return
        title = f"{Strings.APP_TITLE} - {self._current_macro.name}"
        self.setWindowTitle(f"{title} *" if dirty else title)

    def _prompt_unsaved_changes(self) -> QMessageBox.StandardButton:
        return QMessageBox.question(
            self,
            Strings.UNSAVED_CHANGES_TITLE,
            Strings.UNSAVED_CHANGES_MSG.format(name=self._current_macro.name),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

    def _confirm_discard_changes(self) -> bool:
        """Return True when it is safe to replace or close the current macro."""
        if not self.is_dirty():
            return True
        choice = self._prompt_unsaved_changes()
        if choice == QMessageBox.StandardButton.Save:
            return self.save_current_macro()
        return choice == QMessageBox.StandardButton.Discard

    def _on_library_macro_selected(self, swm_path: str) -> None:
        # Stop a pending step test before any modal prompt can let its timer fire.
        self._cancel_step_test()
        if self._is_running:
            self.lib_panel.select_path(self._current_macro_path, emit=False)
            return
        if not self._confirm_discard_changes():
            self.lib_panel.select_path(self._current_macro_path, emit=False)
            return
        self.load_macro_file(swm_path)

    def _confirm_new_macro(self) -> bool:
        """Asked by the library before it writes a new macro file to disk."""
        self._cancel_step_test()
        if self._is_running:
            return False
        return self._confirm_discard_changes()

    def _on_macro_created(self, swm_path: str) -> None:
        # The unsaved-changes prompt already ran in _confirm_new_macro.
        self.load_macro_file(swm_path)

    def _update_status_bar_screen_info(self) -> None:
        t = get_theme_tokens()
        screen = get_screen_info()
        w, h, scale = screen["width"], screen["height"], screen["scale_percent"]
        rec = self._current_macro.recorded_screen

        if rec.width == w and rec.height == h and rec.scale_percent == scale:
            self.lbl_screen_info.setText(f"Screen {w}x{h} @{scale}% ✅")
            self.lbl_screen_info.setStyleSheet(f"color: {t['status_ok']}; font-weight: 500;")
        else:
            self.lbl_screen_info.setText(f"Screen {w}x{h} @{scale}% ⚠")
            self.lbl_screen_info.setStyleSheet(f"color: {t['status_fail']}; font-weight: bold;")

    def load_macro_file(self, swm_path: str) -> None:
        self._cancel_step_test()
        if self._is_running:
            return
        package_temp = tempfile.TemporaryDirectory(prefix="stepwise_pkg_")
        try:
            macro, extract_dir = load_package(swm_path, extract_dir=package_temp.name)
            previous_temp = self._package_temp
            self._package_temp = package_temp if extract_dir == package_temp.name else None
            self._package_dir = extract_dir
            if self._package_temp is None:
                package_temp.cleanup()
            if previous_temp:
                previous_temp.cleanup()
            if hasattr(self, "overlay"):
                self.overlay.close()
            self.prop_panel.set_action(None)
            self._current_macro = macro
            self._current_macro_path = swm_path
            self.action_tree.load_macro(macro)
            self.action_tree.set_data_row_count(len(self._data_rows))
            self._update_status_bar_screen_info()
            self._cancel_step_test()
            self._mark_saved()
            self.data_panel.set_reconnect_hint(
                None if self._data_filepath else self._recent_data_file(swm_path)
            )
            # Saving A while switching to B re-selects A; keep the list on the open macro.
            self.lib_panel.select_path(swm_path, emit=False)
            self.status_bar.showMessage(f"Loaded: {macro.name}")
        except Exception as e:
            package_temp.cleanup()
            QMessageBox.critical(self, "Load Error", f"Failed to load macro:\n{e}")

    def save_current_macro(self) -> bool:
        self._cancel_step_test()
        path = self._current_macro_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Macro", self._library_dir, "Stepwise Macro (*.swm)"
            )
            if not path:
                return False
        try:
            macro_snapshot = copy.deepcopy(self._current_macro)
            image_files: dict[str, bytes] = {}
            for actions in (macro_snapshot.setup, macro_snapshot.per_row, macro_snapshot.cleanup):
                self._collect_package_images(actions, image_files)
            save_package(macro_snapshot, path, image_files=image_files)
        except Exception as e:
            QMessageBox.warning(self, Strings.SAVE_ERROR_TITLE, Strings.SAVE_ERROR.format(error=e))
            return False
        self._current_macro_path = path
        self._mark_saved()
        if self._data_filepath:
            self._remember_data_file(self._data_filepath)
        self.lib_panel.refresh_list()
        self.lib_panel.select_path(path, emit=False)
        self.status_bar.showMessage(f"Saved: {os.path.basename(self._current_macro_path)}")
        return True

    def _collect_package_images(
        self, actions: list[ActionItem], image_files: dict[str, bytes]
    ) -> None:
        for action in actions:
            for owner in (action, action.guard, action.verify):
                if owner is None or not owner.image:
                    continue
                reference = owner.image
                source = os.path.normpath(os.path.join(self._package_dir, reference))
                if not os.path.isfile(source):
                    raise FileNotFoundError(reference)
                # Canonicalize references in the saved snapshot, including legacy
                # bare filenames and external images, so the archive is portable.
                entry = reference.replace("\\", "/")
                if os.path.isabs(reference) or ".." in entry.split("/"):
                    entry = f"images/{uuid.uuid5(uuid.NAMESPACE_URL, source).hex}_{os.path.basename(source)}"
                elif not entry.startswith("images/"):
                    entry = f"images/{entry}"
                owner.image = entry
                # Read all referenced assets before replacing the package. This
                # also prevents save_package from silently skipping a file that
                # disappears between collection and archive serialization.
                with open(source, "rb") as image_file:
                    image_files[entry] = image_file.read()
            self._collect_package_images(action.items, image_files)

    def _on_action_selected(self, action: ActionItem | None) -> None:
        # Property edits also rebuild the tree. Keep the active editor and its cursor.
        if self.prop_panel._current_action is not action:
            self.prop_panel.set_action(action)

    def _on_property_changed(self) -> None:
        self.action_tree.rebuild_tree()
        self._update_window_title()

    def _add_quick_action(self, act_type: str) -> None:
        sec_name, parent, idx = self.action_tree.get_current_insertion_target()
        self._on_request_add_action(act_type, sec_name, idx, parent)

    def _on_request_add_action(
        self, act_type: str, section: str, index: int, parent: ActionItem | None = None
    ) -> None:
        if section not in ("setup", "per_row", "cleanup"):
            return
        if parent is not None:
            location = self._current_macro.find_action_location(parent)
            if parent.type != "group" or location is None or location.section != section:
                return
        new_act = ActionItem(type=act_type, enabled=True)
        target_list = parent.items if parent is not None else getattr(self._current_macro, section)
        idx = min(max(0, index), len(target_list))
        target_list.insert(idx, new_act)
        self.action_tree.rebuild_tree(select_id=new_act.id)
        self._update_window_title()
        self.status_bar.showMessage(f"Added {act_type} to {section.upper()}")

    def _on_request_move_section(self, action: ActionItem, target_section: str) -> None:
        location = self._current_macro.find_action_location(action)
        if location is None or target_section not in ("setup", "per_row", "cleanup"):
            return
        location.items.pop(location.index)
        target_list = getattr(self._current_macro, target_section)
        target_list.append(action)
        self.action_tree.rebuild_tree(select_id=action.id)
        self._update_window_title()
        self.status_bar.showMessage(f"Moved step to {target_section.upper()}")

    def _on_request_delete_action(self, action: ActionItem) -> None:
        self._cancel_step_test()
        location = self._current_macro.find_action_location(action)
        if location is None:
            return
        location.items.pop(location.index)
        if location.items:
            next_select_id = location.items[min(location.index, len(location.items) - 1)].id
        elif location.parent is not None:
            next_select_id = f"empty_group_{location.parent.id}"
        else:
            next_select_id = f"empty_{location.section}"
        self.action_tree.rebuild_tree(select_id=next_select_id)
        self._update_window_title()
        self.status_bar.showMessage("Deleted step")

    def _on_request_duplicate_action(self, action: ActionItem) -> None:
        location = self._current_macro.find_action_location(action)
        if location is None:
            return
        new_act = copy.deepcopy(action)

        def renew_ids(item: ActionItem) -> None:
            item.id = str(uuid.uuid4())
            for child in item.items:
                renew_ids(child)

        renew_ids(new_act)
        location.items.insert(location.index + 1, new_act)
        self.action_tree.rebuild_tree(select_id=new_act.id)
        self._update_window_title()
        self.status_bar.showMessage(f"Duplicated {action.type} step")

    def _on_move_up_clicked(self) -> None:
        selected_act = self.action_tree._get_selected_action()
        if selected_act:
            self._on_request_move_up(selected_act)

    def _on_move_down_clicked(self) -> None:
        selected_act = self.action_tree._get_selected_action()
        if selected_act:
            self._on_request_move_down(selected_act)

    def _on_request_move_up(self, action: ActionItem) -> None:
        self._move_action(action, -1)

    def _on_request_move_down(self, action: ActionItem) -> None:
        self._move_action(action, 1)

    def _move_action(self, action: ActionItem, offset: int) -> None:
        location = self._current_macro.find_action_location(action)
        if location is None:
            return
        items, index = location.items, location.index
        target = index + offset
        if not 0 <= target < len(items):
            self.status_bar.showMessage(
                Strings.MOVE_BOUNDARY_TOP if offset < 0 else Strings.MOVE_BOUNDARY_BOTTOM
            )
            return
        items[index], items[target] = items[target], items[index]
        self.action_tree.rebuild_tree(select_id=action.id)
        self._update_window_title()
        self.status_bar.showMessage("Moved step up" if offset < 0 else "Moved step down")

    def _locate_target_only(self, action: ActionItem) -> None:
        """Visual-only locate target without sending clicks or keystrokes."""
        self.status_bar.showMessage(Strings.LOCATE_TARGET_ACTIVE, 2000)
        target_mode = getattr(action, "target_mode", "coords")
        if target_mode == "selector" and getattr(action, "selector", None):
            self._validate_and_highlight_selector(action)
        elif getattr(action, "x", None) is not None and getattr(action, "y", None) is not None:
            self._show_screen_crosshair(action.x, action.y)
        elif getattr(action, "image", None):
            self._test_image_match(action)
        else:
            self.status_bar.showMessage(Strings.SELECTOR_SUMMARY_EMPTY, 2500)

    def _show_screen_crosshair(self, x: int, y: int) -> None:
        self._crosshair_overlay = ScreenCrosshairOverlay(x, y)
        self.status_bar.showMessage(f"Displaying target coordinate ({x}, {y}) on screen (1.5s)...")

    def _request_step_test(self, action: ActionItem) -> None:
        """Count down before testing a step so input lands on the target window."""
        if self._is_running:
            return
        if self._step_test_pending:
            self.status_bar.showMessage(Strings.STEP_TEST_BUSY, 2000)
            return
        seconds = int(float(self._user_settings.get("countdown_seconds", 3) or 0))
        if seconds <= 0:
            self._test_single_action(action)
            return
        self._step_test_pending = True
        self._step_test_action = action
        self._step_test_remaining = seconds
        self.status_bar.showMessage(Strings.STEP_TEST_COUNTDOWN.format(seconds=seconds))
        self._step_test_timer.start()

    def _on_step_test_tick(self) -> None:
        if (
            QApplication.activeModalWidget() is not None
            or QApplication.activePopupWidget() is not None
        ):
            # A dialog or menu opened during the countdown: never send input into it.
            self._cancel_step_test()
            self.status_bar.showMessage(Strings.STEP_TEST_CANCELLED_DIALOG, 3000)
            return
        self._step_test_remaining -= 1
        if self._step_test_remaining > 0:
            self.status_bar.showMessage(
                Strings.STEP_TEST_COUNTDOWN.format(seconds=self._step_test_remaining)
            )
            return
        action = self._step_test_action
        self._cancel_step_test()
        if action is None:
            return
        if self._current_macro.find_action_location(action) is None:
            # The step was deleted (or another macro was opened) during the countdown.
            self.status_bar.showMessage(Strings.STEP_TEST_CANCELLED, 3000)
            return
        self._test_single_action(action)

    def _cancel_step_test(self) -> None:
        self._step_test_timer.stop()
        self._step_test_pending = False
        self._step_test_action = None
        self._step_test_remaining = 0

    def _test_single_action(self, action: ActionItem) -> None:
        if self._is_running:
            return
        try:
            from stepwise.engine.actions import execute_action

            sample_row = self._data_rows[0] if self._data_rows else {}
            pkg_dir = self._package_dir
            settings = getattr(self._current_macro, "settings", None) or {}
            def_wait = (
                float(getattr(settings, "default_wait_before", 0.2))
                if hasattr(settings, "default_wait_before")
                else 0.2
            )
            def_conf = (
                float(getattr(settings, "image_confidence", 0.95))
                if hasattr(settings, "image_confidence")
                else 0.95
            )
            self.status_bar.showMessage(f"Executing step '{action.type}' immediately...")
            execute_action(
                action,
                sample_row,
                package_dir=pkg_dir,
                default_confidence=def_conf,
                default_wait_before=def_wait,
            )
            self.status_bar.showMessage(f"Step '{action.type}' executed successfully! ✅")
        except Exception as e:
            QMessageBox.warning(self, "Step Test Failed", f"Execution error:\n{e}")

    def _test_image_match(self, action: ActionItem) -> None:
        self._cancel_step_test()
        if not action.image:
            QMessageBox.warning(
                self, "Image Match Test", "No template image specified for this action."
            )
            return

        pkg_dir = self._package_dir
        target_path = (
            os.path.join(pkg_dir, action.image)
            if pkg_dir and not os.path.isabs(action.image)
            else action.image
        )

        if not os.path.exists(target_path):
            QMessageBox.warning(
                self, "Image Match Test", f"Template image file not found:\n{target_path}"
            )
            return

        try:
            from stepwise.services.matcher import find_image_on_screen

            match_res = find_image_on_screen(
                target_path,
                confidence=action.confidence or 0.8,
                region=action.region,
            )
            if match_res and match_res.found:
                self.status_bar.showMessage(
                    f"Match found at ({match_res.center_x}, {match_res.center_y}) "
                    f"confidence: {match_res.confidence:.2f} ✅"
                )
                self._show_screen_crosshair(match_res.center_x, match_res.center_y)
            else:
                self.status_bar.showMessage("Image match failed: template not found on screen ❌")
                QMessageBox.information(
                    self,
                    "Image Match Test",
                    "Target image was not found on screen with current confidence.",
                )
        except Exception as e:
            QMessageBox.warning(self, "Image Match Test", f"Error during image matching:\n{e}")

    def _on_delete_action(self) -> None:
        selected = self.action_tree.tree.selectedItems()
        if not selected:
            return
        data = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, ActionItem):
            self._on_request_delete_action(data)

    def _on_data_loaded(
        self,
        filepath: str,
        headers: list[str],
        rows: list[dict[str, str]],
        row_nums: list[int] | None = None,
    ) -> None:
        pristine = self._is_pristine_macro()
        self._data_filepath = filepath
        self._data_headers = headers
        self._data_rows = rows
        self._data_row_nums = (
            list(row_nums) if row_nums is not None else list(range(1, len(rows) + 1))
        )
        self._row_status_overrides.clear()
        sample_row = rows[0] if rows else {}
        self.prop_panel.update_variable_completions(headers, sample_row=sample_row)
        self.action_tree.set_data_row_count(len(rows))

        file_hint = os.path.basename(filepath)
        if self._current_macro.data_source is None:
            ext = os.path.splitext(filepath)[1].lower()
            self._current_macro.data_source = DataSourceConfig(
                type="csv" if ext == ".csv" else "xlsx"
            )
        self._current_macro.data_source.file_hint = file_hint
        self._remember_data_file(filepath)
        if pristine:
            # Just previewing data in the blank start-up macro is not an edit.
            self._mark_saved()
        else:
            self._update_window_title()
        self._update_run_button_text()
        self.status_bar.showMessage(f"Connected data: {file_hint} ({len(rows)} rows)")

    @staticmethod
    def _macro_key(swm_path: str) -> str:
        return os.path.normcase(os.path.abspath(swm_path))

    def _remember_data_file(self, filepath: str) -> None:
        """Remember the last data file per saved macro (offered later as [Reconnect])."""
        if not self._current_macro_path or not os.path.isabs(filepath):
            return
        recent = dict(self._user_settings.get("recent_data_files") or {})
        key = self._macro_key(self._current_macro_path)
        if recent.get(key) == filepath:
            return
        recent.pop(key, None)
        recent[key] = filepath
        # Keep the settings file small: only the most recent entries survive.
        self._user_settings["recent_data_files"] = dict(list(recent.items())[-30:])
        try:
            save_user_settings(self._user_settings)
        except OSError:
            pass

    def _recent_data_file(self, swm_path: str) -> str | None:
        recent = self._user_settings.get("recent_data_files") or {}
        path = recent.get(self._macro_key(swm_path)) if isinstance(recent, dict) else None
        return path if isinstance(path, str) and os.path.isfile(path) else None

    def _on_row_status_override(self, row_num: int, new_status: str) -> None:
        self._row_status_overrides[row_num] = new_status
        self.status_bar.showMessage(f"Row #{row_num} marked as {new_status}")

    def _on_run_only_row(self, row_num: int) -> None:
        if self._is_running:
            return
        try:
            row_idx = self._data_row_nums.index(row_num)
        except ValueError:
            self.status_bar.showMessage(
                f"Cannot run row #{row_num}: row is not in the loaded data."
            )
            return

        start_row = row_idx + 1
        opts: dict[str, Any] = {
            "start_row": start_row,
            "end_row_index": start_row,
            "speed": SpeedMode.NORMAL,
            "skip_setup": False,
            "skip_cleanup": False,
            "step_by_step": False,
            "run_1_row": True,
            "countdown_seconds": float(self._user_settings.get("countdown_seconds", 3.0)),
        }
        if 0 <= row_idx < len(self._data_rows):
            opts["custom_rows"] = [self._data_rows[row_idx]]
            opts["custom_row_nums"] = [row_num]
        self._start_execution(opts)

    def _update_run_button_text(self) -> None:
        n = len(self._data_rows)
        if n:
            self.btn_run.setText(f"▶ {Strings.RUN} ({Strings.RUN_ROW_COUNT.format(n=n)})")
        else:
            self.btn_run.setText(f"▶ {Strings.RUN}")

    def _on_test_1_row_clicked(self) -> None:
        """Run only one data row (the selected one, else the first) after a countdown."""
        if self._is_running:
            return
        self._cancel_step_test()
        row_index = 0
        if self._data_rows:
            selected = self.data_panel.table.currentRow()
            if 0 <= selected < len(self._data_rows):
                row_index = selected
        rows = [self._data_rows[row_index]] if self._data_rows else None
        row_nums = [self._data_row_nums[row_index]] if self._data_rows else None
        blocking = [
            issue
            for issue in run_preflight_checks(
                macro=self._current_macro,
                rows_data=rows,
                row_numbers=row_nums,
                package_dir=self._package_dir,
                headers=self._data_headers,
            )
            if issue.is_error
        ]
        if blocking:
            details = "\n".join(f"• {localize_issue(issue)[0]}" for issue in blocking[:5])
            QMessageBox.warning(
                self, Strings.TEST_1_ROW_BLOCKED_TITLE, Strings.TEST_1_ROW_BLOCKED.format(issues=details)
            )
            return
        start_row = row_index + 1
        opts: dict[str, Any] = {
            "start_row": start_row,
            "end_row_index": start_row,
            "speed": SpeedMode.NORMAL,
            "skip_setup": False,
            "skip_cleanup": False,
            "step_by_step": False,
            "run_1_row": True,
            "countdown_seconds": float(self._user_settings.get("countdown_seconds", 3) or 0),
        }
        if rows and row_nums:
            opts["custom_rows"] = rows
            opts["custom_row_nums"] = row_nums
        self._start_execution(opts)

    def _insert_variable_into_current_action(self, col_name: str) -> None:
        act = self.prop_panel._current_action
        if act is None or act.type != "type_text":
            self.status_bar.showMessage(Strings.SELECT_TYPE_TEXT_FIRST, 3000)
            return
        # Data panel emits "{Column}"; the properties panel adds the braces itself.
        if col_name.startswith("{") and col_name.endswith("}"):
            col_name = col_name[1:-1]
        self.prop_panel._insert_column_token(col_name)

    def _trigger_pick_overlay(self) -> None:
        act = self.prop_panel._current_action
        if not act:
            return

        def _on_picked(x: int, y: int) -> None:
            act.x = x
            act.y = y
            self.prop_panel.set_action(act)
            self.action_tree.rebuild_tree()
            self.status_bar.showMessage(f"Picked coordinate: ({x}, {y})")

        self.overlay = CaptureOverlay(
            mode="pick", images_dir=os.path.join(self._package_dir, "images")
        )
        self.overlay.coords_picked.connect(_on_picked)
        self.overlay.show()

    def _trigger_element_pick_overlay(self) -> None:
        act = self.prop_panel._current_action
        if not act or act.type != "click":
            return

        def _on_element_picked(selector: dict[str, Any], x: int, y: int) -> None:
            act.target_mode = "selector"
            act.selector = selector
            act.x = x
            act.y = y
            self.prop_panel.set_action(act)
            self.action_tree.rebuild_tree()
            ctrl = selector.get("control_type") or "Element"
            name = selector.get("name") or selector.get("automation_id") or ""
            self.status_bar.showMessage(f"Picked UI Element: [{ctrl}] {name} at ({x}, {y})")

        self.overlay = CaptureOverlay(
            mode="element", images_dir=os.path.join(self._package_dir, "images")
        )
        self.overlay.element_picked.connect(_on_element_picked)
        self.overlay.show()

    def _validate_and_highlight_selector(self, action: ActionItem) -> None:
        self._cancel_step_test()
        if not action.selector:
            QMessageBox.information(
                self,
                "UI Selector Validation",
                Strings.SELECTOR_SUMMARY_EMPTY,
            )
            return
        try:
            from stepwise.services.uia_win import resolve_selector

            sample_row = self._data_rows[0] if self._data_rows else {}
            match = resolve_selector(action.selector, row_data=sample_row)
            label = f"[{match.control_type}] {match.name or match.automation_id or match.class_name}"
            self._element_highlight_overlay = ElementHighlightOverlay(
                match.rect, label=label
            )
            tx, ty = match.target_point()
            self.status_bar.showMessage(
                f"Selector matched uniquely at ({tx}, {ty}): {label} ✅"
            )
        except Exception as e:
            self.status_bar.showMessage(f"Selector validation failed: {e} ❌")
            QMessageBox.warning(self, "UI Selector Validation", str(e))

    def _trigger_capture_overlay(self) -> None:
        act = self.prop_panel._current_action
        if not act:
            return

        def _on_captured(rel_img: str, region: list[int]) -> None:
            act.image = rel_img
            act.region = region
            self.prop_panel.set_action(act)
            self.action_tree.rebuild_tree()
            self.status_bar.showMessage(f"Captured image: {rel_img}")

        self.overlay = CaptureOverlay(
            mode="region", images_dir=os.path.join(self._package_dir, "images")
        )
        self.overlay.region_captured.connect(_on_captured)
        self.overlay.capture_failed.connect(
            lambda error: QMessageBox.warning(
                self, Strings.CAPTURE_ERROR_TITLE, Strings.CAPTURE_ERROR.format(error=error)
            )
        )
        self.overlay.show()

    def _open_settings(self) -> None:
        self._cancel_step_test()
        dlg = SettingsDialog(parent=self)
        if dlg.exec() == SettingsDialog.Accepted:
            self._user_settings = load_user_settings()
            new_lib = self._user_settings.get("library_dir")
            if new_lib and new_lib != self._library_dir:
                self._library_dir = str(new_lib)
                self.lib_panel.set_library_dir(str(new_lib))
            self.retranslate_ui()
            self.status_bar.showMessage("Settings saved.")

    def _toggle_theme(self) -> None:
        from PySide6.QtWidgets import QApplication

        next_theme = "light" if get_current_theme() == "dark" else "dark"
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, next_theme)
        self._user_settings["theme"] = next_theme
        try:
            save_user_settings(self._user_settings)
        except OSError:
            pass
        self.retranslate_ui()

    def _toggle_language(self) -> None:
        next_lang = "en" if get_current_language() == "ko" else "ko"
        apply_language(next_lang)
        self._user_settings["language"] = next_lang
        try:
            save_user_settings(self._user_settings)
        except OSError:
            pass
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Refresh all UI labels, tooltips, and theme colors across MainWindow and child panels."""
        t = get_theme_tokens()
        self._update_run_button_text()
        self.btn_run.setToolTip(Strings.Tooltips.RUN)
        self.btn_test_1_row.setText(Strings.TEST_1_ROW)
        self.btn_test_1_row.setToolTip(Strings.Tooltips.TEST_1_ROW)
        self.btn_pause.setText(f"⏸ {Strings.PAUSE}")
        self.btn_pause.setToolTip(Strings.Tooltips.PAUSE)
        self.btn_stop.setText(f"■ {Strings.STOP}")
        self.btn_stop.setToolTip(Strings.Tooltips.STOP)
        self.btn_save.setText(f"💾 {Strings.SAVE_MACRO}")
        self.btn_save.setToolTip(Strings.Tooltips.SAVE_MACRO)
        self.btn_schedule.setText(f"⏰ {Strings.SCHEDULE}")
        self.btn_schedule.setToolTip(Strings.Tooltips.SCHEDULE)
        self.btn_theme.setText(
            Strings.THEME_DARK if get_current_theme() == "dark" else Strings.THEME_LIGHT
        )
        self.btn_lang.setText(
            Strings.LANG_KO if get_current_language() == "ko" else Strings.LANG_EN
        )
        self.btn_settings.setText(f"⚙ {Strings.SETTINGS}")
        self.btn_settings.setToolTip(Strings.Tooltips.SETTINGS)

        self.lbl_add_action.setText(Strings.ADD_ACTION_LABEL)
        self.lbl_add_action.setStyleSheet(f"font-weight: bold; color: {t['text_secondary']};")
        self.btn_add_click.setText(Strings.BTN_ADD_CLICK)
        self.btn_add_click.setToolTip(Strings.Tooltips.ADD_CLICK)
        self.btn_add_type.setText(Strings.BTN_ADD_TYPE)
        self.btn_add_type.setToolTip(Strings.Tooltips.ADD_TYPE)
        self.btn_add_key.setText(Strings.BTN_ADD_KEY)
        self.btn_add_key.setToolTip(Strings.Tooltips.ADD_KEY)
        self.btn_add_wait.setText(Strings.BTN_ADD_WAIT)
        self.btn_add_wait.setToolTip(Strings.Tooltips.ADD_WAIT)
        self.btn_add_win.setText(Strings.BTN_ADD_WIN)
        self.btn_add_win.setToolTip(Strings.Tooltips.ADD_WINDOW)
        self.btn_move_up.setText(Strings.MOVE_UP)
        self.btn_move_down.setText(Strings.MOVE_DOWN)
        self.btn_delete.setText(f"🗑 {Strings.DELETE}")
        self.btn_delete.setToolTip(Strings.Tooltips.DELETE_ACTION)

        self._update_status_bar_screen_info()
        self.lib_panel.retranslate_ui()
        self.action_tree.retranslate_ui()
        self.data_panel.retranslate_ui()
        self.prop_panel.retranslate_ui()
        self.floating_panel.retranslate_ui()
        self._setup_menu_bar()

    def _open_scheduler(self) -> None:
        if self._is_running:
            return
        self._cancel_step_test()
        dlg = SchedulerDialog(
            macro=self._current_macro,
            rows_data=self._data_rows,
            row_numbers=self._data_row_nums,
            package_dir=self._package_dir,
            data_file_path=self._data_filepath,
            results_dir=str(self._user_settings.get("results_dir") or default_results_directory()),
            jiggler_enabled=bool(self._user_settings.get("anti_lock_jiggler_enabled", False)),
            jiggler_interval=safe_jiggler_interval(
                self._user_settings.get("anti_lock_jiggler_interval_sec"), default=45.0
            ),
            parent=self,
        )
        if dlg.exec() == SchedulerDialog.Accepted and dlg.confirmed_opts:
            self._start_execution(dlg.confirmed_opts)

    def _on_run_clicked(self) -> None:
        if self._is_running:
            return
        self._cancel_step_test()
        self._is_running = True
        self._execution_phase = "preflight"
        try:
            self._show_preflight()
        finally:
            if self._execution_phase == "preflight":
                self._is_running = False
                self._execution_phase = "idle"
                if self._close_requested:
                    QTimer.singleShot(0, self.close)

    def _show_preflight(self) -> None:
        excluded_rows = self.data_panel.get_excluded_row_numbers()
        dlg = PreflightDialog(
            macro=self._current_macro,
            rows_data=self._data_rows,
            row_numbers=self._data_row_nums,
            headers=self._data_headers,
            package_dir=self._package_dir,
            data_file_path=self._data_filepath,
            results_dir=str(self._user_settings.get("results_dir") or default_results_directory()),
            countdown_seconds=self._user_settings.get("countdown_seconds", 3),
            excluded_row_numbers=excluded_rows,
            excluded_count=len(excluded_rows),
            row_statuses=self.data_panel.get_row_statuses(),
            parent=self,
        )
        if dlg.exec() != PreflightDialog.Accepted:
            return
        if self._close_requested:
            return

        opts = getattr(dlg, "confirmed_opts", None)
        if not opts:
            speed = (
                SpeedMode.SLOW
                if dlg.rad_slow.isChecked()
                else (SpeedMode.VERY_SLOW if dlg.rad_veryslow.isChecked() else SpeedMode.NORMAL)
            )
            opts = {
                "start_row": dlg.spin_start_row.value(),
                "speed": speed,
                "skip_setup": dlg.chk_skip_setup.isChecked(),
                "skip_cleanup": dlg.chk_cleanup_checked(),
                "step_by_step": dlg.chk_step_by_step.isChecked(),
                "run_1_row": False,
            }
        # The modal preflight owns the guard until it has fully closed.
        self._is_running = False
        self._execution_phase = "idle"
        if opts.get("reset_statuses"):
            self.data_panel.reset_all_statuses()
        self._start_execution(opts)

    def _show_info_dialog(self, title: str, text: str) -> None:
        """Show information message dialog."""
        QMessageBox.information(self, title, text)

    def _start_execution(self, opts: dict[str, Any]) -> None:
        if self._is_running or (self._worker_thread and self._worker_thread.is_alive()):
            return
        self._cancel_step_test()
        opts = dict(opts)
        if opts.pop("reset_statuses", False):
            self.data_panel.reset_all_statuses()
        self._is_running = True
        self._execution_phase = "starting"
        # Swapping the data mid-run would desync row statuses and later retries.
        self.data_panel.set_running(True)
        run_token = str(uuid.uuid4())
        self._run_token = run_token
        self._pending_summary = None
        try:
            macro_snapshot = copy.deepcopy(self._current_macro)
            total_data_len = len(self._data_rows)
            excluded_row_nums = self.data_panel.get_excluded_row_numbers()
            if "custom_rows" in opts and "custom_row_nums" in opts:
                rows_snapshot = copy.deepcopy(opts["custom_rows"])
                row_nums_snapshot = copy.deepcopy(opts["custom_row_nums"])
                start_row_idx = 0
                end_row_idx = None
            elif total_data_len > 0 and (excluded_row_nums or opts.get("run_1_row")):
                raw_start = max(0, opts.get("start_row", 1) - 1)
                if opts.get("end_row_index") is not None:
                    raw_end = min(total_data_len, int(opts["end_row_index"]))
                elif opts.get("run_1_row"):
                    # When running 1 specific row without an explicit end_row_index, never scan past that row
                    raw_end = min(total_data_len, raw_start + 1)
                else:
                    raw_end = total_data_len

                sliced_rows = self._data_rows[raw_start:raw_end]
                sliced_nums = self._data_row_nums[raw_start:raw_end]

                final_rows = []
                final_nums = []
                for r_data, r_num in zip(sliced_rows, sliced_nums, strict=True):
                    if r_num not in excluded_row_nums:
                        final_rows.append(r_data)
                        final_nums.append(r_num)

                if opts.get("run_1_row", False):
                    final_rows = final_rows[:1]
                    final_nums = final_nums[:1]

                if not final_rows:
                    self._is_running = False
                    self._execution_phase = "idle"
                    self.data_panel.set_running(False)
                    if opts.get("scheduled"):
                        msg = Strings.ISSUE_ALL_ROWS_EXCLUDED
                        self.status_bar.showMessage(msg, 5000)
                        logger.warning("[Scheduled] %s", msg)
                        return

                    row_statuses = self.data_panel.get_row_statuses()
                    all_done = bool(sliced_nums) and all(
                        normalize_status_code(row_statuses.get(n, "")) == "Done"
                        for n in sliced_nums
                    )
                    if all_done:
                        reply = QMessageBox.question(
                            self,
                            Strings.PREFLIGHT_ALL_DONE_TITLE,
                            Strings.PREFLIGHT_ALL_DONE_MSG,
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.Yes,
                        )
                        if reply == QMessageBox.StandardButton.Yes:
                            self.data_panel.reset_all_statuses()
                            self._start_execution(opts)
                            return

                    self.status_bar.showMessage(Strings.ISSUE_ALL_ROWS_EXCLUDED, 5000)
                    self._show_info_dialog(
                        Strings.APP_TITLE,
                        f"{Strings.ISSUE_ALL_ROWS_EXCLUDED}\n{Strings.ISSUE_ALL_ROWS_EXCLUDED_DETAILS}",
                    )
                    return

                rows_snapshot = copy.deepcopy(final_rows)
                row_nums_snapshot = copy.deepcopy(final_nums)
                start_row_idx = 0
                end_row_idx = None
            else:
                rows_snapshot = copy.deepcopy(self._data_rows)
                row_nums_snapshot = copy.deepcopy(self._data_row_nums)
                end_row_index = opts.get("end_row_index")
                start_row_idx = max(0, opts.get("start_row", 1) - 1)
                end_row_idx = int(end_row_index) if end_row_index is not None else None
            opts = copy.deepcopy(opts)
            if opts.get("run_1_row") or (total_data_len > 0 and excluded_row_nums):
                opts["custom_row_nums"] = list(row_nums_snapshot)
                opts["custom_rows"] = list(rows_snapshot)
            self._last_run_opts = opts
            snapshot = ExecutionSnapshot(
                macro=macro_snapshot,
                rows=tuple(rows_snapshot),
                row_numbers=tuple(row_nums_snapshot),
                package_dir=self._package_dir,
                data_filepath=self._data_filepath,
                results_dir=str(self._user_settings.get("results_dir") or default_results_directory()),
                speed=opts.get("speed", SpeedMode.NORMAL),
                start_row_index=start_row_idx,
                end_row_index=end_row_idx,
                skip_setup=opts.get("skip_setup", False),
                skip_cleanup=opts.get("skip_cleanup", False),
                run_1_row=opts.get("run_1_row", False),
                countdown_seconds=float(opts.get("countdown_seconds", 0.0)),
                anti_lock_jiggler=opts.get(
                    "anti_lock_jiggler",
                    bool(self._user_settings.get("anti_lock_jiggler_enabled", False)),
                ),
                jiggler_interval_seconds=safe_jiggler_interval(
                    opts.get(
                        "jiggler_interval_seconds",
                        self._user_settings.get("anti_lock_jiggler_interval_sec"),
                    ),
                    default=45.0,
                ),
            )
        except Exception as e:
            self._teardown_runner()
            logger.exception("Failed to prepare execution snapshot: %s", e)
            if not opts.get("scheduled"):
                QMessageBox.warning(
                    self, Strings.RUN_ERROR_TITLE, Strings.SNAPSHOT_ERROR.format(error=e)
                )
            else:
                self.status_bar.showMessage(Strings.SNAPSHOT_ERROR.format(error=e), 5000)
            return

        controller = ExecutionController()
        self._controller = controller
        if opts.get("step_by_step"):
            controller.enable_step_by_step(True)
            self.floating_panel.set_step_by_step(True)
        else:
            self.floating_panel.set_step_by_step(False)

        speed: SpeedMode = opts.get("speed", SpeedMode.NORMAL)
        self.floating_panel.set_speed_text(speed)

        try:
            self._hotkey_mgr = GlobalHotkeyManager()
            self._hotkey_mgr.start()
            vk_f12 = VK_MAP.get("f12", 0x7B)
            if not self._hotkey_mgr.register_hotkey(vk_f12, 0, callback=controller.stop):
                raise RuntimeError("F12 registration was unsuccessful")
        except Exception as e:
            self._teardown_runner()
            logger.exception("F12 hotkey registration failed: %s", e)
            if not opts.get("scheduled"):
                QMessageBox.warning(self, Strings.RUN_ERROR_TITLE, Strings.F12_ERROR.format(error=e))
            else:
                self.status_bar.showMessage(Strings.F12_ERROR.format(error=e), 5000)
            return

        self.btn_run.setEnabled(False)
        self.btn_test_1_row.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)

        self.showMinimized()
        self.floating_panel.show()

        bridge = self._bridge

        def emit_event(name: str, *args: Any) -> None:
            bridge.event.emit(run_token, name, args)

        callbacks = ExecutionCallbacks(
            on_run_started=lambda r_id, tot: emit_event("run_started", r_id, tot),
            on_row_started=lambda r_num, data: emit_event("row_started", r_num, data),
            on_step_started=lambda s_id, lbl: emit_event("step_started", s_id, lbl),
            on_step_finished=lambda s_id, lbl: emit_event("step_finished", s_id, lbl),
            on_row_finished=lambda r_num, st: emit_event("row_finished", r_num, st),
            on_run_finished=lambda summ: emit_event("run_finished", summ),
            on_run_failed=lambda fail, shot: emit_event("run_failed", fail, shot),
        )

        def _worker() -> None:
            try:
                run_macro(
                    macro=snapshot.macro,
                    rows_data=snapshot.rows,
                    controller=controller,
                    callbacks=callbacks,
                    speed=snapshot.speed,
                    skip_setup=snapshot.skip_setup,
                    skip_cleanup=snapshot.skip_cleanup,
                    run_1_row=snapshot.run_1_row,
                    start_row_index=snapshot.start_row_index,
                    end_row_index=snapshot.end_row_index,
                    package_dir=snapshot.package_dir,
                    countdown_seconds=snapshot.countdown_seconds,
                    data_filepath=snapshot.data_filepath,
                    results_dir=snapshot.results_dir,
                    row_numbers=snapshot.row_numbers,
                    anti_lock_jiggler=snapshot.anti_lock_jiggler,
                    jiggler_interval_seconds=snapshot.jiggler_interval_seconds,
                )
            except Exception as e:
                print(f"Unhandled exception in macro runner: {e}")
                fail_summary = RunSummary(
                    run_id="error",
                    macro_name=snapshot.macro.name,
                    started_at="",
                    finished_at="",
                    duration_sec=0.0,
                    total_rows=0,
                    done_count=0,
                    failed_count=1,
                    interrupted_count=0,
                    skipped_count=0,
                    failure=StepFailure(message=f"Fatal runner failure: {e}"),
                )
                emit_event("run_finished", fail_summary)
            finally:
                emit_event("worker_finished")

        try:
            self._worker_thread = threading.Thread(target=_worker, daemon=True)
            self._execution_phase = "running"
            self._worker_thread.start()
        except Exception as e:
            self._teardown_runner()
            self.showNormal()
            logger.exception("Failed to start runner thread: %s", e)
            if not opts.get("scheduled"):
                QMessageBox.warning(
                    self, Strings.RUN_ERROR_TITLE, Strings.RUN_START_ERROR.format(error=e)
                )
            else:
                self.status_bar.showMessage(Strings.RUN_START_ERROR.format(error=e), 5000)

    @Slot(str, str, object)
    def _on_runner_event(self, token: str, name: str, args: tuple[Any, ...]) -> None:
        if token != self._run_token:
            return
        if name == "worker_finished":
            self._finish_worker(token)
        else:
            getattr(self, f"_on_engine_{name}")(*args)

    def _finish_worker(self, token: str) -> None:
        if token != self._run_token:
            return
        if self._worker_thread and self._worker_thread.is_alive():
            QTimer.singleShot(10, lambda: self._finish_worker(token))
            return
        summary = self._pending_summary
        self._teardown_runner()
        if self._close_requested and not (summary and summary.persistence_errors):
            self.close()
            return
        self._close_requested = False
        self.showNormal()
        if (
            self._last_run_opts.get("scheduled")
            and self._last_run_opts.get("lock_after")
            and not (summary and summary.interrupted)
        ):
            from stepwise.services.power import lock_workstation

            lock_workstation()
        if summary:
            # Flash taskbar icon to gently notify the user
            app = QApplication.instance()
            if app:
                QApplication.alert(self, 0)
            dlg = RunSummaryDialog(summary, parent=self)
            dlg.jump_to_step_requested.connect(self._jump_to_step)
            dlg.retry_failed_requested.connect(self._retry_failed_rows)
            dlg.exec()

    def _retry_failed_rows(self, failed_row_numbers: list[int] | None = None) -> None:
        if failed_row_numbers is None:
            if self._pending_summary and getattr(self._pending_summary, "failed_row_numbers", None):
                failed_row_numbers = self._pending_summary.failed_row_numbers
            else:
                failed_row_numbers = self.data_panel.get_failed_row_numbers()

        if not failed_row_numbers:
            self.status_bar.showMessage("No failed rows to retry.")
            return

        first_fail = min(failed_row_numbers)
        # Resume from the first failed row, but never past the range the user chose:
        # a previous retry keeps its own row set, otherwise honour its end row.
        prev = self._last_run_opts or {}
        prev_row_nums = prev.get("custom_row_nums")
        allowed = set(prev_row_nums) if prev_row_nums else None
        prev_end = None
        if allowed is None:
            if prev.get("run_1_row"):
                prev_end = prev.get("start_row", 1)
            else:
                prev_end = prev.get("end_row_index")
        retry_rows: list[dict[str, str]] = []
        retry_row_nums: list[int] = []
        excluded_rows = self.data_panel.get_excluded_row_numbers()
        for idx, r_num in enumerate(self._data_row_nums):
            if idx >= len(self._data_rows):
                break
            if prev_end is not None and idx >= int(prev_end):
                break
            if allowed is not None and r_num not in allowed:
                continue
            if r_num in excluded_rows:
                continue
            if r_num >= first_fail:
                retry_rows.append(self._data_rows[idx])
                retry_row_nums.append(r_num)

        if not retry_rows:
            return

        # Preserve user's previous run options (speed, skip_setup, skip_cleanup, step_by_step, etc.)
        opts = copy.deepcopy(self._last_run_opts) if self._last_run_opts else {}
        opts.pop("scheduled", None)
        opts.pop("lock_after", None)
        opts.pop("end_row_index", None)
        opts.pop("reset_statuses", None)
        countdown = float(self._user_settings.get("countdown_seconds", 3) or 0)
        opts.update(
            {
                "start_row": 1,
                "run_1_row": False,
                "custom_rows": retry_rows,
                "custom_row_nums": retry_row_nums,
                "countdown_seconds": countdown,
            }
        )
        self.status_bar.showMessage(
            Strings.RETRY_FAILED_STATUS.format(
                count=len(retry_rows), row=retry_row_nums[0], sec=f"{countdown:g}"
            )
        )
        self._start_execution(opts)

    def _jump_to_step(self, step_id: str) -> None:
        self.action_tree.highlight_step(step_id, is_running=False, is_failed=True)
        for act in self._current_macro.all_actions():
            if act.id == step_id:
                self.prop_panel.set_action(act)
                break

    def _pause_run(self) -> None:
        if self._controller:
            self._controller.pause()

    def _resume_run(self) -> None:
        if self._controller:
            self._controller.resume()

    def _stop_run(self) -> None:
        if self._controller:
            self._controller.stop()

    def _next_step(self) -> None:
        if self._controller:
            self._controller.step_next()

    def _on_engine_run_started(self, run_id: str, total_rows: int) -> None:
        self._run_total_rows = total_rows
        self._run_row_index = 0
        self.floating_panel.update_progress(0, total_rows, Strings.RUN_PANEL_STARTING, 0, 0)

    def _on_engine_row_started(self, row_num: int, row_data: dict) -> None:
        self._run_row_index += 1
        tot = max(1, self._run_total_rows)
        self.floating_panel.update_progress(
            self._run_row_index, tot, Strings.RUN_PANEL_EXECUTING_ROW.format(row=row_num), 0, 0
        )
        self.data_panel.update_row_status(row_num, Strings.STATUS_RUNNING)

    def _on_engine_step_started(self, step_id: str, label: str) -> None:
        self.floating_panel.lbl_step.setText(label or f"Step {step_id}")
        self.action_tree.highlight_step(step_id, is_running=True)

    def _on_engine_step_finished(self, step_id: str, label: str) -> None:
        pass

    def _on_engine_row_finished(self, row_num: int, status: str) -> None:
        self.data_panel.update_row_status(row_num, status)

    def _on_engine_run_finished(self, summary: RunSummary) -> None:
        self._pending_summary = summary
        if summary.persistence_errors:
            self._retained_summaries.append(summary)
        self._execution_phase = "finishing"

    def _on_engine_run_failed(self, failure: StepFailure, screenshot_path: str | None) -> None:
        if failure.step_id:
            self.action_tree.highlight_step(failure.step_id, is_running=False, is_failed=True)

    def _teardown_runner(self) -> None:
        hotkey_mgr = self._hotkey_mgr
        self._hotkey_mgr = None
        try:
            if hotkey_mgr:
                hotkey_mgr.stop()
        except Exception as e:
            print(f"Warning: Could not stop global hotkey manager cleanly: {e}")
        finally:
            self._run_token = None
            self._controller = None
            self._worker_thread = None
            self._is_running = False
            self._execution_phase = "idle"
            self.floating_panel.hide()
            self.data_panel.set_running(False)
            self.btn_run.setEnabled(True)
            self.btn_test_1_row.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._cancel_step_test()
        if self._is_running:
            self._close_requested = True
            self._stop_run()
            event.ignore()
            return

        if not self._confirm_discard_changes():
            self._close_requested = False
            event.ignore()
            return

        # Save window geometry & splitter states to UserSetting/settings.json
        try:
            self._user_settings["window_geometry"] = (
                self.saveGeometry().toHex().data().decode("ascii")
            )
            if hasattr(self, "main_splitter"):
                self._user_settings["main_splitter_state"] = (
                    self.main_splitter.saveState().toHex().data().decode("ascii")
                )
            if hasattr(self, "center_splitter"):
                self._user_settings["center_splitter_state"] = (
                    self.center_splitter.saveState().toHex().data().decode("ascii")
                )
            save_user_settings(self._user_settings)
        except Exception as e:
            print(f"Warning: Failed to persist window layout: {e}")

        if hasattr(self, "overlay"):
            self.overlay.close()
        self.floating_panel.close()
        if self._package_temp:
            self._package_temp.cleanup()
            self._package_temp = None
        super().closeEvent(event)

    def _setup_menu_bar(self) -> None:
        """Setup application menu bar."""
        menubar = self.menuBar()
        menubar.clear()

        cur_lang = get_current_language()

        # Help Menu
        help_title = "도움말 (&H)" if cur_lang == "ko" else "&Help"
        menu_help = menubar.addMenu(help_title)

        act_update = menu_help.addAction(Strings.UPDATE_CHECK_MENU)
        act_update.triggered.connect(self._check_updates_interactive)

        menu_help.addSeparator()

        act_settings = menu_help.addAction(Strings.OPEN_SETTINGS_FOLDER)
        act_settings.triggered.connect(self._open_settings_folder)

        act_results = menu_help.addAction(Strings.OPEN_RESULTS_FOLDER)
        act_results.triggered.connect(self._open_results_folder)

        menu_help.addSeparator()

        act_about = menu_help.addAction(
            "Stepwise 정보 (&A)..." if cur_lang == "ko" else "&About Stepwise..."
        )
        act_about.triggered.connect(self._open_settings)

    def _open_settings_folder(self) -> None:
        from stepwise.core.app_paths import user_settings_directory
        try:
            os.startfile(str(user_settings_directory()))
        except Exception:
            QMessageBox.warning(self, Strings.SAVE_ERROR_TITLE, Strings.FOLDER_OPEN_FAILED)

    def _open_results_folder(self) -> None:
        try:
            res_dir = self._user_settings.get("results_dir") or str(default_results_directory())
            os.makedirs(res_dir, exist_ok=True)
            os.startfile(str(res_dir))
        except Exception:
            QMessageBox.warning(self, Strings.SAVE_ERROR_TITLE, Strings.FOLDER_OPEN_FAILED)

    def _check_updates_interactive(self) -> None:
        """User manually initiated update check via menu."""
        from stepwise import __version__
        from stepwise.services.updater import RateLimitError, fetch_latest_release
        from stepwise.ui.update_dialog import UpdateDialog

        self._cancel_step_test()
        try:
            release_info, status = fetch_latest_release(force=True)
            if status == "update_available" and release_info:
                dlg = UpdateDialog(
                    release_info,
                    is_macro_running=self._is_running,
                    is_scheduler_armed=False,
                    parent=self,
                )
                dlg.exec()
            elif status == "up_to_date":
                QMessageBox.information(
                    self,
                    Strings.UPDATE_UP_TO_DATE_TITLE,
                    Strings.UPDATE_UP_TO_DATE_MSG.format(version=__version__),
                )
            else:
                QMessageBox.information(
                    self,
                    Strings.UPDATE_UP_TO_DATE_TITLE,
                    f"Check completed: {status}",
                )
        except RateLimitError:
            QMessageBox.warning(self, "GitHub Rate Limit", Strings.UPDATE_RATE_LIMITED)
        except Exception as exc:
            QMessageBox.warning(self, "Update Check Failed", str(exc))

    def _check_updates_background(self) -> None:
        """Silent background update check 15s after startup."""
        if self._is_running:
            return

        def _bg_check() -> None:
            try:
                from stepwise.services.updater import fetch_latest_release

                release_info, status = fetch_latest_release(force=False)
                if status == "update_available" and release_info:
                    # Notify UI thread
                    QTimer.singleShot(
                        0,
                        lambda: self._show_update_available(release_info),
                    )
            except Exception:
                # Background check fails silently
                pass

        threading.Thread(target=_bg_check, daemon=True).start()

    def _show_update_available(self, release_info: Any) -> None:
        """Show non-modal update dialog when new release is discovered in background."""
        if self._is_running:
            return
        from stepwise.ui.update_dialog import UpdateDialog

        dlg = UpdateDialog(
            release_info,
            is_macro_running=self._is_running,
            is_scheduler_armed=False,
            parent=self,
        )
        dlg.show()

