#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_ROOT=${NATIVE_DISPLAY_FIDELITY_DIR:-}
if [ -z "$TEST_ROOT" ]; then
  TEST_ROOT=$(mktemp -d "$REPO_DIR/build/prime-g2-display-fidelity.XXXXXX")
fi
VM_PID=

cleanup_vm() {
  if [ -n "$VM_PID" ]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
    VM_PID=
  fi
}

cleanup() {
  status=$?
  cleanup_vm
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

run_case() {
  name=$1
  boot_mode=$2
  fault=$3
  expectation=$4
  panel_marker=$5
  case_dir="$TEST_ROOT/$name"
  mkdir -p "$case_dir"

  NATIVE_VM_BUILD_DIR="$case_dir" NATIVE_STORAGE_MODE=ephemeral \
    PRIME_G2_PANEL_FAULT="$fault" \
    "$REPO_DIR/vm/run-native-vm.sh" --headless "$boot_mode" \
    >"$case_dir/runner.log" 2>&1 &
  VM_PID=$!

  attempt=0
  while [ "$attempt" -lt 960 ]; do
    if grep -q "Lefony OS: control ready" "$case_dir/uart.log" 2>/dev/null &&
        [ -S "$case_dir/qmp.sock" ]; then
      break
    fi
    if ! kill -0 "$VM_PID" 2>/dev/null; then
      sed -n '1,240p' "$case_dir/runner.log" >&2
      exit 1
    fi
    attempt=$((attempt + 1))
    sleep 0.25
  done
  if [ "$attempt" -ge 960 ]; then
    echo "Timed out waiting for $name display state." >&2
    sed -n '1,240p' "$case_dir/runner.log" >&2
    exit 1
  fi

  if [ "$fault" = fifo ]; then
    python3 "$REPO_DIR/vm/qmp-screendump.py" \
      "$case_dir/qmp.sock" "$case_dir/underflow.ppm"
    python3 "$REPO_DIR/vm/inspect-ppm.py" \
      "$case_dir/underflow.ppm" --expect black
    grep -q "$panel_marker" "$case_dir/qemu.log"

    python3 "$REPO_DIR/vm/qmp-screendump.py" \
      "$case_dir/qmp.sock" "$case_dir/screen.ppm"
    python3 "$REPO_DIR/vm/inspect-ppm.py" \
      "$case_dir/screen.ppm" --expect visible
    grep -q "prime-g2-panel: LCDIF FIFO scanout restored" \
      "$case_dir/qemu.log"
  else
    python3 "$REPO_DIR/vm/qmp-screendump.py" \
      "$case_dir/qmp.sock" "$case_dir/screen.ppm"
    python3 "$REPO_DIR/vm/inspect-ppm.py" \
      "$case_dir/screen.ppm" --expect "$expectation"
    # A headless QEMU display is refreshed on demand by screendump. The refresh
    # evaluates all modeled hardware gates and emits the authoritative cause.
    grep -q "$panel_marker" "$case_dir/qemu.log"
  fi
  cleanup_vm
}

mkdir -p "$TEST_ROOT"
run_case direct-visible --direct none visible "prime-g2-panel: visible"
run_case capsule-visible --capsule none visible "prime-g2-panel: visible"
run_case spi-fault-white --direct spi white \
  "prime-g2-panel: ILI9322 is in standby or display-off state"
run_case iomux-fault-white --direct iomux white \
  "prime-g2-panel: IOMUXC display pad routing is invalid"
run_case signal-fault-white --direct signal white \
  "prime-g2-panel: panel signal timing violates electrical margins"
run_case timing-fault-white --direct timing white \
  "prime-g2-panel: pixel clock or sync porch timing is outside tolerance"
run_case polarity-fault-white --direct polarity white \
  "prime-g2-panel: pixel clock or sync polarity is invalid"
run_case power-fault-white --direct power white \
  "prime-g2-panel: ILI9322 power/reset timing is invalid"
run_case fifo-recovery --direct fifo visible \
  "prime-g2-panel: LCDIF FIFO underflow recovered"

direct_sha=$(shasum -a 256 "$TEST_ROOT/direct-visible/screen.ppm" | awk '{print $1}')
capsule_sha=$(shasum -a 256 "$TEST_ROOT/capsule-visible/screen.ppm" | awk '{print $1}')
if [ "$direct_sha" != "$capsule_sha" ]; then
  echo "Direct and capsule display output differ." >&2
  exit 1
fi

echo "PASS: physical panel path renders identically through direct and capsule boot"
echo "PASS: powered panel faults reproduce the diagnosed optical white screen"
echo "PASS: IOMUXC, signal, sync, polarity, and power faults are diagnosed"
echo "PASS: LCDIF FIFO underflow asserts status, blanks one frame, and recovers"
echo "Artifacts: $TEST_ROOT"
