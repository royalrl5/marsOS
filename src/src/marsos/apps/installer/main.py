from __future__ import annotations
import sys

from marsos import paths
from marsos.ui.app import make_app, run


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    live = "--live" in argv
    if live and not paths.is_live():
        return 0           # autostart entry only applies to the live USB/ISO session
    safe = "--dry-run" in argv or "--demo" in argv or "--i-know-what-i-am-doing" in argv
    if not paths.is_live() and not safe:
        print("marsOS is already installed on this computer. The installer only runs from the installation USB/ISO "
              "(use --demo to preview it safely).", file=sys.stderr)
        return 1
    app = make_app("org.marsos.Installer", argv)
    from marsos.apps.installer.window import InstallerWindow
    w = InstallerWindow(live=paths.is_live(), dry_run="--dry-run" in argv, demo="--demo" in argv)
    return run(app, w)


if __name__ == "__main__":
    sys.exit(main())
