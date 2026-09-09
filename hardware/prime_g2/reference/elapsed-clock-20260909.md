# Sleep-aware battery scheduling — 2026-09-09

Battery sampling, charger polling, and percentage-change hold deadlines now
use `PrimeG2::Timing::elapsedMillis()`. This is a main-loop elapsed-time API,
not the user-adjustable calendar and not a new battery capacity estimator.

The physical implementation accumulates the full 47-bit, 32.768 kHz SNVS
counter. This hardware remains available when GPT stops or the CPU sleeps.
Unlike the previous battery-specific wrapper, it does not discard all but
one second of a long interval or lose multi-day sleep across a low-word wrap.
Two matching full reads handle the SNVS asynchronous clock domain; failed
reads leave elapsed time unchanged and are bounded.

The OS calendar setter accounts for elapsed time before rewriting SNVS,
then rebases the counter reference without changing accumulated duration.
Supported forward/backward calendar changes therefore do not move battery
deadlines. Uncoordinated external writes to the RTC are not calendar changes
supported by this API. The pure counter helper also ignores an unexpected
backwards reset rather than treating it as decades of sleep.

After a long sleep, existing overdue battery work runs on the next service
poll, then schedules its next deadline from now; it does not replay thousands
of missed samples. This change does not add periodic wake alarms, alter
Shift-Off, or change the GPT clock, charging policy, or voltage calibration.
The legacy emulator-target TIME ADVANCE facility is retained; the physical
firmware in the hardware emulator uses the real SNVS-based path.

## Tests

- `tests/test_prime_battery_clock.py`: compiled C++ elapsed arithmetic,
  calendar rebases both directions, low-word/full-width rollover, stopped
  clock, two-day sleep, backwards reset, and fractional accumulation;
  checks calendar-setter ordering and battery scheduling integration.
- `tests/test_prime_g2_usb_diag.py`: read-only, versioned 64-bit elapsed
  diagnostic at vendor request `0x55`, value `2` (magic `0x3143544c`).
- `vm/test-prime-main-timer.py --elapsed`: complete physical-firmware boot,
  GPT/millisecond progression, elapsed-time/SNVS comparison over USB.
- `vm/test-prime-battery-usb.py`: deliberately stopped GPT, live battery
  sampling, stable full-battery display, and a simulated two-day sleep gap
  with the guest CPU paused while the hardware counter advances.

The synthetic sleep-gap test is not a physical power-button suspend test.
Calendar rebasing is covered by compiled arithmetic and integration checks;
the test does not change the user's physical calculator date/time.

## Candidate

- Build: `260909-042559-66e806`.
- SHA-256: `81492f50c85d75517a07d76d6b4e8971e164d6a645a2a989601944cec03037fb`.
- Size: 2,103,216 bytes.
- 102 targeted unit tests passed; main/elapsed clock emulator test passed.
- Battery emulator passed with GPT stopped and a 172,800,014 ms synthetic
  sleep gap; full-battery display remained stable.
- History: `20260909T042751073334Z-recovery-capsule-81492f50c85d`.
- Native installation completed with byte-for-byte NAND readback matching
  the capsule hash; normal reboot returned native USB without user reset.
- Physical `vm/test-prime-main-timer.py --physical --elapsed` passed ten
  successive GPT/millisecond and elapsed/SNVS comparisons: main timer advanced
  10,391 ms over 10.391 host seconds.
- Postboot USB: valid ADC 229 / 4,178 mV, battery FULL / 100%, elapsed time
  19,491 ms while main time was 19,506 ms (separate initialization origins).
- No U-Boot changes. Physical calendar setting and unplugged suspend/resume
  were not exercised; those remain user-observation checks.
