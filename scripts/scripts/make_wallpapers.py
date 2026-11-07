"""Generate the 'Golden Gate' wallpapers (original artwork drawn with Qt). usage: python scripts/make_wallpapers.py"""
import math, os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

W, H = 2560, 1600
OUT = Path(__file__).resolve().parent.parent / "src/marsos/data/wallpapers"


def hills(p, base, amp, color, seed, freq=1.0):
    path = QPainterPath(QPointF(0, H))
    for x in range(0, W + 20, 20):
        y = base + amp * (math.sin((x / W) * math.pi * 2 * freq + seed) * 0.6 + math.sin((x / W) * math.pi * 5 * freq + seed * 2) * 0.4)
        path.lineTo(x, y)
    path.lineTo(W, H); path.closeSubpath(); p.fillPath(path, QColor(color))


def bridge(p, color, horizon):
    pen = QPen(QColor(color), 10); p.setPen(pen)
    towers = [W * 0.34, W * 0.70]; top = horizon - 560
    for x in towers:
        p.drawLine(QPointF(x - 22, horizon + 40), QPointF(x - 22, top)); p.drawLine(QPointF(x + 22, horizon + 40), QPointF(x + 22, top))
        for k in range(4):
            y = top + 90 + k * 120; p.drawLine(QPointF(x - 22, y), QPointF(x + 22, y))
    deck = horizon - 70
    p.setPen(QPen(QColor(color), 14)); p.drawLine(QPointF(0, deck), QPointF(W, deck))
    p.setPen(QPen(QColor(color), 6)); p.setBrush(Qt.BrushStyle.NoBrush)
    t0, t1, ty = towers[0], towers[1], top + 6
    main = QPainterPath(QPointF(t0, ty)); main.quadTo(QPointF((t0 + t1) / 2, 2 * (deck - 45) - ty), QPointF(t1, ty)); p.drawPath(main)
    left = QPainterPath(QPointF(t0, ty)); left.quadTo(QPointF(t0 * 0.45, (ty + deck) / 2 + 120), QPointF(-60, deck - 10)); p.drawPath(left)
    right = QPainterPath(QPointF(t1, ty)); right.quadTo(QPointF(t1 + (W - t1) * 0.55, (ty + deck) / 2 + 120), QPointF(W + 60, deck - 10)); p.drawPath(right)
    p.setPen(QPen(QColor(color), 3))
    for x in range(int(t0) + 60, int(t1) - 40, 70):   # suspenders
        u = (x - (t0 + t1) / 2) / ((t1 - t0) / 2); cy = ty + (deck - 45 - ty) * (1 - u * u)
        p.drawLine(QPointF(x, cy), QPointF(x, deck))


def make(name, stops, sun, hill_cols, bridge_col):
    img = QImage(W, H, QImage.Format.Format_RGB32); p = QPainter(img); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(0, 0, 0, H * 0.72)
    for pos, col in stops: g.setColorAt(pos, QColor(col))
    p.fillRect(0, 0, W, H, g)
    horizon = H * 0.66
    rg = QRadialGradient(QPointF(W * 0.52, horizon), W * 0.42); rg.setColorAt(0, QColor(*sun)); rg.setColorAt(1, QColor(sun[0], sun[1], sun[2], 0))
    p.fillRect(0, 0, W, H, QBrush(rg))
    sea = QLinearGradient(0, horizon, 0, H); sea.setColorAt(0, QColor(hill_cols[0])); sea.setColorAt(1, QColor(hill_cols[1]))
    p.fillRect(QRectF(0, horizon, W, H - horizon), sea)
    bridge(p, bridge_col, horizon)
    hills(p, H * 0.80, 60, hill_cols[2], 1.0, 0.8); hills(p, H * 0.90, 70, hill_cols[3], 3.0, 1.2)
    p.end(); OUT.mkdir(parents=True, exist_ok=True); img.save(str(OUT / name), "JPG", 92); print("wrote", OUT / name)


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    make("golden-gate-dawn.jpg", [(0, "#3B2A6B"), (0.45, "#C7476E"), (0.8, "#FF9E5E"), (1, "#FFD59A")], (255, 190, 110, 230),
         ["#E88A5A", "#4B2D5F", "#34224B", "#1F1535"], "#C0392B")
    make("golden-gate-dusk.jpg", [(0, "#0B1030"), (0.5, "#2B2563"), (0.85, "#8A3B6E"), (1, "#E0745A")], (240, 120, 90, 200),
         ["#4A2A55", "#120E26", "#0E0B1E", "#08060F"], "#8E2A24")
