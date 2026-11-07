"""Reusable macOS-style widgets."""
from __future__ import annotations
import hashlib

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from marsos.ui import anim
from marsos.ui.theme import current_colors


def label(text: str = "", role: str = "", wrap: bool = True, align=None) -> QLabel:
    l = QLabel(text)
    if role:
        l.setProperty("role", role)
    l.setWordWrap(wrap)
    if align is not None:
        l.setAlignment(align)
    return l


def button(text: str, kind: str = "", pill: bool = False) -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setProperty(kind, True)
    if pill:
        b.setProperty("pill", True)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


class Card(QFrame):
    def __init__(self, parent=None, warn: bool = False):
        super().__init__(parent)
        self.setProperty("card", "warn" if warn else "true")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 16, 18, 16)
        self.lay.setSpacing(8)


def separator() -> QFrame:
    f = QFrame(); f.setProperty("sep", True); f.setFixedHeight(1)
    return f


_PALETTE = [("#FF9F0A", "#FF375F"), ("#0A84FF", "#5E5CE6"), ("#30D158", "#00C7BE"), ("#BF5AF2", "#FF375F"),
            ("#FFD60A", "#FF9F0A"), ("#64D2FF", "#0A84FF")]


def icon_pixmap(name: str, text: str, size: int = 48) -> QPixmap:
    """Theme icon if available, otherwise a rounded gradient tile with the app's first letter."""
    if name:
        ic = QIcon.fromTheme(name)
        if not ic.isNull():
            return ic.pixmap(QSize(size, size))
    pm = QPixmap(size, size); pm.fill(Qt.GlobalColor.transparent)
    c1, c2 = _PALETTE[int(hashlib.md5((text or "?").encode()).hexdigest(), 16) % len(_PALETTE)]
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(0, 0, size, size); g.setColorAt(0, QColor(c1)); g.setColorAt(1, QColor(c2))
    path = QPainterPath(); path.addRoundedRect(QRectF(0, 0, size, size), size * 0.225, size * 0.225)
    p.fillPath(path, g)
    p.setPen(Qt.GlobalColor.white); f = QFont(); f.setBold(True); f.setPixelSize(int(size * 0.5)); p.setFont(f)
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, (text or "?")[0].upper())
    p.end()
    return pm


def icon_label(name: str, text: str, size: int = 48) -> QLabel:
    l = QLabel(); l.setPixmap(icon_pixmap(name, text, size)); l.setFixedSize(size, size)
    return l


class Toggle(QAbstractButton):
    """iOS/macOS-style switch with an animated knob."""
    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True); self.setChecked(checked); self.setFixedSize(46, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._go)

    def _go(self, on: bool) -> None:
        ms = anim._ms(180)
        self._anim.stop(); self._anim.setDuration(max(ms, 1))
        self._anim.setStartValue(self._pos); self._anim.setEndValue(1.0 if on else 0.0); self._anim.start()

    def _get(self) -> float:
        return self._pos

    def _set(self, v: float) -> None:
        self._pos = v; self.update()

    knob = Property(float, _get, _set)

    def sizeHint(self) -> QSize:
        return QSize(46, 28)

    def paintEvent(self, _e) -> None:
        c = current_colors(); p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        off, on = QColor(c["scroll"]), QColor(c["ok"] if False else c["accent"])
        t = self._pos
        track = QColor(int(off.red() + (on.red() - off.red()) * t), int(off.green() + (on.green() - off.green()) * t),
                       int(off.blue() + (on.blue() - off.blue()) * t))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(track); p.drawRoundedRect(QRectF(0, 2, 46, 24), 12, 12)
        p.setBrush(QColor("white")); p.drawEllipse(QRectF(3 + 20 * t, 4, 20, 20)); p.end()


class FadeStack(QStackedWidget):
    """Stacked pages that fade in when switched."""
    def go(self, index: int) -> None:
        self.setCurrentIndex(index)
        w = self.currentWidget()
        if w is not None:
            anim.fade_in(w, 220)


class SettingRow(QWidget):
    """label + optional description on the left, control on the right."""
    def __init__(self, title: str, desc: str = "", control: QWidget | None = None, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self); h.setContentsMargins(0, 6, 0, 6); h.setSpacing(14)
        col = QVBoxLayout(); col.setSpacing(2)
        col.addWidget(label(title, "heading" if False else ""))
        if desc:
            col.addWidget(label(desc, "caption"))
        h.addLayout(col, 1)
        if control is not None:
            h.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        self.control = control
