from __future__ import annotations
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget

from marsos.core import updates
from marsos.core.runner import Runner
from marsos.ui.widgets import button, icon_label, label
from marsos.ui.workers import run_async, run_commands


class UpdaterWindow(QMainWindow):
    def __init__(self, runner: Runner | None = None, autocheck: bool = True):
        super().__init__()
        self.setWindowTitle("Software Update"); self.resize(560, 520); self.r = runner or Runner(); self.info = None
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        v = QVBoxLayout(root); v.setContentsMargins(40, 30, 40, 26); v.setSpacing(12)
        v.addWidget(icon_label("system-software-update", "U", 84), 0, Qt.AlignmentFlag.AlignHCenter)
        self.head = label("Checking for updates…", "title", align=Qt.AlignmentFlag.AlignCenter); v.addWidget(self.head)
        self.sub = label("", "subtitle", align=Qt.AlignmentFlag.AlignCenter); v.addWidget(self.sub)
        self.bar = QProgressBar(); self.bar.setRange(0, 0); v.addWidget(self.bar)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.hide(); v.addWidget(self.log, 1)
        v.addStretch(1)
        self.go = button("Update Now", "primary", pill=True); self.go.hide(); self.go.clicked.connect(self.apply)
        v.addWidget(self.go, 0, Qt.AlignmentFlag.AlignHCenter)
        self.restart = button("Restart Now", "primary", pill=True); self.restart.hide()
        self.restart.clicked.connect(lambda: subprocess.Popen(["systemctl", "reboot"])); v.addWidget(self.restart, 0, Qt.AlignmentFlag.AlignHCenter)
        if autocheck:
            self.check()

    def check(self) -> None:
        self.head.setText("Checking for updates…"); self.bar.show(); self.go.hide()
        run_async(lambda: updates.check(self.r), self.show_info, lambda m: self.show_error())

    def show_error(self) -> None:
        self.bar.hide(); self.head.setText("Couldn't check for updates"); self.sub.setText("Please make sure you are connected to the internet.")

    def show_info(self, info: updates.UpdateInfo) -> None:
        self.info = info; self.bar.hide()
        if info.count == 0:
            self.head.setText("Your computer is up to date"); self.sub.setText("marsOS and all your apps are the latest versions.")
            return
        self.head.setText(f"{info.count} update{'s' if info.count != 1 else ''} available")
        self.sub.setText("Includes security and improvements." + (" Your computer will need to restart afterwards." if info.needs_restart else ""))
        self.go.show()

    def apply(self) -> None:
        self.go.hide(); self.bar.show(); self.log.show(); self.head.setText("Updating… please keep your computer on")
        self.sub.setText("You may be asked for your password.")

        def fin(rc: int) -> None:
            self.bar.hide()
            if rc == 0:
                self.head.setText("Everything is up to date"); self.sub.setText("Please restart soon to finish." if self.info and self.info.needs_restart else "All done.")
                self.restart.setVisible(bool(self.info and self.info.needs_restart))
            else:
                self.head.setText("The update didn't finish"); self.sub.setText("Nothing was harmed. Please try again in a little while.")
                self.go.show()
        run_commands(updates.apply_commands(), lambda l: self.log.appendPlainText(l), fin, self.r)
