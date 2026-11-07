from __future__ import annotations
import subprocess

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QSlider, QVBoxLayout, QWidget

from marsos.core import network, system
from marsos.core.prefs import Prefs
from marsos.core.runner import Runner
from marsos.ui.theme import current_colors
from marsos.ui.widgets import Card, Toggle, button, label
from marsos.ui.workers import run_async


class Tile(Card):
    def __init__(self, title: str, sub: str, checked: bool):
        super().__init__()
        h = QHBoxLayout(); col = QVBoxLayout(); col.setSpacing(0)
        col.addWidget(label(title, "heading", wrap=False)); self.sub = label(sub, "caption", wrap=False); col.addWidget(self.sub)
        h.addLayout(col, 1); self.toggle = Toggle(checked); h.addWidget(self.toggle); self.lay.addLayout(h)


class ControlCenter(QWidget):
    """Quick settings popup (Wi-Fi, Bluetooth, dark mode, brightness, volume)."""
    def __init__(self, runner: Runner | None = None, popup: bool = True):
        super().__init__()
        self.r = runner or Runner(); self.prefs = Prefs.load()
        if popup:
            self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFixedWidth(360); self.setObjectName("root")
        v = QVBoxLayout(self); v.setContentsMargins(14, 14, 14, 14); v.setSpacing(10)
        self.wifi = Tile("Wi-Fi", "…", True); self.bt = Tile("Bluetooth", "…", False)
        self.dark = Tile("Dark Mode", "Easier on the eyes at night", current_colors().get("dark", False))
        for t in (self.wifi, self.bt, self.dark):
            v.addWidget(t)
        self.wifi.toggle.toggled.connect(lambda on: run_async(lambda: network.set_wifi(self.r, on)))
        self.bt.toggle.toggled.connect(lambda on: run_async(lambda: network.set_bluetooth(self.r, on)))
        self.dark.toggle.toggled.connect(self.set_dark)
        b = Card(); b.lay.addWidget(label("Display", "heading")); self.bright = QSlider(Qt.Orientation.Horizontal); self.bright.setRange(5, 100); b.lay.addWidget(self.bright)
        b.lay.addWidget(label("Sound", "heading")); self.vol = QSlider(Qt.Orientation.Horizontal); self.vol.setRange(0, 100); b.lay.addWidget(self.vol)
        v.addWidget(b)
        self.bright.sliderReleased.connect(lambda: network.set_brightness(self.r, self.bright.value()))
        self.vol.valueChanged.connect(lambda x: network.set_volume(self.r, x))
        s = button("System Settings…", "flat"); s.clicked.connect(lambda: (subprocess.Popen(["marsos-settings"], start_new_session=True), self.close()))
        v.addWidget(s, 0, Qt.AlignmentFlag.AlignRight)
        run_async(lambda: (network.wifi_enabled(self.r), network.bluetooth_enabled(self.r), network.get_brightness(self.r), network.get_volume(self.r)), self.populate)

    def populate(self, st) -> None:
        w, b, br, vo = st
        for t, on in ((self.wifi, w), (self.bt, b)):
            t.toggle.blockSignals(True); t.toggle.setChecked(on); t.toggle._pos = 1.0 if on else 0.0; t.toggle.update(); t.toggle.blockSignals(False)
        self.wifi.sub.setText("On" if w else "Off"); self.bt.sub.setText("On" if b else "Off")
        if br: self.bright.setValue(br)
        if vo is not None: self.vol.setValue(vo)

    def set_dark(self, on: bool) -> None:
        self.prefs.appearance = "dark" if on else "light"; self.prefs.save()
        run_async(lambda: system.apply_appearance(self.r, on, self.prefs.accent))
