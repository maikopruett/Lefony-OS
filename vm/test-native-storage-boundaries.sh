#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ARTIFACT_DIR=${NATIVE_STORAGE_BOUNDARY_TEST_DIR:-}
if [ -z "$ARTIFACT_DIR" ]; then
  ARTIFACT_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-storage-boundaries.XXXXXX")
fi
INPUT_SOCKET="$ARTIFACT_DIR/input.sock"
RUNNER_LOG="$ARTIFACT_DIR/runner.log"
UART_LOG="$ARTIFACT_DIR/uart.log"
VM_PID=

cleanup() {
  if [ -n "$VM_PID" ]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$ARTIFACT_DIR"
NATIVE_VM_BUILD_DIR="$ARTIFACT_DIR" NATIVE_STORAGE_MODE=ephemeral \
  "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot \
  >"$RUNNER_LOG" 2>&1 &
VM_PID=$!

attempt=0
until [ "$attempt" -ge 80 ]; do
  if grep -q "Lefony OS: control ready" "$UART_LOG" 2>/dev/null &&
      [ -S "$INPUT_SOCKET" ]; then
    break
  fi
  if ! kill -0 "$VM_PID" 2>/dev/null; then
    sed -n '1,240p' "$RUNNER_LOG" >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep 0.25
done

if [ "$attempt" -ge 80 ]; then
  echo "Timed out waiting for native Upsilon; see $RUNNER_LOG" >&2
  exit 1
fi

test "$(python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
  raw STORAGE SELFTEST)" = OK

echo "PASS: Ion storage zero-length, maximum-size, duplicate, rename, delete, and out-of-space boundaries"
echo "Artifacts: $ARTIFACT_DIR"
