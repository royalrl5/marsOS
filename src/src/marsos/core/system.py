"""Apply user preferences to the Plasma desktop (kwriteconfig6 / KWin). Pure command generation + Runner."""
from __future__ import annotations

from marsos.core.prefs import Prefs
from marsos.core.runner import Runner

EFFECTS = {   # profile -> KWin plugin switches
    "full":     dict(blur=True,  wobblywindows=True,  magiclamp=True,  squash=False, overview=True, slide=True, fade=True, scale=True),
    "balanced": dict(blur=False, wobblywindows=False, magiclamp=True,  squash=False, overview=True, slide=True, fade=True, scale=True),
    "light":    dict(blur=False, wobblywindows=False, magiclamp=False, squash=True,  overview=True, slide=False, fade=True, scale=False),
}
ACCENTS = {"blue": "0,122,255", "purple": "175,82,222", "pink": "255,45,85", "red": "255,59,48",
           "orange": "255,149,0", "yellow": "255,204,0", "green": "40,205,65", "graphite": "142,142,147"}
SCALES = {"Default": 1.0, "Large": 1.25, "Extra large": 1.5}


def kw(r: Runner, file: str, group: str, key: str, value) -> None:
    v = str(value).lower() if isinstance(value, bool) else str(value)
    r.run(["kwriteconfig6", "--file", file, "--group", group, "--key", key, v])


def apply_effects(r: Runner, profile: str, reduce_motion: bool = False) -> None:
    e = EFFECTS.get(profile, EFFECTS["balanced"])
    for name, key in (("blur", "blur"), ("wobblywindows", "wobblywindows"), ("magiclamp", "magiclamp"),
                      ("squash", "squash"), ("overview", "overview"), ("slide", "slide"),
                      ("fade", "kwin4_effect_fadingpopups"), ("scale", "kwin4_effect_scale")):
        kw(r, "kwinrc", "Plugins", f"{key}Enabled", e[name] and not (reduce_motion and name in ("wobblywindows", "magiclamp")))
    factor = 0.0 if reduce_motion else {"full": 0.7, "balanced": 0.8, "light": 0.5}[profile]
    kw(r, "kdeglobals", "KDE", "AnimationDurationFactor", factor)
    r.run(["qdbus6", "org.kde.KWin", "/KWin", "reconfigure"])


def apply_appearance(r: Runner, dark: bool, accent: str = "blue") -> None:
    laf = "com.github.vinceliuice.WhiteSur-dark" if dark else "com.github.vinceliuice.WhiteSur"
    have = r.run(["plasma-apply-lookandfeel", "--list"]).stdout
    if laf in have:
        r.run(["plasma-apply-lookandfeel", "-a", laf])
    else:
        r.run(["plasma-apply-lookandfeel", "-a", "org.kde.breezedark.desktop" if dark else "org.kde.breeze.desktop"])
    kw(r, "kdeglobals", "General", "AccentColor", ACCENTS.get(accent, ACCENTS["blue"]))
    kw(r, "kdeglobals", "Icons", "Theme", "WhiteSur-dark" if dark else "WhiteSur")


def apply_text_scale(r: Runner, scale: float) -> None:
    size = round(10 * scale)
    font = f"Inter,{size},-1,5,50,0,0,0,0,0"
    for key in ("font", "menuFont", "toolBarFont", "activeFont"):
        kw(r, "kdeglobals", "General", key, font)
    kw(r, "kdeglobals", "General", "smallestReadableFont", f"Inter,{max(9, size - 1)},-1,5,50,0,0,0,0,0")
    kw(r, "kcminputrc", "Mouse", "cursorSize", int(24 * scale))
    kw(r, "kwinrc", "org.kde.kdecoration2", "ButtonsOnLeft", "XIA")
    kw(r, "kwinrc", "org.kde.kdecoration2", "ButtonsOnRight", "")


def apply_all(r: Runner, p: Prefs, dark: bool, profile: str) -> None:
    apply_appearance(r, dark, p.accent)
    apply_text_scale(r, p.text_scale)
    apply_effects(r, profile, p.reduce_motion)


def apply_wallpaper(r: Runner, dark: bool) -> None:
    from marsos.paths import DATA_DIR
    img = DATA_DIR / "wallpapers" / ("golden-gate-dusk.jpg" if dark else "golden-gate-dawn.jpg")
    if img.exists():
        r.run(["plasma-apply-wallpaperimage", str(img)])
