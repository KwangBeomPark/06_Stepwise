"""Update notification and installer download dialog for Stepwise."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from stepwise import __version__
from stepwise.core.app_paths import is_installed_build
from stepwise.services.update_worker import UpdateWorker
from stepwise.services.updater import (
    ReleaseInfo,
    can_safely_update,
    execute_installer_handoff,
)
from stepwise.ui.strings import Strings, get_current_language
from stepwise.ui.theme import get_theme_tokens

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class UpdateDialog(QDialog):
    """Non-blocking dialog showing new release notes, download progress, and install actions."""

    def __init__(
        self,
        release_info: ReleaseInfo,
        is_macro_running: bool = False,
        is_scheduler_armed: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.release_info = release_info
        self.is_macro_running = is_macro_running
        self.is_scheduler_armed = is_scheduler_armed
        self._worker: UpdateWorker | None = None
        self._verified_installer_path: str | None = None

        self.setWindowTitle(Strings.UPDATE_AVAILABLE_TITLE)
        self.setMinimumSize(560, 480)
        self.resize(600, 520)

        self._build_ui()
        self._apply_tokens()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Title
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        self.title_lbl = QLabel(f"🚀 Stepwise v{self.release_info.version}")
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_box.addWidget(self.title_lbl)

        cur_lang = get_current_language()
        cur_text = f"현재 버전: v{__version__}  ➜  최신 버전: v{self.release_info.version}" if cur_lang == "ko" else f"Current: v{__version__}  ➜  Latest: v{self.release_info.version}"
        self.subtitle_lbl = QLabel(cur_text)
        self.subtitle_lbl.setStyleSheet("font-size: 13px; color: #94a3b8;")
        title_box.addWidget(self.subtitle_lbl)
        layout.addLayout(title_box)

        # Release Notes Browser
        self.notes_browser = QTextBrowser()
        self.notes_browser.setOpenExternalLinks(False)
        self.notes_browser.anchorClicked.connect(self._on_anchor_clicked)
        # Render markdown release notes
        body = self.release_info.body.strip() if self.release_info.body else "No release notes provided."
        self.notes_browser.setMarkdown(body)
        layout.addWidget(self.notes_browser, stretch=1)

        # Progress bar & Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size: 12px; font-weight: 500;")
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)

        # Safety Gate Notice
        self.gate_notice_lbl = QLabel("")
        self.gate_notice_lbl.setWordWrap(True)
        self.gate_notice_lbl.setStyleSheet("font-size: 12px; color: #ef4444; font-weight: bold;")
        self.gate_notice_lbl.hide()
        layout.addWidget(self.gate_notice_lbl)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.view_web_btn = QPushButton(Strings.UPDATE_VIEW_RELEASE)
        self.view_web_btn.clicked.connect(self._open_web_release)
        btn_layout.addWidget(self.view_web_btn)

        btn_layout.addStretch()

        self.later_btn = QPushButton(Strings.UPDATE_LATER_BTN)
        self.later_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.later_btn)

        self.action_btn = QPushButton(Strings.UPDATE_DOWNLOAD_BTN)
        self.action_btn.setStyleSheet("font-weight: bold;")
        self.action_btn.clicked.connect(self._on_action_clicked)
        btn_layout.addWidget(self.action_btn)

        layout.addLayout(btn_layout)

        self._check_initial_state()

    def _apply_tokens(self) -> None:
        tokens = get_theme_tokens()
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {tokens['bg_window']};
                color: {tokens['text']};
            }}
            QTextBrowser {{
                background-color: {tokens['bg_surface']};
                color: {tokens['text']};
                border: 1px solid {tokens['border']};
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                line-height: 1.5;
            }}
            QProgressBar {{
                border: 1px solid {tokens['border']};
                border-radius: 4px;
                text-align: center;
                background-color: {tokens['bg_alt']};
                color: {tokens['text']};
                height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: {tokens['accent']};
                border-radius: 3px;
            }}
            """
        )

    def _check_initial_state(self) -> None:
        """Check if dev mode or active state blocks automatic updating."""
        if not is_installed_build():
            # Running from source tree or portable build
            self.action_btn.setText(Strings.UPDATE_VIEW_RELEASE)
            self.gate_notice_lbl.setText(Strings.UPDATE_DEV_MODE_NOTICE)
            self.gate_notice_lbl.setStyleSheet("font-size: 12px; color: #f59e0b; font-weight: 500;")
            self.gate_notice_lbl.show()
            self.action_btn.clicked.disconnect()
            self.action_btn.clicked.connect(self._open_web_release)

    def _on_anchor_clicked(self, url: QUrl) -> None:
        """Open web links safely in default browser."""
        if url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)

    def _open_web_release(self) -> None:
        """Open GitHub release page in browser."""
        QDesktopServices.openUrl(QUrl(self.release_info.html_url))

    def _on_action_clicked(self) -> None:
        """Handle download or install action depending on state."""
        if self._verified_installer_path:
            self._execute_install()
            return

        # Start download
        self.action_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.status_lbl.show()
        self.status_lbl.setText(Strings.UPDATE_CHECKING)

        self._worker = UpdateWorker(self.release_info, parent=self)
        self._worker.progress.connect(self._on_download_progress)
        self._worker.status.connect(self._on_worker_status)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.failed.connect(self._on_download_failed)
        self._worker.start()

    def _on_download_progress(self, percent: int, speed: str, downloaded: int, total: int) -> None:
        self.progress_bar.setValue(percent)
        self.status_lbl.setText(
            Strings.UPDATE_DOWNLOADING.format(progress=percent, speed=speed)
        )

    def _on_worker_status(self, status_key: str) -> None:
        msg = getattr(Strings, status_key, status_key)
        self.status_lbl.setText(msg)

    def _on_download_finished(self, local_path: str) -> None:
        self._verified_installer_path = local_path
        self.progress_bar.setValue(100)
        self.later_btn.setEnabled(True)

        # Verification passed!
        tokens = get_theme_tokens()
        self.status_lbl.setText("✅ " + ("무결성 및 Authenticode 디지털 서명 검증 완료" if get_current_language() == "ko" else "Verified Authenticode Digital Signature & Checksum"))
        self.status_lbl.setStyleSheet(f"font-size: 12px; color: {tokens['status_ok']}; font-weight: bold;")

        self.action_btn.setText(Strings.UPDATE_READY_INSTALL_BTN)
        self.action_btn.setEnabled(True)

        # Check safety gate
        safe, reason = can_safely_update(self.is_macro_running, self.is_scheduler_armed)
        if not safe:
            self.action_btn.setEnabled(False)
            warn_msg = Strings.UPDATE_BLOCKED_RUNNING if reason == "UPDATE_BLOCKED_RUNNING" else Strings.UPDATE_BLOCKED_ARMED
            self.gate_notice_lbl.setText(f"⚠ {warn_msg}")
            self.gate_notice_lbl.show()

    def _on_download_failed(self, error: str) -> None:
        self.later_btn.setEnabled(True)
        self.action_btn.setEnabled(True)
        self.action_btn.setText(Strings.UPDATE_DOWNLOAD_BTN)

        tokens = get_theme_tokens()
        self.status_lbl.setText(f"❌ {Strings.UPDATE_VERIFY_FAILED.format(error=error)}")
        self.status_lbl.setStyleSheet(f"font-size: 12px; color: {tokens['status_fail']}; font-weight: bold;")

    def _execute_install(self) -> None:
        """Launch installer and exit Stepwise cleanly."""
        if not self._verified_installer_path:
            return

        safe, reason = can_safely_update(self.is_macro_running, self.is_scheduler_armed)
        if not safe:
            warn_msg = Strings.UPDATE_BLOCKED_RUNNING if reason == "UPDATE_BLOCKED_RUNNING" else Strings.UPDATE_BLOCKED_ARMED
            self.gate_notice_lbl.setText(f"⚠ {warn_msg}")
            self.gate_notice_lbl.show()
            return

        try:
            execute_installer_handoff(
                self._verified_installer_path,
                language=get_current_language(),
                is_macro_running=self.is_macro_running,
                is_scheduler_armed=self.is_scheduler_armed,
            )
            # Exit main application cleanly
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.quit()
        except Exception as exc:
            self.gate_notice_lbl.setText(f"Error launching installer: {exc}")
            self.gate_notice_lbl.show()

    def closeEvent(self, event) -> None:
        """Cancel running worker on dialog close."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        super().closeEvent(event)
