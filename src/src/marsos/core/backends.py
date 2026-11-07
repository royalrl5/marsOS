"""Install apps from Flathub, pacman and the AUR; search Flathub and the AUR."""
from __future__ import annotations
import json
import urllib.parse
import urllib.request

from marsos import paths
from marsos.core.catalog import App
from marsos.core.runner import Runner

FLATHUB_REPO = "https://dl.flathub.org/repo/flathub.flatpakrepo"
ASKPASS = "/usr/lib/marsos/sudo-askpass"


def install_commands(app: App) -> list[list[str]]:
    if app.source == "flatpak":
        return [["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", FLATHUB_REPO],
                ["flatpak", "install", "--user", "-y", "--noninteractive", "flathub", *app.packages]]
    if app.source == "pacman":
        return [[paths.helper_path(), "pacman-install", *app.packages]]
    if app.source == "aur":
        return [["paru", "--sudo", ASKPASS, "-S", "--needed", "--noconfirm", "--skipreview", *app.packages]]
    raise ValueError(app.source)


def remove_commands(app: App) -> list[list[str]]:
    if app.source == "flatpak":
        return [["flatpak", "uninstall", "--user", "-y", "--noninteractive", app.pkg]]
    return [[paths.helper_path(), "pacman-remove", app.packages[0]]]


def is_installed(r: Runner, app: App) -> bool:
    if app.source == "flatpak":
        return r.run(["flatpak", "info", app.pkg]).ok
    return r.run(["pacman", "-Q", app.packages[0]]).ok


def _get_json(url: str, data: dict | None = None):
    req = urllib.request.Request(url, headers={"User-Agent": "marsOS-Store", "Content-Type": "application/json"},
                                 data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def search_flathub(q: str) -> list[App]:
    try:
        hits = _get_json("https://flathub.org/api/v2/search", {"query": q}).get("hits", [])[:12]
    except Exception:
        return []
    return [App(id="fh-" + h["app_id"], name=h.get("name") or h["app_id"], category="Search results",
                source="flatpak", pkg=h["app_id"], summary=(h.get("summary") or "")[:90],
                description=h.get("summary") or "No description provided.", icon=h["app_id"])
            for h in hits if h.get("app_id")]


def search_aur(q: str) -> list[App]:
    try:
        res = _get_json("https://aur.archlinux.org/rpc/v5/search/" + urllib.parse.quote(q) + "?by=name-desc")["results"]
    except Exception:
        return []
    res = sorted(res, key=lambda x: -x.get("NumVotes", 0))[:10]
    return [App(id="aur-" + x["Name"], name=x["Name"], category="Search results", source="aur", pkg=x["Name"],
                summary="Community software", description=x.get("Description") or "No description provided.",
                advanced=True) for x in res]
