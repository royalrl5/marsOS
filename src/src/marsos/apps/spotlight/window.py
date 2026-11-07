from __future__ import annotations
from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from marsos.core import search as S
from marsos.ui.theme import current_colors
from marsos.ui.widgets import icon_pixmap, label


class Row(QWidget):
    def __init__(self, r: S.Result):
        super().__init__()
        h = QHBoxLayout(self); h.setContentsMargins(8, 4, 8, 4); h.setSpacing(12)
        ic = label("", wrap=False); ic.setPixmap(icon_pixmap(r.icon, r.title, 34)); ic.setFixedSize(34, 34); h.addWidget(ic)
        col = QVBoxLayout(); col.setSpacing(0)
        col.addWidget(label(r.title, "heading", wrap=False)); col.addWidget(label(r.subtitle, "caption", wrap=False))
        h.addLayout(col, 1)
        kind = {"app": "Application", "settings": "Settings", "file": "Document", "calc": "Calculator", "action": "System",
                "store": "App Store", "web": "Web"}.get(r.kind, "")
        h.addWidget(label(kind, "caption", wrap=False))


class SpotlightWindow(QWidget):
    def __init__(self, engine: S.SearchEngine, perform=S.perform):
        super().__init__()
        self.engine, self.perform = engine, perform
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(700)
        v = QVBoxLayout(self); v.setContentsMargins(16, 14, 16, 14); v.setSpacing(8)
        self.input = QLineEdit(); self.input.setPlaceholderText("Spotlight Search")
        self.input.setStyleSheet("QLineEdit { border: none; background: transparent; font-size: 20pt; padding: 6px 8px; }")
        self.input.textChanged.connect(lambda: self.timer.start(70)); self.input.installEventFilter(self)
        v.addWidget(self.input)
        self.list = QListWidget(); self.list.setObjectName("plain"); self.list.hide()
        self.list.itemActivated.connect(self.run_item); self.list.itemClicked.connect(self.run_item)
        v.addWidget(self.list)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.refresh)
        self.results: list[S.Result] = []

    def refresh(self) -> None:
        self.results = self.engine.search(self.input.text())
        self.list.clear(); self.list.setVisible(bool(self.results))
        for r in self.results:
            it = QListWidgetItem(); w = Row(r); it.setSizeHint(w.sizeHint().expandedTo(w.minimumSizeHint())); self.list.addItem(it); self.list.setItemWidget(it, w)
        if self.results:
            self.list.setCurrentRow(0); self.list.setFixedHeight(min(len(self.results), 8) * 52 + 6)
        self.adjustSize()

    def run_item(self, item=None) -> None:
        row = self.list.currentRow() if item is None else self.list.row(item)
        if not 0 <= row < len(self.results):
            return
        r = self.results[row]
        if r.action and r.action[0] == "copy":
            QGuiApplication.clipboard().setText(r.action[1])
        else:
            self.perform(r)
        self.hide()

    def eventFilter(self, obj, e) -> bool:
        if obj is self.input and e.type() == QEvent.Type.KeyPress:
            k = e.key()
            if k == Qt.Key.Key_Escape:
                self.hide(); return True
            if k in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self.list.count():
                d = 1 if k == Qt.Key.Key_Down else -1
                self.list.setCurrentRow((self.list.currentRow() + d) % self.list.count()); return True
            if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.run_item(); return True
        return super().eventFilter(obj, e)

    def paintEvent(self, _e) -> None:
        c = current_colors(); p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath(); path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 18, 18)
        bg = QColor(c["surface"]); bg.setAlpha(238); p.fillPath(path, bg)
        p.setPen(QColor(c["border"])); p.drawPath(path)

    def popup(self) -> None:
        self.input.clear(); self.list.clear(); self.list.hide(); self.adjustSize()
        scr = QGuiApplication.primaryScreen().availableGeometry()
        self.move(scr.center().x() - self.width() // 2, scr.top() + int(scr.height() * 0.2))
        self.show(); self.raise_(); self.activateWindow(); self.input.setFocus()

    def changeEvent(self, e) -> None:
        if e.type() == QEvent.Type.ActivationChange and not self.isActiveWindow() and self.isVisible():
            QTimer.singleShot(120, lambda: self.hide() if not self.isActiveWindow() else None)
        super().changeEvent(e)
