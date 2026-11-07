"""macOS-style theme (light / dark, accent colours, adjustable text size)."""
from __future__ import annotations
import os
from pathlib import Path
from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from marsos.core.prefs import Prefs
from marsos.core.system import ACCENTS
from marsos.paths import QSS_FILE

LIGHT = dict(bg="#F5F5F7", surface="#FFFFFF", sidebar="#E9E9EC", text="#1D1D1F", secondary="#6E6E73",
             border="#D8D8DC", hover="#E8E8ED", scroll="#BDBDC2", danger="#D70015", ok="#248A3D", warnbg="#FFF1F0")
DARK = dict(bg="#1E1E20", surface="#2C2C2E", sidebar="#262628", text="#F5F5F7", secondary="#98989D",
            border="#3D3D40", hover="#3A3A3D", scroll="#5A5A5E", danger="#FF453A", ok="#32D74B", warnbg="#3A2220")
FONT_STACK = "Inter, SF Pro Text, Noto Sans, Helvetica Neue, sans-serif"


def accent_hex(name: str) -> str:
    r, g, b = (int(x) for x in ACCENTS.get(name, ACCENTS["blue"]).split(","))
    return f"#{r:02X}{g:02X}{b:02X}"


def _shade(hexcolor: str, f: float) -> str:
    r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(c * f))) for c in (r, g, b))


def system_is_dark(app: QApplication) -> bool:
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        return False


def colors(dark: bool, accent: str = "blue") -> dict:
    c = dict(DARK if dark else LIGHT)
    a = accent_hex(accent)
    r, g, b = (int(a[i:i + 2], 16) for i in (1, 3, 5))
    c.update(accent=a, accent_hover=_shade(a, 0.9), accent_soft=f"rgba({r},{g},{b},{0.30 if dark else 0.16})")
    return c


def check_icon() -> str:
    """White check mark PNG used inside ticked check boxes (QSS needs a file)."""
    d = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "marsos"
    f = d / "check.png"
    if not f.exists():
        d.mkdir(parents=True, exist_ok=True)
        img = QImage(20, 20, QImage.Format.Format_ARGB32); img.fill(QColor(0, 0, 0, 0))
        p = QPainter(img); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("white"), 2.4); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen); p.drawPolyline([(5.0, 10.5), (8.6, 14.0), (15.0, 6.5)] if False else
                                      [__import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(*pt) for pt in ((5.0, 10.5), (8.6, 14.0), (15.0, 6.5))])
        p.end(); img.save(str(f))
    return f.as_posix()


def build_qss(dark: bool, scale: float = 1.0, accent: str = "blue") -> str:
    s = 10 * scale
    c = colors(dark, accent)
    c.update(check=check_icon(), font=FONT_STACK, size=f"{s:g}", small=f"{s * 0.88:g}", h2=f"{s * 1.2:g}", h1=f"{s * 1.9:g}", hero=f"{s * 2.9:g}")
    return Template(QSS_FILE.read_text()).safe_substitute(c)


def apply_theme(app: QApplication, prefs: Prefs | None = None) -> dict:
    p = prefs or Prefs.load()
    dark = p.appearance == "dark" or (p.appearance == "auto" and system_is_dark(app))
    app.setStyle("Fusion")
    f = QFont(); f.setFamilies(["Inter", "Noto Sans", "Sans Serif"]); f.setPointSizeF(10 * p.text_scale)
    app.setFont(f)
    app.setStyleSheet(build_qss(dark, p.text_scale, p.accent))
    cols = colors(dark, p.accent)
    cols["dark"] = dark
    app.setProperty("mcolors", cols)
    return cols


def current_colors() -> dict:
    app = QGuiApplication.instance()
    c = app.property("mcolors") if app else None
    return c or {**colors(False), "dark": False}
