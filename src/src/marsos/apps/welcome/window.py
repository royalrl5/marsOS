from __future__ import annotations
import json
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QProgressBar, QVBoxLayout, QWidget

from marsos import paths
from marsos.core import hardware, system
from marsos.core.prefs import Prefs
from marsos.core.runner import Runner
from marsos.ui.segmented import Segmented
from marsos.ui.widgets import Card, FadeStack, button, label
from marsos.ui.wifi import WifiPanel
from marsos.ui.workers import run_async


def done_marker() -> Path:
    return paths.config_dir() / "welcome-done"


class Slide(QWidget):
    def __init__(self, title: str, sub: str = ""):
        super().__init__()
        self.v = QVBoxLayout(self); self.v.setContentsMargins(60, 36, 60, 10); self.v.setSpacing(14)
        self.v.addWidget(label(title, "hero")); 
        if sub:
            self.v.addWidget(label(sub, "subtitle"))


class WelcomeWindow(QMainWindow):
    def __init__(self, runner: Runner | None = None, hw=None):
        super().__init__()
        self.setWindowTitle("Welcome"); self.resize(860, 620)
        self.r, self.prefs, self.hw = runner or Runner(), Prefs.load(), hw or hardware.detect()
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        v = QVBoxLayout(root); v.setContentsMargins(0, 0, 0, 0)
        self.stack = FadeStack(); v.addWidget(self.stack, 1)
        nav = QHBoxLayout(); nav.setContentsMargins(60, 0, 60, 26)
        self.dots = label("", "caption", wrap=False); nav.addWidget(self.dots, 1)
        self.back = button("Back"); self.next = button("Continue", "primary", pill=True)
        self.back.clicked.connect(lambda: self.go(self.stack.currentIndex() - 1)); self.next.clicked.connect(self.forward)
        nav.addWidget(self.back); nav.addWidget(self.next); v.addLayout(nav)

        s = Slide("Hello", "Welcome to marsOS. Let's make yourself at home.")
        s.v.addWidget(label("It looks and works much like a Mac, so you'll feel right at home. "
                            "The next few steps take about two minutes.")); s.v.addStretch(1); self.stack.addWidget(s)
        s = Slide("Connect to Wi-Fi"); c = Card(); c.lay.addWidget(WifiPanel(self.r)); s.v.addWidget(c); self.stack.addWidget(s)
        s = Slide("Make it comfortable", "You can change these any time in System Settings.")
        c = Card(); c.lay.addWidget(label("Text size", "heading"))
        cur = min(system.SCALES.values(), key=lambda x: abs(x - self.prefs.text_scale))
        seg = Segmented(list(system.SCALES.items()), cur); seg.changed.connect(self.set_scale); c.lay.addWidget(seg)
        c.lay.addWidget(label("Look", "heading"))
        look = Segmented([("Automatic", "auto"), ("Light", "light"), ("Dark", "dark")], self.prefs.appearance); look.changed.connect(self.set_look)
        c.lay.addWidget(look); s.v.addWidget(c); s.v.addStretch(1); self.stack.addWidget(s)
        s = Slide("Things worth knowing")
        for t, d in (("Search for anything", "Press ⌘ Space (or Ctrl Space) to open Spotlight. Type an app, a file, a sum, or “restart”."),
                     ("Find your apps", "Click the rocket in the Dock to see every app. The App Store has more, each with a plain explanation."),
                     ("Stay up to date", "System Settings → Software Update keeps marsOS safe and fresh.")):
            c = Card(); c.lay.addWidget(label(t, "heading")); c.lay.addWidget(label(d)); s.v.addWidget(c)
        s.v.addStretch(1); self.stack.addWidget(s)
        self.pending = Slide("Setting up your apps", "Your chosen apps are being downloaded. You can keep using your computer.")
        self.pbar = QProgressBar(); self.pbar.setRange(0, 100); self.pstat = label("", "caption")
        self.pending.v.addWidget(self.pbar); self.pending.v.addWidget(self.pstat); self.pending.v.addStretch(1); self.stack.addWidget(self.pending)
        s = Slide("You're all set"); s.v.addWidget(label("Enjoy marsOS.", "subtitle")); s.v.addStretch(1); self.stack.addWidget(s)
        self.timer = QTimer(self); self.timer.timeout.connect(self.poll); self.timer.start(2000)
        self.go(0)

    def has_pending(self) -> bool:
        return paths.pending_file().exists() or paths.pending_status_file().exists()

    def set_scale(self, v) -> None:
        self.prefs.text_scale = v; self.prefs.save(); run_async(lambda: system.apply_text_scale(self.r, v))

    def set_look(self, v) -> None:
        self.prefs.appearance = v; self.prefs.save()
        if v != "auto":
            run_async(lambda: system.apply_appearance(self.r, v == "dark", self.prefs.accent))

    def poll(self) -> None:
        try:
            st = json.loads(paths.pending_status_file().read_text())
        except (OSError, ValueError):
            return
        total = max(1, st.get("total", 1)); self.pbar.setValue(int(100 * st.get("done", 0) / total))
        self.pstat.setText("All apps are ready." if st.get("finished") else f"Getting {st.get('current') or '…'}  ({st.get('done', 0)} of {total})")

    def steps(self) -> list[int]:
        n = self.stack.count()
        return [i for i in range(n) if i != 4 or self.has_pending()]

    def go(self, i: int) -> None:
        order = self.steps()
        if i not in order:
            i = min(order, key=lambda x: abs(x - i))
        self.stack.go(i); pos = order.index(i)
        self.dots.setText("  ".join("●" if k == pos else "○" for k in range(len(order))))
        self.back.setVisible(pos > 0); last = pos == len(order) - 1
        self.next.setText("Get Started" if last else "Continue")

    def forward(self) -> None:
        order = self.steps(); pos = order.index(self.stack.currentIndex())
        if pos == len(order) - 1:
            done_marker().parent.mkdir(parents=True, exist_ok=True); done_marker().write_text("1"); self.close()
        else:
            self.go(order[pos + 1])
