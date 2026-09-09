# HP Prime G2 ILI9322 display model

This document records the sourced behavior implemented by the native display
driver and the Prime-specific QEMU model. It is a digital controller contract,
not a claim that QEMU reproduces the analog panel glass or PCB traces.

## Authoritative references

- [ILI9322 v1.12 datasheet](https://www.df.lth.se/~triad/krad/dlink-dir-685/ILI9322DS_V1.12.pdf)
- [Upstream Linux ILI9322 DRM driver](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/panel/panel-ilitek-ili9322.c)
- [Prinux Linux ILI9322 driver at the pinned source revision](https://github.com/RaymiiOrg/prinux-linux/blob/8739abed6866a57067c553a086e80f5f68659f1c/drivers/video/backlight/ili9322.c)

The datasheet defines controller behavior and limits. The upstream driver is a
cross-check for register meanings. The pinned Prinux source is board evidence
for the Prime's GPIO assignments, mode-3 bit-banged SPI, and working gamma and
interface values. A Linux capture from this exact calculator remains the
authority for SoC-side LCDIF, clock, PWM, and IOMUXC state.

## Implemented controller contract

The SPI transaction is 16 bits: one read/write bit, seven address bits, and
eight data bits. The Prime exposes SCK, CS, and MOSI but no MISO. Emulator read
transactions therefore exercise controller state without providing a guest
readback path. The model enforces the datasheet's 50 ns minimum SCLK and CS
periods, 25 ns high/low clock periods, and 15 ns data setup/hold periods.

Reset restores documented register defaults and read-only device ID `0x96`.
Writes are restricted by per-register masks, including reserved bits. The
important state transitions are:

1. Hold panel reset low while LCDIF begins DCLK, sync, DE, and RGB signaling.
2. Release reset and wait for the controller to recover.
3. Program interface, direction, polarity, and gamma registers.
4. Write register `0x07` to leave standby and enable normal power.
5. Wait at least 10 frames before enabling display output.
6. Write register `0x30` with `AUTO_DP` and `DISP_ON`; model the selected
   10/20/40/80-frame automatic white startup interval.
7. Enable the panel supply/backlight only after that interval.

Polarity-control register `0x0A` retains its documented `REV=1` reset
default (`0x49` with the Prime's sync polarities). This is the normal optical
grayscale direction for the Prime panel and is also what the working Prinux
driver preserves. Clearing `REV` makes white appear black and maps Lefony's
green accents to their purple complement. The QEMU model treats `REV=1` as
normal for this board so the software accessibility setting remains off by
default on both targets.

Register `0x05` is the power-setting register, but it is not the controller's
standby/charge-pump state machine. The old native sequence treated it as that
control because the historical Prinux driver writes `0xef` there. Masking its
reserved bits makes that value effectively `0x67`. Actual standby and charge-
pump state live in power-control register `0x07`.

## Optical fault interpretation

A missing backlight is electrically dark and renders black. The panel supply
is separate: PF1550 LDO1 powers the LCD at 3.3 V, while PWM7 and GPIO2_IO21
control the backlight. If LDO1 is absent but the backlight is enabled, the
physical screen can be white and dim normally even though no LCD pixels are
being driven. Native startup now configures and verifies LDO1 before reset.
A powered panel in reset, standby, invalid interface state, invalid LCDIF
timing/polarity, or the automatic display-on interval renders white. This is
why the emulator can now reproduce the calculator's white-screen class of
failure instead of mapping every failure to black. FIFO underflow remains a
one-scanout black interruption because it is a missing-pixel-stream event.

## Remaining physical proof

The model cannot infer analog voltage margins, ringing, skew, impedance,
crosstalk, connector faults, or the panel module's undocumented tolerances.
The corrected order is a strong root-cause hypothesis, not proof of the
physical white-screen fix. Final sign-off requires flashing a diagnostic
build and comparing its event log plus logic-analyzer traces against emulator
markers at reset, SPI, DCLK, sync, DE, RGB, panel power, and backlight.
