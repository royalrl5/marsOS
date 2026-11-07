"""List disks that marsOS may be installed onto."""
from __future__ import annotations
import json
from dataclasses import dataclass

from marsos.core.installer_backend import MIN_DISK_BYTES
from marsos.core.runner import Runner


@dataclass
class Disk:
    path: str
    model: str
    size: int
    removable: bool = False
    rotational: bool = False
    mounted: bool = False
    live_medium: bool = False

    @property
    def size_gb(self) -> float:
        return self.size / 1000 ** 3

    @property
    def label(self) -> str:
        kind = "Hard disk" if self.rotational else "Solid-state drive"
        if self.removable:
            kind = "External drive"
        return f"{self.model or kind}"

    def problem(self) -> str | None:
        if self.live_medium:
            return "This is the drive you started the installer from"
        if self.size < MIN_DISK_BYTES:
            return "Too small (needs at least 16 GB)"
        return None


def _mounted(node: dict) -> bool:
    mps = node.get("mountpoints") or [node.get("mountpoint")]
    if any(m for m in mps if m):
        return True
    return any(_mounted(c) for c in node.get("children", []))


def parse_lsblk(text: str) -> list[Disk]:
    out = []
    for n in json.loads(text).get("blockdevices", []):
        if n.get("type") != "disk" or n.get("name", "").startswith(("zram", "loop", "sr", "ram")):
            continue
        out.append(Disk(path=n.get("path") or "/dev/" + n["name"], model=(n.get("model") or "").strip(),
                        size=int(n.get("size") or 0), removable=str(n.get("rm")) in ("1", "True", "true"),
                        rotational=str(n.get("rota")) in ("1", "True", "true"), mounted=_mounted(n)))
    return out


def list_disks(r: Runner) -> list[Disk]:
    res = r.run(["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,MODEL,RM,ROTA,TYPE,MOUNTPOINTS"])
    disks = parse_lsblk(res.stdout) if res.ok and res.stdout.strip() else []
    src = r.run(["findmnt", "-no", "SOURCE", "/run/archiso/bootmnt"]).stdout.strip()
    if src:
        parent = r.run(["lsblk", "-no", "PKNAME", src]).stdout.strip().splitlines()
        for d in disks:
            if parent and d.path == "/dev/" + parent[0]:
                d.live_medium = True
    return disks
