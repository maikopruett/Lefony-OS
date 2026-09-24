#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=${NATIVE_SERVICES_TEST_DIR:-}
if [ -z "$TEST_DIR" ]; then
  TEST_DIR=$(mktemp -d "$REPO_DIR/build/prime-g2-native-services.XXXXXX")
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
  if grep -q "Lefony OS: control ready" "$LOG" 2>/dev/null && [ -S "$SOCKET" ]; then break; fi
  if ! kill -0 "$VM_PID" 2>/dev/null; then sed -n '1,240p' "$TEST_DIR/runner.log" >&2; exit 1; fi
  attempt=$((attempt + 1)); sleep 0.25
done
test "$attempt" -lt 160

raw() { python3 "$REPO_DIR/vm/prime-control.py" --socket "$SOCKET" raw "$@"; }

# TIME ADVANCE changes the modeled source before all ten ADC samples have
# passed through the normal two-phase filter. Wait for the exact steady value
# with a bound; an immediate intermediate average is not a driver failure.
await_voltage() {
  expected_voltage=$1
  voltage_attempt=0
  while [ "$voltage_attempt" -lt 30 ]; do
    observed_voltage=$(raw BATTERY VOLTAGE)
    if [ "$observed_voltage" = "VALUE $expected_voltage" ]; then return 0; fi
    voltage_attempt=$((voltage_attempt + 1))
    sleep 0.1
  done
  echo "Battery filter did not settle: $observed_voltage, expected VALUE $expected_voltage" >&2
  return 1
}

test "$(raw STACK SAFE)" = "VALUE 1"
test "$(raw TIME ROLLOVER SELFTEST)" = OK
test "$(raw BATTERY SET 2 3850 0)" = OK
test "$(raw BATTERY LEVEL)" = "VALUE 2"
test "$(raw BATTERY VOLTAGE)" = "VALUE 3853"
test "$(raw BATTERY ADC RAW)" = "VALUE 211"
test "$(raw BATTERY CHARGING)" = "VALUE 0"
test "$(raw BATTERY PERCENT)" = "VALUE 75"
test "$(raw BATTERY CALIBRATED)" = "VALUE 1"
test "$(raw BATTERY CHARGER OPERATION)" = "VALUE 2"
test "$(raw BATTERY CHARGER CONFIGURED)" = "VALUE 1"
test "$(raw TIME ADVANCE 600000)" = OK
await_voltage 3835
test "$(raw BATTERY SET 2 3800 1)" = OK
test "$(raw BATTERY VOLTAGE)" = "VALUE 3799"
test "$(raw BATTERY CHARGING)" = "VALUE 1"
test "$(raw TIME ADVANCE 100000)" = OK
await_voltage 3817
test "$(raw BATTERY SET 4 4200 0 2>/dev/null || true)" = "ERR invalid battery state"

# PF1550 power input, charger phase, and battery presence are independent.
# An absent cell in precharge must never be presented as actively charging.
test "$(raw BATTERY PF1550 SET 1 0 6)" = OK
test "$(raw BATTERY EXTERNAL)" = "VALUE 1"
test "$(raw BATTERY PRESENT)" = "VALUE 0"
test "$(raw BATTERY CHARGING)" = "VALUE 0"
test "$(raw BATTERY FULL)" = "VALUE 0"
test "$(raw BATTERY FAULT)" = "VALUE 0"
test "$(raw BATTERY CHARGER STATE)" = "VALUE 0"
test "$(raw BATTERY SENSE STATE)" = "VALUE 6"
sleep 0.3
no_battery_crc=$(raw DISPLAY CRC)

# A detected cell in precharge, CC, CV, or EOC is actively charging.
for charger_state in 0 1 2 3; do
  test "$(raw BATTERY PF1550 SET 1 "$charger_state" 4)" = OK
  test "$(raw BATTERY CHARGING)" = "VALUE 1"
  test "$(raw BATTERY PRESENT)" = "VALUE 1"
done
test "$(raw BATTERY TELEMETRY FRESH)" = "VALUE 1"
test "$(raw BATTERY PMIC AVAILABLE)" = "VALUE 1"

# A failed PF1550 refresh must revoke the previous charging/VBUS claim.  This
# is the regression for a charging icon that remained latched after unplug.
test "$(raw BATTERY PF1550 READ FAIL)" = OK
test "$(raw BATTERY EXTERNAL)" = "VALUE 0"
test "$(raw BATTERY CHARGING)" = "VALUE 0"
test "$(raw BATTERY TELEMETRY FRESH)" = "VALUE 0"
test "$(raw BATTERY PMIC AVAILABLE)" = "VALUE 0"
test "$(raw BATTERY PF1550 SET 1 3 4)" = OK
test "$(raw BATTERY CHARGING)" = "VALUE 1"
sleep 0.3
charging_crc=$(raw DISPLAY CRC)
test "$charging_crc" != "$no_battery_crc"

# DONE is full and externally powered, but no longer drawing charge current.
test "$(raw BATTERY PF1550 SET 1 4 4)" = OK
test "$(raw BATTERY EXTERNAL)" = "VALUE 1"
test "$(raw BATTERY CHARGING)" = "VALUE 0"
test "$(raw BATTERY FULL)" = "VALUE 1"
test "$(raw BATTERY LEVEL)" = "VALUE 3"
sleep 0.3
full_crc=$(raw DISPLAY CRC)
test "$full_crc" != "$charging_crc"

# Every documented fault/suspend state remains distinct from active charging.
for charger_state in 6 7 9 10 12; do
  test "$(raw BATTERY PF1550 SET 1 "$charger_state" 4)" = OK
  test "$(raw BATTERY CHARGING)" = "VALUE 0"
  test "$(raw BATTERY FULL)" = "VALUE 0"
  test "$(raw BATTERY FAULT)" = "VALUE 1"
done
sleep 0.3
fault_crc=$(raw DISPLAY CRC)
test "$fault_crc" != "$full_crc"

test "$(raw BATTERY PF1550 SET 0 8 0)" = OK
test "$(raw BATTERY EXTERNAL)" = "VALUE 0"
test "$(raw BATTERY PRESENT)" = "VALUE 1"
test "$(raw BATTERY CHARGING)" = "VALUE 0"
test "$(raw BATTERY FAULT)" = "VALUE 0"

test "$(raw RTC SET 2024 2 28 23 59 59 2)" = OK
test "$(raw TIME ADVANCE 2000)" = OK
test "$(raw RTC DATE)" = "VALUE 20240229"
test "$(raw RTC TIME)" = "VALUE 1"
test "$(raw RTC SET 2023 2 29 0 0 0 2 2>/dev/null || true)" = "ERR invalid rtc value"
test "$(raw TOUCH STATUS)" = "VALUE 1"
test "$(raw TOUCH PRODUCT)" = "VALUE 5688"

test "$(raw LED SET 63488)" = OK
test "$(raw LED COLOR)" = "VALUE 63488"
test "$(raw LED BLINK 750 25)" = OK
test "$(raw LED PERIOD)" = "VALUE 750"
test "$(raw LED DUTY)" = "VALUE 25"
test "$(raw POWER PANEL)" = "VALUE 7939"

# Exercise the native idle policy with a separate deterministic idle-clock
# offset: dim at 45 seconds, suspend at 55 seconds, then reconstruct on wake.
# Calendar TIME ADVANCE above refreshes PF1550 sense registers from the modeled
# source, whose earlier charging fixture still had external power connected.
# Idle is intentionally inhibited on external power. Unplug that source first.
test "$(raw BATTERY SET 2 3850 0)" = OK
test "$(raw BATTERY EXTERNAL)" = "VALUE 0"
test "$(raw BRIGHTNESS SET 210)" = OK
test "$(raw POWER IDLE ADVANCE 45000)" = OK
idle_brightness=$(raw BRIGHTNESS GET | awk '{print $2}')
test "$idle_brightness" -le 15
test "$(raw POWER IDLE ADVANCE 10000)" = OK
test "$(raw POWER STATE)" = "VALUE 1"
test "$(raw POWER HARDWARE)" = "VALUE 1"
test "$(raw POWER RESUME)" = OK
test "$(raw POWER STATE)" = "VALUE 0"
test "$(raw POWER HARDWARE)" = "VALUE 2"
test "$(raw BRIGHTNESS GET)" = "VALUE 210"
test "$(raw DISPLAY GUARDS)" = OK

test "$(raw POWER STATE)" = "VALUE 0"
test "$(raw BATTERY SET 2 3850 0)" = OK
test "$(raw STORAGE PUT suspend.bin 73757276697665)" = OK
before=$(raw POWER COUNT | awk '{print $2}')
test "$(raw POWER SUSPEND)" = OK
test "$(raw POWER STATE)" = "VALUE 1"
test "$(raw POWER HARDWARE)" = "VALUE 1"
test "$(raw TIME ADVANCE 3600000)" = OK
test "$(raw BATTERY VOLTAGE)" = "VALUE 3853"
after=$(raw POWER COUNT | awk '{print $2}')
test "$after" -eq $((before + 1))
test "$(raw POWER RESUME)" = OK
test "$(raw POWER STATE)" = "VALUE 0"
test "$(raw POWER HARDWARE)" = "VALUE 2"
test "$(raw STORAGE GET suspend.bin)" = "DATA 73757276697665"
test "$(raw DISPLAY GUARDS)" = OK
test "$(raw DISPLAY SELFTEST)" = "VALUE 0"

i=0
while [ "$i" -lt 10 ]; do
  test "$(raw POWER BUTTON 100)" = OK
  test "$(raw POWER STATE)" = "VALUE 1"
  test "$(raw POWER BUTTON 100)" = OK
  test "$(raw POWER STATE)" = "VALUE 0"
  i=$((i + 1))
done

# Orderly long-press off is terminal until reset; the UART remains available
# solely so the test can prove that a powered-off VM cannot falsely resume.
test "$(raw POWER BUTTON 2500)" = OK
test "$(raw POWER OFF)" = "VALUE 1"
test "$(raw POWER HARDWARE)" = "VALUE 5"
test "$(raw POWER PMIC)" = "VALUE 45058"
test "$(raw POWER RESUME 2>/dev/null || true)" = "ERR powered off"

echo "PASS: PF1550 energy, leap-year RTC, LED, real idle dim/suspend, storage-safe suspend, peripheral reconstruction, rapid wake, and orderly off"
echo "Artifacts: $TEST_DIR"
