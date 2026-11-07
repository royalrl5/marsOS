from __future__ import annotations
import sys

from marsos.ui.app import make_app, run


def main(argv: list[str] | None = None) -> int:
    app = make_app("org.marsos.Updater", argv)
    from marsos.apps.updater.window import UpdaterWindow
    return run(app, UpdaterWindow())


if __name__ == "__main__":
    sys.exit(main())
