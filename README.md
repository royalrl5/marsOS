# marsOS 1.0 "Golden Gate"

A Mac-like Linux for a 2011 MacBook (and anything newer): Arch Linux + KDE Plasma, with its own
App Store, Spotlight, Launchpad, Control Center, installer and `.bundle` runner. Written in Python (PySide6/Qt 6).

## What you get
| App | Command | What it does |
|---|---|---|
| App Store | `marsos-store` | Curated apps + live Flathub and AUR search. A plain-English explanation under every app. No terminal. |
| Installer | `marsos-installer` | 7-step wizard (disk, account, apps…). Offers Zen/Firefox/Chromium/Brave/LibreWolf/Vivaldi, Waydroid, VirtualBox. |
| Bundle Runner | `marsos-bundle` | Drop a `.bundle` file: it explains what it is, shows its fingerprint, optional checksum check, then installs. |
| Spotlight | `marsos-spotlight` | **Ctrl+Space** (⌘Space on a Mac): apps, files, calculator, settings, "restart", App Store, web. |
| Launchpad | `marsos-launchpad` | Full-screen app grid with search. |
| Control Center | `marsos-control-center` | Wi-Fi, Bluetooth, dark mode, brightness, volume. |
| System Settings | `marsos-settings` | Wi-Fi, appearance, **text size**, sound, ⌘-key shortcuts, trackpad, time zone, password. |
| Software Update | `marsos-updater` | One button; says if a restart is needed. |
| Welcome | `marsos-welcome` | First-login tour (Wi-Fi, text size, tips, progress of the apps chosen during install). |

Made for a grandmother: no terminal anywhere, large-text option, automatic login, passwords asked in normal windows,
installer refuses the wrong disk, effects tuned down automatically on old hardware.

## Build the ISO (needs Arch Linux)
```bash
git clone <this repo> && cd marsos
./scripts/build-iso.sh          # ~20-40 min the first time; output in out/marsos-*.iso
```
Use an Arch machine, an Arch VM, or `docker run --privileged -it archlinux`, as a **normal user with sudo**.

## Test in a VM first (do this before touching the MacBook)
**QEMU/KVM (recommended):** `./scripts/run-vm.sh out/marsos-*.iso` (add `--bios` to test legacy boot, `--reset` to wipe the VM disk).

**VirtualBox:** New VM → Linux/Arch Linux (64-bit), 4 GB RAM, 2 CPUs, 40 GB disk. Settings → System → **Enable EFI**;
Display → Graphics controller **VMSVGA**, 128 MB, 3D acceleration on. Attach the ISO and start.

In the live session the installer opens by itself. Choose the virtual disk, create an account, install, restart.
Safe preview without installing anything: `marsos-installer --demo`.

## Put it on the MacBook
1. Write the ISO to a USB stick (8 GB+): **balenaEtcher**, or `sudo dd if=marsos.iso of=/dev/sdX bs=4M status=progress oflag=sync`.
2. Plug it in, hold **Option (⌥)** while powering on, choose **EFI Boot**.
3. Run the installer. It erases the chosen disk (it will not let you pick the USB stick you booted from).
4. After install, if it doesn't start: hold Option and pick the internal disk's "EFI Boot".
2011 specifics handled for you: Broadcom Wi-Fi (`broadcom-wl-dkms`, conflicting drivers blacklisted), Apple keyboard
media-key behaviour, fan control (`mbpfan`), thermal management, zram swap for 4 GB RAM, "Balanced" visual effects,
⌘ key acting as Ctrl (⌘C/⌘V/⌘Q/⌘Space) via keyd, natural scrolling and tap-to-click.

## Develop
```bash
python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
pytest                                   # 60 tests, headless (QT_QPA_PLATFORM=offscreen)
python scripts/screenshots.py /tmp/shots # render every app to PNG
python -m marsos.apps.store.main         # run any app directly
```
Layout: `src/marsos/core` (logic, no GUI), `src/marsos/ui` (theme, widgets, animations), `src/marsos/apps/*` (one package per app),
`system/` (files installed to `/`), `iso/` (live-session files + package lists), `packaging/PKGBUILD`, `scripts/`.

## Security design
Apps never run as root. Admin actions go through one audited program, `marsos-helper`, via polkit (`pkexec`), which accepts a
fixed set of commands and validates every argument (no shell strings). The installer runs as root only in the live session,
reads the account password from a 0600 plan file that it deletes immediately, and never puts it on a command line.

## Known limitations (please read)
* **Not tested on real hardware or a real ISO build.** Unit/UI tests and the installer's dry-run pass; the ISO build, boot
  and Plasma layout need a first run on Arch. Expect to fix small things (AUR package names, boot-menu patching).
* **"macOS 27 Golden Gate" look** is an original, similar design (WhiteSur theme, Inter font, original wallpapers), not Apple's.
  Apple's fonts, icons and wallpapers are copyrighted and are not included.
* **Rolling release:** Arch updates can occasionally break things. Updates are user-triggered, not automatic. Consider
  Btrfs + snapshots before relying on it for someone non-technical.
* **marsos-desktop updates** need a package repo you host; until then update the apps by rebuilding/reinstalling.
* 15"/17" MacBook Pros from 2011 have a notorious GPU defect; if the screen glitches, that is the hardware, not marsOS.
* Waydroid and VirtualBox are offered but not recommended on a 2011 Mac.
* Plasma 6.8+ is Wayland-only; the dock/menu-bar layout script uses Plasma's scripting API and may need tweaks per Plasma version.
