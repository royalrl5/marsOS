"""A macOS-style segmented control and colour swatches."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from marsos.ui.theme import accent_hex, current_colors


class Segmented(QWidget):
    changed = Signal(object)

    def __init__(self, options: list[tuple[str, object]], current=None):
        super().__init__()
        h = QHBoxLayout(self); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        self.group = QButtonGroup(self); self.group.setExclusive(True); self.values = []
        for i, (text, val) in enumerate(options):
            b = QPushButton(text); b.setCheckable(True); b.setCursor(Qt.CursorShape.PointingHandCursor)
            r = "9px" if True else ""
            tl, bl = (r if i == 0 else "0"), (r if i == 0 else "0")
            tr, br = (r if i == len(options) - 1 else "0"), (r if i == len(options) - 1 else "0")
            b.setStyleSheet(f"QPushButton {{ border-radius: 0; border-top-left-radius:{tl}; border-bottom-left-radius:{bl};"
                            f"border-top-right-radius:{tr}; border-bottom-right-radius:{br}; padding: 7px 16px; }}"
                            f"QPushButton:checked {{ background: {current_colors()['accent']}; color: white; border-color: {current_colors()['accent']}; }}")
            self.group.addButton(b, i); h.addWidget(b); self.values.append(val)
            if val == current:
                b.setChecked(True)
        if self.group.checkedId() < 0 and options:
            self.group.button(0).setChecked(True)
        self.group.idClicked.connect(lambda i: self.changed.emit(self.values[i]))

    def value(self):
        return self.values[self.group.checkedId()]


class Swatches(QWidget):
    changed = Signal(str)

    def __init__(self, names: list[str], current: str):
        super().__init__()
        h = QHBoxLayout(self); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        self.group = QButtonGroup(self); self.names = names
        for i, n in enumerate(names):
            b = QPushButton(); b.setCheckable(True); b.setFixedSize(26, 26); b.setToolTip(n.title())
            b.setStyleSheet(f"QPushButton {{ background: {accent_hex(n)}; border-radius: 13px; border: 3px solid transparent; padding: 0; }}"
                            f"QPushButton:checked {{ border: 3px solid {current_colors()['text']}; }}")
            self.group.addButton(b, i); h.addWidget(b)
            b.setChecked(n == current)
        self.group.idClicked.connect(lambda i: self.changed.emit(self.names[i]))
