#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ROOT=${NATIVE_RUNTIME_TEST_DIR:-$(mktemp -d "$REPO_DIR/build/prime-g2-runtime.XXXXXX")}
PID=

stop_vm() {
  if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
    PID=
  fi
}
trap stop_vm EXIT HUP INT TERM

start_vm() {
  name=$1
  DIR="$ROOT/$name"
  mkdir -p "$DIR"
  NATIVE_VM_BUILD_DIR="$DIR" NATIVE_STORAGE_MODE=ephemeral \
    "$REPO_DIR/vm/run-native-vm.sh" --headless --direct \
    >"$DIR/runner.log" 2>&1 &
  PID=$!
  for _ in $(seq 1 120); do
    if [ -S "$DIR/input.sock" ] &&
       grep -q "Lefony OS: control ready" "$DIR/uart.log" 2>/dev/null; then
      return
    fi
    kill -0 "$PID" 2>/dev/null || {
      sed -n '1,240p' "$DIR/runner.log" >&2
      exit 1
    }
    sleep 0.1
  done
  echo "native runtime VM did not become ready" >&2
  exit 1
}

v1() {
  id=$1
  shift
  python3 "$REPO_DIR/vm/prime-control.py" --socket "$DIR/input.sock" \
    v1 "$id" "$@"
}

start_vm runtime
test "$(v1 1 SYSTEM SELFTEST)" = "V1 1 OK"
test "$(v1 2 SYSTEM TYPE NULL)" = "V1 2 VALUE 0"
test "$(v1 3 SYSTEM TYPE CODE)" = "V1 3 VALUE 1"
test "$(v1 4 SYSTEM TYPE DATA)" = "V1 4 VALUE 2"
test "$(v1 5 SYSTEM TYPE DEVICE)" = "V1 5 VALUE 3"
test "$(v1 6 SYSTEM TYPE FRAMEBUFFER)" = "V1 6 VALUE 4"
test "$(v1 7 IRQ SELFTEST)" = "V1 7 OK"

tick_before=$(v1 8 TIMER IRQ TICKS | awk '{print $4}')
sleep 0.1
tick_after=$(v1 9 TIMER IRQ TICKS | awk '{print $4}')
test "$tick_after" -gt "$tick_before"

kpp_before=$(v1 10 IRQ COUNT 114 | awk '{print $4}')
test "$(v1 11 IRQ INJECT 114)" = "V1 11 OK"
sleep 0.05
kpp_after=$(v1 12 IRQ COUNT 114 | awk '{print $4}')
test "$kpp_after" -gt "$kpp_before"
test "$(v1 13 IRQ UNHANDLED)" = "V1 13 VALUE 0"
feeds_before=$(v1 14 WATCHDOG FEEDS | awk '{print $4}')
sleep 0.4
feeds_after=$(v1 15 WATCHDOG FEEDS | awk '{print $4}')
test "$feeds_after" -gt "$feeds_before"
test "$(v1 16 WATCHDOG STATUS)" = "V1 16 VALUE 1"
test "$(v1 17 HEAP SELFTEST)" = "V1 17 OK"
heap_capacity=$(v1 18 HEAP CAPACITY | awk '{print $4}')
heap_highwater=$(v1 19 HEAP HIGHWATER | awk '{print $4}')
test "$heap_capacity" -gt 1000000
test "$heap_highwater" -gt 1000000
test "$heap_highwater" -le "$heap_capacity"
test "$(v1 20 HEAP CURRENT)" = "V1 20 VALUE 0"
stack_capacity=$(v1 21 STACK CAPACITY | awk '{print $4}')
stack_highwater=$(v1 22 STACK HIGHWATER | awk '{print $4}')
test "$stack_highwater" -gt 0
test "$stack_highwater" -lt "$stack_capacity"
stop_vm

for kind in DEADLOCK IRQ_STORM INFINITE; do
  start_vm "watchdog-$kind"
  test "$(v1 25 WATCHDOG HANG "$kind")" = "V1 25 OK"
  expired=false
  for _ in $(seq 1 60); do
    if ! kill -0 "$PID" 2>/dev/null; then
      expired=true
      break
    fi
    sleep 0.1
  done
  if [ "$expired" != true ]; then
    echo "watchdog did not reset $kind" >&2
    exit 1
  fi
  wait "$PID" 2>/dev/null || true
  PID=
done

# A fresh cache/MMU startup after a hardware-reset path must remain healthy.
start_vm warm-restart
test "$(v1 30 SYSTEM SELFTEST)" = "V1 30 OK"
test "$(v1 31 DISPLAY SELFTEST)" = "V1 31 VALUE 0"
stop_vm

echo "PASS: MMU/cache attributes, GIC dispatch, interrupt timer, KPP IRQ, watchdog health feeding, three hang resets, and restart"
echo "Artifacts: $ROOT"
