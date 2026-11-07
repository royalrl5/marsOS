from __future__ import annotations
import sys

from PySide6.QtGui import QCursor, QGuiApplication

from marsos.ui import anim
from marsos.ui.app import make_app


def main(argv: list[str] | None = None) -> int:
    app = make_app("org.marsos.ControlCenter", argv)
    from marsos.apps.controlcenter.window import ControlCenter
    w = ControlCenter(); w.adjustSize()
    scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    g = scr.availableGeometry(); w.move(g.right() - w.width() - 10, g.top() + 6)
    w.show(); anim.fade_in(w, 160)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
