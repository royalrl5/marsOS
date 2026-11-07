from __future__ import annotations
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
                               QProgressBar, QVBoxLayout, QWidget)

from marsos.core import bundle_backend as bb
from marsos.core.runner import Runner
from marsos.ui import anim
from marsos.ui.widgets import Card, FadeStack, button, icon_label, label, separator
from marsos.ui.workers import run_async, run_commands


def human_size(n: int) -> str:
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.1f} MB" if n >= 1e6 else f"{max(1, n // 1000)} KB"


class DropZone(Card):
    def __init__(self, on_file):
        super().__init__()
        self.on_file = on_file; self.setAcceptDrops(True); self.setMinimumHeight(230)
        self.lay.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lay.setSpacing(12)
        self.lay.addWidget(icon_label("package-x-generic", "B", 84), 0, Qt.AlignmentFlag.AlignHCenter)
        self.lay.addWidget(label("Drop a .bundle file here", "title", align=Qt.AlignmentFlag.AlignCenter))
        self.lay.addWidget(label("Bundle Runner will look inside it first and explain what it is "
                                 "before anything is installed.", "caption", align=Qt.AlignmentFlag.AlignCenter))
        b = button("Choose File…", "primary", pill=True); b.clicked.connect(self.choose)
        self.lay.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)

    def choose(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Choose a bundle", os.path.expanduser("~/Downloads"),
                                           "Bundles (*.bundle *.flatpak);;All files (*)")
        if f:
            self.on_file(f)

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.on_file(urls[0])


class BundleWindow(QMainWindow):
    def __init__(self, path: str | None = None, runner: Runner | None = None):
        super().__init__()
        self.setWindowTitle("Bundle Runner"); self.resize(680, 720)
        self.r = runner or Runner(); self.info: bb.BundleInfo | None = None
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        v = QVBoxLayout(root); v.setContentsMargins(28, 22, 28, 22); v.setSpacing(14)
        self.stack = FadeStack(); v.addWidget(self.stack, 1)
        self.stack.addWidget(DropZone(self.load))
        # --- details page
        d = QWidget(); dv = QVBoxLayout(d); dv.setContentsMargins(0, 0, 0, 0); dv.setSpacing(12)
        head = QHBoxLayout(); self.icon = icon_label("package-x-generic", "B", 64); head.addWidget(self.icon)
        hc = QVBoxLayout(); self.name = label("", "title"); self.kind = label("", "subtitle"); hc.addWidget(self.name); hc.addWidget(self.kind)
        head.addLayout(hc, 1); dv.addLayout(head)
        self.details = Card(); dv.addWidget(self.details)
        self.warn = Card(warn=True); self.warn_label = label("", "warn"); self.warn.lay.addWidget(self.warn_label); dv.addWidget(self.warn)
        chk = Card(); chk.lay.addWidget(label("Optional: check the file is genuine", "heading"))
        chk.lay.addWidget(label("If the website that gave you this file showed a long code (a “checksum” or “SHA-256”), paste it here.", "caption"))
        self.sum = QLineEdit(); self.sum.setPlaceholderText("Paste the code here (optional)"); self.sum.textChanged.connect(self.check_sum)
        chk.lay.addWidget(self.sum); self.sum_msg = label("", "caption"); chk.lay.addWidget(self.sum_msg); dv.addWidget(chk)
        from PySide6.QtWidgets import QCheckBox
        self.trust = QCheckBox("I got this file from a source I trust"); self.trust.toggled.connect(self.update_btn); dv.addWidget(self.trust)
        self.bar = QProgressBar(); self.bar.setRange(0, 0); self.bar.hide(); dv.addWidget(self.bar)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMinimumHeight(110); self.log.hide(); dv.addWidget(self.log)
        self.result = label("", "heading"); dv.addWidget(self.result)
        row = QHBoxLayout(); self.other = button("Choose Another File"); self.other.clicked.connect(lambda: self.stack.go(0))
        self.go = button("Install", "primary", pill=True); self.go.clicked.connect(self.install)
        row.addWidget(self.other); row.addStretch(1); row.addWidget(self.go); dv.addLayout(row)
        self.stack.addWidget(d)
        self.setAcceptDrops(True)
        if path:
            self.load(path)

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.load(urls[0])

    def load(self, path: str) -> None:
        try:
            info = bb.inspect(path)
        except (OSError, FileNotFoundError) as e:
            QMessageBox.warning(self, "Can't open file", f"That file couldn't be opened.\n\n{e}"); return
        self.info = info
        self.name.setText(info.product or info.name); self.kind.setText(f"{info.kind_label} · {human_size(info.size)}")
        while self.details.lay.count():
            w = self.details.lay.takeAt(0).widget()
            if w: w.deleteLater()
        facts = [("File", info.name), ("Where", os.path.dirname(info.path) or "."), ("Fingerprint (SHA-256)", info.sha256)]
        if info.notes:
            facts.insert(2, ("It says", "  ".join(info.notes)))
        for k, val in facts:
            self.details.lay.addWidget(label(k, "caption")); t = label(val); t.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.details.lay.addWidget(t)
        self.warn_label.setText("\n".join(info.warnings)); self.warn.setVisible(bool(info.warnings))
        self.trust.setChecked(False); self.trust.setVisible(info.runnable); self.go.setVisible(info.runnable)
        self.result.setText(""); self.bar.hide(); self.log.hide(); self.log.clear(); self.sum.clear(); self.sum_msg.setText("")
        self.update_btn(); self.stack.go(1)

    def check_sum(self, text: str) -> None:
        if not text.strip() or not self.info:
            self.sum_msg.setText(""); return
        ok = bb.checksum_matches(self.info, text)
        self.sum_msg.setText("✓ The code matches. This file is genuine." if ok else "✗ The code does NOT match. Don't install this file.")
        self.sum_msg.setProperty("role", "ok" if ok else "warn")
        self.sum_msg.style().unpolish(self.sum_msg); self.sum_msg.style().polish(self.sum_msg)

    def update_btn(self) -> None:
        self.go.setEnabled(bool(self.info and self.info.runnable and self.trust.isChecked()))

    def install(self) -> None:
        if not self.info:
            return
        self.go.setEnabled(False); self.other.setEnabled(False); self.bar.show(); self.log.show(); self.result.setText("Installing… please wait.")

        def fin(rc: int) -> None:
            self.bar.hide(); self.other.setEnabled(True); self.go.setEnabled(True)
            self.result.setText("✓ All done!" if rc == 0 else "That didn't work. Details are shown above.")
            self.result.setProperty("role", "ok" if rc == 0 else "warn")
            self.result.style().unpolish(self.result); self.result.style().polish(self.result)
        run_commands([bb.run_command(self.info)], lambda l: self.log.appendPlainText(l), fin, self.r)
