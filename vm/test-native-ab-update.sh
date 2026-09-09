#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD_DIR=${NATIVE_AB_TEST_DIR:-"$REPO_DIR/build/prime-g2-native-vm"}
mkdir -p "$BUILD_DIR"
VM_PID=
cleanup() {
  if [ -n "$VM_PID" ]; then kill "$VM_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT HUP INT TERM

NATIVE_VM_BUILD_DIR="$BUILD_DIR" NATIVE_STORAGE_MODE=ephemeral \
  "$REPO_DIR/vm/run-native-vm.sh" --headless --ab \
  >"$BUILD_DIR/ab-runner.log" 2>&1 &
VM_PID=$!

python3 "$REPO_DIR/vm/native-ab-update-test.py" \
  --socket "$BUILD_DIR/usb-host.sock" \
  --qmp "$BUILD_DIR/qmp.sock" \
  --uart "$BUILD_DIR/uart.log" \
  --payload "$BUILD_DIR/lefony-os-vm.zImage" \
  --private-key "$REPO_DIR/tests/fixtures/prime_g2_emulator_update_private.pem"

echo "Artifacts: $BUILD_DIR"
