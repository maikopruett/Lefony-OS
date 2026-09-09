#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ARTIFACT_DIR=${NATIVE_PERSISTENCE_TEST_DIR:-}
if [ -z "$ARTIFACT_DIR" ]; then
  ARTIFACT_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-persistence.XXXXXX")
fi
INPUT_SOCKET="$ARTIFACT_DIR/input.sock"
UART_LOG="$ARTIFACT_DIR/uart.log"
RUNNER_LOG="$ARTIFACT_DIR/runner.log"
OVERLAY="$ARTIFACT_DIR/storage.qcow2"
VM_PID=

stop_vm() {
  if [ -n "$VM_PID" ]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
    VM_PID=
  fi
}

cleanup() {
  stop_vm
}
trap cleanup EXIT HUP INT TERM

start_vm() {
  NATIVE_VM_BUILD_DIR="$ARTIFACT_DIR" \
    NATIVE_STORAGE_MODE=persistent \
    NATIVE_STORAGE_OVERLAY="$OVERLAY" \
    "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot \
    >"$RUNNER_LOG" 2>&1 &
  VM_PID=$!

  attempt=0
  until [ "$attempt" -ge 80 ]; do
    if grep -q "Lefony OS: control ready" "$UART_LOG" 2>/dev/null && \
        [ -S "$INPUT_SOCKET" ]; then
      return
    fi
    if ! kill -0 "$VM_PID" 2>/dev/null; then
      echo "Native VM exited before becoming ready:" >&2
      sed -n '1,240p' "$RUNNER_LOG" >&2
      exit 1
    fi
    attempt=$((attempt + 1))
    sleep 0.25
  done
  echo "Timed out waiting for native Upsilon; see $RUNNER_LOG" >&2
  exit 1
}

mkdir -p "$ARTIFACT_DIR"
VALUE=4d6168616c6f

start_vm
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE PUT persist.bin "$VALUE")" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE PUT variable.exp 766172)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE PUT function.func 66756e63)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE PUT script.py 7072696e74283129)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE PUT list.exp 6c697374)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE PUT matrix.exp 6d6174726978)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE PUT statistics.stat 73746174)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE PUT regression.reg 726567)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE COMPAT SET 0 123456)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw DATA SET 0 0 0 0 12)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw DATA SET 0 0 1 0 3)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw DATA SET 1 1 0 0 7)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw DATA SET 1 1 1 0 21)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE GET persist.bin)" = "DATA $VALUE"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE COMMIT)" = OK
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE COMMIT)" = OK
cp "$UART_LOG" "$ARTIFACT_DIR/first-boot-uart.log"

# Stop without asking the guest to shut down. The committed generation must
# remain readable after this abrupt VM power loss.
stop_vm
start_vm
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE GET persist.bin)" = "DATA $VALUE"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE GET variable.exp)" = "DATA 766172"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE GET function.func)" = "DATA 66756e63"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE GET script.py)" = "DATA 7072696e74283129"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE GET list.exp)" = "DATA 6c697374"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE GET matrix.exp)" = "DATA 6d6174726978"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE GET statistics.stat)" = "DATA 73746174"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE GET regression.reg)" = "DATA 726567"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE COMPAT GET 0)" = "VALUE 123456"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw DATA GET 0 0 0 0)" = "VALUE 12"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw DATA GET 0 0 1 0)" = "VALUE 3"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw DATA GET 1 1 0 0)" = "VALUE 7"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw DATA GET 1 1 1 0)" = "VALUE 21"
grep -q "Lefony storage: loaded" "$UART_LOG"

cp "$UART_LOG" "$ARTIFACT_DIR/second-boot-uart.log"
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE CORRUPT ACTIVE)" = OK
stop_vm
start_vm
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE GET persist.bin)" = "DATA $VALUE"
grep -q "Lefony storage: recovered one valid slot" "$UART_LOG"

test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE CORRUPT ACTIVE)" = OK
stop_vm
start_vm
test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE GET persist.bin 2>/dev/null || true)" = "ERR not found"
grep -q "Lefony storage: initialized defaults" "$UART_LOG"

echo "PASS: native Ion storage survived reboot and recovered from slot corruption"
echo "Artifacts: $ARTIFACT_DIR"
