# Native Lefony development and diagnostics

Start with [README.md](../README.md), [current status](STATUS.md), and
[the emulator guide](../vm/README.md). These are the current setup instructions.
The detailed diagnostic notes below describe implementation contracts and
bring-up history; candidate-specific observations are not release acceptance.

## Daily development

```sh
make test
make check-public
make firmware
make firmware-vm
make emulator
.venv/bin/python vm/test-prime-coordinate-touch.py \
  --elf dist/lefony-os-prime-g2-vm-native.elf --functions
```

Run physical and VM builds sequentially: they share the prepared upstream
checkout. Keep edits in `ports/lefony-prime-g2/`, its patches, or the preparation
scripts. `build/lefony-prime-g2/` is recreated by each build. The physical image
excludes test controls. None of these commands writes to a calculator.

Public CI runs host tests, the repository boundary check and both firmware
builds. Its optional emulator job builds custom QEMU and exercises direct-ELF
Functions and Calculator touch. Full U-Boot/storage/fault suites are separate:
`./vm/test-native-comprehensive.sh` needs Docker, QEMU tools and boot media.
Private stock-fixture research requires the inputs listed in `STATUS.md`.

## Memory and media map

| Address or region | Owner | Purpose |
| --- | --- | --- |
| `0x02000000..0x021fffff` | i.MX6ULL | peripheral MMIO used by native drivers |
| `0x82000000..0x84ffffff` | Upsilon | code, read-only data, data, BSS, heap, 1 MiB stack |
| `0x87ff0000` | U-Boot | temporary manifest load address |
| `0x88000000..0x887fffff` | U-Boot | maximum 8 MiB ELF staging range |
| `0x8f000000..0x8f0fffff` | LCDIF/Upsilon | framebuffer allocation and integrity guards |

The linker rejects exhausted heap or framebuffer overflow. The boot-media
script rejects payloads that exceed the staging range. The SD image has a
fixed MBR/FAT boot partition, two 512 KiB atomic storage slots, and a reserved
tail; exact sectors are specified in `LEFONY-NATIVE-STORAGE-FORMAT.md`.

## Ion service ownership

| Service | Physical target | VM target |
| --- | --- | --- |
| startup, VFP, stack, heap | native ARMv7 code | identical code |
| UART console | UART1 | QEMU UART1 |
| control/test UART | excluded | UART3 socket bridge |
| monotonic timing | GPT1: owned 24 MHz PERCLK divided by 8 to 3 MHz | same selector and prescaler |
| display | serial-RGB LCDIF and ILI9322 setup | identical guest driver; Prime-specific QEMU model enforces IOMUXC, serialized RGB, sync/polarity, digital timing, power sequence, and FIFO recovery contracts |
| backlight | PWM7 and supply GPIO | identical guest driver; Prime-specific QEMU model gates visibility on supply and PWM7 state |
| keypad | 8x8 KPP interrupt wake plus debounced scan; all 51 physical keys and Prime Alpha/Shift legends | identical driver against the QEMU KPP matrix/electrical model with exhaustive modifier testing |
| touch | Goodix GT5688 over I2C2, reset/IRQ GPIOs, bounded report parser | identical physical driver against the GT5688 model; coordinate contacts flow through view hit-testing and graph gestures |
| storage | RAM-only pending medium decision | atomic dual-slot SD/QCOW2 backend |
| preferences/datasets | compiled defaults/RAM | checked records in atomic storage |
| power/battery | PF1550 charger/status and SNVS on-key plus ADC1_IN1 HP-compatible five-level voltage estimate | PF1550 cold reset/charger model and ADC1 conversion model consumed by the identical guest drivers |
| RTC | SNVS LP secure RTC | identical conversion logic with deterministic virtual-time control |
| USB/recovery | USBOTG1 device controller and PHY; bounded EP0 diagnostics and RAM capsule staging | identical guest driver enumerates on the modeled USBOTG bus and is tested through reset, reconnect, suspend, malformed transfers, and capsule upload |
| NAND/update | destructive writes remain separately gated; stock layout is preserved | sparse NAND model plus A/B slots, bad blocks, readback, atomic metadata, boot attempts, and rollback |

VM substitutions are compiled only with `PRIME_G2_EMULATOR`; production
physical builds contain no control protocol. A VM passing validates the
programmed panel sequence, register-level display state, deterministic digital
timing, Goodix/PF1550 I2C transactions, and modeled NAND behavior. It cannot
validate analog voltage/impedance, ringing, crosstalk, EMI, physical KPP scan
behavior, USB signal integrity, PMIC calibration, flash wear, or suspend
current.

## U-Boot and recovery behavior

The generated environment loads `upsilon.env` and `lefony-os.elf` from the FAT
partition, checks exact length and SHA-256, validates ELF load segments, and
then calls `bootelf`. Missing, truncated, corrupt, oversized, or overlapping
payloads print a specific error and leave a non-destructive U-Boot prompt.
Normal VM runs use a QCOW2 overlay, so the reproducible base image is unchanged.

Storage modes are:

- `persistent`: reusable QCOW2 writes;
- `ephemeral`: throwaway snapshot for independent tests;
- `readonly`: rescue overlay whose marker makes the native block layer reject
  writes.

Factory reset requires the Shift+Alpha+Backspace confirmation chord through
the VM control protocol. The internal `STORAGE RESET CONFIRM` form exists for
bounded automation. Reset and format details are in
`LEFONY-NATIVE-STORAGE-FORMAT.md`.

## Diagnostics

For an interactive run, inspect:

- `build/prime-g2-native-vm/uart.log` — U-Boot and guest console;
- `build/prime-g2-native-vm/qemu.log` — unimplemented/invalid guest MMIO;
- `build/prime-g2-native-vm/runner.log` when launched by a test;
- QMP screenshots captured with `vm/qmp-screendump.py`.

Semantic state can be queried without interpreting pixels:

```sh
./vm/prime-control.py --socket build/prime-g2-native-vm/input.sock v1 1 INFO
./vm/prime-control.py --socket build/prime-g2-native-vm/input.sock v1 2 STATE
./vm/prime-control.py --socket build/prime-g2-native-vm/input.sock v1 3 DISPLAY GUARDS
```

Protocol commands are versioned and request-tagged. Unknown, oversized, and
malformed input is rejected. `INPUT RESET` clears keys, pending input,
modifiers, and repeat state; `RESET WARM` returns to Home without deleting
records. `RESET COLD` requests WDOG1 and, because the VM uses `-no-reboot`,
terminates the current cold-boot instance.

Prime G2 directional events are single-step: holding Left, Right, Up, or Down
does not synthesize additional navigation events. The key must be released and
pressed again. Backspace retains normal hold-to-repeat editing behavior.

Undefined-instruction, SVC, prefetch-abort, data-abort, IRQ, and FIQ vectors
have separate stacks and handlers. Fatal handlers preserve the incoming
register set, report PC/LR/SP/CPSR and ARM fault registers over UART, draw a
minimal red crash screen when LCDIF is usable, and remain in a bounded USB
diagnostic polling loop; they never return into a possibly corrupted
application. The emulator suite safely
triggers and verifies undefined, SVC, prefetch-abort, and data-abort. IRQ/FIQ
delivery uses the Cortex-A7 GIC, and watchdog/SNVS diagnostics retain the reset
reason for the next boot.

The native runtime installs a 16 KiB ARMv7 section table before entering Ion.
Code is read-only/executable, mutable state and stack/heap are read-write/XN,
peripherals are device memory, the framebuffer is non-cacheable DMA memory,
and unmapped space faults. Storage and USB DMA ownership changes include cache
maintenance and barriers. The test protocol exposes MMU attributes, heap and
stack high-water marks, allocator fragmentation/exhaustion checks, interrupt
latency, missed timer deadlines, and watchdog state.

WDOG1 reset-reason capture starts during board initialization, but WDE is set
only by the first healthy event-loop poll. This prevents physical UI
construction from racing a two-second watchdog before its feed path exists.
After arming, it is fed by that health-checked event-loop path and during
bounded atomic-storage progress, then tested with deadlock, IRQ-storm, and
deliberate-hang resets.
Idle power uses an independent monotonic inactivity clock: RTC/battery test
time jumps cannot manufacture an idle timeout. The services suite verifies
dim, suspend, wake reconstruction, brightness restoration, and framebuffer
guards with deterministic idle-clock advancement.

### Physical USB boot diagnostics

The physical bare-metal target exposes an independent control-only USB device
with VID:PID `CAFE:5052`. It starts before display initialization and does not
depend on Upsilon's UI, keypad, touch, filesystem, Linux, or working LCD
timing. Install libusb on the Mac, connect a normally booted diagnostic image,
and run:

```sh
brew install libusb
./scripts/prime_g2_usb_diag.py
./scripts/prime_g2_usb_diag.py --watch 1
./scripts/prime_g2_usb_diag.py --json > prime-g2-diagnostic.json
```

The host reads three vendor requests over endpoint zero: protocol/status,
individual records from a 128-entry RAM boot ring, and a frozen 256-byte
register snapshot. Events bracket USB clock/PHY/controller setup, display pin
and clock setup, panel reset, every ILI9322 register write, LCDIF reset and RUN,
backlight, Upsilon entry, and ARM fatal exceptions. The snapshot includes the
relevant CCM/ANATOP, LCDIF, IOMUX, GPIO, PWM, USB, and framebuffer values. All
controller waits are bounded; a failed USB handshake is recorded rather than
allowed to stop display boot.

The report distinguishes these classes of white-screen failure:

- boot stopped or faulted before LCDIF start;
- LCDIF held in reset, not running, underflowing, or configured with the wrong
  transfer geometry/framebuffer address;
- panel RESET held low or configured incorrectly;
- an all-white framebuffer versus rendered pixels that never reached the
  glass.

The event ring is volatile and resets at each boot. The ILI9322 connection is
write-only on this board, so software cannot read back panel registers. If the
report proves that rendered pixels exist and all software-visible clock,
LCDIF, pin, reset, and PWM state is correct, the remaining boundary is
electrical: measure panel power/reset, SPI, pixel clock, data, and sync lines
with an oscilloscope or logic analyzer.

Physical bring-up images do not arm WDOG1. They record watchdog health and
service a watchdog inherited from U-Boot, but preserve a stable fault screen
and diagnostic snapshot instead of converting a post-redraw failure into an
opaque two-second boot loop. The hardware-faithful VM continues to arm WDOG1
and runs the complete deadlock, interrupt-storm, reset, and restart contract.

Physical first-redraw diagnostics use twenty bottom-edge slots. Stage 7 enters
the first `Window::redraw`, stage 8 means dirty-region setup returned, and
stage 9 means the vblank boundary returned and `View::redraw` is beginning.
Stages 10-11 bracket the Home content draw, 12-13 the
background inner view, and 14-15 an app cell. Stage 16 enters the first icon,
17 means its 6,160-byte stack buffer passed the guard check, 18 means LZ4 icon
decompression returned, 19 means all icon pixels were published, and 20 means
the complete recursive redraw returned. Unreached slots are near-black.
A physical bring-up image then resets and reuses the row for its first event
cycle: 1-7 bracket USB/display monitoring, services, and touch polling. Stage
8 enters the first keypad scan; 9 is after making all columns inputs; 10 is
after driving column 0 low; 11 is after selecting it as the sole output; 12 is
after bounded line settling; 13 is after reading GPIO2_PSR; 14 is after row
decode; 15 is after returning column 0 to high impedance; 16 means all eight
columns completed; 17 means the scan returned; and 18-20 mean mapping and the
keyboard call returned. A physical trace stopping at stage 8 isolated the
original lockup to the KPP scan. The physical build therefore scans the same
alternating GPIO2 row/column pads directly, leaving unselected columns
high-impedance; the VM retains its full KPP peripheral model.
After this one-shot trace completes, the first eight slots become a live raw
matrix monitor: each slot is one column, dark means no asserted row, a row's
diagnostic color means one asserted key, and white means multiple asserted
rows. This distinguishes pad-level sensing from Upsilon event mapping without
USB. Physical runtime delays use a bounded Cortex-A7 instruction loop so a
stopped GPT cannot freeze the event loop after its first scan. Peripheral and panel
power-up delays retain the proven GPT path; only post-initialization runtime
sleeps switch to the bounded Cortex-A7 instruction loop.
A red screen with one black block is `abort()` (normally an assertion), while
the exception screen is red with the existing long top stripe. Each newly
reached stage is also retained as a `BOOT_PROGRESS` USB diagnostic event.

The RTC represents a timezone-free calculator wall clock and intentionally
stores no timezone or daylight-saving metadata. The physical SNVS counter has
a 32-bit seconds horizon; dates beyond its 2106 rollover must not be treated as
persistent even though deterministic emulator date-conversion tests cover a
wider Gregorian range.

## Recovery upload and emulator NAND management

The native USB endpoint accepts diagnostics and a sequential, bounded,
CRC-checked zImage capsule into an 8 MiB RAM staging area. Both builds
authenticate a signed LFU1 model/version/digest manifest. The emulator writes
its modeled inactive slot directly. A physical build exposes a recovery-install
capability and can enter ROM recovery only after authentication; the installer
then uses Linux GPMI/BCH, verifies readback, and commits redundant metadata.
Unprovisioned physical NAND is rejected before any write. Query diagnostics,
stage a raw capsule, or exercise a signed update with:

```sh
python3 scripts/prime_g2_usb_diag.py --json
python3 scripts/prime_g2_usb_diag.py --stage build/prime-g2-native-nand/upsilon-native.zImage
python3 scripts/prime_g2_usb_diag.py --update build/prime-g2-native-nand/lefony-os-native.lfu
```

The emulator A/B manager exercises erase, bad-block skipping, SHA-256
readback, pending boot attempts, confirmation, power-loss interruption, and
rollback. A factory slot and matching U-Boot text environment can be prepared
with:

```sh
python3 scripts/prime_g2_nand_update.py --image nand.bin --state nand.json \
  create --factory build/prime-g2-native-nand/upsilon-native.zImage
python3 scripts/prime_g2_nand_update.py --image nand.bin --state nand.json \
  export-env upsilon-ab.env
python3 scripts/prime_g2_nand_update.py --image nand.bin --state nand.json \
  install build/prime-g2-native-nand/upsilon-native.zImage
```

The running VM tests cover the full USB-to-firmware-to-GPMI/BCH-to-U-Boot
path. `vm/test-native-usb.sh` rejects forged signatures before erase and checks
inactive-slot program/readback. `vm/test-native-ab-update.sh` transfers the
complete capsule, performs the requested reset, boots and self-confirms slot B,
then boots a signed non-confirming image three times and proves automatic
rollback. The separate manager retains deterministic power-loss, corruption,
and interrupted-transaction fault injection.

The captured stock UBI partition occupies the proposed second-slot tail. The
one-time migration therefore remains a separate, explicit qualification gate;
ordinary updates never create metadata or repartition a device implicitly.

The manager validates capsule headers and readback digests again at boot
selection. A corrupt pending slot rolls back without consuming attempts; a
corrupt active slot selects the other verified copy; if both are invalid, the
generated U-Boot policy enters the read-only recovery prompt. The QEMU NAND
model additionally injects corrected and uncorrectable data/OOB faults, read
disturb, partial-program exhaustion, erase wear, and bad-block promotion.

## Performance, fuzzing, and soak evidence

`test-native-performance.sh` records boot-to-home, calculation and application
open time, redraw throughput, key/touch-to-frame latency, storage commit time,
memory-region sizes, heap/stack high-water use, IRQ latency, missed deadlines,
and application-switch leak checks in `metrics.json`; the test fails when a
declared budget is exceeded.

The complete suite includes malformed storage, update-capsule, USB-request,
and UART control-protocol corpora. The accelerated soak advances 24 hours of
virtual RTC/power time while repeatedly exercising UI, display, storage,
watchdog, heap, and stack health. It deliberately models USB power so battery
depletion does not turn a stability run into the separate empty-battery test.
This is 24 hours of modeled time, not the final 24-hour physical or wall-clock
endurance gate.

## Extending the port

To add a key, edit only `ion/src/prime_g2/keymap.inc`. Every row includes the
test name, evdev value, Ion key, and KPP row/column. The generated Python
controller and exhaustive modifier test parse this same table.

To add a VM control command, keep it inside `PRIME_G2_EMULATOR` in
`emulator.cpp`, require a `V1 <request-id>` envelope in automated tests, bound
every input before access, add a host unit or protocol test, and confirm the
physical ELF contains no bridge symbol.

To add an application workflow, extend `native-app-test.py` using key events or
the `ExternalText` event bridge and assert guest semantic state as well as a
framebuffer capture. Put generated artifacts beneath the test directory.

To add a device model, first document registers, IRQs, clocks, reset state, and
the hardware source. Add the model to a pinned QEMU tree, connect control input
at the electrical/device boundary, run the unmodified physical driver in QEMU,
and remove the corresponding VM substitution only after parity tests pass.

## Safe future physical bring-up

The emulator workflow never authorizes installation. Initial physical tests
must remain RAM-loaded from a recoverable U-Boot prompt, preserve a verified
stock NAND backup, avoid `nand write` and persistent `bootcmd` changes, and
keep ROM recovery accessible. Permanent installation is gated by documented
NAND geometry/ECC, redundant boot slots, rollback, bad-block/power-loss tests,
and a separate explicit user action.

## Known limitations

- Critical: persistent storage is VM-only; physical native builds are RAM-only.
- Critical: physical validation of USB enumeration, Goodix input, PF1550
  battery/on-key, SNVS power-off/wake, and permanent NAND recovery is still
  required. Native drivers, RAM-only USB recovery staging, and emulator device
  models exist, but they are not substitutes for target measurements.
- Critical: Shift+OFF now explicitly places ILI9322 in display-off/standby,
  drives PWM7 and the backlight-enable GPIO low, stops LCDIF, and waits in WFI
  for either the SNVS power-key interrupt or PF1550's GPIO5 interrupt before
  reconstructing display, backlight, USB, and touch. The non-returning standby
  path programs PF1550 restart/ONKEY/CORE_OFF controls before SNVS `TOP`.
  Physical current, individual wake-source measurements, full rail-off/reboot,
  and target validation of watchdog reset persistence remain hardware gates. The
  modeled lifecycle, health policy, MMU/cache protection, GIC IRQ delivery,
  and reset-reason path are implemented and emulator-tested.
- High: the pinned Prime-specific QEMU models ILI9322 registers, writable
  masks, power/display states, automatic startup-white frames and datasheet
  SPI timing; serialized RGB decoding; exact IOMUXC routing/pad values; panel
  GPIOs; PWM7; pixel-clock/sync tolerances; signal polarities; and LCDIF FIFO
  underflow recovery. Analog trace/glass behavior and physical tolerances are
  not modeled. KPP input now enters the modeled electrical matrix; Goodix
  touch, PF1550, and sparse NAND models are provisional pending differential
  captures from the calculator.
- Medium: Reader and External apps are excluded because the native product has
  no filesystem/app-loading and sandbox policy yet.
- Low: battery level uses HP's recovered ADC1 calibration and deliberately
  reports only the shipping 0/25/50/75/100 voltage groups. PF1550 separately
  supplies VBUS, active-charge, full, presence, and fault states. Meter-based
  target validation across load, temperature, and cell age remains required;
  this hardware has no coulomb counter and cannot honestly promise 1% accuracy.
- Low: clipboard operations use Upsilon's bounded in-process Escher buffer;
  there is intentionally no host/system clipboard integration.

These are engineering boundaries, not silently successful features. Physical
gates remain unchecked in the authoritative checklist.
