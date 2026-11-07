#!/usr/bin/env bash
# Build the marsOS installation ISO.  Run on Arch Linux (or in an Arch container with --privileged)
# as a NORMAL user with sudo.  Output: out/marsos-*.iso
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
WORK="$ROOT/work"; OUT="$ROOT/out"; REPO="$WORK/repo"; PROFILE="$WORK/profile"
[ "$(id -u)" -ne 0 ] || { echo "Run as a normal user (makepkg refuses root)."; exit 1; }

sudo pacman -S --needed --noconfirm archiso base-devel git python-build python-installer python-setuptools python-wheel pyside6
rm -rf "$WORK"; mkdir -p "$REPO" "$OUT"
cp -r /usr/share/archiso/configs/releng "$PROFILE"

echo "==> Wallpapers"; [ -f src/marsos/data/wallpapers/golden-gate-dawn.jpg ] || QT_QPA_PLATFORM=offscreen python scripts/make_wallpapers.py

echo "==> Building marsos-desktop"
( cd packaging && makepkg -sf --noconfirm --nodeps PKGDEST="$REPO" )

echo "==> Building AUR packages"
while read -r pkg; do
  case "$pkg" in ''|\#*) continue;; esac
  git clone --depth 1 "https://aur.archlinux.org/$pkg.git" "$WORK/aur/$pkg"
  ( cd "$WORK/aur/$pkg" && makepkg -sfc --noconfirm --needed PKGDEST="$REPO" )
done < iso/aur-packages.txt
repo-add "$REPO/marsos-local.db.tar.gz" "$REPO"/*.pkg.tar.zst

echo "==> Preparing profile"
cat >> "$PROFILE/pacman.conf" <<EOT

[marsos-local]
SigLevel = Optional TrustAll
Server = file://$REPO
EOT
# swap the stock kernel/driver for ours
sed -i -E '/^(linux|linux-headers|broadcom-wl|memtest86\+?|edk2-shell)$/d' "$PROFILE/packages.x86_64" || true
grep -vE '^(#|$)' iso/packages.txt >> "$PROFILE/packages.x86_64"
{ grep -vE '^(#|$)' iso/aur-packages.txt; echo marsos-desktop; } >> "$PROFILE/packages.x86_64"
# files for the live session
cp -a iso/airootfs/. "$PROFILE/airootfs/"
# kernel names in every boot menu: linux -> linux-zen
grep -rlE 'vmlinuz-linux|initramfs-linux' "$PROFILE" | while read -r f; do
  sed -i -E 's#vmlinuz-linux([^-]|$)#vmlinuz-linux-zen\1#g; s#initramfs-linux\.img#initramfs-linux-zen.img#g' "$f"
done
# initramfs preset for the live image
if [ -f "$PROFILE/airootfs/etc/mkinitcpio.d/linux.preset" ]; then
  sed -E 's#vmlinuz-linux([^-]|$)#vmlinuz-linux-zen\1#; s#initramfs-linux\.img#initramfs-linux-zen.img#' \
    "$PROFILE/airootfs/etc/mkinitcpio.d/linux.preset" > "$PROFILE/airootfs/etc/mkinitcpio.d/linux-zen.preset"
  rm "$PROFILE/airootfs/etc/mkinitcpio.d/linux.preset"
fi
# services: graphical login + NetworkManager (not systemd-networkd / iwd)
SYS="$PROFILE/airootfs/etc/systemd/system"; mkdir -p "$SYS/multi-user.target.wants"
ln -sf /usr/lib/systemd/system/graphical.target "$SYS/default.target"
ln -sf /usr/lib/systemd/system/sddm.service "$SYS/display-manager.service"
ln -sf /usr/lib/systemd/system/NetworkManager.service "$SYS/multi-user.target.wants/NetworkManager.service"
rm -f "$SYS"/multi-user.target.wants/{systemd-networkd.service,iwd.service,reflector.service} "$SYS"/sockets.target.wants/systemd-networkd.socket 2>/dev/null || true
# branding + permissions
sed -i 's/^iso_name=.*/iso_name="marsos"/; s/^iso_application=.*/iso_application="marsOS Installer"/; s/^iso_publisher=.*/iso_publisher="marsOS"/' "$PROFILE/profiledef.sh"
sed -i 's/^iso_label=.*/iso_label="MARSOS_$(date +%Y%m)"/' "$PROFILE/profiledef.sh"
cat >> "$PROFILE/profiledef.sh" <<'EOT'
file_permissions+=(
  ["/etc/sudoers.d/10-live"]="0:0:440"
  ["/usr/lib/marsos/sudo-askpass"]="0:0:755"
)
EOT

echo "==> Building the ISO (this takes a while)"
sudo mkarchiso -v -w "$WORK/tmp" -o "$OUT" "$PROFILE"
ls -lh "$OUT"
