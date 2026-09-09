#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -n "${NATIVE_TOUCH_TEST_DIR:-}" ]; then
  TEST_DIR=$NATIVE_TOUCH_TEST_DIR
  mkdir -p "$TEST_DIR"
else
  TEST_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-touch.XXXXXX")
fi
SOCKET="$TEST_DIR/input.sock"
LOG="$TEST_DIR/uart.log"
VM_PID=
cleanup() {
  status=$?
  if [ -n "$VM_PID" ]; then kill "$VM_PID" 2>/dev/null || true; wait "$VM_PID" 2>/dev/null || true; fi
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

NATIVE_VM_BUILD_DIR="$TEST_DIR" NATIVE_VM_SOCKET_DIR="$TEST_DIR" \
NATIVE_STORAGE_MODE=ephemeral \
  "$REPO_DIR/vm/run-native-vm.sh" --headless --direct \
  >"$TEST_DIR/runner.log" 2>&1 &
VM_PID=$!
attempt=0
until [ "$attempt" -ge 160 ]; do
  if grep -q "Lefony OS: control ready" "$LOG" 2>/dev/null && [ -S "$SOCKET" ]; then break; fi
  if ! kill -0 "$VM_PID" 2>/dev/null; then sed -n '1,240p' "$TEST_DIR/runner.log" >&2; exit 1; fi
  attempt=$((attempt + 1)); sleep 0.1
done
test "$attempt" -lt 160
raw() { python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" raw "$@"; }

test "$(raw TOUCH STATUS)" = "VALUE 1"
test "$(raw TOUCH PRODUCT)" = "VALUE 5688"
before=$(raw TOUCH SEQUENCE | awk '{print $2}')
test "$(raw TAP 100 110)" = OK
sleep 0.15
test "$(raw TOUCH X)" = "VALUE 100"
test "$(raw TOUCH Y)" = "VALUE 110"
test "$(raw TOUCH CANCELLED)" = "VALUE 0"
after=$(raw TOUCH SEQUENCE | awk '{print $2}')
test "$after" -ge $((before + 2))

test "$(raw HOLD 120 120 700)" = OK
sleep 0.85
duration=$(raw TOUCH DURATION | awk '{print $2}')
# The model schedules release 700 ms after injection. Guest observation starts
# when its bounded poll consumes the first report, so allow one poll interval
# of bounded polling latency while still proving this is a hold rather than a
# tap. Physical calibration remains a target gate.
test "$duration" -ge 300
test "$duration" -le 850

# The native parser rejects bad contacts/coordinates and recovers on the next
# valid report without retaining a half-gesture.
test "$(raw TAP 400 120)" = OK
sleep 0.15
test "$(raw TOUCH CANCELLED)" = "VALUE 1"
test "$(raw TOUCH FAULT 2)" = OK
test "$(raw TAP 120 120)" = OK
sleep 0.15
test "$(raw TOUCH CANCELLED)" = "VALUE 1"
test "$(raw TOUCH FAULT 0)" = OK

# Missing controller and reset/re-detection path.
test "$(raw TOUCH FAULT 1)" = OK
test "$(raw TOUCH REINIT)" = "VALUE 0"
test "$(raw TOUCH FAULT 0)" = OK
test "$(raw TOUCH REINIT)" = "VALUE 1"

# Lost IRQ must not lose reports because the native driver has a bounded poll
# fallback. A KPP event during the same contact must release independently.
test "$(raw TOUCH FAULT 3)" = OK
test "$(raw HOLD 160 120 300)" = OK
python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" down right >/dev/null
python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" up right >/dev/null
sleep 0.4
test "$(raw KEY STATE 106)" = "VALUE 0"
test "$(raw TOUCH CANCELLED)" = "VALUE 0"
test "$(raw TOUCH FAULT 0)" = OK

echo "PASS: Goodix coordinates, tap/hold timing, bounds/cancellation, missing/malformed/lost-IRQ recovery, and simultaneous KPP input"
echo "Artifacts: $TEST_DIR"
