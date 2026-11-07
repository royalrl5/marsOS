from __future__ import annotations
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtWidgets import (QHBoxLayout, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
                               QProgressBar, QVBoxLayout, QWidget)

from marsos import paths
from marsos.apps.installer import pages
from marsos.core import catalog, disks as disklib, hardware
from marsos.core.installer_backend import Plan
from marsos.core.runner import Runner
from marsos.ui import anim
from marsos.ui.widgets import FadeStack, button, label

STEPS = ["Welcome", "Disk", "Account", "Apps", "Review", "Installing", "Finished"]


class ProgressPage(pages.Page):
    title = "Installing marsOS"
    subtitle = "Please keep your computer plugged in. This usually takes 5 to 15 minutes."

    def __init__(self):
        super().__init__()
        self.v.addStretch(1)
        self.status = label("Starting…", "heading"); self.v.addWidget(self.status)
        self.bar = QProgressBar(); self.bar.setRange(0, 100); self.v.addWidget(self.bar)
        self.tip = label(pages.TIPS[0], "caption"); self.v.addWidget(self.tip)
        self.v.addStretch(1)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(120); self.log.hide(); self.v.addWidget(self.log)
        self.more = button("Show details", "flat"); self.more.clicked.connect(lambda: (self.log.setVisible(not self.log.isVisible())))
        self.v.addWidget(self.more, 0, Qt.AlignmentFlag.AlignLeft)
        self._i = 0; self.timer = QTimer(self); self.timer.timeout.connect(self._next_tip); self.timer.start(7000)

    def _next_tip(self) -> None:
        self._i = (self._i + 1) % len(pages.TIPS); self.tip.setText(pages.TIPS[self._i]); anim.fade_in(self.tip, 400)


class DonePage(pages.Page):
    def __init__(self, dry: bool):
        super().__init__()
        self.v.addStretch(1)
        self.head = label("marsOS is installed!", "hero"); self.v.addWidget(self.head)
        self.sub = label("", "subtitle"); self.v.addWidget(self.sub)
        self.restart = button("Restart now", "primary", pill=True); self.v.addWidget(self.restart, 0, Qt.AlignmentFlag.AlignLeft)
        self.v.addStretch(1)
        self.dry = dry

    def success(self, is_mac: bool) -> None:
        self.head.setText("marsOS is installed!")
        self.sub.setText("Remove the USB stick or disc, then restart." + (
            " If your Mac doesn't start marsOS, hold the Option (⌥) key while it starts and choose “EFI Boot”." if is_mac else ""))
        self.restart.setVisible(True)

    def failure(self, msg: str) -> None:
        self.head.setText("Something went wrong"); self.sub.setText(msg + "\n\nYour computer was not changed in a way that stops the "
                                                                   "installer from running again. You can close this window and try again.")
        self.restart.setVisible(False)


class InstallerWindow(QMainWindow):
    def __init__(self, live: bool = False, dry_run: bool = False, demo: bool = False,
                 hw: hardware.HardwareInfo | None = None, runner: Runner | None = None):
        super().__init__()
        self.setWindowTitle("Install marsOS"); self.resize(960, 660)
        self.live, self.dry, self.demo = live, dry_run, demo
        self.hw = hw or hardware.detect(); self.r = runner or Runner()
        self.uefi = Path("/sys/firmware/efi").exists() or demo
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        h = QHBoxLayout(root); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        self.steps = QListWidget(); self.steps.setObjectName("sidebar"); self.steps.setFixedWidth(210)
        self.steps.setFocusPolicy(Qt.FocusPolicy.NoFocus); self.steps.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        for s in STEPS:
            it = QListWidgetItem(s); it.setFlags(Qt.ItemFlag.NoItemFlags); self.steps.addItem(it)
        h.addWidget(self.steps)
        right = QVBoxLayout(); right.setContentsMargins(0, 0, 0, 0)
        self.stack = FadeStack(); right.addWidget(self.stack, 1)
        self.nav = QWidget(); nv = QHBoxLayout(self.nav); nv.setContentsMargins(40, 8, 40, 24)
        self.hint = label("", "caption"); nv.addWidget(self.hint, 1)
        self.back = button("Back"); self.next = button("Continue", "primary", pill=True)
        self.back.clicked.connect(lambda: self.go(self.stack.currentIndex() - 1)); self.next.clicked.connect(self.forward)
        nv.addWidget(self.back); nv.addWidget(self.next); right.addWidget(self.nav)
        h.addLayout(right, 1)

        disk_list = self._demo_disks() if demo else disklib.list_disks(self.r)
        self.welcome = pages.WelcomePage(self.hw, live, self.close)
        self.disk = pages.DiskPage(disk_list)
        self.account = pages.AccountPage(self.hw.is_mac, self._tz())
        self.apps = pages.AppsPage(self.hw)
        self.review = pages.ReviewPage()
        self.progress = ProgressPage(); self.done = DonePage(dry_run)
        self.done.restart.clicked.connect(self.restart)
        for p in (self.welcome, self.disk, self.account, self.apps, self.review, self.progress, self.done):
            self.stack.addWidget(p); p.changed.connect(self.refresh)
        self.proc: QProcess | None = None
        self.go(0)

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _demo_disks():
        return [disklib.Disk("/dev/sda", "APPLE HDD ST9500325AS", 500_107_862_016, rotational=True),
                disklib.Disk("/dev/sdb", "SanDisk Ultra USB", 16_000_000_000, removable=True, live_medium=True)]

    @staticmethod
    def _tz() -> str:
        try:
            return Path("/etc/timezone").read_text().strip() or "America/New_York"
        except OSError:
            return "America/New_York"

    def go(self, i: int) -> None:
        i = max(0, min(i, len(STEPS) - 1))
        self.stack.go(i)
        for n in range(self.steps.count()):
            it = self.steps.item(n); f = it.font(); f.setBold(n == i); it.setFont(f)
            it.setText(("✓ " if n < i else "   ") + STEPS[n])
        if i == 4:
            self.review.fill(self.summary())
        self.refresh()

    def refresh(self) -> None:
        i = self.stack.currentIndex(); p = self.stack.currentWidget()
        self.nav.setVisible(i < 5)
        self.back.setVisible(i > 0)
        self.next.setText("Install marsOS" if i == 4 else "Continue")
        self.next.setProperty("danger", i == 4); self.next.setProperty("primary", i != 4)
        self.next.style().unpolish(self.next); self.next.style().polish(self.next)
        self.next.setEnabled(p.valid())
        self.hint.setText(p.problem())

    def summary(self) -> list[tuple[str, str]]:
        d, a = self.disk.selected(), self.account
        names = [catalog.by_id(x).name for x in self.apps.selected()]
        return [("Install on", f"{d.label} ({d.size_gb:.0f} GB), everything on it will be erased" if d else "-"),
                ("Account", f"{a.name.text()} ({a.user.text()}) on “{a.host.text()}”"),
                ("Language and time", f"{a.locale.currentText()}, {a.keymap.currentText()} keyboard, {a.tz.currentText()}"),
                ("Automatic login", "Yes" if a.auto.isChecked() else "No"),
                ("Extra apps", ", ".join(names) or "None (Firefox is included)")]

    def forward(self) -> None:
        if self.stack.currentIndex() == 4:
            self.start_install()
        else:
            self.go(self.stack.currentIndex() + 1)

    # -------------------------------------------------------------- install
    def build_plan(self) -> Plan:
        a, d = self.account, self.disk.selected()
        apps = [{"id": c.id, "name": c.name, "source": c.source, "pkg": c.pkg}
                for c in (catalog.by_id(x) for x in self.apps.selected()) if c]
        return Plan(disk=d.path, full_name=a.name.text().strip(), username=a.user.text(), password=a.pw.text(),
                    hostname=a.host.text(), timezone=a.tz.currentText(), locale=a.locale.currentData(),
                    keymap=a.keymap.currentData(), autologin=a.auto.isChecked(), uefi=self.uefi,
                    is_mac=self.hw.is_mac, apps=apps)

    def start_install(self) -> None:
        self.go(5)
        fd, plan_path = tempfile.mkstemp(prefix="marsos-plan-", suffix=".json"); os.close(fd)
        try:
            self.build_plan().dump(plan_path)
        except Exception as e:  # noqa: BLE001
            self.finish_fail(str(e)); return
        args = ["python3", "-m", "marsos.core.installer_backend", plan_path] + (["--dry-run"] if self.dry or self.demo else [])
        prog = "python3"; argv = args[1:]
        if os.geteuid() != 0 and not (self.dry or self.demo):
            prog, argv = "sudo", ["-n"] + args
        self.proc = QProcess(self); self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read_output)
        self.proc.start(prog, argv)
        self._buf = ""; self._err = ""; self._finished = False

    def read_output(self) -> None:
        self._buf += bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        *lines, self._buf = self._buf.split("\n")
        for l in lines:
            self.handle_line(l.strip())

    def handle_line(self, l: str) -> None:
        if l.startswith("PROGRESS "):
            _, pct, *rest = l.split(" ", 2)
            self.progress.bar.setValue(int(pct)); self.progress.status.setText(rest[0] if rest else "")
        elif l == "DONE":
            self._finished = True; self.done.success(self.hw.is_mac); self.go(6)
        elif l.startswith("ERROR "):
            self._err = l[6:]; self._finished = True; self.finish_fail(self._err)
        elif l:
            self.progress.log.appendPlainText(l)

    def finish_fail(self, msg: str) -> None:
        self.done.failure(msg); self.go(6)

    def restart(self) -> None:
        if self.dry or self.demo:
            self.close(); return
        import subprocess
        subprocess.Popen(["systemctl", "reboot"])

    def closeEvent(self, e) -> None:
        if self.stack.currentIndex() == 5 and self.proc and self.proc.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "Installing", "marsOS is still installing. Please wait until it finishes.")
            e.ignore(); return
        super().closeEvent(e)
