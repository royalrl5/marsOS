"""Small, gentle animations (fade, slide, pop, bounce). They shrink or vanish with 'Reduce motion' / light effects."""
from __future__ import annotations
from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from marsos.core.prefs import Prefs


def _ms(ms: int) -> int:
    return int(ms * Prefs.load().anim_factor)


def fade_in(w: QWidget, ms: int = 240) -> None:
    d = _ms(ms)
    if d <= 0:
        return
    eff = QGraphicsOpacityEffect(w); eff.setOpacity(0.0); w.setGraphicsEffect(eff)
    a = QPropertyAnimation(eff, b"opacity", w)
    a.setDuration(d); a.setStartValue(0.0); a.setEndValue(1.0); a.setEasingCurve(QEasingCurve.Type.OutCubic)
    a.finished.connect(lambda: w.setGraphicsEffect(None))
    w._fade = a; a.start()


def pop_in(window: QWidget, ms: int = 260) -> None:
    """Window appears by growing slightly from 96% while fading in (like opening a macOS window)."""
    d = _ms(ms)
    window.setWindowOpacity(0.0 if d else 1.0)
    window.show()
    if d <= 0:
        return
    g = window.geometry()
    dx, dy = int(g.width() * 0.02), int(g.height() * 0.02)
    start = QRect(g.x() + dx, g.y() + dy, g.width() - 2 * dx, g.height() - 2 * dy)
    geo = QPropertyAnimation(window, b"geometry", window)
    geo.setDuration(d); geo.setStartValue(start); geo.setEndValue(g); geo.setEasingCurve(QEasingCurve.Type.OutCubic)
    op = QPropertyAnimation(window, b"windowOpacity", window)
    op.setDuration(d); op.setStartValue(0.0); op.setEndValue(1.0)
    window._pop = (geo, op); geo.start(); op.start()


def bounce(w: QWidget, height: int = 14, ms: int = 520) -> None:
    d = _ms(ms)
    if d <= 0:
        return
    p = w.pos()
    a = QPropertyAnimation(w, b"pos", w)
    a.setDuration(d); a.setKeyValueAt(0, p); a.setKeyValueAt(0.4, QPoint(p.x(), p.y() - height)); a.setKeyValueAt(1, p)
    a.setEasingCurve(QEasingCurve.Type.OutBounce)
    w._bounce = a; a.start()


def slide_fade(w: QWidget, dx: int = 0, dy: int = 18, ms: int = 280) -> None:
    fade_in(w, ms)
    d = _ms(ms)
    if d <= 0:
        return
    p = w.pos()
    a = QPropertyAnimation(w, b"pos", w)
    a.setDuration(d); a.setStartValue(QPoint(p.x() + dx, p.y() + dy)); a.setEndValue(p)
    a.setEasingCurve(QEasingCurve.Type.OutCubic)
    w._slide = a; a.start()
