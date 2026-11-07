"""marsos-spotlight: runs once as a small background service; the keyboard shortcut runs `marsos-spotlight --toggle`.

The toggle client uses a plain socket and imports no Qt, so pressing the shortcut feels instant even on an old Mac.
"""
from __future__ import annotations
import os
import socket
import sys


def sock_path() -> str:
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "marsos-spotlight.sock")


def send(msg: bytes = b"toggle") -> bool:
    try:
        s = socket.socket(socket.AF_UNIX); s.settimeout(0.5); s.connect(sock_path()); s.sendall(msg); s.close()
        return True
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--toggle" in argv and send():
        return 0
    from PySide6.QtCore import QObject
    from PySide6.QtNetwork import QLocalServer
    from PySide6.QtWidgets import QApplication
    from marsos.ui.app import make_app
    app = make_app("org.marsos.Spotlight", argv); app.setQuitOnLastWindowClosed(False)
    from marsos.apps.spotlight.window import SpotlightWindow
    from marsos.core.desktop_entries import load_all
    from marsos.core.search import FileIndex, SearchEngine
    index = FileIndex(); index.build_async()
    win = SpotlightWindow(SearchEngine(load_all(), index))
    server = QLocalServer(); QLocalServer.removeServer(sock_path())
    if not server.listen(sock_path()):
        return 1

    def on_conn() -> None:
        c = server.nextPendingConnection(); c.waitForReadyRead(200)
        if win.isVisible(): win.hide()
        else: win.popup()
        c.disconnectFromServer()
    server.newConnection.connect(on_conn)
    if "--daemon" not in argv:
        win.popup()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
