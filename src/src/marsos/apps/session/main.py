"""marsos-session-init: runs at every login. Applies the macOS look once, keeps preferences in force, tunes input devices."""
from __future__ import annotations
import sys

from marsos import paths
from marsos.core import hardware, system
from marsos.core.backends import FLATHUB_REPO
from marsos.core.prefs import Prefs
from marsos.core.runner import Runner

LAYOUT_VERSION = "1"


def apply_input(prefs: Prefs, r: Runner | None = None) -> None:
    """Natural scrolling + tap-to-click on every touchpad, through KWin's D-Bus interface (Wayland)."""
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtDBus import QDBusConnection, QDBusInterface
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    bus = QDBusConnection.sessionBus()
    mgr = QDBusInterface("org.kde.KWin", "/org/kde/KWin/InputDevice", "org.kde.KWin.InputDeviceManager", bus)
    if not mgr.isValid():
        return
    for name in mgr.property("devicesSysNames") or []:
        dev = QDBusInterface("org.kde.KWin", f"/org/kde/KWin/InputDevice/{name}", "org.kde.KWin.InputDevice", bus)
        if dev.isValid() and dev.property("touchpad"):
            dev.setProperty("naturalScroll", prefs.natural_scroll)
            dev.setProperty("tapToClick", prefs.tap_to_click)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    prefs = Prefs.load(); r = Runner()
    if "--input" in argv:
        apply_input(prefs); return 0
    marker = paths.config_dir() / "session-layout"
    first = not marker.exists() or marker.read_text().strip() != LAYOUT_VERSION or "--reset-layout" in argv
    r.run(["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", FLATHUB_REPO])
    if first:
        hw = hardware.detect(); dark = prefs.appearance == "dark"
        system.apply_all(r, prefs, dark, prefs.resolved_effects(hw))
        from marsos.apps.session.layout import apply_layout
        system.apply_wallpaper(r, dark)
        apply_layout(r, prefs.dock_size)
        marker.parent.mkdir(parents=True, exist_ok=True); marker.write_text(LAYOUT_VERSION)
    try:
        apply_input(prefs)
    except Exception:  # noqa: BLE001 - input tuning is best-effort
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
