# HP Prime G2 emulator parity ledger

This is the implementation ledger for a one-to-one HP Prime G2 emulator.
“Modeled” means the behavior exists; it does not mean physical parity has been
proved. A row becomes **verified** only when the emulator is compared against a
repeatable observation from pristine Linux or a controlled physical test.

| Priority | Subsystem | Physical evidence | Current state | Next proof or implementation |
| --- | --- | --- | --- | --- |
| P0 | LCDIF scanout | Live register snapshot, DT, exact `mxsfb` source | Modeled; physical differential pending | SET/CLR/TOG, CTRL2 outstanding requests, VSYNC buffer latching, frame IRQ and FIFO underflow/recovery are implemented and regression-tested. Capture dynamic physical transitions for final proof. |
| P0 | Pixel/sync polarity | Live VDCTRL0 `0x11300001`, DT `pixelclk-active=1` | Corrected from wrong falling-edge requirement | Regression-lock rising-active state; separately model deliberately wrong polarity as a physical blank/fault case. |
| P0 | LCDIF clock tree | Live CCM snapshot and observed 18 MHz framebuffer timing | Linux/native parents modeled | Emulator accepts captured video-PLL selection 5 at 540 MHz and native PLL2 at 528 MHz. Capture clock-summary transitions for final proof. |
| P0 | IOMUXC/pads | DT pin groups; first combined direct-read command timed out | Display-only shadow model | Re-run the hardened one-register probes, verify offsets against the NXP register map, then implement daisy/select-input and electrical pad behavior used by fitted devices. |
| P0 | ILI9322 panel | Datasheet v1.12, DT SPI GPIOs/mode/rate, exact Linux init sequence | Register-level controller model; physical differential pending | SPI mode 3 command decoding, reset defaults/write masks, standby/power, `AUTO_DP` startup frames, display enable, pixel acceptance, color controls, and datasheet digital timing are modeled. Verify boundaries against physical traces. |
| P0 | Framebuffer serialization | Live 320x240 XRGB8888; HCOUNT/valid count 960 | Modeled for display path | Prove channel/byte order and line timing with physical patterns; model invalid packing and bus-width cases. |
| P0 | PWM7/backlight/panel power | DT plus live PWM7 and GPIO snapshots | Live clocks, nominal FIFO/repeats, FWE, compare/rollover IRQs and GPIO supply modeled | Implement watermark and output waveform contracts in `PWM-CONFORMANCE.md`; physical clock/pin/FIFO-edge timing needs qualification. |
| P0 | KPP keypad | Exact 50-key DT matrix; live input device | 8x8 MMIO model and native scan path implemented | Host events now enter the modeled row/column matrix; status/IRQ and migration are covered. Capture physical debounce/ghost/chord timing for final calibration. |
| P0 | Goodix touch | Live ID 5688/version 0200, I2C address and GPIO routing | Native-driver GT5688 I2C/GPIO model | ID/config/report registers, timed down/release, reset, active-low IRQ, missing/malformed/lost-IRQ injection, coordinate bounds and gesture sequencing are tested. Physical axes/calibration remain provisional until controlled corner taps are captured. |
| P0 | Boot chain/NAND | `/proc/mtd`, NAND geometry, DTB, FCB/DBBT, both U-Boot copies, A/B metadata, and slot readbacks from a private raw+OOB capture | Functional cold-boot boundary; 2026-09 boot regression reproduced | The modeled ROM validates FCB/DBBT/IVT, executes DCD, skips marked blocks, tries both U-Boot copies, and falls back to SDP. Exact emulation reproduces the NUL-truncated U-Boot environment stopping at an invisible prompt, then cold-boots repaired legacy and physical A/B stacks to a visible Lefony frame. Add BCH correction equations and differential command/DMA timing traces. |
| P0 | USB OTG1/recovery | Linux gadget enumeration; physical ROM descriptors and strings captured 2026-09-07 | Descriptor parity verified; native ChipIdea and functional ROM SDP transactions | SDP DCD/download/readback/IVT handoff executes captured U-Boot and boots Lefony from NAND. EP0/native endpoints and watchdog recovery are tested. Full HAB, other DCD commands, macOS USB-backend interoperability and physical timing remain open. |
| P1 | PF1550 PMIC | Live I2C binding, DT regulators/onkey/charger | Deterministic lifecycle model | Register state covers regulator/charger/on-key structure, charging/drain rates, running/suspended/off domains, and IRQ updates. Identity/status calibration and electrical sequencing still await safe physical reads. |
| P1 | SNVS/power key/RTC | Live input and RTC devices | SoC-level partial | Model button timing, duplicate PF1550/SNVS event paths, RTC, reset cause and shutdown/wakeup transitions. |
| P1 | GPIO | Live DR/GDIR/PSR snapshots for banks 1-4 | Only paths needed by current display | Implement banks, edge/level IRQs, direction/input/output behavior and connection graph for every board-routed pin. |
| P1 | I2C controllers | Live buses/devices and IRQs | Generic/incomplete | Model i.MX I2C registers, clocks, IRQs, arbitration/error states and attach PF1550/GT5688 device models. |
| P1 | Timers/interrupts | `/proc/interrupts`, SoC documentation | QEMU generic coverage | Diff every live IRQ source, implement missing GIC routing, EPIT/GPT behavior, watchdog and clock-dependent timing. |
| P1 | RAM/OCRAM/cache-visible map | `/proc/iomem`, CPU data, DT | Broad SoC support | Verify aliases/reserved regions, reset contents, OCRAM, DMA coherency/alignment and framebuffer reservation. |
| P1 | Reset/SRC/watchdogs | Live SRC snapshot, NXP U-Boot reset-cause decoder and Linux devices | Sticky/W1C status and watchdog boot overrides modeled | WDOG1/3 status, repeated recovery exit, cold reset, and NAND ROM reset ordering are tested. Physical reset-button/PMIC domains and retention still need differential capture. |
| P1 | Battery/charger/thermal | Live sysfs, PF1550 presence and HP ADC conversion algorithm | Deterministic battery/charger model; thermal pending | ADC1 conversion/calibration, battery voltage groups, USB power, charger modes/faults and charge/drain progression are covered. Capture physical ADC codes and PF1550 status at controlled charge points; add the fitted thermal path. |
| P2 | LEDs | DT heartbeat on GPIO1_IO02 active-low | Not modeled | Add GPIO-connected LED state and optional UI indicator. |
| P2 | Audio/unused SoC blocks | DT status and platform topology | Generic stubs | Determine fitted hardware first; do not implement disabled/unpopulated blocks merely because the SoC supports them. |
| P2 | Physical tolerances/fault injection | ILI9322 digital SPI limits plus NXP electrical specs and panel experiments | Panel SPI limits are sourced; other thresholds remain approximations | Replace remaining broad thresholds with sourced limits or measured boundaries; keep fault injection independent from nominal behavior. |

## Immediate capture queue after one calculator reset

1. Re-run the hardened capture to obtain clock, GPIO, and pinmux debugfs files
   plus the expanded live device tree.
2. Add a read-only `EVIOCGABS` helper for every Goodix absolute axis and
   multi-touch slot, then record untouched and controlled corner taps.
3. Verify the IOMUXC address list using the NXP register map and retry using
   the new one-register-at-a-time probes. The combined-command timeout is not
   evidence that the pins or KPP registers are absent.
4. Read only documented, non-destructive PF1550 identity/status registers via
   the bound Linux driver or carefully scoped I2C access. Never bus-scan.
5. Capture repeated LCDIF/CCM/PWM snapshots at normal brightness and during a
   Linux framebuffer pattern change to distinguish configuration from dynamic
   status bits.

## Offline implementation pass completed 2026-08-31

- [x] Machine-readable and Markdown register decoders with a golden captured-state decode.
- [x] LCDIF atomic aliases, CTRL2, frame-boundary buffers, IRQ and FIFO behavior.
- [x] i.MX KPP controller plus the physical Upsilon scan path and host matrix ingress.
- [x] Provisional Goodix 5688 I2C/register/reset/IRQ model with unknowns labeled.
- [x] PF1550 regulator/on-key/charger register skeleton with provisional values labeled.
- [x] GPMI/BCH command/ECC/OOB/geometry/partition skeleton using erased synthetic NAND only.
- [x] Renewable watchdog-first physical capture mode with bounded individual probes.
- [x] Physical-capture versus emulator-contract comparator and regression tests.

## Cold NAND boot milestone completed 2026-09-03

- [x] The i.MX6ULL ROM reads the captured FCB and DBBT structures instead of
  receiving an injected U-Boot executable.
- [x] The ROM validates IVT/boot-data bounds and executes the production DCD
  32-bit register-write list before entering U-Boot.
- [x] Primary corruption selects the redundant U-Boot copy; invalid boot
  control enters the emulated SDP device with USB identity `15A2:0080`.
- [x] A current Lefony capsule cold-boots from the private raw NAND fixture to
  a visible 320x240 application frame with no `-kernel` or loader device.

Run `python3 vm/test-prime-g2-nand-rom-boot.py` where the ignored private NAND
capture and archived current capsule are available. The checked-in model and
test contain no proprietary NAND bytes.

## Physical boot-regression milestone completed 2026-09-04

- [x] Replayed the actual `cbf3…`, `da8…`, and `e537…` failure mechanism:
  shortening `bootcmd_mfg` with NUL padding terminated U-Boot's packed default
  environment before `panel`, `fdt_addr`, `bootargs`, and `bootcmd`.
- [x] Proved at the U-Boot prompt that `bootdelay=0` was present while
  `bootcmd` was undefined. The kernel was never entered in these images.
- [x] Repaired the patcher with whitespace padding, preserving the original
  single terminator and all following variables.
- [x] Cold-booted the repaired legacy stream and the repaired physical A/B
  stream. The A/B test consumes the captured FCB, redundant metadata, slot-A
  bytes and SHA-256, and DTB, then requires a nonblank 320x240 Lefony frame.
- [x] U-Boot history inspection now parses only the environment U-Boot will
  import; strings located after an early double-NUL no longer pass validation.

This reproduces a concrete failure in the archived NAND boot stacks. Physical
revalidation of the repaired bootloader is still required before attributing
every reported blank screen to this cause. It does not complete the
one-to-one project: reset-domain, analog power, precise BCH, and physical timing
items in the ledger remain open.

## ROM recovery and reset milestone, 2026-09-07 (QEMU r32)

- Physical, read-only USB descriptor capture from the connected calculator
  now matches the emulator byte-for-byte: device/configuration/HID report and
  language/manufacturer/product/configuration/interface strings. The preserved
  fixture is `reference/rom-usb-descriptors.json`; it contains no unique serial.
- The functional SDP implementation accepts HID SET_REPORT command/data,
  streams padded 1024-byte download reports into RAM, reads RAM/SRC registers,
  executes the Prime's 32-bit DCD writes, handles skip-DCD and status commands,
  and enters an open ARM image through its IVT. USB reset/disconnect discard
  unfinished transfers. Invalid IVTs and unsupported commands fail explicitly.
- SRC reset status is sticky and write-one-to-clear. WDOG1 and WDOG3 cause
  bits, acknowledgement, retained boot overrides, and repeated exit-recovery
  sequences are tested. This does not establish the physical reset-button or
  PMIC reset domains; QMP `system_reset` still represents the modeled cold reset.
- NAND ROM selection runs after device reset has latched SRC state. Image
  entry runs on the vCPU thread, preventing an executing translation from
  overwriting the new PC. Both were previously emulator ordering defects.
- Integration tests perform two recovery/exit/NAND boot cycles and a cold
  reset, and require a visible frame afterward. A separate test starts with
  invalid FCBs, sends the captured U-Boot image and DCD through SDP, then boots
  the current Lefony capsule from NAND to a visible frame.

The SDP transport remains the local transaction socket, not a macOS USB device
backend. Its CPU handoff uses a reset profile rather than an instruction-level
ROM image. HAB/CSF execution, arbitrary register writes/reads outside RAM and
SRC, other DCD operations, electrical timing, and exact reset-domain retention
remain unverified or unsupported. These tests are not a claim of full parity.

Read-only physical comparison commands:

```sh
python3 scripts/capture_prime_g2_rom_usb.py --check hardware/prime_g2/reference/rom-usb-descriptors.json
python3 scripts/capture_prime_g2_rom_usb.py --src
```

The second command requests only SDP READ_REGISTER at five fixed SRC addresses;
it never sends WRITE_REGISTER, WRITE_FILE, DCD, JUMP, reset, or NAND commands.
Earlier libusb attempts required a privileged path that never reached the calculator.
macOS denied the unprivileged HID claim (`LIBUSB_ERROR_ACCESS`). The user then
approved the administrator prompt, but the privileged Python process could
not open the capture script under Documents (`Operation not permitted`). This
failure occurred before the script ran or any SRC read command was sent.
Descriptor capture succeeded without a claim. Administrator authentication
alone therefore does not resolve the macOS file-access restriction; do not
repeat authentication prompts as if the user had failed to approve them.

Follow-up: terminal-based sudo authentication succeeded and opened the script,
but libusb still could not claim the HID interface. Native macOS IOHID solved
the transport problem without administrator access, driver detach, or device
reset. `scripts/capture_prime_g2_rom_hid.c` now reads the same five fixed SRC
registers successfully as the ordinary user. Build it with the command in its
header and run `build/capture-prime-rom-hid`; no password is needed.

The physical result is preserved in `reference/rom-src-snapshot.json`: SRSR
is `0x1` (POR recorded), GPR9/10 are zero, SBMR1 is `0x893`, and SBMR2 is
`0x02000001`. This snapshot rules out a retained software boot override at
the time of this capture; it does not identify why the ROM selected recovery.
Battery presence and physical transitions still need separate observations.

## Captured boot-mode profile, QEMU r33

The Prime machine now initializes SRC_SBMR1/SBMR2 from the captured values,
`0x00000893` and `0x02000001`. Generic i.MX6UL EVK defaults remain separate.
Both registers ignore software writes, with software boot override remaining
in GPR9/10. The regression compares all five captured SRC values before boot,
checks SBMR write protection, reads the same values through SDP after watchdog
recovery, and compares the full profile again after a modeled cold reset.

These are the measured values for this calculator's captured state; they are
not proof that every physical reset/power domain has been reproduced. A
repeat read-only physical capture returned the same values. The capture
script now selects native IOHID automatically on macOS, compiling its small
fixed-register helper when needed. It does not request a password, detach a
driver, or reset the device.

These boxes mean the eight offline implementation tasks exist and pass their
current tests. They do not convert provisional behavior into physically
verified behavior; the capture queue above remains the evidence needed for
one-to-one sign-off.

## BCH mathematical reference qualification (2026-09-07)

`vm/prime_bch.py` now implements binary BCH generator construction, encoding,
syndromes, Berlekamp-Massey, and shortened-word Chien search. Its decoder sees
only damaged data and parity, never the injected error positions.
`python3 vm/test-prime-bch.py` builds the local U-Boot `lib/bch.c` unchanged as
an independent host oracle. The small compatibility wrapper avoids a macOS
`fls()` collision; it does not replace the oracle's ECC logic.

Oracle source SHA-256:
`2084bf1b132c86f461c96f13520e25de6ff1e0b2d4fb2debc7ebc300f107307b`.
The suite checks exact parity and corrected bit locations for GF(13) strengths
4/8/16/40, GF(14) strength 8, 512/522/1024-byte inputs, and exhaustive double
errors in a small GF(5) code. It includes data and parity corruption, clean
words, malformed inputs, and a selected uncorrectable overload vector.
Standalone unit tests retain an oracle-checked parity vector.

This is a validated **reference codec**, not yet QEMU controller integration.
It does not establish GPMI bit packing, metadata interleaving, erased-page
handling, bad-block-marker swapping, or BCH timing. Existing NAND captures
contain decoded payload plus OOB; they are not evidence of original on-chip
ECC codewords. The controller still has synthetic correction behavior until
the reference is connected to a validated wire-layout model. Beyond-strength
errors can miscorrect or be undetected; universal detection is not claimed.

## GPMI layout reference and newly measured discovery gap (2026-09-07)

`vm/prime_gpmi_bch.py` now decodes i.MX6 layout registers (four-byte data
units, ECC strength twice the encoded field, GF13/GF14 selection, and NBLOCKS
as blocks *after* the first). It packs interleaved LSB-first data/parity,
protects metadata with block zero, supports metadata-only block zero, derives
the non-byte-aligned marker location, and constructs per-block DMA status.
Seven tests cover those boundaries, real data/metadata/parity corruption,
an uncorrectable vector, and the archived recovery geometry below. The
reference is not yet linked into QEMU. Exact erased codewords are recognized;
threshold-based erased recovery remains unverified.

Sources for the layout are the local Prime U-Boot `drivers/mtd/nand/mxs_nand.c`,
Linux `gpmi_ecc_read_page_raw` and `gpmi_copy_bits`, and U-Boot's i.MX
`encode_bch_ecc` (which reverses data and parity bit order around the generic
codec). These support the register/packing model, not a physical parity
byte-for-byte qualification.

The archived physical log
`build/prime-g2-physical-qualification/restore-a606-20260903T034645Z/evidence/kobs.log`
reports strength 2, four 512-byte chunks, 10 metadata bytes, 2071 encoded
bytes, and marker byte 2028 / bit 2. The reference reproduces these values.
This is the recovery kernel's configuration, not a captured ONFI parameter
page or proof of the physical U-Boot's configuration.

A fresh r33 exact-NAND boot exposed a more important limitation: U-Boot prints
`cannot support the NAND, missing necessary info`, and qtest reads layout0
`0x030a0080`, layout1 `0x08400080` at BCH addresses `0x01808080` and
`0x01808090`. Those values configure **zero-strength ECC**. The runtime still
boots because QEMU supplies decoded payloads. The hard-coded payload marker
at 2038 is consistent with that zero-ECC path, but not the captured physical
recovery geometry. Consequently the successful runtime tests must not be
described as validating physical NAND ECC. NAND READID/parameter discovery,
dynamic marker handling, and real controller ECC remain required next work.
No physical reset or write was performed to obtain this emulator evidence.

## NAND discovery and dynamic marker adaptation, QEMU r34

The GPMI command path now handles READID address `0x20` and PARAM `0xec`,
including three identical 256-byte ONFI parameter pages with CRC16. The
default page is explicitly **PROVISIONAL**, not a hardware capture: it uses
the known 512 MiB / 2048+64 / 64-pages-per-block backing geometry and a 1-bit
per 512-byte requirement, rounded to strength 2 by MXS. The archived recovery
configuration supports that resulting strength, but does not prove the
actual ONFI contents. `onfi-parameters=/absolute/path` accepts a signature/
CRC/geometry-checked 256-byte capture; `onfi=off` retains a negative control.
An actual parameter-page capture remains on the parity evidence queue.

Unmodified captured U-Boot now selects layout0 `0x030a0880` and layout1
`0x08400880` (2-bit ECC), with no missing-NAND-information warning. The
decoded-capture adapter derives the marker bit location from those registers
instead of assuming byte 2038. Both DMA directions perform the involution:
logical backing to driver-visible buffers on reads, and driver-visible
buffers back to logical backing on writes. Unsupported capture layouts are
rejected instead of silently copying a fixed-size layout.

`vm/test-prime-g2-nand-discovery.py` tests real CLE/ALE/APBH traffic, ONFI
signature/CRC/redundant pages and disabled-ONFI behavior. DMA read/write
checks cover strengths 0/2/6/8, including the physical recovery marker byte
2028 / bit 2. The complete NAND boot suite still reaches visible legacy and
A/B Lefony, reproduces the archived broken environment, and exercises
recovery exits, resets, redundant firmware and invalid boot controls.
Reset qualification now also checks the guest-selected nonzero-ECC layout.

This closes the **parameter-discovery and hard-coded marker** gaps. It does
not close controller BCH mathematics, actual raw codeword backing, erased
thresholds, or DMA timing: the runtime controller still consumes decoded
capture records. Real ECC integration remains necessary. No physical writes,
resets, or administrator prompts were used for this qualification.

## Real controller BCH with explicit physical-page backing, QEMU r35

`vm/qemu/prime_g2_bch.c` is a C implementation of the independently checked
binary BCH codec: generator construction, byte-table encoding, syndromes,
Berlekamp-Massey, and shortened-word Chien search. Failed decoding leaves
input buffers unchanged. The C/Python differential suite covers clean,
correctable and beyond-strength inputs; ASan/UBSan checks 480 maximum-length
and parity-only cases across GF13/GF14 strengths 2 through 40. The U-Boot
oracle suite now also covers the board's strength-2 and unaligned strength-6
cases. Beyond-strength miscorrection/undetected errors remain mathematical
possibilities, not universally rejected conditions.

The controller now supports `prime-g2-gpmi-bch.physical-pages=on`. In this
mode BCH encode DMA stores actual interleaved codewords and decode DMA
computes corrections from those stored bits, including metadata and parity.
No fault location or expected correction count is passed to the decoder.
LSB-first unaligned transfers, GF13/GF14, metadata-only first chunks,
per-chunk correction/failure status and exact-erased-page recognition are
implemented. The status maximum is derived from actual decoding. Driver-side
marker swapping is not duplicated inside the physical BCH engine.

The qtest suite writes damaged physical pages through NAND/APBH (without any
fault injection hints), then compares corrected payload, metadata and status
against the Python model. It also checks exact encoder bytes, persistence
across process restart, and refusal to open a physical overlay as decoded
data. Physical overlays have distinct `PG2RAW1` magic; decoded overlays retain
`PG2OVL1`. Original private decoded captures are not reinterpreted or rewritten.

Important boundary: existing cold-boot capture tests still use the decoded
adapter. **ROM FCB/firmware loading from physical-page backing is not yet
implemented**, and that mode explicitly refuses the decoded-ROM shortcut.
The next work is to connect physical ROM decoding and qualify the same boot
chain through genuine codewords, not to call the existing decoded boot tests
proof of the new physical mode. Physical ONFI/codeword captures, erased-page
threshold behavior and command/DMA timing still require evidence.

## Physical-codeword ROM boot, QEMU r36

The ROM model now decodes the i.MX6ULL FCB's eight GF13/BCH-40 codewords
(128 data + 65 parity bytes, after a 32-byte prefix), checks the complete
1024-byte FCB checksum, validates the board geometry/marker fields, and
configures firmware BCH from the FCB. DBBT headers and redundant firmware
are read through actual codeword decoding. An uncorrectable firmware page
rejects that firmware copy rather than silently skipping the page/block.

An additional archive check recovered all four FCB copies from the projected
capture. Each had eight clean BCH-40 blocks and the same valid checksum;
each decoded FCB SHA-256 is
`8fd9ed9f1993290168d600d5719310a6ab9ea375bb37024b8ddc5670e3326231`.
The projection inverse is also tested on randomized FCB tails, avoiding a
test that only works because the archived tail is zero-filled.

`vm/prime_nand_image.py` produces explicitly **re-encoded qualification
fixtures**, not supposed physical acquisitions. It recovers/checks all FCBs,
preserves logical payloads and markers, generates actual interleaved parity,
and records source/overlay/output hashes. The r36 full-size fixture uses the
previously qualified repaired U-Boot and current Lefony capsule. Original
captures remain untouched. Its SHA-256 is
`93ff53c5bc6ea6e3cb99ac2f7c2856d41b56393ba05662208700890fb75e9bcd`.

`vm/test-prime-g2-physical-rom-boot.py` now proves these paths through the
physical-page backend, not the decoded adapter:

- Cold ROM -> BCH-checked FCB/firmware -> U-Boot -> visible Lefony UI.
- Forty corrected FCB bits plus corrected IVT and kernel errors -> visible UI.
- Valid BCH but invalid FCB checksum -> next FCB copy.
- Uncorrectable primary firmware -> redundant firmware copy.
- Repeated ROM-recovery exits, watchdog resets and system reset -> Lefony.
- All FCBs uncorrectable -> enumerated ROM SDP `15a2:0080`.

Both the physical-codeword and legacy decoded-capture boot suites pass. The
FCB/image unit tests bring discovery to 186 passing unittest cases. The ROM
is still a functional implementation, not execution of a captured mask ROM.
Full DBBT-list behavior, erased thresholds, native NAND timing/power/reset
traces, physical ONFI parameters, and ordinary physical codeword acquisition
remain required for one-to-one qualification. No physical writes or resets
were performed during this work.

## Single-NAND DBBT entries and marker policy, QEMU r37

The ROM now consumes BBTN data four pages after a DBBT header rather than
only recognizing the header fingerprint. The single-NAND format has NAND
index and entry count followed by up to 510 block indices in a 2 KiB page;
entry order is not assumed. Zero list pages means an empty table. i.MX6
header checksum/numberbb fields remain reserved, not mistaken for the count.
The implementation validates each whole candidate before publishing a
ROM-local bitmap. Listed blocks affect ROM firmware positioning only; they
do not turn into physical NAND markers or leak from a rejected candidate.

Format evidence is the local U-Boot `imx-nandbcb.h` and `cmd_nandbcb.c`, plus
NXP's [BootControlBlocks.h](https://github.com/nxp-imx/imx-kobs/blob/c155f9e9d2e0008937c37d6e6f79e8436c099afa/src/BootControlBlocks.h)
and [mtd.c](https://github.com/nxp-imx/imx-kobs/blob/c155f9e9d2e0008937c37d6e6f79e8436c099afa/src/mtd.c).
Those sources explicitly permit unsorted entries and define `DISBBSearch`
as disabling physical-marker checks while continuing to use DBBT. Physical
mode now honors that FCB field. Effective physical marker reads also consult
overlay/programmed pages, rather than incorrectly inspecting only the base
capture. No new bytes are written to the original NAND fixture.

`vm/test-prime-g2-dbbt.py` qualifies empty lists, 510 unsorted entries, the
last NAND block, leading/interior listed blocks with erased physical markers,
visible Lefony UI after skipping, replayed physical markers, DBBT-only marker
policy with BCH still active, invalid NAND/count/range fields, unsupported
page counts, corrected/uncorrectable BBTN data, transactional copy fallback,
and enumerated ROM recovery when all required lists are absent. The full
physical-codeword and decoded boot/reset suites continue to pass.

Inspection of the re-encoded archived working stack found empty tables in
the first three valid DBBT headers; its fourth candidate occupies the known
bad block. This change therefore closes a model gap, not evidence of a
DBBT-caused physical regression. Current handling covers the single-page,
single-NAND format emitted by the Prime's kobs/U-Boot chain; larger/multi-NAND
lists are explicitly unsupported. Malformed-input rejection rules and exact
ROM search timing still need physical trace comparison. Other open parity
work includes erased thresholds, NAND operation timing/power behavior,
physical ONFI/codeword captures, and the remaining board peripherals.

## r38: physical-page erased thresholds

Physical-page BCH decoding now applies MODE[7:0] to the count of zero bits
in each complete codeword (including first-chunk metadata and parity).
Recognized erased chunks report FF, retain their raw DMA data, and contribute
to DEBUG1. The count is refreshed on each ECC transfer. Threshold zero keeps
the previous exact-all-ones behavior. Programmed FF payloads with real BCH
parity are decoded as normal codewords, not identified by payload alone.
This does not change the explicit decoded-capture compatibility mode.

Evidence: the local Prime U-Boot `drivers/mtd/nand/mxs_nand.c` sets MODE to
ECC strength on MX6UL and performs software FF repair after reading DEBUG1;
the downstream Linux `gpmi-lib.c` and `gpmi-nand.c` agree. The original
[driver patch](https://lkml.iu.edu/hypermail/linux/kernel/1606.3/00660.html)
explains the software repair and supplies the nine-bit DEBUG1 mask. NXP's
[threshold explanation](https://community.nxp.com/t5/i-MX-Processors/Handling-bit-flip-in-erased-page/m-p/427816)
states that both data and ECC bits count toward a chunk's threshold.

Limitations: summing recognized erased chunks and saturating at 0x1ff is an
explicit provisional functional choice. Related NXP documentation describes
a ten-bit count, so overflow width, saturation and mixed-page aggregation
must be resolved with Prime measurements before claiming register-exact
parity. Full STATUS0 flags, FCB erase-threshold configuration of the ROM
model, timing and power-loss behavior remain separate open work. This closes
a known model omission; it does not establish another physical boot cause.
No calculator writes, resets or privileged operations were used for r38.

The Python reference and real-QEMU APBH test cover threshold boundaries,
metadata/data/parity damage, non-byte-aligned codewords, mixed erased and
programmed chunks, programmed FF negative controls and counter refresh.
These verify the implementation against the stated model, not against a
new physical NAND acquisition.

r38 qualification passed all 188 repository unit tests, 140 C/Python BCH
differential cases, 480 sanitizer boundary cases, NAND discovery/threshold
and persistence tests, peripheral and ROM recovery suites, both complete
physical-codeword and decoded boot/reset suites, and the DBBT suite.
Binary SHA-256: `d56a0fa23c6af8b0ae0071c779053bf4cf5157dfe66efd70164f3533d6a3a6c0`.
The local qualification manifest is
`build/prime-g2-emulator-qualification/r38-20260907/qualification.json`.

## r39: FCB-to-BCH_MODE ROM handoff

The physical-page ROM path now applies `fcb_block.erase_th` (offset 0x5c)
to BCH_MODE's defined threshold bits before reading DBBT or firmware.
Evidence is the local upstream U-Boot `imx-nandbcb.h` field comment explicitly
specifying BCH_MODE; MODE[7:0] is also defined in the Prime fork's
`arch/arm/include/asm/mach-imx/regs-bch.h`. This connects the r38 decoder
behavior to boot-control configuration instead of leaving its threshold zero
until U-Boot runs. Decoded-capture compatibility handling is unchanged.

`vm/test-prime-g2-fcb-mode.py` halts the CPU before U-Boot executes and checks
thresholds 0/1/2/8/255, masking reserved high bits, and fallback from a valid
FCB with an unusable DBBT to another FCB with a different threshold. Each
case deliberately changes the live register and checks that a reset restores
the selected FCB configuration. The test fails on r38 at threshold 1.
The original re-encoded archive declares threshold zero, so this omission
does not explain its historical physical boot regression. Real ROM traces,
exact reserved-bit behavior and the remaining status/timing work still need
qualification; successful synthetic cases are not proof of full parity.

r39 passed the new halted-CPU configuration/reset test, all 188 unit tests,
NAND discovery/threshold/persistence, physical and decoded full boot/reset,
DBBT, ROM SDP and peripheral suites. Binary SHA-256:
`c981fe216679d6995f6691784136aea680b798db0c6105e08553aaa139667b1d`.
Evidence is recorded under `build/prime-g2-emulator-qualification/r39-20260907/`.
A native-HID read-only physical snapshot again showed SBMR1=0x893,
SBMR2=0x02000001, SRSR=1, GPR9=GPR10=0. No password, download, reset or
NAND write was used. Those register values alone do not establish why the
calculator is in recovery.

## r40: BCH completion interrupt lifecycle

BCH completion now sets CTRL.COMPLETE_IRQ and drives a level-sensitive output
only when CTRL.COMPLETE_IRQ_EN is also set. Enabling an already-pending result
asserts the line; masking it leaves completion pending; CTRL_CLR acknowledgement
deasserts it. Direct, SET, CLR and TOG writes recompute the line, as do device
reset and migration post-load. Decode and encode paths use the same helper.
STATUS0 and DEBUG1 reject guest writes rather than inventing an interrupt
when STATUS0 bit 0 is written. MODE's reserved high bits are masked.

The Prime fork's `regs-bch.h` defines these bits, and `mxs_nand.c` enables
completion through CTRL_SET and acknowledges through CTRL_CLR. The NXP-authored
[i.MX8MP reference manual](https://debix-oss.oss-cn-hongkong.aliyuncs.com/debix/IMX8MPRM%20Rev.%201.06.pdf)
describes the shared BCH CTRL register lifecycle. This related-chip source
does not independently prove all i.MX6ULL pipeline behavior.

The QTest qualification intercepts the NAND device's actual sysbus IRQ 1,
not a synthetic status register. It tests disabled completion, pending enable,
mask/unmask, acknowledgement, encode/decode completion, CTRL aliases/direct
writes, read-only results and system reset. It fails on r39 because a masked
decode emits both a raise and a lower event. Migration has a line-recompute
hook but has not yet received a dedicated cross-process qualification.

Still incomplete: full STATUS0 result fields, completion backpressure while
an earlier result is pending, debug/AHB-error interrupt sources, BCH soft
reset and clock-gating timing, and physical trace validation. The ROM boot
and peripheral tests cannot substitute for those gates. No physical device
operations are required by this change.

r40 qualification passed the IRQ-wire test, all 188 unit tests, FCB MODE,
NAND discovery/threshold/persistence, both complete boot/reset suites, DBBT,
ROM recovery and peripheral suites. The first peripheral run exposed a
host-timed PWM test that treated two identical samples of a wrapping counter
as failure. It now requires progress within 100 ms, checks sample bounds and
checks that disabling PWM stops the counter; 20 repeated SNVS/PWM runs passed.
The PWM model was not changed. Binary SHA-256:
`cd8700b697c70e88900ea11be2ff490ef194cea3a639f9b7a526e00cb7e47893`.
The local manifest is under `build/prime-g2-emulator-qualification/r40-20260907/`.

## r41: physical ROM clock and NAND-status evidence

`scripts/capture_prime_g2_rom_usb.py --src --clocks --nand-status` now supports
fixed read-only register profiles through native macOS HID, without sudo.
The NAND profile first reads CCM_CCGR4/6 and refuses NAND MMIO unless all
required APB/core/interconnect gates are enabled. It never enables clocks,
accesses data FIFOs, resets, downloads code or issues NAND commands. Native
and Python transports share tested whitelist/guard semantics; arbitrary
address arguments remain unsupported.

The live capture is preserved in
`hardware/prime_g2/reference/rom-clock-nand-status-20260907.json` and a second
read matched the saved descriptors and all requested registers. It records:

- BCH_STATUS0=0x4: the uncorrectable flag for a prior controller operation;
  it does not identify the affected page or prove the cause of every failure.
- BCH layout 030a0880/08170880: 2048 payload bytes, 10 metadata bytes, four
  GF13 BCH-2 chunks, and 2071 transferred codeword bytes.
- BCH_VERSION=0x01000000; MODE=0; DEBUG1=0; CTRL=0.
- GPMI_TIMING0=0x00010202, TIMING1=0x003b0000, TIMING2=0x23023336.
- The prior SRC state is unchanged, including GPR9=GPR10=0.

This reveals a genuine model mismatch: the functional ROM configured the
2112-byte backing-record size as PAGE_SIZE. r41 computes transfer bytes from
the FCB's metadata, data and parity geometry and matches the captured 2071.
It also supplies the captured read-only BCH version. It does not copy an
uncorrectable flag into the emulator: simulated errors must come from decoded
codewords. The existing reference fixture is still explicitly re-encoded,
not a raw physical NAND acquisition. No physical storage was changed.

Clock fields and masks follow the Prime fork's `crm_regs.h` and `clock.c`.
With their 24 MHz reference assumption, the captured PLL2/PFD2 settings imply
396 MHz followed by divide-by-two for GPMI/BCH (198 MHz). This is a
register-derived inference, not a measured clock or proof that those settings
were active at the failed NAND read. In particular, this snapshot must not be
mistaken for pristine power-on defaults or a trace of the failing operation.
The next hardware evidence needed is the actual failed page/codewords and
time-ordered controller state. Clock-coupled NAND timing, full STATUS0 and
physical fault comparison remain open gates.

r41 passed 193 unittest cases, native capture compilation/whitelist checks,
physical capture comparison, FCB size/version/threshold handoff, BCH IRQ,
NAND discovery/threshold/persistence, both full boot/reset suites, DBBT,
ROM SDP and peripheral tests. Binary SHA-256:
`bbd28fc00ede32559360332e9b70177938ec44060aabd2233db2c15538a3c63d`.
The manifest is under `build/prime-g2-emulator-qualification/r41-20260907/`.

## r42: BCH STATUS0 error fields from decoded codewords

Ordinary physical-page decoding now publishes STATUS_BLK0 in bits 15:8 and
the page-wide CORRECTED/UNCORRECTABLE flags in bits 3/2. The first field is
not the maximum number of corrected errors in any chunk. Both flags can be
set when different chunks contain correctable and uncorrectable errors.
A subsequent decoded page replaces the previous results; acknowledging the
completion IRQ and attempting a guest write to STATUS0 leave them intact.
Encoding does not replace the last decode result.

The field definitions are in the Prime U-Boot `regs-bch.h`, consistent with
the NXP-authored [BCH register description](https://debix-oss.oss-cn-hongkong.aliyuncs.com/debix/IMX8MPRM%20Rev.%201.06.pdf).
The real `STATUS0=4` snapshot is consistent with the first chunk being clean
and a later chunk being uncorrectable; the snapshot does not identify the
page, the specific later chunk, or the cause of its corruption.

The NAND/APBH suite stores independently damaged physical pages with no
decoder fault hints. Explicit vectors check clean reads, corrected first or
later chunks, an uncorrectable later chunk yielding 0x4, mixed corrected and
uncorrectable chunks, and subsequent clean-page refresh. Additional checks
cover GF13/GF14 layouts and erased thresholds. Only documented error fields
are asserted: ALLONES semantics with thresholds/programmed FF, HANDLE/CE,
pipeline backpressure, specialized ROM FCB status reporting and migration
qualification remain open. Decoded-capture compatibility is not promoted to
physical error evidence. The new tests reject r41's always-zero STATUS0.

r42 passed 193 unittest cases, the new STATUS0 codeword vectors, NAND
discovery/threshold/persistence, FCB configuration, IRQ, both full boot/reset
suites, DBBT, ROM SDP and peripheral tests. Canonical test pages preserve
the physical marker through driver-side swapping and verify program success;
the initial un-swapped fixture correctly triggered bad-block rejection.
Binary SHA-256: `c487f8da358163c16439e6b09886c0c8a14276d0a25ac938cdb199ba5e1f1cc2`.
The manifest is under `build/prime-g2-emulator-qualification/r42-20260907/`.

## Physical retained-DMA evidence (2026-09-07, QEMU remains r42)

The read-only capture tool now offers `--dma-status`, `--dma-chain` and
`--dma-buffers` on macOS. It checks the APBHDMA clock before APBH reads,
requires an idle channel and aligned on-chip-RAM pointer, and bounds the
descriptor window to 1024 bytes within 0x00900000..0x0091ffff. Payload and
auxiliary reads require a unique ECC descriptor and independently validated
OCRAM buffer bounds (2048+64 bytes). No registers are written, no DMA is
started and no NAND command is issued. `--output` creates a new capture and
refuses to overwrite an existing file. Clock/register offsets follow the
Prime U-Boot `crm_regs.h`, `regs-apbh.h` and `imx-regs.h`.

Saved physical evidence:

- `reference/rom-dma-chain-20260907.json`: idle APBH channel 0, CURCMDAR
  0x00901f08, no APBH error, and retained descriptors in OCRAM.
- `reference/rom-dma-buffers-20260907.json`: the same chain plus retained
  decoded payload/auxiliary buffers. Repeated capture matched every saved
  descriptor, register and buffer word.

`scripts/analyze_prime_g2_rom_dma.py` validates a READ0/READSTART chain that
reaches the current terminating descriptor. Its command bytes are
`00 00 00 00 05 00 00 00`, followed by READSTART 0x30. Under the Prime's
two-column/three-row-byte convention this is column 0, page 0x500 (1280).
The two additional zero address bytes are retained explicitly: their exact
hardware interpretation is not silently assumed. The ECC descriptor requests
2071 bytes into payload 0x00907000 and auxiliary 0x0090b074.

The auxiliary statuses are `[0, 0, 254, 0]`: the third codeword is reported
uncorrectable. The captured BCH_STATUS0 remains 4. All 2048 retained payload
bytes match page 1280 of the archived r36 reference after marker fixup,
including the IVT at offset 1024. Payload SHA-256 is
`4781c830aee3c3a7e71a5a1fe7bb986706725e8cd3160bfbaccad875d61e8a22`.
The reference FCB declares firmware starts 512/1280 and 190 pages per copy.
Reproduce the comparison with the analyzer's `--reference-nand` option and
`build/prime-g2-emulator-qualification/r36-20260907/reencoded-physical-nand.raw`.

This strongly narrows the current retained failure evidence to the secondary
U-Boot first-page read, before a successful bootloader handoff. It does not
prove which bits were read incorrectly: the buffers are decoded and may
already have been modified by ROM marker handling. The reference's parity
was regenerated, and matching payload does not establish physical parity.
ECC layout, parity corruption, read timing and stale-buffer possibilities
must be distinguished with actual raw page/codeword acquisition and an
execution trace. It is not justification to suppress ECC failures or to
attribute every historical display failure to this one event.

The QEMU binary was unchanged during this evidence-gathering turn. New tests
cover capture guards, output protection, chain bounds, incomplete/malformed
chains, active-channel rejection, and the retained chunk-status decoding.
All 204 unittest cases pass. The evidence manifest is under
`build/prime-g2-emulator-qualification/physical-dma-20260907/`.

## r43: replaying the physical ROM DMA chain

`vm/test-prime-g2-retained-dma.py` seeds the exact captured descriptor and
command bytes into emulated OCRAM, configures the captured BCH layout, and
starts APBH at the captured chain head. It checks the resulting payload,
per-chunk statuses, STATUS0, terminal descriptor, NEXT, BAR and semaphore.
The clean r36 reference reaches the retained terminal descriptor and matches
the captured payload after marker fixup, without an ECC failure.

A separate, explicitly synthetic case flips 16 parity bits in the third
codeword while preserving all data bits. It must yield statuses
`[0, 0, 254, 0]` and STATUS0=4 with the same payload. This establishes that
parity-only corruption can produce the observed decoded outcome, not that
these are the unknown physical parity bytes. The actual reference file still
contains regenerated parity, not a raw acquisition of page 1280.

Replay exposed two register gaps: CH0_CMD was always zero instead of the
captured terminal 0x48, and PHORE was returned in the low byte instead of
SEMA[23:16]. r43 records the last fetched command and corrects PHORE's field;
INCREMENT remains the writable low byte. CMD writes are ignored. The new
command state resets to zero and uses NAND migration version 2, with version
1 accepted without that previously unmodeled field. Cross-process migration,
live byte-count changes, DMA_SENSE failure branches, cycle timing and pending
BCH-result backpressure still need qualification.

No calculator accesses are required for this replay. The sources for the
semaphore/command fields are the Prime fork's `regs-apbh.h` and the captured
physical terminal state; matching a stopped terminal does not prove active
DMA timing parity.

r43 passed the exact-chain clean/synthetic-parity replays, CMD/PHORE checks,
all 204 unittest cases, NAND discovery/status/threshold/persistence, both
full boot/reset suites, FCB configuration, BCH IRQ, DBBT, ROM SDP and
peripheral suites. Binary SHA-256:
`ee96cd4397a09dd04e6de6b2385a9b161a7340d006a7f87f0ff45ed3f7b0af87`.
The manifest is under `build/prime-g2-emulator-qualification/r43-20260907/`.

## Raw-page experiment qualification on r43

`scripts/prime_g2_raw_read_plan.py` produces an offline plan for only the
captured read-only descriptor template and secondary boot page 1280. It
validates command/address bytes, PIO words, links, the terminating SENSE
alternate branch and the bounded OCRAM destination. It does not implement
hardware transport or execute any operation on the calculator.

The retained-DMA integration suite now temporarily changes four descriptor
words to read all 2112 raw bytes with BCH disabled. Both clean and synthetic
third-chunk parity-damaged records match byte-for-byte, including parity.
The test checks that auxiliary RAM, BCH result status and the NAND overlay
are unchanged. It restores all four words and the entire 2112-byte RAM
destination, verifies those backups byte-for-byte, and reruns the original
ECC-enabled chain to reproduce its original payload/status. The extra 64
bytes beyond a normal 2048-byte payload are explicitly backed up and tested.

These checks qualify the experiment in QEMU only. They do not establish
physical DMA timing, SENSE failure behavior, or complete controller-state
restoration. No physical writes, resets or NAND access were performed in
this round. The QEMU binary remains r43. All 207 unit tests, retained-DMA
replay/raw restoration, NAND discovery, BCH IRQ, ROM recovery and complete
physical-codeword boot/reset suites pass. The qualification manifest is in
`build/prime-g2-emulator-qualification/raw-read-20260907/`. Physical raw parity
and time-ordered boot evidence remain missing; the root cause of the current
calculator failure is not yet established.

## Cross-process NAND checkpoint qualification on r43

`vm/test-prime-g2-nand-migration.py` now migrates a halted emulator through a
local Unix socket into an independently started QEMU process. It captures
the retained ROM chain after a read, with BCH completion pending and enabled,
non-default MODE, and PHORE=3 queued without a next descriptor. The test
checks CMD, PHORE, BCH registers, OCRAM descriptors, payload and auxiliary
bytes after migration. It also checkpoints 37 bytes into a raw cached-page
read and checks the next 100 bytes resume at the correct cursor.

Both clean and synthetic third-codeword parity-damaged cases pass. The
destination starts with an empty overlay even when the source contains a
damaged page. Three subsequent ECC reads consume the saved semaphore and
reproduce the original data and chunk statuses. Thus the damaged case checks
that sparse NAND state transfers, rather than merely reopening an identical
overlay file. These are emulator-only experiments on regenerated parity.

This qualifies current r43-to-r43 NAND checkpoint state with the same machine
configuration and backing NAND. It does not qualify old-version migration,
mismatched backing/configuration rejection, persistence of migrated overlays
after a later process restart, electrical timing, or interruption mid-DMA
(the present DMA executor is synchronous). Register-level pending state is
checked; this test does not intercept the restored IRQ wire. No calculator
access or QEMU source/binary change was needed. Full hardware parity remains
incomplete.

## r44: APBH channel-zero completion interrupt

The previous model unconditionally pulsed APBH IRQ on a descriptor's IRQ
flag and silently cleared pending status at the start of every chain. The
new `vm/test-prime-g2-apbh-irq.py` fails against r43 because a masked
completion still produces a pulse. r44 retains CTRL1[0] until acknowledged
and drives the completion IRQ level from CTRL1[0] AND CTRL1[16]. Direct,
SET/CLR/TOG writes update the wire; reset lowers it and migration post-load
reconstructs it. Starting another transfer is not an acknowledgement.

The bit positions and driver acknowledgement sequence are defined in the
Prime fork's `arch/arm/include/asm/mach-imx/regs-apbh.h` and
`drivers/dma/apbh_dma.c` (`mxs_dma_enable_irq`, `mxs_dma_ack_irq`). The same
definitions are available in the [published U-Boot source](https://android.googlesource.com/platform/external/u-boot/+/refs/heads/android-tv-s-beta3/arch/arm/include/asm/imx-common/regs-apbh.h).

The new test intercepts sysbus IRQ output 2, checking masked completion,
enabling pending status, level retention across another non-IRQ transfer,
masking without losing status, acknowledgement aliases, non-IRQ descriptors,
other-channel isolation and reset. The NAND migration suite now also checks
the actual restored BCH and APBH wires and their acknowledgement/reassertion.
This work covers channel-zero completion, not APBH error IRQ generation,
other channel engines, cycle timing, soft-reset sequencing or SENSE branches.
No physical calculator access is involved.

r44 passes the new APBH IRQ negative-control regression, both clean and
parity-damaged migration cases with restored IRQ wires, all 207 unit tests,
retained DMA/raw restoration, BCH IRQ, NAND discovery, FCB MODE, DBBT,
peripherals, ROM recovery and both full boot/reset suites. Binary SHA-256:
`7b83a677d7ae5013645dd96d53b10c78bdcb24b4be25b5c0f65b0b8eb350f9cf`.
The qualification manifest is in
`build/prime-g2-emulator-qualification/r44-20260907/`. These passes do not
establish the cause of the current physical NAND failure.

## Distinguishing retained DMA completion from ECC success

The [NXP i.MX 6 Series Firmware Guide, chapter 13](https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/imx-processors/81029/2/iMX6_Firmware_Guide.pdf)
documents READ0/READSTART, ready wait, DMA_SENSE and ECC-read descriptor
ordering. On failed sense, BAR supplies the alternate descriptor address;
the ordinary path uses NEXT. Its sample terminal handlers report success
and failure separately from transfer completion.

The saved Prime chain has SENSE at `0x00901e9c`, ordinary NEXT `0x00901ecc`
(the ECC read), and alternate `0x00901f14` (terminal command `0x48`, result
1). Captured CURCMDAR instead identifies `0x00901f08`, the ordinary terminal
with result 0. Captured CMD, NEXT and BAR agree with that terminal in OCRAM.
The analyzer now reports this consistency explicitly, independently of the
third chunk's uncorrectable BCH result. It refuses the classification when
live registers are absent/inconsistent or the alternate handler is unknown.

This narrows the retained evidence: a normal DMA terminal and an ECC failure
can coexist. It does not establish a time-ordered execution path, rule out
earlier timeouts, or prove the physical parity bytes are corrupt. Testing
SENSE failure in the hardware model still requires a documented ready/busy
and timeout state machine; replacing it with a guessed immediate failure
would not establish parity. No QEMU binary or calculator state changed.

## r45: asynchronous NAND ready wait and timeout SENSE branch

The GPMI timeout uses 4096 clock cycles per TIMING1 unit, confirmed by
[Linux upstream fix 06781a5026350](https://lkml.iu.edu/2206.3/02725.html).
The documented DMA_SENSE alternate branch is described in the NXP firmware
guide linked above. r45 adds an external `nand-ready` digital input and a
virtual-time wait state, preserving the APBH descriptor and semaphore while
the NAND is busy. A ready edge cancels the timer and resumes the ordinary
chain. Expiry records CTRL1 timeout and channel-zero RDY_TIMEOUT status,
then SENSE selects the alternate BAR descriptor. A subsequent successful
wait replaces the failed sense result; reset cancels any outstanding timer.

The clock is explicitly supplied through `gpmi-clock-hz`, default zero
(unconnected). This is not yet a live CCM connection. With an unconnected
clock a busy wait remains pending until readiness, rather than silently
assuming a frequency. Tests explicitly supply 99 and 198 MHz. They check
one nanosecond before and at the rounded deadline, zero and maximum 16-bit
timeout fields, readiness-before-expiry, timer cancellation, successive
failure/success paths, unconnected clock and reset. The qtest accelerator
advances virtual time without executing guest instructions.

The existing captured TIMING1 value is 59 units. At the separately derived
198 MHz clock this corresponds to 241664 cycles, about 1.221 ms; it is a
register-derived expectation, not a physical measurement. The model does not
yet generate NAND program/read/erase busy intervals automatically, connect
the dynamic clock tree, deliver the GPMI timeout IRQ, or implement
READ_AND_COMPARE sense results. Timeout status lifetime, clock changes during
a wait and physical edge timing still need differential qualification.
The functional ROM surrogate also does not yet use this APBH wait path.

NAND migration v3 stores readiness, pending/completed wait, sense result and
the timer. Existing idle-state migration tests pass; an active-wait migration
test and cross-version/configuration checks remain required. No physical
calculator was accessed in this round.

r45 passed all 210 unit tests, the new timed-ready tests, retained DMA/raw
restoration, APBH/BCH IRQ, idle migration, NAND discovery, FCB MODE, DBBT,
peripheral and recovery checks, and both full NAND boot/reset suites. Binary
SHA-256: `198739e2ff7f2b99e3797dffc6d4ee37b637bbedee9e9c83154bad59dc3eed9e`.
The manifest is in `build/prime-g2-emulator-qualification/r45-20260907/`.

## Active-wait checkpoint qualification on r45

`vm/test-prime-g2-ready-migration.py` migrates a paused machine while DMA is
waiting for NAND readiness. It checks migration after one nanosecond,
halfway through the wait, and one nanosecond before expiry. For each phase,
the destination must remain pending until the original deadline, then either
take the SENSE error branch, accept a ready edge and complete normally, or
cancel the wait on reset. The source process is stopped before checking any
destination completion. DMA descriptor, semaphore, ready level, timeout
status and completion IRQ are observed.

The qtest accelerator maintains an external static clock counter in
`accel/qtest/qtest.c`, which is not migrated machine state. The first harness
attempt incorrectly left the destination counter at zero. The test now
aligns that external counter before loading any state, while the incoming
machine is suspended. It never sets or adjusts the migrated timer. This
distinguishes a test-clock epoch mismatch from an emulator timer regression.

These cases qualify current-build active-wait migration with the same
explicit 198 MHz clock configuration and synchronized qtest epochs. They do
not establish dynamic-clock changes, cross-accelerator migration, differing
clock configuration safety, or physical timing parity. The QEMU binary
remains r45; no calculator access is involved.

## r46: GPMI timeout interrupt and register-side effects

GPMI CTRL1 TIMEOUT_IRQ is bit 9 and TIMEOUT_IRQ_EN is bit 20 in the Prime
fork's `regs-gpmi.h`; the [published U-Boot definitions](https://android.googlesource.com/platform/external/u-boot/+/refs/heads/android-tv-s-beta3/arch/arm/include/asm/imx-common/regs-gpmi.h)
provide the same fields. r46 drives the timeout IRQ wire from both bits,
updates it on expiry and direct/SET/CLR/TOG writes, lowers it on reset, and
reconstructs it after migration. The active-wait test observes GPMI output
0 in addition to APBH completion output 2. Idle migration checks an explicit
pending/enabled timeout register fixture and verifies unrelated DMA reads
do not acknowledge it.

The new comparison-register negative control fails against r45: writing
COMPARE with its low bit set incorrectly cleared that bit and emitted an
IRQ pulse. r46 preserves comparison data and removes that invented trigger.
It also removes unconditional NAND PAGEPROG/BLOCKERASE IRQ pulses; the
NAND-only board has no modeled ATA device interrupt source. These synthetic
NAND operations are checked not to generate IRQ events. GPMI STAT and its
otherwise unused alias write offsets cannot fabricate hardware status.

Timed-ready tests now check masked timeout, enabling an already-pending
timeout, masking without discarding it, acknowledgements and read-only
status. This covers timeout delivery, not READ_AND_COMPARE execution, ATA
mode, physical timeout-status lifetime, clock gating or abort sequencing.
The live clock-tree connection and operation-derived busy intervals remain
unfinished. No physical calculator access was performed.

r46 passes all 210 unit tests, timed-ready and timeout IRQ tests, active and
idle migration, NAND discovery, APBH/BCH IRQ, retained/raw DMA restoration,
peripheral/recovery/FCB/DBBT suites and both complete NAND boot/reset suites.
Binary SHA-256:
`70d75ef7c0f7f33d240329c744610014a36d7e2f480dc98cce40cd182bf8f4da`.
The manifest is in `build/prime-g2-emulator-qualification/r46-20260907/`.

## NAND clock-root decoder groundwork

Inspection of upstream QEMU's `imx6ul_ccm_get_clock_frequency` confirms that
its current interface does not expose GPMI/BCH root clocks. The Prime
U-Boot `clock.c`/`crm_regs.h` and [Linux i.MX6UL clock driver](https://android.googlesource.com/kernel/common/+/e27738d0c5b1/drivers/clk/imx/clk-imx6ul.c)
identify independent muxes at CSCMR1 bits 19/18 selecting PLL2 PFD2/PFD0,
and dividers at CSCDR1 bits 22/19. The [Linux PFD implementation](https://raw.githubusercontent.com/torvalds/linux/master/drivers/clk/imx/clk-pfd.c)
provides the parent*18/fraction calculation and supported fraction range.

`scripts/prime_g2_nand_clocks.py` is an offline, exact-rational reference
decoder for these clock roots. It distinguishes known stopped clocks from
unknown external bypass inputs or unsupported fractions, preserves separate
gate encodings and stability flags, and never calls a configured root rate
a measured or effective clock. Its tests cover the saved 198 MHz settings,
both independent parents, all post-dividers, PLL 480/528 MHz selection,
oscillator bypass, missing inputs, gated/powered-down clocks and invalid
fractions. The assumed oscillator rate is explicit in its output.

This is groundwork for the live clock connection, not that connection.
CCM callbacks, power-mode gate interpretation, timer rescheduling on clock
changes and PLL/PFD settling remain to be integrated and qualified. The
QEMU binary remains r46, and no calculator access was performed.

## r47: live CCM NAND clock outputs

`qemu-prime-g2-nand-clocks.patch` adds independent `gpmi` and `bch` QEMU
clock outputs to the CCM model. Their root rates follow the register decode
above; guest CCM and ANATOP writes (including SET/CLR/TOG), reset and post-load
recompute them. RUN-mode gate values 01/11 enable the clock; 00 and unsupported
10 stop it. Powered-down/disabled PLL2, gated PFDs, unsupported fractions or
unknown external bypass inputs do not create a fabricated frequency. Rates
are represented as integer Hz before conversion to QEMU clock periods.

`vm/test-prime-g2-nand-clocks.py` observes the actual clock objects, not a
diagnostic frequency shortcut. It verifies writable field readback and
compares output periods against the separate Python reference across both
muxes, all eight dividers, both gate stages, PLL settings, PFD states, analog
aliases and reset. The captured configuration produces both 198 MHz roots.

The outputs are not yet connected to the NAND timer input. Its explicit
test-clock property remains unchanged, and existing wait/migration tests do
not prove clock-change handling. That next step must preserve remaining
cycles when frequency changes or gates close. Low-power clock modes,
PLL/PFD settling, external bypass input frequencies, clock-output migration
and physical timing remain unqualified. No calculator access was performed.

r47 passes all 217 unit tests, the live-clock output test, existing active/idle
NAND migration and waits, both full NAND boot/reset suites, NAND discovery,
peripherals, APBH/BCH IRQ and ROM recovery. The clock test fails against r46
because the CCM output does not exist. Binary SHA-256:
`ce49a7e3a90e88e5cdbe9ab702e48b5df88c6da949cb65bc5f0680d8dd2641ed`.
The manifest is in `build/prime-g2-emulator-qualification/r47-20260907/`.

## r48: cycle-preserving live NAND wait clock

The board now connects CCM's `gpmi` output to a NAND clock input. By default,
ready waits use that live clock, not a constant. The model records remaining
nano-cycles and the previous rate/time; on each clock change it subtracts
elapsed work before scheduling the remaining duration at the new rate.
Gating cancels the timer without consuming remaining cycles. A ready edge
while gated cannot complete the command until a usable clock returns.
The nonzero `gpmi-clock-hz` override remains for isolated tests, while
`use-ccm-clock=off` selects deliberately unconnected test behavior.

`vm/test-prime-g2-live-nand-timing.py` drives actual CCM registers after 1980
of 8192 cycles have elapsed. Slowing to 99 MHz preserves 6212 cycles; a
second frequency change preserves 5222. Core, IO and PFD gates hold the same
6212 cycles across one simulated second. A ready edge while gated completes
only on ungating. Slowed and gated waits also survive migration, followed
by another frequency change or ungating. Tests observe the APBH descriptor,
semaphore, timeout IRQ and actual NAND clock input. r47 fails the same test
because the wait timer was not connected to the live root.

NAND migration v4 adds remaining-cycle accounting. Same-build tests pass;
the legacy deadline-derived reconstruction is not a blanket qualification
of old snapshots or mismatched clock configurations. This implementation
covers WAIT_FOR_READY only: general transfer stalls, clocked BCH execution,
NAND-generated read/program/erase busy intervals, PLL/PFD settling, low-power
modes and physical edge timing remain unfinished. No calculator access was
performed in this round.

r48 passes all 217 unit tests, eight live-clock timing/migration cases,
existing active/idle migration and explicit-clock waits, clock-output tests,
NAND discovery, IRQ, retained/raw DMA, peripheral/recovery/FCB/DBBT suites,
and both complete NAND boot/reset suites. Binary SHA-256:
`724d102fdab69306d9b1503ce722be39862dd8f2338795d8dcfa0991bfba19b6`.
The manifest is in `build/prime-g2-emulator-qualification/r48-20260907/`.

## r49: gated GPMI/BCH transfer dispatch

The board now connects both CCM clock outputs to the NAND controller. APBH
holds a descriptor before transfer side effects when its required GPMI or
BCH clock is unavailable. The semaphore remains pending; payload/auxiliary
buffers and completion IRQs are unchanged. Clock callbacks retry dispatch
only when the required clocks are available, rechecking dependencies if a
second clock was gated in the meantime. NAND migration v5 preserves the
blocked-clock mask; reset clears it.

`vm/test-prime-g2-dma-clock-gates.py` replays the physically captured ROM
read chain against the regenerated reference NAND. Eleven cases cover GPMI
core/IO and BCH core/IO gating, disabled PLL, gated PFD, both clocks off,
GPMI gated after a BCH stall,
preconfigured ECC buffers with a one-word PIO launch, reset cancellation
and migration. Each held case preserves poisoned destination RAM and IRQ
levels across one simulated second, then completes with the correct decoded
payload when clocks return. r48 fails the same GPMI-gated case because it
advances NAND commands as far as the ready wait instead of holding the first
command. ECC launch requires a PIO command, so no-PIO terminal descriptors
do not retrigger the preceding decode.

This establishes dispatch-level clock dependencies, not cycle-accurate BCH
execution. Decode/encode calculations remain atomic once started; gating
mid-codeword, real NAND busy intervals, bus timing, latched-descriptor behavior
and physical reset/power-domain ordering still need qualification. The ROM
functional surrogate retains its separate boot-read path. No calculator
access was performed in this round.

Qualification passed on binary SHA-256
`612cdd7317be5b0029d96a7bd6897a007ef1b9967366ea4611e5eeb32b978a0b`:
217 unit tests; all eleven gated-DMA cases; live and explicit-clock timeout
tests; idle/active NAND migration; clock-output, discovery, retained/raw DMA,
BCH/APBH IRQ, FCB, DBBT, peripheral and recovery tests; and both full
physical-codeword and decoded-capture boot/reset suites. The qualification
manifest is `build/prime-g2-emulator-qualification/r49-20260907/qualification.json`.
These are emulator regression results, not a physical clock measurement or
proof of the calculator's NAND boot failure cause.

## r50: APBH channel gate and freeze

APBH CTRL0 channel-zero clock gate and CHANNEL_CTRL channel-zero freeze
previously stored register values without affecting DMA. Dispatch now checks
both controls, separately from the GPMI/BCH clock roots. Releasing one hold
cannot bypass the other. Direct/SET/CLR/TOG register access retains the same
semantics, and a falling hold retries pending dispatch. An idle channel with
zero PHORE no longer launches a descriptor on writes containing only reserved
or read-only semaphore bits.

The Prime U-Boot fork's `drivers/dma/apbh_dma.c` uses CTRL0 gating in
`mxs_dma_enable`/`mxs_dma_disable`; its MX6 `regs-apbh.h` selects channel-zero
bit 0, not the MX23 bit 8. Linux's
[MXS DMA pause/resume implementation](https://android.googlesource.com/kernel/common/+/22051d9c4a57d3b4a8b5a7407efc80c71c7bfb16/drivers/dma/mxs-dma.c)
uses CHANNEL_CTRL SET/CLR to freeze/resume the newer APBH controller.

`vm/test-prime-g2-apbh-pause.py` covers ten cases: gate, freeze, combined
holds, toggle/direct releases, peripheral-ready and timeout during a freeze,
system reset, cross-process migration, and zero semaphore increments. Paused
DMA leaves PIO destination registers and completion IRQ unchanged across one
simulated second. The independently running GPMI timeout can raise its own
IRQ without advancing the paused DMA chain. Tests also check other-channel
bit isolation. r49 fails both gate and freeze cases by completing immediately,
and fails the zero-increment case by fetching a descriptor with zero PHORE.

Existing migration v5 already preserves all required control registers,
semaphore and completed-wait state; no new serialized fields were needed.
This is dispatch-boundary behavior, not cycle-accurate APBH transactions.
Mid-burst freeze/abort behavior, channel software reset, semaphore overflow,
AHB error reporting and full physical power/reset ordering remain unfinished.
No calculator access or administrator privilege was used.

Qualification passed on binary SHA-256
`7dd87e7836006fc11394a42aeff46398c5fe978bfc9e7526e68198ae6d65f40e`:
all ten new pause cases, eleven peripheral-clock gate cases, 217 unit tests,
the live/explicit-clock timing and migration suites, retained/raw DMA,
discovery, BCH/APBH IRQ, clock output, FCB, complete DBBT, peripheral and
recovery tests, and both full NAND boot/reset suites. Source-copy comparison
and `git diff --check` also pass. Manifest:
`build/prime-g2-emulator-qualification/r50-20260907/qualification.json`.

## r51: NAND status read-and-compare

The controller now executes the single-byte, 8-bit NAND READ_AND_COMPARE
descriptor form instead of silently skipping it. The byte comes from the
same NAND data path as ordinary reads, with significant bits selected by
COMPARE's upper mask after XOR against its reference. No RAM DMA transfer
is performed. APBH SENSE selects its alternate descriptor on mismatch.
STAT DEV0_ERROR now reflects the existing channel-zero compare/timeout
sense latch; direct STAT writes cannot change it. Merely configuring
COMPARE does not execute a command or acknowledge an error. Compare failure
does not manufacture a GPMI timeout IRQ.

Reference basis: the Prime fork's GPMI register definitions; the
[NXP i.MX6 firmware guide](https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/imx-processors/81029/2/iMX6_Firmware_Guide.pdf)
for command modes; and NXP's
[i.MX8MP reference manual](https://debix-oss.oss-cn-hongkong.aliyuncs.com/debix/IMX8MPRM%20Rev.%201.06.pdf)
sections 9.5 and 9.7 for the status/compare/SENSE descriptor example and
mask/reference fields. Applying the shared controller description to the
Prime is a model inference, not a new physical trace measurement.

`vm/test-prime-g2-nand-compare.py` has nine functional cases: actual modeled
bad-block program failure, success, masked failure, matching failure
reference, full-byte match/mismatch, paused dispatch, success after failure,
and cross-process migration of the sense latch. It checks branch terminal,
semaphore, status, unchanged poisoned RAM, IRQ separation, and system reset.
r50 fails the program-failure case because it never performs the comparison.
The existing NAND-ready suite now checks DEV0_ERROR for both ready and
timeout outcomes as well.

Three additional tests verify that unqualified multi-byte, zero-count and
16-bit-bus compare forms stop without fabricating completion. Those tests
prove explicit limitations, not hardware parity. General compare sequencing,
PIO-only RUN execution, broader sense-latch lifetime, bus timing and physical
trace qualification remain unfinished. Migration uses the existing saved
sense latch without adding state fields. No physical calculator was accessed.

Qualification passed on binary SHA-256
`7efbdc0ee140e199d2552cb0db44bccf506f22d3d2e8394042815d4ab7b26dcb`:
nine functional compare cases and three explicit limitation checks, 217
unit tests, ready/timeout status, APBH pause, clock gating/timing, active and
idle migration, retained/raw DMA, discovery, BCH/APBH IRQ, clock-output,
FCB, complete DBBT, peripheral/recovery and both full NAND boot/reset suites.
The source copy matches the built tree and `git diff --check` passes.
Manifest: `build/prime-g2-emulator-qualification/r51-20260907/qualification.json`.

## r51 boot-path audit: reset polling and stubbed accesses

`vm/audit-prime-g2-boot.py --output NEW_DIRECTORY` now captures a bounded
write trace and unsupported-access diagnostics through the native runtime
entry marker, using a disposable NAND overlay. `--include-reads` also captures
polling; `--summarize-log LOG --output NEW_DIRECTORY` analyzes saved traces
without starting a VM. Reports identify host versus vCPU accesses, retain
diagnostics, and explicitly separate the functional ROM substitute from
instruction-level ROM execution. QEMU's `system/memory.c` supplies absolute
addresses for these events, not region-relative offsets. A touched region
may still only shadow registers; coverage never implies hardware parity.

On r51, the full read/write capture hit its size bound at 137,334,950 bytes
before runtime entry. It contains exactly 1,000,000 reads of APBH CTRL0 at
`0x01804000`, followed by 319,405 reads of GPMI CTRL0 before capture stopped.
The APBH sequence clears SFTRST/CLKGATE, sets SFTRST, then repeatedly reads
`0x80000000`: the expected automatic CLKGATE assertion never occurs.
The Prime fork's `arch/arm/mach-imx/misc.c:mxs_reset_block` waits for that
assertion; `drivers/dma/apbh_dma.c` ignores its return value. This explains
how the emulator can eventually boot despite a broken reset handshake.
Fixing block soft reset is now the next boot-fidelity priority, ahead of
adding more nominal-path assertions. This is an emulator defect, not proof
that the physical calculator has the same failure.

The lower-volume write capture reaches the runtime marker, touches 22
regions, and occupies 12,051,264 bytes. Unsupported accesses include MMDC
DDR initialization writes, OCOTP fuse reads, USBMISC reads/writes and an
IOMUXC GPR read. The current tests therefore do not establish faithful DDR
training, fuse contents, or the full USB/pad initialization path.

Evidence under `build/prime-g2-emulator-qualification/`:
`r51-boot-audit-20260907` (bounded incomplete read/write capture),
`r51-boot-write-audit-20260907` (completed write capture), and
`r51-read-address-audit-20260907` / `r51-write-address-audit-20260907`
(saved-trace summaries). Collector/parser tests bring the unit suite to 219
passing tests. QEMU remains r51, unchanged; no physical device was accessed.

## r52: APBH block soft-reset handshake

APBH SFTRST now clears channel registers/queued DMA/completion IRQ and
asserts CLKGATE. Clearing SFTRST leaves CLKGATE asserted until software
releases it. While reset is held, non-CTRL0 APBH writes are ignored. The
global block gate and reset bits independently prevent transfer dispatch.
Resetting APBH does not erase NAND storage or reset GPMI/BCH configuration.
The model detaches any pending DMA wait continuation; exact in-flight
peripheral-abort timing is not yet modeled.

The regression `vm/test-prime-g2-apbh-reset.py` follows the Prime U-Boot
fork's `mxs_reset_block` sequence. Direct, SET and TOG reset assertion clear
queued work/IRQ, preserve neighboring block configuration, reject channel
writes while reset is held, and allow new work only after clock-gate release.
The TOG case migrates while held in reset. r51 fails at the missing CLKGATE
acknowledgement.

A fresh cold-boot read trace on r52 shows exactly four APBH reads and the
expected `0 -> c0000000 -> 40000000 -> 0` handshake, compared with one million
APBH reads in r51. Trace directory:
`build/prime-g2-emulator-qualification/r52-read-audit-20260907`.
It remains an **incomplete** full-boot trace: its size bound was reached at
136,650,819 bytes after one million GPMI CTRL0 reads and 315,855 BCH CTRL reads.
Those two block reset handshakes remain the next demonstrated defects.
This is direct emulator execution evidence, not a physical reset capture.

APBH reset-clock prerequisites, cycle-level reset latency, in-flight bus
aborts and per-channel reset remain unfinished. No physical device was
accessed or changed.

Qualification passed on binary SHA-256
`bd3e33c9c9fa4655d6ee7e5c5b1078572e251a6368eeee3a1f6c863fa8d780ea`:
new reset tests, 219 unit tests, pause/compare/clock-gate/timing tests,
active and idle migration, retained/raw DMA, discovery, BCH/APBH IRQ,
clock-output, FCB, full DBBT, peripheral/recovery and both NAND boot/reset
suites. Source-copy comparison and `git diff --check` pass. Manifest:
`build/prime-g2-emulator-qualification/r52-20260907/qualification.json`.

## r53: GPMI/BCH reset and local clock gates

GPMI and BCH now acknowledge block soft reset by asserting CLKGATE, clear
their own configuration and IRQ, reject configuration writes while held in
reset, and retain the gate after SFTRST clears. Neither controller reset
erases NAND contents/status or resets neighboring controller registers.
The existing serialized register arrays preserve reset-held state.

DMA dispatch checks the local GPMI/BCH gate/reset bits before applying PIO
words, separately from the upstream CCM clocks. GPMI local gating suspends
the ready timeout's remaining-cycle accounting and defers ready completion
until ungating. GPMI reset cancels the old wait continuation, clears its
timeout/sense status, and cannot implicitly restart that wait on release.
The pending APBH semaphore is not falsely completed by a peripheral reset.

Tests add six block/alias cases including reset-held migration for each
controller, two local-gate cases in the captured ROM DMA replay, and four
live-wait cases (local gate, ready while gated, gated migration, reset during
wait). These cover configuration/IRQ isolation, preserved modeled NAND
failure status, exact remaining-cycle deadlines and absence of late IRQs.
r52 fails the block-reset test at the missing CLKGATE acknowledgement.

The complete read/write cold-boot trace now reaches native runtime entry:
`build/prime-g2-emulator-qualification/r53-read-audit-20260907`. It captures
24 regions in 78,389,160 bytes, below the trace-size limit. Each initial
APBH/GPMI/BCH reset handshake shows four reads and the expected
`0 -> c0000000 -> 40000000 -> 0` states, instead of the million-read timeout.
Later BCH completion polling is separate from this initialization sequence.
Remaining high-volume accesses include GPT counter reads; remaining explicit
stubs include MMDC, OCOTP and USBMISC. A completed trace does not qualify
those components, instruction-level ROM, or physical timing.

Reset prerequisites when upstream clocks are unavailable, precise reset
latency, in-flight bus aborts and real physical power/retention domains remain
unfinished. All work used the emulator and saved fixtures, not the calculator.

Qualification passed on binary SHA-256
`5f795602c2c7713f247eb913a3fe6f5dbc8162ce495d53ebbceb4c35714a1c82`:
all new reset/local-gate/wait cases; 219 unit tests; APBH reset/pause, compare,
clock/timing, active/idle migration, discovery, retained/raw DMA, BCH/APBH IRQ,
clock output, FCB, full DBBT, peripheral/recovery and both full NAND boot/reset
suites. Source-copy comparison and `git diff --check` pass. Manifest:
`build/prime-g2-emulator-qualification/r53-20260907/qualification.json`.

## r53 USB initialization gap: USBNC configuration is discarded

The completed boot trace includes USBMISC writes of `2` then `0` at
`0x02184800`, and `0x200` at `0x02184818`. The native driver in
`ports/lefony-prime-g2/ion/src/prime_g2/usb_diagnostics.cpp` first sets
NON_BURST_SETTING (bit 1), then clears only wakeup enables, and selects BVALID
as VBUS wakeup source (bits 9:8 = 2). The second write should preserve bit 1.
It does not because `fsl-imx6ul.c` still instantiates `a7mpcore-usbmisc` as an
unimplemented device returning zero. The Linux i.MX usbmisc driver confirms
the register fields and the read-modify-write configuration pattern.

`vm/test-prime-g2-usbmisc.py` now executes that native sequence against the
actual MMIO model, without booting a guest or accessing the calculator.
It **fails on r53**: non-burst and BVALID source read back zero. The test also
contains a port-isolation check to exercise once readback is implemented.
This is a deliberate failing hardware-contract test, not a passed parity
claim; it is separate from the general Python unit discovery suite.

The next implementation must replace USBMISC's placeholder with controller
configuration and actual wakeup-source/enable/status behavior connected to
USB/PHY events. Merely adding a writable register array would fix this
readback symptom without establishing wakeup or power-domain fidelity.
Reset values, read-only/W1C status, IRQ wiring and physical wakeup timing
still need source verification. This defect does not by itself establish
the cause of the physical calculator's historical NAND boot failures.

## r54: USBNC configuration and BVALID wake requests

USBNC is now a second MMIO region of the Prime USB device model instead of
the USBMISC placeholder. Known i.MX6 configuration fields preserve native
read-modify-write sequences, with independent port control and VBUS-source
registers. WIR is a hardware latch, not writable configuration. Port-zero
digital cable transitions set it when WIE, VBUS wake and BVALID selection
are enabled. Duplicate CONNECT commands do not create new edges. Clearing
WIE acknowledges WIR; writing WIR or clearing USBSTS does not. The wake
request and normal USB interrupt are ORed without acknowledging each other.
ChipIdea controller reset leaves USBNC intact; modeled system reset clears
it. USB migration v4 preserves configuration/wake latches and restores IRQ
and cable output levels without inventing a cable edge.

The i.MX Linux usbmisc driver supplies the field offsets and BVALID/WIE
configuration pattern. The shared-block WIR acknowledgement behavior is
also described in NXP's
[i.MX RT1060 reference manual, USBNC section](https://www.pjrc.com/teensy/IMXRT1060RM_rev3_annotations.pdf).
Applying that description and shared IRQ behavior to the Prime remains a
model inference pending an exact i.MX6ULL register/physical differential.
Cold-reset register defaults are explicitly provisional zeroes. ID/DPDM,
other VBUS selectors, overcurrent electrical behavior, port-one external
events and actual low-power wake latency are not yet implemented.

`vm/test-prime-g2-usbmisc.py` now passes the previously failing native
initialization sequence and exercises cable-source/IRQ masks, duplicate
edges, pending status, WIE acknowledgement, normal-IRQ independence, port
isolation, USB-vs-system reset, and cross-process pending-wake migration.
The fresh write boot trace reaches runtime entry and contains three USBNC
writes with no USBMISC/USBNC unsupported-access diagnostics:
`build/prime-g2-emulator-qualification/r54-write-audit-20260907`.
These results qualify the implemented digital path, not full USB parity or
the physical calculator's historical boot failure. No calculator access was
performed.

Qualification passed on binary SHA-256
`561bc56bc8f5c87cab2061366953a0bb424db042dad01adf6ab75852125fef86`:
the USBNC test; native USB enumeration, signed inactive-slot NAND
install/readback/pending commit, reconnect and recovery staging **in the
emulator**; 219 unit tests; NAND/APBH reset/gate/pause/compare/timing,
active/idle migration, discovery, retained/raw DMA, IRQ, peripheral/recovery,
clock-output, FCB, full DBBT and both NAND boot/reset suites. Source-copy
comparison and `git diff --check` pass. Native USB artifacts:
`build/prime-g2-native-usb.loAFP0`; manifest:
`build/prime-g2-emulator-qualification/r54-20260907/qualification.json`.

## GPT physical-clock Linux qualification and masked status (r55)

The patched GPT already supplies selector 5 at 3 MHz. The old Linux VM
builder still substituted a 24 MHz timer because its default launcher uses
stock QEMU. `PRIME_G2_PHYSICAL_GPT=1` now retains the physical GPT1 DT
properties, and `PRIME_G2_QEMU` selects the patched executable in that
launcher. The default stock-QEMU fallback remains unchanged.

`vm/test-prime-g2-linux-gpt.py` restores only the GPT properties in a
temporary copy of the existing Linux fixture DT. On r54 Linux reports
`sched_clock: 32 bits at 3000kHz`, switches to `mxc_timer1`, and reaches
`Welcome to Prinux`. This does not remove the other VM adaptations or
validate Linux NAND, physical power, DDR training or ROM behavior.

The expanded `vm/test-prime-g2-gpt-oscillator.py` exposed a separate r54
failure: output-compare status does not latch when its interrupt is masked.
The underlying QEMU scheduler filtered both event scheduling and status by
IR. The r55 patch schedules compare/rollover status independently, leaving
IRQ assertion controlled by SR and IR. It also restores masked OCR1
restart-mode scheduling. Register-event versus IRQ-mask separation follows
[NXP's GPT API](https://mcuxpresso.nxp.com/api_doc/dev/4627/a00017.html) and
[NXP support's GPT explanation](https://community.nxp.com/t5/i-MX-RT-Crossover-MCUs/i-MX-RT1010-GPT-behavior/td-p/1245506).
The latter is related GPT-IP evidence, not a physical i.MX6ULL differential.
Input capture, oscillator enable/prescaler upper fields, power gating and
cycle-exact boundary behavior remain unqualified. No calculator access was
performed; this is not evidence of the historical physical NAND failure's
cause.

The rebuilt r55 binary SHA-256 is
`53edeba8ec6ef35645216ed62db4c04a53c06583870bd628b7514c5d648f0172`.
Both GPTs pass 3 MHz counter/prescaler/stopped-counter checks, all three
masked compare flags, pending-event interrupt enabling/masking, selective
W1C acknowledgement and masked OCR1 restart. The Linux physical-GPT smoke
test also passes on r55. All 219 unit tests, USBNC wake/reset/migration,
and regenerated physical-codeword boot/correction/redundancy/repeated-reset
tests pass. Shell syntax, whitespace checks and peripheral source-copy
comparison pass. The first masked-compare test fails on r54 and passes on
r55; the hardware-parity and physical-failure-cause claims remain false.
The decoded-capture NAND boot suite, CCM clock-root tests and live NAND
timing/reset/migration tests also pass. Qualification manifest and Linux
console log: `build/prime-g2-emulator-qualification/r55-20260907/`.

## GPT reset and checkpoint IRQ continuity (r56)

The r55 model preserves a running timer's remaining deadline across process
migration, but fails to restore an already pending IRQ output. Both soft
reset and whole-system reset clear SR/IR while leaving the timer's output
wire asserted. These are independent, reproduced negative controls in
`vm/test-prime-g2-gpt-state.py`; they are not hypotheses about the physical
calculator's earlier boot failure.

The r56 patch recomputes the IRQ from loaded registers in a migration
post-load hook, and from cleared registers at the end of timer reset. No
new migration fields or synthetic status events are added. The test uses
two independent QEMU processes with qtest clocks explicitly aligned before
loading, and observes the GPT's actual sysbus IRQ output. Cases cover an
active deadline, pending enabled event, pending masked event, selective
acknowledgement, soft/system reset and absence of a late pre-reset event,
for both GPT instances. Physical reset sequencing, low-power clock behavior
and electrical timing remain unqualified. No calculator access is needed.

Qualification on r56 binary SHA-256
`134a3ab2f37c430a5b0781d6a61ca6825f02f5ea6fe1e07fa809bdb4e8536936`:
all ten GPT state cases and both oscillator suites pass, along with 219
unit tests, USBNC wake/reset/migration, live NAND timing/reset/migration,
Linux physical-GPT boot, and both regenerated-codeword and decoded-capture
NAND boot suites. The latter still reproduces the known packed-environment
failure and boots its repairs. Source-copy comparison, patch reverse-check,
shell syntax and whitespace checks pass. Manifest and Linux console:
`build/prime-g2-emulator-qualification/r56-20260907/`.

## PWM7 counter-contract corrections (r57)

The boot write trace includes the native backlight PWM7 setup at
`0x020f8000`. Auditing that model found a fixed 66 MHz counter for every
clock selector, writable PWMCNR and a maximum period of 65537 ticks, which
cannot be represented by the physical 16-bit counter. Six new black-box
cases fail on r56: read-only counter writes, disconnected clock, 32 kHz
rate, its prescaler, the maximum-period wrap and disconnect/reconnect phase.

The r57 correction leaves the counter stopped for CLKSRC=0, supplies 32768 Hz
for CLKSRC=3, ignores PWMCNR writes, and treats PWMPR=0xffff like 0xfffe.
The divisor-8 test also exposed overflow in the nanoseconds-times-prescaler
denominator: QEMU's `muldiv64` accepts a 32-bit denominator, so merely
casting the multiplication to 64 bits does not fix it. Divide the integer
source-clock ticks by the prescaler afterward; nested floor division is
equivalent for positive integers. Divisors 8 and 4096 now both pass.
Clock selectors and the special maximum-period encoding are corroborated by
the [Linux i.MX PWM driver](https://github.com/torvalds/linux/blob/master/drivers/pwm/pwm-imx27.c).
This is a counter correction, not full backlight parity: selectors 1/2
still use the existing 66 MHz approximation, CCM rate/gate transitions are
not connected, and FIFO/repeat/IRQ/output waveform behavior remains open.
Fractional phase across control writes and exact reset sequencing also need
qualification. No physical calculator access was performed; these bugs are
not evidence that the native driver's selector-2 setup caused its earlier
physical black screens.

Next clock-tree work has concrete local sources: native `backlight.cpp`
enables CCGR6 bits 31:30 and selects PWM CLKSRC=2; Linux 4.14
`drivers/clk/imx/clk-imx6ul.c` binds PWM7 to `perclk`, whose parent selector
is CSCMR1 bit 6 (IPG/OSC) and divider is bits 5:0. QEMU already calculates
IPG and perclk in `imx6ul_ccm_get_clock_frequency` but PWM does not use them.
Connect rate-change notifications and preserve accumulated phase rather than
recomputing all elapsed time at the new frequency. Gate and rate changes,
migration while gated, fractional phase and optical output require separate
tests. The saved ROM snapshot has PWM7 gated; native code enables it later,
so applying the ROM gate value permanently would be another false model.

Qualification on final r57 SHA-256
`268513b0807d3fd6db8e46c4548a78f4218f159ead66b4fb082a7fe31ffbf675`:
seven PWM cases, the peripheral suite including stock display counter
polling, ten GPT state cases, 219 unit tests, Linux physical-GPT boot and
both NAND boot suites pass. Patch application against r56, source-copy
comparison, shell syntax and whitespace checks pass. Manifest and final
Linux console: `build/prime-g2-emulator-qualification/r57-20260907/`.

## Live PWM7 CCM clocks and fractional state (r58)

The r57 fixed-66-MHz model fails all seven initial live-clock tests. PWM7
now receives separate gated IPG and perclk outputs from the existing CCM
tree, updated after register/analog writes, reset and migration load.
The RUN gate is CCGR6 bits 31:30; CSCMR1 chooses and divides the perclk
parent. Inputs 1/2 no longer substitute a constant frequency. Existing
generic parent PLL/bypass calculations remain subject to their own parity
limitations, and low-power modes have not been qualified.

On every rate change the counter first accounts for elapsed time using its
previous rate. It retains source-cycle/prescaler remainder without floating
point, including a 1 ns partial cycle across a long gated interval. LCDIF
migration v4 adds the cached rate and fractional remainder, with older
streams defaulting the missing fraction to zero. Preserving normalized
fractional phase on a PWM control-divider write is a model choice pending
physical characterization; the root-rate/gate tests do not prove that edge.

`test-prime-g2-pwm-clocks.py` covers OSC, perclk divider transitions, RUN
gate modes, fractional gating, unrelated PWM5 gate isolation, IPG versus
divided-perclk selection and active/gated cross-process migration. The
peripheral smoke test now enables the PWM7 gate explicitly. It also stops
the SNVS 1024 Hz periodic source before checking W1C, eliminating a race
where a new event could occur between the acknowledgement and readback.

PWM FIFO/repeat/IRQ/output-pad waveform, the optical effect of holding a
gated output, 32 kHz-domain gate routing and exact power/reset transitions
remain open. No physical calculator access was performed. The native driver
uses this faster source, but successful emulator tests are not proof of
the cause of its historical physical black screens.

Qualification on final r58 SHA-256
`6a18625826bce2ab8259ff32e66994bae587a1fc51c571a937ad50f4e97485ba`:
eleven live-clock/migration cases, seven PWM counter contracts, 219 unit
tests, peripheral suite, ten GPT state cases, USBNC, live NAND timing,
Linux physical-GPT boot and both NAND boot suites pass. Patch application,
shell syntax, source-copy comparison and whitespace checks pass. Manifest
and Linux console: `build/prime-g2-emulator-qualification/r58-20260907/`.

## PWM FIFO conformance audit after r58

The new black-box audit exposes four failures not covered by boot or counter
tests: FIFO occupancy stays zero across four writes, overflow is absent,
occupancy bits accept writes, and W1C writes inject status flags. Run
`python3 vm/test-prime-g2-pwm-fifo.py` to reproduce the failing tests. Use
`--audit NEW_JSON_PATH` only to collect evidence: its JSON explicitly marks
conformance false even though audit collection itself succeeds.

This turn changes tests and documentation, not the r58 binary. The exact
fixture/proof requirements and source distinctions are recorded in
`hardware/prime_g2/PWM-CONFORMANCE.md`. Results are under
`build/prime-g2-emulator-qualification/r58-pwm-fifo-audit-20260907/`.
Shared-IP SDK semantics and modern Linux's empty-FIFO workaround inform the
work, but do not establish the Prime's silicon erratum applicability. No
physical access occurred; no additional physical boot cause is claimed.

## Nominal PWM FIFO/repeat lifecycle (r59)

The four r58 FIFO audit failures are corrected. PWM7 now has four queued
16-bit samples separate from its active compare sample. A fifth write
cannot overwrite queued data and sets FWE. FIFOAV is derived/read-only and
status writes clear selected flags without injecting events. Software and
system reset clear queue state. LCDIF migration v5 adds FIFO contents,
head/count and repeat progress with bounds validation; older streams have
no recoverable queue and load with an empty one.

Elapsed counter periods consume queued samples with 1/2/4/8 repetition;
the final sample remains active on exhaustion. Consumption accounting is
bounded by queue/repeat state even over a long elapsed interval. Panel
readiness synchronizes that active sample instead of reading the latest
queued bus write. This is a nominal model: first-enable consumption and
empty-FIFO update edges remain physically unqualified. Swap controls are
explicitly unsupported. FE/ROV/CMP event generation, IRQ output and pin
waveform remain incomplete; the complete objective is not achieved.

Tests cover the original four contracts and all repeat counts through
consumption, gated pauses, reset, partial-period migration and ring refill.
The build script also recognizes later PWM patches when re-running an
incremental build instead of attempting to reapply their superseded
parent contexts. No calculator access was performed.

Final r59 SHA-256:
`c2d20b2290ec64c67cc2a0a3b2af2c791ed672b3be1cd8da50c65b35e852057f`.
Four original FIFO contracts, 24 lifecycle cases, seven PWM counter tests,
eleven live-clock/migration cases, peripheral suite, ten GPT state cases,
USBNC, live NAND timing, 219 unit tests, Linux boot and both NAND boot
suites pass. Both boots were rerun against the final incremental-build
binary. Manifest and final Linux console are under
`build/prime-g2-emulator-qualification/r59-20260907/`.

## PWM compare/rollover deadlines and interrupt wiring (r60)

The prior model produced neither CMP/ROV flags nor their interrupts. r60
advances counter events alongside FIFO consumption, latches masked status,
and schedules enabled events on the virtual clock. PWM has its own IRQ
connected to GIC SPI 116, independent of LCDIF. Clock changes, W1C, reset
and migration refresh the derived deadline and IRQ state.

Twelve event tests pass: masked compare/rollover, asynchronous delivery,
late enable, selective acknowledgement, two reset paths, three migration
states and actual GIC input routing. A failed non-secure GIC acknowledge
audit is retained separately; it cannot configure reset secure-only state.
The input routing test does not establish CPU acknowledge/EOI or exception
handler behavior. A separate secure ARM-state TCG guest now passes that
integration check: configure GIC, take ID 148 through the IRQ vector, clear
PWM, EOI, and return to the interrupted supervisor program. It is implemented
in `vm/test-prime-g2-pwm-cpu-irq.py` and `vm/guest/prime-g2-pwm-irq.S`, with no
NAND fixture or physical access. FE, output waveform and silicon event timing
remain open.

Binary SHA-256:
`cbb52aa3ce714886a371a0e6e5dae6ed865b8438a4865b93a74ee588bb166caf`.
Linux userspace and both NAND boot suites pass, as do 219 unit tests, PWM
FIFO/lifecycle/live-clock/counter suites and peripheral smoke tests.
No physical calculator access occurred. This is not full hardware parity
or proof of the cause of every observed physical black screen.

## PWM sample bus ordering and watermark audit (r61)

The r60 swap audit reproduced discarded writes in all three non-default
HCTR/BCTR combinations, both before and across migration. r61 transforms
aligned 32-bit writes into a 16-bit sample before queue insertion: HCTR
selects the other bus halfword, and BCTR reverses its bytes. The transformed
sample is stored; later control changes do not reinterpret queued data.
All eight cases pass with overflow still rejecting a fifth sample.

The independent watermark audit fails all eight threshold/masking cases.
Those failures remain visible: FE generation has not been implemented using
an invented W1C/reassertion rule. See `PWM-CONFORMANCE.md` for sources and
the distinction between documented thresholds and unqualified edge behavior.
Neither the swap fix nor other green suites resolves that missing feature.

r61 binary SHA-256:
`ae22c582387f508b9a272c625b227211bb3a1e35626065f0637235152af4d453`.
Eight swap cases, twelve event cases, secure CPU IRQ entry/EOI/return,
FIFO/lifecycle/live-clock/counter suites, peripheral smoke, GPT state,
USBNC, live NAND timing, 219 unit tests, Linux userspace and both NAND
boot suites pass. The manifest and boot logs are preserved under
`build/prime-g2-emulator-qualification/r61-20260907/`.
No physical device access or physical NAND writes occurred.

## Black-screen diagnostic priority: DCD DDR negative control (r61)

All 34 DCD MMDC writes were redirected to OCRAM scratch in both redundant
copies of a disposable saved-image overlay. Baseline and altered images
both reach visible Lefony UI. The existing unimplemented MMDC region and
unconditional RAM therefore allow an important DDR setup defect to escape
the boot suites. This is a demonstrated emulator blind spot, not a proven
physical root cause. See `BLACK-SCREEN-DIAGNOSIS.md` and
`build/prime-g2-emulator-qualification/r61-ddr-negative-control-20260907/`.
QEMU itself is unchanged. DDR state, reset retention and PMIC sequencing
now take diagnostic priority over unrelated peripheral refinements.

## DDR prerequisite: functional ROM copy order (r62)

DCD now executes from the functional ROM staging buffer before the firmware
copy into external DDR. The rejected-DCD negative control fails on r61
(firmware IVT already present in DDR) and passes on r62 (destination remains
zero). Both copies are invalidated to exclude redundant-copy fallback.
Normal decoded and physical-codeword NAND boot suites, recovery/reset suite,
peripheral smoke and 231 unit tests pass.

The separate MMDC-bypass experiment still boots: fixing ordering is not an
MMDC state model, and DDR/power-retention completion is explicitly false.
Five archived image comparisons also show identical MMDC initialization
sequences; only those artifacts are covered, not all historical attempts.
Evidence and binary hash are in
`build/prime-g2-emulator-qualification/r62-20260907/` and the r62 DDR negative
control directory. See `BLACK-SCREEN-DIAGNOSIS.md`. No physical access occurred.

## MMDC command lifecycle and NAND boundary (r63)

MMDC now has nominal CS0 DDR3 command state, including configuration
request/acknowledgement, mode-register commands, initial long ZQ and derived
completion. Partial state survives migration; cold model reset clears it.
Fourteen tests cover valid and varied mode data, each omitted mode/ZQ
command, missing request/chip-select, unsupported rank/type, reset and two
migration checkpoints. The NAND ROM requires completion before copying
firmware to external DDR. Baseline boots; the DCD-MMDC bypass now fails with
an explicit initialization error, not an unexplained absent UI.

Full CPU/DMA/USB/alias memory gating, clocks/PHY/refresh, detailed DDR3
ordering and physical reset/power retention are still incomplete. Register
shadows and zero cold defaults are not physical reset-value qualification.
See `MMDC-CONFORMANCE.md`. Both NAND boot suites, ROM recovery/reset,
peripheral smoke, secure CPU PWM IRQ and 231 unit tests pass. Evidence is
under `build/prime-g2-emulator-qualification/r63-20260907/` and
`r63-ddr-negative-control-20260907/`. No physical device was accessed.

## Common CPU/DMA DDR gate (r64)

The Prime bank and its alias now share a memory-map gate derived from MMDC
command state. An OCRAM ARM program verifies actual external data aborts
before initialization and during configuration, successful initialized
access, and preservation of backing bytes across a rejected write. ROM SDP
DMA is rejected before setup and succeeds after DCD delivered over USB.
Four alias/reset/migration cases and the fourteen MMDC cases pass. The
rejected-DCD test opens DDR before inspecting bytes so blocked zeros cannot
mask a firmware-copy ordering bug.

The original peripheral smoke and direct-loaded PWM/watchdog stubs required
explicit preinitialized-DDR fixtures. Their old expected results were not
relaxed. Strict NAND and DDR tests do not use that profile. Both NAND boot
suites and ROM recovery/reset pass; generic-EVK Linux and 231 unit tests
also pass, with their narrower scopes recorded in the manifest under
`build/prime-g2-emulator-qualification/r64-20260907/`.

This is not physical reset/power-retention completion. Unavailable DDR
currently returns a synthetic bus error; backing bytes persist across
controller reset. Clocks, training, refresh, supply loss and true retention
domains remain required. See `MMDC-CONFORMANCE.md`. No physical access.

## DDR supply-loss diagnostic input (r65)

A separate paused-VM rail fault now invalidates DDR backing storage and
initialization, independently of controller reset. Reset cannot resurrect an
absent supply; rail restoration cannot resurrect old contents. Six qtest
power/reset/migration cases and an actual ARM/TCG supply transition pass.
Both saved NAND boot suites, DDR gating/USB/command tests, recovery and 231
unit tests pass on the r65 binary. This is not a measured PF1550 power model
and is not wired to USB presence. See `MMDC-CONFORMANCE.md` and the r65
qualification manifest for scope and remaining limitations.

## DDR startup ordering (r66)

The unordered startup false-positive was reproduced on r65. r66 checks
the startup MRS order and initial DLL enable/reset fields before long ZQ
can qualify DDR. All 24 permutations, five additional DLL/ZQ negative
controls with recovery, runtime MRS and invalid-state migration pass.
Both saved NAND suites, DDR power/gate/CPU/USB/copy-order tests, ROM recovery,
fourteen MMDC cases and 231 unit tests pass on the recorded r66 binary.
See `build/prime-g2-emulator-qualification/r66-20260907/qualification.json`.
This remains incomplete: self-refresh, timing, training and actual board
reset/power sequencing are not qualified. No physical device was accessed.

## Definition of one-to-one for this project (completion criteria)

r68 moves DCD preparation before remaining candidate NAND reads. Five
early/late-ECC and cross-page header tests pass with independently observed
MMDC state. Both saved boot suites, DDR/reset/recovery regressions and 234
unit tests pass; see the r68 qualification manifest. Payload streaming and
the ROM-driven warm-reset retry remain unfinished, so this is not the full
vendor-described redundant-boot failure model.

Software self-refresh now has a separate r67 request/acknowledgement path,
not a writable completion bit. Four retention/reset/migration/power cases,
actual ARM CPU and USB DMA negative controls pass. Existing DDR command,
ordering, gate, power, copy-order and recovery tests, both saved NAND boot
suites, and 231 unit tests also pass. The recorded binary and limitations
are in `build/prime-g2-emulator-qualification/r67-20260907/qualification.json`.
This does not qualify clock timing, hardware warm-reset handshakes or actual
board power retention. No physical device was accessed.

The emulator is complete only when it can boot the same open boot chain,
exercise the same MMIO/I2C/SPI/GPIO-visible interfaces, reproduce keypad and
touch event timing, render the same panel output, expose Linux USB gadget and
recovery behavior, and pass trace comparisons for normal and fault cases. A
screenshot match alone is insufficient.
