#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ROOT=${NATIVE_EXCEPTION_TEST_DIR:-}
if [ -z "$ROOT" ]; then ROOT=$(mktemp -d "$REPO_DIR/build/prime-g2-native-exceptions.XXXXXX"); fi
VM_PID=

cleanup() {
  status=$?
  if [ -n "$VM_PID" ]; then kill "$VM_PID" 2>/dev/null || true; wait "$VM_PID" 2>/dev/null || true; fi
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

run_fault() {
  kind=$1
  expected=$2
  DIR="$ROOT/$(printf '%s' "$kind" | tr A-Z a-z)"
  SOCKET="$DIR/input.sock"
  QMP="$DIR/qmp.sock"
  LOG="$DIR/uart.log"
  mkdir -p "$DIR"
  NATIVE_VM_BUILD_DIR="$DIR" NATIVE_STORAGE_MODE=ephemeral \
    "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot >"$DIR/runner.log" 2>&1 &
  VM_PID=$!
  attempt=0
  until [ "$attempt" -ge 160 ]; do
    if grep -q "Lefony OS: control ready" "$LOG" 2>/dev/null && [ -S "$SOCKET" ]; then break; fi
    kill -0 "$VM_PID" 2>/dev/null || return 1
    attempt=$((attempt + 1)); sleep 0.25
  done
  test "$attempt" -lt 160
  test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" raw FAULT "$kind")" = OK
  attempt=0
  until grep -q "Lefony OS fatal exception: $expected" "$LOG" 2>/dev/null; do
    attempt=$((attempt + 1)); test "$attempt" -lt 100; sleep 0.05
  done
  for field in PC LR SP CPSR DFSR DFAR IFSR IFAR; do grep -q "^$field=0x" "$LOG"; done
  python3 "$REPO_DIR/vm/qmp-screendump.py" "$QMP" "$DIR/crash.ppm"
  test -s "$DIR/crash.ppm"
  kill "$VM_PID" 2>/dev/null || true
  wait "$VM_PID" 2>/dev/null || true
  VM_PID=
}

run_fault UNDEFINED undefined
run_fault SVC svc
run_fault PREFETCH prefetch-abort
run_fault DATA data-abort

echo "PASS: undefined, SVC, prefetch-abort, and data-abort report full state and crash screen"
echo "Artifacts: $ROOT"
