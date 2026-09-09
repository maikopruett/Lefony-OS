# Prime G2 QEMU peripherals

Patchset r69 streams received firmware into DDR after DCD preparation.
Late ECC failure preserves the received prefix without copying the failed
page; transfers stop at the declared byte boundary. Six staging tests now
compare the prefix through both DDR mappings. ROM warm-retry/clock behavior
is still unfinished; this is not the complete redundant-boot hang model.

Patchset r68 prepares IVT/boot data/DCD as NAND pages arrive, allowing a
later ECC failure to occur after initialization. Run
`python3 vm/test-prime-g2-rom-dcd-staging.py` for five early/late and
page-boundary cases. ROM-driven warm reset and streamed DDR writes remain
unfinished; this does not yet reproduce the complete NXP redundant-boot hang.

Patchset r67 models the explicit software self-refresh request/DVACK path.
Run `python3 vm/test-prime-g2-ddr-self-refresh.py` plus the DDR CPU/USB tests.
Memory access closes while requested; wake retains bytes, supply loss does
not. This synchronous software path does not qualify physical warm reset,
CCM handshakes, automatic low-power behavior, or entry/exit clock delays.

Patchset r66 requires the DDR3 startup MRS order, initial DLL enable/reset
and long ZQ. `python3 vm/test-prime-g2-ddr-order.py` covers all 24 MRS
permutations, invalid DLL/ZQ setup, recovery and invalid-state migration.
This is command qualification, not clock timing or PHY training.

Patchset r65 adds paused-VM DDR supply-loss fault injection through QOM
`/machine/soc/mmdc`, property `ddr-supply-present`. Run
`python3 vm/test-prime-g2-ddr-power.py` and the DDR CPU test. Rail loss clears
backing memory and initialization; reset and migration cannot resurrect it.
This diagnostic input is not connected to USB or a qualified PMIC sequence.

Patchset r64 gates the Prime DDR bank and mirror through the common CPU/DMA
address space until nominal MMDC initialization completes. Run
`test-prime-g2-ddr-gate.py`, `test-prime-g2-ddr-cpu.py` and
`test-prime-g2-ddr-usb.py` for migration/alias, actual CPU-abort and ROM SDP
tests. Direct-loaded fixtures needing already available RAM must explicitly
use `-global prime-g2-mmdc.preinitialized=on` or execute MMDC setup. The gate
returns transaction errors; physical bus latency and power retention remain
unqualified. See `hardware/prime_g2/MMDC-CONFORMANCE.md`.

Patchset r63 replaces the MMDC stub with initial DDR3 CS0 command state and
blocks the NAND firmware copy when that sequence is incomplete. Run
`python3 vm/test-prime-g2-mmdc.py` for 14 command/reset/migration cases.
The normal image boots and the DCD-MMDC bypass is now rejected. Full memory
access gating and physical power/retention semantics remain incomplete;
see `hardware/prime_g2/MMDC-CONFORMANCE.md` before interpreting readiness.

Patchset r62 fixes functional ROM ordering: execute DCD before copying the
boot stream into external DDR. `test-prime-g2-ddr-load-order.py` verifies
that rejected DCDs in both boot copies leave the DDR destination untouched.
This is a prerequisite for DDR gating, not an MMDC initialization model.
See `hardware/prime_g2/BLACK-SCREEN-DIAGNOSIS.md` for the remaining blind spot.

Patchset r61 fixes PWM sample writes with HCTR/BCTR enabled. Aligned 32-bit
writes now select/swap the FIFO input rather than being discarded. Run
`python3 vm/test-prime-g2-pwm-swap.py` for all four combinations, overflow,
post-insertion control changes and migration. `test-prime-g2-pwm-watermark.py`
is a separate, currently failing conformance audit; use `--audit NEW_JSON`
to retain evidence without asserting success. Watermark flag reassertion
semantics must be established before claiming that feature is complete.

Patchset r60 adds timed PWM compare/rollover flags and an independent IRQ
to GIC SPI 116. Run `python3 vm/test-prime-g2-pwm-irq.py` for twelve masked,
asynchronous, reset, migration and wiring cases. Run
`python3 vm/test-prime-g2-pwm-cpu-irq.py` for a secure ARM guest taking ID 148,
performing EOI and returning from the IRQ. The latter uses a local Clang
ARM assembler and TCG; neither test accesses the physical calculator.
Watermark and waveform behavior and physical event timing remain open.

Patchset r59 adds PWM7's four-word FIFO and separate active sample,
overflow rejection/FWE, read-only occupancy, W1C flags, nominal
period-boundary consumption and 1/2/4/8 repeats. Reset and migration retain
the correct queue lifecycle. `test-prime-g2-pwm-fifo.py` and
`test-prime-g2-pwm-fifo-state.py` exercise these contracts. First-enable
timing and empty-FIFO glitches remain provisional; watermark IRQs and
physical output waveform are still incomplete.

Patchset r58 replaces PWM7's fixed IPG/peripheral rates with live CCM
outputs, including its CCGR6 RUN gate. Counter accounting retains fractional
cycles across root changes and active/gated migration. Run
`test-prime-g2-pwm-clocks.py` for rates, divider transitions, gate modes,
unrelated-gate isolation and migration. The optical waveform, FIFO and IRQ
model are still incomplete; a stopped counter alone does not prove a dark
physical panel.

Patchset r57 corrects PWM7's clock-off and 32 kHz selector behavior,
read-only counter writes and 16-bit maximum period. Its IPG/IPG-high inputs
still use the older 66 MHz approximation; live CCM gates/rates, FIFO,
interrupts and output waveform are not qualified by this change.
`test-prime-g2-pwm-counter.py` covers the corrected counter contracts.

Patchset r56 recomputes GPT IRQ outputs after reset and migration load.
The registers and remaining timer deadline were already serialized, but
the pending interrupt wire was not restored, and reset did not lower it.
`test-prime-g2-gpt-state.py` exercises both timers' active/pending
checkpoints, post-restore acknowledgement, soft reset and system reset.
This qualifies logical state continuity, not physical reset timing.

Patchset r55 separates GPT compare/rollover status from interrupt enables.
`test-prime-g2-gpt-oscillator.py` covers both 3 MHz timer sources, masked
compare/restart behavior and IRQ acknowledgement. The Linux VM can retain
the physical GPT clock properties using `PRIME_G2_PHYSICAL_GPT=1` at build
time and the patched `PRIME_G2_QEMU` at run time; the stock-QEMU fallback
is unchanged. This does not qualify unmodeled timer capture/power behavior.

## USBOTG1 device mode

Upstream QEMU's i.MX6UL ChipIdea block only implements its EHCI host
personality. The Prime model replaces USBOTG1 with a peripheral-mode model of
the registers, EP0 queue heads, transfer descriptors, DMA, reset/address/
configuration lifecycle, connect/disconnect, and suspend/resume used by the
native driver. `run-native-vm.sh` exposes the modeled cable at
`usb-host.sock`; `prime_usb_host.py` sends USB setup/IN/OUT transactions over
that boundary. This is a digital transaction model, not an electrical UTMI
PHY or a claim of real-host interoperability.

`test-native-usb.sh` cold-enumerates the unchanged native driver, reads its
descriptors, configures it, injects malformed transfers, stages and verifies a
recovery capsule, disconnects, and enumerates again at a new address.

QEMU patchset r32 also models open ROM SDP downloads, RAM/SRC readback,
the Prime's 32-bit DCD setup, and IVT handoff. ROM descriptors and strings
match a read-only physical capture in
`hardware/prime_g2/reference/rom-usb-descriptors.json`. Run
`python3 vm/test-prime-g2-rom-recovery.py` for protocol/reset tests and
`python3 vm/test-prime-g2-nand-rom-boot.py` for the captured U-Boot transfer
through SDP to a visible NAND-booted Lefony UI, plus repeated recovery exits.
Full HAB, arbitrary MMIO SDP access, electrical timing, and host USB-backend
interoperability are not implemented. Existing r31 migration snapshots are
not compatible with the new reset-controller and SDP migration state.

Patchset r54 replaces the USBMISC placeholder with USBNC registers mapped
through the device-mode USB model. Port-zero BVALID cable transitions latch
a wake request only with source and wake interrupt enabled; disabling WIE
acknowledges it. The wake request and normal USBSTS/USBINTR share the IRQ
without acknowledging each other. USB controller reset preserves USBNC;
system reset clears its provisional defaults. USB migration v4 preserves
configuration/pending wake and restores the output wire. Run
`test-prime-g2-usbmisc.py` for initialization, masking, edges, acknowledgement,
port isolation, migration and reset separation. Cold defaults, other VBUS
sources, ID/DPDM/overcurrent and physical analog/low-power timing remain open.

Patchset r53 implements GPMI/BCH soft-reset acknowledgement and local
clock-gate dependencies. Reset clears that block's configuration/IRQ and
holds its gate, without erasing NAND or resetting neighboring controllers.
Local GPMI gating pauses ready-timeout accounting; reset cancels the pending
wait continuation. `test-prime-g2-nand-block-reset.py` checks both blocks,
aliases, isolation and reset-held migration. The clock-gate and live-timing
suites additionally cover local gates, readiness and canceled waits.
Reset clock prerequisites and physical in-flight abort behavior remain open.

Patchset r52 implements the APBH block soft-reset handshake: asserting
SFTRST clears channel state and completion IRQ and asserts CLKGATE. Clearing
SFTRST alone leaves the clock gated. Channel writes are ignored while reset
is held; the block gate also prevents dispatch. GPMI/BCH configuration and
NAND contents are not reset by APBH. `test-prime-g2-apbh-reset.py` covers
direct/SET/TOG assertion, queued work, IRQ clearing, isolation and migration.
In-flight peripheral abort timing and GPMI/BCH soft reset remain unfinished.

Patchset r51 implements single-byte, 8-bit NAND READ_AND_COMPARE status
commands and their APBH SENSE result. GPMI STAT DEV0_ERROR reflects the
compare/timeout sense latch. Compare configuration writes do not acknowledge
that latch, and a compare mismatch does not generate a timeout IRQ. Run
`test-prime-g2-nand-compare.py` for success/failure masks, resume, migration,
reset and explicit unsupported-form checks. Wider/multi-byte/zero-count
compare commands remain unqualified and do not fabricate DMA completion.

Patchset r50 honors channel-zero APBH CTRL0 clock gating and CHANNEL_CTRL
freeze independently of the GPMI/BCH roots. Dispatch resumes only after both
controls release; a GPMI ready/timeout event while frozen cannot advance DMA.
Idle zero-semaphore writes cannot launch descriptors. Run
`test-prime-g2-apbh-pause.py` for gate/freeze, aliases, combined holds,
ready/timeout, reset and migration tests. Mid-transfer bus timing and channel
software-reset semantics remain unqualified.

Patchset r49 connects the BCH clock input and holds APBH transfer dispatch
when GPMI or a required BCH clock is gated. No payload/auxiliary writes or
completion IRQs occur while held. Ungating resumes the descriptor; reset
cancels it and migration v5 preserves the blocked-clock mask. Run
`test-prime-g2-dma-clock-gates.py` for captured-chain, independent/combined
gates, preconfigured ECC, reset and migration checks. This is dispatch-level
clock gating, not cycle-accurate BCH latency or mid-codeword suspension.

Patchset r48 connects the NAND wait timer to the CCM `gpmi` clock by default.
It tracks remaining nano-cycles, accounts for elapsed work before each clock
change, and suspends deadlines while gated. Ready received while gated is
handled on ungating. `test-prime-g2-live-nand-timing.py` tests rate changes,
three gate paths and migration while slowed/gated. Nonzero `gpmi-clock-hz`
is an isolated-test override; `use-ccm-clock=off` permits an explicitly
unconnected test clock. NAND migration v4 adds cycle accounting. This clock
connection covers WAIT_FOR_READY; r49 adds transfer-dispatch gating.

Patchset r47 exposes live CCM `gpmi` and `bch` QEMU clock outputs. Guest
CCM/ANATOP writes, including analog aliases, update both roots independently;
reset and migration rebuild them from registers. Run
`test-prime-g2-nand-clocks.py` for actual output-period checks against the
offline reference decoder. RUN-mode gate handling is modeled; PLL settling,
low-power modes and unknown external bypass inputs remain unqualified.
The GPMI timeout consumer is connected in r48 and BCH dispatch gating in
r49. BCH execution latency and operation-derived NAND busy intervals remain
unfinished.

Patchset r46 delivers NAND ready-wait timeout IRQ as a masked sticky level
from CTRL1[9] and CTRL1[20]. Direct/SET/CLR/TOG writes, reset and migration
update the actual wire. COMPARE writes preserve their full value and no
longer trigger IRQs; synthetic NAND program/erase completion no longer
fabricates device IRQ pulses. STAT is read-only. Timed-ready and migration
tests check these behaviors. ATA device IRQs remain outside the board model.

Patchset r45 adds a `nand-ready` input and an asynchronous APBH ready-wait.
An explicitly supplied `gpmi-clock-hz` determines the timeout in 4096-cycle
units. A ready edge resumes the chain; expiry records timeout status and
DMA_SENSE selects BAR instead of NEXT. Run `test-prime-g2-nand-ready.py` for
virtual-time boundary, cancellation, recovery and reset cases. No clock rate
is invented when this input is unconnected (default zero). CCM clock-tree
wiring, automatic NAND operation busy intervals,
READ_AND_COMPARE sense behavior and physical timing qualification remain
unfinished. NAND migration v3 adds the wait state and timer; migration during
an active wait is checked by `test-prime-g2-ready-migration.py`, including
remaining deadline, readiness and reset at first/half/last elapsed phases.
That test synchronizes the two externally controlled qtest clock epochs
before loading machine state; it does not modify the migrated timer.
Cross-accelerator and mismatched-clock migration remain unqualified.

Patchset r44 models APBH channel-zero completion as a masked, sticky level
interrupt (CTRL1 pending bit 0 and enable bit 16), with explicit
acknowledgement rather than implicit clearing at every transfer. Run
`test-prime-g2-apbh-irq.py` for actual-wire tests and the NAND migration suite
for restored APBH/BCH interrupt levels. APBH error generation, other channel
engines and timing remain incomplete.

Patchset r43 replays the captured physical ROM DMA chain in
`vm/test-prime-g2-retained-dma.py`, exposes its last fetched APBH command and
places PHORE in SEMA[23:16]. It checks a clean reference and explicitly
synthetic parity corruption; matching the latter's decoded outcome is not a
capture of the physical parity. Command state is added to NAND migration v2.

The same replay suite qualifies an offline raw-read plan from
`scripts/prime_g2_raw_read_plan.py`: all 2112 data/parity bytes are checked,
temporary descriptors and the complete RAM destination are restored, and
the original ECC read is repeated. The plan has no hardware transport;
passing this test does not qualify it for execution on the calculator.

`test-prime-g2-nand-migration.py` checks r43-to-r43 cross-process migration of
CMD/PHORE, BCH pending registers, descriptor/payload RAM, the cached-page
cursor and sparse NAND contents. A source-only parity-damaged overlay must
still produce the same failure after transfer to an initially clean
destination. Old-version and mismatched-configuration migration, subsequent
overlay-file persistence and mid-DMA timing remain unqualified.

Patchset r42 publishes ordinary physical-page STATUS0 first-block results and
page-wide corrected/uncorrectable flags from actual decoding. It can produce
the captured 0x4 pattern from a clean first chunk and an uncorrectable later
chunk. The NAND discovery suite checks independent error vectors and result
retention/refresh. ALLONES, handle/CE fields and completion backpressure are
still incomplete; this is not full BCH register parity.

Patchset r41 uses the ROM's codeword byte count for BCH PAGE_SIZE (2071 for
the captured BCH-2 geometry) and exposes the physically captured BCH_VERSION
0x01000000. Backing records still contain all 2112 bytes. Evidence is in
`hardware/prime_g2/reference/rom-clock-nand-status-20260907.json`.
The capture also reports an uncorrectable prior BCH operation; it cannot
identify that operation's page or prove a complete physical boot diagnosis.

Patchset r40 derives the BCH completion IRQ wire from CTRL status and enable
instead of pulsing unconditionally. CTRL aliases, reset and migration restore
recompute it; STATUS0/DEBUG1 ignore guest writes and MODE masks reserved bits.
`vm/test-prime-g2-bch-irq.py` observes the sysbus IRQ itself. Full STATUS0
contents, pipeline completion backpressure and clock/reset timing remain open.

Patchset r39 applies FCB `erase_th` to BCH_MODE before reading DBBT and
firmware. `vm/test-prime-g2-fcb-mode.py` inspects that handoff with the CPU
halted, including candidate fallback and reset reconfiguration, so U-Boot
cannot mask a ROM setup error. STATUS0 details and timing remain open work.

Patchset r38 implements physical-page BCH MODE erased thresholds over each
complete metadata/data/parity codeword, status FF and DEBUG1 zero counts.
DMA bytes remain damaged for the guest's software erased-page repair.
`vm/test-prime-g2-nand-discovery.py` checks threshold boundaries, repeat reads,
mixed pages and programmed-FF negative controls. DEBUG1 page aggregation and
nine-bit saturation are provisional, not physically measured chip behavior.

Patchset r37 consumes the Prime's single-NAND DBBT/BBTN list, validates whole
copies before using them, skips listed firmware blocks, and honors FCB
DBBT-only marker policy. Physical marker reads now include replayed overlay
state. `vm/test-prime-g2-dbbt.py` covers list boundaries, correction, fallback,
visible UI and ROM recovery. Multi-NAND/multi-page lists remain unsupported.

Patchset r36 connects physical codewords to ROM boot: BCH-40 FCB decoding and
checksum validation, FCB-driven firmware BCH, and error-aware redundant
firmware fallback. `vm/test-prime-g2-physical-rom-boot.py` qualifies visible
Lefony UI, corrected FCB/IVT/kernel errors and recovery/reset cycles using an
explicitly re-encoded full NAND fixture. This is not a physical acquisition
or a cycle-accurate mask-ROM implementation.

Patchset r35 adds actual BCH encode/decode in the explicit
`prime-g2-gpmi-bch.physical-pages=on` mode. Physical overlays are format-tagged
separately from decoded captures. NAND/APBH tests exercise damaged stored
codewords without decoder error hints. Its initial physical-page ROM boot
limitation is addressed by r36 above; decoded capture support remains separate.
Run `python3 vm/test-prime-bch-c.py` and the NAND discovery suite to qualify it.

Patchset r34 adds provisional ONFI parameter discovery (captured-page override
supported) and register-derived, bidirectional NAND marker adaptation. The
unmodified U-Boot selects 2-bit ECC instead of silently using zero strength.
Run `python3 vm/test-prime-g2-nand-discovery.py` for command/DMA qualification.
This still uses decoded NAND captures; real controller BCH integration and a
physical ONFI capture remain required.

Patchset r33 adds the captured Prime SRC boot-mode profile and read-only boot
mode latches. `test-prime-g2-rom-recovery.py` compares the emulator with
`hardware/prime_g2/reference/rom-src-snapshot.json`, including after resets.
Use `python3 scripts/capture_prime_g2_rom_usb.py --src` to repeat the physical
read-only capture; macOS uses native IOHID without sudo.

`prime_g2_peripherals.c` contains board models absent from upstream QEMU's
i.MX6UL machine: KPP, Goodix touch, PF1550, and GPMI/BCH NAND. The pinned QEMU
build copies this source into its tree and applies
`qemu-prime-g2-peripherals.patch` for SoC wiring and LCDIF semantics.

Evidence boundaries are intentional:

- KPP layout and the 39 Upsilon mappings are derived from the preserved board
  DT and use the same scan routine in VM and hardware builds.
- Goodix identity/address/reset/IRQ are captured; axis configuration remains
  provisional.
- PF1550 address and child functions are captured; register reset values are
  provisional until a safe read is possible.
- NAND geometry and partitions are captured. The default model starts erased
  and carries no proprietary HP bytes. When an ignored private raw+OOB capture
  is supplied, the machine ROM consumes its FCB/DBBT/IVT/DCD boot structures,
  loads either redundant U-Boot copy, and U-Boot reads kernel and DTB through
  the modeled controller/APBH/BCH path. Exact-stack tests now also replay the
  captured physical A/B metadata and slot hash, and reproduce the historical
  U-Boot packed-environment truncation before qualifying its repaired image.
  APBH and BCH remain behavioral rather than cycle-accurate electrical/timing
  models.

Run the comparator with:

```sh
python3 scripts/compare_prime_g2_traces.py \
  hardware/prime_g2/decoded/20260831T154107Z.json \
  hardware/prime_g2/emulator-contract.json \
  hardware/prime_g2/differential-contract.json
```
