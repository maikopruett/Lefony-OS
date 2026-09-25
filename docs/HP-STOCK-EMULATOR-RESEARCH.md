# HP Prime stock-firmware emulator research

This workflow runs privately supplied HP Prime G2 firmware and a physical
raw+OOB NAND backup in the Lefony hardware emulator. It exists to answer one
specific installation question safely: can a calculator running HP's normal
operating system enter a native update path that can bootstrap Lefony without
using i.MX ROM recovery?

HP firmware and NAND contents are proprietary and device-specific. They must
remain under the ignored `build/hp-prime-stock/` directory and must not be
committed or redistributed. The repository contains only parsers, emulator
models, tests, and documentation.

## Preparing private fixtures

Extract the OS and updater/bootloader images from a locally supplied official
firmware archive:

```sh
python3 scripts/prepare_hp_prime_stock_fixture.py \
  /private/path/HP_Prime_Calculator_G2_Firmware.zip \
  --output-dir build/hp-prime-stock \
  --fast-boot --exploratory-shims
```

The script validates the container table and both i.MX IVTs, records SHA-256
digests, preserves the original images, and optionally creates two clearly
labeled local research copies:

- `HPPrime.fast.img` removes one exact calibrated delay routine. This changes
  elapsed emulator time only.
- `HPPrime.research.img` additionally exits one repeatable startup loop. This
  is fault isolation, not a bootable release artifact; the loop consumes a
  64-position keypad map whose normal boot-time handoff state is not yet
  reproduced by direct image loading.
- `bootloader.research.img` replaces two timer-dependent waits with immediate
  progress/yield behavior. Its one-shot USB settle delay calls HP's native NAND
  initializer after the RTOS allocator is live, supplying the geometry handoff
  normally inherited from the preceding stage. The original `bootloader.img`
  remains untouched. These exact, fail-closed substitutions exist only to
  exercise the maintenance path; they do not change package-validation code.

A physical backup made with `nanddump --noecc --oob --bb=dumpbad` can be joined
without transforming its physical page layout:

```sh
python3 scripts/prepare_hp_prime_nand_fixture.py \
  /private/path/to/eight-64MiB-backup-chunks \
  --output build/hp-prime-stock
```

The resulting `stock-nand.raw` is 528 MiB because every 2,048-byte data page
retains 64 OOB bytes. QEMU maps it read-only. Erases and programs go to the
emulator's sparse copy-on-write overlay, so research runs never modify the
source backup.

## Running the stock images

Build the pinned QEMU fork, then launch either stock component:

```sh
./vm/build-prime-g2-qemu.sh
./vm/run-hp-prime-stock-vm.sh --fast
./vm/run-hp-prime-stock-vm.sh --bootloader
./vm/run-hp-prime-stock-vm.sh --bootloader-research --paused
./vm/run-hp-prime-stock-vm.sh --research --allow-reset
```

Use `--headless` for monitor-only work, `--os` for the unmodified extracted OS,
`--research` for the explicitly patched OS fault-isolation copy, or
`--bootloader-research` for the private timer-handoff shim. `--paused` starts
the CPU stopped so a host can connect before the first instruction. The USB
cable model now drives the board's GPIO1_IO00 and GPIO1_IO03 role inputs, so
manual qtest writes are not required. Every run gets its own directory containing the QEMU
log, UART log, USB research socket, and qtest socket.

`--allow-reset` omits QEMU's normal `-no-reboot` research guard. It is needed
when tracing an authentic software or watchdog reset; the NAND fixture remains
read-only with writes confined to the sparse copy-on-write overlay.

## What executes today

The authentic current HP OS now passes DDR sizing, CBAR discovery, I2C/PMIC
initialization, SNVS high-power register access, and descriptor-driven APBH
DMA. The APBH model parses the firmware's real chained command control words
and sends its NAND command/address/data cycles to the GPMI model. The authentic
HP updater/bootloader also enters its `HP Prime Update Mode` task, registers its
USB role manager, and reaches the FreeRTOS low-power idle path. An injected SNVS
power-key event wakes it and advances its runtime state.

The first concrete handoff gap is now identified. HP's tickless idle reads the
SNVS high-power RTC at `HPRTCMR/HPRTCLR`, programs `HPTAMR/HPTALR`, enables the
alarm in `HPCR`, and clears the latched status in `HPSR`. Those registers, the
alarm timer, interrupt, write-one-clear behavior, reset behavior, and migration
state are now modeled and black-box tested. Nevertheless, a maintenance image
loaded directly still inherits an already-expired software deadline: the
preceding boot stage has not supplied the RTOS handoff state that this image
expects. It consequently spins in scheduler bookkeeping before it can re-arm
the alarm. This is evidence that direct-loading the updater is not equivalent
to the real OS-to-updater transition.

The private research copy bypasses only the known settle/debounce waits and
turns the receiver's idle delay into a scheduler yield. With
the modeled cable GPIO state, PF1550 external-power sense, PHY `DEVPLUGIN`,
and analog VBUS sense present before execution, HP's own code initializes
USBOTG1 in device mode. The modeled controller reports `run=1`, and the stock
endpoint returns this real device descriptor:

```text
USB 2.0, EP0 64 bytes, VID 0x03f0, PID 0x2541
```

It also returns a 41-byte configuration descriptor with one HID interface and
endpoint 2 OUT / endpoint 1 IN. Authentic startup takes about 12 seconds in an
uninstrumented local run, so the stock-only probe allows 30 seconds while the
normal Lefony host helper retains its shorter default. This proves that the
maintenance transport is executable in the emulator.

### Stock upload framing

The Connectivity Kit serializes and verifies the complete official
`HPPrime_OS.img` update container, then sends it as fixed 64-byte HID reports
on endpoint 2 OUT. It does not send the extracted OS or bootloader image by
itself. Bytes 0--3 contain the little-endian package offset, bytes 4--5
contain a CRC-16 (initial value `0x1234`, polynomial `0x1021`) calculated over
the entire report with the CRC field initially zero, and bytes 6--63 contain up
to 58 package bytes followed by zero padding. Valid reports are accumulated
without a per-report reply. Endpoint 1 carries a four-byte next-offset value
for error resynchronization and the response emitted after the complete
declared container has arrived.

The repository's host probe deliberately accepts only the emulator's Unix
socket, so it cannot contact a physical calculator:

```sh
python3 vm/hp_prime_stock_update.py \
  --socket build/hp-prime-stock/run-<timestamp>/usb.sock \
  --package build/hp-prime-stock/HPPrime_OS.img \
  --reports 1
```

The authentic updater's application receive worker has been observed under a
debugger, and official-container reports reach its active dTDs. The
emulator now models cable-role GPIOs, queue-head current/overlay completion,
and the real `ENDPTPRIME` self-clearing versus `ENDPTSTAT` lifetime. The stock
interrupt handler and application worker consume the completion, validate the
report CRC, allocate the package buffer from the container's declared size,
copy the 58 payload bytes, and re-arm endpoint 2. The earlier expectation of a
per-report endpoint 1 acknowledgment was incorrect.

A complete current package is 304,980 reports. The authentic updater receives
that entire stream, validates it, and performs a finite native NAND transaction
against the private fixture. The settled successful run BCH-encoded and wrote
8,734 pages, with zero program failures, zero out-of-range pages, and zero
overlay-capacity failures. Its command counters remain stable after completion.

Reaching that result required four independently tested emulator semantics:

- APBH channel 0 `CURCMDAR` retains the terminal descriptor address;
- NAND `ERASE1` consumes three row-only address cycles;
- BCH encode descriptors source clean payload/auxiliary bytes through their PIO
  pointer registers, not the ordinary APBH buffer;
- successful/failed NAND status bytes are `0xE0`/`0xE1`, matching HP's native
  status routine.

The copy-on-write overlay covers 65,536 changed pages and exposes read-only
failure-class diagnostics. The private source NAND remains unmodified.

### Normal OS to updater transition

The transition out of the running HP OS is now characterized independently of
the later firmware upload. The G2 update path constructs a normal HP linking
protocol packet with command byte `0xE8` and a one-byte mode. The corresponding
stock reset dispatcher maps modes 0--3 to soft reboot, two factory-reset
variants, and `start_updater()` respectively. Mode 3 therefore asks the
running calculator to enter its maintenance image; it does not itself write
NAND or authenticate an update. `vm/hp_prime_stock_transition.py` reproduces
the 11-byte inner mode-3 packet and its HID-report wrapper for emulator tests.
It deliberately has no physical USB transport.

### Software-triggered Boot ROM recovery

The i.MX6ULL software boot override is now modeled and tested independently of
HP's updater. The transition used by upstream U-Boot's `bmode usb` support is:

1. write USB boot configuration `0x20` to `SRC_GPR9`;
2. set bit 28 (`BMODE`) in `SRC_GPR10`;
3. issue a warm reset through WDOG1.

The QEMU reset controller now distinguishes watchdog resets from cold/QMP
resets. It retains `SRC_GPR9/GPR10` only for the warm watchdog case, evaluates
the boot override, and hands USB ownership to a minimal i.MX6ULL ROM SDP model.
That model exposes the public NXP ROM identity `15a2:0080` and enough HID
control descriptors for normal host enumeration. A cold reset clears the
override, and an incorrect boot configuration remains in guest mode.

The original RAM-stub experiment was retired after physical testing disproved
its ROM-reset assumptions. The stub and builder have been removed. Corrected
ROM reset-model tests remain in `vm/test-prime-g2-rom-recovery.py`; product
recovery uses the [one-shot U-Boot protocol](UBOOT-ONESHOT-RECOVERY.md).
The preceding description records the original model, not a supported physical
native-to-ROM transition.

The authentic current OS and maintenance image were also audited without
emitting firmware bytes, signatures, or hashes:

```sh
python3 -m pip install capstone
python3 scripts/analyze_hp_prime_bootmode.py
```

The normal USB command handler compares command `0xE8`, extracts its one-byte
mode, and enters a table dispatcher whose explicit upper bound is 3. Mode 3
records HP's updater state and calls the same soft-reset routine used by mode
0. Across both ARM and Thumb decoding, neither authentic image has an aligned
literal or nearby `MOVW/MOVT` construction for `SRC_GPR9`, `SRC_GPR10`, or the
ROM USB boot value. Therefore there is no hidden reset mode that already asks
the Boot ROM for SDP.

A live 45-second direct-loaded normal-OS probe still reports the modeled
ChipIdea controller stopped (`run=0`). This is the same missing boot-stage
timer/interrupt/NAND handoff described above, so dynamic normal-mode command
enumeration is not yet honest or complete. The maintenance image's USB and
signed update path are dynamically proven; the normal OS command dispatcher is
currently a static result corroborated by the Connectivity Kit packet format.

The engineering conclusion for this route is precise: software-triggered ROM
recovery is valid on the SoC and needs no NAND write, but the inspected HP
firmware exposes no intended command that performs it or launches arbitrary
RAM code. The remaining blocker is obtaining an authorized native-execution
handoff from stock OS. Without that, this bridge is useful after an execution
mechanism is found, but it is not by itself a plug-and-install product path.

This materially narrows the no-tweezers question: entering HP update mode can
be initiated over normal USB, but that is only a transport transition. A safe
Lefony first-install still depends on demonstrating that the updater accepts an
authorized Lefony-controlled RAM bootstrap, or on finding a separate intended
native-execution path. The installer detects both `03F0:2441` (running HP OS)
and `03F0:2541` (current G2 update mode), labels them as research-only, and will
not send NAND commands in either state.

The private NAND fixture has also exposed the ROM FCB and both NAND views. A
Linux `nanddump --noecc --oob` made through the GPMI driver is not a literal
copy of the NAND bus: `gpmi_ecc_read_page_raw()` first transcribes the block
marker and then projects the controller's bit-packed payload/ECC layout into a
2,048-byte data area plus 64-byte OOB area. The capture kernel used 10 metadata
bytes, BCH strength 2, four 512-byte chunks, and GF(2^13). HP's stock image uses
36 metadata bytes, BCH strength 4, four 512-byte chunks, and GF(2^13).

`vm/hp_prime_stock_nand.py` and the GPMI emulator now reverse the capture
projection, extract the stock payload at the correct bit offsets, and restore
the transcribed block marker. This boundary is applied on demand; the private
528 MiB source remains read-only. As an independent oracle, the reconstructed
pages beginning at NAND page 768 were compared with the separately extracted
authentic OS image: 8,116,349 of 8,116,352 compared bytes match. The only three
differences are in its final partial page. That result validates the page
geometry without adding any HP bytes to this repository.

The ROM FCB uses a separate boot-control layout and remains a distinct piece of
work. The remaining stock-emulation work is to reproduce the normal
pre-application software/timer/interrupt handoff without a binary shim and boot
the resulting NAND through the special ROM pages. In the current direct-loaded
OS trace, the guest issues eleven NAND commands but enters its idle path before
submitting an ECC payload transfer. The complete native update transaction is
therefore proven in the maintenance artifact, while an unmodified
OS-to-maintenance reboot is not yet reproduced end to end.

The Connectivity Kit verifies the official container's `files.sig` with
RSA/SHA-256 before transmission. The same verification path is present in both
the inspected 2020 and current packages. Device-side enforcement is now proven
independently: `--flip-byte <offset>` mutates one package bit in memory while
recalculating every HID-report CRC, so all 304,980 reports remain
transport-valid. HP's updater rejects the complete package before programming.
The settled rejected run performs only read-only NAND discovery: zero overlay
pages, zero BCH writes, and zero program attempts. No modified proprietary file
is created.

Consequently, HP's stock updater is not a direct Lefony first-install vehicle.
Entering it without tweezers is feasible, but a Lefony-controlled payload does
not pass the observed signature boundary without HP authorization. A separate
intended execution mechanism, an HP-authorized bootstrap, or a responsibly
handled vulnerability would still be required.

## Research gates for a no-recovery install

A convenient install from the running HP OS is feasible only if at least one
of these emulator tests succeeds:

1. The normal HP update transport accepts a capsule we can authenticate using
   a key controlled by Lefony, or supports a separately authorized extension
   payload.
2. The normal OS exposes an intended native execution or maintenance API that
   can run a small RAM-resident NAND bootstrap.
3. A reproducible parser or protocol defect provides code execution. This is a
   security-research path, not a product assumption, and must be disclosed and
   tested without touching a physical NAND until the complete write set is
   understood.

Finding only an HP-signature-enforced updater is not enough: without HP's
private signing key, changing its payload while retaining a valid signature is
not a deployment design. In that outcome, ROM recovery remains necessary for
the first Lefony installation, while all later releases use Lefony's signed,
power-loss-safe A/B updater.

Before any physical experiment, the emulator must record every NAND erase and
program, prove that boot structures and the Linux/UBI backup remain recoverable,
and reboot successfully from the resulting image. A failed or interrupted run
must be repeatable from the untouched raw fixture.

## Upstream hardware references

- [Linux MXS/APBH DMA driver](https://github.com/torvalds/linux/blob/master/drivers/dma/mxs-dma.c)
- [Linux GPMI NAND driver](https://github.com/torvalds/linux/blob/master/drivers/mtd/nand/raw/gpmi-nand/gpmi-nand.c)
- [Linux ChipIdea device controller](https://github.com/torvalds/linux/blob/master/drivers/usb/chipidea/udc.c)
- [Linux i.MX USB miscellaneous controls](https://github.com/torvalds/linux/blob/master/drivers/usb/chipidea/usbmisc_imx.c)
- [Linux SNVS power-key driver](https://github.com/torvalds/linux/blob/master/drivers/input/keyboard/snvs_pwrkey.c)
