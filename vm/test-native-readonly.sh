#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=${NATIVE_READONLY_TEST_DIR:-}
if [ -z "$TEST_DIR" ]; then
  TEST_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-readonly.XXXXXX")
fi
BOOT_MEDIA="$REPO_DIR/build/prime-g2-native-vm/upsilon-boot.img"
INPUT_SOCKET="$TEST_DIR/input.sock"
UART_LOG="$TEST_DIR/uart.log"
RUNNER_LOG="$TEST_DIR/runner.log"
VM_PID=

cleanup() {
  if [ -n "$VM_PID" ]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$TEST_DIR"
if [ ! -s "$BOOT_MEDIA" ]; then
  "$REPO_DIR/vm/build-native-boot-media.sh"
fi
BEFORE=$(shasum -a 256 "$BOOT_MEDIA" | awk '{print $1}')

NATIVE_VM_BUILD_DIR="$TEST_DIR" NATIVE_STORAGE_MODE=readonly \
  "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot \
  >"$RUNNER_LOG" 2>&1 &
VM_PID=$!

attempt=0
until [ "$attempt" -ge 80 ]; do
  if grep -q "Lefony OS: control ready" "$UART_LOG" 2>/dev/null && \
      [ -S "$INPUT_SOCKET" ]; then
    break
  fi
  if ! kill -0 "$VM_PID" 2>/dev/null; then
    echo "Read-only VM exited before becoming ready:" >&2
    sed -n '1,200p' "$RUNNER_LOG" >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep 0.25
done
test "$attempt" -lt 80

test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE COMMIT 2>/dev/null || true)" = "ERR commit failed"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  press right)" = OK
cleanup
VM_PID=

AFTER=$(shasum -a 256 "$BOOT_MEDIA" | awk '{print $1}')
test "$BEFORE" = "$AFTER"

echo "PASS: read-only rescue boot refused storage commits and preserved base media"
echo "Artifacts: $TEST_DIR"
