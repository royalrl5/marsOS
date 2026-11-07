from __future__ import annotations
import sys

from marsos.ui.app import make_app, run


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    pane = argv[argv.index("--pane") + 1] if "--pane" in argv and argv.index("--pane") + 1 < len(argv) else "wifi"
    app = make_app("org.marsos.Settings", argv)
    from marsos.apps.settings.window import SettingsWindow
    return run(app, SettingsWindow(pane))


if __name__ == "__main__":
    sys.exit(main())
