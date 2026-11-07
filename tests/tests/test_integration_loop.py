"""Real partition/format/mount/copy on a loop device. Skipped unless root with gdisk, rsync and loop devices."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from marsos.core import installer_backend as ib
from marsos.core.runner import Runner

pytestmark = pytest.mark.skipif(
    os.geteuid() != 0 or not all(shutil.which(t) for t in ("sgdisk", "mkfs.ext4", "rsync", "losetup", "mount")),
    reason="needs root and disk tools")


def test_real_bios_layout_copy(tmp_path, monkeypatch):
    monkeypatch.delenv("MARSOS_DRY_RUN", raising=False)
    img = tmp_path / "disk.img"; subprocess.run(["truncate", "-s", "1G", str(img)], check=True)
    r = subprocess.run(["losetup", "-f", "--show", "-P", str(img)], capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("no loop devices")
    dev = r.stdout.strip()
    src = tmp_path / "live"; (src / "etc").mkdir(parents=True); (src / "etc/os-release").write_text("NAME=marsOS\n")
    (src / "home/live").mkdir(parents=True); (src / "home/live/secret").write_text("x")
    target = tmp_path / "target"; out = []
    try:
        plan = ib.Plan(disk=dev, full_name="Rose", username="rose", password="pw1234", hostname="rose-mac", uefi=False)
        inst = ib.Installer(plan, Runner(dry_run=False), target=target, emit=out.append, source=str(src))
        inst.partition(); inst.format_and_mount(); inst.copy_system()
        layout = subprocess.run(["sgdisk", "-p", dev], capture_output=True, text=True).stdout
        assert "EF02" in layout and "8300" in layout
        assert (target / "etc/os-release").read_text() == "NAME=marsOS\n"
        assert not (target / "home/live").exists(), "live home must not be copied"
        assert (target / "tmp").stat().st_mode & 0o1777 == 0o1777
        assert any(l.startswith("PROGRESS 75") for l in out)
    finally:
        subprocess.run(["umount", "-R", str(target)], capture_output=True)
        subprocess.run(["losetup", "-d", dev], capture_output=True)
