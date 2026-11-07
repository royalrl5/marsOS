"""Wi-Fi picker used by Welcome, Settings and Control Center. No terminal, no jargon."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from marsos.core import network
from marsos.core.runner import Runner
from marsos.ui.widgets import Toggle, button, label
from marsos.ui.workers import run_async

BARS = ["▂", "▂▄", "▂▄▆", "▂▄▆█"]


class WifiPanel(QWidget):
    def __init__(self, runner: Runner | None = None, parent=None):
        super().__init__(parent)
        self.r = runner or Runner()
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(label("Wi-Fi", "heading"), 1)
        self.switch = Toggle(True); top.addWidget(self.switch)
        v.addLayout(top)
        self.status = label("Looking for networks…", "caption"); v.addWidget(self.status)
        self.list = QListWidget(); self.list.setObjectName("plain"); self.list.setMinimumHeight(190)
        self.list.itemActivated.connect(self._pick); self.list.itemClicked.connect(self._pick)
        v.addWidget(self.list, 1)
        self.refresh_btn = button("Look again"); self.refresh_btn.clicked.connect(lambda: self.refresh(True))
        v.addWidget(self.refresh_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.switch.toggled.connect(self._toggle)
        self.refresh()

    def refresh(self, rescan: bool = False) -> None:
        self.status.setText("Looking for networks…")
        run_async(lambda: (network.wifi_enabled(self.r), network.list_wifi(self.r, rescan)), self._show)

    def _show(self, res) -> None:
        on, nets = res
        self.switch.blockSignals(True); self.switch.setChecked(on); self.switch._pos = 1.0 if on else 0.0
        self.switch.update(); self.switch.blockSignals(False)
        self.list.clear()
        if not on:
            self.status.setText("Wi-Fi is turned off."); return
        if not nets:
            self.status.setText("No networks found. Move closer to your router and tap “Look again”."); return
        self.status.setText("Tap your home network to connect.")
        for n in nets:
            lock = "🔒 " if n.secured else ""
            it = QListWidgetItem(f"{'✓ ' if n.in_use else ''}{n.ssid}      {lock}{BARS[n.bars - 1]}")
            it.setData(Qt.ItemDataRole.UserRole, n); self.list.addItem(it)

    def _toggle(self, on: bool) -> None:
        run_async(lambda: network.set_wifi(self.r, on), lambda _: self.refresh(on))

    def _pick(self, item: QListWidgetItem) -> None:
        n = item.data(Qt.ItemDataRole.UserRole)
        if n.in_use:
            return
        pw = None
        if n.secured:
            pw, ok = QInputDialog.getText(self, f"Join “{n.ssid}”", "Enter the Wi-Fi password:", QLineEdit.EchoMode.Password)
            if not ok or not pw:
                return
        self.status.setText(f"Connecting to {n.ssid}…")
        run_async(lambda: network.connect(self.r, n.ssid, pw), self._connected)

    def _connected(self, res) -> None:
        ok, msg = res
        self.status.setText(msg)
        self.status.setProperty("role", "ok" if ok else "warn")
        self.status.style().unpolish(self.status); self.status.style().polish(self.status)
        self.refresh()
