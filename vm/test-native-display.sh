#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=${NATIVE_DISPLAY_TEST_DIR:-}
if [ -z "$TEST_DIR" ]; then
  TEST_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-display.XXXXXX")
fi
SOCKET="$TEST_DIR/input.sock"
QMP_SOCKET="$TEST_DIR/qmp.sock"
LOG="$TEST_DIR/uart.log"
VM_PID=

cleanup() {
  status=$?
  if [ "$status" -ne 0 ] && [ -n "$VM_PID" ]; then
    "$REPO_DIR/vm/capture-native-failure.sh" "$TEST_DIR" "$SOCKET" "$QMP_SOCKET" || true
  fi
  if [ -n "$VM_PID" ]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
  fi
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$TEST_DIR"
NATIVE_VM_BUILD_DIR="$TEST_DIR" NATIVE_STORAGE_MODE=ephemeral \
  "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot \
  >"$TEST_DIR/runner.log" 2>&1 &
VM_PID=$!

attempt=0
# Include first-run U-Boot/media construction in the bounded wait. A clean
# cross-build can take longer than the previous 40-second launch-only window.
until [ "$attempt" -ge 960 ]; do
  if grep -q "Lefony OS: control ready" "$LOG" 2>/dev/null &&
      [ -S "$SOCKET" ]; then
    break
  fi
  if ! kill -0 "$VM_PID" 2>/dev/null; then
    sed -n '1,240p' "$TEST_DIR/runner.log" >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep 0.25
done
test "$attempt" -lt 960

raw() {
  python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" raw "$@"
}

test "$(raw DISPLAY SELFTEST)" = "VALUE 0"
test "$(raw DISPLAY GUARDS)" = OK
for value in 0 1 120 239 240; do
  test "$(raw BRIGHTNESS SET "$value")" = OK
  test "$(raw BRIGHTNESS GET)" = "VALUE $value"
done
test "$(raw BRIGHTNESS SET 241 2>/dev/null || true)" = "ERR invalid brightness"
test "$(raw DISPLAY GUARDS)" = OK

python3 "$REPO_DIR/vm/qmp-screendump.py" "$QMP_SOCKET" "$TEST_DIR/display-selftest.ppm"
python3 "$REPO_DIR/vm/inspect-ppm.py" \
  "$TEST_DIR/display-selftest.ppm" --expect visible
grep -q "prime-g2-panel: visible" "$TEST_DIR/qemu.log"

echo "PASS: exhaustive RGB565, colors, gradient, clipping, guards, and brightness range"
echo "Artifacts: $TEST_DIR"
