import json
from pathlib import Path

import pytest

from marsos.core import (bundle_backend, catalog, disks, hardware, helper, installer_backend as ib,
                         network, prefs, search, system, updates, backends)
from marsos.core.desktop_entries import parse_entry, load_all
from marsos.core.runner import Runner


# ---------------------------------------------------------------- hardware
def test_detects_2011_macbook(tmp_path):
    dmi = tmp_path / "dmi"; dmi.mkdir()
    (dmi / "sys_vendor").write_text("Apple Inc.\n"); (dmi / "product_name").write_text("MacBookPro8,1\n")
    mem = tmp_path / "meminfo"; mem.write_text("MemTotal:        4045000 kB\n")
    cpu = tmp_path / "cpuinfo"; cpu.write_text("model name\t: Intel(R) Core(TM) i5-2415M CPU\n")
    hw = hardware.detect(dmi, mem, cpu, tmp_path / "nodrm")
    assert hw.is_mac and hw.mac_year == 2011 and "13-inch" in hw.friendly
    assert hw.ram_gb == 3.9
    assert hardware.recommended_effects(hw) == "balanced"


def test_effects_profiles():
    assert hardware.recommended_effects(hardware.HardwareInfo("X", "Y", 2000)) == "light"
    assert hardware.recommended_effects(hardware.HardwareInfo("X", "Y", 16000)) == "full"


# ---------------------------------------------------------------- prefs / catalog
def test_prefs_roundtrip():
    p = prefs.Prefs(text_scale=1.5, appearance="dark"); p.save()
    q = prefs.Prefs.load()
    assert q.text_scale == 1.5 and q.appearance == "dark"
    assert prefs.Prefs(reduce_motion=True).anim_factor == 0


def test_catalog_complete():
    apps = catalog.load()
    ids = [a.id for a in apps]
    assert len(ids) == len(set(ids))
    for a in apps:
        assert a.description and a.summary, a.id          # explanation under every app
        assert a.source in ("flatpak", "pacman", "aur")
    assert {"zen", "waydroid", "virtualbox"} <= {a.id for a in catalog.installer_options()}
    assert catalog.by_id("zen").source_label == "App Store"


def test_install_commands_never_use_shell():
    for a in catalog.load():
        for cmd in backends.install_commands(a):
            assert isinstance(cmd, list) and all(isinstance(x, str) for x in cmd)
    assert backends.install_commands(catalog.by_id("virtualbox"))[0][1] == "pacman-install"


# ---------------------------------------------------------------- search
def test_calculator():
    assert search.calculate("2*(3+4)") == "14"
    assert search.calculate("15% of 80") == "12"
    assert search.calculate("10/4") == "2.5"
    assert search.calculate("sqrt(16)") == "4"
    assert search.calculate("hello") is None
    assert search.calculate("2024") is None
    assert search.calculate("__import__('os')") is None
    assert search.calculate("9**9999") is None


def _entries(tmp_path):
    d = tmp_path / "apps"; d.mkdir()
    (d / "org.mozilla.firefox.desktop").write_text("[Desktop Entry]\nType=Application\nName=Firefox\nGenericName=Web Browser\nExec=firefox\nIcon=firefox\n")
    (d / "hidden.desktop").write_text("[Desktop Entry]\nType=Application\nName=Hidden\nNoDisplay=true\nExec=x\n")
    (d / "notes.desktop").write_text("[Desktop Entry]\nType=Application\nName=Notes\nKeywords=memo;write;\nExec=notes\n")
    return load_all([d])


def test_desktop_entries(tmp_path):
    e = _entries(tmp_path)
    assert [x.name for x in e] == ["Firefox", "Notes"]


def test_spotlight_ranking(tmp_path):
    eng = search.SearchEngine(_entries(tmp_path))
    r = eng.search("fire")
    assert r[0].kind == "app" and r[0].title == "Firefox"
    assert r[-1].kind == "web"
    assert eng.search("wifi")[0].kind == "settings"
    assert eng.search("restart")[0].kind == "action"
    assert eng.search("3+4")[0].title == "7"
    assert eng.search("   ") == []
    assert any(x.kind == "store" and "Zen" in x.title for x in eng.search("zen"))


def test_file_index(tmp_path):
    root = tmp_path / "Documents"; (root / "sub").mkdir(parents=True)
    (root / "sub" / "Recipe for apple pie.txt").write_text("x")
    idx = search.FileIndex([root]); idx.build()
    assert idx.search("apple")[0].endswith("Recipe for apple pie.txt")


# ---------------------------------------------------------------- network
def test_wifi_parsing():
    text = "*:Home\\:5G:80:WPA2\n :Cafe:40:--\n :Home\\:5G:30:WPA2\n ::10:WPA2\n"
    nets = network.parse_wifi_list(text)
    assert [n.ssid for n in nets] == ["Home:5G", "Cafe"]
    assert nets[0].in_use and nets[0].secured and not nets[1].secured and nets[0].bars == 4


def test_device_parsers():
    assert network.parse_volume("Volume: 0.45") == 45
    assert network.parse_brightness("intel_backlight,backlight,2000,50%,4000") == 50


def test_wifi_password_not_in_argv():
    r = Runner(dry_run=True)
    network.connect(r, "Home", "secret123")
    assert all("secret123" not in " ".join(c) for c in r.history)


# ---------------------------------------------------------------- updates / bundles
def test_update_restart_detection():
    assert updates.UpdateInfo(system=["linux-zen 6.1-1 -> 6.2-1"]).needs_restart
    assert not updates.UpdateInfo(system=["vlc 3 -> 4"]).needs_restart


def test_bundle_inspect(tmp_path):
    f = tmp_path / "VMware-Workstation-17.bundle"
    f.write_bytes(b"#!/bin/sh\n# VMware installer\n# Copyright VMware Inc\n" + b"x" * 200)
    info = bundle_backend.inspect(f)
    assert info.kind == "shell" and info.product == "VMware software" and info.runnable
    assert bundle_backend.checksum_matches(info, info.sha256.upper())
    assert not bundle_backend.checksum_matches(info, "abc")
    assert bundle_backend.run_command(info)[1] == "run-bundle"
    g = tmp_path / "mystery.bundle"; g.write_bytes(b"\x7fELF" + b"0" * 100)
    assert not bundle_backend.inspect(g).runnable
    with pytest.raises(FileNotFoundError):
        bundle_backend.inspect(tmp_path / "nope.bundle")


# ---------------------------------------------------------------- helper
@pytest.mark.parametrize("bad", ["--help", "a b", "x;rm", "$(id)", "../x", "", "-Syu"])
def test_helper_rejects_bad_packages(bad):
    r = Runner(dry_run=True)
    assert helper.main(["pacman-install", bad], r) == 2
    assert r.history == []


def test_helper_commands():
    r = Runner(dry_run=True)
    assert helper.main(["pacman-install", "virtualbox", "virtualbox-host-dkms"], r) == 0
    assert r.history[0][:4] == ["pacman", "-S", "--needed", "--noconfirm"]
    assert helper.main(["bogus"], Runner(dry_run=True)) == 2
    assert helper.main(["set-timezone", "../../etc/passwd"], Runner(dry_run=True)) == 2
    assert helper.main(["keyd-set", "maybe"], Runner(dry_run=True)) == 2


def test_process_pending(tmp_path):
    pend, st = tmp_path / "p.json", tmp_path / "s.json"
    pend.write_text(json.dumps({"user": "gran", "apps": [
        {"id": "zen", "name": "Zen", "source": "flatpak", "pkg": "app.zen_browser.zen"},
        {"id": "virtualbox", "name": "VirtualBox", "source": "pacman", "pkg": "virtualbox"}]}))
    r = Runner(dry_run=True)
    helper.process_pending(r, pend, st)
    s = json.loads(st.read_text())
    assert s["finished"] and s["done"] == 2 and not s["errors"]
    assert ["usermod", "-aG", "vboxusers", "gran"] in r.history
    assert not pend.exists()


# ---------------------------------------------------------------- installer
def _plan(**kw):
    base = dict(disk="/dev/sda", full_name="Grandma Rose", username="rose", password="hunter22", hostname="roses-macbook")
    base.update(kw)
    return ib.Plan(**base)


def test_partition_names():
    assert ib.part_path("/dev/sda", 2) == "/dev/sda2"
    assert ib.part_path("/dev/nvme0n1", 2) == "/dev/nvme0n1p2"
    assert ib.part_path("/dev/mmcblk0", 1) == "/dev/mmcblk0p1"


@pytest.mark.parametrize("kw", [dict(username="root"), dict(username="Bad Name"), dict(password="12"),
                                dict(hostname="-x"), dict(disk="sda"), dict(timezone="../x"), dict(full_name="a:b")])
def test_plan_validation(kw):
    with pytest.raises(ib.PlanError):
        ib.validate(_plan(**kw))


def test_dry_run_uefi_mac_install(tmp_path):
    out = []
    r = Runner(dry_run=True)
    inst = ib.Installer(_plan(is_mac=True, uefi=True, apps=[{"id": "zen", "name": "Zen", "source": "flatpak", "pkg": "x"}]),
                        r, emit=out.append)
    # create a fake kernel in the (temporary) target so kernel installation is exercised
    k = inst.path("usr/lib/modules/6.99-zen1-1-zen"); k.mkdir(parents=True)
    (k / "pkgbase").write_text("linux-zen\n"); (k / "vmlinuz").write_text("k")
    inst.run_all()
    cmds = r.commands()
    assert any(c.startswith("sgdisk -n 1:0:+512M -t 1:ef00") for c in cmds)
    assert any(c.startswith("mkfs.fat -F 32") and c.endswith("/dev/sda1") for c in cmds)
    assert any(c.startswith("mkfs.ext4") and c.endswith("/dev/sda2") for c in cmds)
    assert any(c.startswith("rsync -aAXH") for c in cmds)
    assert any("grub-install --target=x86_64-efi" in c and "--removable" in c for c in cmds)
    assert any("useradd -m" in c and c.endswith("rose") for c in cmds)
    assert not any("hunter22" in c for c in cmds)                     # password never on a command line
    assert any("install -Dm644" in c and "vmlinuz-linux-zen" in c for c in cmds)
    assert out[0].startswith("PROGRESS") and out[-1] == "PROGRESS 100 Done"
    pcts = [int(l.split()[1]) for l in out]
    assert pcts == sorted(pcts)
    assert "[zram0]" in inst.path("etc/systemd/zram-generator.conf").read_text()
    assert "leftmeta = leftcontrol" in inst.path("etc/keyd/default.conf").read_text()
    assert "Autologin" in inst.path("etc/sddm.conf.d/20-marsos-autologin.conf").read_text()
    assert json.loads(inst.path("var/lib/marsos/pending-apps.json").read_text())["user"] == "rose"
    assert inst.path("etc/hostname").read_text() == "roses-macbook\n"


def test_dry_run_bios_install():
    r = Runner(dry_run=True)
    inst = ib.Installer(_plan(uefi=False, disk="/dev/nvme0n1"), r, emit=lambda s: None)
    inst.partition(); inst.bootloader()
    cmds = r.commands()
    assert any("-t 1:ef02" in c for c in cmds)
    assert any("grub-install --target=i386-pc /dev/nvme0n1" in c for c in cmds)
    assert inst.root == "/dev/nvme0n1p2"


def test_dry_run_never_touches_real_target():
    inst = ib.Installer(_plan(), Runner(dry_run=True), target=Path("/mnt"), emit=lambda s: None)
    assert str(inst.target) != "/mnt"


def test_plan_file_is_private(tmp_path):
    f = tmp_path / "plan.json"; _plan().dump(f)
    assert oct(f.stat().st_mode)[-3:] == "600"
    assert ib.Plan.load(f).username == "rose"


# ---------------------------------------------------------------- disks / system
LSBLK = json.dumps({"blockdevices": [
    {"name": "sda", "path": "/dev/sda", "size": 250059350016, "model": "APPLE HDD ", "rm": False, "rota": True, "type": "disk",
     "mountpoints": [None], "children": [{"name": "sda1", "type": "part", "mountpoints": [None]}]},
    {"name": "sdb", "path": "/dev/sdb", "size": 8000000000, "model": "USB Stick", "rm": True, "rota": False, "type": "disk", "mountpoints": [None]},
    {"name": "zram0", "path": "/dev/zram0", "size": 2000000000, "type": "disk", "mountpoints": ["[SWAP]"]},
    {"name": "sr0", "type": "rom", "size": 1}]})


def test_disks():
    ds = disks.parse_lsblk(LSBLK)
    assert [d.path for d in ds] == ["/dev/sda", "/dev/sdb"]
    assert ds[0].problem() is None and ds[0].label == "APPLE HDD"
    assert "16 GB" in ds[1].problem()
    ds[0].live_medium = True
    assert "started the installer" in ds[0].problem()


def test_apply_effects_profiles():
    r = Runner(dry_run=True)
    system.apply_effects(r, "balanced")
    c = r.commands()
    assert any("wobblywindowsEnabled false" in x for x in c) and any("magiclampEnabled true" in x for x in c)
    r2 = Runner(dry_run=True); system.apply_effects(r2, "full", reduce_motion=True)
    assert any("AnimationDurationFactor 0.0" in x for x in r2.commands())
    assert any("magiclampEnabled false" in x for x in r2.commands())
