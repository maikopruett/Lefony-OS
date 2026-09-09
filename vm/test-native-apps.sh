#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=${NATIVE_APPS_TEST_DIR:-}
if [ -z "$TEST_DIR" ]; then
  TEST_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-apps.XXXXXX")
fi
SOCKET="$TEST_DIR/input.sock"
QMP_SOCKET="$TEST_DIR/qmp.sock"
LOG="$TEST_DIR/uart.log"
VM_PID=

capture_failure() {
  "$REPO_DIR/vm/capture-native-failure.sh" "$TEST_DIR" "$SOCKET" "$QMP_SOCKET" || true
}

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    capture_failure
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
until [ "$attempt" -ge 160 ]; do
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
test "$attempt" -lt 160

python3 "$REPO_DIR/vm/native-app-test.py" --socket "$SOCKET"
python3 "$REPO_DIR/vm/qmp-screendump.py" "$QMP_SOCKET" "$TEST_DIR/final.ppm"
! grep -q "Lefony OS: abort" "$LOG"
echo "Artifacts: $TEST_DIR"
