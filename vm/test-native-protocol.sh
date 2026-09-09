#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=${NATIVE_PROTOCOL_TEST_DIR:-}
if [ -z "$TEST_DIR" ]; then
  TEST_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-protocol.XXXXXX")
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

raw() {
  python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" raw "$@"
}
v1() {
  request_id=$1
  shift
  python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" v1 "$request_id" "$@"
}

test "$(v1 7 PING)" = "V1 7 PONG"
case "$(v1 8 INFO)" in
  "V1 8 INFO protocol=1 firmware=1.1.2-native build=f36520e0 platform=prime_g2_vm storage=1") ;;
  *) exit 1 ;;
esac
test "$(v1 9 STATE)" = "V1 9 STATE app=0 home_row=0 home_column=0"

before=$(v1 10 TIME GET | awk '{print $4}')
test "$(v1 11 TIME ADVANCE 60000)" = "V1 11 OK"
after=$(v1 12 TIME GET | awk '{print $4}')
test "$after" -ge $((before + 60000))

test "$(v1 13 KEY STATE 42)" = "V1 13 VALUE 0"
test "$(v1 14 KEY 42 1)" = "V1 14 OK"
test "$(v1 15 KEY STATE 42)" = "V1 15 VALUE 1"
test "$(v1 16 KEY 42 0)" = "V1 16 OK"
test "$(v1 17 KEY STATE 42)" = "V1 17 VALUE 0"
test "$(v1 18 STORAGE RESET 2>/dev/null || true)" = "V1 18 ERR confirmation required"
test "$(raw NOT_A_COMMAND 2>/dev/null || true)" = "ERR unknown command"
test "$(raw V1 nope PING 2>/dev/null || true)" = "ERR malformed envelope"

python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" \
  sequence up up up up left left left left >/dev/null
test "$(v1 29 STATE)" = "V1 29 STATE app=0 home_row=0 home_column=0"
python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" press ok >/dev/null
python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" sequence one plus two ok >/dev/null
test "$(v1 30 STATE)" = "V1 30 STATE app=1 home_row=0 home_column=0"
test "$(v1 31 RESULT INPUT)" = "V1 31 TEXT 1+2"
test "$(v1 32 RESULT EXACT)" = "V1 32 TEXT 3"
test "$(v1 34 RESULT APPROX)" = "V1 34 TEXT 3"
python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" press apps >/dev/null
test "$(v1 33 STATE)" = "V1 33 STATE app=0 home_row=0 home_column=0"

# A warm reset returns to Home while preserving user storage.
test "$(v1 35 STORAGE PUT warm.bin 7761726d)" = "V1 35 OK"
python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" press ok >/dev/null
test "$(v1 36 RESET WARM)" = "V1 36 OK"
sleep 0.2
test "$(v1 37 STATE)" = "V1 37 STATE app=0 home_row=0 home_column=0"
test "$(v1 38 STORAGE GET warm.bin)" = "V1 38 DATA 7761726d"

# Factory reset has a deliberate three-key confirmation gesture.
test "$(v1 39 KEY 42 1)" = "V1 39 OK"   # Shift
test "$(v1 40 KEY 56 1)" = "V1 40 OK"   # Alpha
test "$(v1 41 KEY 14 1)" = "V1 41 OK"   # Backspace
test "$(v1 42 STORAGE RESET)" = "V1 42 OK"
test "$(v1 43 STORAGE GET warm.bin 2>/dev/null || true)" = "V1 43 ERR not found"

echo "PASS: semantic protocol covers app/result/key/time/build, warm reset, and guarded storage reset"
echo "Artifacts: $TEST_DIR"
