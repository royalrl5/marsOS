from __future__ import annotations
import sys

from marsos import paths
from marsos.ui.app import make_app, run


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    from marsos.apps.welcome.window import done_marker
    if "--first-run" in argv and (paths.is_live() or done_marker().exists()):
        return 0
    app = make_app("org.marsos.Welcome", argv)
    from marsos.apps.welcome.window import WelcomeWindow
    return run(app, WelcomeWindow())


if __name__ == "__main__":
    sys.exit(main())
