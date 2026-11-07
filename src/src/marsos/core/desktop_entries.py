"""Read .desktop files (installed apps, Flatpak apps)."""
from __future__ import annotations
import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DesktopEntry:
    id: str
    name: str
    path: str
    generic: str = ""
    comment: str = ""
    icon: str = ""
    exec: str = ""
    keywords: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)


def default_dirs() -> list[Path]:
    home = Path.home()
    dirs = [Path("/usr/share/applications"), Path("/usr/local/share/applications"),
            Path("/var/lib/flatpak/exports/share/applications"),
            home / ".local/share/flatpak/exports/share/applications",
            home / ".local/share/applications"]
    for d in os.environ.get("XDG_DATA_DIRS", "").split(":"):
        if d:
            dirs.append(Path(d) / "applications")
    return dirs


def parse_entry(path: Path, base: Path | None = None) -> DesktopEntry | None:
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str  # keep case
    try:
        cp.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError, OSError):
        return None
    if not cp.has_section("Desktop Entry"):
        return None
    s = cp["Desktop Entry"]
    if s.get("Type") != "Application" or s.get("NoDisplay", "false").lower() == "true" \
            or s.get("Hidden", "false").lower() == "true":
        return None
    only = s.get("OnlyShowIn")
    if only and "KDE" not in only.split(";"):
        return None
    name = s.get("Name")
    if not name:
        return None
    rel = path.relative_to(base) if base and path.is_relative_to(base) else Path(path.name)
    split = lambda v: [x for x in (v or "").split(";") if x]
    return DesktopEntry(id=str(rel).replace("/", "-"), name=name, path=str(path),
                        generic=s.get("GenericName", ""), comment=s.get("Comment", ""),
                        icon=s.get("Icon", ""), exec=s.get("Exec", ""),
                        keywords=split(s.get("Keywords")), categories=split(s.get("Categories")))


def load_all(dirs: list[Path] | None = None) -> list[DesktopEntry]:
    seen: dict[str, DesktopEntry] = {}
    for d in dirs if dirs is not None else default_dirs():
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.desktop")):
            e = parse_entry(p, d)
            if e:
                seen[e.id] = e
    return sorted(seen.values(), key=lambda e: e.name.lower())
