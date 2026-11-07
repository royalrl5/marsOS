from __future__ import annotations
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QProgressBar, QScrollArea, QVBoxLayout, QWidget)

from marsos.core import backends, catalog
from marsos.core.catalog import App
from marsos.core.prefs import Prefs
from marsos.core.runner import Runner
from marsos.ui import anim
from marsos.ui.widgets import Card, Toggle, button, icon_label, label
from marsos.ui.workers import run_async, run_commands

DISCOVER = "Discover"
RESULTS = "Search results"


class AppCard(Card):
    def __init__(self, app: App, store: "StoreWindow"):
        super().__init__()
        self.app, self.store = app, store
        row = QHBoxLayout(); row.setSpacing(16)
        row.addWidget(icon_label(app.icon, app.name, 56), 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout(); col.setSpacing(3)
        title = QHBoxLayout()
        title.addWidget(label(app.name, "heading", wrap=False))
        tag = label(app.source_label.upper(), "caption", wrap=False); title.addWidget(tag); title.addStretch(1)
        col.addLayout(title)
        col.addWidget(label(app.summary, "subtitle" if False else "caption"))
        self.desc = label(app.description)            # the explanation under every application
        col.addWidget(self.desc)
        self.bar = QProgressBar(); self.bar.setRange(0, 0); self.bar.hide(); col.addWidget(self.bar)
        self.msg = label("", "caption"); self.msg.hide(); col.addWidget(self.msg)
        row.addLayout(col, 1)
        self.btn = button("Get", "primary", pill=True); self.btn.clicked.connect(lambda: store.ask_install(app, self))
        row.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignTop)
        self.lay.addLayout(row)
        self.installed = False

    def set_installed(self, yes: bool) -> None:
        self.installed = yes
        self.btn.setProperty("primary", not yes)
        self.btn.setText("Open" if yes and self.store.can_open(self.app) else ("Installed" if yes else "Get"))
        self.btn.setEnabled(not yes or self.store.can_open(self.app))
        self.btn.style().unpolish(self.btn); self.btn.style().polish(self.btn)
        try: self.btn.clicked.disconnect()
        except RuntimeError: pass
        if yes:
            self.btn.clicked.connect(lambda: self.store.open_app(self.app))
        else:
            self.btn.clicked.connect(lambda: self.store.ask_install(self.app, self))

    def busy(self, text: str) -> None:
        self.btn.setEnabled(False); self.bar.show(); self.msg.setText(text); self.msg.show()

    def done(self, ok: bool, text: str) -> None:
        self.bar.hide(); self.msg.setText(text); self.msg.show()
        self.msg.setProperty("role", "ok" if ok else "warn")
        self.msg.style().unpolish(self.msg); self.msg.style().polish(self.msg)
        self.btn.setEnabled(True)
        self.set_installed(ok)


class StoreWindow(QMainWindow):
    def __init__(self, runner: Runner | None = None, focus_app: str | None = None):
        super().__init__()
        self.setWindowTitle("App Store"); self.resize(980, 700)
        self.r = runner or Runner(); self.prefs = Prefs.load(); self.cards: list[AppCard] = []
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        h = QHBoxLayout(root); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        side = QVBoxLayout(); side.setContentsMargins(0, 0, 0, 0)
        self.side = QListWidget(); self.side.setObjectName("sidebar"); self.side.setFixedWidth(210)
        self.side.currentTextChanged.connect(self.show_category)
        side.addWidget(self.side, 1)
        adv = QWidget(); adv.setStyleSheet("background: transparent;"); ah = QHBoxLayout(adv); ah.setContentsMargins(16, 8, 14, 14)
        ah.addWidget(label("Show advanced apps", "caption"), 1)
        self.adv = Toggle(self.prefs.show_advanced_apps); self.adv.toggled.connect(self.set_advanced); ah.addWidget(self.adv)
        side.addWidget(adv)
        sidew = QWidget(); sidew.setLayout(side); sidew.setFixedWidth(210); sidew.setStyleSheet("background: palette(window);")
        h.addWidget(sidew)
        main = QVBoxLayout(); main.setContentsMargins(26, 20, 26, 8); main.setSpacing(12)
        top = QHBoxLayout()
        self.title = label(DISCOVER, "title", wrap=False); top.addWidget(self.title, 1)
        self.search = QLineEdit(); self.search.setProperty("search", True)
        self.search.setPlaceholderText("Search apps…"); self.search.setFixedWidth(280)
        self.search.returnPressed.connect(self.do_search); top.addWidget(self.search)
        main.addLayout(top)
        self.note = label("", "caption"); main.addWidget(self.note)
        sc = QScrollArea(); sc.setWidgetResizable(True)
        self.body = QWidget(); self.vbox = QVBoxLayout(self.body); self.vbox.setSpacing(12); self.vbox.setContentsMargins(0, 0, 8, 12)
        self.vbox.addStretch(1); sc.setWidget(self.body); main.addWidget(sc, 1)
        h.addLayout(main, 1)
        self.reload_sidebar()
        if focus_app and catalog.by_id(focus_app):
            self.search.setText(catalog.by_id(focus_app).name); self.do_search()

    # ------------------------------------------------------------ lists
    def reload_sidebar(self) -> None:
        self.side.blockSignals(True); self.side.clear()
        for name in [DISCOVER] + catalog.categories(self.prefs.show_advanced_apps):
            if name != DISCOVER:
                self.side.addItem(QListWidgetItem(name))
            else:
                self.side.insertItem(0, QListWidgetItem(DISCOVER))
        self.side.blockSignals(False)
        self.side.setCurrentRow(0); self.show_category(DISCOVER)

    def show_category(self, name: str) -> None:
        if not name:
            return
        adv = self.prefs.show_advanced_apps
        apps = [a for a in catalog.load() if adv or not a.advanced] if name == DISCOVER else \
               [a for a in catalog.load() if a.category == name and (adv or not a.advanced)]
        self.title.setText(name); self.note.setText("" if name != DISCOVER else "Everything here comes with a plain-English explanation.")
        self.set_apps(apps)

    def set_apps(self, apps: list[App]) -> None:
        for c in self.cards:
            c.setParent(None); c.deleteLater()
        self.cards = []
        if not apps:
            self.note.setText("Nothing found. Try a different word.")
        for a in apps:
            c = AppCard(a, self); self.cards.append(c)
            self.vbox.insertWidget(self.vbox.count() - 1, c)
            run_async(lambda a=a: backends.is_installed(self.r, a), lambda ok, c=c: c.set_installed(bool(ok)))
        if self.cards:
            anim.fade_in(self.body, 200)

    def set_advanced(self, on: bool) -> None:
        self.prefs.show_advanced_apps = on; self.prefs.save(); self.reload_sidebar()

    def do_search(self) -> None:
        q = self.search.text().strip()
        if not q:
            return self.show_category(DISCOVER)
        self.title.setText(RESULTS); self.note.setText("Searching…")
        local = catalog.search(q, self.prefs.show_advanced_apps)

        def work():
            res = list(local)
            have = {a.pkg for a in res}
            res += [a for a in backends.search_flathub(q) if a.pkg not in have]
            if self.prefs.show_advanced_apps:
                res += backends.search_aur(q)
            return res
        run_async(work, lambda apps: (self.note.setText(f"{len(apps)} result(s) for “{q}”"), self.set_apps(apps)))

    # ------------------------------------------------------------ install
    def can_open(self, app: App) -> bool:
        return app.source == "flatpak" or bool(app.desktop_id)

    def open_app(self, app: App) -> None:
        cmd = ["flatpak", "run", app.pkg] if app.source == "flatpak" else ["gtk-launch", app.desktop_id]
        subprocess.Popen(cmd, start_new_session=True)

    def confirm_text(self, app: App) -> str:
        t = f"{app.description}\n\n"
        if app.source == "aur":
            t += ("This is a community app. It is built on your computer by volunteers' instructions, can take several "
                  "minutes and is not checked by marsOS. You may be asked for your password.")
        elif app.source == "pacman":
            t += "This is a system component. You will be asked for your password."
        else:
            t += "It will be downloaded from the App Store. No password needed."
        return t

    def ask_install(self, app: App, card: AppCard) -> None:
        box = QMessageBox(self); box.setWindowTitle("Get " + app.name); box.setText(f"Get “{app.name}”?")
        box.setInformativeText(self.confirm_text(app))
        go = box.addButton("Get", QMessageBox.ButtonRole.AcceptRole); box.addButton("Not now", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is go:
            self.begin_install(app, card)

    def begin_install(self, app: App, card: AppCard) -> None:
        card.busy("Getting ready…")
        lines: list[str] = []

        def on_line(l: str) -> None:
            lines.append(l)
            card.msg.setText("Installing…  " + l.strip()[:70])

        def finished(rc: int) -> None:
            ok = rc == 0
            card.done(ok, f"{app.name} is ready." if ok else "That didn't work. Please check your internet connection and try again.")
        run_commands(backends.install_commands(app), on_line, finished, self.r)
