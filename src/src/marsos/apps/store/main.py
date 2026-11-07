from __future__ import annotations
import sys

from marsos.ui.app import make_app, run


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    focus = argv[argv.index("--app") + 1] if "--app" in argv and argv.index("--app") + 1 < len(argv) else None
    app = make_app("org.marsos.Store", argv)
    from marsos.apps.store.window import StoreWindow
    return run(app, StoreWindow(focus_app=focus))


if __name__ == "__main__":
    sys.exit(main())
