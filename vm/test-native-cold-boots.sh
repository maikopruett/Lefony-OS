#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=${NATIVE_COLD_BOOT_DIR:-"$REPO_DIR/build/prime-g2-native-cold-boots"}
BOOT_COUNT=${NATIVE_COLD_BOOT_COUNT:-25}
VM_PID=

cleanup_vm() {
  if [ -n "$VM_PID" ]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
    VM_PID=
  fi
}
trap cleanup_vm EXIT HUP INT TERM

case "$BOOT_COUNT" in
  ''|*[!0-9]*)
    echo "NATIVE_COLD_BOOT_COUNT must be a positive integer." >&2
    exit 2
    ;;
esac
if [ "$BOOT_COUNT" -lt 1 ]; then
  echo "NATIVE_COLD_BOOT_COUNT must be a positive integer." >&2
  exit 2
fi

mkdir -p "$TEST_DIR"
boot_number=1
while [ "$boot_number" -le "$BOOT_COUNT" ]; do
  boot_label=$(printf '%02d' "$boot_number")
  boot_dir="$TEST_DIR/boot-$boot_label"
  runner_log="$boot_dir/runner.log"
  uart_log="$boot_dir/uart.log"
  mkdir -p "$boot_dir"

  NATIVE_VM_BUILD_DIR="$boot_dir" NATIVE_STORAGE_MODE=ephemeral \
    "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot \
    >"$runner_log" 2>&1 &
  VM_PID=$!

  attempt=0
  until [ "$attempt" -ge 80 ]; do
    if [ -f "$uart_log" ] && \
        grep -q 'Lefony OS: entering calculator runtime' "$uart_log"; then
      break
    fi
    if ! kill -0 "$VM_PID" 2>/dev/null; then
      echo "Cold boot $boot_number exited before native startup:" >&2
      sed -n '1,200p' "$runner_log" >&2
      exit 1
    fi
    attempt=$((attempt + 1))
    sleep 0.25
  done
  if [ "$attempt" -ge 80 ]; then
    echo "Cold boot $boot_number timed out" >&2
    exit 1
  fi
  grep -q 'Lefony OS: verified native payload' "$uart_log"
  cleanup_vm
  printf 'PASS: cold boot %d/%d\n' "$boot_number" "$BOOT_COUNT"
  boot_number=$((boot_number + 1))
done

echo "PASS: $BOOT_COUNT consecutive native media cold boots"
echo "Artifacts: $TEST_DIR"
