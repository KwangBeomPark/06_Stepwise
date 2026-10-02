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

import os
import threading
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from stepwise.core.models import ActionItem, Macro
from stepwise.core.package import load_package, save_package
from stepwise.engine.errors import StepFailure
from stepwise.engine.runner import ExecutionCallbacks, RunSummary, run_macro
from stepwise.engine.timing import ExecutionController, SpeedMode
from stepwise.services.hotkeys import VK_MAP, GlobalHotkeyManager
from stepwise.services.screen import get_screen_info
from stepwise.ui.action_tree import ActionTreeWidget
from stepwise.ui.capture_overlay import CaptureOverlay
from stepwise.ui.data_panel import DataPanel
from stepwise.ui.macro_library import MacroLibraryPanel
from stepwise.ui.preflight_dialog import PreflightDialog
from stepwise.ui.properties_panel import PropertiesPanel
from stepwise.ui.run_panel import FloatingRunPanel
from stepwise.ui.run_summary import RunSummaryDialog
from stepwise.ui.settings_dialog import SettingsDialog
from stepwise.ui.strings import Strings


class RunnerBridge(QObject):
    run_started = Signal(str, int)
    row_started = Signal(int, dict)
    step_started = Signal(str, str)
    step_finished = Signal(str, str)
    row_finished = Signal(int, str)
    run_finished = Signal(object)
    run_failed = Signal(object, str)


class MainWindow(QMainWindow):
    def __init__(self, library_dir: str = "macros", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(Strings.APP_TITLE)
        self.resize(1200, 800)

        self._current_macro: Macro = Macro()
        self._current_macro_path: str | None = None
        self._library_dir = library_dir
        self._data_filepath: str | None = None
        self._data_headers: list[str] = []
        self._data_rows: list[dict[str, str]] = []
        self._data_row_nums: list[int] = []

        self._controller: ExecutionController | None = None
        self._hotkey_mgr: GlobalHotkeyManager | None = None
        self._worker_thread: threading.Thread | None = None

        self._bridge = RunnerBridge()
        self._bridge.run_started.connect(self._on_engine_run_started)
        self._bridge.row_started.connect(self._on_engine_row_started)
        self._bridge.step_started.connect(self._on_engine_step_started)
        self._bridge.step_finished.connect(self._on_engine_step_finished)
        self._bridge.row_finished.connect(self._on_engine_row_finished)
        self._bridge.run_finished.connect(self._on_engine_run_finished)
        self._bridge.run_failed.connect(self._on_engine_run_failed)

        self.floating_panel = FloatingRunPanel()
        self.floating_panel.pause_clicked.connect(self._pause_run)
        self.floating_panel.resume_clicked.connect(self._resume_run)
        self.floating_panel.stop_clicked.connect(self._stop_run)
        self.floating_panel.next_step_clicked.connect(self._next_step)

        self._setup_ui()
        self._setup_shortcuts()
        self._update_status_bar_screen_info()

    def _setup_ui(self) -> None:
        # Toolbar
        self.toolbar = QToolBar("Main Controls")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self.btn_run = QPushButton(f"▶ {Strings.RUN}")
        self.btn_run.setObjectName("btn_run")
        self.btn_run.clicked.connect(self._on_run_clicked)
        self.toolbar.addWidget(self.btn_run)

        self.btn_pause = QPushButton(f"⏸ {Strings.PAUSE}")
        self.btn_pause.setObjectName("btn_pause")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._pause_run)
        self.toolbar.addWidget(self.btn_pause)

        self.btn_stop = QPushButton(f"■ {Strings.STOP}")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_run)
        self.toolbar.addWidget(self.btn_stop)

        self.toolbar.addSeparator()

        self.btn_settings = QPushButton(f"⚙ {Strings.SETTINGS}")
        self.btn_settings.clicked.connect(self._open_settings)
        self.toolbar.addWidget(self.btn_settings)

        # Splitters
        main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(main_splitter)

        self.lib_panel = MacroLibraryPanel(self._library_dir)
        self.lib_panel.macro_selected.connect(self.load_macro_file)
        main_splitter.addWidget(self.lib_panel)

        center_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(center_splitter)

        tree_container = QWidget()
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(8, 8, 8, 8)
        tree_layout.setSpacing(6)

        self.action_tree = ActionTreeWidget()
        self.action_tree.action_selected.connect(self._on_action_selected)
        tree_layout.addWidget(self.action_tree)

        action_btn_layout = QHBoxLayout()
        self.btn_add_click = QPushButton("+ Click")
        self.btn_add_click.clicked.connect(lambda: self._add_quick_action("click"))
        self.btn_add_type = QPushButton("+ Type")
        self.btn_add_type.clicked.connect(lambda: self._add_quick_action("type_text"))
        self.btn_add_key = QPushButton("+ Key")
        self.btn_add_key.clicked.connect(lambda: self._add_quick_action("key"))
        self.btn_add_wait = QPushButton("+ Wait")
        self.btn_add_wait.clicked.connect(lambda: self._add_quick_action("wait"))
        self.btn_delete = QPushButton(Strings.DELETE)
        self.btn_delete.clicked.connect(self._on_delete_action)

        action_btn_layout.addWidget(self.btn_add_click)
        action_btn_layout.addWidget(self.btn_add_type)
        action_btn_layout.addWidget(self.btn_add_key)
        action_btn_layout.addWidget(self.btn_add_wait)
        action_btn_layout.addWidget(self.btn_delete)
        action_btn_layout.addStretch()
        tree_layout.addLayout(action_btn_layout)

        center_splitter.addWidget(tree_container)

        self.bottom_tabs = QTabWidget()
        self.prop_panel = PropertiesPanel()
        self.prop_panel.property_changed.connect(self._on_property_changed)
        self.prop_panel.request_pick.connect(self._trigger_pick_overlay)
        self.prop_panel.request_capture.connect(self._trigger_capture_overlay)
        self.bottom_tabs.addTab(self.prop_panel, Strings.PROPERTIES_TITLE)

        self.data_panel = DataPanel()
        self.data_panel.data_loaded.connect(self._on_data_loaded)
        self.data_panel.insert_variable_requested.connect(self._insert_variable_into_current_action)
        self.bottom_tabs.addTab(self.data_panel, Strings.DATA_PANEL_TITLE)
        center_splitter.addWidget(self.bottom_tabs)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 4)
        center_splitter.setStretchFactor(0, 3)
        center_splitter.setStretchFactor(1, 2)

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
        try:
            macro, extract_dir = load_package(swm_path)
            self._current_macro = macro
            self._current_macro_path = swm_path
            self.action_tree.load_macro(macro)
            self._update_status_bar_screen_info()
            self.setWindowTitle(f"{macro.name} — {Strings.APP_TITLE}")
            self.status_bar.showMessage(f"Loaded: {macro.name}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load macro:\n{e}")

    def save_current_macro(self) -> None:
        if not self._current_macro_path:
            path, _ = QFileDialog.getSaveFileName(self, "Save Macro", self._library_dir, "Stepwise Macro (*.swm)")
            if not path:
                return
            self._current_macro_path = path

        save_package(self._current_macro, self._current_macro_path)
        self.lib_panel.refresh_list()
        self.status_bar.showMessage(f"Saved: {os.path.basename(self._current_macro_path)}")

    def _on_action_selected(self, action: ActionItem | None) -> None:
        self.prop_panel.set_action(action)

    def _on_property_changed(self) -> None:
        self.action_tree.rebuild_tree()

    def _add_quick_action(self, act_type: str) -> None:
        new_act = ActionItem(type=act_type, enabled=True)
        self._current_macro.per_row.append(new_act)
        self.action_tree.rebuild_tree()

    def _on_delete_action(self) -> None:
        selected = self.action_tree.tree.selectedItems()
        if not selected:
            return
        data = selected[0].data(0, Qt.UserRole)
        if isinstance(data, ActionItem):
            for sec in (self._current_macro.setup, self._current_macro.per_row, self._current_macro.cleanup):
                if data in sec:
                    sec.remove(data)
                    break
            self.action_tree.rebuild_tree()
            self.prop_panel.set_action(None)

    def _on_data_loaded(self, filepath: str, headers: list[str], rows: list[dict[str, str]]) -> None:
        self._data_filepath = filepath
        self._data_headers = headers
        self._data_rows = rows
        self._data_row_nums = list(range(1, len(rows) + 1))
        self.status_bar.showMessage(f"Connected data: {os.path.basename(filepath)}")

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

        self.overlay = CaptureOverlay(mode="pick")
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

        self.overlay = CaptureOverlay(mode="region")
        self.overlay.region_captured.connect(_on_captured)
        self.overlay.show()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(parent=self)
        if dlg.exec() == SettingsDialog.Accepted:
            self.status_bar.showMessage("Settings saved.")

    def _on_run_clicked(self) -> None:
        pkg_dir = os.path.dirname(self._current_macro_path) if self._current_macro_path else None
        dlg = PreflightDialog(
            macro=self._current_macro,
            rows_data=self._data_rows,
            row_numbers=self._data_row_nums,
            package_dir=pkg_dir,
            data_file_path=self._data_filepath,
            parent=self,
        )
        if dlg.exec() != PreflightDialog.Accepted:
            return

        speed = SpeedMode.SLOW if dlg.rad_slow.isChecked() else (SpeedMode.VERY_SLOW if dlg.rad_veryslow.isChecked() else SpeedMode.NORMAL)
        opts = {
            "start_row": dlg.spin_start_row.value(),
            "speed": speed,
            "skip_setup": dlg.chk_skip_setup.isChecked(),
            "skip_cleanup": dlg.chk_cleanup_checked(),
            "step_by_step": dlg.chk_step_by_step.isChecked(),
            "run_1_row": False,
        }
        self._start_execution(opts)

    def _start_execution(self, opts: dict[str, Any]) -> None:
        self._controller = ExecutionController()
        if opts.get("step_by_step"):
            self._controller.enable_step_by_step(True)
            self.floating_panel.set_step_by_step(True)
        else:
            self.floating_panel.set_step_by_step(False)

        speed: SpeedMode = opts.get("speed", SpeedMode.NORMAL)
        self.floating_panel.set_speed_text(speed)

        try:
            self._hotkey_mgr = GlobalHotkeyManager()
            self._hotkey_mgr.start()
            vk_f12 = VK_MAP.get("f12", 0x7B)
            self._hotkey_mgr.register_hotkey(vk_f12, 0, callback=self._controller.stop)
        except Exception as e:
            print(f"Warning: Could not register F12 hotkey: {e}")

        self.btn_run.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)

        self.showMinimized()
        self.floating_panel.show()

        callbacks = ExecutionCallbacks(
            on_run_started=lambda r_id, tot: self._bridge.run_started.emit(r_id, tot),
            on_row_started=lambda r_num, data: self._bridge.row_started.emit(r_num, data),
            on_step_started=lambda s_id, lbl: self._bridge.step_started.emit(s_id, lbl),
            on_step_finished=lambda s_id, lbl: self._bridge.step_finished.emit(s_id, lbl),
            on_row_finished=lambda r_num, st: self._bridge.row_finished.emit(r_num, st),
            on_run_finished=lambda summ: self._bridge.run_finished.emit(summ),
            on_run_failed=lambda fail, shot: self._bridge.run_failed.emit(fail, shot),
        )

        start_idx = max(0, opts.get("start_row", 1) - 1)

        def _worker() -> None:
            pkg_dir = os.path.dirname(self._current_macro_path) if self._current_macro_path else None
            run_macro(
                macro=self._current_macro,
                rows_data=self._data_rows,
                controller=self._controller,
                callbacks=callbacks,
                speed=speed,
                skip_setup=opts.get("skip_setup", False),
                skip_cleanup=opts.get("skip_cleanup", False),
                run_1_row=opts.get("run_1_row", False),
                start_row_index=start_idx,
                package_dir=pkg_dir,
                countdown_seconds=0.0,
            )

        self._worker_thread = threading.Thread(target=_worker, daemon=True)
        self._worker_thread.start()

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
        self.floating_panel.update_progress(0, total_rows, "Starting run...", 0, 0)

    def _on_engine_row_started(self, row_num: int, row_data: dict) -> None:
        tot = len(self._data_rows) if self._data_rows else 1
        self.floating_panel.update_progress(row_num, tot, f"Executing row {row_num}", 0, 0)
        self.data_panel.update_row_status(row_num, Strings.STATUS_RUNNING)

    def _on_engine_step_started(self, step_id: str, label: str) -> None:
        self.floating_panel.lbl_step.setText(label or f"Step {step_id}")
        self.action_tree.highlight_step(step_id, is_running=True)

    def _on_engine_step_finished(self, step_id: str, label: str) -> None:
        pass

    def _on_engine_row_finished(self, row_num: int, status: str) -> None:
        self.data_panel.update_row_status(row_num, status)

    def _on_engine_run_finished(self, summary: RunSummary) -> None:
        self._teardown_runner()
        self.showNormal()
        self.floating_panel.hide()

        dlg = RunSummaryDialog(summary, parent=self)
        dlg.exec()

    def _on_engine_run_failed(self, failure: StepFailure, screenshot_path: str | None) -> None:
        if failure.step_id:
            self.action_tree.highlight_step(failure.step_id, is_running=False, is_failed=True)

    def _teardown_runner(self) -> None:
        if self._hotkey_mgr:
            self._hotkey_mgr.stop()
            self._hotkey_mgr = None
        self.btn_run.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
