#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
FIXTURE_DIR=${HP_PRIME_STOCK_FIXTURE_DIR:-"$REPO_DIR/build/hp-prime-stock"}
QEMU_SYSTEM_ARM=${PRIME_G2_QEMU:-"$REPO_DIR/build/qemu-prime-g2/qemu-system-arm"}
IMAGE_KIND=os_fast
DISPLAY_MODE=cocoa
START_PAUSED=0
ALLOW_RESET=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --headless) DISPLAY_MODE=none ;;
    --os) IMAGE_KIND=os ;;
    --fast) IMAGE_KIND=os_fast ;;
    --bootloader) IMAGE_KIND=bootloader ;;
    --bootloader-research) IMAGE_KIND=bootloader_research ;;
    --research) IMAGE_KIND=os_research ;;
    --paused) START_PAUSED=1 ;;
    --allow-reset) ALLOW_RESET=1 ;;
    *)
      echo "Usage: $0 [--headless] [--paused] [--allow-reset] [--os|--fast|--research|--bootloader|--bootloader-research]" >&2
      exit 2
      ;;
  esac
  shift
done

if [ ! -x "$QEMU_SYSTEM_ARM" ]; then
  "$REPO_DIR/vm/build-prime-g2-qemu.sh"
fi
if [ ! -s "$FIXTURE_DIR/fixture.json" ]; then
  echo "Private HP fixture is missing." >&2
  echo "Prepare it with:" >&2
  echo "  python3 scripts/prepare_hp_prime_stock_fixture.py /path/to/HP_firmware.zip --fast-boot" >&2
  exit 1
fi

set -- $(python3 - "$FIXTURE_DIR/fixture.json" "$IMAGE_KIND" <<'PY'
import json
import shlex
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
image = manifest["images"].get(sys.argv[2])
if image is None:
    raise SystemExit(f"fixture has no {sys.argv[2]} image; rerun preparation with --fast-boot")
print(shlex.quote(image["path"]), f'{image["ivt"]["entry"]:#x}')
PY
)
IMAGE_PATH="$FIXTURE_DIR/$1"
ENTRY_POINT=$2
if [ ! -s "$IMAGE_PATH" ]; then
  echo "Fixture image is missing: $IMAGE_PATH" >&2
  exit 1
fi

RUN_DIR="$FIXTURE_DIR/run-$(date -u +%Y%m%dT%H%M%SZ)-$$"
USB_SOCKET="$RUN_DIR/usb.sock"
QTEST_SOCKET="$RUN_DIR/qtest.sock"
QMP_SOCKET="$RUN_DIR/qmp.sock"
GDB_SOCKET="$RUN_DIR/gdb.sock"
mkdir -p "$RUN_DIR"
echo "Starting private HP Prime G2 stock firmware research VM."
echo "Image: $IMAGE_KIND"
echo "Entry: $ENTRY_POINT"
echo "Logs:  $RUN_DIR"

set -- \
  -name "HP Prime G2 stock firmware research" \
  -machine hp-prime-g2 \
  -global imx6ul-lcdif.prime-g2-panel=on \
  -global prime-g2-pf1550.external-power=on \
  -global prime-g2-goodix-gt5688.drive-irq=off \
  -cpu cortex-a7 \
  -m 256M \
  -device "loader,file=$IMAGE_PATH,addr=0x80000000,force-raw=on" \
  -device "loader,addr=$ENTRY_POINT,cpu-num=0" \
  -serial "file:$RUN_DIR/uart.log" \
  -serial null \
  -serial null \
  -chardev "socket,id=primeusb,path=$USB_SOCKET,server=on,wait=off" \
  -global prime-g2-usbotg-device.chardev=primeusb \
  -qtest "unix:$QTEST_SOCKET,server=on,wait=off" \
  -qmp "unix:$QMP_SOCKET,server=on,wait=off" \
  -gdb "unix:$GDB_SOCKET,server=on,wait=off" \
  -monitor stdio \
  -display "$DISPLAY_MODE" \
  -d guest_errors,unimp,cpu_reset \
  -D "$RUN_DIR/qemu.log"

if [ "$ALLOW_RESET" -eq 0 ]; then
  set -- "$@" -no-reboot
else
  echo "Reset: warm watchdog/system resets remain inside the VM"
fi

if [ "${HP_PRIME_STOCK_NO_SHUTDOWN:-0}" = 1 ]; then
  set -- "$@" -no-shutdown
  echo "Power: guest shutdown pauses the VM for boundary inspection"
fi

echo "USB:   $USB_SOCKET"
echo "QTest: $QTEST_SOCKET"
echo "QMP:   $QMP_SOCKET"
echo "GDB:   $GDB_SOCKET"

if [ -n "${HP_PRIME_STOCK_TRACE_EVENTS:-}" ]; then
  if [ ! -s "$HP_PRIME_STOCK_TRACE_EVENTS" ]; then
    echo "Trace event list is missing: $HP_PRIME_STOCK_TRACE_EVENTS" >&2
    exit 1
  fi
  set -- "$@" -trace "events=$HP_PRIME_STOCK_TRACE_EVENTS,file=$RUN_DIR/trace.log"
  echo "Trace: $RUN_DIR/trace.log"
fi

if [ -s "$FIXTURE_DIR/nand-fixture.json" ]; then
  NAND_PATH=$(python3 - "$FIXTURE_DIR/nand-fixture.json" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["image"]["path"])
PY
)
  if [ ! -s "$FIXTURE_DIR/$NAND_PATH" ]; then
    echo "Private NAND fixture image is missing: $FIXTURE_DIR/$NAND_PATH" >&2
    exit 1
  fi
  set -- "$@" -global "prime-g2-gpmi-bch.stock-nand=$FIXTURE_DIR/$NAND_PATH"
  echo "NAND:  private raw+OOB fixture (copy-on-write in the VM)"
  if [ -n "${HP_PRIME_STOCK_OVERLAY:-}" ]; then
    set -- "$@" -global "prime-g2-gpmi-bch.stock-overlay=$HP_PRIME_STOCK_OVERLAY"
    echo "NAND:  private persistent overlay $HP_PRIME_STOCK_OVERLAY"
  fi
else
  echo "NAND:  erased synthetic fixture"
fi

if [ "${HP_PRIME_STOCK_ILITEK_PRESENT:-1}" = "0" ]; then
  set -- "$@" -global prime-g2-ilitek-ili2117.present=off
  echo "Touch: Ilitek 0x26 will NAK (stock continues without that endpoint)"
fi

if [ "$START_PAUSED" -eq 1 ]; then
  set -- "$@" -S
  echo "CPU:   paused for pre-boot qtest setup (use monitor 'cont' to start)"
fi

"$QEMU_SYSTEM_ARM" "$@"
