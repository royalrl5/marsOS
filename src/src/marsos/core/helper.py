"""marsos-helper: the ONLY thing the GUI apps run as root (through pkexec).

Every sub-command validates its input; nothing here accepts shell strings.
"""
from __future__ import annotations
import json
import os
import pwd
import re
import sys
from pathlib import Path

from marsos import paths
from marsos.core.runner import Runner

PKG_RE = re.compile(r"^[a-z0-9@][a-z0-9@._+-]{0,80}$")
TZ_ROOT = Path("/usr/share/zoneinfo")
KEYD_CONF = Path("/etc/keyd/default.conf")
KEYD_ON = """# Written by marsOS: Command key acts like Ctrl, so Cmd+C / Cmd+V / Cmd+Q work like on a Mac
[ids]
*

[main]
leftmeta = leftcontrol
rightmeta = rightcontrol
leftcontrol = leftmeta
"""
KEYD_OFF = "# Written by marsOS: standard keyboard layout\n[ids]\n*\n"


class HelperError(Exception):
    pass


def _pkgs(args: list[str]) -> list[str]:
    if not args:
        raise HelperError("no packages given")
    for a in args:
        if not PKG_RE.match(a):
            raise HelperError(f"invalid package name: {a!r}")
    return args


def _caller_user() -> str:
    uid = os.environ.get("PKEXEC_UID")
    if not uid:
        raise HelperError("must be run through pkexec")
    return pwd.getpwuid(int(uid)).pw_name


def run_bundle(r: Runner, path: str) -> int:
    p = Path(path).resolve()
    if not p.is_file():
        raise HelperError("bundle not found")
    if p.stat().st_size < 64:
        raise HelperError("file too small to be an installer")
    env = {"TERM": "dumb", "PATH": "/usr/local/sbin:/usr/local/bin:/usr/bin"}
    return r.stream(["sh", str(p)], lambda l: print(l, flush=True), env=env)


def process_pending(r: Runner, pending: Path | None = None, status: Path | None = None) -> int:
    pending = pending or paths.pending_file()
    status = status or paths.pending_status_file()
    if not pending.exists():
        return 0
    data = json.loads(pending.read_text())
    user, apps = data.get("user", ""), data.get("apps", [])
    st = {"total": len(apps), "done": 0, "current": "", "finished": False, "errors": []}

    def save():
        status.parent.mkdir(parents=True, exist_ok=True)
        status.write_text(json.dumps(st))

    sudoers = Path("/etc/sudoers.d/99-marsos-firstboot")
    try:
        if any(a["source"] == "aur" for a in apps) and user and not r.dry_run:
            sudoers.write_text(f"{user} ALL=(ALL) NOPASSWD: ALL\n"); sudoers.chmod(0o440)
        r.run(["flatpak", "remote-add", "--system", "--if-not-exists", "flathub",
               "https://dl.flathub.org/repo/flathub.flatpakrepo"])
        for a in apps:
            st["current"] = a["name"]; save()
            pk = _pkgs(a["pkg"].split())
            if a["source"] == "flatpak":
                cmd = ["flatpak", "install", "--system", "-y", "--noninteractive", "flathub", *pk]
            elif a["source"] == "pacman":
                cmd = ["pacman", "-S", "--needed", "--noconfirm", *pk]
            else:
                cmd = ["runuser", "-u", user, "--", "paru", "-S", "--needed", "--noconfirm", "--skipreview", *pk]
            res = r.run(cmd, timeout=3600)
            if not res.ok:
                st["errors"].append(a["name"])
            elif a["id"] == "virtualbox" and user:
                r.run(["usermod", "-aG", "vboxusers", user])
            elif a["id"] == "waydroid":
                r.run(["systemctl", "enable", "waydroid-container.service"])
            st["done"] += 1; save()
    finally:
        if sudoers.exists():
            sudoers.unlink()
        st["finished"], st["current"] = True, ""; save()
    if not st["errors"]:
        pending.unlink(missing_ok=True)
    return 0


def main(argv: list[str] | None = None, runner: Runner | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    r = runner or Runner()
    try:
        if os.geteuid() != 0 and not r.dry_run:
            raise HelperError("marsos-helper must run as root")
        if not argv:
            raise HelperError("usage: marsos-helper <command> [args]")
        cmd, args = argv[0], argv[1:]
        if cmd == "pacman-install":
            return r.stream(["pacman", "-S", "--needed", "--noconfirm", *_pkgs(args)], lambda l: print(l, flush=True))
        if cmd == "pacman-remove":
            return r.stream(["pacman", "-Rns", "--noconfirm", *_pkgs(args)], lambda l: print(l, flush=True))
        if cmd == "system-update":
            return r.stream(["pacman", "-Syu", "--noconfirm"], lambda l: print(l, flush=True))
        if cmd == "run-bundle":
            if len(args) != 1:
                raise HelperError("run-bundle needs one path")
            return run_bundle(r, args[0])
        if cmd == "keyd-set":
            if args not in (["on"], ["off"]):
                raise HelperError("keyd-set on|off")
            if not r.dry_run:
                KEYD_CONF.parent.mkdir(parents=True, exist_ok=True)
                KEYD_CONF.write_text(KEYD_ON if args[0] == "on" else KEYD_OFF)
            r.run(["systemctl", "enable", "--now", "keyd"])
            r.run(["keyd", "reload"])
            return 0
        if cmd == "set-timezone":
            if len(args) != 1 or ".." in args[0] or not re.fullmatch(r"[A-Za-z0-9_+/-]+", args[0]) \
                    or not ((TZ_ROOT / args[0]).is_file() or r.dry_run):
                raise HelperError("invalid timezone")
            return r.run(["timedatectl", "set-timezone", args[0]]).returncode
        if cmd == "set-password":
            pw = sys.stdin.readline().rstrip("\n")
            if len(pw) < 4:
                raise HelperError("password too short")
            return r.run(["chpasswd"], input=f"{_caller_user()}:{pw}\n").returncode
        if cmd == "process-pending":
            return process_pending(r)
        raise HelperError(f"unknown command: {cmd}")
    except HelperError as e:
        print(f"marsos-helper: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
