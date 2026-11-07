"""Plasma menu bar (top) and floating Dock (bottom) in a macOS arrangement, via Plasma's scripting API."""
from __future__ import annotations
import time

from marsos.core.runner import Runner

DOCK_APPS = ["org.marsos.Launchpad", "firefox", "org.kde.dolphin", "org.marsos.Store", "org.marsos.Settings"]


def layout_script(dock_height: int = 56) -> str:
    launchers = ", ".join(f'"applications:{a}.desktop"' for a in DOCK_APPS)
    return f"""
var old = panels(); for (var i = 0; i < old.length; i++) {{ old[i].remove(); }}
var bar = new Panel(); bar.location = "top"; bar.height = 28;
try {{ bar.hiding = "none"; }} catch (e) {{}}
var logo = bar.addWidget("org.kde.plasma.icon");
logo.currentConfigGroup = ["General"]; logo.writeConfig("icon", "distributor-logo"); logo.writeConfig("url", "applications:org.marsos.Settings.desktop");
bar.addWidget("org.kde.plasma.appmenu");
bar.addWidget("org.kde.plasma.panelspacer");
bar.addWidget("org.kde.plasma.systemtray");
var cc = bar.addWidget("org.kde.plasma.icon");
cc.currentConfigGroup = ["General"]; cc.writeConfig("icon", "configure"); cc.writeConfig("url", "applications:org.marsos.ControlCenter.desktop");
var sp = bar.addWidget("org.kde.plasma.icon");
sp.currentConfigGroup = ["General"]; sp.writeConfig("icon", "system-search"); sp.writeConfig("url", "applications:org.marsos.Spotlight.desktop");
bar.addWidget("org.kde.plasma.digitalclock");
var dock = new Panel(); dock.location = "bottom"; dock.height = {dock_height}; dock.alignment = "center";
try {{ dock.lengthMode = "fit"; }} catch (e) {{}}
try {{ dock.floating = true; }} catch (e) {{}}
try {{ dock.hiding = "dodgewindows"; }} catch (e) {{}}
var tasks = dock.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"]; tasks.writeConfig("launchers", [{launchers}]);
"""


def apply_layout(r: Runner, dock_height: int = 56, wait: float = 40.0) -> bool:
    deadline = time.time() + wait
    while True:
        res = r.run(["qdbus6", "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", layout_script(dock_height)])
        if res.ok or r.dry_run or time.time() > deadline:
            return res.ok
        time.sleep(2)
