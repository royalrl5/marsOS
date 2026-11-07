from __future__ import annotations
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QMainWindow, QScrollArea, QWidget

from marsos.apps.settings import panes
from marsos.core import hardware
from marsos.core.prefs import Prefs
from marsos.core.runner import Runner
from marsos.ui.widgets import FadeStack


class SettingsWindow(QMainWindow):
    def __init__(self, pane: str = "wifi", runner: Runner | None = None, hw=None):
        super().__init__()
        self.setWindowTitle("System Settings"); self.resize(900, 640)
        r, prefs, hw = runner or Runner(), Prefs.load(), hw or hardware.detect()
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        h = QHBoxLayout(root); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        self.side = QListWidget(); self.side.setObjectName("sidebar"); self.side.setFixedWidth(230); h.addWidget(self.side)
        self.stack = FadeStack(); h.addWidget(self.stack, 1)
        self.index = {}
        for i, (pid, title) in enumerate(panes.ORDER):
            self.side.addItem(QListWidgetItem(title))
            sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(panes.PANES[pid](r, prefs, hw)); self.stack.addWidget(sc)
            self.index[pid] = i
        self.index["bluetooth"] = 0
        self.side.currentRowChanged.connect(self.stack.go)
        self.side.setCurrentRow(self.index.get(pane, 0))
