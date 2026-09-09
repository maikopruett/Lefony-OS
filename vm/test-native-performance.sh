#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=${NATIVE_PERFORMANCE_TEST_DIR:-}
if [ -z "$TEST_DIR" ]; then TEST_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-performance.XXXXXX"); fi
SOCKET="$TEST_DIR/input.sock"
QMP_SOCKET="$TEST_DIR/qmp.sock"
LOG="$TEST_DIR/uart.log"
VM_PID=
cleanup() {
  status=$?
  if [ "$status" -ne 0 ] && [ -n "$VM_PID" ]; then "$REPO_DIR/vm/capture-native-failure.sh" "$TEST_DIR" "$SOCKET" "$QMP_SOCKET" || true; fi
  if [ -n "$VM_PID" ]; then kill "$VM_PID" 2>/dev/null || true; wait "$VM_PID" 2>/dev/null || true; fi
  exit "$status"
}
trap cleanup EXIT HUP INT TERM
mkdir -p "$TEST_DIR"
started=$(python3 -c 'import time; print(time.monotonic())')
NATIVE_VM_BUILD_DIR="$TEST_DIR" NATIVE_STORAGE_MODE=ephemeral \
  "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot >"$TEST_DIR/runner.log" 2>&1 &
VM_PID=$!
attempt=0
until [ "$attempt" -ge 160 ]; do
  if grep -q "Lefony OS: control ready" "$LOG" 2>/dev/null && [ -S "$SOCKET" ]; then break; fi
  kill -0 "$VM_PID" 2>/dev/null || exit 1
  attempt=$((attempt + 1)); sleep 0.25
done
test "$attempt" -lt 160
boot_seconds=$(python3 -c 'import sys,time; print(time.monotonic()-float(sys.argv[1]))' "$started")
python3 "$REPO_DIR/vm/native-performance-test.py" --socket "$SOCKET" \
  --output "$TEST_DIR/metrics.json" --boot-seconds "$boot_seconds"
echo "PASS: boot, calculation, app-open, redraw, key/touch latency, storage, memory, IRQ, and leak budgets"
echo "Artifacts: $TEST_DIR"
