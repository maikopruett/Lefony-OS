#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
NATIVE_VM_BUILD_DIR=${NATIVE_VM_BUILD_DIR:-"$REPO_DIR/build/prime-g2-native-vm"}
NATIVE_ELF=${NATIVE_ELF:-"$REPO_DIR/dist/lefony-os-prime-g2-vm-native.elf"}
UBOOT_ELF=${UBOOT_ELF:-"$REPO_DIR/build/prime-g2-native-vm/u-boot/u-boot.elf"}
BOOT_MEDIA=${NATIVE_BOOT_MEDIA:-"$REPO_DIR/build/prime-g2-native-vm/lefony-os-boot.img"}
NATIVE_BIN=${NATIVE_BIN:-"$REPO_DIR/dist/lefony-os-prime-g2-vm-native.bin"}
NATIVE_CAPSULE=${NATIVE_CAPSULE:-"$REPO_DIR/build/prime-g2-native-vm/lefony-os-vm.zImage"}
STORAGE_MODE=${NATIVE_STORAGE_MODE:-persistent}
STORAGE_OVERLAY=${NATIVE_STORAGE_OVERLAY:-"$NATIVE_VM_BUILD_DIR/native-state-v1.qcow2"}
READONLY_OVERLAY="$NATIVE_VM_BUILD_DIR/native-readonly-v1.qcow2"
QEMU_SYSTEM_ARM=${PRIME_G2_QEMU:-"$REPO_DIR/build/qemu-prime-g2/qemu-system-arm"}
PANEL_FAULT=${PRIME_G2_PANEL_FAULT:-none}
case "$(uname -s)" in
  Darwin) DISPLAY_MODE=${LEFONY_VM_DISPLAY:-desktop} ;;
  *) DISPLAY_MODE=${LEFONY_VM_DISPLAY:-browser} ;;
esac
BOOT_MODE=direct

while [ "$#" -gt 0 ]; do
  case "$1" in
    --headless) DISPLAY_MODE=none ;;
    --browser) DISPLAY_MODE=browser ;;
    --desktop) DISPLAY_MODE=desktop ;;
    --u-boot) BOOT_MODE=u-boot ;;
    --capsule) BOOT_MODE=capsule ;;
    --ab) BOOT_MODE=ab ;;
    --direct) BOOT_MODE=direct ;;
    *)
      echo "Usage: $0 [--headless|--browser|--desktop] [--direct|--u-boot|--capsule|--ab]" >&2
      exit 2
      ;;
  esac
  shift
done
PANEL_MODE=
case "$DISPLAY_MODE" in
  browser|desktop) PANEL_MODE=$DISPLAY_MODE; DISPLAY_MODE=none ;;
esac
PANEL_PYTHON=${PYTHON:-"$REPO_DIR/.venv/bin/python"}
if [ -n "$PANEL_MODE" ] && [ ! -x "$PANEL_PYTHON" ]; then
  echo "Create the project virtualenv and install requirements-dev.txt for the emulator panel." >&2
  exit 2
fi
if [ ! -x "$QEMU_SYSTEM_ARM" ]; then
  "$REPO_DIR/vm/build-prime-g2-qemu.sh"
fi
if [ ! -s "$NATIVE_ELF" ]; then
  "$REPO_DIR/scripts/build_lefony_prime_g2_vm.sh"
fi
if [ "$BOOT_MODE" = capsule ] || [ "$BOOT_MODE" = ab ]; then
  if [ "$BOOT_MODE" = ab ]; then
    UBOOT_ELF="$NATIVE_VM_BUILD_DIR/u-boot-ab/u-boot.elf"
    BOOT_MEDIA="$NATIVE_VM_BUILD_DIR/lefony-os-ab-boot.img"
  else
    UBOOT_ELF="$NATIVE_VM_BUILD_DIR/u-boot-capsule/u-boot.elf"
    BOOT_MEDIA="$NATIVE_VM_BUILD_DIR/lefony-os-capsule-boot.img"
  fi
  if [ ! -s "$NATIVE_BIN" ]; then
    "$REPO_DIR/scripts/build_lefony_prime_g2_vm.sh"
  fi
  if [ ! -s "$NATIVE_CAPSULE" ] || [ "$NATIVE_BIN" -nt "$NATIVE_CAPSULE" ] || \
      [ "$REPO_DIR/native/prime_g2/nand_boot_capsule.S" -nt "$NATIVE_CAPSULE" ]; then
    "$REPO_DIR/scripts/build_prime_g2_nand_capsule.sh" \
      "$NATIVE_BIN" "$NATIVE_CAPSULE"
  fi
fi
if [ "$BOOT_MODE" = u-boot ] || [ "$BOOT_MODE" = capsule ] || [ "$BOOT_MODE" = ab ]; then
  if [ ! -s "$UBOOT_ELF" ] || \
      [ "$REPO_DIR/vm/build-u-boot.sh" -nt "$UBOOT_ELF" ] || \
      [ "$REPO_DIR/vm/patches/u-boot-qemu-memory.patch" -nt "$UBOOT_ELF" ] || \
      { [ "$BOOT_MODE" = ab ] && \
        { [ "$REPO_DIR/vm/u-boot/lefony_ab.c" -nt "$UBOOT_ELF" ] || \
          [ "$REPO_DIR/vm/patches/u-boot-lefony-ab-command.patch" -nt "$UBOOT_ELF" ]; }; }; then
    if [ "$BOOT_MODE" = ab ]; then
      UBOOT_BOOT_FORMAT=ab UBOOT_OUTPUT_DIR="$NATIVE_VM_BUILD_DIR/u-boot-ab" \
        "$REPO_DIR/vm/build-u-boot.sh"
    elif [ "$BOOT_MODE" = capsule ]; then
      UBOOT_BOOT_FORMAT=capsule UBOOT_OUTPUT_DIR="$NATIVE_VM_BUILD_DIR/u-boot-capsule" \
        "$REPO_DIR/vm/build-u-boot.sh"
    else
      "$REPO_DIR/vm/build-u-boot.sh"
    fi
  fi
  BOOT_PAYLOAD="$NATIVE_ELF"
  BOOT_PAYLOAD_FILENAME=lefony-os.elf
  if [ "$BOOT_MODE" = capsule ] || [ "$BOOT_MODE" = ab ]; then
    BOOT_PAYLOAD="$NATIVE_CAPSULE"
    BOOT_PAYLOAD_FILENAME=lefony-os.zImage
  fi
  if [ ! -s "$BOOT_MEDIA" ] || [ "$BOOT_PAYLOAD" -nt "$BOOT_MEDIA" ] || \
      [ "$REPO_DIR/vm/build-native-boot-media.sh" -nt "$BOOT_MEDIA" ]; then
    NATIVE_ELF="$BOOT_PAYLOAD" NATIVE_BOOT_PAYLOAD_FILENAME="$BOOT_PAYLOAD_FILENAME" \
      NATIVE_BOOT_MEDIA="$BOOT_MEDIA" "$REPO_DIR/vm/build-native-boot-media.sh"
  fi
  case "$STORAGE_MODE" in
    persistent)
      if ! command -v qemu-img >/dev/null 2>&1; then
        echo "qemu-img is required for persistent native storage." >&2
        exit 1
      fi
      mkdir -p "$(dirname -- "$STORAGE_OVERLAY")"
      if [ ! -s "$STORAGE_OVERLAY" ]; then
        qemu-img create -q -f qcow2 -F raw -b "$BOOT_MEDIA" \
          "$STORAGE_OVERLAY"
      fi
      ;;
    readonly)
      if ! command -v qemu-img >/dev/null 2>&1 || \
          ! command -v qemu-io >/dev/null 2>&1; then
        echo "qemu-img and qemu-io are required for read-only rescue mode." >&2
        exit 1
      fi
      mkdir -p "$NATIVE_VM_BUILD_DIR"
      if [ ! -s "$READONLY_OVERLAY" ]; then
        qemu-img create -q -f qcow2 -F raw -b "$BOOT_MEDIA" \
          "$READONLY_OVERLAY"
        qemu-io -f qcow2 -c "write -P 0xa5 68157440 512" \
          "$READONLY_OVERLAY" >/dev/null
      fi
      ;;
    ephemeral) ;;
    *)
      echo "NATIVE_STORAGE_MODE must be persistent, ephemeral, or readonly." >&2
      exit 2
      ;;
  esac
fi

mkdir -p "$NATIVE_VM_BUILD_DIR"
PUBLIC_INPUT_SOCKET="$NATIVE_VM_BUILD_DIR/input.sock"
PUBLIC_CONSOLE_SOCKET="$NATIVE_VM_BUILD_DIR/console.sock"
PUBLIC_QMP_SOCKET="$NATIVE_VM_BUILD_DIR/qmp.sock"
PUBLIC_USB_SOCKET="$NATIVE_VM_BUILD_DIR/usb-host.sock"
SOCKET_DIR=${NATIVE_VM_SOCKET_DIR:-"$NATIVE_VM_BUILD_DIR"}
PRIVATE_SOCKET_DIR=false
# macOS limits AF_UNIX paths to 103 bytes. Test artifact directories are
# intentionally descriptive, so use a short private runtime directory and
# expose stable symlinks from the artifact directory when necessary.
if [ ${#SOCKET_DIR} -gt 72 ]; then
  SOCKET_DIR="${TMPDIR:-/tmp}/lefony-native-$$"
  PRIVATE_SOCKET_DIR=true
fi
mkdir -p "$SOCKET_DIR"
INPUT_SOCKET="$SOCKET_DIR/input.sock"
INPUT_UART_SOCKET="$SOCKET_DIR/input-uart.sock"
CONSOLE_SOCKET="$SOCKET_DIR/console.sock"
QMP_SOCKET="$SOCKET_DIR/qmp.sock"
QTEST_SOCKET="$SOCKET_DIR/qtest.sock"
USB_SOCKET="$SOCKET_DIR/usb-host.sock"
QEMU_LOG="$NATIVE_VM_BUILD_DIR/qemu.log"
UART_LOG="$NATIVE_VM_BUILD_DIR/uart.log"
rm -f "$PUBLIC_INPUT_SOCKET" "$PUBLIC_CONSOLE_SOCKET" "$PUBLIC_QMP_SOCKET" \
  "$PUBLIC_USB_SOCKET" \
  "$INPUT_SOCKET" "$INPUT_UART_SOCKET" "$CONSOLE_SOCKET" "$QMP_SOCKET" \
  "$QTEST_SOCKET" "$USB_SOCKET" \
  "$QEMU_LOG" "$UART_LOG"
if [ "$SOCKET_DIR" != "$NATIVE_VM_BUILD_DIR" ]; then
  ln -s "$INPUT_SOCKET" "$PUBLIC_INPUT_SOCKET"
  ln -s "$CONSOLE_SOCKET" "$PUBLIC_CONSOLE_SOCKET"
  ln -s "$QMP_SOCKET" "$PUBLIC_QMP_SOCKET"
  ln -s "$USB_SOCKET" "$PUBLIC_USB_SOCKET"
fi

echo "Starting native Lefony OS in the Prime G2 VM."
echo "Boot:   $BOOT_MODE"
if [ "$BOOT_MODE" = u-boot ] || [ "$BOOT_MODE" = capsule ] || [ "$BOOT_MODE" = ab ]; then
  echo "Store:  $STORAGE_MODE"
fi
echo "Input:  $REPO_DIR/vm/prime-control.py --socket $PUBLIC_INPUT_SOCKET press up"
echo "USB:    $PUBLIC_USB_SOCKET"
echo "Shell:  none (this is the bare-metal image)"
echo "UART:   $UART_LOG"

python3 "$REPO_DIR/vm/input-proxy.py" "$INPUT_UART_SOCKET" "$INPUT_SOCKET" \
  "$QTEST_SOCKET" &
PROXY_PID=$!
QEMU_PID=
PANEL_PID=

cleanup() {
  if [ -n "$PANEL_PID" ]; then
    kill "$PANEL_PID" 2>/dev/null || true
  fi
  if [ -n "$QEMU_PID" ]; then
    kill "$QEMU_PID" 2>/dev/null || true
  fi
  kill "$PROXY_PID" 2>/dev/null || true
  if [ "$PRIVATE_SOCKET_DIR" = true ]; then
    rm -f "$INPUT_SOCKET" "$INPUT_UART_SOCKET" "$CONSOLE_SOCKET" "$QMP_SOCKET" \
      "$QTEST_SOCKET" "$USB_SOCKET"
    rmdir "$SOCKET_DIR" 2>/dev/null || true
  fi
}
trap cleanup EXIT HUP INT TERM

set -- \
  -name "Lefony OS Prime G2 native" \
  -machine mcimx6ul-evk \
  -global imx6ul-lcdif.prime-g2-panel=on \
  -cpu cortex-a7 \
  -m 256M
if [ -n "$PANEL_MODE" ]; then
  # Interactive previews model external power; battery/suspend qualification
  # keeps the existing headless and plain Cocoa/SDL defaults.
  set -- "$@" -global prime-g2-pf1550.external-power=on
fi
case "$PANEL_FAULT" in
  none) ;;
  spi)
    set -- "$@" -global imx6ul-lcdif.prime-g2-fault-spi=on
    ;;
  iomux|signal|timing|polarity|power|fifo)
    set -- "$@" -global "imx6ul-lcdif.prime-g2-fault-$PANEL_FAULT=on"
    ;;
  *)
    echo "PRIME_G2_PANEL_FAULT must be none, spi, iomux, signal, timing, polarity, power, or fifo." >&2
    exit 2
    ;;
esac
if [ "$BOOT_MODE" = u-boot ] || [ "$BOOT_MODE" = capsule ] || [ "$BOOT_MODE" = ab ]; then
  set -- "$@" -device "loader,file=$UBOOT_ELF,cpu-num=0"
  if [ "$STORAGE_MODE" = persistent ]; then
    set -- "$@" -drive \
      "file=$STORAGE_OVERLAY,format=qcow2,if=sd,cache=directsync"
  elif [ "$STORAGE_MODE" = readonly ]; then
    set -- "$@" -drive \
      "file=$READONLY_OVERLAY,format=qcow2,if=sd,snapshot=on"
  else
    set -- "$@" -drive \
      "file=$BOOT_MEDIA,format=raw,if=sd,snapshot=on"
  fi
else
  set -- "$@" -kernel "$NATIVE_ELF"
fi
set -- "$@" \
  -chardev socket,id=primeconsole,path="$CONSOLE_SOCKET",server=on,wait=off,logfile="$UART_LOG" \
  -serial chardev:primeconsole \
  -serial null \
  -chardev socket,id=primeinput,path="$INPUT_UART_SOCKET",server=on,wait=off \
  -serial chardev:primeinput \
  -chardev socket,id=primeusb,path="$USB_SOCKET",server=on,wait=off \
  -global prime-g2-usbotg-device.chardev=primeusb \
  -qtest unix:"$QTEST_SOCKET",server=on,wait=off \
  -qmp unix:"$QMP_SOCKET",server=on,wait=off \
  -display "$DISPLAY_MODE" \
  -d guest_errors,unimp \
  -D "$QEMU_LOG"

if [ "$BOOT_MODE" != ab ]; then
  set -- "$@" -no-reboot
fi

"$QEMU_SYSTEM_ARM" "$@" &
QEMU_PID=$!
if [ -n "$PANEL_MODE" ]; then
  set -- --input "$INPUT_SOCKET" --qmp "$QMP_SOCKET" --output "$NATIVE_VM_BUILD_DIR" --qemu-pid "$QEMU_PID"
  if [ "$PANEL_MODE" = desktop ]; then set -- "$@" --desktop; fi
  "$PANEL_PYTHON" "$REPO_DIR/vm/emulator-panel.py" "$@" &
  PANEL_PID=$!
  wait "$PANEL_PID"
  exit $?
fi
wait "$QEMU_PID"
