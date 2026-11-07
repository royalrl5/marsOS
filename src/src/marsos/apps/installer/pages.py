from __future__ import annotations
import re
import zoneinfo
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QCheckBox, QComboBox, QFormLayout, QLineEdit, QListWidget, QListWidgetItem,
                               QScrollArea, QVBoxLayout, QWidget)

from marsos.core import catalog, hardware
from marsos.core.disks import Disk
from marsos.core.installer_backend import HOST_RE, RESERVED_USERS, USER_RE
from marsos.ui.widgets import Card, button, icon_label, label

LOCALES = [("English (United States)", "en_US.UTF-8"), ("English (United Kingdom)", "en_GB.UTF-8"),
           ("Deutsch", "de_DE.UTF-8"), ("Français", "fr_FR.UTF-8"), ("Español", "es_ES.UTF-8"),
           ("Italiano", "it_IT.UTF-8"), ("Português", "pt_PT.UTF-8"), ("Nederlands", "nl_NL.UTF-8")]
KEYMAPS = [("English (US)", "us"), ("English (UK)", "gb"), ("German", "de"), ("French", "fr"),
           ("Spanish", "es"), ("Italian", "it"), ("Portuguese", "pt"), ("Dutch", "nl")]


class Page(QWidget):
    changed = Signal()
    title = ""
    subtitle = ""

    def __init__(self):
        super().__init__()
        self.v = QVBoxLayout(self); self.v.setContentsMargins(40, 32, 40, 16); self.v.setSpacing(14)
        if self.title:
            self.v.addWidget(label(self.title, "title"))
        if self.subtitle:
            self.v.addWidget(label(self.subtitle, "subtitle"))

    def valid(self) -> bool:
        return True

    def problem(self) -> str:
        return ""


class WelcomePage(Page):
    title = "Welcome to marsOS"
    subtitle = "Let's get your computer set up. It only takes a few minutes."

    def __init__(self, hw: hardware.HardwareInfo, live: bool, on_try=None):
        super().__init__()
        card = Card()
        card.lay.addWidget(label("Your computer", "caption"))
        card.lay.addWidget(label(hw.friendly, "heading"))
        bits = [f"{hw.ram_gb:g} GB memory"] + ([hw.cpu] if hw.cpu else [])
        card.lay.addWidget(label(" · ".join(bits), "caption"))
        if hw.is_mac and hw.mac_year:
            card.lay.addWidget(label("✓ marsOS has special support for your Mac: Wi-Fi, keyboard, trackpad and fan control "
                                     "are set up for you automatically.", "ok"))
        profile = hardware.recommended_effects(hw)
        card.lay.addWidget(label({"full": "Visual effects: full", "balanced": "Visual effects will be tuned so everything feels smooth on this computer.",
                                  "light": "Visual effects will be kept light so everything feels smooth on this computer."}[profile], "caption"))
        self.v.addWidget(card)
        self.v.addWidget(label("Installing marsOS will replace everything on the disk you choose. "
                               "Make sure anything precious is backed up first.", "caption"))
        if live and on_try:
            b = button("Try marsOS first (nothing is changed)", "flat"); b.clicked.connect(on_try)
            self.v.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        self.v.addStretch(1)


class DiskPage(Page):
    title = "Where should marsOS go?"
    subtitle = "Choose the disk to install on."

    def __init__(self, disks: list[Disk]):
        super().__init__()
        self.disks = disks
        self.list = QListWidget(); self.list.setObjectName("plain"); self.list.setMinimumHeight(180)
        for d in disks:
            prob = d.problem()
            it = QListWidgetItem(); it.setData(Qt.ItemDataRole.UserRole, d); it.setSizeHint(QSize(0, 76))
            if prob:
                it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(it); self.list.setItemWidget(it, self._row(d, prob))
        if not disks:
            self.v.addWidget(label("No disks were found. If you are using a virtual machine, add a virtual hard disk first.", "warn"))
        self.list.itemSelectionChanged.connect(self.changed); self.v.addWidget(self.list, 1)
        self.warn = Card(warn=True)
        self.warn.lay.addWidget(label("Everything on this disk will be permanently erased.", "warn"))
        self.confirm = QCheckBox("I understand and want to erase this disk"); self.confirm.toggled.connect(lambda *_: self.changed.emit())
        self.warn.lay.addWidget(self.confirm); self.v.addWidget(self.warn)
        ok = [i for i in range(self.list.count()) if self.list.item(i).flags() != Qt.ItemFlag.NoItemFlags]
        if len(ok) == 1:
            self.list.setCurrentRow(ok[0])

    @staticmethod
    def _row(d: Disk, prob: str | None) -> QWidget:
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(12, 8, 12, 8); h.setSpacing(14)
        h.addWidget(icon_label("drive-removable-media-usb" if d.removable else "drive-harddisk", d.label, 46))
        col = QVBoxLayout(); col.setSpacing(1)
        col.addWidget(label(d.label, "heading", wrap=False))
        col.addWidget(label(f"{d.size_gb:.0f} GB · {d.path}", "caption", wrap=False))
        if prob:
            col.addWidget(label("⚠ " + prob, "warn", wrap=False))
        h.addLayout(col, 1); w.setEnabled(not prob); w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        return w

    def selected(self) -> Disk | None:
        it = self.list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def valid(self) -> bool:
        d = self.selected()
        return bool(d and not d.problem() and self.confirm.isChecked())

    def problem(self) -> str:
        return "Choose a disk and tick the box to continue." if not self.valid() else ""


class AccountPage(Page):
    title = "Create your account"
    subtitle = "This is the name and password you'll use every day."

    def __init__(self, is_mac: bool, default_tz: str = "UTC"):
        super().__init__()
        self.is_mac = is_mac; self._user_touched = self._host_touched = False
        f = QFormLayout(); f.setSpacing(10); f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.name = QLineEdit(); self.user = QLineEdit(); self.host = QLineEdit()
        self.pw = QLineEdit(); self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw2 = QLineEdit(); self.pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self.name.setPlaceholderText("For example: Rose Smith")
        for w, t in ((self.name, "Your name"), (self.user, "Account name"), (self.host, "Computer name"),
                     (self.pw, "Password"), (self.pw2, "Password again")):
            f.addRow(t, w); w.textChanged.connect(self.changed)
        self.name.textEdited.connect(self._derive)
        self.user.textEdited.connect(lambda *_: setattr(self, "_user_touched", True))
        self.host.textEdited.connect(lambda *_: setattr(self, "_host_touched", True))
        self.locale = QComboBox(); [self.locale.addItem(n, c) for n, c in LOCALES]
        self.keymap = QComboBox(); [self.keymap.addItem(n, c) for n, c in KEYMAPS]
        self.tz = QComboBox(); self.tz.setEditable(False)
        zones = sorted(z for z in zoneinfo.available_timezones() if "/" in z and not z.startswith(("Etc", "posix", "right")))
        self.tz.addItems(zones or ["UTC"])
        i = self.tz.findText(default_tz); self.tz.setCurrentIndex(max(i, 0))
        f.addRow("Language", self.locale); f.addRow("Keyboard", self.keymap); f.addRow("Time zone", self.tz)
        self.v.addLayout(f)
        self.auto = QCheckBox("Log in automatically (recommended for a computer used at home)"); self.auto.setChecked(True)
        self.v.addWidget(self.auto)
        self.msg = label("", "warn"); self.v.addWidget(self.msg); self.v.addStretch(1)

    def _derive(self, text: str) -> None:
        first = re.sub(r"[^a-z0-9]", "", (text.split() or [""])[0].lower())
        if not self._user_touched:
            self.user.setText(first)
        if not self._host_touched and first:
            self.host.setText(f"{first}s-{'macbook' if self.is_mac else 'computer'}")

    def problem(self) -> str:
        if not self.name.text().strip():
            return "Please type your name."
        if any(c in self.name.text() for c in ":,"):
            return "Your name can't contain commas or colons."
        u = self.user.text()
        if not USER_RE.match(u) or u in RESERVED_USERS:
            return "The account name must be lowercase letters and numbers only (no spaces), and can't be “root” or “live”."
        if not HOST_RE.match(self.host.text()):
            return "The computer name can only use letters, numbers and dashes."
        if len(self.pw.text()) < 4:
            return "Please choose a password with at least 4 characters."
        if self.pw.text() != self.pw2.text():
            return "The two passwords don't match."
        return ""

    def valid(self) -> bool:
        return not self.problem()


class AppsPage(Page):
    title = "Choose some apps"
    subtitle = "Optional. You can always add more later from the App Store."

    def __init__(self, hw: hardware.HardwareInfo):
        super().__init__()
        self.boxes: dict[str, QCheckBox] = {}
        sc = QScrollArea(); sc.setWidgetResizable(True)
        inner = QWidget(); iv = QVBoxLayout(inner); iv.setSpacing(10); iv.setContentsMargins(0, 0, 8, 0)
        weak = hw.ram_mb and hw.ram_mb < 6000
        groups = [("Web browsers", [a for a in catalog.installer_options() if a.category == "Internet"]),
                  ("Advanced", [a for a in catalog.installer_options() if a.category != "Internet"])]
        for title, apps in groups:
            if not apps:
                continue
            iv.addWidget(label(title, "heading"))
            for a in apps:
                c = Card(); cb = QCheckBox(a.name); cb.setChecked(a.default); self.boxes[a.id] = cb
                c.lay.addWidget(cb); c.lay.addWidget(label(a.description, "caption"))
                if weak and a.category == "Virtual machines":
                    c.lay.addWidget(label("Not recommended: this computer has limited memory.", "warn"))
                iv.addWidget(c)
        iv.addStretch(1); sc.setWidget(inner); self.v.addWidget(sc, 1)
        self.v.addWidget(label("Firefox is already included. Chosen apps are downloaded the first time your computer starts, "
                               "so you'll need an internet connection then.", "caption"))

    def selected(self) -> list[str]:
        return [k for k, b in self.boxes.items() if b.isChecked()]


class ReviewPage(Page):
    title = "Ready to install"
    subtitle = "Please check everything looks right."

    def __init__(self):
        super().__init__()
        self.card = Card(); self.v.addWidget(self.card); self.v.addStretch(1)

    def fill(self, rows: list[tuple[str, str]]) -> None:
        while self.card.lay.count():
            w = self.card.lay.takeAt(0).widget()
            if w: w.deleteLater()
        for k, val in rows:
            self.card.lay.addWidget(label(k, "caption")); self.card.lay.addWidget(label(val))


TIPS = ["Press ⌘ Space (or Ctrl Space) any time to search for anything, like Spotlight on a Mac.",
        "The App Store has hundreds of free apps, each with a plain-English explanation.",
        "Drag the corner of any window to resize it. Click the yellow button to tuck it into the Dock.",
        "Need help? Ask a family member to install “Family Help” so they can fix things from their own computer.",
        "To print, just connect your printer. marsOS will usually find it by itself."]
