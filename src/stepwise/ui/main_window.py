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
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
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
    load_user_settings,
    save_user_settings,
)
from stepwise.core.models import ActionItem, Macro
from stepwise.core.package import load_package, save_package
from stepwise.engine.errors import StepFailure
from stepwise.engine.runner import ExecutionCallbacks, RunSummary, run_macro
from stepwise.engine.timing import ExecutionController, SpeedMode
from stepwise.services.hotkeys import GlobalHotkeyManager
from stepwise.services.input_win import VK_MAP
from stepwise.services.screen import get_screen_info
from stepwise.ui.action_tree import ActionTreeWidget
from stepwise.ui.capture_overlay import CaptureOverlay
from stepwise.ui.data_panel import DataPanel
from stepwise.ui.macro_library import MacroLibraryPanel
from stepwise.ui.preflight_dialog import PreflightDialog
from stepwise.ui.properties_panel import PropertiesPanel
from stepwise.ui.run_panel import FloatingRunPanel
from stepwise.ui.run_summary import RunSummaryDialog
from stepwise.ui.screen_crosshair import ScreenCrosshairOverlay
from stepwise.ui.settings_dialog import SettingsDialog
from stepwise.ui.strings import Strings


class RunnerBridge(QObject):
    event = Signal(str, str, object)  # run token, event name, arguments


@dataclass(frozen=True)
class ExecutionSnapshot:
    macro: Macro
    rows: tuple[dict[str, str], ...]
    row_numbers: tuple[int, ...]
    package_dir: str
    data_filepath: str | None
    speed: SpeedMode
    start_row_index: int
    skip_setup: bool
    skip_cleanup: bool
    run_1_row: bool


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

    def _setup_ui(self) -> None:
        # Toolbar
        self.toolbar = QToolBar("Main Controls")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self.btn_run = QPushButton(f"▶ {Strings.RUN}")
        self.btn_run.setObjectName("btn_run")
        self.btn_run.setToolTip(Strings.Tooltips.RUN)
        self.btn_run.clicked.connect(self._on_run_clicked)
        self.toolbar.addWidget(self.btn_run)

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

        self.btn_save = QPushButton("💾 Save")
        self.btn_save.setToolTip(Strings.Tooltips.SAVE_MACRO)
        self.btn_save.clicked.connect(self.save_current_macro)
        self.toolbar.addWidget(self.btn_save)

        self.toolbar.addSeparator()

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
        self.lib_panel.macro_selected.connect(self.load_macro_file)
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
        tree_layout.addWidget(self.action_tree)

        action_btn_layout = QHBoxLayout()
        action_btn_layout.setSpacing(8)

        lbl_add = QLabel("Add Action:")
        lbl_add.setStyleSheet("font-weight: bold; color: #475569;")
        action_btn_layout.addWidget(lbl_add)

        self.btn_add_click = QPushButton("👆 + Click")
        self.btn_add_click.setToolTip(Strings.Tooltips.ADD_CLICK)
        self.btn_add_click.clicked.connect(lambda: self._add_quick_action("click"))

        self.btn_add_type = QPushButton("⌨ + Type")
        self.btn_add_type.setToolTip(Strings.Tooltips.ADD_TYPE)
        self.btn_add_type.clicked.connect(lambda: self._add_quick_action("type_text"))

        self.btn_add_key = QPushButton("↵ + Key")
        self.btn_add_key.setToolTip(Strings.Tooltips.ADD_KEY)
        self.btn_add_key.clicked.connect(lambda: self._add_quick_action("key"))

        self.btn_add_wait = QPushButton("⏱ + Wait")
        self.btn_add_wait.setToolTip(Strings.Tooltips.ADD_WAIT)
        self.btn_add_wait.clicked.connect(lambda: self._add_quick_action("wait"))

        self.btn_add_win = QPushButton("🪟 + Window")
        self.btn_add_win.setToolTip(Strings.Tooltips.ADD_WINDOW)
        self.btn_add_win.clicked.connect(lambda: self._add_quick_action("window_set_bounds"))

        self.btn_move_up = QPushButton(f"↑ {Strings.MOVE_UP}")
        self.btn_move_up.setToolTip("Move selected step up within section (Alt+Up)")
        self.btn_move_up.clicked.connect(self._on_move_up_clicked)

        self.btn_move_down = QPushButton(f"↓ {Strings.MOVE_DOWN}")
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
        self.data_panel.insert_variable_requested.connect(self._insert_variable_into_current_action)
        self.data_panel.row_status_override.connect(self._on_row_status_override)
        self.data_panel.run_only_row_requested.connect(self._on_run_only_row)
        self.center_splitter.addWidget(self.data_panel)

        # Right Column: Properties Panel (Full-height vertical inspector)
        self.prop_panel = PropertiesPanel()
        self.prop_panel.property_changed.connect(self._on_property_changed)
        self.prop_panel.request_pick.connect(self._trigger_pick_overlay)
        self.prop_panel.request_capture.connect(self._trigger_capture_overlay)
        self.prop_panel.request_show_crosshair.connect(self._show_screen_crosshair)
        self.prop_panel.request_test_step.connect(self._test_single_action)
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

    def _update_status_bar_screen_info(self) -> None:
        screen = get_screen_info()
        w, h, scale = screen["width"], screen["height"], screen["scale_percent"]
        rec = self._current_macro.recorded_screen

        if rec.width == w and rec.height == h and rec.scale_percent == scale:
            self.lbl_screen_info.setText(f"Screen {w}x{h} @{scale}% ✅")
            self.lbl_screen_info.setStyleSheet("color: #16a34a; font-weight: 500;")
        else:
            self.lbl_screen_info.setText(f"Screen {w}x{h} @{scale}% ⚠")
            self.lbl_screen_info.setStyleSheet("color: #dc2626; font-weight: bold;")

    def load_macro_file(self, swm_path: str) -> None:
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
            self._update_status_bar_screen_info()
            self.setWindowTitle(f"{macro.name} — {Strings.APP_TITLE}")
            self.status_bar.showMessage(f"Loaded: {macro.name}")
        except Exception as e:
            package_temp.cleanup()
            QMessageBox.critical(self, "Load Error", f"Failed to load macro:\n{e}")

    def save_current_macro(self) -> None:
        path = self._current_macro_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Macro", self._library_dir, "Stepwise Macro (*.swm)"
            )
            if not path:
                return
        try:
            macro_snapshot = copy.deepcopy(self._current_macro)
            image_files: dict[str, bytes] = {}
            for actions in (macro_snapshot.setup, macro_snapshot.per_row, macro_snapshot.cleanup):
                self._collect_package_images(actions, image_files)
            save_package(macro_snapshot, path, image_files=image_files)
        except Exception as e:
            QMessageBox.warning(self, Strings.SAVE_ERROR_TITLE, Strings.SAVE_ERROR.format(error=e))
            return
        self._current_macro_path = path
        self.lib_panel.refresh_list()
        self.status_bar.showMessage(f"Saved: {os.path.basename(self._current_macro_path)}")

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
        self.status_bar.showMessage(f"Added {act_type} to {section.upper()}")

    def _on_request_move_section(self, action: ActionItem, target_section: str) -> None:
        location = self._current_macro.find_action_location(action)
        if location is None or target_section not in ("setup", "per_row", "cleanup"):
            return
        location.items.pop(location.index)
        target_list = getattr(self._current_macro, target_section)
        target_list.append(action)
        self.action_tree.rebuild_tree(select_id=action.id)
        self.status_bar.showMessage(f"Moved step to {target_section.upper()}")

    def _on_request_delete_action(self, action: ActionItem) -> None:
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
        self.status_bar.showMessage("Moved step up" if offset < 0 else "Moved step down")

    def _show_screen_crosshair(self, x: int, y: int) -> None:
        self._crosshair_overlay = ScreenCrosshairOverlay(x, y)
        self.status_bar.showMessage(f"Displaying target coordinate ({x}, {y}) on screen (1.5s)...")

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
        self._data_filepath = filepath
        self._data_headers = headers
        self._data_rows = rows
        self._data_row_nums = (
            list(row_nums) if row_nums is not None else list(range(1, len(rows) + 1))
        )
        self.prop_panel.update_variable_completions(headers)
        self.status_bar.showMessage(
            f"Connected data: {os.path.basename(filepath)} ({len(rows)} rows)"
        )

    def _on_row_status_override(self, row_num: int, new_status: str) -> None:
        self.status_bar.showMessage(f"Row #{row_num} marked as {new_status}")

    def _on_run_only_row(self, row_num: int) -> None:
        if self._is_running:
            return
        try:
            start_row = self._data_row_nums.index(row_num) + 1
        except ValueError:
            self.status_bar.showMessage(
                f"Cannot run row #{row_num}: row is not in the loaded data."
            )
            return

        opts = {
            "start_row": start_row,
            "speed": SpeedMode.NORMAL,
            "skip_setup": False,
            "skip_cleanup": False,
            "step_by_step": False,
            "run_1_row": True,
        }
        self._start_execution(opts)

    def _insert_variable_into_current_action(self, var_text: str) -> None:
        act = self.prop_panel._current_action
        if act and act.type == "type_text":
            act.text += var_text
            self.prop_panel.set_action(act)
            self.action_tree.rebuild_tree()

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
        dlg = SettingsDialog(parent=self)
        if dlg.exec() == SettingsDialog.Accepted:
            self._user_settings = load_user_settings()
            new_lib = self._user_settings.get("library_dir")
            if new_lib and new_lib != self._library_dir:
                self._library_dir = str(new_lib)
                self.lib_panel.set_library_dir(str(new_lib))
            self.status_bar.showMessage("Settings saved.")

    def _on_run_clicked(self) -> None:
        if self._is_running:
            return
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
        dlg = PreflightDialog(
            macro=self._current_macro,
            rows_data=self._data_rows,
            row_numbers=self._data_row_nums,
            package_dir=self._package_dir,
            data_file_path=self._data_filepath,
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
        self._start_execution(opts)

    def _start_execution(self, opts: dict[str, Any]) -> None:
        if self._is_running or (self._worker_thread and self._worker_thread.is_alive()):
            return
        self._is_running = True
        self._execution_phase = "starting"
        run_token = str(uuid.uuid4())
        self._run_token = run_token
        self._pending_summary = None
        try:
            # All mutable UI state is copied on the UI thread. The worker closes
            # over only these private snapshots, its controller, and run token.
            macro_snapshot = copy.deepcopy(self._current_macro)
            rows_snapshot = copy.deepcopy(self._data_rows)
            row_nums_snapshot = copy.deepcopy(self._data_row_nums)
            opts = copy.deepcopy(opts)
            snapshot = ExecutionSnapshot(
                macro=macro_snapshot,
                rows=tuple(rows_snapshot),
                row_numbers=tuple(row_nums_snapshot),
                package_dir=self._package_dir,
                data_filepath=self._data_filepath,
                speed=opts.get("speed", SpeedMode.NORMAL),
                start_row_index=max(0, opts.get("start_row", 1) - 1),
                skip_setup=opts.get("skip_setup", False),
                skip_cleanup=opts.get("skip_cleanup", False),
                run_1_row=opts.get("run_1_row", False),
            )
        except Exception as e:
            self._teardown_runner()
            QMessageBox.warning(
                self, Strings.RUN_ERROR_TITLE, Strings.SNAPSHOT_ERROR.format(error=e)
            )
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
            QMessageBox.warning(self, Strings.RUN_ERROR_TITLE, Strings.F12_ERROR.format(error=e))
            return

        self.btn_run.setEnabled(False)
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
                    package_dir=snapshot.package_dir,
                    countdown_seconds=0.0,
                    data_filepath=snapshot.data_filepath,
                    row_numbers=snapshot.row_numbers,
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
            QMessageBox.warning(
                self, Strings.RUN_ERROR_TITLE, Strings.RUN_START_ERROR.format(error=e)
            )

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
        if summary:
            dlg = RunSummaryDialog(summary, parent=self)
            dlg.exec()

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
        self.floating_panel.update_progress(0, total_rows, "Starting run...", 0, 0)

    def _on_engine_row_started(self, row_num: int, row_data: dict) -> None:
        self._run_row_index += 1
        tot = max(1, self._run_total_rows)
        self.floating_panel.update_progress(
            self._run_row_index, tot, f"Executing row {row_num}", 0, 0
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
            self.btn_run.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._is_running:
            self._close_requested = True
            self._stop_run()
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
