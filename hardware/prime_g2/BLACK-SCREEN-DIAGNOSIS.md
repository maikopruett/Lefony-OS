# Physical black-screen diagnosis

## Evidence, not a single established cause

The archived NUL-padded U-Boot environment has a reproduced failure: the
environment terminates before `bootcmd`, leaving an invisible U-Boot prompt.
The repaired image boots the emulator. This does not explain every physical
blank screen, particularly reports involving RAM boot, reset or no battery.

## DDR negative control, r61

`vm/audit-prime-g2-ddr-boot.py --output NEW_DIRECTORY` changes only a
disposable overlay of the saved decoded NAND fixture. It redirects all 34
MMDC writes in the captured DCD to one OCRAM scratch word in both redundant
U-Boot copies. Other DCD writes, the repaired environment and the Lefony
capsule remain unchanged. The original saved image is never modified.
**These deliberately damaged test overlays must never be flashed.**

Both baseline and altered runs reach the U-Boot banner, kernel handoff,
Lefony runtime marker and a visible framebuffer. This exposes an emulator
qualification failure: boot success is insensitive to the DCD's DDR setup.
The SoC currently registers MMDC as an unimplemented device and provides
RAM independently. Later guest activity is not claimed to be removed by
this experiment; specifically, this is a DCD-MMDC negative control.

Evidence: `build/prime-g2-emulator-qualification/r61-ddr-negative-control-20260907/`.
The report includes exact binary/image hashes and each redirected write;
console logs and separate visible-frame checks are retained for both cases.
No physical calculator was accessed. This is not a measurement of DDR failure
on the real board and not proof of its black-screen cause.

## Next work, in diagnostic order

### r62 prerequisite: DCD before DDR copy

The functional ROM previously copied firmware into external DDR before
executing DCD. r62 executes DCD from its host staging buffer first. A new
black-box test invalidates DCD in both boot copies and checks the destination
IVT word after ROM fallback: r61 left `0x402000d1` in DDR; r62 leaves zero.
Run `python3 vm/test-prime-g2-ddr-load-order.py`. This verifies ordering on
the rejected-DCD path, not DDR training or physical reset behavior.

### Archived initialization comparison

`scripts/inspect_prime_g2_ddr.py` compares ordered MMDC address/value writes
and decodes MDSCR commands without accessing a calculator. Five archived
images from the handoff, provisioning and a606 restore paths have the same
MMDC sequence hash:
`8f446cac2a70da637f1cc9ffb3f1fbdef5d56264b8382da2e423406d61127649`.
Exact paths and whole-image hashes are recorded in
`build/prime-g2-emulator-qualification/r62-20260907/archive-ddr-comparison.json`.
This excludes a changed DCD MMDC sequence among those five artifacts only.
It neither assigns a physical success/failure label to each artifact nor
excludes pinmux, later firmware, reset retention, or supply differences.

### Remaining model requirements

The new physical ROM capture `reference/rom-reset-clock-20260908T053848Z.json`
reads CCDR `0x00020000` twice, confirming that the r69 zero baseline differs
from this calculator's recovery state. GPR9/GPR10 are zero: a retained
software override is not demonstrated in this snapshot. No reset, flash,
firmware download or register write was performed. This narrows model work;
it still does not identify the physical black-screen cause.

The r69 reset audit also confirms that modeled CCDR bit 17 cannot be
written and its reset value is zero. This conflicts with the register
operation used in NXP's i.MX6ULL redundant-boot workaround. Resolve the
exact CCM/reset definitions before implementing that handshake; do not
treat the inherited i.MX6UL clock model as qualified Prime hardware.
See `build/prime-g2-emulator-qualification/r69-20260907/ccdr-audit.json`.

r69 makes a failed candidate's successfully received prefix visible in DDR
before a late ECC error. Six tests compare full decoded bytes through both
DDR mappings, exclude the failed page, and check a non-page-aligned declared
end. The normal NAND boot suites still pass. This establishes partial-memory
state for the future ROM warm-retry model; it does not yet implement that
retry or qualify physical DMA timing and read-ahead behavior.

r68 implements the missing DCD-versus-late-ECC ordering: a candidate's DCD
executes as soon as its header bytes are decoded, before remaining NAND
pages are read. Five tests distinguish early errors, late errors and
page-spanning headers/DCD using actual post-failure MMDC state. Redundant
ROM warm reset and its clock handshake are still absent, so the complete
NXP failure cannot yet be claimed reproduced. Payload bytes are still
staged rather than incrementally written into DDR.

NXP documents a related i.MX6ULL redundant-NAND warm-reset hang:
[vendor report and DCD workaround](https://community.nxp.com/t5/i-MX-Security/Serial-download-mode-is-not-triggered-and-hang-when-NAND-ECC/ta-p/1109118).
The enhanced archive inspection finds no boot-size overrun in the five
compared artifacts, and no DCD write to CCM_CCDR/SRC_SCR in any of them.
This does not prove the reported trigger occurred on Prime. Importantly,
the emulator stages and decodes all firmware before DCD and directly tries
the redundant copy without ROM warm reset. Its current fallback tests do
not cover NXP's post-DCD failure sequence. See `MMDC-CONFORMANCE.md` for
the required late-error/reset/clock test pair before drawing conclusions.

The r67 reset-domain audit confirms CPU-only reset preserves initialized
DDR while actually clearing CPU state. However, watchdog tests with SRC_SCR
warm-reset enable clear/set produce identical DDR outcomes: controller
state is lost but backing bytes remain. The emulator's unconditional
system-reset watchdog path cannot qualify the hardware warm handshake.
Saved Linux source clears warm-reset enable for reliability; Prime U-Boot
configures the MMDC handshake mask. Capture SRC_SCR, CCM_CCDR and MMDC state
at each boot handoff before attributing physical failures to this difference.
The available physical ROM snapshot omits SRC_SCR, so it is insufficient.
Evidence: `build/prime-g2-emulator-qualification/r67-20260907/reset-domains.json`.

r67 distinguishes explicit software self-refresh from DDR supply loss.
The prior writable acknowledgement false-positive is reproduced by the
new test. A modeled self-refresh request now suspends common DDR accesses
without erasing contents; CPU and USB DMA negative controls confirm this,
and wake restores access to the same data. Supply loss still destroys it.
This is synchronous, source-backed software handshake behavior; the actual
SRC/CCM warm-reset handshake and physical entry/exit timing remain open.

r66 closes another demonstrated false-positive: r65 accepted MR2, MR3,
MR0, MR1 as a cold initialization. Command progress now checks startup
ordering and the initial DLL enable/reset fields; the dedicated test
checks all 24 permutations plus invalid DLL/ZQ setup and recovery. This
does not establish that any physical attempt used an invalid sequence.
The archived-image DDR comparison remains distinct evidence.

r65 adds an explicit, paused-emulator DDR supply-loss fault. Unlike controller
reset, it destroys backing contents and mode/ZQ progress; restoring the rail
cannot restore a bootable RAM image. Six reset/migration/power cases and the
actual ARM/TCG loss test pass, and both saved NAND boot suites still pass.
This makes a power-loss hypothesis testable without silently retaining RAM.
It does **not** establish that physical USB unplugging or reset caused that
fault: board supply sequencing and retention remain unmeasured. No physical
device was accessed. See `MMDC-CONFORMANCE.md` for the exact boundary.

r64 extends that boundary to the common system memory map, including the
DDR alias. An OCRAM-resident ARM test takes actual CPU aborts before setup
and on a write while access is closed; the same location works after setup
and retains its prior value across the rejected write. USB SDP DMA is also
rejected before setup and succeeds after USB-delivered DCD. Open/closed gate
migration and controller-reset checks pass. The unavailable-memory response
is currently a synthetic bus error, not a measured physical stall/timeout.
Backing RAM is not yet coupled to physical supply loss; power retention is
still unqualified.

r63 adds nominal MMDC command state and a NAND firmware-copy check. The
normal image still reaches visible UI; the DCD-MMDC-bypassed image is now
rejected explicitly before U-Boot is copied. Fourteen command/reset/migration
cases and the preserved NAND boot/recovery suites pass. This is not a full
DDR model: CPU/DMA/USB access gating, timing, calibration and physical
power-retention behavior remain open. See `MMDC-CONFORMANCE.md` for the exact
boundary and remaining requirements. The QOM `initialized` property describes
the modeled command sequence, not proven electrical readiness.

The local Prime U-Boot `arch/arm/mach-imx/mx6/ddr.c` and `include/fsl_mmdc.h`
provide the initialization sequence and command fields: configuration
request, timing/type/geometry, chip-select enable, mode-register commands,
ZQ, refresh and request release. These are evidence for a state model, not
permission to accept only the exact archived register values. The physical
reset-domain mapping, self-refresh retention and power-loss behavior still
require separate evidence. r63's command-based NAND boundary does not claim
those requirements are implemented.

1. Replace the MMDC stub with documented initialization/state behavior and
   connect memory availability to it. A shadow register bank or a hard-coded
   allowlist of the known-good DCD is not physical qualification. Preserve
   distinctions between cold power-on, warm reset and RAM-download entry.
2. Compare exact DCD sequences from confirmed working and failing boot images;
   classify differences separately from boot-environment differences.
3. Establish physical reset/PMIC retention and batteryless USB-power behavior
   with controlled observations. Do not infer those domains from a QMP reset.
4. Correlate each physical attempt with image hashes and the last independently
   observed stage: ROM, U-Boot, kernel entry, native runtime, display scanout.
   A dark panel alone does not identify where execution stopped.

Keep the confirmed environment defect, the demonstrated emulator DDR blind
spot, and the untested physical power/retention hypotheses separate.
