#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ROOT=${NATIVE_COLD_RESET_TEST_DIR:-}
if [ -z "$ROOT" ]; then ROOT=$(mktemp -d "$REPO_DIR/build/prime-g2-native-cold-reset.XXXXXX"); fi
VM_PID=
cleanup() {
  status=$?
  if [ -n "$VM_PID" ]; then kill "$VM_PID" 2>/dev/null || true; wait "$VM_PID" 2>/dev/null || true; fi
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

start_vm() {
  DIR=$1
  mkdir -p "$DIR"
  NATIVE_VM_BUILD_DIR="$DIR" NATIVE_STORAGE_MODE=ephemeral \
    "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot >"$DIR/runner.log" 2>&1 &
  VM_PID=$!
  attempt=0
  until [ "$attempt" -ge 160 ]; do
    if grep -q "Lefony OS: control ready" "$DIR/uart.log" 2>/dev/null && [ -S "$DIR/input.sock" ]; then return 0; fi
    kill -0 "$VM_PID" 2>/dev/null || return 1
    attempt=$((attempt + 1)); sleep 0.25
  done
  return 1
}

start_vm "$ROOT/first"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$ROOT/first/input.sock" raw RESET COLD)" = OK
attempt=0
while kill -0 "$VM_PID" 2>/dev/null && [ "$attempt" -lt 120 ]; do
  attempt=$((attempt + 1)); sleep 0.05
done
test "$attempt" -lt 120
wait "$VM_PID" 2>/dev/null || true
VM_PID=

start_vm "$ROOT/second"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$ROOT/second/input.sock" ping)" = PONG
grep -q "Lefony OS: entering calculator runtime" "$ROOT/second/uart.log"

echo "PASS: WDOG1 cold reset exits -no-reboot VM and a fresh cold boot recovers"
echo "Artifacts: $ROOT"
