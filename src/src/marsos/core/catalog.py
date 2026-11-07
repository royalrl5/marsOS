"""The curated app catalog (apps.json): every app has a plain-language explanation."""
from __future__ import annotations
import json
from dataclasses import dataclass
from functools import lru_cache

from marsos.paths import DATA_DIR

SOURCE_LABEL = {"flatpak": "App Store", "pacman": "System", "aur": "Community"}


@dataclass(frozen=True)
class App:
    id: str
    name: str
    category: str
    source: str            # flatpak | pacman | aur
    pkg: str               # space separated for pacman/aur
    summary: str
    description: str
    installer: bool = False   # offered on the installer's app page
    advanced: bool = False    # hidden from the store unless "advanced apps" is on
    default: bool = False     # pre-ticked in the installer
    icon: str = ""
    desktop_id: str = ""

    @property
    def source_label(self) -> str:
        return SOURCE_LABEL.get(self.source, self.source)

    @property
    def packages(self) -> list[str]:
        return self.pkg.split()


@lru_cache(maxsize=1)
def load(path=None) -> tuple[App, ...]:
    raw = json.loads((path or DATA_DIR / "apps.json").read_text())
    return tuple(App(**item) for item in raw)


def by_id(app_id: str) -> App | None:
    return next((a for a in load() if a.id == app_id), None)


def categories(include_advanced: bool) -> list[str]:
    seen: list[str] = []
    for a in load():
        if (include_advanced or not a.advanced) and a.category not in seen:
            seen.append(a.category)
    return seen


def search(query: str, include_advanced: bool = True) -> list[App]:
    q = query.lower().strip()
    out = []
    for a in load():
        if a.advanced and not include_advanced:
            continue
        if not q or q in a.name.lower() or q in a.summary.lower() or q in a.description.lower() or q in a.category.lower():
            out.append(a)
    return out


def installer_options() -> list[App]:
    return [a for a in load() if a.installer]
