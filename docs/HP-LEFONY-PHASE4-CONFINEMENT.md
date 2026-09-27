# HP/Lefony Phase 4: RAM filesystem confinement

Date: 2026-09-26. Phase 4 is complete for the tested experimental profile,
with the unsupported reset/update routes explicitly rejected below. This is an
emulator research milestone, not an installable shared NAND layout. No calculator USB
connection, NAND write, repartition or new backup was performed in Phase 4.
The accepted installed Lefony boot menu still has HP disabled.

## Exact compatibility and write policy

`hp-v15751-research-256-v4` accepts only the original V15751 component hashes
recorded in [Phase 2](HP-LEFONY-PHASE2-COMPATIBILITY.md). Research7 U-Boot verifies
the entire original image, exact length, IVT, inherited HP DDR mapping, NAND
geometry and every replacement site before applying a RAM-only patch. Unknown
images, partial matches and mismatched sites fail closed. The optional
`research-256` argument is confined to the experimental loader; the ordinary
Lefony build and Phase 3 unmodified-image command remain unchanged.

| Region / operation | Experimental policy |
| --- | --- |
| HP YAFFS blocks 392–2047 | Read/write; 207 MiB raw filesystem region |
| HP bad-block metadata blocks 4–7 | Erase and program pages 0/4 only, from the exact native metadata call sites |
| All other blocks below 392 | No HP program or erase |
| Blocks 2048–4095 | No HP program or erase; per-page canaries in the test fixture |
| Official firmware update | Both component entry points return failure |
| Maintenance reload | Request helper and reset-dispatch mode 3 reject the operation |
| HP factory-reset shortcuts | Both dispatcher modes and their shared helper reject the operation |
| Ordinary restart | Existing reset route retained; cold launches re-enter the verified RAM loader in the test setup |
| YAFFS format | Tested through HP's native format/remount implementation |

These are research offsets, not a frozen release layout. Phase 5 must reserve
and validate the metadata, image, boot-control and recovery regions together.
The metadata exception is not a general low-region permission: raw/OOB writes
remain confined to the filesystem; ECC writes require the matching return
address and page within each copy; erases require the metadata caller. The
bad-block callback rejects blocks outside HP's filesystem and a metadata header
whose table-page field is not 256, before changing RAM tables or NAND. Ordinary
raw writers cannot use the metadata exception. This is compatibility policy for
trusted, exact HP code, not isolation against malicious code that can program
DMA or forge return addresses.

The factory-reset frontend has indirect application callbacks that are not yet
qualified. It is explicitly refused rather than treated as equivalent to the
verified YAFFS format routine. These shortcuts must remain refused in a future
shared-layout launcher until individually qualified. This restriction is in the
experimental RAM profile only, not the user's installed firmware.

## Implementation

- [Profile and assembler](../scripts/prime_hp_confinement.py): full-input and
  geometry checks, two-phase site validation, unsigned page/block guards,
  metadata ownership and reset/update policy.
- [Generated U-Boot patch table](../native/prime_g2/hp_handoff/hp_confinement.h)
  and [RAM loader](../native/prime_g2/hp_handoff/hp_ram.c): the same patches are
  applied by actual ARM U-Boot before HP's original ARM entry.
- [Disposable fixture builder](../vm/prepare-prime-hp-confined-fixture.py):
  preserve original system data and factory markers, erase the smaller HP
  filesystem, and place canaries above its boundary. Its output is explicitly
  not a device flashing input.
- [Write observer](../vm/qemu/prime_g2_peripherals.c) and
  [trace analysis](../scripts/analyze_prime_hp_write_trace.py): record NAND
  program/erase confirmations before failure handling, including APBH/BCH
  transfers. Check attempted writes and committed overlay records separately.
  The observer does not reject escaping writes.
- [Instruction tests](../vm/test-prime-hp-confinement-instructions.py) exercise
  both original component instruction streams. Allowed hardware backends are
  intercepted only in these function-level tests; the full storage matrix uses
  the actual HP drivers and modeled NAND/DMA/BCH.
- [Storage matrix](../vm/test-prime-hp-confinement.py) and its
  [GDB helper](../vm/prime_hp_storage_gdb.py) call HP's real filesystem APIs from
  an ordinary SYS-mode application context. They never substitute filesystem
  results, rewrite user-visible state or intercept NAND callbacks.

QEMU r85 expands its overlay from 65,536 pages to the full 262,144-page chip.
The old host capacity produced false NAND failures at 128 MiB; that failed run
is excluded from qualification. A public regression fills 65,537 distinct pages
and verifies a higher page survives erasing the colliding lower block. NAND
snapshot version 6 explicitly rejects older snapshots whose serialized overlay
arrays have different lengths. Existing NAND files and overlay journal formats
are unchanged. No upstream QEMU revision or physical storage geometry changed.

## Reproduction

Private firmware and physical NAND captures stay under ignored `build/`.
The fixture builder requires the exact backed-up stock capture from Phase 3;
it does not read a connected calculator. Reuse that capture and existing
backups. Install `requirements-hp-research.txt` in the project virtualenv and
have the ARM assembler/linker and GDB available.

```sh
.venv/bin/python scripts/generate_prime_hp_confinement.py \
  native/prime_g2/hp_handoff/hp_confinement.h
PRIME_HP_HANDOFF_SOURCE_DIR="$PWD/build/lefony-uboot-hp-handoff7-src" \
PRIME_HP_HANDOFF_OUTPUT_DIR="$PWD/build/lefony-uboot-hp-handoff7-v4" \
  ./scripts/build_prime_hp_handoff.sh
./vm/build-prime-g2-qemu.sh
.venv/bin/python vm/prepare-prime-hp-confined-fixture.py \
  --stock build/dual-boot-phase3/stock-physical.raw \
  --output build/dual-boot-phase4/fixture-new
.venv/bin/python vm/test-prime-hp-confinement.py \
  --images build/dual-boot-phase2/fixture \
  --fixture build/dual-boot-phase4/fixture-new \
  --uboot build/lefony-uboot-hp-handoff7-v4/u-boot-dtb.bin \
  --ddr-image build/lefony-uboot-hp-handoff7-v4/u-boot-dtb.imx \
  --output build/dual-boot-phase4/qualification-new
.venv/bin/python vm/test-prime-nand-write-trace.py
.venv/bin/python vm/test-prime-nand-overlay-capacity.py
```

Output directories must be new. The combined matrix freezes its GDB helper,
records loader/model/profile hashes, retains complete private write logs and
checks that its original backing remains byte-identical. It covers initial
scan, file creation/readback, checkpoint save/restore, forced full scan, cold
retention, deletion, capacity exhaustion, space reclamation and format/remount.
An injected first-page program failure is reclaimed through HP's native YAFFS
empty-block path, then checked across a fresh cold boot with the injected fault
removed; the persisted HP bad-block table must still exclude that block.

For an interrupted orchestration run, `--resume` rechecks completed observations
against the current image, loader, DCD, QEMU, probe, profile and GDB-script hashes.
It reparses the original write logs and overlays before accepting a completed
stage. An incomplete stage directory must be preserved; use a new output
directory to rerun it. Empty write traces are not accepted as confinement proof.

## Completed qualification

The final matrix is recorded privately in
`build/dual-boot-phase4/qualification-v4/qualification.json`. All five storage
stages ran actual ARM research7 U-Boot, selected HP through its menu, verified
the RAM patches, and exercised HP's original filesystem and NAND drivers in
QEMU r85. Every observed attempt and committed overlay record stayed within
the declared filesystem or narrowly permitted bad-block metadata regions.

| Storage stage | Program/erase attempts | Result |
| --- | ---: | --- |
| Create/read 4 MiB, checkpoint and forced full scan | 2,241 | Data retained |
| Cold read, delete and format/remount | 1,682 | Data retained before deletion; format bounded |
| Injected program failure and native block retirement | 2,251 | File intact; metadata persisted |
| Cold boot without injected fault | 1,681 | Retired block still excluded; file intact |
| Fill, verify, delete, reclaim and format | 116,309 | Capacity and reclamation verified |

The capacity file reached **212,144,128 bytes (about 202 MiB)**. A subsequent
16 MiB rewrite after deletion exercised **496 distinct block erases** before
format/remount. This is one fixture's measured usable capacity, not a universal
capacity guarantee. No out-of-range attempt or model overlay-capacity failure
occurred. The source fixture remained byte-identical, and no write reached the
upper canary region. The captured stock bad-block table already retires blocks
6 and 7, so the real failure test used metadata copies 4 and 5: two erases and
four page programs. Separate instruction tests cover all four usable copies.

Additional passing checks:

- Both exact HP component instruction streams: 54 raw-writer boundary cases,
  432 metadata page/caller cases, callback ownership/header rejection, native
  metadata sequencing, bounded format loops and disabled reset/update entries.
- Separately verified updater RAM transfer with all expected patches present;
  no NAND writes occurred during that observation. Its write-path evidence is
  instruction-level, not an exercised updater frontend.
- Independent observer regression: protected writes really execute and are
  reported, including injected failures and out-of-chip attempts. The observer
  cannot hide an escaping write by rejecting it.
- Full-chip overlay capacity regression and NAND/BCH, OOB, bad-block, restart,
  GPIO/keypad, ADC, SNVS and LCDIF model regressions.
- Ordinary Lefony menu/recovery: actual auto/manual boot, Enter during the bar
  and held at startup, all arrow keys, priority persistence, Goodix touch/cancel,
  disabled HP, invalid-image rejection and one-shot recovery return.
- 49 targeted host tests; generated C table matches the assembler source.
  Research U-Boot and QEMU builds, Python syntax checks, local documentation
  links, `make check-public` and `git diff --check` passed. The broader `make test` run was
  interrupted after 233 passing tests to keep validation scoped; a complete
  repository-wide host-suite pass is not claimed.

Final candidate identities (SHA-256):

| Artifact | SHA-256 |
| --- | --- |
| Research7 v4 `u-boot-dtb.bin` | `190b2813c436a699138d666e3116329427c9ecf81599047c61b9ae1040f71702` |
| Paired `u-boot-dtb.imx` / HP-compatible DCD | `0f1afae2fd75f633f161e771ac308e661b5d3ce2c560e5858ccb1f2fe7265c20` |
| QEMU r85 executable | `e35643035d82b8b23621b9335e5c79e8fe56571fd05e37919bfbe038ffd81a42` |
| Patched HP OS RAM image | `00941db104a2d0148d3ab51f855d1a7f14ae1c15b8f33b6f4d706d346db3163c` |
| Patched updater RAM image | `48860125a64c2922bdbdb7eb108896b5fa955af3de3faa3421c0224f4398b2d6` |

These are qualification identities, not release signatures. Private fixture
hashes, frozen experiment source, runtime captures and complete logs remain
under ignored `build/`; no vendor firmware or NAND capture is published.

## Qualification limits

No physical boundary-patched HP boot, shared-layout migration, release profile
signature, whole-device power-loss behavior or flash endurance is claimed.
The nominal 256 MiB split remains an experiment. Phase 5 must enforce verified
profile selection on every persistent boot route, never fall back to unpatched
HP on a migrated calculator, and preserve recovery and transactional migration.

This milestone's functional tests exercise storage APIs, not HP UI automation.
A recreated filesystem reaches HP's welcome screen, but its modeled unlock
swipe remains unresolved. No HP touch fix or UI bypass was included. The
separate updater has exact-image instruction and loader-transfer coverage;
its frontend is not qualified or exposed as an installed update route.
The physical calculator continues running the previously restored Lefony OS.
