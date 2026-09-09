#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=${NATIVE_PREFERENCES_TEST_DIR:-}
if [ -z "$TEST_DIR" ]; then
  TEST_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-preferences.XXXXXX")
fi
SOCKET="$TEST_DIR/input.sock"
LOG="$TEST_DIR/uart.log"
OVERLAY="$TEST_DIR/preferences.qcow2"
VM_PID=

stop_vm() {
  if [ -n "$VM_PID" ]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
    VM_PID=
  fi
}
trap stop_vm EXIT HUP INT TERM

start_vm() {
  NATIVE_VM_BUILD_DIR="$TEST_DIR" NATIVE_STORAGE_MODE=persistent \
    NATIVE_STORAGE_OVERLAY="$OVERLAY" \
    "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot \
    >"$TEST_DIR/runner.log" 2>&1 &
  VM_PID=$!
  attempt=0
  until [ "$attempt" -ge 80 ]; do
    if grep -q "Lefony OS: control ready" "$LOG" 2>/dev/null && \
        [ -S "$SOCKET" ]; then
      return
    fi
    if ! kill -0 "$VM_PID" 2>/dev/null; then
      sed -n '1,220p' "$TEST_DIR/runner.log" >&2
      exit 1
    fi
    attempt=$((attempt + 1))
    sleep 0.25
  done
  echo "Timed out waiting for native preferences VM" >&2
  exit 1
}

raw() {
  python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" raw "$@"
}

mkdir -p "$TEST_DIR"
start_vm
test "$(raw PREF GET ANGLE)" = "VALUE 0"
test "$(raw PREF GET DIGITS)" = "VALUE 7"
test "$(raw PREF SET ANGLE 2)" = OK
test "$(raw PREF SET DIGITS 11)" = OK
test "$(raw PREF SET AUTOCOMPLETE 0)" = OK
test "$(raw PREF SET FONT 1)" = OK
test "$(raw DATA SET 0 0 0 0 99)" = OK
test "$(raw DATA SET 1 0 0 0 88)" = OK
test "$(raw STORAGE COMMIT)" = OK
test "$(raw STORAGE COMMIT)" = OK
stop_vm

start_vm
test "$(raw PREF GET ANGLE)" = "VALUE 2"
test "$(raw PREF GET DIGITS)" = "VALUE 11"
test "$(raw PREF GET AUTOCOMPLETE)" = "VALUE 0"
test "$(raw PREF GET FONT)" = "VALUE 1"
test "$(raw DATA GET 0 0 0 0)" = "VALUE 99"
test "$(raw DATA GET 1 0 0 0)" = "VALUE 88"
test "$(raw STORAGE RESET CONFIRM)" = OK
test "$(raw PREF GET ANGLE)" = "VALUE 0"
test "$(raw PREF GET DIGITS)" = "VALUE 7"
test "$(raw PREF GET AUTOCOMPLETE)" = "VALUE 1"
test "$(raw PREF GET FONT)" = "VALUE 0"
test "$(raw DATA GET 0 0 0 0 2>/dev/null || true)" = "ERR dataset value unavailable"
test "$(raw DATA GET 1 0 0 0 2>/dev/null || true)" = "ERR dataset value unavailable"
stop_vm

start_vm
test "$(raw PREF GET ANGLE)" = "VALUE 0"
test "$(raw PREF GET DIGITS)" = "VALUE 7"
test "$(raw PREF GET AUTOCOMPLETE)" = "VALUE 1"
test "$(raw PREF GET FONT)" = "VALUE 0"
test "$(raw DATA GET 0 0 0 0 2>/dev/null || true)" = "ERR dataset value unavailable"
grep -Eq "Lefony storage: (loaded|recovered one valid slot)" "$LOG"

echo "PASS: native preferences persisted and factory reset restored defaults"
echo "Artifacts: $TEST_DIR"
