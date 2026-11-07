"""marsOS installer backend. Runs as root: marsos-install-backend plan.json [--dry-run]

Copies the running live system to the chosen disk (offline, no downloads) and configures it.
Progress protocol on stdout:  PROGRESS <0-100> <label> | LOG <text> | DONE | ERROR <message>
"""
from __future__ import annotations
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

from marsos.core.helper import KEYD_ON
from marsos.core.runner import Runner

MIN_DISK_BYTES = 16 * 1024 ** 3
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,30}$")
HOST_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}$")
RESERVED_USERS = {"root", "live", "daemon", "bin", "sys", "nobody", "sddm"}
LIVE_FILES = [
    "etc/sddm.conf.d/10-live.conf", "etc/sudoers.d/10-live", "etc/polkit-1/rules.d/49-live.rules",
    "etc/xdg/autostart/org.marsos.LiveInstaller.desktop", "etc/mkinitcpio.conf.d/archiso.conf",
    "etc/tmpfiles.d/live-home.conf", "root/.automated_script.sh", "etc/motd",
    "etc/systemd/system/getty@tty1.service.d/autologin.conf", "etc/sysusers.d/live.conf",
]
RSYNC_EXCLUDES = ["/dev/*", "/proc/*", "/sys/*", "/run/*", "/tmp/*", "/mnt/*", "/media/*", "/lost+found",
                  "/home/live", "/var/cache/pacman/pkg/*", "/var/log/*", "/etc/machine-id", "/etc/pacman.d/gnupg"]
DISABLE_UNITS = ["systemd-networkd.service", "systemd-networkd-wait-online.service", "iwd.service",
                 "reflector.service", "pacman-init.service", "choose-mirror.service"]
PRESET = """ALL_config="/etc/mkinitcpio.conf"
ALL_kver="/boot/vmlinuz-linux-zen"
PRESETS=('default' 'fallback')
default_image="/boot/initramfs-linux-zen.img"
fallback_image="/boot/initramfs-linux-zen-fallback.img"
fallback_options="-S autodetect"
"""


class PlanError(ValueError):
    pass


@dataclass
class Plan:
    disk: str
    full_name: str
    username: str
    password: str
    hostname: str
    timezone: str = "UTC"
    locale: str = "en_US.UTF-8"
    keymap: str = "us"
    autologin: bool = True
    uefi: bool = True
    is_mac: bool = False
    apps: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "Plan":
        return cls(**json.loads(Path(path).read_text()))

    def dump(self, path: str | Path) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(asdict(self), f)


def validate(plan: Plan) -> None:
    if not re.fullmatch(r"/dev/[A-Za-z0-9/_-]+", plan.disk):
        raise PlanError("Invalid disk")
    if not USER_RE.match(plan.username) or plan.username in RESERVED_USERS:
        raise PlanError("Please choose a different account name (letters and numbers only)")
    if not HOST_RE.match(plan.hostname):
        raise PlanError("The computer name can only contain letters, numbers and dashes")
    if len(plan.password) < 4:
        raise PlanError("The password is too short")
    if not re.fullmatch(r"[A-Za-z0-9_+/-]+", plan.timezone) or ".." in plan.timezone:
        raise PlanError("Invalid time zone")
    if not re.fullmatch(r"[A-Za-z_]+(\.[A-Za-z0-9-]+)?", plan.locale) or not re.fullmatch(r"[a-z0-9_-]+", plan.keymap):
        raise PlanError("Invalid language or keyboard")
    if "\n" in plan.full_name or ":" in plan.full_name or "," in plan.full_name:
        raise PlanError("The name can't contain commas or colons")


def part_path(disk: str, n: int) -> str:
    return f"{disk}p{n}" if disk[-1].isdigit() else f"{disk}{n}"


class Installer:
    def __init__(self, plan: Plan, runner: Runner, target: Path = Path("/mnt"), emit=None, source: str = "/"):
        validate(plan)
        self.plan, self.r, self.source = plan, runner, source.rstrip("/") + "/"
        self.emit = emit or (lambda s: print(s, flush=True))
        self.target = Path(tempfile.mkdtemp(prefix="marsos-dry-")) if runner.dry_run else Path(target)
        self.esp = part_path(plan.disk, 1) if plan.uefi else None
        self.root = part_path(plan.disk, 2)

    # ----------------------------------------------------------- helpers
    def progress(self, pct: int, label: str) -> None:
        self.emit(f"PROGRESS {pct} {label}")

    def run(self, cmd, tolerate: bool = False, **kw):
        res = self.r.run(cmd, **kw)
        if not tolerate and not res.ok:
            raise RuntimeError(f"{' '.join(map(str, cmd))} failed: {res.stdout[-400:]}")
        return res

    def chroot(self, cmd, tolerate: bool = False, **kw):
        return self.run(["arch-chroot", str(self.target), *cmd], tolerate=tolerate, **kw)

    def path(self, rel: str) -> Path:
        return self.target / rel.lstrip("/")

    def write(self, rel: str, content: str, mode: int = 0o644) -> None:
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        p.chmod(mode)

    # ----------------------------------------------------------- steps
    def partition(self) -> None:
        self.progress(2, "Preparing the disk")
        d = self.plan.disk
        self.run(["wipefs", "-af", d])
        self.run(["sgdisk", "--zap-all", d], tolerate=True)
        if self.plan.uefi:
            self.run(["sgdisk", "-n", "1:0:+512M", "-t", "1:ef00", "-c", "1:EFI", "-n", "2:0:0", "-t", "2:8300", "-c", "2:marsOS", d])
        else:
            self.run(["sgdisk", "-n", "1:0:+2M", "-t", "1:ef02", "-c", "1:BIOS", "-n", "2:0:0", "-t", "2:8300", "-c", "2:marsOS", d])
        self.run(["partprobe", d], tolerate=True)
        self.run(["udevadm", "settle"], tolerate=True)

    def format_and_mount(self) -> None:
        self.progress(6, "Formatting")
        if self.esp:
            self.run(["mkfs.fat", "-F", "32", "-n", "MARSOS_EFI", self.esp])
        self.run(["mkfs.ext4", "-F", "-L", "marsOS", self.root])
        self.target.mkdir(parents=True, exist_ok=True)
        self.run(["mount", self.root, str(self.target)])
        if self.esp:
            self.path("boot/efi").mkdir(parents=True, exist_ok=True)
            self.run(["mount", self.esp, str(self.path("boot/efi"))])

    def copy_system(self) -> None:
        self.progress(11, "Copying marsOS (this takes a few minutes)")
        cmd = ["rsync", "-aAXH", "--numeric-ids", "--no-inc-recursive", "--info=progress2"]
        cmd += [f"--exclude={e}" for e in RSYNC_EXCLUDES] + [self.source, str(self.target) + "/"]

        def on_line(line: str) -> None:
            m = re.search(r"(\d+)%", line)
            if m:
                self.progress(11 + int(int(m.group(1)) * 0.64), "Copying marsOS (this takes a few minutes)")

        rc = self.r.stream(cmd, on_line)
        if rc not in (0, 23, 24):      # 23/24: some files vanished/unreadable – harmless for a live copy
            raise RuntimeError(f"Copying the system failed (rsync exit {rc})")
        for d in ("dev", "proc", "sys", "run", "tmp", "mnt", "media"):
            self.path(d).mkdir(exist_ok=True)
        self.path("tmp").chmod(0o1777)

    def configure(self) -> None:
        p = self.plan
        self.progress(76, "Setting up your account")
        for rel in LIVE_FILES:
            self.path(rel).unlink(missing_ok=True)
        # remove the live-only local package repo from pacman.conf
        pc = self.path("etc/pacman.conf")
        if pc.exists():
            pc.write_text(re.sub(r"\n\[marsos-local\][^\[]*", "\n", pc.read_text()))
        self.write("etc/mkinitcpio.d/linux-zen.preset", PRESET)
        self.run(["bash", "-c", f"genfstab -U {self.target} > {self.target}/etc/fstab"])
        self.write("etc/hostname", p.hostname + "\n")
        self.write("etc/hosts", f"127.0.0.1 localhost\n::1 localhost\n127.0.1.1 {p.hostname}\n")
        self.write("etc/locale.conf", f"LANG={p.locale}\n")
        self.write("etc/vconsole.conf", f"KEYMAP={p.keymap}\n")
        lg = self.path("etc/locale.gen")
        lines = lg.read_text().splitlines() if lg.exists() else []
        want = f"{p.locale} UTF-8"
        lines = [l for l in lines if l.strip("# ").strip() != want] + [want, "en_US.UTF-8 UTF-8"]
        lg.parent.mkdir(parents=True, exist_ok=True)
        lg.write_text("\n".join(dict.fromkeys(lines)) + "\n")
        self.write("etc/systemd/zram-generator.conf", "[zram0]\nzram-size = min(ram / 2, 4096)\ncompression-algorithm = zstd\n")
        self.write("etc/sudoers.d/10-wheel", "%wheel ALL=(ALL:ALL) ALL\n", 0o440)
        self.run(["ln", "-sf", f"/usr/share/zoneinfo/{p.timezone}", str(self.path("etc/localtime"))])
        self.chroot(["locale-gen"], tolerate=True)
        self.chroot(["hwclock", "--systohc"], tolerate=True)
        self.chroot(["userdel", "-f", "live"], tolerate=True)
        self.chroot(["useradd", "-m", "-G", "wheel,audio,video,storage,lp,network", "-c", p.full_name,
                     "-s", "/bin/bash", p.username])
        self.chroot(["chpasswd"], input=f"{p.username}:{p.password}\n")
        self.chroot(["passwd", "-l", "root"], tolerate=True)
        kx = f"[Layout]\nLayoutList={p.keymap}\nUse=true\n"
        self.write(f"home/{p.username}/.config/kxkbrc", kx)
        if p.is_mac:
            self.write("etc/keyd/default.conf", KEYD_ON)
            self.write(f"home/{p.username}/.config/marsos/prefs.json", json.dumps({"command_as_ctrl": True}))
        self.chroot(["chown", "-R", f"{p.username}:{p.username}", f"/home/{p.username}"], tolerate=True)
        if p.autologin:
            self.write("etc/sddm.conf.d/20-marsos-autologin.conf", f"[Autologin]\nUser={p.username}\nSession=plasma\n")
        if p.apps:
            self.write("var/lib/marsos/pending-apps.json",
                       json.dumps({"user": p.username, "apps": p.apps}), 0o600)
        self.progress(82, "Preparing to start up")
        self.chroot(["pacman-key", "--init"], tolerate=True)
        self.chroot(["pacman-key", "--populate", "archlinux"], tolerate=True)
        self.install_kernel_files()
        self.chroot(["mkinitcpio", "-P"])
        for unit in DISABLE_UNITS:
            self.chroot(["systemctl", "disable", unit], tolerate=True)
        units = ["NetworkManager.service", "sddm.service", "bluetooth.service", "fstrim.timer",
                 "cups.service", "marsos-firstboot.service"]
        if p.is_mac:
            units += ["keyd.service", "mbpfan.service", "thermald.service"]
        for unit in units:
            self.chroot(["systemctl", "enable", unit], tolerate=True)

    def install_kernel_files(self) -> None:
        mods = self.path("usr/lib/modules")
        if mods.is_dir():
            for d in sorted(mods.iterdir()):
                pb, vm = d / "pkgbase", d / "vmlinuz"
                if pb.exists() and pb.read_text().strip() == "linux-zen" and vm.exists():
                    self.run(["install", "-Dm644", str(vm), str(self.path("boot/vmlinuz-linux-zen"))])
                    return
        if not self.r.dry_run:
            raise RuntimeError("Couldn't find the system's kernel")

    def bootloader(self) -> None:
        self.progress(90, "Installing the startup files")
        gd = self.path("etc/default/grub")
        text = gd.read_text() if gd.exists() else ""
        settings = {"GRUB_TIMEOUT": "2", "GRUB_TIMEOUT_STYLE": "hidden", "GRUB_DISTRIBUTOR": '"marsOS"',
                    "GRUB_CMDLINE_LINUX_DEFAULT": '"quiet loglevel=3"', "GRUB_DISABLE_OS_PROBER": "true"}
        for k, v in settings.items():
            if re.search(rf"^#?{k}=", text, re.M):
                text = re.sub(rf"^#?{k}=.*$", f"{k}={v}", text, flags=re.M)
            else:
                text += f"\n{k}={v}"
        gd.parent.mkdir(parents=True, exist_ok=True)
        gd.write_text(text.strip() + "\n")
        if self.plan.uefi:   # --removable also works on Macs, which ignore normal EFI boot entries
            self.chroot(["grub-install", "--target=x86_64-efi", "--efi-directory=/boot/efi",
                         "--bootloader-id=marsOS", "--removable"])
        else:
            self.chroot(["grub-install", "--target=i386-pc", self.plan.disk])
        self.chroot(["grub-mkconfig", "-o", "/boot/grub/grub.cfg"])

    def finish(self) -> None:
        self.progress(98, "Finishing")
        self.run(["sync"])
        self.run(["umount", "-R", str(self.target)], tolerate=True)
        self.progress(100, "Done")

    def run_all(self) -> None:
        for step in (self.partition, self.format_and_mount, self.copy_system, self.configure, self.bootloader, self.finish):
            step()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]
    if len(argv) != 1:
        print("usage: marsos-install-backend plan.json [--dry-run]", file=sys.stderr)
        return 2
    try:
        if os.geteuid() != 0 and not dry:
            raise RuntimeError("The installer needs administrator rights")
        plan = Plan.load(argv[0])
        os.unlink(argv[0]) if not dry else None      # the plan holds the password
        Installer(plan, Runner(dry_run=dry)).run_all()
    except Exception as e:     # noqa: BLE001 - reported to the GUI
        print(f"ERROR {e}", flush=True)
        return 1
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
