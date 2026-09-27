# HP/Lefony dual boot: Phase 2 compatibility research

Date: 2026-09-25. Phase 2's research deliverable is complete with the unresolved
paths below. **No HP build is approved for physical dual boot.** Phase 3 must
establish the authentic handoff; Phase 4 must establish confinement. This is
not an installable or signed compatibility profile.

## Inputs and reproducibility

Only the following original V15751 inputs are accepted. The analysis tools
reject a different size or SHA-256 before executing any image instructions.

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| Official container `HPPrime_OS.img` | 19,483,788 | `80ba573472b3731bdbb0165bf13390579863ca1d3f5c003dfb21c17dd4871461` |
| Main `HPPrime.img` | 8,192,864 | `25d3d2d27e45fc3ce7dc8c4a111b31f8aefc14c4b21e8d8ee4b32251e31c1b82` |
| Separate `bootloader.img` updater | 358,316 | `9bfe04ec74eed51b606001caa3e5c0f701acd70eeb7d622f5a25616efdc0436e` |

Hashes identify research inputs; they are not signature verification or release
approval. The retained older stock-emulator fixture has different hashes. Its
shim-assisted update results cannot qualify V15751.

Supply a locally retained official container; no HP firmware is downloaded or
redistributed by these tools. From the repository root:

```sh
.venv/bin/python -m pip install -r requirements-hp-research.txt
.venv/bin/python scripts/prepare_hp_prime_stock_fixture.py \
  /path/to/HPPrime_OS.img --output-dir build/dual-boot-phase2/fixture
.venv/bin/python scripts/analyze_hp_prime_compatibility.py \
  --container /path/to/HPPrime_OS.img \
  --fixture-dir build/dual-boot-phase2/fixture \
  --output-dir build/dual-boot-phase2/report
.venv/bin/python scripts/probe_hp_prime_direct_boot.py \
  --fixture-dir build/dual-boot-phase2/fixture \
  --output-dir build/dual-boot-phase2/direct-boot-ddr --seconds 20
```

The probe requires the existing [Prime QEMU build](../vm/build-prime-g2-qemu.sh).
Use a new probe output directory for a repeat run. Reports, disassembly and
screenshots stay under ignored `build/`; the tools enforce that output boundary.
The analyzer checks source files again after execution and never writes them.
The probe uses synthetic erased NAND, no persistent overlay and no physical
USB connection. Its successful process exit means the observation completed,
not that HP booted successfully.

Private evidence retained for this run:

- `build/dual-boot-phase2/report/compatibility.json`: identities, exact expected
  store bytes, decoded ranges, function execution results and candidate writer
  references from ARM/Thumb scans.
- `build/dual-boot-phase2/report/COMPATIBILITY.md`: private evidence index.
- `build/dual-boot-phase2/analysis/bootmode.json`: independent reset-dispatch audit.
- `build/dual-boot-phase2/direct-boot-ddr/`: per-image command, CPU samples,
  model counters, UART, reset log and inspected screen captures.

## Reproduced filesystem boundaries

Both images calculate `ceil(48 MiB / eraseblock_bytes) + 8` for the start and
`total_blocks - 1` for the inclusive end. On the modeled 512 MiB / 128 KiB
geometry this is **392–4095**, or 49–512 MiB.

| Evidence | Main OS | Updater |
| --- | --- | --- |
| Initialization | `0x802B1A24` | `0x80007BDC` |
| Parameter start store (`dev+0x14`) | `0x802B1ACA` | `0x80007CF0` |
| Parameter end store (`dev+0x18`) | `0x802B1AD0` | `0x80007CFE` |
| Internal-bound copy start | `0x804716E4` | `0x800060E0` |
| Format function | `0x8047181C` | `0x80006218` |

The instruction harness executes the actual division routine, parameter stores
and copy to `dev+0xF4`/`dev+0xF8`. Three geometry cases per image pass, including
a different block size. Those extra cases test interpretation of the code;
they do not approve other physical geometries.

Format-loop execution confirms the inclusive end, skips blocks reported with
state 9, and performs no iteration when end precedes start. The stock case
queries/erases 3,704 blocks. A synthetic end of 2047 with bad blocks 400 and
2047 queries 1,656 and erases 1,654. The initializer, state query and erase
callbacks are intercepted explicitly. Supplying synthetic internal bounds is
a data-flow experiment, not an implemented HP RAM patch.

The end-setting sequence is therefore a verified **candidate patch location**.
There is no approved replacement encoding, selected storage split, loader
integration or physical confinement claim. Future profiles must bind the whole
image, exact expected bytes, geometry, layout and handoff version.

## Writer and transition inventory

Addresses below refer to this exact loaded image pair. The private report also
indexes direct branch and pointer candidates to the raw writer functions.
Linear disassembly crosses mixed code/data; it cannot prove reachability or
find every indirect call. **An exhaustive writer proof remains open.**

| Path | Evidence in V15751 | Compatibility decision |
| --- | --- | --- |
| Main initialization | `0x8039DFD6 → 0x802B31BE → 0x802B1A24`; actual boundary/copy execution passes | Boundary research supported; full startup unqualified |
| YAFFS program/erase | Main callbacks `0x802B18E6` / `0x802B191E`; updater `0x800079BA` / `0x80007A28` | Narrower format bounds alone do not prove all write/GC/checkpoint paths |
| Cold boot | ARM vector at `0x80002000` enters main `0x80741EBC`, updater `0x8003B9E8` | RAM placement established; authentic boot-chain state unresolved |
| Software reset | USB `0xE8` dispatch at `0x80415AE0`: mode 0 calls `0x802B076C` | Dispatch executed; full reset path not qualified |
| Maintenance entry | Mode 3 calls `0x802B0B7E`, writes a request and enters reset; other direct callers also exist | Updater reload and direct maintenance-key paths must be mediated; unsupported |
| Factory reset | Modes 1/2 call `0x802F5580` with second argument 0/1; continuation includes indirect object callbacks near `0x802F5716` | Dispatch verified; complete deletion/format and reboot effects unresolved; unsupported |
| Diagnostic format | Main `0x804E931E` calls YAFFS format wrapper `0x8039D7EE` | Format loop has bounded evidence; its whole UI/error path remains unqualified |
| Diagnostic erase OS | Main `0x80525ECA → 0x805155EC → 0x804E9232 → 0x803A23D4`; updater `0x80031790 → 0x8002FB80 → 0x80029E6C → 0x80014744` | Both actual erase routines request raw blocks **0–3**; bypass YAFFS; unsupported |
| Official update | Main writer `0x803A2680`, updater `0x80014A40`; raw erase helpers `0x803A1FD2` / `0x80014628` | Separate system-area writer; must not run unchanged after migration |
| Raw page program | Main `0x803A1700` and retry wrapper `0x803A1BE0`; updater `0x80013F24` / `0x80014404` | Callers include boot/system and metadata code outside YAFFS; require separate policy |
| Bad-block marking | Main `0x803A190A`, updater `0x8001412E`; YAFFS callbacks `0x802B192E` / `0x80007A40` | Marks and metadata rewrites escape filesystem bounds; unsupported until protected |
| Bad-block scan | Main diagnostic `0x804E9332 → 0x803A209E`; updater scan `0x800146EC` | Observed scan builds a RAM list through raw status queries; not itself proof of a NAND writer |

The raw update erase helpers were executed with a requested 384-block prefix
and synthetic bad block 7. They scan blocks 4–4095, then erase 0–383 except 7
(383 erase calls). Both update callers derive the prefix from 48 MiB divided
by block size. This preserves neither the installed boot manager nor current
Lefony payloads. The write routines independently stop at the system-area
limit; changing YAFFS's end field does not change them.

The bad-block callbacks were executed with synthetic table placements at block
4 and block 16. Each appends the failed block to the RAM table, erases four
table-copy blocks and programs pages 0 and 4 in each copy. Placement comes from
boot metadata's page field at `header+0x78`, not YAFFS's end. These synthetic
placements demonstrate dependency and bypass behavior; they do not measure
the connected calculator's HP metadata. Failure/retry exhaustion and every
boot-control rewrite remain unresolved.

## Placement and handoff findings

Both images are linked at **`0x80000000`**, have IVT at `0x80000400`, DCD at
`0x80000440`, boot-data at `0x80000420`, and ARM entry at `0x80002000`.
Absolute reset vectors and RAM literals rule out assuming arbitrary relocation.
The boot-data lengths are 8,192,863 and 358,314, respectively, slightly shorter
than the extracted files; retain the complete hash-checked payloads rather than
silently truncating them to those fields.

Both system writers calculate the first component's nominal start as
`12 * pages_per_block`: **page 768, 1.5 MiB** with 64 pages/block and 2 KiB pages.
Selected instruction execution reproduces this. Bad-block skipping can advance
the actual first page. Subsequent components are aligned after the preceding
writer's returned end. A current stock NAND readback, complete component map,
boot-copy selection and ECC/OOB audit are still needed before choosing offsets.
The older fixture's page 768 observation is consistent, but is not a V15751
physical readback.

The ARM startup disables IRQs and clears MMU/cache-related control bits, sets
IRQ/system/SVC stacks, invokes platform initialization, then enables IRQs and
enters the runtime. The stack literals are main IRQ `0x807CE8F0`, system/SVC
`0x807CE4F0`; updater IRQ `0x80055108`, system/SVC `0x80054D08`.
Do not interpret this as a complete handoff ABI. DDR, DCD effects, interrupt
sources, DMA ownership, caches and timer/peripheral state still require a
working preceding stage and explicit validation.

The unmodified direct-load probe used QEMU 11.1.1, Prime patchset r79, pinned
source `c3d48b7d1e89604920e5b81b91140c2ad39a1943`, Cortex-A7 and 256 MiB RAM.
DDR was explicitly preinitialized by the model; HP's DCD was not executed.
At both 10 and 20 seconds the main image sampled the IRQ vector `0x80002018`
with return address `0x803A134A`; the updater sampled NAND/APBH wait
`0x80013B6A`. Both screens were blank. Each recorded five NAND commands and
zero ECC writes/overlay pages. These are failed startup observations, not proof
of no possible writes. An earlier probe without modeled DDR initialization
aborted before HP code could execute and is excluded from HP startup evidence.

## Supported scope and next gates

Supported now: exact-hash offline analysis, isolated selected-function
execution, and bounded emulator observation. **Supported physical HP/dual-boot
paths: none.** The accepted Phase 1 Lefony boot menu remains installed and HP
selection remains disabled. No calculator flash, layout, boot default,
signature policy or installer behavior changed during Phase 2.

Phase 3 can proceed with an unmodified, hash-checked HP loader experiment in
RAM and unchanged HP geometry. Its first target is authentic NAND/interrupt
handoff, using the recorded stalled addresses. Before physical testing, retain
a verified stock backup and use an isolated HP test setup; the currently
installed Lefony layout collides with HP's system and filesystem regions.

Before any dual layout is enabled, resolve all indirect writers, cold/reset and
maintenance reloads, factory resets, diagnostic paths, official-update policy,
bad-block/FCB/DBBT failure paths and complete NAND placement/ECC. Re-run the
confinement matrix with actual writes and injected failures. These are explicit
remaining gates, not paths implicitly approved by this research milestone.

Validation: 25 relevant host tests and four subtests pass; exact-input private
instruction checks pass; both bounded QEMU observations completed and their
blank frames were inspected. Public-tree and whitespace checks are recorded in
the private evidence index. No production target changed, so no firmware rebuild
or physical flash was required.
