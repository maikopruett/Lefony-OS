# Battery voltage collection blocked by stopped GPT

## Physical evidence

Read-only native USB endpoint `C0/55`, diagnostic build
`260909-033129-5646b8`, returned repeated captures with:

- `millis = 1117`, `GPT_CNT = 3351421`, `GPT_CR = 0x749`, `GPT_PR = 0`
- `ADC_HC0 = 1`, `ADC_HS = 1`, `ADC_CFG = 0xc3f3`, `ADC_GC = 0x20`, `ADC_GS = 0`
- ADC initialized and software conversion pending, but accepted raw/mV/valid all zero
- `SNVS_LPCR = 0x21`; RTC low counter advanced from 14182819 to 14607412

The completed ADC conversion was never collected because `Services::poll`
scheduled collection at a future GPT-based millisecond deadline that never
arrived. This establishes the immediate cause of the zero-voltage reading,
not the underlying cause of GPT stopping.

## Fix and tests

Physical battery sampling, PMIC refresh, and percentage hold deadlines now
use accumulated SNVS RTC ticks. Low-word rollover is supported; wall-clock
adjustments and long suspensions advance the scheduler by at most one second.
This describes the initial workaround. It was superseded by the shared,
full-counter sleep-aware clock in [elapsed-clock-20260909.md](elapsed-clock-20260909.md),
which preserves complete sleep intervals and explicitly rebases calendar writes.
ADC collection remains nonblocking and preserves the existing conversion and
ten-sample trimmed-mean voltage calibration. No charger policy, U-Boot,
display initialization, or general UI timing was changed.

- 96 relevant unit tests pass, including compiled C++ clock arithmetic tests.
- `vm/test-prime-battery-usb.py` stops GPT1 before the physical-target firmware
  can accumulate voltage samples. The fixed image returns raw 211 / 3853 mV
  over USB while GPT stays stopped and SNVS continues advancing.
- The same test against the preceding diagnostic image fails with raw/mV/valid
  zero and a pending completed ADC conversion, reproducing the physical fault.

## Physical deployment

Build `260909-033415-767ea3`, SHA-256
`7d03939ccf19aebe7ede50a119fe37f1e62870f316414273f6103d834a31432e`,
2,103,224 bytes: native USB installation completed with byte-for-byte NAND
verification. The endpoint was initially absent after the reboot request,
then returned. Repeated physical USB reads reported **raw 231, 4214 mV,
valid = 1**, with SNVS continuing to advance and GPT still stopped at
3351377. The ordinary diagnostic snapshot also reports a calibrated voltage.
Thus the real battery collection path, not just the emulator, is verified.
Whether the reboot completed automatically or the user pressed reset was
not established by the host observations.

Read the new telemetry with `python3 scripts/prime_g2_usb_diag.py --battery`.
This endpoint never reads ADC_R0 (which would consume the driver's result),
starts no conversion, and performs no writes to peripheral registers or NAND.
