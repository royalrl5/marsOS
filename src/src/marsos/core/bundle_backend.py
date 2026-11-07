"""Inspect and run .bundle installers (e.g. VMware) and .flatpak bundles safely."""
from __future__ import annotations
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from marsos import paths

KNOWN = {"vmware": "VMware software", "virtualbox": "VirtualBox", "nvidia": "NVIDIA driver", "jetbrains": "JetBrains"}


@dataclass
class BundleInfo:
    path: str
    name: str
    size: int
    kind: str                 # shell | flatpak | unknown
    product: str = ""
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sha256: str = ""

    @property
    def runnable(self) -> bool:
        return self.kind in ("shell", "flatpak")

    @property
    def kind_label(self) -> str:
        return {"shell": "Installer program", "flatpak": "App Store bundle"}.get(self.kind, "Unknown file")


def sha256_of(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def inspect(path: str | Path, with_hash: bool = True) -> BundleInfo:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    with open(p, "rb") as f:
        head = f.read(8192)
    if p.suffix in (".flatpak", ".flatpakref"):
        kind = "flatpak"
    elif head.startswith(b"#!"):
        kind = "shell"
    else:
        kind = "unknown"
    text = head.decode("utf-8", "replace")
    info = BundleInfo(str(p), p.name, p.stat().st_size, kind)
    low = text.lower() + p.name.lower()
    for key, label in KNOWN.items():
        if key in low:
            info.product = label
            break
    if kind == "shell":
        info.notes = [re.sub(r"^#+\s*", "", l).strip() for l in text.splitlines()[1:12]
                      if l.startswith("#") and len(l.strip("# ")) > 3][:3]
        info.warnings.append("This is an installer program. Only continue if you got it from a website you trust.")
    elif kind == "unknown":
        info.warnings.append("marsOS doesn't recognise this kind of file, so it can't install it.")
    if not os.access(p, os.R_OK):
        info.warnings.append("This file can't be read.")
    if with_hash:
        info.sha256 = sha256_of(p)
    return info


def checksum_matches(info: BundleInfo, expected: str) -> bool:
    e = re.sub(r"\s+", "", expected).lower()
    return bool(e) and e == (info.sha256 or sha256_of(info.path))


def run_command(info: BundleInfo) -> list[str]:
    if info.kind == "flatpak":
        return ["flatpak", "install", "--user", "-y", "--noninteractive", "--bundle", info.path]
    if info.kind == "shell":
        return [paths.helper_path(), "run-bundle", info.path]
    raise ValueError("unsupported bundle")
