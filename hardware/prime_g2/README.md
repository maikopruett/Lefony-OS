# HP Prime G2 hardware reference

This directory is the evidence base for the Lefony OS HP Prime G2 emulator.
It deliberately separates facts observed on the working calculator from
device-tree declarations and from deductions. A complete emulator is the
goal; the current model is not yet a one-to-one replica.

## Evidence rules

- **Observed** means read from the pristine Prinux Linux system or from a
  working peripheral's live MMIO state.
- **Declared** means present in the calculator's exact device tree. This is
  strong routing/configuration evidence, but it does not prove the fitted
  component. The touch controller is an example: the DT says GT928 while the
  live controller identifies as 5688.
- **Decoded** means derived from observed values using the exact Linux driver
  and NXP documentation. Calculations and assumptions must remain explicit.
- **Unknown** means the emulator must not invent behavior yet.

## Public reference boundary

Only selected register values, decoded board contracts, fbset mode information,
and identity hashes are distributed here. Full captures, device-tree binaries
and decompiled device trees stay private. `reference/sources.json` records
provenance and hashes for optional private references. The public analyzer
fixture `reference/rom-dma-buffers-20260907.json` replaces every payload word
with synthetic zeroes; it must not be used as physical payload evidence.

`reference/keypad-matrix.csv` contains the 50 decoded keypad positions. The
retained subset of `captures/20260831T154107Z` is indexed by its manifest and
remains explicitly incomplete: the original read-only dump stalled before
finalization. Other capture directories mentioned in historical notes are
private and not included in this checkout. See [status](../../docs/STATUS.md)
for optional private-fixture checks.

## First live baseline

The following observations summarize the original physical bring-up. They
explain model provenance, not qualification of every current firmware image.

Observed baseline:

- ARMv7 Cortex-A7 i.MX6ULL, 256 MiB physical RAM at
  `0x80000000..0x8fffffff`.
- Linux `4.14.98-gbd1091339-dirty`, Buildroot 2019.08.3, board model
  `HP Prime G2 Calculator`.
- Raw NAND with 2,048-byte pages, 64-byte OOB, and 128 KiB erase blocks.
  Partitions are boot 4 MiB, kernel 8 MiB, DTB 1 MiB, misc 1 MiB, and the
  remaining 522,190,848 bytes for rootfs.
- USB OTG1 runs as a `g_serial` peripheral on `2184000.usb`, exposing
  `ttyGS0`. This is the Linux diagnostic path, not a native Upsilon feature.
- KPP is the i.MX 8x8 keypad controller at `0x020b8000`. The board populates
  50 positions. Power is separate and appears through both PF1550 on-key and
  SNVS power-key input devices.
- Touch is on I2C1 address `0x14`, IRQ GPIO1_IO25, reset GPIO1_IO24. The live
  controller reports ID `5688`, version `0200`, despite the DT compatible
  `goodix,gt928`. The optional Ilitek device at `0x26` did not bind.
- PF1550 is on I2C0 address `0x08` and supplies on-key, charger, and regulator
  functions. The DT describes SW1/SW2/SW3, VREFDDR, and LDO1/LDO2/LDO3.
- LCDIF is at `0x021c8000`; PWM7 is at `0x020f8000`; the framebuffer is
  XRGB8888 at physical `0x88000000`, 320x240, 1,280-byte stride.

## Display decode

The board uses an ILI9322 control interface on software SPI mode 3 at 100 kHz:
GPIO4_IO21 SCK, GPIO4_IO22 CS, GPIO4_IO23 MOSI, and GPIO3_IO04 reset. Pixel
data does not travel over this SPI link. LCDIF sends each XRGB8888 pixel over
the panel's 8-bit RGB bus in three transfers, so the physical horizontal
active count is 960 while the logical framebuffer width remains 320.

The native bring-up and emulator register model are derived from the
[ILI9322 v1.12 datasheet](https://www.df.lth.se/~triad/krad/dlink-dir-685/ILI9322DS_V1.12.pdf),
the [upstream Linux ILI9322 DRM driver](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/panel/panel-ilitek-ili9322.c),
and the [exact Prinux panel driver](https://github.com/RaymiiOrg/prinux-linux/blob/8739abed6866a57067c553a086e80f5f68659f1c/drivers/video/backlight/ili9322.c).
The model includes reset values, per-register writable masks, SPI read/write
framing and 50 ns chip-select/clock plus 15 ns data setup/hold limits, power
control in register `0x07`, display control in register `0x30`, and the
automatic 10/20/40/80-frame white startup state. The serial link has no MISO
wire on the Prime, so native software still cannot read registers back.

The LCD electrical supply is PF1550 LDO1 (`0x4c`/`0x4d`) at 3.3 V. Native
firmware programs selector `0x1f`, enables the rail in RUN and standby, and
verifies both registers before touching panel reset. This is required for a
battery-cold boot: a warm boot after Linux can otherwise hide missing
regulator setup by leaving LDO1 configured. The emulator intentionally resets
LDO1 disabled at 1.8 V so lifecycle tests prove that native startup performs
the configuration itself.

The datasheet also exposed an ordering defect in the first native sequence.
LCDIF now starts its DCLK, HSYNC, VSYNC, DE, and RGB signals while the panel is
held in reset; only then is reset released, the charge pump enabled through
register `0x07`, the required frame delay observed, and display output enabled
through register `0x30`. This mirrors the working Linux order, where LCDIF was
already active before the panel driver completed its probe.

The working Linux state is:

```text
LCDIF_CTRL           0x000A4521
LCDIF_CTRL1          0x03070300
LCDIF_CTRL2          0x00A00000
LCDIF_TRANSFER_COUNT 0x00F003C0   # 240 rows, 960 transfers
LCDIF_CUR_BUF         0x88000000
LCDIF_NEXT_BUF        0x88000000
LCDIF_VDCTRL0         0x11300001
LCDIF_VDCTRL1         0x00000108   # 264 lines total
LCDIF_VDCTRL2         0x0004046C   # hsync 1, 1132 transfers total
LCDIF_VDCTRL3         0x00480012   # horizontal wait 72, vertical wait 18
LCDIF_VDCTRL4         0x000403C0   # 960 valid transfers
LCDIF_DEBUG0          0x2F04000F
```

With the observed 18 MHz pixel clock, the physical refresh is
`18,000,000 / (1,132 * 264) = 60.2313 Hz`. `fbset` reports about 138.6 Hz
because it computes from logical width 320 and does not know about the three
serialized transfers per pixel.

The most important proven discrepancy was pixel-clock polarity. Working Linux
has LCDIF VDCTRL0 `0x11300001`, where bit 25 (`DOTCLK_ACT_FALLING`) is clear.
The earlier native code set that bit, and the emulator required it. That made
the emulator validate a state different from the physical calculator. Native
and emulator contracts now use the observed rising-active configuration.

Other display differences remain open rather than guessed:

- Linux CTRL2 is `0x00a00000`; native currently requests `0x00800000`. The
  meaning/source of bit 20 and LCDIF SET/CLR alias behavior need a controlled
  decode before changing native code.
- Working PWM7 uses period 60,000 counts and sample 30,117 counts (50.195%).
  Native currently starts at about 75%, so initial brightness is not yet
  hardware-identical.
- The live clock tree has CCM CSCDR2 `0x0002d150`; the native clock setup uses
  a different selection. Frequency and parent behavior need a dedicated
  clock capture after the console reset.

See `EMULATOR-PARITY.md` for the implementation ledger.

The decoded golden snapshot is available in both machine-readable and review
forms under `decoded/20260831T154107Z.json` and `.md`. The emulator-side facts
are in `emulator-contract.json`; `differential-contract.json` defines the
repeatable comparisons rather than relying on screenshots.

## Safe recapture workflow

Boot pristine Linux and wait for `/dev/cu.usbmodem*`, then run:

```sh
python3 scripts/capture_prime_g2_linux_hardware.py \
  --watchdog-safe \
  --dtb hardware/prime_g2/reference/imx6ull-14x14-prime.dtb
```

The tool performs read-only Linux/sysfs/procfs queries and selected safe MMIO
reads. It does not scan I2C addresses, write registers, erase/modify NAND, or
copy firmware partitions. It may temporarily mount debugfs and will unmount it
when it mounted it. Individual MMIO reads have timeouts and are recorded as
`UNREADABLE` rather than silently omitted.
With `--watchdog-safe`, the tool arms `/dev/watchdog` before risky reads and
renews a bounded lease for each command. If the USB shell or MMIO access
freezes, the lease expires and the calculator reboots; a clean completion uses
the watchdog magic-close sequence.

If a session is interrupted, seal its existing files without reconnecting:

```sh
python3 scripts/capture_prime_g2_linux_hardware.py \
  --finalize-existing hardware/prime_g2/captures/TIMESTAMP \
  --incomplete-reason "description of interruption"
```

## Primary external references

- NXP, *i.MX 6ULL Applications Processors Data Sheet*, IMX6ULLIEC Rev. 1.2:
  <https://www.nxp.com/docs/en/data-sheet/IMX6ULLIEC.pdf>
- NXP, *i.MX Linux Reference Manual*:
  <https://www.nxp.com/docs/en/reference-manual/IMX_REFERENCE_MANUAL.pdf>
- NXP, *PF1550 Power Management IC Data Sheet*:
  <https://www.nxp.com/docs/en/data-sheet/PF1550.pdf>
- Exact Prinux kernel tree, commit `8739abed6866a57067c553a086e80f5f68659f1c`:
  <https://github.com/RaymiiOrg/prinux-linux/tree/8739abed6866a57067c553a086e80f5f68659f1c>
- Exact Prinux `mxsfb` driver used to decode LCDIF:
  <https://github.com/RaymiiOrg/prinux-linux/blob/8739abed6866a57067c553a086e80f5f68659f1c/drivers/video/fbdev/mxsfb.c>
- Upstream Linux Goodix driver:
  <https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/input/touchscreen/goodix.c>
- Upstream QEMU i.MX6UL machine model:
  <https://github.com/qemu/qemu/blob/master/hw/arm/fsl-imx6ul.c>
