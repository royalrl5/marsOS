#!/usr/bin/env bash
# Try the ISO in QEMU (UEFI, like a Mac).  usage: scripts/run-vm.sh out/marsos-*.iso [--bios] [--reset]
set -euo pipefail
ISO="${1:?usage: run-vm.sh <iso> [--bios] [--reset]}"; shift || true
DISK=vm/marsos.qcow2; mkdir -p vm
[[ " $* " == *" --reset "* ]] && rm -f "$DISK" vm/OVMF_VARS.fd
[ -f "$DISK" ] || qemu-img create -f qcow2 "$DISK" 40G
ARGS=(-enable-kvm -cpu host -smp 2 -m 4096 -machine q35
      -device virtio-vga-gl -display gtk,gl=on
      -device virtio-net-pci,netdev=n0 -netdev user,id=n0
      -device intel-hda -device hda-duplex
      -drive file="$DISK",if=virtio,format=qcow2
      -drive file="$ISO",media=cdrom,readonly=on
      -usb -device usb-tablet)
if [[ " $* " != *" --bios "* ]]; then
  CODE=$(ls /usr/share/edk2/x64/OVMF_CODE.4m.fd /usr/share/edk2/x64/OVMF_CODE.fd /usr/share/OVMF/OVMF_CODE.fd /usr/share/edk2-ovmf/x64/OVMF_CODE.fd 2>/dev/null | head -1)
  VARS=$(ls /usr/share/edk2/x64/OVMF_VARS.4m.fd /usr/share/edk2/x64/OVMF_VARS.fd /usr/share/OVMF/OVMF_VARS.fd /usr/share/edk2-ovmf/x64/OVMF_VARS.fd 2>/dev/null | head -1)
  [ -n "$CODE" ] || { echo "Install OVMF (pacman -S edk2-ovmf) or use --bios"; exit 1; }
  [ -f vm/OVMF_VARS.fd ] || cp "$VARS" vm/OVMF_VARS.fd
  ARGS+=(-drive if=pflash,format=raw,readonly=on,file="$CODE" -drive if=pflash,format=raw,file=vm/OVMF_VARS.fd)
fi
exec qemu-system-x86_64 "${ARGS[@]}"
