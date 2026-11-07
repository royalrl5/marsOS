from __future__ import annotations
import sys

from marsos.ui.app import make_app, run


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    path = next((a for a in argv[1:] if not a.startswith("-")), None)
    app = make_app("org.marsos.Bundle", argv)
    from marsos.apps.bundle.window import BundleWindow
    return run(app, BundleWindow(path))


if __name__ == "__main__":
    sys.exit(main())
