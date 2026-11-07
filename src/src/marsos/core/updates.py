"""Software updates, explained simply."""
from __future__ import annotations
from dataclasses import dataclass, field

from marsos import paths
from marsos.core.runner import Runner

REBOOT_PKGS = ("linux", "systemd", "mesa", "sddm", "plasma-workspace", "kwin")


@dataclass
class UpdateInfo:
    system: list[str] = field(default_factory=list)
    apps: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.system) + len(self.apps)

    @property
    def needs_restart(self) -> bool:
        return any(p.split()[0].startswith(REBOOT_PKGS) for p in self.system)


def check(r: Runner) -> UpdateInfo:
    info = UpdateInfo()
    res = r.run(["checkupdates"], timeout=120)       # rc 2 = nothing to do
    if res.returncode == 0:
        info.system = [l for l in res.stdout.splitlines() if l.strip()]
    res = r.run(["flatpak", "remote-ls", "--updates", "--columns=application"], timeout=60)
    if res.ok:
        info.apps = [l.strip() for l in res.stdout.splitlines() if l.strip()]
    return info


def apply_commands() -> list[list[str]]:
    return [[paths.helper_path(), "system-update"],
            ["flatpak", "update", "--user", "-y", "--noninteractive"]]
