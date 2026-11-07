"""Render every app headless to PNGs (for docs and visual checks).  usage: python scripts/screenshots.py OUTDIR [dark]"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["MARSOS_DRY_RUN"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from pathlib import Path
from PySide6.QtCore import QTimer, QCoreApplication
from PySide6.QtTest import QTest
from marsos.core import backends, network, hardware, search
from marsos.core.runner import Runner
from marsos.core.prefs import Prefs

out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/shots"); out.mkdir(parents=True, exist_ok=True)
if "dark" in sys.argv:
    Prefs(appearance="dark").save()
backends.is_installed = lambda r, a: a.id in ("firefox",)
network.list_wifi = lambda r, rescan=False: [network.WifiNetwork("Rose's Home Wi-Fi", 82, "WPA2", True), network.WifiNetwork("NETGEAR-5G", 55, "WPA2"),
                                             network.WifiNetwork("Coffee Shop Guest", 30, "--")]
network.wifi_enabled = lambda r: True; network.bluetooth_enabled = lambda r: False
network.get_volume = lambda r: 60; network.get_brightness = lambda r: 70
HW = hardware.HardwareInfo("Apple Inc.", "MacBookPro8,1", 3950, "Intel(R) Core(TM) i5-2415M CPU @ 2.30GHz", ["Intel"])

from marsos.ui.app import make_app
app = make_app("shots")
from marsos.apps.store.window import StoreWindow
from marsos.apps.installer.window import InstallerWindow
from marsos.apps.bundle.window import BundleWindow
from marsos.apps.settings.window import SettingsWindow
from marsos.apps.welcome.window import WelcomeWindow
from marsos.apps.updater.window import UpdaterWindow
from marsos.apps.controlcenter.window import ControlCenter
from marsos.apps.spotlight.window import SpotlightWindow
from marsos.apps.launchpad.window import LaunchpadWindow
from marsos.core.desktop_entries import DesktopEntry
from marsos.core import updates


def snap(w, name, wait=250):
    w.show(); QTest.qWait(wait); w.grab().save(str(out / f"{name}.png")); print("saved", name)

s = StoreWindow(); s.prefs.show_advanced_apps = False; snap(s, "store")
i = InstallerWindow(demo=True, hw=HW); snap(i, "installer-1-welcome")
i.go(1); i.disk.list.setCurrentRow(0); i.disk.confirm.setChecked(True); snap(i, "installer-2-disk")
i.go(2); i.account.name.setText("Rose Smith"); i.account.name.textEdited.emit("Rose Smith"); i.account.pw.setText("secret1"); i.account.pw2.setText("secret1"); snap(i, "installer-3-account")
i.go(3); snap(i, "installer-4-apps")
i.go(4); snap(i, "installer-5-review")
i.go(5); i.progress.bar.setValue(48); i.progress.status.setText("Copying marsOS (this takes a few minutes)"); snap(i, "installer-6-progress")
b = BundleWindow(); snap(b, "bundle-1-drop")
p = Path("/tmp/VMware-Workstation-Full-17.5.bundle"); p.write_bytes(b"#!/bin/sh\n# VMware Workstation installer\n" + b"x" * 5000)
b.load(str(p)); snap(b, "bundle-2-details")
st = SettingsWindow("appearance", hw=HW); snap(st, "settings-appearance")
st.side.setCurrentRow(0); snap(st, "settings-wifi", 400)
st.side.setCurrentRow(8); snap(st, "settings-about")
w = WelcomeWindow(hw=HW); w.go(2); snap(w, "welcome-look")
u = UpdaterWindow(autocheck=False); u.show_info(updates.UpdateInfo(["linux-zen 6.1-1 -> 6.2-1", "vlc 3.0 -> 3.1"], ["org.mozilla.firefox"])); snap(u, "updater")
c = ControlCenter(popup=False); snap(c, "control-center", 400)
ents = [DesktopEntry("a.desktop", n, "/x", generic=g, comment=g) for n, g in (("Firefox", "Web Browser"), ("Files", "File Manager"), ("Fire Safety Notes", "Notes"))]
sp = SpotlightWindow(search.SearchEngine(ents)); sp.popup(); sp.input.setText("fire"); sp.refresh(); snap(sp, "spotlight-apps")
sp.input.setText("15% of 80"); sp.refresh(); snap(sp, "spotlight-calc")
lp = LaunchpadWindow([DesktopEntry(f"{n}.desktop", n, "/x") for n in ("Firefox", "Files", "App Store", "Settings", "Terminal", "Text Editor", "Photos", "Music", "Calendar", "Mail", "Maps", "Notes")])
lp.resize(1100, 700); snap(lp, "launchpad")
QCoreApplication.processEvents()
os._exit(0)
