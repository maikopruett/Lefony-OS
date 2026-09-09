#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DIR=${NATIVE_PROTOCOL_FUZZ_TEST_DIR:-$(mktemp -d "$REPO_DIR/build/prime-g2-protocol-fuzz.XXXXXX")}
PID=
cleanup() {
  code=$?
  if [ -n "$PID" ]; then kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; fi
  exit "$code"
}
trap cleanup EXIT HUP INT TERM
mkdir -p "$DIR"
NATIVE_VM_BUILD_DIR="$DIR" NATIVE_STORAGE_MODE=ephemeral \
  "$REPO_DIR/vm/run-native-vm.sh" --headless --direct >"$DIR/runner.log" 2>&1 &
PID=$!
for _ in $(seq 1 160); do
  [ -S "$DIR/input.sock" ] && grep -q "control ready" "$DIR/uart.log" 2>/dev/null && break
  kill -0 "$PID" 2>/dev/null || exit 1
  sleep 0.1
done
python3 "$REPO_DIR/vm/native-protocol-fuzz.py" --socket "$DIR/input.sock"
! grep -q "Lefony OS: abort" "$DIR/uart.log"
echo "Artifacts: $DIR"
