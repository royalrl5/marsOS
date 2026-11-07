from __future__ import annotations
import subprocess

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QKeyEvent, QPainter
from PySide6.QtWidgets import QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from marsos.core.desktop_entries import DesktopEntry, load_all
from marsos.core.search import score
from marsos.ui.widgets import icon_pixmap, label


class LaunchpadWindow(QWidget):
    """Full-screen grid of every app, like macOS Launchpad."""
    def __init__(self, entries: list[DesktopEntry] | None = None):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.entries = entries if entries is not None else load_all()
        v = QVBoxLayout(self); v.setContentsMargins(90, 50, 90, 50); v.setSpacing(24)
        self.search = QLineEdit(); self.search.setProperty("search", True); self.search.setPlaceholderText("Search")
        self.search.setFixedWidth(320); self.search.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search.setStyleSheet("background: rgba(255,255,255,40); color: white; border: 1px solid rgba(255,255,255,60);")
        self.search.textChanged.connect(self.fill); v.addWidget(self.search, 0, Qt.AlignmentFlag.AlignHCenter)
        self.grid = QListWidget(); self.grid.setObjectName("plain")
        self.grid.setViewMode(QListWidget.ViewMode.IconMode); self.grid.setIconSize(QSize(72, 72)); self.grid.setGridSize(QSize(140, 126))
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust); self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setWordWrap(True); self.grid.setSpacing(6); self.grid.setStyleSheet("QListWidget { color: white; background: transparent; }"
                                                                                       "QListWidget::item:selected { background: rgba(255,255,255,50); }")
        self.grid.itemActivated.connect(self.launch); self.grid.itemClicked.connect(self.launch)
        v.addWidget(self.grid, 1)
        self.fill("")

    def fill(self, q: str) -> None:
        self.grid.clear()
        items = self.entries if not q else sorted((e for e in self.entries if score(q, e.name) or score(q, e.generic) // 2),
                                                  key=lambda e: -score(q, e.name))
        for e in items:
            it = QListWidgetItem(e.name); it.setIcon(icon_pixmap(e.icon, e.name, 72)); it.setData(Qt.ItemDataRole.UserRole, e)
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter); self.grid.addItem(it)
        if self.grid.count():
            self.grid.setCurrentRow(0)

    def launch(self, item: QListWidgetItem) -> None:
        e: DesktopEntry = item.data(Qt.ItemDataRole.UserRole)
        subprocess.Popen(["gio", "launch", e.path], start_new_session=True)
        self.close()

    def paintEvent(self, _e) -> None:
        p = QPainter(self); p.fillRect(self.rect(), QColor(18, 18, 24, 215))

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.grid.currentItem():
            self.launch(self.grid.currentItem())
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e) -> None:
        if not self.grid.itemAt(self.grid.mapFromParent(e.position().toPoint())):
            self.close()
