"""Common start-up for every marsOS app."""
from __future__ import annotations
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from marsos.ui import anim
from marsos.ui.theme import apply_theme


def make_app(name: str, argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(name)
    app.setDesktopFileName(name)
    apply_theme(app)
    from marsos.ui import workers
    app.aboutToQuit.connect(lambda: workers.wait_idle(2.0))
    return app


def run(app: QApplication, window: QWidget) -> int:
    anim.pop_in(window)
    return app.exec()
