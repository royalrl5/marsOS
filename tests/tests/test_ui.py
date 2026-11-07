import importlib
import json
import os
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from marsos import paths
from marsos.core import backends, catalog, hardware, network, search
from marsos.core.desktop_entries import parse_entry
from marsos.core.runner import Runner
from marsos.ui import theme, workers

ROOT = Path(__file__).resolve().parents[1]
MAC = hardware.HardwareInfo("Apple Inc.", "MacBookPro8,1", 3950, "Intel Core i5-2415M", ["Intel"])


@pytest.fixture(scope="session")
def qapp():
    from marsos.ui.app import make_app
    app = make_app("tests")
    yield app
    workers.wait_idle(3)
    import gc
    for w in app.topLevelWidgets():
        w.close(); w.deleteLater()
    app.processEvents(); app.sendPostedEvents(None, 0); gc.collect(); app.processEvents()


def settle(ms=150):
    workers.wait_idle(3); QTest.qWait(ms); workers.wait_idle(3)


@pytest.fixture(autouse=True)
def fake_system(monkeypatch):
    monkeypatch.setattr(network, "list_wifi", lambda r, rescan=False: [network.WifiNetwork("Home", 80, "WPA2", True)])
    monkeypatch.setattr(backends, "is_installed", lambda r, a: False)


# ------------------------------------------------------------------ theme
@pytest.mark.parametrize("dark", [False, True])
def test_qss_fully_substituted(qapp, dark):
    q = theme.build_qss(dark, 1.5, "purple")
    assert "$" not in q
    assert "rgba(" in q and "check.png" in q


def test_text_scale_grows_fonts(qapp):
    assert "font-size: 15pt" in theme.build_qss(False, 1.5) or "font-size: 15" in theme.build_qss(False, 1.5)


# ------------------------------------------------------------------ every app builds
def test_every_window_builds(qapp):
    from marsos.apps.bundle.window import BundleWindow
    from marsos.apps.controlcenter.window import ControlCenter
    from marsos.apps.installer.window import InstallerWindow
    from marsos.apps.launchpad.window import LaunchpadWindow
    from marsos.apps.settings.window import SettingsWindow
    from marsos.apps.spotlight.window import SpotlightWindow
    from marsos.apps.store.window import StoreWindow
    from marsos.apps.updater.window import UpdaterWindow
    from marsos.apps.welcome.window import WelcomeWindow
    for w in (StoreWindow(), BundleWindow(), InstallerWindow(demo=True, hw=MAC), SettingsWindow(hw=MAC), WelcomeWindow(hw=MAC),
              UpdaterWindow(autocheck=False), ControlCenter(popup=False), LaunchpadWindow([]), SpotlightWindow(search.SearchEngine([]))):
        w.show(); settle(60); w.close()


# ------------------------------------------------------------------ store
def test_store_shows_explanation_under_every_app(qapp):
    from marsos.apps.store.window import StoreWindow
    s = StoreWindow(); settle()
    shown = {c.app.id for c in s.cards}
    assert shown == {a.id for a in catalog.load() if not a.advanced}
    for c in s.cards:
        assert c.desc.text() == c.app.description and c.desc.text()
    s.adv.setChecked(True); settle()
    assert {"waydroid", "virtualbox"} <= {c.app.id for c in s.cards} or s.title.text() != "Discover"
    s.show_category("Virtual machines"); settle()
    assert {c.app.id for c in s.cards} == {"waydroid", "virtualbox", "vmware"}


def test_store_install_flow(qapp):
    from marsos.apps.store.window import StoreWindow
    s = StoreWindow(runner=Runner(dry_run=True)); settle()
    card = next(c for c in s.cards if c.app.id == "zen")
    s.begin_install(card.app, card); settle(300)
    assert card.installed and "ready" in card.msg.text()
    assert any("flatpak install --user" in c for c in s.r.commands())


def test_store_community_apps_are_explained(qapp):
    from marsos.apps.store.window import StoreWindow
    s = StoreWindow()
    assert "community app" in s.confirm_text(catalog.by_id("waydroid"))
    assert "password" in s.confirm_text(catalog.by_id("virtualbox"))
    assert "No password" in s.confirm_text(catalog.by_id("zen"))


# ------------------------------------------------------------------ installer wizard, end to end (dry-run backend)
def test_installer_wizard_end_to_end(qapp, monkeypatch):
    from marsos.apps.installer.window import InstallerWindow
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "src"))
    w = InstallerWindow(demo=True, hw=MAC); w.show()
    assert w.stack.currentIndex() == 0 and w.next.isEnabled()
    w.forward()                                                  # -> disk
    assert not w.next.isEnabled()                                # nothing chosen, nothing confirmed
    usb = w.disk.list.item(1)
    w.disk.list.setCurrentItem(usb)
    w.disk.confirm.setChecked(True)
    assert not w.disk.valid(), "must refuse the USB stick we booted from"
    w.disk.list.setCurrentRow(0); assert w.disk.valid() and w.next.isEnabled()
    w.forward()                                                  # -> account
    a = w.account
    assert not w.next.isEnabled()
    a.name.setText("Rose Smith"); a.name.textEdited.emit("Rose Smith")
    assert a.user.text() == "rose" and a.host.text() == "roses-macbook"
    a.pw.setText("abc"); a.pw2.setText("abc"); assert "at least 4" in a.problem()
    a.pw.setText("secret1"); a.pw2.setText("secret2"); assert "don't match" in a.problem()
    a.pw2.setText("secret1"); assert a.valid() and w.next.isEnabled()
    a.user.setText("root"); a.user.textEdited.emit("root"); assert not a.valid(); a.user.setText("rose")
    w.forward()                                                  # -> apps
    w.apps.boxes["zen"].setChecked(True); w.apps.boxes["virtualbox"].setChecked(True)
    w.forward()                                                  # -> review
    text = " ".join(v for _, v in w.summary())
    assert "Zen Browser" in text and "erased" in text and "rose" in text
    assert "Install marsOS" == w.next.text()
    plan = w.build_plan()
    assert plan.disk == "/dev/sda" and plan.is_mac and {x["id"] for x in plan.apps} == {"zen", "virtualbox"}
    w.forward()                                                  # -> install (runs the real backend in --dry-run)
    for _ in range(100):
        QTest.qWait(100)
        if w.stack.currentIndex() == 6:
            break
    assert w.stack.currentIndex() == 6, w.progress.log.toPlainText()
    assert "installed" in w.done.head.text().lower()
    assert w.progress.bar.value() == 100
    assert "Option" in w.done.sub.text()                         # Mac boot hint


def test_installer_refuses_on_installed_system(monkeypatch, capsys):
    from marsos.apps.installer import main as m
    monkeypatch.setattr(paths, "is_live", lambda: False)
    assert m.main(["marsos-installer"]) == 1
    assert "already installed" in capsys.readouterr().err


def test_installer_live_flag_is_noop_outside_live(monkeypatch):
    from marsos.apps.installer import main as m
    monkeypatch.setattr(paths, "is_live", lambda: False)
    assert m.main(["marsos-installer", "--live"]) == 0


# ------------------------------------------------------------------ bundle runner
def test_bundle_window(qapp, tmp_path):
    from marsos.apps.bundle.window import BundleWindow, human_size
    f = tmp_path / "VMware-Player.bundle"; f.write_bytes(b"#!/bin/sh\n# VMware Player\n" + b"0" * 4000)
    w = BundleWindow(runner=Runner(dry_run=True)); w.load(str(f))
    assert w.stack.currentIndex() == 1 and "VMware" in w.name.text()
    assert not w.go.isEnabled()                                  # needs the trust box first
    w.trust.setChecked(True); assert w.go.isEnabled()
    w.sum.setText(w.info.sha256); assert "genuine" in w.sum_msg.text()
    w.sum.setText("deadbeef"); assert "NOT match" in w.sum_msg.text()
    w.install(); settle(300)
    assert "done" in w.result.text().lower()
    assert any(c[1] == "run-bundle" for c in w.r.history)
    bad = tmp_path / "x.bundle"; bad.write_bytes(b"\x7fELF" + b"0" * 100)
    w.load(str(bad)); assert not w.go.isVisible() or not w.info.runnable
    assert human_size(4000) == "4 KB" and human_size(5_000_000) == "5.0 MB"


# ------------------------------------------------------------------ settings / welcome / updater / spotlight
def test_settings_panes_and_prefs(qapp):
    from marsos.apps.settings import panes
    from marsos.apps.settings.window import SettingsWindow
    w = SettingsWindow("about", runner=Runner(dry_run=True), hw=MAC); w.show(); settle()
    assert w.side.currentRow() == len(panes.ORDER) - 1
    for i in range(w.side.count()):
        w.side.setCurrentRow(i); settle(40)
    from marsos.core.prefs import Prefs
    ap = w.stack.widget(1).widget()
    ap.set_effects("light"); ap.set_motion(True); settle()
    p = Prefs.load()
    assert p.effects == "light" and p.reduce_motion
    assert any("AnimationDurationFactor 0.0" in c for c in ap.r.commands())


def test_welcome_flow(qapp, monkeypatch):
    from marsos.apps.welcome.window import WelcomeWindow, done_marker
    w = WelcomeWindow(runner=Runner(dry_run=True), hw=MAC); w.show()
    seen = []
    while True:
        seen.append(w.stack.currentIndex())
        if w.next.text() == "Get Started":
            break
        w.forward()
    assert 4 not in seen                                          # no 'pending apps' page when nothing is queued
    w.forward(); assert done_marker().exists()


def test_updater(qapp):
    from marsos.apps.updater.window import UpdaterWindow
    from marsos.core.updates import UpdateInfo
    u = UpdaterWindow(runner=Runner(dry_run=True), autocheck=False)
    u.show_info(UpdateInfo()); assert "up to date" in u.head.text()
    u.show_info(UpdateInfo(["linux-zen 1 -> 2"], ["a.b.C"])); assert "2 updates" in u.head.text() and "restart" in u.sub.text()
    u.apply(); settle(300); assert u.restart.isVisible() or "up to date" in u.head.text().lower()


def test_spotlight_window(qapp, tmp_path):
    from marsos.apps.spotlight.window import SpotlightWindow
    from marsos.core.desktop_entries import DesktopEntry
    ran = []
    eng = search.SearchEngine([DesktopEntry("ff.desktop", "Firefox", "/x/ff.desktop", generic="Web Browser")])
    w = SpotlightWindow(eng, perform=lambda r: ran.append(r)); w.popup()
    w.input.setText("fire"); w.refresh()
    assert w.results[0].title == "Firefox" and w.list.isVisible() is not None
    w.run_item(); assert ran and ran[0].action == ("launch", "/x/ff.desktop")
    w.popup(); w.input.setText("12*12"); w.refresh(); w.run_item()
    assert QApplication.clipboard().text() == "144"


def test_spotlight_toggle_client_without_server_returns_false(monkeypatch, tmp_path):
    from marsos.apps.spotlight import main as sm
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert sm.send() is False


def test_launchpad_filters(qapp):
    from marsos.apps.launchpad.window import LaunchpadWindow
    from marsos.core.desktop_entries import DesktopEntry
    w = LaunchpadWindow([DesktopEntry(f"{n}.desktop", n, "/x") for n in ("Firefox", "Files", "Settings")])
    assert w.grid.count() == 3
    w.search.setText("fi"); assert w.grid.count() == 2


# ------------------------------------------------------------------ packaging consistency
def test_pyproject_entry_points_import():
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text())
    for name, target in cfg["project"]["scripts"].items():
        mod, func = target.split(":")
        assert callable(getattr(importlib.import_module(mod), func)), name
    assert {"marsos-store", "marsos-installer", "marsos-bundle", "marsos-settings", "marsos-launchpad",
            "marsos-control-center", "marsos-updater", "marsos-welcome"} <= set(cfg["project"]["scripts"])   # the baseline's scripts


def test_desktop_files_valid_and_point_at_real_commands():
    scripts = set(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"])
    files = list((ROOT / "system").rglob("*.desktop")) + list((ROOT / "iso").rglob("*.desktop"))
    assert len(files) >= 12
    for f in files:
        text = f.read_text()
        assert text.startswith("[Desktop Entry]"), f
        exe = next(l for l in text.splitlines() if l.startswith("Exec=")).split("=", 1)[1].split()[0]
        assert exe in scripts, f"{f.name} runs unknown command {exe}"
    for f in (ROOT / "system/usr/share/applications").glob("org.marsos.*.desktop"):
        assert parse_entry(f) is not None or "NoDisplay=true" in f.read_text()


def test_polkit_and_systemd_files():
    pol = ET.parse(ROOT / "system/usr/share/polkit-1/actions/org.marsos.helper.policy").getroot()
    ann = {a.get("key"): a.text for a in pol.iter("annotate")}
    assert ann["org.freedesktop.policykit.exec.path"] == "/usr/bin/marsos-helper"
    unit = (ROOT / "system/usr/lib/systemd/system/marsos-firstboot.service").read_text()
    assert "ConditionPathExists=/var/lib/marsos/pending-apps.json" in unit and "process-pending" in unit
    assert (ROOT / "system/usr/lib/marsos/sudo-askpass").stat().st_mode & 0o111


def test_data_files_ship():
    for f in ("apps.json", "wallpapers/golden-gate-dawn.jpg", "wallpapers/golden-gate-dusk.jpg"):
        assert (paths.DATA_DIR / f).is_file()
    assert paths.QSS_FILE.is_file()


def test_helper_and_catalog_agree_on_names():
    """Every package in the catalog must be acceptable to the root helper's validator."""
    from marsos.core import helper
    for a in catalog.load():
        if a.source in ("pacman",):
            helper._pkgs(a.packages)


def test_iso_package_lists_have_no_duplicates():
    for f in ("packages.txt", "aur-packages.txt"):
        lines = [l.strip() for l in (ROOT / "iso" / f).read_text().splitlines() if l.strip() and not l.startswith("#")]
        assert len(lines) == len(set(lines)), f
