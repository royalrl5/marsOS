"""Spotlight search engine: apps, settings, files, calculator, system actions, App Store, web."""
from __future__ import annotations
import ast
import math
import operator
import os
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from marsos.core import catalog
from marsos.core.desktop_entries import DesktopEntry

SETTINGS_PANES = [  # id, title, keywords
    ("wifi", "Wi-Fi", "wireless internet network connect"),
    ("bluetooth", "Bluetooth", "headphones speaker mouse keyboard"),
    ("appearance", "Appearance", "dark mode light theme wallpaper background colour effects"),
    ("display", "Display & Text Size", "screen resolution brightness bigger text larger font zoom"),
    ("sound", "Sound", "volume speakers microphone"),
    ("keyboard", "Keyboard & Trackpad", "command key mouse scroll tap click shortcuts"),
    ("datetime", "Date & Time", "clock timezone"),
    ("users", "Users & Password", "account password login"),
    ("updates", "Software Update", "upgrade install updates"),
    ("about", "About This Mac", "version memory model specs"),
]
SYSTEM_ACTIONS = [  # title, keywords, command
    ("Shut Down", "power off turn off shutdown", ["systemctl", "poweroff"]),
    ("Restart", "reboot restart", ["systemctl", "reboot"]),
    ("Sleep", "suspend sleep", ["systemctl", "suspend"]),
    ("Lock Screen", "lock", ["loginctl", "lock-session"]),
    ("Log Out", "logout sign out", ["qdbus6", "org.kde.Shutdown", "/Shutdown", "logout"]),
]


@dataclass
class Result:
    kind: str       # app | settings | file | calc | action | store | web
    title: str
    subtitle: str = ""
    icon: str = ""
    action: tuple = ()
    score: int = 0


def score(query: str, text: str) -> int:
    q, t = query.lower(), text.lower()
    if not q or not t:
        return 0
    if t == q:
        return 100
    if t.startswith(q):
        return 90
    if any(w.startswith(q) for w in re.split(r"[\s\-_.]+", t)):
        return 75
    if q in t:
        return 60
    it = iter(t)
    if len(q) >= 3 and len(t) <= 40 and all(c in it for c in q):
        return 30
    return 0


# ---------------------------------------------------------------- calculator
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {"sqrt": math.sqrt, "abs": abs, "round": round, "sin": math.sin, "cos": math.cos, "tan": math.tan,
          "log": math.log10, "ln": math.log}
_CONST = {"pi": math.pi, "e": math.e}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        l, r = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(r) > 1000:
            raise ValueError("too big")
        return _OPS[type(node.op)](l, r)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONST:
        return _CONST[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS and len(node.args) == 1:
        return _FUNCS[node.func.id](_eval(node.args[0]))
    raise ValueError("unsupported")


def calculate(text: str) -> str | None:
    t = text.strip().lower().replace("×", "*").replace("÷", "/").replace("^", "**").replace(",", "")
    m = re.fullmatch(r"([\d.]+)\s*%\s*of\s*([\d.]+)", t)
    if m:
        t = f"{m.group(1)}/100*{m.group(2)}"
    if not re.search(r"\d", t) or not re.search(r"[-+*/%]|\(|sqrt|sin|cos|tan|log|ln|abs|round", t):
        return None
    if re.fullmatch(r"[\d.\s]+", t):
        return None
    try:
        v = _eval(ast.parse(t, mode="eval"))
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, TypeError):
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        v = round(v, 10)
        return str(int(v)) if v == int(v) and abs(v) < 1e15 else f"{v:.10g}"
    return str(v)


# ---------------------------------------------------------------- file index
class FileIndex:
    def __init__(self, roots: list[Path] | None = None, max_depth: int = 4, max_files: int = 60000):
        home = Path.home()
        self.roots = roots if roots is not None else [home / n for n in
                     ("Documents", "Desktop", "Downloads", "Pictures", "Music", "Videos")]
        self.max_depth, self.max_files = max_depth, max_files
        self.files: list[tuple[str, str]] = []  # (lower name, path)
        self.ready = threading.Event()

    def build(self) -> None:
        out: list[tuple[str, str]] = []
        for root in self.roots:
            if not root.is_dir():
                continue
            base = len(root.parts)
            for dp, dn, fn in os.walk(root):
                depth = len(Path(dp).parts) - base
                dn[:] = [d for d in dn if not d.startswith(".")] if depth < self.max_depth else []
                for n in fn + (list(dn) if True else []):
                    if not n.startswith("."):
                        out.append((n.lower(), os.path.join(dp, n)))
                if len(out) >= self.max_files:
                    break
        self.files = out
        self.ready.set()

    def build_async(self) -> None:
        threading.Thread(target=self.build, daemon=True).start()

    def search(self, q: str, limit: int = 6) -> list[str]:
        q = q.lower()
        hits = [(score(q, n), p) for n, p in self.files if q in n]
        hits.sort(key=lambda x: (-x[0], len(x[1])))
        return [p for _, p in hits[:limit]]


# ---------------------------------------------------------------- engine
class SearchEngine:
    def __init__(self, entries: list[DesktopEntry], index: FileIndex | None = None, installed_ids: set[str] | None = None):
        self.entries = entries
        self.index = index
        self.installed_ids = installed_ids or set()

    def search(self, query: str, limit: int = 9) -> list[Result]:
        q = query.strip()
        if not q:
            return []
        res: list[Result] = []
        calc = calculate(q)
        if calc is not None:
            res.append(Result("calc", calc, f"{q} =  (press Return to copy)", "accessories-calculator", ("copy", calc), 1000))
        for e in self.entries:
            ns = score(q, e.name)
            s = max(ns + 5 if ns else 0, score(q, e.generic), score(q, e.comment) // 2,
                    max((score(q, k) for k in e.keywords), default=0) // 2)
            if s:
                res.append(Result("app", e.name, e.generic or e.comment, e.icon, ("launch", e.path), 20 + s))
        for pid, title, kw in SETTINGS_PANES:
            s = max(score(q, title), score(q, kw) // 2)
            if s:
                res.append(Result("settings", title, "System Settings", "preferences-system", ("settings", pid), 10 + s))
        for title, kw, cmd in SYSTEM_ACTIONS:
            s = max(score(q, title), score(q, kw) // 2)
            if s >= 60:
                res.append(Result("action", title, "System", "system-shutdown", ("cmd", cmd), 15 + s))
        have = {e.id.removesuffix(".desktop") for e in self.entries} | self.installed_ids
        for a in catalog.load():
            if a.id in have or a.desktop_id in have or a.pkg in have or a.advanced:
                continue
            s = score(q, a.name)
            if s >= 60:
                res.append(Result("store", f"Get {a.name}", a.summary + " – from the App Store", a.icon, ("store", a.id), 5 + s))
        if self.index and len(q) >= 2:
            for p in self.index.search(q, 5):
                res.append(Result("file", os.path.basename(p), os.path.dirname(p).replace(str(Path.home()), "~"),
                                  "text-x-generic", ("open", p), score(q, os.path.basename(p))))
        res.sort(key=lambda r: -r.score)
        res = res[:limit]
        if len(q) >= 2 and calc is None:
            res.append(Result("web", f"Search the web for “{q}”", "DuckDuckGo", "internet-web-browser",
                              ("url", "https://duckduckgo.com/?q=" + _quote(q)), 1))
        return res


def _quote(s: str) -> str:
    from urllib.parse import quote
    return quote(s)


def perform(r: Result) -> None:
    kind, arg = r.action[0], (r.action[1] if len(r.action) > 1 else None)
    if kind == "launch":
        subprocess.Popen(["gio", "launch", arg], start_new_session=True)
    elif kind == "open":
        subprocess.Popen(["xdg-open", arg], start_new_session=True)
    elif kind == "url":
        subprocess.Popen(["xdg-open", arg], start_new_session=True)
    elif kind == "settings":
        subprocess.Popen(["marsos-settings", "--pane", arg], start_new_session=True)
    elif kind == "store":
        subprocess.Popen(["marsos-store", "--app", arg], start_new_session=True)
    elif kind == "cmd":
        subprocess.Popen(arg, start_new_session=True)
    # "copy" is handled by the UI (needs the clipboard)
