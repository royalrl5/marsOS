from __future__ import annotations
import sys

from marsos.ui import anim
from marsos.ui.app import make_app


def main(argv: list[str] | None = None) -> int:
    app = make_app("org.marsos.Launchpad", argv)
    from marsos.apps.launchpad.window import LaunchpadWindow
    w = LaunchpadWindow()
    w.showFullScreen(); anim.fade_in(w, 220); w.search.setFocus()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
