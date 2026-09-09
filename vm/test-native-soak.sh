#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DIR=${NATIVE_SOAK_TEST_DIR:-$(mktemp -d "$REPO_DIR/build/prime-g2-soak.XXXXXX")}
PID=
cleanup() {
  code=$?
  if [ -n "$PID" ]; then kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; fi
  exit "$code"
}
trap cleanup EXIT HUP INT TERM
mkdir -p "$DIR"
NATIVE_VM_BUILD_DIR="$DIR" NATIVE_STORAGE_MODE=ephemeral \
  "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot >"$DIR/runner.log" 2>&1 &
PID=$!
for _ in $(seq 1 200); do
  [ -S "$DIR/input.sock" ] && grep -q "control ready" "$DIR/uart.log" 2>/dev/null && break
  kill -0 "$PID" 2>/dev/null || exit 1
  sleep 0.1
done
python3 "$REPO_DIR/vm/native-soak-test.py" --socket "$DIR/input.sock" \
  --hours 24 --output "$DIR/metrics.json"
! grep -q "Lefony OS: abort" "$DIR/uart.log"
echo "PASS: 24 hours of accelerated virtual time with UI, storage, power, display, watchdog, heap, and stack checks"
echo "Artifacts: $DIR"
