#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -n "${NATIVE_USB_TEST_DIR:-}" ]; then
  ARTIFACT_DIR=$NATIVE_USB_TEST_DIR
  mkdir -p "$ARTIFACT_DIR"
else
  ARTIFACT_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-usb.XXXXXX")
fi
VM_PID=
cleanup() {
  if [ -n "$VM_PID" ]; then kill "$VM_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT HUP INT TERM

NATIVE_VM_BUILD_DIR="$ARTIFACT_DIR" \
NATIVE_VM_SOCKET_DIR="$ARTIFACT_DIR" \
NATIVE_STORAGE_MODE=ephemeral \
  "$REPO_DIR/vm/run-native-vm.sh" --headless --direct \
  >"$ARTIFACT_DIR/runner.log" 2>&1 &
VM_PID=$!

python3 "$REPO_DIR/vm/native-usb-test.py" \
  --socket "$ARTIFACT_DIR/usb-host.sock"
python3 "$REPO_DIR/vm/prime-control.py" \
  --socket "$ARTIFACT_DIR/input.sock" raw "USB STATUS" \
  | grep -q '^VALUE 63$'

echo "Artifacts: $ARTIFACT_DIR"
