from __future__ import annotations
import subprocess
import zoneinfo

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QInputDialog, QLineEdit, QSlider, QVBoxLayout, QWidget, QMessageBox

from marsos import PRETTY
from marsos import paths
from marsos.core import hardware, network, system
from marsos.core.prefs import Prefs
from marsos.core.runner import Runner
from marsos.ui.segmented import Segmented, Swatches
from marsos.ui.widgets import Card, SettingRow, Toggle, button, label, separator
from marsos.ui.wifi import WifiPanel
from marsos.ui.workers import run_async


class Pane(QWidget):
    title = ""

    def __init__(self, r: Runner, prefs: Prefs, hw: hardware.HardwareInfo):
        super().__init__()
        self.r, self.prefs, self.hw = r, prefs, hw
        self.v = QVBoxLayout(self); self.v.setContentsMargins(34, 26, 34, 20); self.v.setSpacing(14)
        self.v.addWidget(label(self.title, "title"))

    def card(self, *rows: QWidget) -> Card:
        c = Card()
        for i, w in enumerate(rows):
            if i: c.lay.addWidget(separator())
            c.lay.addWidget(w)
        self.v.addWidget(c)
        return c

    def save(self) -> None:
        self.prefs.save()

    def finish(self) -> None:
        self.v.addStretch(1)


class WifiPane(Pane):
    title = "Wi-Fi"

    def __init__(self, *a):
        super().__init__(*a)
        c = Card(); c.lay.addWidget(WifiPanel(self.r)); self.v.addWidget(c)
        bt = Toggle(False); bt.toggled.connect(lambda on: run_async(lambda: network.set_bluetooth(self.r, on)))
        run_async(lambda: network.bluetooth_enabled(self.r), lambda on: bt.setChecked(bool(on)))
        self.card(SettingRow("Bluetooth", "For wireless headphones, speakers, keyboards and mice.", bt))
        self.finish()


class AppearancePane(Pane):
    title = "Appearance"

    def __init__(self, *a):
        super().__init__(*a)
        seg = Segmented([("Automatic", "auto"), ("Light", "light"), ("Dark", "dark")], self.prefs.appearance)
        seg.changed.connect(self.set_mode)
        sw = Swatches(list(system.ACCENTS), self.prefs.accent); sw.changed.connect(self.set_accent)
        eff = QComboBox()
        for t, v in (("Automatic (best for this computer)", "auto"), ("Full", "full"), ("Balanced", "balanced"), ("Light (fastest)", "light")):
            eff.addItem(t, v)
        eff.setCurrentIndex(max(0, eff.findData(self.prefs.effects))); eff.currentIndexChanged.connect(lambda _: self.set_effects(eff.currentData()))
        rm = Toggle(self.prefs.reduce_motion); rm.toggled.connect(self.set_motion)
        self.card(SettingRow("Appearance", "Choose a light or dark look.", seg),
                  SettingRow("Highlight colour", "Used for buttons and selections.", sw))
        self.card(SettingRow("Visual effects", f"Animations and transparency. “Automatic” picks “{self.prefs.resolved_effects(self.hw)}” for this computer.", eff),
                  SettingRow("Reduce motion", "Turns off most animations.", rm))
        self.finish()

    def set_mode(self, v) -> None:
        self.prefs.appearance = v; self.save()
        dark = v == "dark"
        run_async(lambda: system.apply_appearance(self.r, dark, self.prefs.accent) if v != "auto" else None)

    def set_accent(self, v) -> None:
        self.prefs.accent = v; self.save()
        run_async(lambda: system.kw(self.r, "kdeglobals", "General", "AccentColor", system.ACCENTS[v]))

    def set_effects(self, v) -> None:
        self.prefs.effects = v; self.save()
        run_async(lambda: system.apply_effects(self.r, self.prefs.resolved_effects(self.hw), self.prefs.reduce_motion))

    def set_motion(self, on) -> None:
        self.prefs.reduce_motion = on; self.save()
        run_async(lambda: system.apply_effects(self.r, self.prefs.resolved_effects(self.hw), on))


class DisplayPane(Pane):
    title = "Display & Text Size"

    def __init__(self, *a):
        super().__init__(*a)
        cur = min(system.SCALES.values(), key=lambda s: abs(s - self.prefs.text_scale))
        seg = Segmented([(k, v) for k, v in system.SCALES.items()], cur); seg.changed.connect(self.set_scale)
        sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(5, 100); sl.setValue(70); sl.setMinimumWidth(220)
        run_async(lambda: network.get_brightness(self.r), lambda v: sl.setValue(v) if v else None)
        sl.sliderReleased.connect(lambda: network.set_brightness(self.r, sl.value()))
        self.card(SettingRow("Text size", "Make everything easier to read. Takes full effect after you log out and back in.", seg),
                  SettingRow("Brightness", "", sl))
        self.note = label("", "ok"); self.v.addWidget(self.note); self.finish()

    def set_scale(self, v) -> None:
        self.prefs.text_scale = v; self.save()
        run_async(lambda: system.apply_text_scale(self.r, v), lambda _: self.note.setText("Saved. Log out and back in to see the change everywhere."))


class SoundPane(Pane):
    title = "Sound"

    def __init__(self, *a):
        super().__init__(*a)
        sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0, 100); sl.setMinimumWidth(260)
        run_async(lambda: network.get_volume(self.r), lambda v: sl.setValue(v or 50))
        sl.valueChanged.connect(lambda v: network.set_volume(self.r, v))
        self.card(SettingRow("Volume", "Use the speaker keys on your keyboard for quick changes.", sl)); self.finish()


class KeyboardPane(Pane):
    title = "Keyboard & Trackpad"

    def __init__(self, *a):
        super().__init__(*a)
        cmd = Toggle(self.prefs.command_as_ctrl); cmd.toggled.connect(self.set_command)
        nat = Toggle(self.prefs.natural_scroll); nat.toggled.connect(lambda on: self.set_input("natural_scroll", on))
        tap = Toggle(self.prefs.tap_to_click); tap.toggled.connect(lambda on: self.set_input("tap_to_click", on))
        self.card(SettingRow("Use the ⌘ Command key for shortcuts", "⌘C copies, ⌘V pastes, ⌘Q quits, ⌘Space searches, just like on a Mac.", cmd))
        self.card(SettingRow("Natural scrolling", "Content follows your fingers, like on a Mac.", nat),
                  SettingRow("Tap to click", "Tap the trackpad instead of pressing it down.", tap))
        self.msg = label("", "caption"); self.v.addWidget(self.msg); self.finish()

    def set_command(self, on) -> None:
        self.prefs.command_as_ctrl = on; self.save()
        run_async(lambda: self.r.run([paths.helper_path(), "keyd-set", "on" if on else "off"]) if False else
                  self.r.run(["pkexec", paths.helper_path(), "keyd-set", "on" if on else "off"]),
                  lambda res: self.msg.setText("Saved." if res.ok else "That change needs your password. Please try again."))

    def set_input(self, key: str, on) -> None:
        setattr(self.prefs, key, on); self.save()
        subprocess.Popen(["marsos-session-init", "--input"], start_new_session=True)


class DateTimePane(Pane):
    title = "Date & Time"

    def __init__(self, *a):
        super().__init__(*a)
        self.tz = QComboBox()
        zones = sorted(z for z in zoneinfo.available_timezones() if "/" in z and not z.startswith(("Etc", "posix", "right")))
        self.tz.addItems(zones or ["UTC"])
        run_async(lambda: self.r.run(["timedatectl", "show", "-p", "Timezone", "--value"]).stdout.strip(),
                  lambda z: self.tz.setCurrentIndex(max(0, self.tz.findText(z))))
        ap = button("Apply", "primary"); ap.clicked.connect(self.apply)
        row = QWidget(); h = QHBoxLayout(row); h.setContentsMargins(0, 0, 0, 0); h.addWidget(self.tz, 1); h.addWidget(ap)
        self.card(SettingRow("Time zone", "Your clock sets itself automatically from the internet.", row))
        self.msg = label("", "caption"); self.v.addWidget(self.msg); self.finish()

    def apply(self) -> None:
        z = self.tz.currentText()
        run_async(lambda: self.r.run(["pkexec", paths.helper_path(), "set-timezone", z]),
                  lambda res: self.msg.setText("Time zone changed." if res.ok else "That change needs your password."))


class UsersPane(Pane):
    title = "Users & Password"

    def __init__(self, *a):
        super().__init__(*a)
        b = button("Change Password…"); b.clicked.connect(self.change)
        self.card(SettingRow("Password", "The password you use to log in and to approve changes.", b)); self.finish()

    def change(self) -> None:
        pw, ok = QInputDialog.getText(self, "New password", "Type your new password:", QLineEdit.EchoMode.Password)
        if not ok or len(pw) < 4:
            if ok: QMessageBox.information(self, "Too short", "Please use at least 4 characters.")
            return
        pw2, ok = QInputDialog.getText(self, "New password", "Type it again to confirm:", QLineEdit.EchoMode.Password)
        if not ok or pw != pw2:
            if ok: QMessageBox.warning(self, "Different", "The two passwords were different. Nothing was changed.")
            return
        res = self.r.run(["pkexec", paths.helper_path(), "set-password"], input=pw + "\n")
        QMessageBox.information(self, "Password", "Your password has been changed." if res.ok else "The password was not changed.")


class UpdatesPane(Pane):
    title = "Software Update"

    def __init__(self, *a):
        super().__init__(*a)
        b = button("Check for Updates…", "primary"); b.clicked.connect(lambda: subprocess.Popen(["marsos-updater"], start_new_session=True))
        self.card(SettingRow("Keep marsOS up to date", "Updates add new features and keep your computer safe.", b)); self.finish()


class AboutPane(Pane):
    title = "About This Mac"

    def __init__(self, *a):
        super().__init__(*a)
        c = Card()
        c.lay.addWidget(label(PRETTY, "hero" if False else "title"))
        for k, val in (("Computer", self.hw.friendly), ("Processor", self.hw.cpu or "-"), ("Memory", f"{self.hw.ram_gb:g} GB"),
                       ("Graphics", ", ".join(self.hw.gpus) or "-"),
                       ("Visual effects", self.prefs.resolved_effects(self.hw).title())):
            c.lay.addWidget(label(k, "caption")); c.lay.addWidget(label(val))
        self.v.addWidget(c); self.finish()


PANES = {"wifi": WifiPane, "bluetooth": WifiPane, "appearance": AppearancePane, "display": DisplayPane,
         "sound": SoundPane, "keyboard": KeyboardPane, "datetime": DateTimePane, "users": UsersPane,
         "updates": UpdatesPane, "about": AboutPane}
ORDER = [("wifi", "Wi-Fi & Bluetooth"), ("appearance", "Appearance"), ("display", "Display & Text Size"), ("sound", "Sound"),
         ("keyboard", "Keyboard & Trackpad"), ("datetime", "Date & Time"), ("users", "Users & Password"),
         ("updates", "Software Update"), ("about", "About This Mac")]
