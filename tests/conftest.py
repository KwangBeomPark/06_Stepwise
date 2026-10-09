"""Keep all default runtime paths away from the real user's settings during tests."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def isolated_user_data(tmp_path_factory):
    root = tmp_path_factory.mktemp("stepwise-user-data")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("LOCALAPPDATA", str(root / "Local"))
        patch.setenv("APPDATA", str(root / "Roaming"))
        patch.setenv("USERPROFILE", str(root / "Profile"))
        yield root


@pytest.fixture(autouse=True)
def isolated_working_directory(tmp_path, monkeypatch):
    """Relative result paths from runner tests must stay in a disposable folder."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def dispose_test_windows():
    """Destroy test-owned widgets while their QApplication is still alive.

    Several widget tests use local session application fixtures and signal cycles.
    Leaving those windows to Python shutdown can destroy Qt children after the
    application, which aborts the native Windows process nondeterministically.
    """
    yield
    app = QApplication.instance()
    if app is not None:
        for widget in app.topLevelWidgets():
            widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
