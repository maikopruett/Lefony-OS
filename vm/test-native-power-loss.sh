#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ROOT_DIR=${NATIVE_POWER_LOSS_TEST_DIR:-}
if [ -z "$ROOT_DIR" ]; then
  ROOT_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-power-loss.XXXXXX")
fi
VM_PID=
PHASE_DIR=
SOCKET=
OVERLAY=

stop_vm() {
  if [ -n "$VM_PID" ]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
    VM_PID=
  fi
}
trap stop_vm EXIT HUP INT TERM

start_vm() {
  NATIVE_VM_BUILD_DIR="$PHASE_DIR" NATIVE_STORAGE_MODE=persistent \
    NATIVE_STORAGE_OVERLAY="$OVERLAY" \
    "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot \
    >"$PHASE_DIR/runner.log" 2>&1 &
  VM_PID=$!
  attempt=0
  until [ "$attempt" -ge 80 ]; do
    if grep -q "Lefony OS: control ready" "$PHASE_DIR/uart.log" 2>/dev/null && \
        [ -S "$SOCKET" ]; then
      return
    fi
    if ! kill -0 "$VM_PID" 2>/dev/null; then
      sed -n '1,220p' "$PHASE_DIR/runner.log" >&2
      exit 1
    fi
    attempt=$((attempt + 1))
    sleep 0.25
  done
  echo "Timed out in power-loss phase $phase" >&2
  exit 1
}

raw() {
  python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" raw "$@"
}

mkdir -p "$ROOT_DIR"
for phase in 0 1 2 3; do
  PHASE_DIR="$ROOT_DIR/phase-$phase"
  SOCKET="$PHASE_DIR/input.sock"
  OVERLAY="$PHASE_DIR/storage.qcow2"
  mkdir -p "$PHASE_DIR"

  start_vm
  test "$(raw STORAGE PUT power.bin 6f6c64)" = OK
  test "$(raw STORAGE COMMIT)" = OK
  test "$(raw STORAGE COMMIT)" = OK
  test "$(raw STORAGE PUT power.bin 6e6577)" = OK
  test "$(raw STORAGE INTERRUPT "$phase")" = OK
  stop_vm

  start_vm
  value=$(raw STORAGE GET power.bin)
  if [ "$phase" -lt 3 ]; then
    test "$value" = "DATA 6f6c64"
  else
    test "$value" = "DATA 6e6577"
  fi
  stop_vm
done

echo "PASS: every native storage commit phase recovered the expected generation"
echo "Artifacts: $ROOT_DIR"
