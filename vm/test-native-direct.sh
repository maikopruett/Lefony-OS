#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=${NATIVE_DIRECT_TEST_DIR:-"$REPO_DIR/build/prime-g2-native-direct"}
SOCKET="$TEST_DIR/input.sock"
QMP_SOCKET="$TEST_DIR/qmp.sock"
UART_LOG="$TEST_DIR/uart.log"
VM_PID=

cleanup() {
  status=$?
  if [ "$status" -ne 0 ] && [ -n "$VM_PID" ]; then
    "$REPO_DIR/vm/capture-native-failure.sh" \
      "$TEST_DIR" "$SOCKET" "$QMP_SOCKET" || true
  fi
  if [ -n "$VM_PID" ]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
  fi
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$TEST_DIR"
NATIVE_VM_BUILD_DIR="$TEST_DIR" \
  "$REPO_DIR/vm/run-native-vm.sh" --headless --direct \
  >"$TEST_DIR/runner.log" 2>&1 &
VM_PID=$!

attempt=0
until [ "$attempt" -ge 80 ]; do
  if grep -q "Lefony OS: control ready" "$UART_LOG" 2>/dev/null &&
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
test "$attempt" -lt 80

test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" ping)" = PONG
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" \
  v1 1 STATE)" = "V1 1 STATE app=0 home_row=0 home_column=0"
grep -q "Lefony OS: entering calculator runtime" "$UART_LOG"
if grep -q "U-Boot" "$UART_LOG"; then
  echo "Direct developer boot unexpectedly traversed U-Boot" >&2
  exit 1
fi
python3 "$REPO_DIR/vm/qmp-screendump.py" \
  "$QMP_SOCKET" "$TEST_DIR/home.ppm"
test -s "$TEST_DIR/home.ppm"

echo "PASS: direct-ELF developer boot reaches the default Upsilon home state"
echo "Artifacts: $TEST_DIR"
