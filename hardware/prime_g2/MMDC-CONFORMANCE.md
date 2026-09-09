# MMDC initialization and retention conformance

This work is incomplete. A command-state model is not a DDR PHY, a memory
timing model, or verification of the physical calculator's reset domains.

## Implemented command state in r63

The MMDC region replaces the prior read-as-zero/write-ignore stub. The
initial model interprets CS0 enable, the DDR3/LPDDR2 selector, configuration
request/acknowledgement, four DDR3 mode-register writes, and initial long ZQ.
The command fields come from the Prime U-Boot `include/fsl_mmdc.h` and
`arch/arm/mach-imx/mx6/ddr.c`. Values are not compared to a known-image hash.

Mode registers and command progress are stored separately from register
readback. `CON_ACK` is derived from the configuration request rather than
being software-writable. Request acknowledgement and command completion
are currently synchronous; their physical clock delays are not modeled.
The QOM `initialized` property reports only this nominal command sequence.
The functional NAND ROM checks it before the external firmware copy.

Other MMDC timing/PHY registers are explicitly shadowed and log that fact.
Their readback does not establish functioning training. Unsupported ranks
and LPDDR2 sequences do not qualify the CS0 DDR3 command state. Cold model
reset clears progress; migration carries mode registers and partial progress.

## Remaining required work

- Qualify the DDR gate's actual bus response and in-flight transactions
  against hardware; r64 now routes normal CPU/DMA/USB/alias accesses through
  the gate, but returns a synthetic transaction error instead of modeling
  a clock-dependent wait/timeout.
- Implement clock-dependent request/command completion, DDR reset/CKE delays,
  geometry/addressing and timing configuration, refresh and calibration.
- Validate DDR3 command ordering, DLL state and electrical timing instead of
  treating presence of the mode-register commands as full initialization.
- Separate controller reset, CPU-only reset, self-refresh, power-down and
  actual power loss. Do not equate these with one QMP system-reset event.
- Couple PF1550/supply state to DDR validity and independently model retention
  requirements. Do not infer batteryless stability or retention from USB
  presence. Physical supply sequencing still needs controlled measurements.
- Save and restore all pending deadlines and retained state; test partial
  initialization, self-refresh and wake/reset transitions through migration.
- Compare against physical observations; current zero reset shadows are not
  a verified table of silicon register reset values.

NXP's [MMDC SDK reference](https://mcuxpresso.nxp.com/api_doc/dev/721/group__mmdc.html)
separates initialization, refresh, calibration and power configuration. Its
shared-IP interface is supporting evidence, not an exact Prime-board oracle.

## r64 unified memory gate

On `hp-prime-g2`, a high-priority unavailable-memory responder covers
`0x80000000..0x9fffffff`, including the fitted DDR and its mirror. It is
enabled until the nominal command state completes, and reenabled during
configuration or controller reset. The same system address space is used
by guest CPU and DMA; opening the gate reveals the original RAM region.
Closed writes return an error and do not change backing bytes. Closed reads
return a transaction error (qtest displays zero; CPU sees an external abort).
Gate state is derived again after migration rather than being independently
serialized. The generic EVK does not acquire Prime-specific gating.

Four gate tests cover aliases, configuration roundtrip, controller reset,
open migration and closed migration. An ARM program executing entirely in
OCRAM verifies actual CPU read/write aborts, initialization and subsequent
access. A ROM SDP test verifies rejection before initialization, DCD delivered
over USB, and successful subsequent DMA download/alias readback. The earlier
rejected-DCD test now explicitly initializes DDR before inspecting backing
bytes, preventing blocked-read zeros from hiding a premature copy.

The opt-in `-global prime-g2-mmdc.preinitialized=on` profile is an explicit
synthetic debugger/direct-load fixture, not the cold boot default. It supplies
nominal command state on model reset. The PWM CPU test, RAM watchdog stub,
and DMA peripheral smoke test use it because they assume prior setup. The
general SDP test performs explicit command initialization; the dedicated USB
DDR test covers its absence. These fixtures do not qualify cold DDR boot.

Controller reset currently blocks access but leaves backing RAM bytes intact.
This is explicitly not a physical power-loss or warm-retention model. Do not
treat a subsequent successful reinitialization as proof of physical retention.

## r65 explicit DDR supply-loss fault

The paused-VM QOM property `/machine/soc/mmdc:ddr-supply-present` now
provides a separate supply fault input. A falling edge invalidates the
entire backing bank, clears DDR mode/ZQ progress, and closes the common
memory gate. Controller register shadows and OCRAM are not erased by this
DDR-only fault. Restoring supply requires fresh initialization. System reset
does not turn an externally absent supply back on, including in the opt-in
preinitialized fixture. Migration preserves the supply level and lost state.
Repeated writes of the same supply level do not erase live memory.

Six qtest cases cover these transitions, migration with supply off/restored,
and rejection of live-VM injection. The actual ARM/TCG test additionally
executes a paused supply-loss transition and verifies invalidated DDR and
preserved OCRAM. CPU/DMA gates, all fourteen command cases, rejected-DCD
copy ordering, both saved NAND suites, ROM recovery and 231 unit tests pass.

This is diagnostic fault injection, not a physical PMIC model. Zero-filled
invalidated memory is deterministic test behavior, not an electrical decay
or power-up pattern. USB removal is deliberately not connected to this input.
Supply thresholds, self-refresh, timing, reset-domain mapping, and the actual
board supply path remain unqualified. Qualification is recorded under
`build/prime-g2-emulator-qualification/r65-20260907/`.

## Further verification strategy

### Startup ordering refinement (r66)

The prior unordered bit-set admitted the permutation MR2, MR3, MR0, MR1
followed by ZQCL. The new `test-prime-g2-ddr-order.py` reproduces that failure
on r65. Startup progress now follows MR2, MR3, MR1 with DLL enabled, MR0
with DLL reset, then long ZQ on bank zero. Invalid startup MRS resets the
partial progress; a fresh complete sequence can recover. Normal MRS writes
after initialization do not require repeating the cold-start sequence.

The local Prime U-Boot `arch/arm/mach-imx/mx6/ddr.c` lines 1451 onward
explicitly uses these commands and DLL fields. Microchip's
[DDR3 startup description](https://onlinedocs.microchip.com/oxy/GUID-FF8061A7-7A15-470F-A6F5-E733C24D85F0-en-US-11/GUID-1353F87C-A407-48AA-8C45-C71655203660.html)
independently documents the MRS order and subsequent long calibration.
That supporting DDR3 description is not used as a source for Prime-specific
clock values or reset delays. Command ordering alone does not implement
tMRD, tMOD, tDLLK, refresh, training or mode-dependent data behavior.

All 24 MRS permutations were exercised: only the documented startup order
qualifies. Five additional negative controls cover disabled DLL, missing
DLL reset, short ZQ, wrong ZQ bank and premature ZQ; each can recover after
fresh initialization. Runtime MRS updates, modeled DLL-reset/ZQ recovery,
and migration of an invalid startup also pass. Migration testing is within
the same patchset, not a qualification of older emulator snapshots.

The next retention gap has a concrete local software reference:
`build/kernel-inspect/arch/arm/mach-imx/suspend-imx6.S` sets MAPSR bit 21
and polls bit 25 before changing low-power state; it clears bit 21 and
waits for bit 25 to clear on exit. These are still shadow bits in r66;
self-refresh entry/exit and retained memory need explicit modeling and
tests, with the i.MX6ULL register specification checked before implementation.

### r67 software self-refresh handshake

The local Freescale/NXP Linux `suspend-imx6.S` explicitly requests software
self-refresh through MAPSR bit 21 and polls bit 25 on entry and exit.
r66 permitted software to forge bit 25 directly; the new self-refresh test
reproduces this. r67 derives that acknowledgement from the request and
nominal initialized state. Requesting self-refresh closes the common DDR
access gate without erasing backing storage or the initialization sequence.
MRS/ZQ commands are not accepted while this request remains set. Clearing
the request reopens initialized DDR without a new mode-register sequence.

This is the software/DVFS path only. Other MAPSR fields, automatic low power,
CCM/SRC hardware handshakes, physical clock/CKE timing and warm retention
remain unqualified. A hardware warm reset is not automatically modeled by
setting the software request. The QOM `initialized` property continues to
mean completed nominal setup; it can remain true during self-refresh even
though memory access is closed. NAND loading checks availability as well.

The attempted full IMX6ULLRM retrieval was unavailable (official URL returned
404; the discovered mirror download returned 403). The software source is
the evidence for this bounded transition model, not verification of the
complete register specification. Entry/exit acknowledgement is synchronous;
unavailable accesses use the existing synthetic transaction error rather
than a measured hardware stall. No electrical retention duration is claimed.

Four qtest cases verify entry/exit, migration, supply loss and controller
reset. The ARM/OCRAM guest takes a real CPU data abort on an attempted write
during requested self-refresh and observes its original data after wake.
The ROM SDP test likewise rejects USB DMA during self-refresh and confirms
unchanged backing bytes after exit. Reset clears model initialization;
supply loss additionally destroys backing data. These test the implemented
distinction, not the physical calculator's warm-reset domains.

### Reset-domain audit on r67

The extended ARM/OCRAM CPU test now exercises SRC_SCR's CPU0 reset bit.
It observes cleared CPU registers/PC and completion of the reset request,
while initialized DDR and OCRAM markers survive. This is an actual TCG CPU
reset, not merely a write/readback assertion on a reset register.

`vm/audit-prime-g2-reset-domains.py` separately compares watchdog resets with
SRC_SCR warm-reset enable clear/set. Both currently clear the MMDC controller
and preserve backing bytes behind a closed gate; explicit reinitialization
is needed to inspect those bytes. Source inspection confirms the watchdog
requests system-wide reset without a separate MMDC/CCM warm handshake.
The audit reports this identical outcome as an unqualified distinction,
not a passing physical-retention test. SRC bit zero is identified by the
local Linux `arch/arm/mach-imx/src.c` definition.

That Linux initializer deliberately clears warm-reset enable for restart
reliability. Conversely, the saved Prime U-Boot `arch_cpu_init` clears the
MMDC channel handshake masks to support warm reset. This provides a concrete
reason to record the inherited SRC/CCM state for RAM, Linux-recovery and
native-NAND entry separately. It is not proof that this difference caused
the observed calculator failure. The saved physical ROM snapshot has no
SRC_SCR or MMDC retention-state capture, so it cannot settle that question.

### NXP redundant-image warm-reset failure: new qualification requirement

NXP documents an i.MX6ULL NAND boot failure where an overstated boot-data
size causes an ECC error, ROM attempts the secondary image through warm
reset, and DDR initialization hangs. Its EVK workaround writes zero to
CCM_CCDR in DCD and restores `0x00020000` later in U-Boot. Source:
[NXP knowledge-base report](https://community.nxp.com/t5/i-MX-Security/Serial-download-mode-is-not-triggered-and-hang-when-NAND-ECC/ta-p/1109118).
This specific report is not a rule that every second DDR initialization
must fail, and not proof that Prime encountered its trigger.

The enhanced `scripts/inspect_prime_g2_ddr.py` checks boot-data artifact
extent and records DCD writes to SRC_SCR/CCM_CCDR relative to the first MMDC
write. All five previously compared archives have their declared boot extent
within the artifact; none writes those reset/handshake registers in DCD.
The size/padding trigger is therefore not demonstrated in those artifacts.
File coverage does not establish actual programmed NAND coverage or ECC.
The missing early write is common to those archives, including the a606
artifacts, so it does not by itself explain a regression between them.

At r67, ROM modeling could not qualify this failure: `prime_rom_load_firmware`
decodes the entire candidate into a host buffer before executing DCD, and
`prime_g2_nand_rom_load` directly calls the secondary loader after rejection.
It does not model a mid-stream, post-DCD ECC error followed by a ROM-driven
warm reset. Existing successful redundant-copy tests must not be interpreted
as testing that sequence. Next implementation needs staged ROM reads/DCD,
the reset handshake and lost-clock state, plus a late-ECC negative control
and NXP's pre-DCD workaround as a paired positive control. Preserve existing
pre-DCD error recovery as a distinct case. Do not hard-code image hashes.

### r68 incremental boot-header/DCD preparation

The loader now checks available bytes after each decoded NAND page. It
executes DCD once the IVT, boot-data structure and full DCD are present,
before reading the remaining candidate pages. Pointer/length checks precede
access to unreceived bytes, and DCD must fit the declared boot size.
Consequently a later ECC error can leave initialized MMDC state; an error
before DCD completion cannot. The new test reproduces the missing late-error
state on r67 and passes on r68.

Five disposable physical-codeword tests cover early/late ECC failures,
page-spanning DCD, an error before that DCD completes, and page-spanning
boot data. They check ordering logs and independently read the actual MMDC
initialized property after failure. Both firmware copies are faulted so
successful fallback cannot hide the observed state.

This is not completion of the NXP failure model. The loader still stages
payload bytes in a host buffer and copies to DDR after the complete read;
it does not yet stream partial payload writes into DDR. Redundant selection
still lacks the ROM-driven warm-reset/clock handshake. Those remain required,
along with a paired test for the early CCDR workaround. No physical access.

### r69 received-prefix DDR transfer

After DCD preparation, the loader transfers the buffered prefix into DDR,
then transfers newly received bytes page by page. A later ECC failure leaves
the successful prefix intact; the failing page is never copied. Transfers
are capped by declared boot size, including a non-page-aligned last span.
The allocation remains a host staging buffer, but memory visibility no longer
waits for completion of the entire candidate. This is functional ordering,
not a measured ROM DMA burst-size, latency or bus-cycle model.

The staging tests now read all ten received pages through DDR and its alias,
plus the failing page. They explicitly initialize the controller before
inspecting early-error backing memory so blocked-read zeros cannot disguise
an unintended write. r68 fails the new late-error prefix check. A sixth
case checks a declared end inside a page, preventing copying its suffix.
The FCB page-count read policy is unchanged and remains separately
unqualified against ROM's exact read-ahead behavior. ROM-driven warm retry,
the CCDR handshake and retained-clock state are still required.

All six staging/transfer cases pass. Expected data is independently decoded
with the Python BCH layout and marker swap, then compared byte-for-byte
against DDR and its mirror. Both saved NAND suites, the DDR/reset/recovery
regressions and 234 unit tests pass. The r69 qualification manifest records
the binary and exact scope; no physical device was accessed.

### CCDR access discrepancy on r69

A new physical recovery capture on 2026-09-08 at 05:38:48 UTC independently
reads CCDR as `0x00020000` twice. SRC_SCR reads `0xa0480539`, SRSR `1`, and
GPR9/GPR10 zero. See `reference/rom-reset-clock-20260908T053848Z.json`.
Only fixed SDP register reads were issued; no reset, download or register
write. This confirms an observed device/emulator CCDR discrepancy, not
all silicon reset defaults or retention semantics. Do not copy SRC reserved
bits from this snapshot into an assumed writable mask. The user confirms
the battery is absent and the calculator was already in recovery; they
performed no new reset or reconnect. The preceding transition is unknown.

The reset audit now exercises CCDR separately. Reset/readback is zero;
writing bit 16 succeeds, while writing bit 17 reads back zero. Source
`hw/misc/imx6ul_ccm.c` confirms reset value zero and reserved-bit mask
`0xfffeffff`. Thus the inherited model cannot represent NXP's documented
i.MX6ULL workaround which changes bit 17 and later restores `0x00020000`.
This is an emulator/specification discrepancy to resolve, not proof of a
physical fault or permission to copy another SoC's complete register map.

The official `https://www.nxp.com/webapp/Download?colCode=IMX6ULLRM` endpoint
redirects to NXP sign-in. The obsolete direct PDF returns 404 and the
discovered mirror returns 403. The user has been asked for IMX6ULLRM Rev. 1
or the relevant CCM/MMDC/SRC/WDOG chapters. Before implementing the warm
handshake, verify CCDR reset/access fields, reset source classification,
handshake masks, bypass timeout, and the retained MMDC/clock domains against
that specification. Do not replace them with a test-only Boolean that simply
selects a successful or failed boot.

Keep the DCD-bypass experiment, missing-command controls and malformed-DCD
copy-order test. Add negative tests for invalid timing, clock-gated commands,
memory accesses before initialization, access during self-refresh, and power
loss followed by a warm reset. Run the preserved working boot chain and RAM
download paths after each change. A rejected bad image must not be achieved
by an image-specific allowlist or by breaking all normal boots.
