# Physical main-timer repair — 2026-09-09

## Observed failure

On installed build `260909-035513-3ea47d`, repeated read-only native USB
requests returned `millis=1116`, `GPT_CNT=3350933`, `GPT_CR=0x749`, and
`GPT_PR=0`. SNVS RTC and battery diagnostics continued advancing. The new
`vm/test-prime-main-timer.py --physical` regression failed on this firmware
because both GPT and milliseconds were stationary.

## Change

The timer now explicitly selects the 24 MHz oscillator for CCM PERCLK,
divide-by-one, before enabling GPT. GPT source selector 2 uses that clock
with its ordinary prescaler set to 7 (divide-by-eight): 3 MHz. Emulator and
physical builds use the same configuration (`GPT_CR=0x289`, `GPT_PR=7`).

Previously, physical builds selected the separate GPT oscillator input
(selector 5), assumed 3 MHz, and left both prescalers at zero. Linux and
the original Prime U-Boot program PRE24M to 7 for their selector-5 3 MHz
configuration. See the [Linux GPT driver](https://github.com/torvalds/linux/blob/master/drivers/clocksource/timer-imx-gpt.c)
and local `build/lefony-prime-g2-u-boot/arch/arm/mach-imx/timer.c`.

This establishes a working replacement clock path. It does **not** isolate
whether the old freeze was caused by the oscillator-input configuration,
inherited state, or the later PERCLK change during backlight setup. Do not
claim that the prescaler mismatch alone explains a stopped counter.

The bounded runtime-delay fallback and independent SNVS battery timebase
remain intact. Clock visibility, charger behavior, and U-Boot are unchanged.

## Qualification

- Build: `260909-040941-f4f9cc`.
- Capsule SHA-256: `df49042a09b2726c9438e599b8a9e381f11775d45c673768f170fdd4a160b2ab`.
- Capsule length: 2,103,216 bytes.
- History: `20260909T041131208881Z-recovery-capsule-df49042a09b2`.
- 101 targeted unit tests passed.
- Emulator: complete physical-target NAND/UI startup; ten successive
  live-counter checks and correct GPT-to-millisecond conversion passed.
  SNVS uses wall/RTC time while GPT uses virtual time in this emulator, so
  strict cross-clock rate comparison applies only to physical hardware.
- Battery emulator regression passed, including deliberately stopping GPT,
  ADC completion via SNVS, and stable full-battery display across PMIC polls.
- Native installation completed with byte-for-byte NAND readback matching
  the capsule hash. No U-Boot writes.
- Normal reboot was requested; native USB returned without a manual reset.
- Physical: ten successive samples advanced from 6,397 to 16,591 ms over
  10.194 host seconds. Each GPT/millis delta agreed with independent SNVS
  elapsed time; e.g. 1,017 ms versus 1,017.33 ms. Test passed.
- Postboot telemetry: LCDIF running, PWM enabled, battery display FULL/100%.
  Visual UI responsiveness and unplugged suspend still require user observation.

Reproduce the read-only physical check:

```sh
python3 vm/test-prime-main-timer.py --physical
```

Emulator check (no physical writes):

```sh
PRIME_G2_CURRENT_CAPSULE="$PWD/build/lefony-settings-candidate/lefony-settings.zImage" \
  python3 vm/test-prime-main-timer.py
```
