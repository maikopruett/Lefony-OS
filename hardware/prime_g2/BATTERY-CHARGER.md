# HP Prime G2 battery and charger

This document records the evidence used by Lefony OS. It intentionally links
to external board references instead of copying detailed motherboard photos
into the repository.

## Architecture

Battery level and charging are two independent hardware paths:

- The NXP PF1550 at I2C1 address `0x08` controls charging and reports external
  power, charger phase, battery presence, completion, and faults.
- i.MX6ULL ADC1 channel 1 measures the cell-divider voltage. The PF1550 has no
  fuel-gauge ADC or coulomb counter, so its status registers cannot provide a
  percentage.

The title-bar state must therefore never infer charging from voltage or infer
battery presence from VBUS. Lefony tracks:

| Meaning | Source | Interpretation |
| --- | --- | --- |
| External power | `VBUS_SNS` (`0x86`) bits 5 and 2 | VBUS valid and not in UVLO |
| Charge phase | `CHG_SNS` (`0x87`) low nibble | 0–3 charging, 4 complete |
| Battery present | `BATT_SNS` (`0x88`) low 3 bits | 6 means not detected |
| Fault/suspend | `CHG_SNS` | 6, 7, 9, 10, or 12 |
| Cell voltage | ADC1 channel 1 | filtered and converted below |

## Root cause of “charges only with the battery removed”

`CHG_OPER` (`0x89`) resets to operating mode 1. That mode can power the system
from VBUS but keeps battery charging off. Reading `CHG_SNS` more accurately did
not fix the problem because Lefony never enabled the charger.

At startup Lefony now writes mode 2 (`BAT_ON`) to `CHG_OPER`, reads it back,
and retries after PMIC communication failures. The write is deliberately
limited to the operating-mode register. HP's OTP-loaded charge voltage,
current, input-current limit, and thermal policy are preserved.

This matches the upstream Linux correction which writes `PF1550_CHG_BAT_ON`
for battery-powered products.

## Root cause of the charging symbol remaining after unplug

The original refresh read device ID, charge phase, battery sense, VBUS sense,
and charger operation in one short-circuiting expression. If any transaction
failed, the refresh returned without changing the cached external-power or
charging flags. Once mode 2 made charging genuinely active, one failed poll
could therefore leave a previous `true` result visible after unplug.

Charging telemetry now fails closed. Each poll first revokes the previous VBUS
and charging claim, reads every PF1550 dimension independently, and asserts
charging only when fresh `VBUS_SNS`, `CHG_SNS`, and `BATT_SNS` values from the
same poll agree. A valid VBUS sample can still remove the icon even if an
unrelated register read fails. The shared PF1550 GPIO wake path also clears the
charger interrupt status register, preventing a level-low charger IRQ from
remaining asserted after suspend or wake.

## HP-compatible voltage estimate

### Display consistency correction (2026-09-09)

The periodic charger refresh used to overwrite a calibrated FULL icon with
SOMEWHERE_INBETWEEN whenever the charger was not reporting charge completion.
The next ADC sample restored FULL, producing visible half/full flicker after
unplugging. Charger-derived level/percentage values are now only a fallback
before an ADC estimate exists; explicit no-battery and charge-complete states
retain their existing precedence. Charging and external-power flags remain
independent and are still refreshed on every PMIC poll.

Settings previously used a separate `(voltage - 3.6) * 166` formula. It now
reads the same platform percentage that controls the battery level, preserving
the existing five-level estimate and 30-second smoothing policy. This is a
display consistency fix, not proof of exact state of charge or a correction
to the unresolved USB-only battery-presence ambiguity.

`vm/test-prime-battery-usb.py` exercises stopped-GPT sampling, then a simulated
full cell with external power removed. After the smoothing interval, 100
consecutive USB display-state reads must remain FULL / 100% across charger
polls. The emulator's USB transport stays available for observing this test;
it is not a physical cable-disconnection qualification.

The shipping HP Prime G2 firmware configures the following path:

- `GPIO1_IO01` routed to ADC1_IN1 with mux mode 5 and pad control `0x90`.
- ADC1 clock gate in CCM CCGR1 bits 17:16.
- ADC `CFG = 0xC3F3`, `GC = 0x20`, `OFS = 0`, followed by hardware
  calibration.
- One sample every 100 ms. Ten samples are collected, the minimum and maximum
  are removed, and the remaining eight are averaged.

The recovered conversion is:

```text
mV = (((0x5A3C * raw) / 5) >> 8) + (raw >= 0xD0 ? 0x2E : 0x16)
```

The shipping five-level display groups are:

| Filtered voltage | Display estimate |
| --- | ---: |
| below 3501 mV | 0% |
| 3501–3663 mV | 25% |
| 3664–3699 mV | 50% |
| 3700–3862 mV | 75% |
| 3863 mV and above | 100% |

The low/critical boundary is 3551 mV. Group changes are held for at least
30 seconds to prevent UI oscillation. Charger state 4 overrides the display to
100% because the PMIC has reached charge completion.

This is a voltage-derived five-level estimate, not laboratory-grade state of
charge. Load, temperature, cell age, and relaxation can move voltage without a
matching capacity change. Lefony does not claim 1% precision because this
two-terminal battery design has no coulomb counter.

## Emulator contract

The Prime-specific QEMU model cold-starts PF1550 in charger-off mode 1, so the
guest must perform the real mode-2 initialization. VBUS presence and active
charging remain independent. Its ADC1 model converts the modeled cell voltage
back to an HP-compatible ADC code, implements calibration completion and the
COCO result flag, and lets the unmodified native ADC driver consume it.

## Physical validation matrix

The following remains a target gate after installing this build:

| Battery | USB | Expected |
| --- | --- | --- |
| absent | absent | no battery, no external power, not charging |
| absent | present | external power, no battery, not charging |
| present | absent | battery present, no external power, ADC level shown |
| present | present | external power and battery present; CHG 0–3 while charging, then 4 when full |

For each row record `VBUS_SNS`, `CHG_SNS`, `BATT_SNS`, `CHG_OPER`, ADC raw,
converted millivolts, displayed level, and current direction. Also verify
plug/unplug, suspend/wake, thermistor suspension, full-charge termination, and
restart from a battery-cold boot.

## Sources

- NXP, [PF1550 data sheet](https://www.nxp.com/docs/en/data-sheet/PF1550.pdf)
- Linux, [PF1550 charger mode correction](https://lkml.iu.edu/hypermail/linux/kernel/2607.3/00578.html)
- HP calculator team, [Prime G2 battery-level algorithm explanation](https://www.hpmuseum.org/forum/thread-14125-post-124763.html)
- HP, [Prime G2 firmware package mirrored by hpcalc.org](https://www.hpcalc.org/details/7783)
- [HP Prime G2 internal reference archive](https://www.hpcalc.org/details/9045)
