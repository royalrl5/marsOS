"""Run slow things (network, commands) off the GUI thread and deliver results back safely."""
from __future__ import annotations
import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot

from marsos.core.runner import Runner

_live: set = set()
_active = 0
_lock = threading.Lock()


def _enter():
    global _active
    with _lock: _active += 1


def _leave():
    global _active
    with _lock: _active -= 1


def wait_idle(timeout: float = 5.0) -> None:
    """Let background work finish (used on shutdown and in tests)."""
    import time
    from PySide6.QtCore import QCoreApplication
    end = time.time() + timeout
    while _active > 0 and time.time() < end:
        QCoreApplication.processEvents(); time.sleep(0.01)
    QCoreApplication.processEvents()


class _Bridge(QObject):
    result = Signal(object)
    error = Signal(str)
    line = Signal(str)
    finished = Signal(int)

    def __init__(self, on_result=None, on_error=None, on_line=None, on_finished=None):
        super().__init__()
        self._r, self._e, self._l, self._f = on_result, on_error, on_line, on_finished
        self.result.connect(self._got_result); self.error.connect(self._got_error)
        self.line.connect(self._got_line); self.finished.connect(self._got_finished)

    @Slot(object)
    def _got_result(self, v):
        if self._r: self._r(v)
        _live.discard(self)

    @Slot(str)
    def _got_error(self, m):
        if self._e: self._e(m)
        _live.discard(self)

    @Slot(str)
    def _got_line(self, s):
        if self._l: self._l(s)

    @Slot(int)
    def _got_finished(self, rc):
        if self._f: self._f(rc)
        _live.discard(self)


def run_async(fn: Callable, on_result: Callable | None = None, on_error: Callable | None = None) -> None:
    b = _Bridge(on_result=on_result, on_error=on_error); _live.add(b)

    def work():
        try:
            b.result.emit(fn())
        except Exception as e:  # noqa: BLE001
            b.error.emit(str(e))
        finally:
            _leave()
    _enter()
    threading.Thread(target=work, daemon=True).start()


def run_commands(cmds: list[list[str]], on_line: Callable[[str], None], on_finished: Callable[[int], None],
                 runner: Runner | None = None) -> None:
    """Run commands one after another, streaming output lines; stops at the first failure."""
    b = _Bridge(on_line=on_line, on_finished=on_finished); _live.add(b)
    r = runner or Runner()

    def work():
        rc = 0
        for c in cmds:
            rc = r.stream(c, lambda l: b.line.emit(l))
            if rc != 0:
                break
        b.finished.emit(rc); _leave()
    _enter()
    threading.Thread(target=work, daemon=True).start()
