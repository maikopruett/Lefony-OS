#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SMOKE_DIR=${NATIVE_VM_TEST_DIR:-"$REPO_DIR/build/prime-g2-native-smoke"}
INPUT_SOCKET="$SMOKE_DIR/input.sock"
QMP_SOCKET="$SMOKE_DIR/qmp.sock"
UART_LOG="$SMOKE_DIR/uart.log"
RUNNER_LOG="$SMOKE_DIR/runner.log"
VM_PID=

cleanup() {
  status=$?
  if [ "$status" -ne 0 ] && [ -n "$VM_PID" ]; then
    "$REPO_DIR/vm/capture-native-failure.sh" "$SMOKE_DIR" "$INPUT_SOCKET" "$QMP_SOCKET" || true
  fi
  if [ -n "$VM_PID" ]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
  fi
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$SMOKE_DIR"
rm -f "$SMOKE_DIR/home.ppm" "$SMOKE_DIR/right.ppm" \
  "$SMOKE_DIR/calculation.ppm" "$SMOKE_DIR/result.ppm" \
  "$SMOKE_DIR/touch-home.ppm" "$SMOKE_DIR/touch-open.ppm" "$RUNNER_LOG"

NATIVE_VM_BUILD_DIR="$SMOKE_DIR" NATIVE_STORAGE_MODE=ephemeral \
  "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot \
  >"$RUNNER_LOG" 2>&1 &
VM_PID=$!

attempt=0
until [ "$attempt" -ge 40 ]; do
  if grep -q "Lefony OS: control ready" "$UART_LOG" 2>/dev/null && \
      [ -S "$INPUT_SOCKET" ]; then
    break
  fi
  if ! kill -0 "$VM_PID" 2>/dev/null; then
    echo "Native VM exited before becoming ready:" >&2
    sed -n '1,240p' "$RUNNER_LOG" >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep 0.25
done
if [ "$attempt" -ge 40 ]; then
  echo "Timed out waiting for native Lefony OS; see $RUNNER_LOG" >&2
  exit 1
fi
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" ping)" = PONG

grep -q "U-Boot 2026.07" "$UART_LOG"
grep -q "Lefony OS: loading native payload from mmc 0:1" "$UART_LOG"
grep -Eq "[0-9]+ bytes read in [0-9]+ ms" "$UART_LOG"
grep -q "Lefony OS: verified native payload" "$UART_LOG"
grep -q "Lefony OS: starting from boot media" "$UART_LOG"
grep -q "Lefony OS: entering calculator runtime" "$UART_LOG"

python3 "$REPO_DIR/vm/qmp-screendump.py" "$QMP_SOCKET" "$SMOKE_DIR/home.ppm"
python3 "$REPO_DIR/vm/inspect-ppm.py" "$SMOKE_DIR/home.ppm" \
  --expect visible --color-tolerance 5 \
  --require-color ffffff:40000 --require-color 466645:5000
python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" press right >/dev/null
sleep 0.15
python3 "$REPO_DIR/vm/qmp-screendump.py" "$QMP_SOCKET" "$SMOKE_DIR/right.ppm"
if python3 "$REPO_DIR/vm/ppm-content-compare.py" \
    "$SMOKE_DIR/home.ppm" "$SMOKE_DIR/right.ppm"; then
  echo "D-pad input did not change the home screen" >&2
  exit 1
fi

python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" press left >/dev/null
python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" press ok >/dev/null
sleep 0.15
python3 "$REPO_DIR/vm/qmp-screendump.py" "$QMP_SOCKET" "$SMOKE_DIR/calculation.ppm"
if python3 "$REPO_DIR/vm/ppm-content-compare.py" \
    "$SMOKE_DIR/home.ppm" "$SMOKE_DIR/calculation.ppm"; then
  echo "OK input did not open the Calculation app" >&2
  exit 1
fi

python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  sequence one plus two ok >/dev/null
sleep 0.15
python3 "$REPO_DIR/vm/qmp-screendump.py" "$QMP_SOCKET" "$SMOKE_DIR/result.ppm"
if python3 "$REPO_DIR/vm/ppm-content-compare.py" \
    "$SMOKE_DIR/calculation.ppm" "$SMOKE_DIR/result.ppm"; then
  echo "Calculation input did not change the display" >&2
  exit 1
fi

# Exercise the Goodix I2C model and the native report parser, rather than an
# Ion-event shortcut: the tapped cell is selected and opened on release.
python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" press apps >/dev/null
sleep 0.15
python3 "$REPO_DIR/vm/qmp-screendump.py" "$QMP_SOCKET" "$SMOKE_DIR/touch-home.ppm"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" tap 160 120)" = OK
sleep 0.2
python3 "$REPO_DIR/vm/qmp-screendump.py" "$QMP_SOCKET" "$SMOKE_DIR/touch-open.ppm"
if python3 "$REPO_DIR/vm/ppm-content-compare.py" \
    "$SMOKE_DIR/touch-home.ppm" "$SMOKE_DIR/touch-open.ppm"; then
  echo "Goodix touch report did not open the tapped home app" >&2
  exit 1
fi

echo "PASS: U-Boot -> native Lefony OS -> LCD/keypad/Goodix/calculation emulator smoke test"
echo "Artifacts: $SMOKE_DIR"
