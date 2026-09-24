# SDK 1.0 implementation ledger

Started 2026-09-12 against base revision
`91701e213d74918226b3692f570079c2c13d9000` and the existing experimental changes.
The full [SDK 1.0 plan](NATIVE-APP-SDK-1.0-PLAN.md) remains the acceptance authority,
including the retained SDK account/folder publication requirements. No milestone
or release gate is waived by this ledger.

The implementation objective includes four working proving applications, SDK
tests and host bundles, developer documentation on the website, coordinated
publication and Git pushes after integration. Physical and independent-developer
qualification must have actual evidence before stable 1.0 can be declared.

| Milestone | Current status | Required remaining acceptance |
| --- | --- | --- |
| R0 decisions/proofs | Runtime/memory, large-file transactions, C++ UI/ARM preview, bounded math/USB and four pinned-app proofs have local evidence; the scoped MIT alternative is applied and the library comparison selects newlib | Final support matrix, complete artifact/source audit, host versions and qualification resources/owners, measured budgets |
| R1 C/C++ foundation | Mixed compilation, ordinary main/newlib startup, public API 3 foreground execution, guarded heap and copied pixels; API 4 input, external debugging, bundled-runtime CMake and API 10 system-service candidate have ARM evidence; the selected library passes 23 expanded ARM phases; four buffered-stream lifecycles also pass debug/release and cold readback on current/retained VM firmware (32 phases) | Broader runtime/function qualification, workload/physical input acceptance, frame pacing, system integration/math acceptance and physical qualification |
| R2 durable files | Production FILE3/FILE4 transactions with FILE5 root protection, authenticated file sessions, newlib stdio/live sync, directory/usage queries, quotas, per-file USB exchange, checkpoint/migration, host private-data recovery and live whole-app archives; cross-signer consent, exact-identity code repair and API 12 writer abort/full-quota app saves have local evidence; selected Doom save/compatible-update recovery and quick-slot sessions pass; 91 frozen macOS storage CLI steps across eight ARM sessions cover cancellation, accepted commits, rollback and damaged-object repair | Broader damaged/unreadable media and resource/error coverage, complete host bundles and physical durability |
| R3 UI authoring/preview | Notebook with OS palette/clipboard and saved math settings, configurable controls/fonts, retained preview data and source/layout inspection; Notebook 0.6 shared dialogs/direct saves, Notebook 0.6.1/UI Gallery 0.1.1 touch caret/selection, clipped long fields/menus and faster populated previews have local ARM evidence; the current macOS bundle passes touch editing, exact saves and cold preview | Broader glyph/constraint coverage, supported-host latency budgets, complete document resource/recovery journeys, remaining host bundles and independent trials |
| R4 app connectivity | API 11 scoped USB channel, HTTPS bridge/companion command and Link Gallery have local signed ARM/TLS evidence; frozen macOS native TLS and ten ARM/model-USB companion streaming/error journeys pass, with three additional disconnect repeats; the later host bridge fixes late-fragment session loss with ARM boundary/cache evidence; the current macOS bundle passes eleven companion cases including late delivery and same-session requests; the new Linux production archive also passes all eleven isolated frozen companion cases | Remaining supported-host bundles and clean-host operation, broader resource and lifecycle qualification, physical USB/network journeys |
| R5 integrated apps/ecosystem | Not complete; four proving apps have working local ARM journeys; SDK account/session/library/project links, folder publication/update, upload recovery, listing merge, metadata-only edits and withdrawal have local evidence; frozen macOS local-service/native-Keychain account and 37-step publication/accepted-download journeys pass; the store-enabled Linux archive also passes 20 Secret Service account checks and 37 local Worker publication/download steps with explicit emulator fixture trust; managed store capacity and artifact cleanup preserve accepted history; production migrations, initial namespace/owner inventory, real GitHub/source-SDK macOS Keychain login, SDK Counter publication and exact signed download/source-rebuild/ARM launch now pass | Complete resource/error/user-data and physical qualification; clean-host credentials and release integration, broader live lifecycle/capacity acceptance, independent beta trials |
| R6 release qualification | Not complete; live private key enrollment/revocation, lost-key signer replacement, unused revoked-key removal and backed-up repair of readable corrupt and unreadable-payload registries have local ARM evidence | Full compatibility/security/lifecycle matrix, native Windows/macOS/Linux, physical performance/storage/power, unreadable-media recovery, exact artifacts, licensing/source distribution and website/download verification |

## Current public distribution and trial scope

The macOS ARM64 and Linux x86-64 SDKs now publicly include the browser Prime
keyboard and larger touchscreen. Both frozen bundles, matching source groups,
source kit and public download routes are verified. See the
[current release record](SDK-EMULATOR-RELEASE.md). Superseded local bundles were
deleted after verification at the user's request; projects, keys and recovery
data remain retained. The user selected maintainer trials on macOS only;
native Linux/Windows, independent feedback and physical acceptance remain open.
No R6 gate is waived by that scope choice.

## Current changes

The sections below preserve implementation history. Later dated checkpoints
supersede earlier statements about unfinished features; use the milestone table
above and the capability matrix for the current overview. A historical pass
continues to qualify only the source/artifact recorded with that checkpoint.

- [API 6 file catalogue](../sdk/FILES.md#directory-listing-and-storage-usage)
  adds generation-checked directory pages and separate committed, staged and
  shared-allocation usage fields. App inspection does not convert legacy storage.
- [API 5 live sync](../sdk/FILES.md) commits a named file while retaining its
  descriptor and position. Ordinary `fflush` plus `fsync` passes ARM forced-exit
  and cold-reopen checks. This is a single-file save, not a complete R2 milestone.
- The [API 4 input stream](../sdk/INPUT.md) adds held/down/up physical keys,
  ordered key/touch events, bounded overflow recovery and focus reset. An
  ordinary C main exercises it through normal KPP/Goodix in signed installed
  ARM execution; the legacy input/scheduling regressions remain passing.
- The [API 3 foreground candidate](../sdk/FOREGROUND.md) now negotiates entry,
  yield/sleep/exit, guarded memory and copied-pixel presentation on both targets.
  Public-service ARM probes and stdio/lifecycle checks pass. Project schema 2
  now selects reusable conventional startup and the candidate newlib profile;
  schema 1 retains callbacks. The
  earlier VM-only prototypes below remain historical architecture evidence.
- Mixed C11/C++17 translation-unit discovery and separate frontend flags, language
  reporting, C-compatible ABI 1 service helpers and ARM layout checks.
- Actual pure-C/mixed-linkage host tests plus a signed installed ARM package that
  saves through C after normal keypad input and verifies the data after cold boot.
- A pinned newlib maintainer build recipe for architecture qualification. It
  intentionally does not make incomplete libc/syscalls the default app runtime.
- A real ARM newlib executable proof covering allocation/exhaustion, realloc
  preservation, formatting/parsing, sort/search, math and honest file errors.
- A [VM-only foreground execution proof](NATIVE-APP-EXECUTION-EXPERIMENT.md)
  saves and resumes the user stack, integer/VFP registers and status across
  timer preemption and explicit yield. Installed execution, exit, normal Home
  interruption and same-OS relaunch passed; the public execution ABI is unchanged.
- A Prime-only keyboard edge fix retains observed releases across event-wait
  timeouts, preventing a press between waits from being lost. Held-key/chord
  behavior and the separate repeat policy are covered by regression checks.
- A [VM-only memory/pixel proof](NATIVE-APP-MEMORY-PIXEL-EXPERIMENT.md) maps a
  guarded, non-executable heap, exercises a 6 MiB allocation and copied RGB565
  frames, and checks isolation, exhaustion, saved data and cleared relaunches.
- Reproducible [Doom engine and Freedoom input pins](../sdk/ports/doom/README.md),
  verified offline fetching, and an ARM compile probe for all 80 portable engine
  translation units, followed by public-API gameplay, save/cold reload and clean
  exit on the ARM emulator. Error/resource and physical acceptance remain open.
- [Configured C/C++ projects and source format 2](../sdk/PROJECTS.md), with
  matching website readers, support explicit source lists, includes/defines,
  bounded language-specific flags and the real Doom source tree. The compatible
  website and SDK changes are local candidates awaiting coordinated release.
- Existing edits preserved; work is on `codex/sdk-1.0`. Baseline patch/status are
  retained privately under ignored `build/sdk-1.0-baseline/`.
- A [production document transaction engine](NATIVE-APP-DOCUMENT-TRANSACTIONS.md)
  separates immutable packages and 64 KiB data snapshots behind atomic FILE3
  roots. Converted apps load, save and upgrade through the guest path. Public
  checkpoint/migration controls now have an API 8 candidate; host rollback remains
  unfinished.
- The [large-file engine](NATIVE-APP-LARGE-FILES.md) uses FILE4 indexes/chunks in
  the same reserved region. The pinned WAD passes streaming, cold-read and
  partial-edit checks with independent hashes. An [experimental file service](../sdk/FILES.md)
  now connects authenticated apps to the engine; real newlib stdio works under
  the VM conventional-execution experiment.
- Foreground resume events now follow normal services/touch/keyboard dispatch,
  preserve the input snapshot through waits and avoid unchanged-surface redraws.
  Key repeat and UI timers account for elapsed time across these frequent wakes.

## Reference program evidence

Doomgeneric is pinned for the first portability proof to
`dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284` from
[its upstream repository](https://github.com/ozkl/doomgeneric/tree/dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284).
The inspected `doomgeneric/` subtree contains 192 C/header files totaling
1,696,790 bytes; its largest file is `info.c` at 139,548 bytes. Default zone
allocation is 6 MiB. These measurements confirm the existing 64-file, 64-KiB
source-file and fixed app-memory limits cannot satisfy this port unchanged.
Sources are retained under ignored `build/sdk-1.0-upstream/doomgeneric/`.
Game data is now pinned to the unmodified Freedoom Phase 1 0.13.0 WAD, with
license and credit files. The current port has the gameplay/save/cold-reload
evidence below; complete workload and release acceptance remain unfinished.

Newlib candidate: 4.6.0.20260123, source SHA-256
`6ff27e3bf022666f43f7802255be680eeff722ac181b1725d21e2e8318604ee3`.
The first configure attempt rejected this checkout's space-containing path.
The durable recipe now uses a temporary neutral build/staging path and copies
successful outputs into the requested directory. Its original failure log is
retained under `build/sdk-newlib/initial-source-path-failure.log`.

## Validation recorded for this batch

Host: macOS 26.6.2 ARM64, Python 3.14.6, GCC 16.2.0.

- C and existing maturity host tests: 33 passed. Final full host suite:
  **550 passed, two expected private DTB/DTS skips**, in 89.75 seconds.
- `vm/test-sdk-c.py`: passed mixed C/C++ linkage, signed modeled installation,
  normal keypad input, checked service failure, staged data save and cold reopen.
  This used the existing VM ELF
  `b94460e09d9ac1170a5cd9f499c401ea1d7756c02d545a8ba059f55b3bb1d2c8`.
- Pinned newlib libraries built successfully. `vm/test-sdk-libc.py` passed its
  ARM non-file library proof using that same VM ELF. Its library/source hashes,
  executable sizes and exact runtime evidence are retained in
  `build/sdk-libc-qualification/report.json` and `build/sdk-newlib/candidate.json`.
  A GNU-stack warning from compiler support code prompted an explicit
  non-executable-stack link option in the probe; the final recheck passed
  without that warning. The mixed-C installed/cold-boot proof also passed again.
- The C/libc work above changed no firmware driver, ABI number or storage format.
  No physical device was written, no website deployment was made and no Git
  push has been performed. The overall implementation objective remains active.

### Foreground execution follow-on

The follow-on changes the shared IRQ/SVC context path and adds emulator-only
opt-in services. Two consecutive installed runs passed after the keyboard fix:
the finite program survived **44 and 37 preemptions**, respectively, one yield
per run, and preserved registers/flags/nested stack data through **45 and 38
resumes**. Each run also verified one `main`, later normal input without restart,
Home interruption of an infinite CPU loop, and same-OS relaunch. Home replay
took 1,048/1,022 ms including intentional key-hold/release waits; these are not
physical response-latency measurements.

Final validation:

- Full host suite: **551 passed, two expected private DTB/DTS skips**, 97.55 s.
- Both `make firmware-vm` and `make firmware`: passed with the key-edge fix.
  Existing upstream overloaded-virtual, missing GNU-stack and firmware RWX
  segment linker warnings remain; no claim of a warning-free build is made.
- `vm/test-sdk-input.py`: passed normal keys, text/modifiers, physical positions,
  two-contact Goodix ordering, cancellation and release.
- Preserved Counter and Surface3D ABI 1 bytes: passed normal interaction again.
- Comprehensive smoke: direct ELF boot, verified U-Boot boot and protocol all
  passed on the final VM. Its summary is under
  `build/prime-g2-native-suite-20260912-010350/`.
- All 38 legacy ARM isolation cases passed after the exception/counter changes,
  before the final shared keyboard-edge patch. Their exact older firmware hash
  is retained with that report; the final input/compatibility/smoke tests above
  cover the subsequent keyboard change.
- Documentation local links, `git diff --check` and public-tree check passed.

Final VM ELF SHA-256:
`fdf95190ed66d44a39162569d0ff6897b4696ad538698701b1b516d7cf7d663d`.
Physical-target binary (compiled, not flashed/tested):
`05733c11eb54ee5f256a69be2f1d8cb3dafe9c89aadeca494281c58148f4712f`.
Developer QEMU:
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
Execution source hashes, both reports and captured frame are retained under
`build/sdk-execution-qualification/`.

Intermediate failures are preserved under that directory's `iterations/`:
diagnostic index bounds, delivered-key counting, an undersized CPU loop that
could finish before preemption, and the shared timeout-boundary key loss. The
first smoke attempt also required starting the installed Colima environment to
rebuild boot media. Final passes above followed those fixes; this remains local
emulator/build evidence, with physical and supported-runtime gates open.

### Larger memory, copied pixels and pinned Doom inputs

The next R0 candidate reserves 8 MiB with two unmapped guard pages, yielding
**8,380,416 usable app-heap bytes** and **20,080,608 bytes reserved for the kernel
heap**. Heap setup took 17 ms in both measured emulator launches. This bounded
setup call exceeds the experiment's 10 ms user slice; physical latency, cache
behavior and final execution budgets remain unqualified. The public ABI 1
limits and discovery capabilities are unchanged; these services are VM-only.

Final candidate validation:

- `vm/test-sdk-memory-pixels.py`: all five installed cases passed. The normal
  case checks a 6 MiB allocation plus a 153,600-byte RGB565 frame, failed-realloc
  preservation, rejected malformed copies, saved data and zeroed memory on
  same-OS relaunch. Unnegotiated access, both heap guard pages and execution
  from the heap faulted while the OS remained responsive.
- `vm/test-sdk-libc.py`: the original non-file ARM newlib proof passed again
  using the shared bounded `_sbrk` adapter, which also supports heap shrinkage.
- `vm/test-sdk-execution.py`: passed again, with 52 timer preemptions, one yield
  and 53 resumes preserving registers/flags/stack. Infinite-loop Home exit and
  same-OS relaunch also passed.
- Preserved Counter and Surface 3D ABI 1 package checks passed. Comprehensive
  smoke passed direct ELF, verified U-Boot boot and protocol; its summary is in
  `build/prime-g2-native-suite-20260912-012519/`.
- Both `make firmware-vm` and `make firmware` passed. The existing compiler and
  linker warnings described above remain. The physical target was compiled,
  not flashed or physically tested.
- Targeted C, key-edge and SDK contract host tests: **103 passed**, 10.52 s.
  A subsequent full-suite research recheck passed **551 tests**, with the two
  expected private DTB/DTS skips, in 89.09 s.
- Doom's 80 portable C files compiled with the pinned toolchain/newlib headers
  without portable-core patches. Before dead-code elimination the relocatable
  engine contains 274,047 code/constant bytes, 59,995 initialized-data bytes
  and 243,608 BSS bytes. The six platform hooks and libc/I/O dependencies remain
  unresolved; this object is not a linked or running application.
- The pinned Freedoom WAD is **28,795,076 bytes**, SHA-256
  `7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d`.
  The fetch command's offline verification passed for the engine, WAD, license
  and credits. Game data stays in the ignored input cache.

Final VM ELF SHA-256:
`e123b09c22ef980079c49a5a87d687ef652d95cfb0014d81cd6bad9187e914f5`.
Physical-target binary:
`b139e260da2f390ea3abc777d1fa8e12109660c1ed5a7cbffc01c3dc916015e8`.
QEMU remains the developer binary identified above. Exact reports and source
identities are in `build/sdk-memory-pixels/`, `build/sdk-doom-architecture/`,
`build/sdk-libc-qualification/` and `build/sdk-execution-qualification/`.
The first memory-test failure was a test assumption that an already signed
negative diagnostic needed unsigned conversion; the corrected test passed.
No R0–R6 milestone is complete, and no website deployment or Git push is claimed.

### Configured projects and coordinated C source exchange

`project.json` schema 1 selects up to 256 C/C++ translation units and bounded
include/define/compiler settings; the original discovery path keeps its 64-unit
limit. Source format 2 supports 512 files, 256 KiB source/notice files, 4 MiB total
contents and 8 MiB encoded JSON, while retaining 64 KiB asset/config/test limits.
The existing source formats, app ABI/memory, package signatures and runtime
storage limits are preserved. The new sizes accommodate the measured Doom tree.

Website source parsing, final ingestion limits, capability discovery and browser
file selection have matching readers. The project configuration remains inert;
no shell/compiler-plugin/build-hook execution was added. The shared 35-case
configuration corpus has identical bytes in both repositories. SDK GitHub login,
folder publishing and upload recovery remain separate work.

Validation on the updated SDK identity
`058cdbab689add148fba9b4c415c6e8108b0ff01419dab3efc34983a795bd0a0`:

- Full host suite: **560 passed, two expected private DTB/DTS skips**, 109.85 s.
  New tests build an 81-unit C/C++ project, preserve selected flags/includes,
  omit an invalid unselected platform file, check cache invalidation, and produce
  identical ARM bytes after extracting/relocating the source bundle.
- `vm/test-sdk-c.py`: a configured source-2 project was extracted, rebuilt to
  identical package bytes, signed/installed into synthetic storage and tested
  with normal keypad input, service errors and cold persistence. The current
  VM ELF remains `e123b09c22ef980079c49a5a87d687ef652d95cfb0014d81cd6bad9187e914f5`.
- Website full suite: **401 passed**, 12.55 s, including the real extracted C
  package's local publication/signing/download check via
  `LEFONY_SDK_TEST_PROJECT`. An earlier broad run had 400 passes and one 5-second
  timeout in the unchanged recovery-download test while host builds ran; the
  same full suite passed after those builds finished. The initial log is retained.
- Website build and lint passed; four companion adapter tests passed. All ten
  app-store browser tests passed, including old/new source upload bounds.
  Desktop/mobile screenshots were inspected, with no horizontal overflow.
- The pinned Doom compile probe passes and emits a **194-file, 1,859,127-byte**
  source-2 bundle, SHA-256
  `9d2899ec2d787a31c1fbd1ba343d53309f7aee2d1d6bcca2c8d63db1ee8b3d3f`.
  The actual website validator accepted it. The engine license is now hash-pinned
  alongside the source; offline input verification passed. This is source/core
  compilation evidence, not a linked/running Doom application.

Evidence is retained under `build/sdk-source2-qualification/`, with ARM reports
in `build/sdk-c-qualification/` and Doom inputs/reports in
`build/sdk-doom-architecture/`. No firmware rebuild was needed for these host
compiler/source-reader changes. No physical operation, deployment or push was
performed. The source-2 rollout must deploy compatible website readers before
distributing the updated SDK; existing download qualifications do not cover it.

### Production package/data transactions

The real `AppStorage::Volume` now integrates the FILE3 transaction engine on its
existing littlefs/NAND backend. It verifies/copies the package on first FILE2
conversion, then performs data-only commits, signed package upgrades, retained
pair acceptance/rollback and bounded object cleanup. Converted apps use the
engine on normal Close. A schema mismatch permits reads but rejects writes;
successful schema-0 closes accept pending upgrades. Faulted callbacks discard
uncommitted edits and retain the pending pair. The VM-only resumable runtime
still treats OS-owned Home/Close termination as successful; its forced-exit/live
checkpoint ownership policy remains unfinished.

Conversion is currently an internal Volume API, exercised through the production
host fixture. No public checkpoint/migration/rollback capability, large-file API
or stdio is advertised. Data remains bounded at 64 KiB. Per-app quotas, guaranteed
recovery headroom, public live-buffer ownership and physical durability are
remaining R2 requirements, not waived by these tests.

Final validation on 2026-09-12:

- `make test`: **561 passed, two expected private DTB/DTS skips**, 112.54 s.
  The final scoped storage run passed six tests under the existing host workflow.
- The new production storage test passed **512 interruption cases**, covering
  pre-operation and torn program/erase boundaries for conversion, saves,
  package upgrades, migration checkpoints, rollback, acceptance and uninstall.
  Unrelated app contents survive every case. Additional cases cover corrupt
  roots/objects, completely full media, repeated saves, maximum IDs, empty data,
  serial exhaustion, cancellation and interrupted-uninstall siblings.
- An independent NAND counter measured **10,240 programmed bytes** for a save
  preserving a **131,333-byte package**, with zero package-object writes.
  This is one modeled fixture, not a physical write-amplification guarantee.
- `vm/test-sdk-documents.py`: all five signed installed ARM cases passed. They
  cover data-only Close/cold reopen, dirty and clean schema-0 acceptance, signed
  USB upgrade, schema-mismatch write rejection, and a fault after a staged write.
  The initial conversion was seeded using the host-compiled production engine.
- Configured C/source-2 persistence and unchanged Counter/Surface 3D ABI 1
  packages passed. Legacy storage with `--preprovisioned --many-apps` passed
  signed install/readback, icons, normal keys/Goodix launch, cold persistence,
  nine-app shared storage and deletion. The test project's pre-existing lock
  bytes were restored after this run.
- Both firmware targets compiled sequentially. Direct ELF, verified U-Boot and
  protocol smoke passed; summary is in
  `build/prime-g2-native-suite-20260912-024051/`. Existing upstream compiler and
  linker warnings remain. No physical target was flashed or tested.
- Local documentation links, whitespace checks and the public-tree check passed
  (747 public files). The runtime/USB public contract and SDK identity are unchanged.

Final VM ELF SHA-256:
`76d2ad67687a49c20ac5762550d1fcf53bbed7b19728e51e1de7879f8f0e0d63`.
Physical-target binary:
`cb67703cf073c2304cf6ad9e441567bd36fe2544747b2620213c15a44a2358dd`.
QEMU retains the previously recorded identity. All nine source-digest entries
and all five firmware-digest entries in the final ARM report matched. Reports,
logs, captured frames and source/artifact hashes are retained under
`build/sdk-production-documents/` and its `evidence/` directory.

Intermediate failures are preserved: a host-test indentation warning promoted
to an error, a full-media fixture that initially left small-file space, and the
ARM fixture's deliberate package-schema switch without updating its temporary
SDK lock. These test issues were fixed before the final passes. The final code
also rejects cancellation once uninstall has removed the root, even while
object pruning continues. No R0–R6 milestone is complete; no deployment, push
or physical-device operation was performed in this batch.

### Streamed FILE4 files and partial edits

The next batch adds a [production large-file engine](NATIVE-APP-LARGE-FILES.md)
to the same volume. Explicit FILE4 roots retain the old pair format while
distinguishing raw byte stores from bounded indexes. Named-file contents live in
immutable chunks; the 64 KiB ABI 1 byte store remains separate. The internal
engine streams creation/replacement, reads/seeks, partial edits, directories,
rename and deletion. Public descriptors, scheduling, stdio and import/export
remain unfinished; no new capability is advertised.

Final local evidence:

- `make test`: **564 passed, two expected private DTB/DTS skips**, 124.58 s.
  A final six-test storage run subsequently passed, including the added
  FILE4 uninstall-interruption and package-rollback checks.
- Production files passed **630 pre-operation/torn program/erase interruption
  cases**. Production FILE3 transactions retain their separate 512-case matrix.
  Full media, corruption, an unavailable block, cancellation/retry, directories,
  seeks/EOF, byte-store coexistence and abandoned-large-stream recovery passed.
- The **28,795,076-byte** pinned WAD streamed through 2048-byte buffers and
  cold-read to its original SHA-256. A 37-byte partial edit wrote one 130,944-byte
  chunk and programmed **159,744 NAND bytes**, with zero unchanged package
  writes. A separate Python oracle matched the complete edited file.
- The exact prior FILE3 reader, preserved from the previous generated build
  after checking its sealed hashes, rejects FILE4 without NAND mutation. The
  preserved base-revision FILE2 reader rejects both FILE3 and FILE4 in default CI.
- Five signed ARM save/upgrade cases passed with FILE4, preserving a 130,961-byte
  asset's full hash through dirty/clean acceptance, schema mismatch and a fault.
  The file was seeded through the host production engine; this is not a guest
  named-file syscall proof.
- The five ARM memory/pixel/isolation cases passed again. Usable experimental
  app heap remains **8,380,416 bytes**; the kernel heap reserve is now
  **19,818,464 bytes**, reflecting the larger bounded storage state. Heap setup
  took 18/14 model ms. The physical `Volume` symbol occupies 262,088 bytes;
  the host object occupies 262,416 bytes.
- Configured C/source-2 persistence, unchanged Counter and Surface 3D ABI 1
  packages, and direct ELF/verified U-Boot/protocol smoke passed. The smoke
  summary is in `build/prime-g2-native-suite-20260912-031813/`.
- Both targets compiled sequentially. The first VM attempt exposed unavailable
  `memchr`, `strrchr` and `strcpy` functions in the firmware's minimal libc.
  Bounded scans/copies fixed those failures; an intermediate retry still had
  older generated copies. A codec fixture also initially omitted its host
  `<initializer_list>` include. These failures are preserved with the final logs.
  Existing upstream compiler/linker warnings remain.

Final VM ELF SHA-256:
`ff260fae1538d9dabef120be6cd6731331b5ed52961e65a73827b11341168798`.
Physical-target binary:
`d7cecf31f527cabf8ff786c55a03f0d4baf334395b86b2e7954e228d49250132`.
QEMU and SDK identities remain unchanged. Exact reports, sources, artifacts and
logs are retained in `build/sdk-large-files/` and its `evidence/` directory.
Public-tree and local documentation-link checks pass. No hardware operation,
deployment or Git push was performed, and no R0–R6 milestone is complete.

### Foreground scheduling and redraw integration

The VM execution experiment now resumes through a dedicated low-priority OS
event while its native container is active. It preserves the last real input
snapshot and repaints only after surface writes or faults. The shared Prime
event loop keeps key-repeat timing across wakes, preserves single-step D-pad
behavior, and counts dispatch time toward the existing 300 ms UI timer interval.
It coalesces overdue UI ticks after stalls instead of accumulating an unbounded
replay backlog. No hardware timer period, register, public ABI service/event
number or discovery capability changed. See [execution details](NATIVE-APP-EXECUTION-EXPERIMENT.md).

The same signed installed C workload measured **32 yields in 45 model ms**
(38 ms maximum gap, including initial presentation) on the final candidate,
versus **10,810 ms** (361 ms maximum gap) on the preserved prior VM ELF.
An intermediate version repainted each yield and took 1,282 ms; dirty-surface
tracking removed that cost. These are emulator workload measurements, not
physical input latency or Doom frame-rate claims. Continuous yield remains
runnable work; timed/blocked low-power waits still need their own contract.

Final local checks:

- `make test`: **564 passed, two expected private DTB/DTS skips**, 126.88 s.
- `vm/test-sdk-scheduling.py`: passed yield cadence, OK input preserved through
  650 ms of waits, Backspace repeat, held/repressed Right, normal Goodix touch,
  Home cleanup and same-OS relaunch. UI timers fired **12 times in 3,602 model
  ms** while 25,326 foreground wakes completed. Captured frames were inspected.
- `vm/test-sdk-execution.py`: preserved integer/VFP/flags/stack through
  24 preemptions and one yield, with 25 resumes. Infinite-loop Home interruption
  and relaunch passed. Its 1,036 ms Home replay includes deliberate key waits.
- All five memory/pixel cases passed, including guards, non-executable heap,
  allocation failure, saved data and zeroed relaunch. Experimental app heap
  remains 8,380,416 bytes; kernel reserve remains 19,818,464 bytes. Setup took
  20/16 model ms, with physical latency still unqualified.
- Normal input and all **38 ARM isolation/service cases** passed. Preserved
  Counter and Surface 3D packages passed without recompilation. The first
  compatibility invocation omitted its required `--corpus` argument; the
  corrected command used `build/sdk-maturity-corpus` and passed.
- Configured C/source-2 rebuild, signed installation and cold persistence
  passed. All five FILE4 guest save/upgrade cases passed while preserving the
  preseeded named asset, including schema mismatch and faulted Close. These
  exercise byte-store compatibility; they are not guest named-file/stdio proof.
- Both firmware targets compiled sequentially. Direct ELF, verified U-Boot
  and protocol smoke passed; summary:
  `build/prime-g2-native-suite-20260912-035947/summary.json`.
  Existing upstream compiler/linker warnings remain.
- The checked preparation script ran twice without changing any of its five
  already-prepared sources. Source changes remain in the port and preparation
  script, not only in the disposable generated checkout.

Final VM ELF SHA-256:
`f998a6792b85162eb357fce2be59527a678cb28abb55e17d23878ab39c5f2fc8`.
Physical-target binary:
`f52e779c03a8870088811dac4332d2a3f7cee2f5bffdebb68e972dd81a286b9c`.
QEMU and SDK identities remain unchanged. Exact source/artifact identities,
reports, earlier iterations and logs are retained under
`build/sdk-foreground-scheduling/`. Physical firmware was compiled, not flashed
or qualified. No deployment, Git push or milestone completion is claimed.

### Independent snapshot readers

The production volume now owns four independent readers alongside its existing
writer. Each retains only its file's immutable extents, a littlefs file/cache and
position. Collection preserves referenced chunks after replacement, rename or
unlink, then reclaims them after the readers close. Owner-checked tokens reject
foreign/stale handles; remount and explicit cleanup invalidate them. Uninstall
rejects an app with live readers. No storage wire format or public ABI changed.

Reads return a pending result while verifying a newly entered chunk. Each
verification step handles at most 2048 content bytes, retains no caller pointer,
and exposes no unverified output. Open still loads the root/index synchronously;
littlefs metadata/backend operations also need measured latency qualification.
The writer still requires the final output size. Application syscall/lifecycle
integration, growing output, stdio, quotas and import/export remain required.
See [file-reader contracts and limits](NATIVE-APP-LARGE-FILES.md#transactions-and-readers).

The host fixture streamed and transformed **261,925 bytes** from an open input
while writing another file, cold-reopened the output and checked every byte
against the independent pattern. It also exercises independent positions, four
reader exhaustion, namespace isolation, stale handles, close during verification,
seeks/EOF, corrupt unread chunks, replacement/rename/unlink visibility and
reclamation after close. The cross-chunk interruption matrix now holds an old
snapshot through the patch, and full-media failure preserves an open reader.
The pinned **28,795,076-byte WAD** also passed the new reader, matching its
original SHA-256 after **14,294 bounded verification steps**. The independent
whole-file oracle for the partial edit still matches with 159,744 NAND bytes
programmed and zero unchanged package bytes written.

The host `Volume` is **378,464 bytes**, including four 29,000-byte readers; the
physical-target volume symbol is **377,992 bytes**. The VM memory proof reports
**19,703,776 bytes** reserved for the kernel heap and the unchanged **8,380,416
bytes** of experimental app heap, with 19/17 model-ms heap setup. All five
allocation/guard/pixel cases pass. The earlier FILE3 host fixture placed many
large volumes on its test stack; the increased size exposed an ASan stack
overflow. Its 23 volume instances now use host heap ownership, preserving all
assertions and sanitizer instrumentation. Production storage remains static.

Final candidate VM ELF SHA-256:
`7ac9e27a00e8c2b4492ffae334eaee2cea6020f9cd98e55c861a3349377b79d8`.
Physical-target binary:
`d15027f154512f253d99ae006d8c845b88688847b9184043d92e06b2818400c2`.
Both targets compile sequentially with the existing upstream warnings. Exact
logs, final validation results and source/artifact hashes are retained under
`build/sdk-file-snapshots/evidence/`. These internal host readers are not a guest
file syscall or playable Doom proof. No physical operation, deployment, Git push
or milestone completion is claimed.

Final checks: `make test` passed **564 tests with two expected private DTB/DTS
skips**, 127.66 seconds, including the 630 FILE4 and 512 FILE3 interruption cases.
The five signed FILE4 ARM save/upgrade cases passed while preserving the seeded
asset; these still exercise guest byte-store services. All five memory/pixel
cases, unchanged Counter/Surface 3D ABI 1 packages, and direct ELF/verified U-Boot/
protocol smoke passed. The final VM was rebuilt after adding noncopyable reader
ownership. Earlier preliminary build/test logs and the diagnosed fixture stack
overflow are retained separately from these final results.

### Growing files, append and backpatches

The internal writer now accepts output without a declared final size, supports
truncate/update/append modes, reads its own staged contents and supports random
seeks/backpatches. Writes past EOF materialize zero-filled gaps; seeking alone
does not extend a file. Four committed snapshot readers remain usable during
the write. A new root atomically publishes the final namespace and file contents.
No storage format, partition, public ABI or capability bit changed.

A single **130,944-byte** chunk cache shares memory with the final index wire
buffer. Content loading, zeroing, programming and readback verification advance
in 2048-byte steps. Rewrites reuse a chunk's part number only within the current
uncommitted generation. This avoids exhausting the 512-part bound during repeated
backpatches while preserving committed objects. Admission checks actual space
and index/metadata headroom before each flush and before publication, preserving
all 24 maintenance-reserve blocks from growing user output. Open/index
loading and admission traversal remain synchronous; physical privileged latency,
per-app quotas and complete recovery headroom qualification remain open.

Fresh host evidence includes:

- **718 additional interruption cases**, covering growing output with header
  backpatching and extension of an existing file with a live old snapshot.
  The earlier 630 FILE4 and 512 FILE3 cases also pass.
- A **261,925-byte** input produced **261,932 bytes** of variable-length output
  while remaining open. The cold output matched an independent Python oracle:
  `dc8b637fd01afaf5634fd712b511d88bdd6b651e59b5edf6478e2b02994dd2c0`.
- Append after seek, zero-filled gaps across chunks, staged readback, size/EOF
  limits, empty files, namespace errors, cancellation/retry and **520 rewrites**
  of a staged 37-byte chunk passed. The rewrites programmed 19,240 object bytes
  without changing the old reader's contents.
- Full-media growth accepted **59,972,352 bytes** before its flush failed with
  no space. The transaction published none of that output, preserved committed
  files, admitted a maximum-size package upgrade and compatible rollback, and
  allowed a smaller retry after orphan collection. Accepted RAM writes
  are not durable until the root commit succeeds.
- The pinned **28,795,076-byte WAD** was written using the growing API without
  passing its length, then cold-read through the snapshot reader to its original
  hash. The partial-edit oracle still matches, with 159,744 NAND bytes programmed
  and no unchanged package bytes rewritten.

Final `make test` passed **564 tests with two expected private DTB/DTS skips**,
140.24 seconds, including the independent output-hash assertions and maintenance
reserve checks. All five signed FILE4 ARM save/upgrade cases
and all five memory/pixel cases pass on the new VM. Those guest storage tests
still exercise byte-store services; the growing file workload runs against the
host-compiled production engine, not guest stdio.

The host volume is **468,456 bytes** and the physical-target volume symbol is
**467,976 bytes**. VM kernel heap reserve is **19,621,856 bytes**, with the
experimental app heap unchanged at **8,380,416 bytes**. Heap setup measured
19/21 model ms. Both targets compiled sequentially with the existing upstream
warnings. VM ELF SHA-256:
`5cc75e1fd5bf1b94073a318e614b42cc0e3351cab1443c0e59e725b929a91940`.
Physical-target binary:
`cc2d2e99754d0bc8c8040e6be647425479a36bcc7e427a689dc0983ce03b6b39`.
Exact sources, reports and build/test logs are retained under
`build/sdk-growing-files/evidence/`. Physical storage and timing remain
unqualified. No deployment, Git push or SDK 1.0 milestone completion is claimed.

Final review changed the shared storage to one byte array and tightened reserve
admission. The larger zero-initialized volume exposed an ASan stack overflow in
the older migration/icon fixture; its 19 large volume instances now use host heap
ownership, preserving all assertions, legacy-bank fixtures and sanitizers.
Earlier logs, that failing scoped run and the final reruns remain in the evidence
directory. Production storage allocation remains static.
Unchanged Counter and Surface 3D ABI 1 packages and direct ELF/verified U-Boot/
protocol smoke also pass on the final candidate. Public-tree and documentation
checks pass, including 90 local links/anchors. The complete SDK 1.0 release gates
remain open.

### Authenticated file sessions and ARM stdio

Service 10, API revision 2 and capability bit 8 now expose app-private files.
The firmware, SDK packer and candidate website readers agree on API 2/features
15 while retaining ABI 1 and its existing memory, signature and byte-store
contracts. The asynchronous service compiles into both targets; conventional
newlib waits still use VM-only execution services.

The session captures authenticated app identity and committed private data,
copies request paths/write buffers and owns four snapshot readers plus one
writer. Requests carry generation tokens, transfers are limited to 2048 bytes,
and completion-buffer retries do not replay mutations. Storage advances outside
the syscall. Home/fault cleanup aborts unclosed staging, drains work past the
commit point and excludes installer/catalog work until ownership is released.
Atomic rename replaces an existing destination while preserving old readers.
See [the public experimental contract](../sdk/FILES.md).

The signed ARM stdio proof writes and processes a **261,925-byte** input with
simultaneous input/output streams, seeks to backpatch a header, checks close,
atomically replaces the destination and reopens it after a cold boot. Export
from the actual synthetic NAND matches an independent Python oracle: **261,932
bytes**, SHA-256
`dc8b637fd01afaf5634fd712b511d88bdd6b651e59b5edf6478e2b02994dd2c0`.
Four same-OS relaunch cases pass for Home, deliberate fault, `exit(7)` and normal
return. Newlib can close and commit files before a nonzero exit reaches the OS;
that exit discards staged private bytes but does not undo completed file commits.

Validation on this candidate:

- Full host suite: **566 passed, two expected private DTB/DTS skips**, 143.31 s.
  FILE4 now exercises **648 interruption cases**, including 18 for replacing an
  existing destination, plus the separate 718 growing-file cases. FILE3's 512
  interruption cases remain passing.
- Signed ARM file proof: two cases; lifecycle: four cases; isolation: 38 cases;
  FILE4 byte-store/save/upgrade: five cases; memory/pixels: five cases. All pass.
  Schema negotiation/rejection, unchanged Counter/Surface 3D binaries and
  direct-ELF/verified-boot/protocol smoke pass.
- Both firmware targets compile sequentially. VM ELF SHA-256:
  `2352761f5183ccc40472a22dba5c0e769b36dbf76c2bccbafe88d9e0d1f23b3a`.
  Physical BIN SHA-256:
  `8d2cfd85e42ab8cb7c8b2bf919c7f966fe502206f4355a7c4cd9e120952ccde1`.
- Candidate website build/lint and 166 scoped tests pass. The full suite passes
  with `npm test -- --maxWorkers=1`: **401 passed, one skipped**, 51.56 s.
  Default parallel runs failed on five-second timeouts: first two failures,
  then seven across varying recovery/firmware cases. Serial success suggests
  contention sensitivity; it does not establish a fixed default test command.
  The skip needs `LEFONY_SDK_TEST_PROJECT` for a real-build store journey.

Evidence and source snapshots are retained under
`build/sdk-file-sessions/evidence/`. The ARM reports' recorded source hashes
match the reviewed working tree. These checks qualify the stated local proofs;
they do not complete R2, physical acceptance or the four proving applications.
Earlier dated sections retain evidence for their earlier candidates.

### Public foreground runtime and file waits

API revision 3 and capability 16 now select foreground profile 1 explicitly.
Public services 11/12 implement entry, yield, monotonic sleep, exit, memory/frame
queries and copied RGB565 presentation on both firmware targets. Existing ABI 1
packages keep their callback behavior and original limits. Firmware, SDK and
candidate website readers agree on API 3/features 31. See [the runtime contract](../sdk/FOREGROUND.md).

Heap entry clears 64 KiB per deferred foreground event across 128 blocks before
mapping any user pages. The 8 MiB reservation has two 4 KiB guards, leaving
8,380,416 app bytes. The final VM reports 19,621,856 bytes of OS heap capacity;
the physical link map leaves 21,882,880 bytes. These are available address ranges,
not measured free memory or integrated application peaks. The physical build
reserves this memory even for legacy apps. The session object remains 2,480 bytes.

The signed ARM foreground suite passes eight variants: state/request validation,
allocation and register preservation, undeclared capability refusal, Home during
a CPU loop/long sleep, pre-entry isolation, both heap guards and non-executable
heap. The ordinary workload allocates 6 MiB, preserves realloc input on failure,
checks a minimum 500 ms sleep and retains integer/VFP state and recursive stack
canaries across 33 preemptions, four yields and 38 resumes. Heap setup took 84
modeled milliseconds in this run. The copied quadrant frame was also inspected
after the app cleared/freed its source buffer. Same-OS relaunch verifies zeroed
memory. Home replay's 1,031/1,032 ms includes deliberate host key waits and is not
physical input latency.

The first two preliminary foreground runs failed at a generic assertion; that
helper obscured which source assertion failed. A later helper emits unique UDF
immediates/source locations. Source review independently found sleep deadlines
using a coarser IRQ clock than the public millisecond clock, allowing an early
wake; the final candidate uses the public clock consistently. The exact cause
of the initial generic assertions was not established. Failing logs and the
pre-correction passing candidate remain retained separately.

The real newlib file adapter now yields through public service 11. The two signed
stream/backpatch/cold-output cases and four exit/Home/fault lifecycle cases pass
on this candidate. The independent output remains 261,932 bytes with SHA-256
`dc8b637fd01afaf5634fd712b511d88bdd6b651e59b5edf6478e2b02994dd2c0`.
Completed closes can survive nonzero newlib exit; uncommitted private bytes do
not. Default SDK builds still use callbacks, and these fixtures supply their own
main wrappers. A reusable startup and qualified libc profile remain required.

Validation on the final candidate:

- Full host suite: **567 passed, two expected private DTB/DTS skips**, 149.11 s.
- Both firmware targets build sequentially. VM ELF:
  `846c594e6a9a3bd8506713fe00f9ca3377fba3066283bf42a9d746c68f8d303c`.
  Physical BIN:
  `303a40d1ab1cf9f59ee90b2cb88a67020f25b535ec250c5994c89ab1e3fc9128`.
  Existing upstream linker warnings remain.
- Eight public foreground, two stdio, four lifecycle, five legacy memory/pixel
  and 38 isolation ARM cases pass. Unchanged Counter/Surface 3D packages and
  direct-ELF, verified-boot and protocol smoke pass.
- Seven current-loader/USB contract cases pass. The optional pre-schema-1
  loader check is **skipped** because no `--old-firmware` was supplied; its
  console message/report now state this rather than claiming it ran.
- Website build/lint and 167 scoped tests pass. Full suite with
  `npm test -- --maxWorkers=1`: **402 passed, one skipped**, 39.60 s. Previous
  default parallel timeouts remain unresolved; this is a qualified one-worker
  result. The real-SDK store journey still requires `LEFONY_SDK_TEST_PROJECT`.
- Whitespace checks pass in both repositories; 174 local links/anchors across
  13 documents and the public-source boundary (775 files) pass.

Exact candidate artifacts, selected source snapshots and logs are retained in
`build/sdk-foreground/evidence/`. Older API 2 evidence remains unchanged under
`build/sdk-file-sessions/evidence/`. This candidate does not establish a working
Doom port, final developer bundles, physical performance/durability or completion
of any R0–R6 milestone. No physical device operation, deployment or Git push has
been performed in this batch.

### Conventional main developer workflow and minigzip

The reusable `foreground-newlib-1` profile now runs ordinary C and C++ main
through the public API 3 loader. Project schema 2 carries explicit runtime and
bounded mutable arguments. The builder supplies preinit/init/fini handling,
normal/failed exit, the pinned newlib sysroot and app-side file adapters; old
project schemas retain callback semantics. Dependency locks verify libraries,
all 134 headers, the source pin, compiler and license notice. The source-kit
packager can include the complete newlib archive, sysroot and notices.

This work exposed and fixed three ordinary-developer gaps:

- The fresh C template's relaunch failed while the native app container remained
  active. Replay now sends normal Home/release, waits up to ten seconds for
  installed storage, and reloads/reopens the app. Raw callback previews reload
  their original package, so globals reset too. Tests cover both callback modes
  and a foreground program returning 7, with explicit exit-status assertions.
- Installed foreground main could run before GDB attached. Debug setup now
  defers app launch until the breakpoint can be installed, and selects `main`
  for the conventional profile. The actual GDB test inspects arguments/source,
  steps an instruction and completes the app after detach. Legacy callback
  debugging and fault reporting remain passing.
- Newlib headers shadowed GCC's compiler-owned headers and broke zlib's C11
  atomic initialization. The foreground build now uses GCC's builtin/fixed
  headers first, then the verified newlib sysroot, with ambient target includes
  disabled. This fixes the shared compiler integration without editing zlib's
  compression library or claiming general multithreaded support.

Earlier main integration selected full newlib reentrancy after the small
configuration failed plain-C atexit cleanup. C++ had pulled in optional metadata
and concealed that failure. The full configuration builds reproducibly in two
fresh canonical temporary paths; all headers and both archives match. Candidate
libc SHA-256 is
`e5d4afe891e0567c49d6fd3059f125dc3f49132c6f35d540f42f56c30f848174`;
libm is
`4cec00e655a619cddc8eeeb451249785d1ce9677375dbf1bdf5ddb2cf16c2b5a`.
The newlib/Picolibc comparison and broader function qualification remain open.

The [non-game C consumer](../sdk/ports/minigzip/README.md) is now the existing
minigzip utility from zlib **1.3.2**, using its published source archive digest
and a per-file allowlist. This replaces the earlier unselected 1.3.1 research
candidate; it does not change firmware's upstream pin. All compression-library
sources remain unchanged. The utility has marked changes for temporary-output
commit and atomic replacement, checked removal and immediate deferred-read
error handling. GCC C11 atomics build its CRC tables in app memory, omitting the
unused 591,749-byte precomputed header from source exchange.

Nine signed ARM cases pass: missing input, large compression, cold decompression
across a package update, a host-produced gzip, truncated and corrupt input, an
identical-package corrected-input retry after each failure, and rejected path
traversal. Input is **262,176 bytes**, SHA-256
`409e413a940da463d45a0c43f55860a09673ed1a48c88e5c39ec12a49570a878`.
The compressed file also exceeds 64 KiB. Host decompression and exact-byte
exports verify useful output. Failed input retains both the source and previous
destination. Corrected retries accept the pending update and allow the following
version; a failed first run is not permission to discard recovery state.

Unmodified upstream minigzip also returned zero on the host for a missing gzip
trailer. The final adaptation checks `gzerror` after each read, before a later
call can clear the recoverable status. Native host checks cover five truncation
lengths and valid input. An initial host test used overlong absolute paths and
did not reach decompression; that report is marked invalid evidence and the
corrected relative-path tests assert the actual unexpected-EOF error. Earlier
ARM failures are retained, including the pending-upgrade rejection that led to
the identical-package retry scenario. No failed result was reclassified as a
successful qualification.

The compression candidate has **81,680 code bytes**, **11,976 static-data bytes**
(including 1,748 initialized bytes), a reserved 64 KiB stack and no embedded input
asset. Heap and stack peaks remain unmeasured. Input/output are streamed through
the public file API; the test helper only prepares and exports offline synthetic
fixtures using the production storage engine. This is not a finished data-import
interface or general gzip CLI. Full-media/allocation acceptance and physical
testing remain required before the non-game proving app is complete.

Validation for the final SDK source candidate:

- `make test`: **573 passed, two expected private DTB/DTS skips**, 185.73 s.
- Four main/initializer/exit/cold cases pass with the final compiler-header order.
  Five developer cases cover main GDB, negative exit checks and raw/installed
  callback relaunch. The existing developer-loop suite passes callback GDB,
  workspace persistence/export/restore and symbolized fault handling.
- The deterministic **319-file** source kit passes external CMake, disposable
  preview, cold saved visits and minigzip preparation/build/source generation
  using its bundled runtime. Archive SHA-256:
  `0b330db195bcca1059eac3f77afee1ca7c4b9114e26184f16406867c2a30e33f`.
  Minigzip's source-format-2 extraction reproduces the exact ARM image.
- Website source/manifest readers retain their API 3/project-2 behavior. Its
  candidate developer documentation now explains the main profile and port
  workflow. The optional real-SDK store fixture also passes for the prepared
  minigzip project, including exact uploaded-byte preservation through mock
  signing. No live submission or website deployment is implied.
- All 136 local links in the eleven touched documents resolve; both repositories
  pass `git diff --check`, and `make check-public` passes its 800-file boundary.
- VM ELF is unchanged in this batch:
  `95b7bcdcdb2c8b61d5dfe4106ca28af3a9552797addb079a45376dd7bbaf9d84`.
  QEMU remains
  `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
  No firmware source/build, physical device operation, commit or push was part
  of this batch. Qualification uses macOS ARM64 and the ARM emulator.

Reports and logs are under `build/sdk-main/`, `build/sdk-minigzip/` and their
adjacent logs. Selected exact inputs and artifacts are retained under
`build/sdk-main/evidence/`; earlier foreground/file-session evidence is preserved.
The full goal remains active, with no R0–R6 milestone declared complete.

### Public input stream and held-key replay

The next candidate adds API revision **4**, feature mask **63**, and service 13
at explicitly declared capability **32**. The 480-byte C/C++ reply combines
current held keys and touch state with up to eight ordered key/touch events from
a 32-event queue. Ten-millisecond per-key stability filtering observes the normal
OS scan before logical chord selection. No peripheral access moves into apps;
the existing driver, logical event/repeat behavior and service-8 layout remain.
This is sampled input, with documented limits for changes between scans.

An overflow returns the current state and discards the incomplete backlog with
an explicit dropped count. Focus resets suppress already-held launcher keys
until release/repress and clear old events/contacts. Home, Apps and power remain
OS-owned; existing navigation depth opts into Back. Sleep/preemption retain the
queue. SDK replay now supports explicit held-key sets and releases them on exit.
The website's shared contract reader accepts API 4, with older device rejection
still preceding upload. No deployment/download change is implied.

Validation:

- Signed installed **ordinary C** ARM input passes held Left+Right, no extra down
  while held, independent releases, Shift+Left, app-owned Back, two stable touch
  IDs, contact cancellation/up, Home and same-OS relaunch. During a ten-second
  sleep, **44** key/touch events were discarded at overflow; the app recovered
  the current held Right state. Relaunch while Right stayed held produced no
  inherited press, then exactly one fresh down after release/repress.
- Real SVC checks reject undeclared capability, invalid pointers, undersized
  buffers, version and reserved words. Failed requests do not consume the first
  focus-reset notification. The separate undeclared-capability C app exits zero.
- `make test`: **580 passed, two expected private DTB/DTS skips**, 279.07 s.
  Queue tests run under sanitizers and cover partial FIFO reads, debounce,
  overflow, focus isolation, clock wrap and 5,000 randomized
  chords. Physical key constants match the authoritative map.
- Legacy service-8 key/text/modifier/two-contact input passes. Foreground
  scheduling passes 32 yields in **47 modeled ms**, maximum gap **40 ms**, and
  **14 UI timer ticks / 4,220 modeled ms**, plus repeat, Home and relaunch.
  These measurements are model regression checks, not physical latency/FPS.
- Current loader/USB/schema/malicious-host rejection regressions pass. The
  retained API 3 ELF also rejects API 4 requirements and required input bit 32.
  The separate pre-schema-1 ELF test remains skipped without its explicit input.
- Website: **419 passed, one optional real-SDK fixture skipped**; build and lint
  pass. Its new manifest test separately rejects API 3 and missing bit 32.
- All 93 local links in the eight changed API/status documents resolve, both
  repositories pass `git diff --check`, and the public boundary passes 808 files.
- The **322-file** bundled-runtime kit passes deterministic packaging, relocated
  CMake, cold saved visits, minigzip source/build and an external C input-stream
  main with exit/relaunch assertions. A final documentation-only repack removes
  a repository-only link; every other archive member except checksums is
  byte-identical to the tested kit. Final archive SHA-256:
  `bdbcd9868c8dd608c1585e1418ce849271afab11e11c132dd308cbd457b9f6d1`.
- Both firmware targets compile sequentially. VM ELF SHA-256:
  `501abb1fd60d8afcc66a5c4cb54106664340d0451f34e85e634a1c209cea8e7e`.
  Physical BIN SHA-256:
  `8995689fa449d355d448d9951990ab50d29f05467551ee36bfb8c4653367461d`.
  The initial VM build failed because the firmware's minimal header lacks
  `UINT32_MAX`; the bounded counter now uses an explicit uint32 constant.
  The initial probe's undeclared variant failed an unused-code warning, corrected
  before the complete passing run. Both failed logs are retained as failures.

Reports, exact artifacts, selected source snapshots and logs are retained in
`build/sdk-input-stream/evidence/`. Earlier main/minigzip and foreground evidence
is preserved. Physical key/touch feel, integrated workload limits, native host
qualification and the remaining proving apps still need acceptance. This does
not complete any R0–R6 milestone. No device operation, deployment, commit or push
was performed in this batch.

### Doom integration and research refresh

The public-API Doom adapter and checked preparation script now produce a real
ARM application. An earlier image runs Freedoom E1M1 using streamed FILE4 data,
normal KPP keys and copied pixels. Inspected frames show gameplay/menu state,
changed views and ammunition decreasing from 50 to 47. The 28,795,076-byte WAD
matches its pin. The current script also adapts failed save close/atomic rename
and the normal Quit path; those later changes do not inherit the earlier pass.

The stronger gameplay/save/load/cold test failed in the 120-second USB install
completion wait after the commit request. It never reached main/GDB or gameplay
assertions. Its log and synthetic workspace remain under `build/sdk-doom*`;
the catalog/root outcome requires reconciliation before another write. Earlier
successful image hash:
`f54fa57270dfd2bb773bb811f509b3e62045e491ccbdfcd0495872323d19ff69`.
Current unqualified image hash:
`aa3b6e7f976001189a482b96d43d47329049d19d8b455439a5f8ede5762e2405`.
No Doom save/load, current clean-quit, heap/stack peak or physical result is
claimed. Both images use the API 4 firmware recorded above.

Shared SDK path handling now accepts bounded leading `./` prefixes and a
mkdir-only trailing slash. The matching ARM stdio/cold-output proof passes.
SDK workspace cleanup now sends Home, checks that the native container was
left and drains storage. A matching owned-Back test passes with saved counts
1 and 2 across cold boots. The earlier weaker Back test did not establish this
cleanup behavior; the final explicit state assertion is the relevant evidence.

Fresh research validation passes **120 SDK host tests** and **206 website
contract/device/store tests**, with one optional real-SDK fixture skipped.
All 440 input-stream and 906 main/minigzip sealed artifact/source entries match
their recorded hashes. These integrity checks preserve the original candidates;
they do not requalify old binaries against current source. No firmware rebuild,
physical operation, release, deployment, commit or push was performed for the
research refresh. See [findings, exact checks and remaining acceptance](NATIVE-APP-SDK-IMPLEMENTATION-VALIDATION.md#15-doom-integration-and-validation-refresh-2026-09-12).

### Doom save/cold reload and approved MIT alternative

The failed large-data update was reconciled using the production root inspector:
the old package/data pair remained intact with no pending upgrade. A clone
reproduced the timeout on the unchanged API 4 ELF. The event loop slept 10 ms
between 2 KiB verification steps; the WAD needs 14,294 steps. Pending storage
work now runs without that idle sleep, after normal input scanning, while UI
timers continue. Transfer bounds, hashes, signatures and timeouts are unchanged.

Both targets compile. The full host suite passes **580 tests with two expected
private-fixture skips**. Scheduling, API 4 stream and legacy input regressions
pass. The strong Doom test passes normal-key movement, turning/firing, menus,
saving, restoring after movement, clean quit, cold restore and a second clean
quit. Its 61,342-byte save remains identical across the cold launch. Read-only
GDB observations establish restored position/angle/ammunition; no game-state
writes or direct game-function calls drive the test. Observed maximum sbrk
extent is 6,643,712 bytes, not a stack or live-allocation peak.

The owner explicitly approved MIT as an alternative for the twelve original
app-side files and startup-argument template in the [license review](NATIVE-APP-LINKED-LICENSE-REVIEW.md).
That grant is applied, the original alternatives remain, and the generated
startup file includes the complete MIT notice. Newly prepared Doom source has
GPL/MIT/component notices; its rebuilt executable is byte-identical to the
strong gameplay candidate. Firmware and third-party terms are unchanged.

VM ELF: `c35211650212ca9227b1b27c49bb20decd764efd3848669a1ae26fb17dd65110`.
Physical BIN: `4796f63db57854945d1f3b0acd633a25e3cf3e4cf426d9893b3622072423d6d9`.
Doom image: `aa3b6e7f976001189a482b96d43d47329049d19d8b455439a5f8ede5762e2405`.
The 887-entry pre-grant batch is sealed at
`build/sdk-doom/evidence-gameplay-pregrant/`. See [exact commands, hashes and limits](NATIVE-APP-SDK-IMPLEMENTATION-VALIDATION.md#16-doom-savecold-reload-storage-scheduling-and-license-grant-2026-09-12).

Doom-specific full-media/interrupted saves, configuration-error checks, complete
control coverage, frame/stack/OS peaks, user WAD import, corresponding-source
qualification and physical acceptance remain open. No R0–R6 milestone is
complete; no physical operation, deployment, commit or push occurred.

The final Doom source-export check found and corrected a preparation-log path
outside the source notice allowlist. The recipe emits `notices/port.txt` and
retains the existing format limits. Its 200-file source bundle rebuilds with a
relocated 332-file SDK/newlib kit to the exact gameplay image; every kit checksum
and the MIT/newlib notices verify. SDK archive SHA-256:
`3f2be541b343810c2dfa785f0032e49dd0dcf01f3f4c6ea041c6c61839312189`.
The final documentation/embedded-license-note repack is
`ef2bab2324403792bf2ca084b99129dc899833f8805e2124b8489115f90dcbb6`;
archive comparisons verify identical executable build inputs and all 332 hashes.
The changed kit documents have no unresolved local links. Preserved Counter
and Surface 3D ABI 1 packages also pass on the new firmware without rebuilding.
The broader smoke suite initially failed opening Calculation after verified
boot; an unchanged rerun passes direct boot, U-Boot/input and protocol. Both
results are preserved; the intermittent failure's cause is not established.

## API 5 live file sync — 2026-09-12

The authenticated file session now accepts additive operation 11 (`SYNC`),
requiring declared capability 64. The unchanged 64-byte wire request commits
the writer through the existing FILE4 root transaction, then reopens the saved
version while preserving the handle, position and append mode. Existing snapshot
readers retain their original contents. Home, fault and immediate exit discard
only subsequent staging. Errors invalidate the writer; a commit that completed
before a reopen failure is not undone. Public private-byte checkpoints and
multi-file transactions are separate work.

The newlib adapter supplies `fsync`, using discovery to return `ENOSYS` on older
firmware. An undeclared sync feature returns `EACCES`. The SDK, firmware and
website readers agree on API revision 5 / feature mask 127. A conventional
main/file/sync app requires API 5 and mask 88. Existing package schemas,
signatures, storage geometry and trust roots retain their meanings.

Validation for this candidate:

- `make firmware-vm` and `make firmware` pass. VM ELF SHA-256:
  `eba930aee3c40ebb7beb0402dd67adbc899e7e88590b699ea4359d8631b33a53`;
  physical BIN SHA-256:
  `79fe5cb28455d1b8f7d5895e0bd0ee9280e67a896e22f444017abd8d4322824b`.
- The full host suite passes: 581 tests, two expected private DTB/DTS skips and
  280 subtests. The final focused session fixture additionally checks sync I/O
  failure, retained position beyond EOF and cross-chunk edits. It covers
  repeated saves, append, snapshot isolation, stale handles and 44 clean/torn
  synthetic NAND interruption points. Every acknowledged sync survives;
  interrupted unacknowledged operations recover a complete old or new file.
- `vm/test-sdk-file-sync.py --old-firmware` using the retained API 4 ELF passes
  eight installed ARM cases: Home/fault/immediate-exit plus cold reopen for each,
  undeclared capability, and `ENOSYS` on older firmware. Cold launches use the
  identical signed app bytes. The intentional fault is matched to its exact
  instruction address, and an independent host export verifies all 8,197 saved
  bytes: SHA-256 `4ba3b4fd7af9c4294e31448d9157284e87f47b3163dcfe16eca0438e4f0989e9`.
- Contract validation passes 11 loader/USB cases including retained API 3/4
  refusal, malicious-host rejection and preservation of the installed app.
  The pre-schema-1 loader case was explicitly skipped without that older ELF.
  The native SDK isolation/service regressions pass on the new VM ELF.
- Website contract/device tests pass (185 tests); production build and lint
  pass. Public-tree and whitespace checks pass. Matching website readers and
  SDK documentation are local changes, not deployed downloads.

Reports and artifacts are under `build/sdk-file-sync/`; command logs are
`build/sdk-file-sync-*.log`. QEMU SHA-256 remains
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The initial ARM harness exposed the strict-C11 `fileno` feature-test requirement;
the proof and documentation now specify `_POSIX_C_SOURCE=200809L`. The harness
also now preserves identical package bytes across cold launches and recognizes
only the explicitly expected fault. No physical operation, deployment, commit
or push occurred. Index/admission latency, full-media application behavior,
flash endurance and physical power-loss qualification remain open.

## API 6 directory and usage queries — 2026-09-12

`LIST` and `SPACE` extend the existing asynchronous file session with declared
capability 128. Both use the authenticated app namespace and copied replies.
Directory pages contain at most 16 immediate children with full app-relative
paths; retained root generations detect commits between pages. A changed root
returns `CHANGED` without silently mixing versions. Current uncommitted output
does not appear in the listing. Invalid completion buffers preserve the reply
for correction. Legacy byte-store apps can inspect their empty named namespace
without conversion or flash writes.

Usage reports distinguish committed named/private/package bytes and counts,
open-writer lengths, shared physical allocation, available capacity and excluded
reserve. Snapshot/recovery/staging overhead is not mislabeled as logical data
or guaranteed allocatable space. The runtime helpers `lefony_file_list` and
`lefony_file_space` provide errno/yield integration. A main/file/catalog app
requires API 6 and mask 152; older firmware returns `ENOSYS` and an undeclared
catalog capability returns `EACCES`. The SDK, firmware and website readers agree
on API revision 6 / feature mask 255. The file request and storage formats retain
their previous layouts; no new storage migration, package schema or trust root
is introduced.

Validation:

- Both firmware builds pass. VM ELF SHA-256:
  `c41ac7ad3c97bb340040e5de34d7d5cb96689bc88b078c87f79d703efb459702`;
  physical BIN SHA-256:
  `39a86fce69412b4915b31f08f48a12640c18815c304d2feed2b979184e3877dd`.
- 110 targeted host tests pass, including the production storage/document
  interruption suites, authenticated file sessions, catalog ownership and
  runtime/package compatibility. The new sanitizer fixture verifies nested and
  multi-page listings, zeroed unused entries, committed/staged accounting,
  generation changes, malformed paths/cursors, corrected poll buffers,
  namespace isolation, cold reads and read-only schema-mismatch inspection.
  The full host suite then passes with 583 tests, two expected private DTB/DTS
  skips and 280 subtests.
- `vm/test-sdk-file-catalog.py --old-firmware` with the preserved API 5 ELF
  passes four signed installed ARM cases: initial operation, identical-package
  cold reopening, undeclared capability and older-firmware fallback. The initial
  case enumerates more than one page, checks usage during a writer, detects a
  changed root, and rejects kernel/code-memory output pointers before retrieving
  the same result with a valid buffer. A host export checks the nested file.
- Loader/USB validation passes 13 cases including retained API 3/4/5 rejection,
  future requirements, malformed packages, malicious-host rejection and cold
  preservation of the installed app. The pre-schema-1 loader case remains an
  explicit skip without that older ELF.
- Website contract/device tests pass (186 tests); production build and lint pass. Matching
  headers, user documentation and website requirement readers remain local
  development changes. Public-tree and whitespace checks pass.

Evidence is under `build/sdk-file-catalog/`, with command logs at
`build/sdk-file-catalog-*.log`. QEMU remains
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
Index loading and allocation traversal still execute synchronously within OS
polling; physical latency is unqualified. Per-app quota policy/enforcement,
import/export, migration/recovery controls and the remaining UI/connectivity/
publishing work are still required. No physical write, deployment, commit or
push occurred, and no SDK 1.0 milestone is marked complete.

## Next implementation dependencies

Complete the libc comparison and supported function matrix around the integrated
ordinary main/newlib profile. Its file waits, cleanup, external debugger and
bundled-runtime developer journey have ARM evidence. The pinned minigzip consumer
now passes actual streaming and malformed-input/retry cases; complete broader
resource/error, user-data exchange and physical qualification, and use the same
public descriptors for the WAD. Complete private-byte checkpoint,
migration/recovery controls and import/export. Bound or measure synchronous
index loading and allocation traversal; short content transfers alone do not
prove a latency bound. Doom's prepared save path now checks close and atomic
replacement; success and cold restoration pass. Complete application-level
error/recovery cases with large retained app data.
Integrate the source-2 readers into the final coordinated SDK/website release
before enabling C publication from downloaded bundles.
Complete broader blocked-wait cases, Doom error/resource acceptance and
physical frame pacing. Authoring, account publication, connectivity and the remaining
apps converge on these same interfaces; all R0–R6 requirements remain tracked.

## API 7 per-app quotas — 2026-09-12

The file engine now enforces a fixed development quota of 32 MiB of current
mutable data per app, including private bytes. The measured pinned Doom WAD and
current saves fit this limit. Signed packages, retained roots/readers and staged
copies continue to use the separate shared-space and maintenance-reserve checks.
This policy does not reserve capacity for an app. Existing oversized FILE4 roots
are preserved and may be edited or shrunk without growth; the next transaction's
ceiling follows each committed shrink toward the ordinary limit.

Known-length files and private checkpoints check allowance before writing;
streaming growth, append and sparse gaps use the same accounting. Short writes
may reach the limit, followed by `EDQUOT`. A failed public writer aborts its
uncommitted replacement. The new 48-byte QUOTA reply separates committed and
projected usage, policy limit, transaction ceiling and remaining logical bytes.
It also identifies failed staging and oversized existing roots. Read-only legacy
and schema-mismatch inspection does not convert data. API 7 / feature mask 511
is coordinated across firmware, SDK and website readers; existing package,
request, SPACE, storage and USB formats are unchanged.

The ARM failure/reopen journey exposed a pre-existing file-session bug: the
writer's retained failure flag incorrectly rejected a snapshot reader's pending
verification. Reader waits now depend on their own handle type. A production
host regression covers opening and reading the committed file after an aborted
quota-limited writer. This fix also applies to other writer failures.

Validation on the final candidate:

- Both `make firmware-vm` and `make firmware` pass. VM ELF SHA-256:
  `c6d9e7abad2d432a7350f895e6a2317ffcb15062b9ff969df460dd7967d1fb37`;
  physical BIN SHA-256:
  `0873b22562d7c83b0c5f67a45d8b6fe44721fe8b7bd580fd76e153d4700e559e`.
- Full host suite: **585 passed, two expected private DTB/DTS skips**, 168.87 s.
  The sanitizer quota fixture seeds real hashed oversized FILE4 chunks and checks
  cold read/edit/shrink, private-byte accounting, declared-size refusal before
  writes, exact growth boundaries, partial-write abort, sparse-gap refusal,
  live sync, independent readers, app isolation and read-only schema mismatch.
  Existing interruption/recovery tests pass. The full-media writer test now uses
  two apps so it continues to reach physical `ENOSPC` before either app's quota;
  maximum package upgrade and compatible rollback still pass at that boundary.
- `vm/test-sdk-file-quota.py --old-firmware` with the retained API 6 ELF passes
  five signed installed ARM cases: initial inspection, quota-full workload,
  identical-package cold reopening, undeclared capability and older-firmware
  fallback. The workload checks `EDQUOT`, saved-file preservation, continued
  reading after failure, truncate allowance, deletion, append/live sync and
  committed/staged accounting. Kernel/code output pointers are rejected before
  the same reply is retrieved into app memory. Independent host export verifies
  the final nine saved bytes in both the workload and cold case.
- Loader/USB compatibility passes 15 cases including API 3/4/5/6 refusal,
  unsupported requirements, malformed input, malicious-host rejection and cold
  preservation. The pre-schema-1 loader case remains explicitly skipped without
  that older ELF. All 38 native SDK isolation/service cases pass on this VM.
- Website contract/device tests: 187 passed; production build and lint pass.
  Public-tree check passes (826 files); both repository whitespace checks and
  local documentation link targets pass. Coordinated readers remain local.

Reports, source identities and retained ARM artifacts are under
`build/sdk-file-quota/`; logs are `build/sdk-file-quota-*.log`. The final VM BIN
SHA-256 is `452f98977216e250935c67a74c00100ac81a199d2788e9814a82524252f8ef8d`.
QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The initial test-harness compilation errors and ARM failure led to the corrected
fixture and reader-isolation fix above; the final runs follow those changes.
No device write, deployment, commit or push occurred. The quota is a fixed
development policy, not physical capacity reservation or a claim of hardware
latency/durability qualification. Import/export, public migration/recovery,
UI, connectivity, publishing and the other SDK 1.0 requirements remain open.

## SDK per-file USB exchange — 2026-09-12

The development [file exchange protocol](NATIVE-APP-FILE-EXCHANGE.md) adds selected-app
inspection, directory listing, import and export through the actual USB app
management channel. The [SDK CLI](../sdk/FILE-EXCHANGE.md) exposes these as explicit
`files` commands. The protocol authenticates installed package metadata and binds
each transfer to an app ID, current root generation and saved data schema. An
open foreground app, another transfer or incompatible/pending schema upgrade
blocks import. Imports honor quotas and check the complete digest before atomic
publication. Existing file contents survive pre-commit cancellation or failure.

The controller only copies bounded frames and cached replies. USB OUT status
acknowledgement precedes execution; an abandoned setup cannot apply its queued
frame. Export reads are repeatable until explicitly acknowledged. A 30-second
host-progress lease and bus-reset cancellation release uncommitted sessions;
commits already acknowledged are drained and never retried automatically.
The SDK writes exports to private temporary files, validates length/hash and
publishes them only on success. Its libusb adapter cannot issue firmware or raw
NAND requests. Hello flags advertise the protocol and an open foreground app;
app API revision 7 and existing storage/package layouts are unchanged.

Initial USB testing found a queued-BEGIN status race, now fixed: the status
reports the pending operation while authentication is deferred to OS polling.
A repeat run also confirmed the host's no-overwrite guard; the harness now clears
only its own generated output files before another run. Website file-management UI, namespace archive/restore,
private-byte exchange, large-asset transfer/performance and physical qualification
remain open; this is not complete SDK 1.0 storage acceptance.

Final per-file candidate validation:

- `.venv/bin/python -m pytest -q`: **607 passed**, 280 subtests passed, two
  expected private DTB/DTS skips in 165.54 seconds. This includes the production
  exchange/session/FILE4/volume sanitizer fixture and 21 SDK client checks.
  The final client rejects a FIFO without blocking or contacting USB, bounds
  prehashing to the initial regular-file length, permits cancellation during
  hashing and refuses short local export writes.
- `.venv/bin/python vm/test-sdk-file-exchange.py`: passed with the final client.
  A signed ordinary-main app receives and exports 131,791 exact bytes through
  modeled USB; directory listing and explicit replacement checks pass. A wrong
  digest and partial import interrupted by actual modeled USB reset preserve
  the previous file. A subsequent 23-byte replacement survives cold restart.
- Both physical and emulator firmware builds pass. The VM ELF SHA-256 is
  `0ff44730f1e34f716ca7ff20e856f7a97c959b13d87a8d60161bed8f318e9cb1`;
  VM BIN is `c28d9e12437b1414986472c8aa4ccbbead846f09c6bc840bf3ac654ed552fea1`;
  physical BIN is `a0a97976ab80a1e07dec277f63c77f2890c9609a86b869e17e707aab0601271f`.
  These are compile/model candidates, not physical acceptance.
- All 38 native SDK isolation/service cases pass. The comprehensive native
  smoke suite passes direct-ELF, smoke and protocol checks; its retained output
  is `build/prime-g2-native-suite-20260912-191101/`. QEMU SHA-256 remains
  `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
- The standalone source kit includes the file-transfer tools and both guides,
  with the verified newlib runtime. All **336** listed file hashes match after
  extraction, and the relocated CLI's `files --help` passes. Archive SHA-256:
  `ab9714ccdd8a4c273c8c544f69530763e61976da4a463d1147d86e116d4eaf2d`.
  This is a local candidate, not an updated public download.
- `make check-public` passes for 837 files; both repositories pass whitespace
  checks and 108 local documentation targets exist. The final host and ARM
  report source hashes match the working files.

The core and ARM reports are `build/sdk-file-exchange/host-report.json` and
`build/sdk-file-exchange/arm/report.json`. Final logs include
`build/sdk-file-exchange-host-final.log` and
`build/sdk-file-exchange-arm-client-final.log`. Earlier failed/rerun logs remain
available; they do not replace the final reports above.

The additional `vm/test-sdk-doom-exchange.py` harness now exercises the actual
SDK user-asset path instead of seeding the WAD with a filesystem fixture. Its
first long run is in progress under `build/sdk-file-exchange/doom/`: the real
missing-WAD error screen was inspected and the initial 1,048,824 bytes imported
in 173.3 seconds. This is an incomplete model/host timing observation, not a
whole-file result or a physical throughput measurement. Quota/cancellation,
post-import launch and cold export are still pending in that run. No device
operation, deployment, commit or push was performed.

## API 8 private-data checkpoints and migrations — 2026-09-12

The [private-data controller](../sdk/DATA.md) is integrated into authenticated
installed app execution. Service 14 requires declared capability 512; API 8 and
combined mask 1023 are coordinated across firmware, SDK and website readers.
The existing 64 KiB private store and ABI 1 services retain their layouts.
Requests copy the private snapshot before returning and complete through normal
OS polling. Later edits remain dirty after the snapshot commits. All file
handles must be closed before a data operation; filesystem work stays outside
the request/status syscall. A second 64 KiB OS snapshot buffer separates submitted
bytes from live staging and the committed snapshot used by named files.

Explicit migration permits the authenticated app to transform private and named
data toward its signed schema. Checkpoints retain the previous compatible
package/data pair until explicit acceptance. Acceptance rejects unsaved private
edits or a mismatched saved schema. Legacy schema-0 Close acceptance remains for
apps that do not opt into the controller. Normal Close drains an acknowledged
checkpoint and saves later edits; Home/fault discards uncommitted changes.
Uncertain storage failure prevents further writes and automatic Close saves in
that session. Multiple named-file commits are not one atomic namespace migration.

Final candidate evidence:

- Full host suite: **609 passed**, 280 subtests passed, two expected private
  DTB/DTS skips in 176.77 seconds. The sanitizer controller fixture covers copied
  snapshots, later dirty edits, truncation, descriptor exclusion, stale generation,
  named-file preservation, migration/rollback and anti-downgrade retention. It
  checks 26 clean/torn checkpoint interruption cases and cancellation across 82
  cancellable steps plus one already-committed outcome. Normal/fault cleanup
  freezes writes and respectively drains or cancels an outstanding checkpoint.
- All 11 signed installed ARM cases pass with the final API 8 manifest. A live
  checkpoint saves 44 while a later edit to 55 remains staged. Fault and Home
  preserve 44; normal Close saves 55. Cold launches verify the independently
  inspected saved bytes. Migration changes private and named data, survives a
  restart with the old pair retained, then explicitly accepts. Undeclared access
  and an optional call against the retained API 7 firmware fail as specified.
- All 38 native SDK isolation/service cases pass. Five legacy FILE4 callback
  cases retain data-only Close, cold update, schema-0 acceptance, schema mismatch
  and faulted-Close behavior. Loader/USB checks include old API 7 refusal of both
  API-8 and capability-512 requirements, unsupported/malformed packages and
  preservation of the installed app. The pre-schema-1 loader case remains an
  explicit skip because that older ELF was not supplied.
- Both target builds pass with separate candidate output names. VM ELF
  `lefony-os-prime-g2-checkpoint-vm.elf` SHA-256:
  `15685cef9b9171cac2c104b267ab92ff189c14391e34d7d26d7426ea5315f14b`;
  VM BIN `3a6a03d38af0bddf09664490695dcf2c6200544f28ad9445600df842ba607e72`;
  physical BIN `lefony-os-prime-g2-checkpoint-native.bin`:
  `3e67d738b3ee2d4fc346a9bfd2cdd2613ae9ef85fa59ca4df008020cc3e594fe`.
  QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
- Website contract/device/store checks: 210 passed, one skipped; production
  build and lint pass. These readers remain local. Public-tree checks pass for
  846 files and both repositories pass whitespace checks.

Reports are under `build/sdk-data-checkpoint/`, including `host-report.json`,
`arm-final/report.json`, `legacy-files/arm-report.json` and `contracts/report.json`.
Final logs use `build/sdk-data-checkpoint-*-final.log`; isolation and legacy-file
logs retain their descriptive suffixes. The host and final ARM report source
hashes match the exercised implementation. Earlier qualification attempts remain
historical evidence. The data headers retain their file-level license; the prior
scoped MIT alternative is not expanded by this addition.

Public host rollback, private-data import/export, namespace archive/restore and
recovery UX remain implementation work. Physical power-loss, endurance and
latency are unqualified. The document/UI workflow, system/math services,
connectivity, SDK account/publishing workflow, private key management and broader
proving-app journeys remain open. No device operation, deployment, commit or
push occurred; no R0–R6 milestone is complete.

### Large Doom asset exchange: failed qualification run

The long per-file candidate run described above has now failed with
`DeviceError: Invalid file import offset`. Its last progress line records
14,680,512 of 28,795,076 bytes at 2425.7 seconds; this is a lower bound on bytes
sent, not the exact failing offset. The original error omitted the returned
state/offset, so the cause remains unresolved. Complete import, quota refusal,
cancelled replacement, post-import gameplay and cold exact-byte export did not
complete. Only the missing-WAD visible error case passed in this run.

`build/sdk-file-exchange/doom/failure-report.json`, the original log and synthetic
workspace preserve the failure. `executed-source.json` binds that execution to
the earlier immutable per-file source snapshot and VM ELF
`0ff44730f1e34f716ca7ff20e856f7a97c959b13d87a8d60161bed8f318e9cb1`.
Checkpoint builds used separate artifact names and did not replace that firmware.
The failed run is not evidence against or qualification of the later API 8
candidate, and the earlier small-file exchange pass does not qualify this WAD.

## USB status acknowledgement race — 2026-09-12

The failed Doom import led to a deterministic reproduction in the actual ARM
EP0 driver. The host can finish status IN and send the next SETUP after `poll`
reads ENDPTCOMPLETE but before it reads ENDPTSETUPSTAT. The old SETUP handler
then discards the still-unacknowledged software command, despite successful USB
completion. A one-byte import reproduces the same offset disagreement on the
retained per-file firmware: the host acknowledged the byte, but status remains
writable at offset zero. The original long-run log omitted the exact returned
state, so this establishes a matching failure mechanism rather than an exact
trace of that earlier occurrence.

`handleSetup` now checks pending reset and completed status IN before abandoning
old request state or reusing the descriptor. The existing completion handler
retains its descriptor-error checks and deferred side-effect handling. No register
addresses, bitfields, timeouts or USB/package/storage formats change. Hardware
reference context was checked against Linux's primary
[ChipIdea completion/setup handling](https://github.com/torvalds/linux/blob/master/drivers/usb/chipidea/udc.c),
including completion-bit handling, status completion and descriptor flushing;
the race reproduction and fix evidence are specific to this Lefony driver.

`vm/test-sdk-usb-status-race.py` uses a GDB breakpoint between the two existing
register reads. All bytes and ACKs traverse the modeled endpoint; the harness
changes no guest register, data or code bytes. It proves both acknowledged-frame
retention and cancellation of a frame whose status never completed. The retained
baseline reproduces the lost ACK; the fixed candidate passes both cases. The
SDK now reports expected/observed offsets and state on an unexpected reply, with
no automatic write retry.

Validation on the fixed candidate:

- Both physical and VM builds pass. VM ELF SHA-256:
  `3a8d54d3541360d70016f101ca529b1b5bf0eae6f4d09e0d5bbfcfceb70ede99`;
  VM BIN `87157f382149973a461911e39ecb14bdf8af8b7aa861251b40ed71edf1323023`;
  physical BIN `aff9334b3b6b8ae504c8e5c895d85be20eeaf6635be96b818777744169476f4b`.
  The `usb-race-vm`/`usb-race-native` output names retain the candidate; the
  standard local dist names now contain the same built bytes. Earlier candidates
  remain in their separate immutable evidence directories.
- Full host suite: **609 passed**, 280 subtests passed, two expected private
  DTB/DTS skips in 189.40 seconds. The focused file-client, exchange-engine and
  USB diagnostics checks also pass (54 cases).
- The signed ARM file-exchange journey passes 131,791-byte import/export,
  exact-byte verification, exclusive replacement, cancellation, wrong digest,
  actual modeled USB reset, subsequent replacement and cold export.
- The comprehensive native smoke suite passes direct ELF, smoke and protocol
  cases on this exact VM. Reports are under `build/sdk-usb-status-race/`; the
  deterministic baseline/fixed reports and assembly/GDB transcripts are retained
  separately. QEMU remains
  `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.

The full Doom USB journey was restarted in `build/sdk-usb-status-race/doom/`.
It has passed the missing-WAD visible error and started actual USB import; it
is still in progress and no whole-file result is claimed. The harness now copies
its chosen firmware and executed sources at startup, records failures with the
completed cases, and rejects a changed QEMU before a cold launch. Work on later
SDK candidates cannot change the firmware used by that run. Physical USB timing
and disconnect behavior remain unqualified. No device operation, publication,
commit or push occurred. Public data recovery and the rest of SDK 1.0 remain open.

## Host private-data backup/restore and retained-pair rollback — 2026-09-12

The [SDK recovery commands](../sdk/DATA-RECOVERY.md) add `data info`, `export`,
`restore` and `rollback`. The host protocol advertises these operations with
hello flag 128, independently of the unchanged app API 8/mask 1023, ABI, package
and storage formats. Private backups bind app ID, data schema, exact length and
SHA-256 in a bounded format. Restore stages at most 64 KiB in OS RAM and checks
the complete hash before a data-only commit; named files and code are preserved.
Exports use atomic local publication and do not replace existing destinations
without an explicit option. Older firmware receives no recovery request.

Rollback binds the inspected current root to its one retained package generation.
The manager verifies the retained package signature, app ID, supported runtime and
signed schema. The storage transaction verifies retained objects before replacing
the current package/data pair. Rollback preserves the highest installed version;
the failed immutable release cannot be reinstalled. Host-supplied code or trust
flags cannot select a rollback target. App execution, installation and exchange
retain exclusive ownership of shared scratch and the volume.

Validation found and fixed two commit/reset boundaries. A status-acknowledged
COMMIT must survive reset/lease expiry even before the next OS poll starts storage
work. Also, reset can clear ENDPTCOMPLETE before software consumes the status ACK.
The driver now inspects the status-IN dTD DMA writeback before flushing it, requiring
Active, error and remaining-byte bits to be clear before acknowledging an app
request. Firmware update/reboot reset handling is unchanged. Linux's primary
[ChipIdea descriptor completion code](https://github.com/torvalds/linux/blob/master/drivers/usb/chipidea/udc.c)
provides the active/error/remaining-byte interpretation; the exact reset
interleaving and retention behavior are qualified in this model, not on hardware.
The QEMU model is unchanged. No frame or ambiguous commit is automatically retried.

Final candidate evidence:

- Full host suite: **632 passed**, 280 subtests passed, two expected private
  DTB/DTS skips in 192.15 seconds. The exchange sanitizer fixture includes
  maximum-length RAM staging without NAND writes, private/named-data isolation,
  wrong hash, empty restore, pre-commit cancellation, target/schema denial and
  cold version-watermark retention. It passes **26 restore and 10 rollback**
  clean/torn-write interruption cases with an exact old-or-new committed root.
- All **eight signed installed ARM recovery journeys** pass using the actual USB
  host/client/controller: initial maximum-size restore, cold data reopen and empty
  restore across COMMIT/reset, schema upgrade followed by rollback, cold rollback
  and rejected same-version reinstall, plus denial of retained packages with an
  invalid signature, different app ID, incompatible schema or unsupported API.
  Independent offline storage reads verify package/private hashes and named files.
- The deterministic `--commit-reset` test reproduces cancellation of an ACKed
  commit on the retained baseline and passes on the corrected candidate. It also
  verifies that a COMMIT whose status was never acknowledged cancels without
  creating the file. GDB only pauses execution; all USB packets traverse the model.
  The prior ACK/next-SETUP race regression also passes.
- All **38** native SDK isolation/service cases pass. The final per-file USB
  regression passes initial import/export, wrong hash, replacement, reset and cold
  export. The native smoke suite passes direct ELF, smoke and protocol cases.
  Its reporter was corrected to hash an explicitly selected firmware path;
  the earlier smoke report recorded the default ELF despite the runner override.
- Both physical and VM builds pass. VM ELF SHA-256:
  `5e9e6733977423a6bdbe884239660bf95c6c8a2b10ef7554efef830f890c1301`;
  VM BIN `801f314f1f5e6dc00b72c014e1b5cacb7247cff1f7347c5c0709a8a4bdd61314`;
  physical BIN `87b067accdce29f6deffff24529d9c7211db28df0ebd983ee94e3feb2dd1e56e`.
  Candidate output names use `data-recovery-vm` and `data-recovery-native`.
  QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
- SDK and website recovery guides describe the same local commands and limits.
  Public-tree and whitespace checks pass, and 131 local documentation targets in
  13 affected guides resolve. The source-kit packager includes the recovery client
  and guide; its separate report records archive/hash and relocated CLI validation.

Final ARM evidence is `build/sdk-data-recovery/arm-final8/report.json`; reset
baseline/fixed reports and the SETUP regression are sibling directories. Final
logs include `build/sdk-data-recovery-suite-reset-final.log`,
`build/sdk-data-recovery-files-final.log` and the firmware `*-reset-final.log`
files. Earlier failed harness runs and the real reset failure are preserved;
they do not qualify the final candidate. Current executed source hashes match
the ARM report. This batch does not extend the earlier scoped MIT grant.

Whole-namespace archive/restore, general damaged-current-data recovery, website
recovery UI and physical durability/USB timing remain open. Current host recovery
requires a readable current package/root/private store. The separate full Doom
asset transfer continues on its copied USB-race candidate and is not included in
this recovery qualification. UI/document work, system/math services, connectivity,
SDK accounts/publishing, private key management and broader proving-app journeys
remain required. No device operation, deployment, commit or push occurred; no
R0–R6 milestone is declared complete.

## C++ Notebook, OS typography and actual ARM layout preview — 2026-09-12

The [UI candidate](../sdk/UI.md) adds service 15, capability 1024 and API 9
(combined mask 2047) without changing ABI 1, package envelopes or storage layout.
A fixed 80-byte request measures or draws up to 256 UTF-8 bytes using the four
pinned OS fonts. Complete scalar/glyph/request validation precedes drawing;
malformed/unsupported calls leave the request and surface unchanged. The public
boundary rejects leading combining marks because the pinned Kandinsky renderer
requires a base. It permits empty null-pointer text. Normalization is explicit:
precomposed accents absent from the OS font are errors, while supported combining
forms render. The original ASCII text service remains unchanged.

Public C++ helpers add configurable widget palettes, measured labels/buttons,
two-line rows, fields with clipped cell/selection/caret painting, choices,
progress and slider rendering, plus bounded list selection/page state and an
atomic whole-value `TextBuffer::set`. Menus/actions and slider value changes
remain developer-owned handlers. Notebook uses ordinary `main`, public input,
files, scalar math and raster helpers for list/edit/confirmation screens,
validation, light/dark themes and a small plot. Its save uses a checked temporary
file followed by atomic rename. A successful live save survives Home/cold reopen;
export writes readable text. Old document format 1 upgrades on save; unsupported
or malformed documents preserve bytes and disable mutation. This is a document
file upgrade, not completion of package/private-schema integration in this app.

`preview` incrementally builds the real ARM package, installs it in fresh
synthetic storage and replays a selected normal-input scenario. A GDB read of
bounded debug-only widget records supplies bounds, clip, state and source lines.
It pauses without guest calls, code patches or register writes and checks symbol
identity. A self-contained HTML viewer shows the actual frame and bounds. Failed
builds/runs retain a visibly stale frame with diagnostics. An optional root-file
fixture directory is retained unchanged and copied into each installation.
Automatic evolving namespace/private-data retention and nested fixture imports
remain unfinished. No physical USB transport is opened by preview.

Final local validation on macOS ARM64:

- **641 host tests passed**, two expected private DTB/DTS skips, 171.87 s. The
  focused UI/contract checks pass 114 cases, including sanitizer validation,
  Unicode boundaries, aliased/full-value editing, list bounds, copied inspection
  records, malformed document preservation and debug-record removal. The shared
  manifest corpus now has 80 cases, retaining its original API 1 expectations
  and adding current/future typography requirements.
- Four signed installed ARM typography cases pass: normal rendering/measurement,
  unchanged-frame comparison after rejected calls, undeclared capability denial
  and old-firmware unsupported behavior. All four fonts, maximum length, supported
  combining text, invalid pointers/UTF-8 and partial clipping are covered. The
  generated font frame was visually inspected.
- **Ten Notebook ARM journeys** pass across debug/release: editing/live save and
  host export, cold reopen, old-format upgrade with scrolling/long text,
  malformed-data preservation and disabled input, and validation/discard/cancel.
  Independent host USB exports match exact expected document/text bytes. All
  **20 captured frames match** across debug and release. Empty, editor, plot,
  dark, invalid, read-only and confirmation screens were inspected.
- The external source-authoring proof passes initial preview, a deliberately
  misplaced/clipped button linked to its real source line, syntax-error stale
  retention, restored layout/frame equality and a public CLI watch-save rebuild.
  Developer action handlers remain byte-identical during the layout edit. The
  first build took 4.32 s; three successful incremental builds took 0.60–0.85 s.
  Their complete build/install/scenario/inspect runs took 14.03–15.00 s. These are
  a few local emulator measurements with other qualification jobs running, not
  ratified latency budgets or host/hardware qualification.
- Notebook debug uses 73,832 code/constant bytes and 13,796 static-data bytes;
  release uses 65,248 and 2,508. The difference includes the 11,288-byte debug
  frame, whose symbol is absent from release. Reserved stack is 65,536 bytes;
  stack and allocation peaks remain unmeasured.
- The source kit with pinned newlib is reproducible, verifies all 355 file hashes,
  and scaffolds/builds/previews Notebook after relocation with spaces/Unicode in
  the path. macOS sandbox rules deny outbound IP networking for these commands.
  The external build uses its bundled newlib, source-2 export succeeds and the
  real GDB inspection works. This does not qualify frozen desktop bundles,
  native Windows/Linux installation or a fresh host without dependencies.
- Both firmware targets compile. All 38 SDK isolation/service cases and the
  three native smoke cases pass on the UI VM candidate. Preserved Counter and
  Surface 3D ABI 1 package bytes also pass normal-input interaction unchanged.
  The existing Forms/Tables normal-input replay passes on this same candidate.
- Website build/lint pass; **426 tests pass**, one optional real-project test is
  skipped. SDK and website retain identical shared manifest corpus bytes and
  API 9/mask 2047 readers. UI documentation is coordinated locally; no website
  UI, download, account/publication operation or deployment is claimed.

Candidate identities:

| Artifact | SHA-256 |
| --- | --- |
| VM ELF | `5a18b9f79d617c4b1ab451460c4f9b3cfc46c18bb2f4adaa5838c1e561954287` |
| VM BIN | `bfa5122ff1e10e8a6663f8e419637d8f4e06bb70b8354519247bdfb3b903abec` |
| Physical ELF | `96a66936106aeef7badf84993c5b0ff15a7bd5ad0f2c163d099c1caafe5ece73` |
| Physical BIN | `843df5a8f2b0e26f3388357348c4cad455465509d0c32b780d7f7a9cdc65ba50` |
| SDK source identity | `f430ac56d642c87835cdf144a549bbf4d95c75d7e78954f09dc37e8ec6275a8b` |
| Source kit with newlib | `82bed589c65673724836fa062bb142ec243cfa1e31444f6336ff1b33e773e54a` |

Output firmware names use `ui-vm` and `ui-native`; standard dist names still
identify the prior recovery candidate. QEMU remains
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
Reports live under `build/sdk-ui/{typography,notebook,preview,kit,compatibility}`;
final host log is `build/sdk-ui-host-frozen.log`. Smoke evidence is
`build/prime-g2-native-suite-20260912-214847/`. Earlier failures remain in logs:
an unsupported precomposed accent exposed the font policy; a replay used the
wrong physical key name; editing the SDK mid-comparison correctly invalidated
its lock; and new corpus rows initially used the historical `supported` field
as if it meant API 9. The corrected focused/full suites pass. Two website
recovery tests timed out under concurrent load; the unchanged tests pass with
bounded worker concurrency. None of those failed runs qualifies the final result.

The separate long Doom test has passed exact WAD import, quota refusal, cancelled
partial replacement and normal gameplay on initial/cold launches. Its complete
cold USB export is still running on its earlier copied firmware. It is not part
of this UI candidate's qualification.

R3 and the overall objective remain open: fuller reusable interaction/gallery
states, smooth scrolling, general glyph/locale handling, evolving preview data,
complete document upgrade/error/resource journeys, frozen/clean-host bundles and
independent developers remain. System/math adapters, app USB/HTTPS, SDK accounts
and folder publication, private key management, complete recovery and physical
qualification remain required. No device operation, deployment, commit or push
occurred, and this batch does not extend the prior scoped MIT alternative.

An immutable local snapshot is retained at `build/sdk-ui/evidence`: 1,130 source,
report, log and artifact files. Its index SHA-256 is
`9b1858ac4070d60dc6207364b862e6c8d5a029e8ea6e04a17a36fc9bfa5bc0ff`.
The snapshot excludes the still-running Doom workspace and preserves this ledger
before the snapshot annotation.

## Public system services, temporary settings and clipboard — 2026-09-12

The [API 10 candidate](../sdk/SYSTEM.md) adds service 16/capability 2048 and
brings the current feature mask to 4095. It preserves ABI 1, signed package
formats, storage geometry and release trust roots. C11/C++17 helpers use a
48-byte copied request and a 160-byte copied snapshot. Complete pointer, size,
reserved-field and overlap validation precedes side effects; failed requests
preserve their request and output bytes.

Snapshots expose 64-bit monotonic milliseconds and separately flagged civil
calendar fields. A stable readable clock is distinguished from one explicitly
set this boot; no UTC offset or persistent trust marker is invented. The
existing voltage filter now records the age of its last valid averaged estimate.
Fresh charger/presence state and a present battery with an estimate at most two
seconds old are required before returning percent/millivolts. Otherwise values
are explicitly unknown. The API copies the OS palette, language and read-only
math preferences. It does not automatically reconfigure app-linked mathematics.

Temporary brightness updates both the OS preference and driver, so normal input
retains the app value. Ownership preserves the first restore value across later
requests, restores after normal exit, Home/focus loss, fault, forced close and
unload, and preserves a later OS preference change. The OS keeps its idle policy.

Shared clipboard access requires a fresh normal input gesture. Copy/Cut grants
one write; Paste grants one read. Grants expire after two seconds, reject replay
and wrong operations, and revoke on subsequent ordinary input or focus loss.
The bounded OS snapshot does not insert math placeholders or mutate the shared
clipboard. Plain UTF-8, tabs and newlines are accepted up to 219 bytes without
truncation; internal math-layout controls are explicit text errors. Shift+View
and Shift+Menu retain Copy/Paste. API 10 apps opt into Shift+OK as Cut because the
Prime has no physical EXE position. Other apps retain their old Shift+OK behavior;
the public snapshot preserves the real OK-key matrix position for Cut.

Validation on the local macOS ARM64 host:

- Full host suite: **648 passed**, two expected private DTB/DTS skips, 172.52 s.
  Final focused checks: **116 passed**, including sanitizer-checked gesture
  ownership/expiry, brightness ownership, UTF-8/request boundaries, checked
  preparation idempotence, C/C++ ARM wire compilation and shared contracts.
  The final physical-key metadata correction is covered by the ARM cases below.
- Both physical and VM firmware targets compile. The final candidate passes
  **11 signed installed ARM system cases**: basic/malformed calls, undeclared
  denial, old API 9 firmware, normal exit, explicit brightness restore, fault,
  Home, Copy/Paste/Cut with same-OS relaunch, 219-byte UTF-8/empty clipboard,
  expired grants and calendar/battery telemetry. Wrong-operation, consumed-grant,
  too-small-buffer and invalid-text calls preserve data. Backward calendar
  changes preserve monotonic time; absent batteries do not return estimates.
- All **38 isolation/service regressions**, three native smoke checks and both
  preserved Counter/Surface 3D ABI 1 packages pass on the final VM hash. The
  complete native services suite passes battery/charger, calendar, LED, idle,
  suspend/resume and repeated power-button checks on the same candidate.
- The source kit with bundled newlib is reproducible and verifies all **358 file
  hashes**. A relocated external ordinary C project builds using that bundled
  runtime and completes real signed ARM system queries/brightness/restore through
  the public CLI. This is local source-kit evidence, not a frozen bundle or
  clean-host qualification. Its archive predates this ledger annotation.
- Website build/lint and **429 tests** pass; one optional real-project test is
  skipped. Its API 10/mask 4095 reader shares the identical 83-case manifest
  corpus. Website system documentation is local; no deployment is claimed.

The older services test initially sampled an intermediate battery-filter value
(3841 mV instead of the expected settled 3835 mV). The identical failure was
reproduced on the prior API 9 UI firmware. After fixing that synchronization,
both candidates also exposed an idle-test fixture that still modeled external
power after a calendar advance. The test now waits with a bound for each exact
settled voltage and explicitly unplugs its modeled battery source before idle
checks. Firmware power behavior was not weakened. Original and traced failures
are preserved alongside the final passing log.

Other earlier failures were in new test plumbing: an ARM narrowing conversion,
a copied request defeating the intended overlap test, observing brightness
before main startup, treating an intentional fault as unexpected, signed diagnostic
formatting, and assuming a fixed package filename while retaining kit evidence.
These were corrected and the relevant complete runs passed. The first firmware
build also exposed missing integer-limit macros in the embedded core headers;
fixed-width constants now work with both the core and newlib headers.

| Artifact | SHA-256 |
| --- | --- |
| VM ELF | `68f32e1f6552c157d42238bd6a74df409e53811ed509e4e6d8fcff016c8545ce` |
| VM BIN | `cf29d28621e0fd6f809987455b336053cfa8f1ddd53408be2eb3c82b03f77086` |
| Physical ELF | `f1d747a8a1f41f1d357025607332bf6366980cae0f73e285ffba84e4196ee1c0` |
| Physical BIN | `5d317b0945c58bd2ec9b959f18b22b730ef964b104cb0d20e30ce87f88fc3f87` |
| SDK source identity | `e5f37451d18f6a90598c9b15de06777972f0af02fb034037be6a5b395d4d9a02` |
| Source kit with newlib | `14293f11f6cd1f588bf507b3f1c7274d22e662819b7360052e3a63c581944880` |

Output firmware names use `system-vm` and `system-native`; standard dist names
still refer to the earlier recovery candidate. QEMU remains
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
Reports live under `build/sdk-system/{arm,kit,compatibility-final,smoke-final}`;
final system, services and host logs have the `build/sdk-system-` prefix. The
executed ARM source hashes match current implementation files.

Notebook integration, complete selected-math acceptance, broader clipboard/UI
journeys, evolving preview data, full archive/damaged-data recovery, app USB/HTTPS,
SDK accounts/folder publication, private key management, host bundles and physical
qualification remain required. No R0–R6 milestone or the overall objective is
complete. This batch does not extend the scoped MIT alternative. No physical
device operation, deployment, commit or push occurred. The independent long Doom
cold export continues on its earlier copied candidate and is excluded here.

An immutable local snapshot at `build/sdk-system/evidence` retains 1,001
source, report, log and artifact files. Its index SHA-256 is
`d5cb41ef8e6e670d4c322f004ed9c6ce1c8442f09a19f1078fd46987c3ff58a4`. It excludes the live Doom workspace and
preserves this ledger before the snapshot annotation.

## Completed Doom large-asset USB round trip — 2026-09-12

The independent long `vm/test-sdk-doom-exchange.py` run has completed. Its nine
recorded cases pass: missing-WAD error, exact 28,795,076-byte USB import, quota
refusal preserving the root, cancellation after 1,048,824 bytes of a replacement,
initial/cold launch with normal input and changed frames, both runtime checks,
and full cold USB export. The exported WAD SHA-256 is
`7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d`,
identical to the pinned Freedoom 0.13.0 input. Semantic gameplay/save/load has
separate earlier evidence; a changed frame alone is not that acceptance.

This run used its copied earlier USB-race VM ELF
`3a8d54d3541360d70016f101ca529b1b5bf0eae6f4d09e0d5bbfcfceb70ede99`
and QEMU `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
It does not qualify the later API 9/10 firmware. Its captured source hashes,
reports, package/ELFs, frames, exact exported WAD and log are retained read-only
under `build/sdk-usb-status-race/doom-evidence`: 32 files, 42,364,721 bytes, index
SHA-256 `c768210a3b8803ab09e7ed951b447ded82200f179b0306f8d2014d822fda68b6`.
The report SHA-256 is
`df7870f034b98ebbeb6b91285b6c66affa167cad0a50873e91b30431459efa03`.

The measured import/export elapsed times were 4,333.19/5,535.14 seconds, and
the complete run took 10,209.61 seconds on this host/model with concurrent work.
These are not physical USB throughput measurements. Physical durability,
performance, broader error workflows and the remaining SDK requirements stay
open. No physical calculator or external publication was involved.

## Notebook system integration, formatting and clipboard — 2026-09-12

Notebook 0.2 now requires API 10 (capability mask 3103). Its light palette derives
from the public OS snapshot; dark appearance remains an app-local customization.
New documents copy the OS angle/display/significant-digit preferences. Options
explicitly selects degrees/radians/gradians, automatic/scientific/engineering
notation and 1–14 significant digits. Apply publishes the settings with the
document; Cancel/Back and cancelled/outside/multicontact slider drags discard
draft changes. Keyboard Left/Right adjusts the focused slider by one digit.
The controls do not mutate OS math settings.

Document format 3 stores theme, angle, format and digits before the expression
lines. Formats 1/2 keep their original radians/automatic/9-digit meaning and
remain byte-unchanged until a successful save. Unsupported or malformed files
remain read-only with original bytes intact. Save still checks a staging file's
write/close before atomic rename. Text export includes settings, evaluates at
x=1 and reports actual parse/domain/unbound errors instead of a bogus answer.

The C-compatible `number_format.h` helper uses explicit finite binary64 values,
digits and modes in the app-linked newlib profile. Engineering notation derives
from the rounded scientific significand, so subnormal conversion does not depend
on an underflowing power-of-ten division. Negative zero is retained; invalid,
nonfinite and short-buffer failures leave the destination untouched. The scalar
context adds explicit gradians while retaining old SDK angle enum values.
System angle ordinals are converted explicitly rather than cast to SDK ordinals.

The reusable text model accepts larger atomic UTF-8 insertions. The expression
adapter normalizes supported calculator symbols into its one-line ASCII grammar.
Notebook uses normal Copy/Cut/Paste grants and supports whole-field or selected
text. Cut deletes only after successful clipboard writing. Empty clipboard,
unsupported text and oversized paste never partially edit the field. This is
the documented bounded scalar subset, not a general OS layout editor or new CAS.

Final local macOS ARM64 evidence:

- **650 host tests pass**, with two expected private DTB/DTS skips, in 168.99 s.
  The focused 11-case run also passes, including ASan/UBSan coverage for number
  formatting, atomic text insertion, selection/aliasing, slider cancellation,
  format upgrades and invalid-header preservation. Existing scalar parser tests
  include gradian known answers and 10,000 bounded arbitrary input cases.
- **24 signed installed Notebook ARM journeys pass** across debug/release:
  live saves, exact USB exports, cold reopen, formats 1/2 upgrade, malformed-file
  preservation, invalid/discard/cancel states, saved degree/gradian formatting,
  slider keyboard/drag cancellation, OS-default draft cancellation and normal
  whole/selected clipboard edits. Legacy `sin(30)` retains its nine-digit radian
  result. All **34 captured frame pairs** match between debug and release.
- **Eight cross-app clipboard journeys pass** across debug/release. Real keypad
  selection/copy moves `2×3−1` from Calculation into Notebook's scalar grammar;
  copying an edited expression back to Calculation evaluates to 7. A second
  signed public-API app supplies Unicode math text, multiline text and 200-byte
  text through a real Copy gesture. Valid text normalizes; rejected paste keeps
  the entire selected field intact. Exact document exports and all **10 frame
  pairs** match. Frames of options, formatting, clipboard, selection and errors
  were visually inspected, including the built-in Calculation return trip.
- **Four ordinary C/C++ ARM programs pass** in debug/release. The same 20 finite
  formatting cases cover rounding carry, signed zero, extreme exponents,
  DBL_MAX, the smallest subnormal, exact capacities and unchanged failure output.
  Ten scalar known answers cover all three angle modes, with unsupported,
  unbound, domain and invalid-mode checks.
- The external source-edit/ARM-preview proof passes initial rendering, a
  deliberately clipped action tied to its source line, syntax-error stale-frame
  retention, repaired frame equality and public CLI watch-save rebuild. Action
  handlers remain byte-identical. First build: 2.58 s; successful incremental
  builds: 0.61–0.72 s; complete successful loops: 14.55–16.54 s. These are a few
  host/model measurements under concurrent load, not physical/host budgets.
- The reproducible relocated source kit verifies **360 file hashes**, uses its
  bundled newlib, scaffolds/previews Notebook through the public CLI and exports
  source format 2. macOS outbound IP networking is denied for those commands.
  This uses locally installed host tools; frozen/clean-host bundles remain open.
- Public source boundary passes **893 files**; 97 relative documentation link
  targets and both repositories' whitespace checks pass. Website changes in this
  batch are documentation only. No deployment or website application change is
  claimed.

SDK source identity is
`525d03444139042064e54c979ceb5ecd81faf03586f6ac531f32958e43dd7d58`.
Notebook debug/release use 83,960/72,488 code-and-constant bytes and 13,796/2,508
static-data bytes. Reserved stack is 65,536 bytes; stack/live-allocation peaks
remain unmeasured. The debug inspection symbol is absent from release.
The kit SHA-256 is
`5df06b250e4d94383882bae5c1d98a24a1dc2b2527fa9f60291421247dc6c460`;
it precedes these final ledger/status annotations.

No firmware implementation changed in this batch. Runs reuse the qualified
API 10 VM ELF `68f32e1f6552c157d42238bd6a74df409e53811ed509e4e6d8fcff016c8545ce`
and unchanged QEMU `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
Both firmware-target builds and isolation/service regressions belong to that
prior system-service evidence; they were not rerun or relabeled here.

Final reports are under `build/sdk-notebook-system/{notebook-ready,clipboard-identity,math,preview,kit}`.
Earlier failed attempts remain separate: three misleading-indentation build
errors; incorrect test UTF-8 byte counts; a replay tapping Export during Save;
Calculation clearing selection on focus loss; a fixture trying Unicode in the
ASCII-only startup-argument contract; and catalog slots changing after helper
installation. Tests now wait for a stable rendered Notebook screen and resolve
app identities again after catalog changes. No production contract was weakened.

The full objective stays active. Evolving preview data, fuller controls/gallery
states, whole-app archive/damaged-data recovery, connected app/USB/HTTPS, SDK
accounts and folder publishing, private signing-key management, clean host
bundles, independent trials and physical qualification remain required.
The prior MIT alternative is unchanged; no device operation,
commit, push or publication occurred.

The immutable local snapshot at `build/sdk-notebook-system/evidence` retains
1,206 source, report, log and artifact files (55,585,694 bytes). Its index SHA-256
is `4d7a08aa169c2b552beb574a45129dcf38d7bb8157bcb81c3520591e051d3978`.
It includes the exact signed Notebook package bytes, final reports and reused
API 10 firmware, and preserves this ledger before the snapshot annotation.

## API 11 app USB channel and HTTPS worker foundation — 2026-09-13

The active goal advances through connectivity. The previous user-facing turn
was a status answer; this turn implements, fixes and qualifies the channel and
a separate HTTPS worker. R4 and the complete SDK objective remain open.

Service 17/capability 4096 adds authenticated foreground app sessions, four
copied 448-byte message slots in each direction and bounded request validation.
The OS owns the pairing screen and physical confirmation. App execution/input
pause during consent; held confirmation keys are blocked until release. Pairing
has a combined 30-second deadline and connected sessions a five-second host
lease. Exit, Home/focus loss, fault, USB reset/shutdown and firmware-update
ownership release queues. Session/sequence counters never wrap into reused
identities. The host binds app ID, signer and package payload hash to a random
session nonce, with explicit receive ACKs and reconciliation of uncertain
sends. The nonce/code are not encryption or protection against a compromised
host with USB access. See [the channel contract](../sdk/CHANNEL.md).

The separate `https_worker.py` executes one explicitly origin/method-granted
HTTPS exchange in a spawned process. It verifies certificate and hostname,
streams known/chunked uploads and bounded responses, returns redirects without
following them, and reports categorical failures without request secrets.
One outstanding chunk/acknowledgement bounds IPC. Cancellation and total
deadlines terminate the worker, including blocked network operations. No HTTP
request is retried; interrupted mutations may have an unknown outcome. This is
an implemented worker foundation, not an integrated app-to-HTTPS companion.
USB message mapping, host policy/account UX, the companion command, progress
presentation and connected proving app remain implementation work.

Validation on the local macOS ARM64 host:

- Full host suite: **712 passed**, two expected private DTB/DTS skips and 280
  subtests, 173.06 s. Focused channel/client/contract checks: **150 passed**.
  The host model covers queues, duplicate/altered/stale frames, idempotent ACKs,
  deadlines, consent and cancellation. Host-client tests cover identity changes,
  malformed responses, backpressure and lost USB completion before/after receipt.
- **11 signed ordinary-C ARM journeys pass** through actual emulator USB and
  normal KPP/Goodix: undeclared capability, API 10 unsupported fallback, streaming,
  user denial, host close, lease expiry, bus reset, Home, fault, fresh reopen and
  pairing expiry. Required API 11/mask 4096 is negotiated without changing ABI 1.
  The stream transfers **70,017 bytes in each direction**, plus zero-length and
  maximum-size frames. The app checks input bytes and transforms them; the host
  verifies exact returned bytes and app counters. The run took 33.51 s in the
  model, not a physical throughput measurement. App/host digests are
  `f9a010d1537653eb705c9935111dc57e62f99b7898bef36bf91b82989b265874` /
  `9a8e8ca3f557fd9cdc7a0c612b558e619853cb348fc024f63c147d5de34dcaa7`.
- The consent screen is explicitly awaited in frame captures, visually inspected
  with app/host names and code, and observed removed after expiry. Digits and
  Goodix touch cannot approve. The app rejects leaked confirmation-key edges and
  observes a fresh normal One key after consent. Fresh reopen rejects the old
  host binding and requires new consent with a new session and nonce.
- Both firmware targets compile sequentially. All **38 existing isolation
  cases**, both public input-stream cases, foreground scheduling/timer/input
  regression and all **three smoke cases** pass. Physical hardware is not tested.
- **25 local HTTPS tests pass** against a real temporary TLS server, including
  131,073-byte fixed/chunked/close-delimited responses; 70,017-byte declared and
  chunked uploads with exact echo; untrusted certificate/wrong hostname;
  redirects; truncation, ambiguous framing and response limits; and cancelled/
  timed-out POST without retry. Policy tests reject ungranted origins/methods,
  credentials/fragments/control characters in URLs, bad headers and excess limits.
  TLS fixture keys stay in temporary test directories and are never packaged.
- The reproducible relocated source kit verifies **365 file hashes**, includes
  the channel guide/headers and both host modules, and builds/runs a pure C
  system/channel program through the public CLI with bundled newlib. It checks
  open/info/send-before-pair/close and prior system/brightness behavior. Installed
  host tools are used; clean-host/frozen companion qualification remains open.
- Website shared readers/corpus: **432 tests pass**, one explicit skip; build
  and lint pass. Public source boundary passes **906 files**. Changes remain local.

SDK source identity is
`5448cfa6fdebc0e733fb0d10684546a25f662f9d0c9fd640fa8ecd6ab0889652`;
all eleven ARM project build records report that identity. Final artifacts:

| Target/artifact | SHA-256 |
| --- | --- |
| `lefony-os-prime-g2-channel-vm.elf` | `b602aa6982ae508bb2bc3f14021971f85e00a186e9beb92a09d344cec3fbd70c` |
| VM BIN | `4a79e9616405d5ca8774430a4c0831e4a7465ac0354ad157b36acc866b67602a` |
| `lefony-os-prime-g2-channel-native.elf` | `ede346f15fd17596db760e54595426632fc2754aeadc23abf40fa5b7e9918010` |
| Physical-target BIN | `6aa9e703c2f54612ad774fdc7cbc9b286bbf41f20cba24534073422b9236270d` |
| Relocated source kit, before this ledger annotation | `e0705f7880e6f5234cc7bf39e1b231205d0db5c7c64a00165cedbb35f8ad2a6e` |

QEMU is unchanged at
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
Standard API 8 distribution filenames and earlier frozen candidates retain their
bytes. Final reports are in `build/sdk-channel/{arm-visible,input-regression,scheduling,smoke,kit}`;
host, build and TLS logs are `build/sdk-channel-*.log` and
`build/sdk-https-worker-3.log`. The website logs are its local
`.local/sdk-channel-{tests,build,lint}.log`.

Failures remain recorded: the initial undefined USB `stall` helper; an input
reset on every scan fixed before final builds; a C fixture passing an overlap
request by value; wrong expected ARM fault classification (-14 for data abort);
a fixture not resetting its expected receive sequence on reopen; and capturing
before the pairing frame rendered. Initial HTTPS fixture failures were header
name case and a zero-body credit race; the worker now sends zero-body requests
without waiting for an upload credit. Earlier logs are not relabeled as passes.
The final pairing harness emits an existing Pillow API deprecation warning.

All other requested SDK work remains tracked: integrated USB/HTTPS and connected
app, accounts/folder publishing, private app-key management, remaining UI/data
recovery and proving-app journeys, complete host bundles, independent developers
and physical qualification. The approved MIT alternative remains scoped to its
original files. No calculator operation, commit, push or
publication occurred.

The immutable channel snapshot at `build/sdk-channel/evidence` contains 1,400
source, report, log and artifact files (49,912,874 bytes). Its index SHA-256 is
`89d97bc894ba8565f734c5b02be76f762b89c3496ed341407e2b20122df32467`.
All copied hashes were checked before making the snapshot read-only. It retains
both repository source trees, final installed package bytes, the four firmware
artifacts, reviewed pairing frames and this ledger before this annotation.

## Integrated HTTPS companion and Link Gallery — 2026-09-13

This supersedes the previous entry's remaining USB/HTTPS adapter, command and
connected-app implementation items. It does not complete R4, R5 or SDK 1.0.

The public C/C++ `lefony/https.h` protocol now carries bounded request metadata,
credited upload chunks, response headers/data, progress, cancellation and
terminal results over API 11. `https_bridge.py` connects it to the isolated TLS
worker. The `lefony-sdk companion` command verifies the app/signer and optional
payload hash, applies explicit HTTPS origin/method grants, waits for OS-owned
consent and closes the worker/session on cancellation or disconnect. Its USB
transport permits only channel requests. Logs contain identities and progress
counts rather than request headers or bodies. The launcher now guards its main
entry for multiprocessing; frozen executable qualification remains open.

Link Gallery is an external-project template with a 288 × 128 RGB565 image and
ordinary C++ controls. It streams into a temporary file, checks the complete
format/checksum, synchronizes and atomically replaces the cache, and displays
the previous image during a replacement. Disconnect, cancellation or invalid
content preserves the saved image. Reconnection requires another explicit
request and fresh pairing; there is no automatic HTTP retry. Cache loading is
available offline. It requires API 11 and a developer-configured HTTPS URL.

Local validation:

- Full host suite: **722 passed**, two expected private DTB/DTS skips and
  **280 subtests passed**, 179.02 s, in `build/sdk-https-full-host.log`.
- **10 signed ordinary-C ARM HTTPS journeys pass** through emulator USB and
  real local TLS: fixed/chunked GET, declared/chunked POST, denied origin,
  untrusted TLS, timeout, cancellation, truncated response and disconnect.
  The fixture verifies 131,073-byte responses and 70,017-byte uploads and
  preserves its prior cache after failure. Report:
  `build/sdk-https/arm-4/report.json`, SHA-256
  `a384982503f1a4e9f46b4900bc317d3c0850b048faa8f788dfa939bc9c9c4621`.
- The production `companion.run` command engine passes a 131,073-byte download
  through emulator USB, normal OS consent and a real local TLS endpoint.
  Exported bytes match exactly and the recorded USB requests stay within the
  channel allowlist. This injects the emulator transport; it does not qualify
  physical libusb or a packaged executable. Report:
  `build/sdk-https/companion/report.json`, SHA-256
  `d9e38bcc15f61410833090581d6393ede700fc04b9c843fa1db5a4c00e1187a0`.
- Link Gallery passes **debug and release connected and cold-cache journeys**:
  initial download, reset during replacement, explicit reconnect, cancellation,
  invalid checksum, exact public file export, absent temporary output and cold
  reopening. Eight captured states match between debug/release; only the
  timing-dependent progress bar is excluded from the loading comparison.
  Report: `build/sdk-gallery/arm-final/report.json`, SHA-256
  `6d9433a5df326ca3f9c16eb5f38d5ceb834ea0c6e36efa1121c38c6b3d07eff4`.
- The Gallery cache reader passes native ASan/UBSan malformed-format, length,
  checksum and missing-file checks without modifying input files.

All journeys reuse the prior API 11 VM ELF
`b602aa6982ae508bb2bc3f14021971f85e00a186e9beb92a09d344cec3fbd70c`;
there are no new firmware changes in this batch. The command and Gallery
reports' source hashes still match the current implementation. After the ten
C cases, the TLS fixture gained a handler that suppresses expected reset/TLS
socket errors during intentional disconnect tests; that report retains its
original fixture hash. The later command/Gallery reports bind the updated
fixture. Earlier frozen source kits do not include the new companion and app.

Failed runs remain retained. Initial C fixture builds exposed missing `fileno`
declarations and an uninitialized result. A successful download exposed a host
observation race with normal app exit. Gallery validation first clicked Refresh
before cancellation cleanup finished, then exposed a real missing redraw after
disconnect. The app now distinguishes pending cancellation from its terminal
state and redraws controls after the session ends; final replays wait for the
enabled control before starting the next request.

Largest remaining implementation work: SDK GitHub sessions/owned-app listing,
project linking and folder publication with website parity; developer app-key
enrollment/revocation/recovery; whole-app archive/restore and general damaged-data
recovery; fuller reusable UI interaction states and evolving preview data; and
complete native host/companion bundles. Remaining acceptance includes broader
libc/app resource-error coverage, compatibility, clean hosts, independent
developers and physical storage/input/performance/power/USB behavior. No
milestone is declared complete by these local results.

## SDK account sessions, owned library and project links — 2026-09-13

The local SDK now implements `login`, `logout`, `whoami`, `apps list`,
`apps show APP_ID`, `project link APP_ID`, `project list` and offline
`project unlink`. The new [account guide](../sdk/ACCOUNTS.md) describes the
protocol, credential storage, limits and current deployment boundary. Folder
publication and its upload/revision recovery remain implementation work.

The website reuses its existing GitHub authorization-code/S256 PKCE flow with
no repository scope. A separate browser page requires the terminal's short
code and explicit account authorization. The CLI's random credential is proved
only through TLS POST requests; only its digest is stored in D1. Atomic grant
consumption and session issuance allow a lost poll response to be retried with
the same credential and expiry. Requests expire after ten minutes, sessions
after 30 days, and each account can hold at most 20 active SDK sessions.

The browser can revoke one or all SDK sessions, including approved requests
that have not yet issued a session. Every SDK request checks revocation, expiry
and account blocking. Browser cookie/origin authorization remains separate from
SDK bearer authorization. Builder, review, installer and firmware authority are
not granted by an SDK store session. Existing SDK download routes retain their
public behavior.

SDK credentials use explicit macOS Keychain, Windows Credential Manager or Linux
Secret Service backends through pinned keyring 25.7.0; no plaintext/plugin-store
fallback is enabled. Account switching revokes the prior session when reachable.
Logout retains the local credential if remote revocation cannot be confirmed.
Local project links require matching manifest ID and current server ownership;
absolute locations are indexed only on the host, separated by account/origin.
Link metadata and local paths are excluded from source submissions.

Validation:

- Full host suite: **743 passed**, two expected private DTB/DTS skips and
  **280 subtests**, 186.38 s. The final focused account suite has **22 passes**,
  including subsequent default-HTTPS-port normalization and truncated-HTTP error
  handling. It covers lost polls, backoff, denial/timeout/cancel, storage failure,
  account switching, expiry/logout, scopes, pagination and local link boundaries.
- Full website suite: **440 passed**, one explicit optional real-SDK fixture
  skip, 13.52 s. The eight new Worker/D1 cases cover GitHub return/PKCE, code
  approval, credential hashing and replay, separate browser/SDK authorities,
  complete owned-app/history pagination, session limits/expiry, revocation and
  cancellation racing issuance. Website build and lint pass.
- Both existing developer-app browser tests pass. The new cross-repository
  journey runs the **actual Python CLI, Worker/D1 and browser over verified
  local TLS** with two synthetic GitHub accounts. It retrieves **55 owned apps
  and 52 releases**, links a project, rejects foreign ownership, revokes access
  in the browser and checks account switching/local-index isolation. Bad TLS and
  redirects fail without forwarding credentials. Command output contains no
  SDK credentials. Desktop/mobile approval and access pages were inspected.
- The same journey passes with SDK modules loaded from a relocated source kit.
  Two archives are byte-identical and **239 file hashes** verify. Archive SHA-256:
  `bda7752f26370a3fd047562b75a94875db29c64d4af508b3c4e348c624aea006`.
  This kit uses installed host Python and a test credential backend; it is not
  a frozen executable, bundled-newlib, native keychain or clean-host qualification.
- Source collection now includes the installed keyring dependency closure and
  its notices. The frozen launcher has a multiprocessing main guard, and desktop
  packaging names the platform keyring backend. A new frozen candidate has not
  been qualified. Public source boundary and whitespace checks pass.

Final SDK source identity:
`0c9b91ac63a6a9a662a285e1c525959501010910d3897e9c8d5c6d5416fb65df`.
The website report is `.local/sdk-account-journey-kit-final/report.json`, SHA-256
`c1c0d4115127d8a8f2992efc29f759957c1351391714080c445fec8b5229c549`;
its recorded SDK and website source hashes match the working trees. OS logs and
kit reports are under `build/sdk-accounts*`; website logs use
`.local/sdk-accounts-*`. No firmware changed in this batch.

Failed runs are retained: a history fixture supplied an extra SQL value; the
first SDK route intercepted public SDK downloads; and the browser harness did
not intercept a redirect-chain hop to GitHub. The final harness models GitHub
inside the local TLS fixture and blocks external browser requests. An initial
website run timed out in two unchanged recovery tests while the host suite ran;
the complete website suite passed after that competing work finished, without
relaxing those tests' five-second limit.

Remaining account acceptance includes real GitHub configuration, platform
credential stores, frozen/clean host bundles and the full folder-publication,
resumable-upload, immutable-version and website-edit conflict journeys. The
matching website migration is local only. No real account authorization,
production migration, deployment, publication, device operation, commit or push
was performed. The full SDK objective and all unfinished milestones remain open.

The read-only account evidence snapshot at `build/sdk-accounts/evidence`
contains 1,115 source/report/log/artifact files (8,101,345 bytes), including
both public source trees, the relocated kit and reviewed browser frames.
Every copied file hash was checked. Its index SHA-256 is
`1f0c41a57a2a4dbb092cfd963b0633fca79076aa2b7ed82c619670f2f176e46f`;
the snapshot contains this ledger before this annotation.

## Folder publication snapshot and exact-package dry run — 2026-09-13

The local SDK now implements `publish --dry-run` as documented in
[the publication guide](../sdk/PUBLISHING.md). New projects have `store/`
metadata/description/notes and screenshot instructions; authors supply actual
icon/screenshots and explicitly enable source publication. All `.lefony/`
metadata, credentials, workspaces and attempts are ignored by new-project Git
configuration and excluded from source collection.

The command snapshots allowlisted source/configuration/resources/replays and
listing inputs before compiling or testing. It pins an absent SDK lock only in
the copied project and rejects an existing mismatched lock. Its release package
is the exact file tested through the normal ARM path. A complete attempt binds
source, package, bounded local report, normalized icon and ordered screenshots
with sizes/hashes in a version-1 submission manifest. Re-verification checks
artifact digests and relationships to the retained input proof. Later edits to
the original project do not change the attempted release. Local logs, runtime
reports, paths and captures are excluded from upload artifacts. No account or
network client is loaded by the dry run.

The SDK and website share a 55-case metadata/media/submission corpus. Tests use
the real Worker PNG parser and require identical normalized image hashes,
including stripped ancillary metadata. UTF-16 text limits, source permission,
repository links, image dimensions/CRC/filter/decompression, file bounds/order
and unknown fields are covered. The website manifest module is a candidate for
future endpoint integration; it does not itself authorize or publish releases.
Replays now discover nested `tests/` JSON files, within the existing 32-case cap,
so publication cannot silently omit a nested author scenario.

Validation so far for this batch:

- Full host suite: **836 passed**, two expected private DTB/DTS skips, 180.28 s,
  in `build/sdk-publish-full-host-1.log`. The final focused publication suite
  has **95 passes**, including three additional cross-file integrity cases
  added after the full suite collected tests. Symlinks, FIFOs, path/case issues,
  oversized/private inputs, failed/skipped/mismatched tests, changed source/
  package/dependencies and tampered retained files fail closed.
- Shared publication/SDK website contract suites: **222 passed**, including the
  55 new publication cases. Website build and lint pass. Logs use
  `.local/sdk-publish-*` in the website checkout.
- The real CLI dry-run journey passes with IP network access denied on macOS.
  It obtains an actual ARM app frame, prepares two independent attempts, and
  runs both the original Goodix/keypad replay and a nested replay in each.
  Both attempts have identical submission/source/package hashes. It checks
  missing-media preflight, private-file exclusion and retained attempts after
  original source/listing edits. Report:
  `build/sdk-publish/snapshot-arm-1/report.json`, SHA-256
  `5328d1cf3179e82070f99c48f635af07908071d17ab3edbdb52940d1e8f41cf1`.
- Desktop and mobile HTML previews were rendered and visually inspected. Both
  PNGs load, literal HTML remains escaped, and neither viewport overflows.
  Captures are beside that report. The icon is a deliberately cropped real
  app-frame fixture, not proposed release artwork.

The ARM submission SHA-256 is
`d74700a0ef9fdb599a26cc1ccb75dbbbe41aa68a3e9a12eaaa651ed9231b6f43`;
the exact unsigned package SHA-256 is
`7663307185f25a8ec0cad8276e5c72c784e2f95dd1765bf44e0ed38dc004c543`.
SDK source identity is
`e5d77bc23faed68953f145c52e04213abecf416bd2b65e04f4099cb58eaf5765`.
The journey uses the unchanged API 11 VM firmware
`b602aa6982ae508bb2bc3f14021971f85e00a186e9beb92a09d344cec3fbd70c`
and QEMU `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
No firmware changed in this batch.

Initial failures are retained: one host fixture used the wrong template replay
filename and another attempted to create two case-colliding files on macOS;
the latter now exercises serialized source validation on every host. The first
website typecheck found an `unknown` narrowing issue in the text validator;
using a separate trimmed string fixes it. These failures were resolved without
weakening validation.

Remote SDK publication remains unfinished. The next work is bounded staging,
resumable/idempotent transfer, exact-byte finalization with current authorization,
immutable higher versions, shared listing revisions, website/SDK conflicts and
metadata/media pull-and-merge. Native hosts, private-key management, remaining
storage/UI/library/app work and all physical/independent release gates remain
open. No real account authorization, production migration, deployment, store
publication, device operation, commit or push occurred in this batch.

Final batch validation: the full website suite has **495 passes and one expected
optional real-SDK fixture skip**, 13.01 s. The final relocated-source-kit ARM
journey also passes with IP networking denied, including nested replays and two
byte-identical submissions. Its report is
`build/sdk-publish/snapshot-kit-final/report.json`, SHA-256
`0ae2ea534265dce874f6e3ddf4ea8c17e00e3b6e09b506239309067ac26c9b5b`.
The relocated and checkout journeys have identical submission and package
hashes. The final SDK source identity matches both reports.

Two independently generated source archives are byte-identical; **249 file
hashes** verify after relocation. Archive:
`build/sdk-publish/kit-final/sdk.tar.gz`, SHA-256
`7a87c2668efbcef18c4c93c63f552134c0fccc440a93f6ab56d79cf0475e8bf7`.
This kit uses installed host Python/compiler/QEMU and the basic callback app;
it does not qualify a frozen executable, newlib app publication, native Windows
or a clean host. The shared corpus copies are identical, SHA-256
`5924d1dd12a51cb5824c005eb1e6bf6b691a9a00f3e3e284a9daec99fb1774cf`.
The public source boundary passes for 940 files and both Git whitespace checks
pass. Local publication preparation has evidence; remote publication and the
full SDK objective remain open.

Frozen evidence is retained read-only at `build/sdk-publish/evidence`: 1,225
source/report/log/artifact files, 14,602,788 bytes, all copied hashes verified.
The index SHA-256 is
`e545039d5efa6c3ced73c7dbd827bc1583cefd435b144c7c39c90a93c9875b11`.
It includes both source trees, the relocated kit, exact attempt artifacts and
reviewed browser captures before this annotation and the website guide-link
addition. All 121 relative targets in the touched OS SDK/status/ledger guides
were checked. This records the completed local-preparation step only; the
remote publishing workflow and full SDK goal remain active.

## Resumable store backend checkpoint, 2026-09-13

The website repository now has a local D1/R2 upload candidate. SDK sessions can
start/resume an account-owned immutable submission, upload hashed chunks, seal
each verified file, query/cancel staging and finalize exact package/source/media
bytes. Finalization signs the unsigned package and checks current session
authorization, ownership, listing revision and a strictly higher numeric version
inside the atomic release transaction. Durable receipts make accepted retries
idempotent. Bounded leases and separate artifact generations prevent a failed
attempt's cleanup from deleting the successful release.

The implementation also resolves signed downloads through their recorded
artifact prefix and keeps numeric version ordering consistent with browser
submissions. Revision tracking preserves public fallback metadata while a
different listing is pending. Existing browser submission remains usable; its
full stale-edit checks and metadata/media merge workflow are not implemented.

Validation uses Miniflare with all migrations, synthetic SDK sessions, signing
keys and app fixtures. The **21 upload tests pass**, covering missing chunks,
lost storage acknowledgements, whole-file corruption, report/source/media
rejection, competing publications, revocation/expiry/blocking at commit,
withdrawal during finalization, superseded leases and retained-release cleanup.
The full website suite passes **516 tests with one expected optional real-SDK
fixture skip**, 13.14 s. Build/typecheck and lint pass. The OS public boundary
passes for 940 files; 76 relative documentation targets and both repositories'
Git whitespace checks pass. No firmware or SDK runtime code changed here.

The first full regression run exposed an existing rate-limit fixture's wall-clock
dependency: its requests crossed a minute boundary. The test now fixes the
ephemeral Worker's clock, leaving production rate limiting unchanged. That
failure and the final logs remain in the evidence snapshot.

Verified source/configuration/test/log copies are retained read-only at
`build/sdk-upload-backend/evidence`: 120 files, 1,314,188 bytes. The index SHA-256
is `3b727c318ae885b8b9303e1d7b46ada757bce61cf8ff120e432da33dd8088ac3`.
This identifies the local backend checkpoint, not a deployed or downloadable
SDK. The SDK still requires `publish --dry-run`; its upload/resume/update and
withdrawal commands, shared website edit conflicts, metadata/media pull-and-merge,
real prepared-ARM-artifact upload journey and production operational qualification
remain open. The backend neither rebuilds source nor independently runs author
tests. Native hosts, private keys, remaining storage/UI/library/app work and
physical/independent acceptance still block full SDK completion. No deployment,
production migration, real account authorization, device operation, commit or
push occurred.

## CLI publication and recovery checkpoint, 2026-09-13

The SDK now provides explicit `publish` in addition to offline `--dry-run`.
It captures the local project, builds/tests the exact release package, binds the
attempt to the current store/account/app, transfers missing hashed chunks and
finalizes the verified submission. `publish --resume ATTEMPT_ID` consumes saved
inputs without rebuilding; `--status` and `--cancel` query or cancel staging.
Local project and remote attempt identities are retained before transfer,
without credentials or uploaded host paths. Process-owned advisory locks prevent
concurrent publication operations on one project and release on process exit.

The first explicit link records the observed listing revision. Successful
publication records the exact commit revision; repeating link or replaying an
older receipt does not silently advance it. Stale website changes stop updates.
The backend now retains `publication_revision` separately from the current
revision and offers read-only receipt lookup after staging cleanup. Status and
cancellation do not require new publication to remain enabled. A local tracking
write failure after remote acceptance is reported alongside the accepted release.
Missing, unaccepted remote staging requires a fresh reviewed attempt.

The new paired CLI/Worker integration harness uses real verified local TLS,
isolated D1/R2, synthetic accounts/signing keys and memory credentials. Its first
journey builds and tests two ARM versions, deliberately loses three acknowledgements
after a chunk was committed, resumes without changing bytes, verifies that signed
downloads contain the exact tested packages and source, rejects another account,
detects a website withdrawal and retrieves durable receipts after staging rows
are removed. It exercises actual CLI commands; the server does not rebuild or
independently execute the app. The original cropped app-frame listing fixture
remains test artwork, not proposed release artwork.

Validation: **853 host tests pass with two expected private-fixture skips**,
180.09 s. Final account/snapshot/upload tests pass **132 cases**, including the
removed-staging recovery case added after full-suite collection. The full website
suite passes **518 tests with one expected optional real-SDK fixture skip**,
13.28 s, including 23 backend upload cases. Website build/typecheck and lint pass.
The public source boundary passes for 943 files and 120 relative documentation
targets exist. Firmware and app runtime interfaces are unchanged in this batch.

The next publication work remains SDK withdrawal, listing diffs and metadata/media
pull-and-merge, and complete alternating website/SDK editing. Native credential
stores, clean hosts, frozen bundles and deployment remain unqualified. The full
SDK goal still includes remaining storage/UI/library/private-key/app work and
physical/independent release acceptance. No live-store publication, real account
authorization, production migration, deployment, device write, commit or push
occurred in this checkpoint.

Final relocated-kit evidence:

- SDK source identity:
  `9416539b59c9755b5a0c6dfb8bd4b8f305937cf46ee0c15fe60e8c01f5846931`.
  It matches the checkout and the identity recorded by both fresh ARM releases.
- Two independently generated archives are identical; 250 extracted file hashes
  verify. `build/sdk-upload-client/kit/sdk.tar.gz`, SHA-256
  `aff6a43cd63628e82cc9414ac4c1d2cd2be5efc3bc85751076fc561d83e531a4`.
- Website `.local/sdk-upload-client-kit-final/report.json`, SHA-256
  `5684e4ac1a8ed5638fd963defddfc4efde5b5b1974dab26d2810ddf07b1ff1f4`;
  its CLI/ARM report at `cli/report.json`, SHA-256
  `592220f3519f501c6170b762c78644da596bbb93c067a0211d13a83a140de9a6`.
  The two unsigned package hashes are
  `058e541ad6dc67fe15ee03cfedbee1f289fe688decb7930bdb0f9b8d917fa7de`
  and `ac2f8b08b10f71d237919a9bc26995d8b3fa6b84fd636d47963776839a56a3c3`.
  Each exact package passes two author replays and is verified inside its signed
  store download. Both versions are withdrawn through the fixture website.
- The same relocated kit also passes the controlled GitHub/browser/TLS account
  journey: two accounts, 55 owned apps, 52 history entries and revocation.
  Website `.local/sdk-upload-account-kit-final/report.json`, SHA-256
  `7623e902db371510d321a07f26fd86747adf33835fd05ef429ec6cdc499b1c55`.

These source-kit checks use installed host Python/compiler/QEMU and the unchanged
API 11 VM firmware. They do not qualify frozen executables, clean hosts, native
Windows, the platform credential stores, newlib-app publication or physical
operation. The archive includes this checkpoint before the final evidence
annotation; its executable SDK sources match the recorded identity.

Read-only evidence is retained at `build/sdk-upload-client/evidence`: 1,381
source/report/log/artifact files, 14,563,384 bytes, all copied hashes verified.
The index SHA-256 is
`71e662052406507c87850f068119f7a0ea3543a03af087dbaef9612e07ad4e88`.
Both Git whitespace checks and the public boundary pass after documentation
updates. The full SDK objective remains active.

## Listing snapshots, SDK merge and browser conflict review — 2026-09-13

The matching store now offers owner-only listing snapshots and historical image
reads for SDK and browser sessions. Snapshot content and revision come from one
D1 batch; delayed R2 metadata reads cannot attach a newer revision to old text.
Withdrawn and hidden apps remain readable by their owner, while public downloads
retain their existing availability rules. Browser submissions persist release
notes/repository URLs and check the author's observed revision and active session
again inside the atomic release commit. Existing-app updates without a revision
are rejected; old callers can still create an unused app ID.

The SDK adds `listing pull`, `listing pull --dry-run`, saved-plan application with
per-field local/remote conflict choices, and offline `listing recover PLAN_ID`.
The three-way merge covers name, description, release notes, repository URL,
icon and ordered screenshots. New links and accepted receipts retain exact
baseline content; older revision-only links use conservative conflicts. Remote
images are owner-scoped, bounded, digest-checked and PNG-validated. Applying a
review rechecks the account/app, exact remote snapshot and raw local file hashes.
It preserves source-sharing permission and changes only the manifest name and
listing files selected by the merge. The baseline records remote content, not
the merged draft. Interrupted writes retain a journal and block publication or
relinking until recovery; recovery refuses to overwrite later user edits.

The browser form now compares its current text/images with a saved listing,
copies selected fields and explicitly accepts the reviewed revision. It can
reuse saved media without selecting local files again. Reselecting source alone
does not acknowledge an intervening edit. A successful publication starts a new
baseline when the next source is selected. Account changes remount the form;
pending image work cannot update another account's form. Desktop/mobile review
captures were inspected, and the 11-case browser suite passes.

Validation so far: the full OS host suite passes **869 tests, with two expected
private-DTB skips**, in 181.51 seconds. That run precedes a subsequently found
maximum-Unicode review-size fix: a new test reproduced the 64 KiB read-limit
failure, and the bounded review limit now covers two escaped maximum-size
listings. The final account/publication/upload/merge suites pass **148 tests**,
including 16 merge cases. The full website suite passes **520 tests with one
expected optional real-SDK skip**, using `npm test -- --maxWorkers=2` (24.90 s).
An earlier unrestricted run timed out in the unchanged five-second recovery
download test; its isolated 12-case suite passes, and no recovery code or timeout
was changed. Website build/typecheck and lint pass after final UI edits.

A paired CLI/Worker/TLS journey already passed two SDK releases and a third
ARM-tested website update, explicit listing conflict resolution, remote icon
retrieval, local-description retention, website notes import, source-permission
preservation, withdrawal and receipt lookup after staging cleanup. The first
attempt stopped correctly when SDK inputs changed during ARM testing; subsequent
runs use an extracted fixed source kit. Final-kit evidence follows below.

Remaining publication implementation: metadata-only revisions distinct from
immutable releases, SDK withdrawal and further alternating-edit acceptance.
Native credential stores, clean Windows/macOS/Linux hosts, complete companion
bundles, private app-key management, remaining storage/UI/library/app work, and
physical/independent qualification remain open. No SDK milestone or full-goal
completion is claimed. No production migration/deployment, real account grant,
calculator write, commit or push occurred. Firmware/runtime interfaces are
unchanged by this checkpoint.

Final listing checkpoint evidence:

- SDK executable-source identity:
  `ca8ee33d8e536a6b31365e90ae1edcf7bcb8c603e1312db4da344196e6866987`.
  The checkout, extracted kit and three fresh ARM release reports agree.
- `build/sdk-listing/final-kit/sdk.tar.gz`, SHA-256
  `a72a15051ba8070a8107be51ac14fa964ec985ac43cebfcb6f3444103554ec89`.
  Two independently generated archives match, and all 251 extracted file hashes
  verify. This archive predates this ledger annotation; its executable SDK code
  is exactly the tested code.
- Website `.local/sdk-listing-final-publication/report.json`, SHA-256
  `dd11cb60f75b8c719bd52def5cc4a1c99cbb490cbba9442061640869f277c71f`.
  The actual CLI report at `cli/report.json` has SHA-256
  `ca2e64d149df7c0a761d6465f3be269bbc0fd91b52b30c19c783785024a3300b`.
  All 17 CLI steps pass. Versions 1.0.0, 1.1.0 and 1.2.0 each pass two normal
  ARM input scenarios, and signed store downloads retain the tested payloads.
- The unchanged API 11 VM ELF is
  `b602aa6982ae508bb2bc3f14021971f85e00a186e9beb92a09d344cec3fbd70c`;
  QEMU is `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
  These SDK/store changes do not qualify a new firmware image or physical board.
- The same final kit passes the controlled GitHub/browser/TLS account journey,
  including two accounts, 55 owned apps, 52 history entries, linking and revocation.
  Website `.local/sdk-listing-final-accounts/report.json` has SHA-256
  `eaa736e5793e748a989135d89d82adf7e53bf69654f9cfe1dd62371be60269ee`.
  Source-kit tests use installed host dependencies and synthetic memory credentials;
  they do not qualify native credential stores or frozen host executables.
- Final website build/typecheck and lint are clean; the 11-case browser suite
  passes after account-form isolation and the bounded media helper refactor.
  The public source boundary passes for 945 files, both Git whitespace checks
  pass, and 78 relative documentation targets in the changed guides resolve.

Read-only evidence is retained under `build/sdk-listing/evidence`: 1,172
source/report/log/artifact files, 8,741,010 bytes, with copied hashes verified.
The index SHA-256 is
`585af20174ee5ab732081ebab526ec773c7b3cd63c0b2d2149178f7c66f3bf8f`.
It captures public sources before this final evidence annotation. All jobs from
this checkpoint have completed; the full SDK goal remains active.

## Metadata-only edits and SDK withdrawal — 2026-09-13

`listing push` now updates the linked project's store name, description, notes,
repository URL, icon and ordered screenshots without compiling or uploading a
package/source archive. Its authenticated `--dry-run` returns a field comparison.
Unchanged owned images use digest references; missing local media is rejected.
Source-sharing permission is preserved. Stale revisions require listing review
and pull/merge. The exact request, account/app/origin and digest are saved before
submission. `--status` reads the original receipt; `--resume` uses saved bytes
after later local edits. Receipt validation and local baseline updates cannot
acknowledge later remote changes or roll back a newer local baseline.

`apps withdraw APP_ID` requires no local source folder. It saves an isolated
host operation journal, checks the observed revision and withdraws all active
releases in one commit. History, reviews and installed copies remain. Replaying
an accepted withdrawal leaves subsequently published releases available. Status
and withdrawal work while publication is paused. New releases still require a
higher unused version and explicit source permission.

The matching website adds immutable listing-operation receipts and per-release
metadata/media revisions. Catalog and owner reads select matching text/media
in one D1 snapshot. New executable releases start with their submitted listing;
original release bytes, metadata and feedback are preserved. Edited calculator
icons are signed against the exact unchanged signed package. The browser editor
offers the same presentation fields, preserves existing media after an invalid
replacement and handles SDK conflicts through explicit review. Failed saves keep
their exact request for retry/status while the page remains open. Browser drafts
do not survive closing the page; SDK journals survive process exit.

Validation:

- Full host suite: **884 passed, two expected private-DTB skips**, 184.89 s,
  `build/sdk-metadata-full-host.log`. Focused SDK mutation/merge/upload suite:
  **45 passed**, including 15 new mutation cases.
- Full website suite: **530 passed, one optional real-SDK fixture skip**,
  `npm test -- --maxWorkers=2`, 31.62 s. Two subsequently added mid-transaction
  rollback cases and the retired-key checks pass in the final **37-case** backend
  suite, `.local/sdk-metadata-operations-final-2.log`.
- Website build/typecheck and lint pass. Browser publication/editor suites pass
  **15 cases**, 21.4 s; mocked calculator installation/icon tests pass **four
  cases**, 6.9 s, including the edited icon route for an already installed app.
  Desktop/mobile metadata-editor captures were visually inspected.
- Both Git whitespace checks pass, the public boundary passes for **947 files**,
  and **90 relative documentation targets** in the changed SDK guides resolve.
  Firmware/runtime code is unchanged by this checkpoint.

The paired actual CLI/Worker/TLS journey passes **28 CLI steps** and four freshly
ARM-tested versions. Each version passes two normal-input scenarios. It loses
three committed chunk acknowledgements and three committed listing-edit
acknowledgements, recovers exact saved bytes, alternates SDK/browser metadata
edits, withdraws versions 1.0.0–1.2.0 and publishes 1.3.0. Replaying the earlier
withdrawal leaves 1.3.0 available. Signed downloads retain the exact tested
payloads; original receipts survive staging cleanup. The first harness run
stopped because its new Markdown assertion omitted the normal trailing newline;
the corrected assertion and complete rerun pass without changing SDK behavior.

- SDK executable-source identity:
  `69d2caa62e9e338bc67709be39ee31d8c71b5ebc967c365b29e289d595163295`.
- Tested relocated source kit: `build/sdk-metadata/kit/sdk.tar.gz`, SHA-256
  `ed92de997202549df24408c6fe121e83d6a5c8088dc1b6c868c1eb3481283b7c`.
  Two archives are byte-identical and all 252 extracted file hashes verify.
  This archive predates final guide/ledger annotations; executable SDK inputs
  remain identical to the checkout and every ARM release report.
- Website `.local/sdk-metadata-publication-final/report.json`, SHA-256
  `f41ddf4f588c0f0d40a0eb7820d3a6b7527bd788cb922e3894099d7b2092d8ac`.
  Its CLI report `cli/report.json`, SHA-256
  `ac247802a68f8b895dbac393dab63b6d0dd2dc15c59a15de2ec385710ba308fa`.
- The unchanged API 11 VM ELF is
  `b602aa6982ae508bb2bc3f14021971f85e00a186e9beb92a09d344cec3fbd70c`;
  QEMU is `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.

These are local candidates using synthetic accounts/keys and memory credentials.
Rejected/interrupted edits may leave unreferenced immutable PNG objects;
production media reclamation/capacity and operational qualification remain open.
Native credential stores, clean Windows/macOS/Linux hosts, complete bundles,
private developer keys, remaining storage/UI/library/app work and independent
and physical acceptance still block the full SDK goal. No production migration,
deployment, real account grant, calculator write, commit or push occurred.

Final metadata checkpoint packaging: `build/sdk-metadata/final-kit/sdk.tar.gz`,
SHA-256 `c1659cfd23a9619f5110498bbbc4738d8e0ffd1777c3961c8661b86804915ea8`.
It includes the updated guides and preceding ledger entry. Repeated archives are
identical, all 252 extracted hashes verify, and its executable SDK identity is
identical to the checkout and the successfully exercised source kit. The final
archive does not include this self-referential hash annotation.

Read-only evidence at `build/sdk-metadata/evidence` retains 131 source, archive,
report, log and screenshot files, 2,174,375 bytes. All copied hashes verify; its
index SHA-256 is
`da7b214c48912389276329380d279e3cfe6d1c1d539fb445e9e4de7129af5a6b`.
The final public-tree and whitespace checks pass. The full SDK goal remains active.

## Developer-key registry and durable trust records — 2026-09-13

The internal [developer-key candidate](NATIVE-APP-DEVELOPER-KEYS.md) now implements
bounded enrollment/revocation proposals, canonical RSA public-key identities,
retained revoked keys and a durable littlefs transaction engine. A stale observed
serial cannot mutate trust. Exact repeated operations are no-ops; full tables
preserve retained keys; serials cannot wrap. Invalid/unknown canonical files fail
closed and cannot be reset by a normal enrollment request.

Writes use a fixed pending file, checked close, complete byte verification,
atomic rename and canonical readback. Cancellation is allowed only before rename
starts. A failed rename/readback clears cached developer authority until the
canonical file is reloaded, because the commit outcome may be unknown. The root
is separate from app namespaces and survives the existing startup/pruning path.
No app file, package, volume geometry or firmware trust root is changed by a
registry operation.

`Table::unwrap` distinguishes execution from inspection. Revoked keys cannot
authorize execution but can still verify authentic retained packages for future
catalog/data-export callers. Both purposes use the complete existing LFAPP1/RSA
checks, now factored into `NativeAppSignature::unwrapWithKey`. The ordinary
`unwrap` still uses only compiled app roots plus the explicit emulator fixture
on emulator builds. Constructing a developer table does not expand that trust.

This engine is compiled for both targets but is not yet loaded or exposed by the
running OS. Live enrollment still requires the OS approval UI, USB/SDK commands,
exclusive AppManagement storage integration, catalog/export-versus-execution
callers and app-signer ownership/recovery policy. In particular, adding a key
must not silently allow it to replace another signer's installed app or take
over its retained data. These remain implementation work, not qualification-only
items. No private-install capability or SDK milestone is claimed complete.

Validation at this checkpoint:

- The focused registry/signing/storage/document suites pass **14 tests**, 42.43 s,
  `build/sdk-developer-keys/focused-tests-final.log`. An additional registry run
  after adding repeated key cycles and normal startup coverage also passes.
- The final ASan/UBSan fixture passes **80 full/torn interruption cases**,
  **17 cancellation boundaries** and **172 backend read-failure cases**. These
  include 9 load failures, 147 failures before commit and 16 uncertain failures
  after commit. Every remount selects the exact old or new table, and an unrelated
  installed app/data pair remains readable. Full media, corrupt roots, stale
  pending files, duplicate keys, malformed records, serial overflow, capacity and
  real signed-package tampering are covered. Public fixture key fingerprints and
  wire bytes agree with Python/OpenSSL. The retained key is never implicitly
  trusted by the compiled-only physical policy.
- Both physical and VM targets compile. The initial physical build caught an
  unavailable `UINT32_MAX` macro in the firmware's minimal headers; the checked-in
  code now uses the explicit 32-bit limit, and both full rebuilds pass. That
  failed build log is retained. Existing upstream build warnings remain.
- The Cortex-A7 compiler reports a **2,600-byte Table** and **8,028-byte Store**;
  the host Store is 8,064 bytes. A compiler stack report is retained, including
  2,920 bytes for `beginEnroll` and 2,656 bytes for `decode`. These are individual
  static frames, not measured complete call-chain peaks or physical timing.
- The current VM passes **38 runtime cases**, including isolation, protected
  memory, faults, timeouts, drawing, discovery and input. The signed ARM/USB data
  recovery journey passes **8 cases**: initial backup/restore, cold restore,
  update rollback, cold rollback, and rejection of bad signatures, wrong app IDs,
  wrong schemas and unsupported runtime requirements. These regressions exercise
  the refactored signature verifier; they do not exercise a live developer-key UI.

Exact artifacts and reports:

- Physical ELF `dist/lefony-os-prime-g2-developer-keys-physical.elf`:
  `76fefb8cdfaf8888c939da8029af19dd306fdc77ade2ea1a63005b276323f27e`.
  Physical BIN:
  `dc1082360c0a87307d0d68aa618de800bd7247e402a875a9ebccb91927cdfe92`.
- VM ELF `dist/lefony-os-prime-g2-developer-keys-vm.elf`:
  `e1d67150bfc222d6003af3df8731029363273b32a890c9d4aaa9f09faabe871f`.
  VM BIN:
  `17566eb1cb711ef3da44ee56b66b5a0651258d170a4110cc7ec6cbd8739f3bff`.
- QEMU remains
  `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
- `build/sdk-developer-keys/storage-report.json`:
  `b593099bfd3b53d3a09543092b7bc7f92ddf75e6c3b021cdd1830eb22674b5cd`.
- `build/sdk-developer-keys/arm-recovery/report.json`:
  `bd58012d06c7e8fbc3fd4a86c5a9f9e5b3a7a11d88e707ec74562da775be65e9`.
- `build/sdk-developer-keys/arm-runtime-report.json`:
  `5d51aad2b5d5bab4de6a8b9d31ded75615d60bffb8fff57f87b7bb439c53a712`.

Validation uses synthetic NAND and the public emulator key fixture. The physical
build reused the existing release public key and generated no signing identity.
No device write, production deployment, commit or push occurred. The full SDK
goal remains active, including the remaining storage/UI/library/host/application
work and independent/physical qualification.

Final checkpoint checks: **885 host tests pass, two expected private-DTB skips**,
185.65 s, `build/sdk-developer-keys/full-host.log`. The public source boundary
passes for **952 files**, all **84 relative documentation targets** in the four
changed guides resolve, and Git's whitespace check passes. The final full suite
includes the added repeated-key-cycle/startup-preservation cases. No jobs from
this checkpoint remain running.

Read-only evidence under `build/sdk-developer-keys/evidence` retains **47 files**,
**13,224,643 bytes**, including exact sources, both firmware targets, host/ARM
reports and the initial failed build log. Every copied hash verifies. The index
SHA-256 is `90f291d3d6efa6dafe1b84d6c3231d961f6df8b772db70b749c1cd70a763aa5b`.
Its ledger copy precedes this self-referential evidence annotation.

## Live private installation and per-app signer recovery — 2026-09-13

The [private-install workflow](../sdk/KEYS.md) now includes OS-approved public-key
enrollment/revocation, `keys status/list/cancel`, signed `install` with complete
readback, and explicit `install --recover-signer`. This supersedes the preceding
registry-only checkpoint's missing live integration. The SDK source and firmware
are local candidates; existing downloads do not contain this implementation.

AppManagement loads the registry under its existing exclusive filesystem owner.
The normal loader and installer require active authority; catalog and data-export
callers can authenticate retained revoked-key packages. Unavailable packages are
quarantined without blocking unrelated authenticated apps or allowing a new
signer to claim their namespace. Ordinary developer updates retain their signer;
compiled store keys retain their existing shared publication authority.

Consent is an OS screen entered from Home through deferred normal event dispatch.
It binds the exact key/operation, random host nonce and observed registry serial,
expires after two minutes, and requires a rendered screen, a fresh all-keys-up
scan and physical OK alone. Back/Home/power and USB disconnect cancel pending
approval. Neither an app callback nor a USB request can supply consent. Firmware
keys, compiled store keys and the public emulator fixture cannot be enrolled as
private developer identities. Terminal results refresh the catalog even when
approval/cancellation finishes outside the ordinary polling step.

Lost-key recovery applies to one authenticated installed app under a retained
revoked developer key. The new signer must already be enrolled and active. The
OS displays both full fingerprints, the app ID/version and exact signed-package
SHA-256. Approval also binds the saved-data generation; package and installed
identity are rechecked before any upgrade write. Recovery requires a strictly
higher version, respects the version high-water mark and rejects unresolved
pending upgrades. It cannot take over store apps or unknown/damaged namespaces.
The old key stays revoked. Named files/private bytes and the previous compatible
package/data pair use the existing transaction and upgrade-acceptance policy.
A legacy byte store is converted after approval before its retained upgrade;
an interrupted conversion can leave the representation converted while preserving
the old package, signer and user bytes.

Host discovery adds flags 256 (keys) and 512 (per-app signer recovery), with fixed
commands `0x80`–`0x84`. Recovery operation 3 uses reserved request/status bytes for
the package hash; other operations require them to remain zero. This changes no
app API revision, ABI layout, package format, NAND geometry or firmware trust root.
Host waits and cancellation are bounded and operation-bound; uncertain results
never cause an automatic write retry or a claimed rollback after commit.

Validation exposed an additional upload-lifecycle gap: a USB reset before the
key request could strand AppManagement in Receiving. Disconnect now releases
uncommitted upload buffers while preserving an acknowledged pending install.
The corresponding physical/VM rebuilds and precisely scheduled USB status/reset
checks pass. Restricted install transports include the existing upload-abort
command without acquiring firmware or raw-storage commands.

Final validation:

- **911 host tests and 280 subtests pass**, with two expected private-DTB skips,
  193.07 s: `build/sdk-signer-recovery/full-host-final.log`. The earlier focused
  registry/controller/host/signature run passed 33 tests. A subsequent protocol,
  architecture and compatibility run passed 146 tests, including preservation
  of the package contract's leading-zero version spelling.
- Both physical and VM targets compile. The first physical attempt exposed the
  firmware's C++11 aggregate-initialization constraint on callback members;
  the fixed source compiles on both targets. The failed log is retained.
  Existing upstream linker warnings remain.
- The final **21-case signed ARM/USB journey** passes through five cold-boot
  phases. It covers normal OS consent, CLI status/list, private install/save,
  cross-signer takeover rejection, revocation/export/cold reopen, reactivation,
  ordinary updates, rejected active-old-key/same-version/hash/store/new-ID
  recoveries, Back and USB-reset cancellation, partial/complete upload reset,
  actual CLI lost-key replacement and later updates under the replacement key.
  A second signer replacement retains both private bytes and a **68,896-byte
  named file**, with byte/hash verification after cold reopening. That file's
  SHA-256 is `dddf8b1153028a8ce33ff9d5db4cfa68ba36ca4a5e93c1bcbc4b55fec63f3c81`.
- The final candidate passes **eight ARM private-data/rollback regressions**.
  Two precisely scheduled package-install ACK/reset cases verify that an
  acknowledged install survives reset and an unacknowledged install is discarded,
  with exact package readback. Two equivalent file-COMMIT ACK/reset cases pass.
- The preceding candidate also passed **38 runtime cases** for isolation,
  protected memory, timeouts, faults, drawing, discovery, input and OS response.
  Those results bind VM hash
  `a078d9cfb285d6e561053ba948dfe0a923194e123a80a459709c0adc17a0135b`, before the
  final upload-disconnect correction; they are not a separate full runtime run
  on the final hash. Its ELF and report are retained under this checkpoint.
- Recovery consent screenshots were visually inspected: the app/version, both
  complete fingerprints, complete package hash and action fit the 320 × 240
  screen. Input follows the normal matrix/event route. The initial ARM run
  stopped because its test reused an existing backup output path; the corrected
  harness uses unique destinations and the complete rerun passes.

Exact final artifacts and reports:

- Physical ELF `dist/lefony-os-prime-g2-signer-recovery-physical.elf`:
  `f2eb510169ad9dc69320fde00f71d17f37e9d996859bb358ef3dabf5c2579ac2`.
  Physical BIN:
  `6298947d35fbe388c876bfde2250344c2b0bb506c1baea04fa3cb0345f05d026`.
- VM ELF `dist/lefony-os-prime-g2-signer-recovery-vm.elf`:
  `9269b25657ff6d06f4f9de05e7cdd6678afd8c56bc4c1399ffcd2285e0e006dc`.
  VM BIN:
  `730ef7fefa9c1e895a6bf768974252667ec0221fac826f31b567e1d900cee82a`.
- QEMU remains
  `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
- SDK executable-source identity:
  `a1f36706503685bdd0a7a09fd0da3e43589a33f793299ef43ff12d226abf4e17`.
- `build/sdk-signer-recovery/arm-upload-reset/report.json`:
  `2a456cd371bd33d1b553824b845a102826f8c4897c2bc86672778f7e101fed87`.
- `build/sdk-signer-recovery/arm-data-final/report.json`:
  `e712f6df255fad80f9f0431c41766022da9301440eb459ad47f138409d0e360c`.
- `build/sdk-signer-recovery/arm-install-reset/report.json`:
  `f90dc22c3b34da71ba998754db99dc493d65bd4b466604a9ed522bb661f5da96`.
- `build/sdk-signer-recovery/arm-commit-reset-final/report.json`:
  `26c94b9936d4efbc7f9bfdd9b80b30251c0b91c2c50d06eb8d2ad27ed2e67e89`.

The ARM journey uses synthetic NAND, temporary independent signing keys and
controlled USB; only their public keys and signed test packages are retained.
Temporary private keys are removed when the harness exits. Physical builds reuse
the existing release public key. No physical device write, production deployment,
real account grant, commit or push occurred.

Remaining private-install work includes explicit damaged-registry recovery and
retained-key removal/full-table policy, integrated full/damaged-media and
interruption coverage, complete native bundles and physical acceptance. The full
SDK goal also retains whole-app archive/restore, remaining UI/preview/library/app
work and independent/host/hardware qualification. This checkpoint does not
complete that goal or declare SDK 1.0 qualified.

The final source kit `build/sdk-signer-recovery/final-kit/sdk.tar.gz` has SHA-256
`983bbbfa77d1ab4bc3c29fba1f6dd80352fc7ead9cf28e7a8c98fbdb9105415d`.
Repeated archives are byte-identical and all **255 extracted file hashes** verify.
Its executable SDK identity matches the checkout and final ARM report. From the
relocated kit, key/install command discovery and independent verification of the
actual recovery package pass. This source kit does not bundle the optional
newlib sysroot or establish complete native/frozen-host qualification. It includes
the preceding ledger entry but not this self-referential packaging annotation.

Final public-tree and whitespace checks pass; **98 relative documentation targets**
in the changed guides resolve. Read-only evidence at
`build/sdk-signer-recovery/evidence` retains **188 files**, **19,039,342 bytes**,
including exact sources, firmware, source kit, reports, consent frames and failed
attempt logs. All copied hashes verify. The index SHA-256 is
`20cb4a2ac1565251b689930100a1093fc5856c11665250799a432700a1df1672`.

## Internal whole-app archive restore engine — 2026-09-13

The [archive design and current limits](NATIVE-APP-ARCHIVES.md) now have a bounded
host parser and an internal firmware restore engine. This is not yet a live
backup/restore command. Export, USB sessions, full installed-signer/update policy
and SDK integration remain required work.

The portable format carries current signed code, private bytes and named
files/directories, plus the prior compatible pair when an upgrade is pending.
The host parser validates exact lengths, hashes, canonical paths, directory
parents, bounded entry/extent counts, versions and data schemas. It distinguishes
structural integrity from independently verified package signatures. File hashes
follow streamed contents; no NAND generation/address or developer trust grant
is imported.

The restore engine stages future-generation immutable objects and verifies
unchanged chunks before reusing them. Corrupt old chunks are replaced from the
incoming stream. A new document-store publication path verifies both incoming
pairs and all references, preserves the existing canonical app and every old
object until the atomic rename, and avoids requiring damaged old data to verify.
Cancellation cleans staged objects before commit; a failed commit is uncertain
and cannot trigger deletion of possibly published objects. Version high-water
marks are preserved, including data restoration to identical code after rollback.

An additional engine-level check rejects treating an existing empty, unknown or
damaged canonical file as an absent app. It also checks the supplied root or
legacy generation against the actual canonical namespace before accepting the
operation. The future exclusive AppManagement owner must still authenticate the
installed package independently of damaged data, enforce signing/update/schema
policy, supply quota/admission and recheck its trust/namespace binding at commit.

Validation completed:

- The full host suite passes **959 tests and 280 subtests**, with two expected
  private-DTB skips, in 224.57 s (`build/sdk-archive/host-final.log`). That run
  began before the final canonical-namespace guard; the subsequent final archive
  run passes **48 tests** in 26.51 s (`target-check.log`). The last fixture
  refinement tests restoring the exact same signed code below a retained high
  watermark, rather than suggesting an arbitrary downgrade; that native
  run passes in 24.22 s (`restore-final.log`).
- Production littlefs and the normal synthetic NAND backend pass **430 intact/
  torn interruption cases**, **154 cancellations**, three damaged-index/private/
  named-data repairs, 21 invalid-content/authority/quota/full-media cases and
  eight namespace-binding rejection cases. A subsequent forced filesystem I/O
  failure during rename reports an unknown outcome and retains the staged
  package/index; that final native run passes in 24.07 s
  (`commit-uncertainty.log`). The matrix covers reused chunks,
  newly written files, legacy FILE2 replacement and a two-pair pending upgrade.
  Cold verification accepts only the exact old or new root and preserves an
  unrelated app. The engine reuses 131,081 verified file bytes in the unchanged
  file case and occupies 333,304 bytes on this host, excluding caller-owned
  package scratch and the existing document store. ASan/UBSan are enabled.
- Both physical and VM targets compile the new engine. The first physical
  attempt found unavailable `strcpy`/`strcat` helpers in the minimal firmware C
  library; bounded copies replaced them. That failed log remains in
  `build/sdk-archive/physical.log`. Final logs are `physical-target-check.log`
  and `vm-target-check.log`. The engine is not instantiated by a live archive
  session yet; a successful build does not establish ARM archive execution.
- The final VM passes **eight existing signed ARM data backup/restore/rollback
  regressions** (`arm-data/report.json`) and **38 runtime/isolation/service
  checks** (`arm-runtime-report.json`). These are regression evidence for the
  existing app paths, not an end-to-end archive USB qualification.
- Public-tree and whitespace checks pass. All 72 relative documentation targets
  in the touched status, archive and progress documents resolve. The SDK source
  packager includes the archive guide alongside the automatically included host
  parser.

Exact final candidate identities:

| Artifact | SHA-256 |
| --- | --- |
| Physical ELF, `archive-engine-physical` | `7efa685e5afa0f8313fd532440e4f176264d226d79a82b8a4e97bfbb2463be8f` |
| Physical BIN | `51967525dfecc717453c050a5863a6d9b0d4dc8cf3aa46251f321c1e6271541e` |
| VM ELF, `archive-engine-vm` | `433225cbb9171b5cbd717859c876ef87a8b3519a12e113b4abe7b6af955fab59` |
| VM BIN | `3bd00406ea031f4cf88bd8af6940775e1d3d166c98c745931d7b21b185baea55` |
| Production restore report | `966c5f1482b7ba386b88dbcf2203382917d8c4dbd5a6560ea84213336c1775da` |
| ARM data report | `314d12a47e1c75b3e49cf04157247cf4e7e17bfd49bd50359517b9d428f2e321` |
| ARM runtime report | `52dcebfb497d409f324bc7bfb01f765a7374ca44f57eedb2763c5281176039ee` |

QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
No public USB command, hello flag, app API, package schema, storage geometry or
firmware trust root changed. No device write, commit, push or deployment occurred.
The full SDK objective remains active, including archive/export/recovery
integration, remaining UI/preview/library/key-maintenance work and complete
application, independent-developer, native-host and physical qualification.

The source kit `build/sdk-archive/source-kit/qualified-sdk.tar.gz` has SHA-256
`92aea484c99e2e7d1a0f3a191b46613c1737d8b8822cd9212e61f0b4666fbacc`.
Its 257 extracted file hashes verify, repeated archives are byte-identical, and
the relocated parser independently authenticates a signed archive fixture. It
contains the ledger before the final commit-uncertainty/packaging annotations.
This kit does not include the optional newlib sysroot or establish native-host
or complete SDK bundle qualification.

Read-only evidence at `build/sdk-archive/evidence` retains 390 files totaling
15,715,911 bytes, including exact sources, reports, build logs, firmware and the
source kit. All copied hashes verify. Its index SHA-256 is
`ecf033d6cc92b72754058a11fbdb7b80365da1448afd288c125f1350b9635fa8`.
The captured ledger precedes this evidence annotation.
Its ledger copy precedes this self-referential evidence annotation. All checks
launched for this checkpoint have completed; the full SDK goal remains active.

## Live whole-app archives, SDK commands and damaged-data repair — 2026-09-13

This supersedes the previous checkpoint's missing export/session/CLI integration.
The [archive commands](../sdk/ARCHIVES.md) now expose `info`, `status`, `export`,
`restore` and scoped `cancel`. Archives preserve exact signed code, private bytes,
named files/directories and pending recovery pairs. Exports use bounded reads
and atomic local publication after hashes and signatures pass. Restore validates
one regular file before USB enumeration and retains its open descriptor through
upload; both peers verify the complete stream before explicit commit.

The exclusive firmware session binds app ID, generation, sequence, random host
nonce and trust revision. It enforces active current-code authority, retained
inspection authority, exact-code replacement or versions above the high-water
mark, schemas, quota and real flash headroom. Waiting transfers expire; cancelled
or disconnected uncommitted work is cleaned up. An acknowledged commit drains
across USB reset and returns a verified canonical-root receipt. Unknown commit
outcomes are not retried or rolled back by the SDK.

Signed package inspection is independent of mutable-data verification. A damaged
index/private store no longer hides an occupied namespace from install admission
or prevents unrelated valid apps from appearing. An intact archive repairs that
data while preserving package ownership. This adds host hello flag 1024 and
commands `0x90`–`0x95`; API 11, ABI 1, package formats, storage geometry and firmware
trust roots retain their meanings.

Completed validation:

- `make test`: **993 passed, two expected private-DTB skips**, 229.79 seconds,
  recorded in `build/sdk-archive-live/host-full.log`. The full run precedes the
  final three native policy cases; that final session run passes independently
  in 6.58 seconds (`session-policy.log`). No firmware or host implementation
  changed after the full suite began.
- **81 focused tests** pass (`host-focused.log`). Host cases include same-open-
  descriptor transfer, changed source contents, invalid signatures before USB,
  old-firmware refusal, cancellation, local destination races, damaged exports
  and lost write acknowledgements without retries. The complete source-kit
  archive parser independently verifies the actual ARM export.
- The final production-filesystem session fixture passes **25 scenarios** with
  ASan/UBSan and real RSA signatures: fresh/existing restores, pending pairs,
  byte-identical exports, malformed bindings, unacknowledged requests, timeouts,
  revoked execution versus retained export, stale trust/generations, exact-code
  and downgrade policy, damaged-index repair and commit/reset boundaries. Session
  storage is **452,096 bytes** on the host, excluding existing shared package
  scratch and the document store. The full suite also reruns the archive engine's
  interruption/cancellation and damaged-content matrix.
- Both physical and VM targets compile the live session. Builds ran sequentially
  using the existing physical release public key. Existing linker warnings remain.
  Logs are `physical.log` and `vm.log` under `build/sdk-archive-live/`.
- `vm/test-sdk-archives.py --firmware dist/lefony-os-prime-g2-archive-live-vm.elf
  --output build/sdk-archive-live/arm-v2` passes **eight signed ARM/USB journeys**:
  export/change/restore, cold reopen and acknowledged-commit USB reset, pending
  export/restore, cold pending reopen, rollback with preserved high-water mark,
  restore into a fresh namespace, damaged-index repair and damaged-private-data
  repair. The actual CLI uses only a substituted synthetic USB opener; package
  verification, transfer, commit and host publication use production code.
  An independent production-filesystem reader verifies the saved package,
  private bytes and 131,137-byte streamed file after each VM shuts down. Unrelated
  apps remain available during damaged-data repair.
- **38 ARM runtime/isolation/service regressions** pass on the same VM ELF.
  Report: `build/sdk-archive-live/arm-runtime-report.json`.
- Public-tree and whitespace checks pass; **134 relative documentation targets**
  in the updated guides resolve. No physical device operation, deployment,
  real credential-store access, commit or push occurred.

The first ARM attempt exposed an existing runner bug: it appended the emulator
public key to an already signed package's explicit trust list, duplicating the
matching identity and causing strict verification to reject it. The runner now
adds the fixture key only when signing an unsigned preview itself. The failed
attempt remains in `build/sdk-archive-live/arm.log`; the successful journey is
`arm-v2.log`. Its recorded source hashes match the final implementation.

| Artifact | SHA-256 |
| --- | --- |
| Physical ELF, `archive-live-physical` | `05e298d2247b03f407ec33d5e1eb63a8505d9e0b2958aa6dabae6169416be875` |
| Physical BIN | `93b7f19e2b7a286358884c744f93b25ab8bd25e71a1a15c6bbce9a0b6a3a340a` |
| VM ELF, `archive-live-vm` | `ed8ffdf82e2a68bfafdddf8aafe49cd8e69b8703827bf0e0fa9d4ea6a93be56a` |
| VM BIN | `705343f71c7bbc2715c9b5ad60f00d4d89fff1cbe6abbc3eddabad755bc45021` |
| Final session report | `d636bfc0d78bf69a8d5ae6b27966eea087e96e2cdf82599cc6d6c505c15b55c0` |
| ARM archive report | `6c583fcb8ccc661e6c171b9cd57981b917974d7e8e95f9ef1433190556d0d62f` |
| ARM runtime report | `b074035d16ac007c59fac6f74403215b0b4bfa482e0aad50be9f27326af712bc` |

QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The single-pair ARM export is 171,266 bytes, SHA-256
`9875ee0f0cb94d0503dbe438deefb06909748cb45ed92644f324a97b94a767d7`;
the pending export is 342,409 bytes, SHA-256
`eab7ec1cf1fddec7cebffb53881ba795e5934c0228ef822578baa67f5c8060d8`.

The source kit `build/sdk-archive-live/source-kit/sdk.tar.gz` includes the verified
newlib sysroot, source and notices. All **398 file hashes** verify, repeated
archives are byte-identical, and relocated command discovery and authentication
of the ARM archive pass. Kit SHA-256:
`445624691dbe0fbc47d7b75c8c7b2d8175d2abfb5ed3d2639d041c7abea32f5c`.
It precedes this ledger entry and does not establish complete native-host/frozen
bundle qualification.

Remaining archive work includes explicit consent for a pending pair with
different developer signers on a fresh calculator, recovery of unreadable signed
code, evolving preview data, broader large-archive/resource cases and physical
qualification. The full SDK objective still includes key-registry maintenance,
remaining UI/library/proving-app work and native-host/independent/physical release
acceptance. No SDK 1.0 milestone or the full goal is declared complete here.

Read-only evidence at `build/sdk-archive-live/evidence` retains **156 files**,
**25,400,639 bytes**, including exact port sources, test sources, build/test logs,
reports, firmware and the source kit. Every copied hash verifies. Index SHA-256:
`54e52c34a5ba861f0e6f2ffd5aeccab2c1af80907730bc1e32e2df61ad6d73d8`.
Its ledger copy precedes this annotation. All checks launched for this checkpoint
have completed; the full SDK goal remains active.

## Persistent ARM preview data and Notebook package upgrades — 2026-09-13

The [preview workflow](../sdk/UI.md) now retains committed named files,
directories and private bytes across source edits. `.lefony/preview/state.json`
atomically selects a verified immutable archive outside `build/` and source
uploads; one prior checkpoint is retained. Nested fixtures include empty
directories, bounded to 127 entries and 32 MiB. Explicit reset reseeds only the
first successful watched run; disposable runs leave saved data untouched.
Changed fixtures require reset, and failed compilation, app faults/nonzero exits
and source changes during a run preserve the prior checkpoint. Ctrl-C publishes
a stale/cancelled status. The receipt remains authoritative if interruption
occurs after data publication but before the frame/status update.

Every run uses public emulator signing fixtures and normal signed installation
and archive restore into fresh synthetic media. Source edits can change code at
the same version without changing physical install policy. A version increase
retains the prior compatible pair and invokes the real API 8 migration/acceptance
contract. Schema changes require a version increase, and another increase is
rejected while an upgrade remains pending. An exact empty state skips redundant
restore; pending pairs and retained schema/version state still require it.

[Notebook 0.3](../sdk/examples/notebook/README.md) declares API 8 data control in
addition to its existing typography/system requirements. It checks package/data
schemas and reads the complete document before accepting an upgrade. Unsupported
or malformed data disables editing and retains recovery state. Unconfirmed
acceptance disables editing without claiming the old pair certainly survived a
possibly committed operation. No private data migration is guessed.

Completed checks, all using the existing archive-live firmware candidate:

- `make test`: **1,011 passed, two expected private-DTB skips**, 238.33 seconds,
  in `build/sdk-preview-data/host-full.log`. The focused preview/archive selection
  passes **103 tests** in 5.14 seconds (`host-final.log`), including atomic receipt
  failure, changed/damaged snapshots, file bounds, symlinks and interrupted status.
- `vm/test-sdk-preview-data.py`: **10 ARM scenarios**, recorded under
  `build/sdk-preview-data/arm-data-v2`. They cover nested fixtures and empty
  directories, same-version source edits, private counters and append files,
  failed builds, changed fixtures, reset/disposable behavior, real schema
  migration/acceptance, cold reconstruction and nonzero-exit preservation.
- `vm/test-sdk-preview.py`: **five source/preview cases** under `arm-preview-v2`,
  covering a deliberate clipping defect, matching source locations, stale failed
  builds, corrected frames and the public CLI watcher. Developer-owned handlers
  stay unchanged. Notebook 0.3 empty-data previews measured **35.7–37.8 seconds**
  total, with builds **0.8–2.8 seconds**, compared with the preceding local
  51.8–54.3-second runs. Concurrent checks and different app revisions make this
  an observation, not a controlled benchmark or a supported-host budget.
- `vm/test-sdk-notebook-upgrade.py`: **seven signed ARM journeys**, under
  `notebook-upgrade-v2`. Normal 0.2-to-0.3 acceptance and cold reopen pass. A
  synthetic pending archive containing an unreadable current document and a
  readable previous pair is restored through normal USB. Notebook preserves
  bytes and generation across startup and cold reopen. Explicit rollback restores
  0.2 and the readable document while retaining the 0.3 version high-water mark.
  The readable, disabled/error and recovered screens were visually reviewed.
- `vm/test-sdk-notebook.py`: **24 debug/release ARM journeys** under
  `notebook-regression`, with **34 byte-identical rendered frames**. Editing,
  live saves, cold reopening, file formats, export, settings, slider cancellation,
  clipboard, malformed documents and long fields pass. The release ELF has no
  layout-inspection record symbol. Debug/release ELF hashes are respectively
  `a5679bf0698a2898ee7de04dab78dadb1b84db0a6e70beeca5b45fa57e912069`
  and `275d1c0a620dc6652a5290962ed2aa351f26aced9145ffe1e7540180d3f35eb8`.
- `vm/test-sdk-preview-kit.py`: the actual CLI from a relocated source kit
  creates an external Unicode-path Notebook project, previews nested fixtures
  with a **131,328-byte attachment**, edits source and retains the saved document
  and attachment. Changed original fixtures are not silently reimported. Source
  format 2 excludes checkpoints, archives and build data. Both previews pass;
  totals of **102.9 and 100.7 seconds** show nonempty-data latency still needs
  improvement. This uses the verified bundled newlib runtime, the existing host
  compiler/Python dependencies and explicit QEMU/firmware paths; it is not a
  clean-host or frozen native bundle qualification.

The first Notebook upgrade attempt is retained in `notebook-upgrade.log`: its
fixture tried to import a replacement file during a pending upgrade, which the
firmware correctly refuses. The revised test explicitly asserts that refusal
and uses a validated synthetic recovery archive; it changes no firmware policy
or raw NAND. An initial host helper return-value mismatch is retained in
`host-first.log`; the strict checkpoint receipt return and subsequent checks pass.

| Artifact/report under `build/sdk-preview-data/` | SHA-256 |
| --- | --- |
| `arm-data-v2/report.json` | `70e2b162d7bd12f3a845c5d68b8826310737206b6e70feb75c5394f3f7c5a093` |
| `arm-preview-v2/report.json` | `7e31bf445a5c3989ca91dc9acb6aacd6cc4d7b6fdbaf746b715587566af408d8` |
| `notebook-upgrade-v2/report.json` | `2cf04ed71e4073d262ed3182c95c9a02c6460959459a496eeb70f861eb2b64ac` |
| `notebook-regression/report.json` | `772981c40c5c6beb715ca4c8be56682c0098f0ca2d1d831b61cbe5d138b535e5` |
| `relocated-kit/report.json` | `d062afe266d539ed66746b508415dc86f599ccaf351e9e052e3d7c2328e0fdd6` |
| `source-kit/sdk.tar.gz` | `d3e0789ef7dda903ce10a90195976320e23109bd9d243835fbb406e0d0e175bc` |

The source kit includes newlib source, sysroot and notices; repeated archives are
byte-identical and all **400 file hashes** verify. It precedes this ledger entry.
Its executable SDK identity is
`ee3b7a5fdf95a7a9e822fcfa26fa0de72f95c4d5fe0e1579a64ebd391730bbef`,
matching the checkout. Recorded test source identities still match. Firmware
sources were unchanged in this checkpoint: the physical ELF remains
`05e298d2247b03f407ec33d5e1eb63a8505d9e0b2958aa6dabae6169416be875`
and VM ELF remains
`ed8ffdf82e2a68bfafdddf8aafe49cd8e69b8703827bf0e0fa9d4ea6a93be56a`;
their preceding sequential target builds remain the applicable compilation
evidence. No physical operation, production deployment, commit or push occurred.

The full SDK goal remains active. Preview latency, fuller UI/glyph/state coverage,
archive recovery across developer signers or unreadable code, key-registry
maintenance, broader library/application/resource cases, native host bundles,
independent developer trials and physical qualification remain open. The existing
scoped MIT alternative is unchanged. This checkpoint does not declare SDK 1.0
or any complete milestone qualified.

Final public-tree and whitespace checks pass, and **153 relative documentation
targets** resolve. Read-only evidence at `build/sdk-preview-data/evidence`
retains **140 files**, **32,421,924 bytes**, including exact SDK/example/test
sources, reports, failure logs, reviewed frames, firmware and the source kit.
All copied hashes verify. Its index SHA-256 is
`355e49ccabf0a3fbbf783762fd8b6ef798ca830d2c2bae036cab11a261d0439a`;
the snapshot's ledger copy precedes this annotation. All checks launched for
this checkpoint have completed; the full SDK goal remains active.


## Revoked-key removal and backed-up registry repair — 2026-09-13

The local private-install workflow now supports explicit removal of unused
revoked developer keys and repair of a readable corrupt registry. Removal scans
current and retained signed packages, refuses active/in-use keys, and fails
closed on unreadable or unauthenticated app metadata. It frees a slot without
resetting the mutation serial, including removal of the last key.

`keys backup-damaged` exports at most 65,536 readable bytes with complete hash
verification and atomic host publication. `keys repair --public-key KEY --label
LABEL --backup NEW_PATH` first saves that verified backup, then requires normal
OS-owned approval of the full public-key fingerprint and damaged-registry hash.
It builds a one-key table; other keys need explicit reenrollment. Installed
packages, document roots, namespace ownership and version high-water marks are
preserved. Healthy/missing registries, stale bytes, unreadable media, oversized
files and failed backups cannot use this repair path. The firmware binds consent
to the exact damaged bytes; it cannot prove remote custody of the host backup.

Registry format 2 reads legacy format 1 and permits an empty table with a
nonzero serial. Mutations write version 2; older firmware fails closed on it.
The app ABI, package formats, NAND geometry and firmware/store roots do not
change. Repair deliberately starts the rebuilt registry serial at 1 under the
exclusive management-session gate. No active transfer survives that operation.

Validation on the dirty `codex/sdk-1.0` candidate based on
`91701e213d74918226b3692f570079c2c13d9000`:

- Full host suite: **1,029 passed, two expected private-DTB skips**, 230.92 s.
  Focused key/storage/CLI tests: **45 passed**. Production filesystem fixtures
  exercise removal and repair across full/torn writes, cancellation, stale
  hashes and size boundaries; shared registry-engine read-fault cases remain
  separate from the repair-specific interruption cases. Legacy v1 decoding is
  checked by the host codec fixture, not a claimed ARM migration journey.
- Sequential physical and VM target builds pass. The first physical build
  exposed a C++11 initialization incompatibility in the recovery hooks, fixed
  before both successful builds. Existing upstream linker warnings remain.
- **10 ARM key-maintenance cases** pass: current/recovery signer protection,
  removal after real Notebook upgrade acceptance, a full table and slot reuse,
  cold preservation, stale/cancelled repair and verified backups, approved CLI
  repair, unchanged document/package roots, cold launch, final-key removal and
  cold reenrollment. Approval traverses normal keyboard input and rendered OS UI.
  The repair and removal frames were visually inspected; both full fingerprints
  and the repair source hash are readable without overlap.
- **21 ARM private-install regression cases** pass, including signer replacement
  with named files/private data and cold reopen. **38 ARM runtime/isolation
  cases** pass. These are synthetic storage/model tests, not physical acceptance.

The first ARM maintenance test failed because its fixture stayed in the app menu
after closing Notebook; the OS correctly denied the next approval. The corrected
fixture returns through normal Back and passes. That failure and the initial
build/host failures are retained beside the successful logs.

| Artifact/report | SHA-256 |
| --- | --- |
| `dist/lefony-os-prime-g2-key-maintenance-physical.elf` | `9861e892f0a27a6b24631c7d0e3bbe5170fa3231e34b42828b6d7c2441124990` |
| `dist/lefony-os-prime-g2-key-maintenance-vm.elf` | `3c1f1932a4e2fb3b7d020fba34caec8724bdbeed3b7763595f789e8451dd9aff` |
| `build/sdk-key-maintenance/arm-v2/report.json` | `5deca4e7b3de3f06e90609cc090a42a417039fda58447f03815ab258a462a08b` |
| `build/sdk-key-maintenance/private-install-regression/report.json` | `973bcffe3d6a3942a94fef9dcc90ec17d4e1bc9455b45a8b07899f14991c36dc` |
| `build/sdk-key-maintenance/runtime-report.json` | `eb59c4bbecd9c3c8e1f7bf46af08711f6929a46393429feec2c2bf0feff9c656` |

The executable SDK identity is
`c48d785d432414e6f58ab172191fd11ad614d2042036c08ea9e951f172ab1859`;
QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
No updated downloadable bundle is claimed by this checkpoint. Public-tree checks
pass. Native hosts, broader resource/large-catalog latency, unreadable-media
recovery, independent trials and physical qualification remain open, alongside
the full SDK objective. No physical device operation, commit, push or deployment
occurred; the scoped MIT alternative is unchanged.


The key-maintenance snapshot at `build/sdk-key-maintenance/evidence` retains
**89 files, 9,380,954 bytes**, with verified read-only copies. Its index SHA-256
is `2363fa59630ecfab0a2a98e47fa363333bdaa610d3fdcf2547f8e1918e4ad875`;
its ledger copy precedes this annotation.

## Fresh archive restore across developer signers — 2026-09-13

`archive restore --allow-recovery-pair` now supports a pending app upgrade whose
current and retained packages have different developer signers, when the app is
absent on the destination calculator. Both keys must already be enrolled; the
current key must be active and the retained key may stay revoked. Compiled store
roots and the emulator fixture cannot receive this developer recovery grant.
Existing app ownership, supported-package checks and version high-water marks
retain their original enforcement. Ordinary fresh restore without the explicit
option still refuses a pair across different signing authorities.

The firmware stages and verifies the entire archive before entering `AwaitUser`.
Its Home-only OS view shows the complete app ID, both versions, both signer
fingerprints and the exact archive SHA-256. Approval requires a rendered view,
an all-up physical scan and then physical OK. The two-minute consent deadline,
Back/Home/power dismissal and USB reset preserve an uncommitted namespace. The
SDK validates the full 216-byte approval record and still sends a separate
sequence/nonce-bound commit. Trust and destination identity are checked again
at approval and commit. Acknowledged commits retain their existing reset and
unknown-outcome rules. Successful restore changes no enrollment/revocation state;
rollback to a revoked signer requires separate explicit reenrollment.

This adds hello flag 4096, restore request flag 2, state 8, error 16, read-only
request `0x96` and status flag 4. That status flag persists through approval and
commit, including when the user approves before the host observes `AwaitUser`.
The SDK therefore cannot skip approval-record inspection in that timing case;
successful granted restores report flags 5. Existing request/status sizes, app
API 11, ABI 1, archive/package formats, geometry and signing roots are unchanged.
The checked preparation scripts add a distinct OS event and remain idempotent on
the final prepared source. The UI retains the reviewed identities when the host
starts its final metadata inspection.

Validation for the final local candidate:

- Full host suite: **1,050 passed, two expected private-DTB skips, 280 subtests**,
  235.91 s. The final focused suite has **59 passes**, including early-approval
  receipt checks. Its production-filesystem fixture has **44 cases**, with real
  RSA signatures for two identities, current/retained authority, protected store
  authority, stale trust, unapproved commit, dismissal, expiry, reset and commit
  acknowledgement boundaries. Existing restore-engine interruption tests also
  pass in the host suite.
- Sequential physical and VM builds pass. The final physical ELF is
  `c71aceed0a152b5d2fed7bbfb34152c9dd3891e16e1aa0eb206526211befe47a`;
  the final VM ELF is
  `7ff2044659af7098919f1bf83837d244dbf60d379a3847b0547fd1b7dbcd462f`.
  Their BIN hashes are respectively
  `671c9096d2aba01fe7897637df1450837c38d216128e78bf479a21f573eeec80`
  and `d0fc56d9e40dbeb489fa0203bac0213ef68c35f9aec7712f4445a4684e397815`.
  Existing upstream linker warnings remain; no physical device was written.
- The final ARM report has **nine live restore/cold checks and one authenticated
  input-reuse receipt**. The source phase previously installed Notebook under A,
  saved a document and 131,137-byte attachment, revoked A, used real OS-approved
  signer replacement with B and exported the pending pair. The final run reuses
  that independently signature/hash-validated 448,890-byte archive rather than
  generating new signing identities. It checks unknown-key and missing-option
  refusal, normal Back cancellation, withheld USB commit acknowledgement and
  reset before approval, approved CLI restore, exact archive round trip, existing
  namespace protection, cold reopening, revoked-key rollback refusal, explicit
  reenrollment, rollback and another cold reopening. The original signer and
  version high-water mark are preserved. Independent filesystem inspection
  checks the resulting package; file exports verify both saved contents.
- The final approval and cancellation frames were visually inspected. The host
  approval notice matches both complete signer fingerprints and the archive hash.
  No test invokes a guest approval callback; approval uses the normal key matrix.
- **Eight ordinary archive ARM journeys** also pass, including cold pending pairs,
  rollback, fresh restore and damaged-index/private-data repair. This separate
  regression was run on the earlier build retained in
  `build/sdk-archive-consent/regression/firmware.elf`; its exact hash is in its
  report. It is supporting evidence for the unchanged ordinary protocol, not a
  claim that those eight journeys ran on the final ELF.
- The final source kit is byte-reproducible, all **400 file hashes** verify and
  its relocated CLI exposes `--allow-recovery-pair`. It contains newlib source,
  sysroot and notices. This checks source packaging and command availability;
  complete native bundles and clean-host USB journeys remain unqualified.

The initial physical build exposed unavailable `snprintf` in the firmware's small
library; a bounded formatter replaced it. The first host run had an obsolete
error-range assertion. An initial ARM run was intentionally stopped for the
store-authority restriction. The next ARM test expected a particular USB error
string for a refused commit, but the model withheld the status acknowledgement
and the helper timed out. The revised fixture checks one bounded status packet
and verifies that the session is still awaiting approval before reset. Review of
early UI handling also exposed the host receipt timing gap described above;
explicit flag/receipt tests and the final CLI journey now pass. Earlier failure
and interruption logs remain available beside the final evidence.

| Artifact under `build/sdk-archive-consent/` | SHA-256 |
| --- | --- |
| `arm-v3/report.json` | `84364829fc6eae922dfedf464e3542417bf75be3a0103fee0647b19e927d1799` |
| `regression/report.json` | `a3c144a22fe8852dcc578ec4d03dccb6633693dc7ade8252faf134d1d528856f` |
| `host-full-final.log` | `e1f7013cf63d5aeb9330a2192e433b53f6ffd01744e6217872157c52ee9bdff0` |
| `host-early-approval.log` | `fa6c3921bdedc1bbcdf9cb4a3f9096982cc5f5840454e28208ab6c18a7538528` |
| `sdk-final.tar.gz` | `a16b1f151c4c2b9bcd5b81d5b926625291826d3c441401e7eb5cc2d19f0e29a8` |

The final executable SDK identity is
`e5abcb484be81e7f92eeb16a7d61bf0a540a0e4ef863a98bb061a2879bbf20b9`.
QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The base is still `91701e213d74918226b3692f570079c2c13d9000` with the dirty
`codex/sdk-1.0` worktree; none of this checkpoint was committed or deployed.
The scoped MIT alternative is unchanged. Public-tree and whitespace checks pass.

This closes the fresh cross-signer pending-archive consent implementation gap.
Unreadable installed code still prevents archive recovery; the current path does
not guess ownership from a corrupt root or treat an occupied namespace as empty.
Broader archive resources, UI/preview/library/proving-app work, native bundles,
independent trials and physical qualification remain part of the full SDK goal.
No complete SDK 1.0 milestone or release is declared qualified here.

Read-only evidence in `build/sdk-archive-consent/evidence` retains **109 files,
39,478,270 bytes**, including current sources, candidate ELFs, reports,
reviewed frames, authenticated source inputs and the final source kit. Copied
hashes verify; the index SHA-256 is
`cfb29490d2c7a182d7dedc9eecb09bf065ca4ce4ae2c7e50bb7db7a960063a84`.
The source kit precedes this ledger entry, and the snapshot's ledger copy
precedes this annotation. All checks launched for this checkpoint have reached
a terminal result; the full SDK goal remains active.

## Exact-identity repair of unreadable app code — 2026-09-13

The local `archive restore --repair-code` path restores an occupied app whose
signed code is unavailable, using an authenticated archive and the surviving
canonical identity. FILE3/FILE4 roots require the exact original package hash
and size. FILE2 can prove the original package from its readable 352-byte signed
envelope; when the envelope is damaged or absent, it requires the original
package/private lengths and combined SHA-256. The firmware authenticates the
incoming package before applying either proof and completes deferred combined
hash verification before exposing commit. An arbitrary signed replacement, even
a newer version, cannot use this repair path.

`archive info --include-unreadable` returns explicit repair metadata. Unknown
signed fields are `null` in SDK output. Healthy apps use ordinary replacement;
absent apps, damaged/unknown canonical records and incompatible proof are refused.
Repair authorizes replacing the app and data from that archive, without granting
new signing authority. Existing active/revoked-key rules, retained cross-signer
identity, high-water marks, quota/headroom and canonical/trust rechecks remain.
Unrelated app namespaces are preserved. All publication uses the existing
staged, verified atomic root replacement and unknown-commit handling.

The additive host extension uses hello flag 8192, request flag 4, a 256-byte
schema-2 repair inspection and status flag 8. Committed repairs report flags 9;
the SDK verifies that receipt and independently inspects the resulting package
and data metadata. Ordinary 192-byte inspection and refusal behavior remain.
App API 11, feature mask 8191, ABI 1, archive/package formats, NAND geometry and
signing roots are unchanged. The session fixture occupies 452,720 host bytes,
384 more than the preceding candidate. Both firmware targets still fit.

Validation on the dirty `codex/sdk-1.0` worktree based on
`91701e213d74918226b3692f570079c2c13d9000`:

- Full host suite: **1,071 passed, two expected private-DTB skips, 280 subtests**,
  236.14 s. The host archive client suite has **75 passes**. Existing archive
  engine tests, including ordinary restoration and interruption coverage, pass.
- The production-filesystem session fixture retains **44 ordinary/consent cases**
  and adds **28 repair cases plus 74 full/torn write interruption cases**. It uses
  real RSA signatures. Cases cover FILE2 and document code damage/truncation,
  missing code objects, surviving prefixes versus exact private-data proof,
  wrong code and retained signer, revoked current key, high-water preservation,
  stale generation/trust, cancellation/expiry and damaged canonical records.
  Interruptions cover both legacy fallback repair and a FILE3 source. Every
  remounted canonical root is exactly the old or new root; another app is intact.
- Sequential physical and VM builds pass. Existing upstream compiler/linker
  warnings remain. The final prepared VM sources match the checked-in repair
  sources. No physical calculator operation occurred.
- **Ten ARM repair-test phases pass**: two signed source/export fixtures, seven
  code repairs with actual CLI/USB transfer and cold launches, and one damaged
  canonical-root refusal. Repairs cover legacy payload/envelope corruption,
  truncation to the canonical header or signed prefix, and missing/truncated/
  corrupt document code objects. Each recovered archive exactly matches its
  backup. Independent production-filesystem reads verify package/private hashes;
  document cases preserve a 130,961-byte streamed asset. A separate helper app
  launches before each repair and remains cataloged afterward. The cold
  document-repair frame was visually inspected and
  shows the expected successful app output. Fixtures and all NAND writes are
  synthetic; this does not qualify physical media.
- The final source kit is byte-reproducible, all **400 file hashes** verify, and
  relocated CLI help exposes both new flags. Newlib source/sysroot/notices are
  included. This validates source packaging and command availability, not a
  complete frozen bundle or clean-host USB workflow.
- Public-tree checks pass for **992 files**; whitespace checks pass. Documentation
  links in the affected guides resolve.

The initial repair test compilation failed on mixed enum/integer deduction in
its test initializer list. The corrected fixture and full suite pass; that log
is preserved. The initial ordinary archive regression suite had 56 passes before
new repair-specific cases were added. No firmware implementation or live ARM
repair failure was observed in this checkpoint.

| Artifact/report | SHA-256 |
| --- | --- |
| `dist/lefony-os-prime-g2-code-repair-physical.elf` | `e862102b08402e7458569049a355e1d6ae3bffc76dbd23801e7dadbf7200e98d` |
| `dist/lefony-os-prime-g2-code-repair-physical.bin` | `ef44a962f9c5504ea1e4cc5d2b48495e7e33878bbf98df9e105fd1ddd0aff4fa` |
| `dist/lefony-os-prime-g2-code-repair-vm.elf` | `6b2dbdc697d8e9ce814753b2191ebe07957a99aa77884c227f3c70d245e96339` |
| `dist/lefony-os-prime-g2-code-repair-vm.bin` | `1c03f726ab77b806a1164eb438e26a4e7b68b9a0369159b6d1c350545e9b2734` |
| `build/sdk-code-repair/arm/report.json` | `fdd24a3990bbde1898e2c0521df7ca998b6e303bb96fd3ec91d87ae7465ed041` |
| `build/sdk-code-repair/session-report.json` | `3a95aac31c98ad18e4c63dc49f6ac2831e342e8656df11cc80f465d1a6a82397` |
| `build/sdk-code-repair/host-full.log` | `cddbc5555be16bc4ec968bc902780cde07c9be10ee33e727ae845e0a5776adf0` |
| `build/sdk-code-repair/sdk-final.tar.gz` | `ac1df56d69758439e9555d919c3b7a9066fa41885375486a2d7e6bccc6102f94` |

The executable SDK identity is
`c52e34cf6130fb0d9424b435903846b014440e4b95dee031e343d50076a250c3`;
QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The kit precedes this ledger entry. No commit, push, deployment or change to the
scoped MIT alternative occurred. The full SDK goal remains active: broader
archive resources and media recovery, UI/preview/library/proving-app work,
native host bundles, independent trials and physical qualification remain open.
No complete SDK 1.0 milestone or release is declared qualified.

The ordinary archive regression also passes **eight ARM journeys on this exact
final VM ELF**: initial restoration and cancellation/stale-generation checks,
cold reopening with acknowledged commit across USB reset, pending upgrade, cold
pending pair, rollback with retained high-water mark, fresh restoration, damaged
index repair and damaged private-data repair. Independent package/private/blob
checks pass. Its report is `build/sdk-code-repair/ordinary-arm/report.json`,
SHA-256 `fa69af1e16fa198387d2c2b41e16d06ec4e781f6e763336949a22ac7ce01c82e`. All recorded firmware and source identities
match the final candidate. These are model/guest checks, not physical acceptance.

Read-only evidence at `build/sdk-code-repair/evidence` retains **133 files,
42,236,033 bytes**, with every copied hash verified. Its index SHA-256 is
`12752210cdb09e0235837dae0a7fdb40d704141b0af3954ff69dec4828dca745`. The copied ledger precedes this index
annotation. Final public-tree/whitespace checks pass and **154 relative
documentation targets** resolve. All checks launched for this checkpoint have
completed; the full SDK goal remains active.

## Shared pixel lists and Notebook 0.4 — 2026-09-13

`ListModel` now supports a configured pixel viewport, visible partial rows,
allocation-free 64-bit content offsets, tap selection and captured vertical
dragging. Repeated identical layout/count calls preserve capture. Keyboard
selection reveals the selected row; changed counts/layouts cancel capture and
clamp the viewport. Cancel, horizontal departure, additional/changed contacts,
keyboard input and navigation cannot turn a drag into a row activation.
Cancellation preserves scroll position. The model tracks the finger directly;
it does not implement inertia.

The shared row painter clips the original row/text geometry. `Canvas::outline`
clips each original edge, avoiding a false border at the viewport boundary.
Pressed rows have a distinct appearance. A noninteractive scrollbar reports
kind 10 in the existing debug layout frame; existing kind values, frame size,
ABI 1, API 11, package formats and firmware contracts are unchanged.
Notebook **0.4.0** uses these components and routes the entire captured gesture
before footer controls. Data stays in document format 3 / schema 0.
The [UI guide](../sdk/UI.md#lists-and-captured-scrolling) documents the public
model, clipped painting, event ownership and lifecycle cancellation.

Validation under `build/sdk-list-scroll/`:

- **1,072 host tests pass**, with **two expected private DTB/DTS skips** and
  **280 passing subtests**, in 242.56 seconds. The new ASan/UBSan list fixture
  covers tap jitter/gaps, cancellation, count shrink/empty state, invalid layout,
  extreme coordinates and `UINT32_MAX` virtual row counts, plus **100,000
  adversarial steps**. Its host model size is **72 bytes**.
- `vm/test-sdk-list-scroll.py` passes **six installed ARM journeys**: long,
  short and empty lists in debug/release, with **28 identical frame pairs**.
  Normal Goodix input exercises a 17-pixel drag with partial top/bottom rows,
  pressed feedback, translated/clipped text, original border edges and untouched
  header/footer pixels. It verifies partial-row taps, both scroll limits,
  scrollbar position, keyboard continuation/footer navigation, horizontal and
  contact cancellation, fresh taps, keyboard cancellation and Home/relaunch.
  Exported document bytes stay unchanged. GDB only reads inspection records;
  no guest controller calls or memory writes implement the input. The clipped,
  cancelled and relocated-preview frames were visually inspected.
- `vm/test-sdk-notebook.py` passes **24 debug/release ARM journeys**, including
  saved/cold documents, old formats, malformed inputs, options/slider cancellation,
  clipboard and export, with **34 identical frame pairs**. Comparison against
  the preceding Notebook checkpoint finds **28 unchanged frames**; all changed
  pixels in the other six lie inside the new scrollbar at `(312,60,4,116)`.
- `vm/test-sdk-notebook-upgrade.py` passes **seven 0.3-to-0.4 ARM phases**:
  readable initial/update/cold, malformed initial/update/cold-pending, and cold
  rollback. Malformed data retains the compatible pair and original bytes.
  The preceding 0.3 sources were extracted from the verified prior source kit
  `ac1df56d69758439e9555d919c3b7a9066fa41885375486a2d7e6bccc6102f94`.
  Both versions are rebuilt with the current SDK: this tests source/update/data
  compatibility, not a retained old-binary corpus.
- `vm/test-sdk-preview-kit.py` passes **two actual CLI previews from a relocated
  source kit** with bundled newlib. A Unicode-path external project loads twelve
  expressions and a **131,328-byte nested attachment**, scrolls through Goodix,
  and exposes the clipped rows and scrollbar in source/layout inspection.
  Changing the title rebuilds the package while preserving handlers, document,
  attachment and checkpoint history; source export excludes saved preview data.
  First build: **2.96 seconds**; incremental build: **0.82 seconds**. Full preview
  totals: **110.03 and 107.67 seconds**. These local runs overlap other validation
  workloads and do not establish a latency regression or a hardware timing budget.
  They do establish that end-to-end preview speed still needs improvement.
- The tested source kit is byte-identical on repeated packaging; all **400
  file hashes** verify. It precedes the final ledger annotations. The test uses
  installed host Python/compiler/GDB and explicit QEMU/firmware paths; it is
  not a complete native desktop bundle or clean-host qualification.

Debug/release Notebook code sizes are **88,656 / 74,976 bytes**, and static data
is **13,796 / 2,508 bytes**. The **11,288-byte** inspection frame accounts for
the static-data difference and its symbol is absent in release. Each app retains
the 64 KiB stack reservation and 8,380,416-byte foreground heap reservation;
actual stack/heap peaks remain unmeasured.

| Artifact/report under `build/sdk-list-scroll/` | SHA-256 |
| --- | --- |
| `arm-v2/report.json` | `df3a739030cd9bc71213723e256dc1476159d9df8bdda73380c405486b454580` |
| `notebook-regression/report.json` | `f9fe3825ccf63af81b0884efb223202f5489155c885ad90e5b6ba4b7036e2fde` |
| `notebook-upgrade-v2/report.json` | `329fc72e5ac924e202188df72af3207c83ecab96271396bcd496b0410d151d87` |
| `relocated-kit/report.json` | `6961808043a205f3303fd52886f6a730c8760fd5ce2175791af3aefa6b51e439` |
| `host-full.log` | `2a6e4c1e2368777c7571eaf489f4ef61afecf86c5b6f1f7dc00e0ec757e692f3` |
| `source-kit/sdk.tar.gz` | `33865d352e809f7fd044af5a11e3fd9f5429a789847e4c55770767e098f47f7b` |
| `arm-v2/debug/app-debug.elf` | `e427ed2066c09203aafbd0f3babc42368f1afe6943f8aa2d997cdb95cad4d364` |
| `arm-v2/release/app-debug.elf` | `53c2c0f381f3418efc5407b21e8e4a5750c7bbc2b2f9a6a1414084ceb7cf0e86` |

The executable SDK identity is
`450fecf2bd50e5dc88f13108d5820df42014565c80453fe20f53d7d395ad402e`.
These changes compile into apps, not the firmware. The preceding sequential
physical/VM builds remain applicable: physical ELF
`e862102b08402e7458569049a355e1d6ae3bffc76dbd23801e7dadbf7200e98d`,
VM ELF `6b2dbdc697d8e9ce814753b2191ebe07957a99aa77884c227f3c70d245e96339`.
Their hashes and the firmware source hashes recorded by the code-repair report
still match. QEMU remains
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
No new firmware build or physical device write was performed in this checkpoint.

Failed checks are retained: an initial nonexistent host-test filename ran no
tests; the in-tree Notebook build refused its stale SDK lock before compilation;
the first scrolling assertion incorrectly compared selected/unselected
background colors; and the first upgrade fixture retained a hardcoded 0.3
high-water version. The external build uses a fresh explicit SDK lock; the glyph
assertion now compares coverage separately from selection color; the recovery
fixture derives its high-water version from the signed packages. Final runs pass.

The full SDK objective remains active. Fuller UI/glyph/gallery states, preview
latency, library/application/resource and media-recovery coverage, complete
native bundles, independent trials and physical qualification remain open.
No SDK 1.0 milestone is declared complete. No deployment, commit, push, additional
license grant or change to the removed visual-editor scope occurred.

Final public-tree and whitespace checks pass (**994 public source files**), and
**144 relative targets** resolve across the six updated SDK/status guides.
Read-only evidence at `build/sdk-list-scroll/evidence` retains **492 files,
64,139,371 bytes**, including exact source, packages, reports, rendered frames,
synthetic cold-state overlays, prior source provenance and the tested source kit.
All copied hashes verify. Its index SHA-256 is
`6b74ae41cafbbb22e79be79a732c34bdb546e60018d38b96a9cf18b1869c455f`;
the snapshot's ledger copy precedes this annotation. All checks launched for
this checkpoint have completed. The full SDK goal remains active.


## Faster ARM preview and USB completion handoff — 2026-09-13

The populated Notebook source/ARM preview now completes in **19.1 seconds** in
one recorded local profile, versus **109.5 seconds** for the prior candidate.
Both run 12 expressions, a 131,328-byte nested attachment and a 17-pixel Goodix
scroll through signed installation, whole-app restore/export and layout inspection.
The final frames are pixel-identical and were visually inspected. Build times
were 2.7 and 2.8 seconds respectively; most of the improvement is in USB and
archive coordination. The new profile records installation at 0.66 seconds,
restore at 3.85 seconds and export at 4.26 seconds.

`vm/profile-sdk-preview.py` makes this workload reproducible from an external
project. It delegates every operation to the production SDK, records cProfile
and operation timings, verifies the expected partially clipped list row, and
rejects an SDK identity change during measurement. The measured host is macOS
26.6.2 ARM64 (25G83), with arm-none-eabi GCC 16.2.0 and the existing pinned custom
QEMU. These single profiled runs are local evidence, not a repeated clean-host
benchmark, a release latency budget or physical USB measurements.

Three coordinated implementation changes reduce idle delays:

- The modeled USB host retries explicit NAK responses after 0.1 ms rather than
  5 ms. Other errors and original transfer deadlines are preserved; physical
  libusb behavior is unchanged.
- After actual app-management/channel SETUP or completion progress, the firmware
  avoids the ordinary 10 ms idle sleep for at most 2 ms. Normal services, input,
  rendering and timers continue on every event-loop iteration. Only progress
  renews this window; a silent/stalled host cannot keep it active. Firmware and
  recovery traffic keep their existing separate bounded burst policy.
- Archive status waits start at 1 ms and back off to 10 ms for work that takes
  longer. Session binding, deadlines and the rule against retrying writes remain.
  Best-effort cleanup now inspects the session and cancels only a matching active
  operation, avoiding rejected cancellation after an already drained failure.

The faster traffic exposed an existing completion race. An old status OUT could
complete after `poll()` read ENDPTCOMPLETE but before it read SETUPSTAT. Reusing
its descriptor let that stale completion falsely finish the next write, which
then stalled. The same condition could affect abandoned data IN/OUT transfers.
`handleSetup()` now quiesces the old endpoints, reads and clears their completions,
retires completed status under the old request, and only then abandons unfinished
data and reuses descriptors. Previously acknowledged app commits remain honored.
Pending reset keeps its separate acknowledgement path. Endpoint flushing now
rechecks active/primed state with a single bounded wait budget.

The register-sequencing reference is Linux v6.12's
[ChipIdea endpoint flush and setup handling](https://github.com/torvalds/linux/blob/v6.12/drivers/usb/chipidea/udc.c).
Its endpoint-active recheck informs the bounded flush; the SDK's completion
retirement is validated separately against the guest/model. No addresses,
bitfields, app API 11/ABI 1 contracts, storage geometry, signature policy or
firmware trust roots changed. This is not physical controller qualification.

Validation on the dirty `codex/sdk-1.0` worktree based on
`91701e213d74918226b3692f570079c2c13d9000`:

- Final `make test`: **1,088 passed, two expected private-DTB/DTS skips**, 240.43 s.
  The preceding firmware-only run had 1,081 passes; seven cleanup ownership and
  terminal-state cases were then added. The final archive/USB/preview host subset
  passes **109 tests**, including deadlines, NAK-only retries and cancellation.
- Both physical and VM firmware builds pass, sequentially. The final prepared
  USB driver matches the checked-in source. Existing upstream build warnings
  remain. No physical calculator operation occurred.
- **12 deterministic ARM USB cases pass**: completed/uncompleted status IN,
  status OUT, superseded data IN and OUT, file commit/reset and package
  install/reset. GDB only pauses at the production register-read boundary;
  normal modeled USB packets provide every transfer and acknowledgement.
  Retained pre-fix firmware reproduces all three new stale-completion cases.
- **Eight final archive journeys pass**: ordinary export/restore, cold reopen,
  pending-pair restore/cold reopen, rollback, fresh recovery and damaged index/
  private-data recovery. Normal CLI/USB transfers preserve exact archives and
  the 131,137-byte streamed file. Independent filesystem reads check saved data
  and package hashes. A new assertion confirms **zero transport errors in every
  phase**, including errors that best-effort cleanup might otherwise hide.
- **11 USB-channel cases and the production HTTPS companion journey pass**,
  covering consent, refusal, streaming, lease/timeout, disconnect/reset, Home,
  fault and reopening. The companion validates the controlled TLS response and
  exact cached bytes. These use local synthetic consent and controlled services.
- Foreground scheduling, held/chord input, touch cancellation, overflow, repeats,
  UI ticks, Home and relaunch pass. The scheduling probe records 32 yields,
  47 ms total modeled yield time, 39 ms maximum gap, and 13 UI ticks over 4,090 ms.
- The source-edit/inspection journey passes its layout defect, deliberately
  failed build with a visibly stale previous frame, correction, and public CLI
  watch/save cases. Successful reported previews take 9.9–11.9 seconds for that
  smaller scenario; failed-build timing fields describe the retained preview.
- A relocated source kit passes two populated CLI previews: **19.41 seconds**
  initially and **17.46 seconds** after a source edit (builds 2.65/0.71 seconds).
  Both preserve all expression/attachment bytes, nested and empty directories,
  handlers and clipping. Publication source excludes private preview archives.
  These regression timings may overlap other tests and are not host budgets.
- Two source kits are byte-identical and all **400 extracted file hashes** verify.
  Public-tree checks pass for **996 files**; whitespace and affected relative
  documentation targets pass. This is source-kit evidence, not a complete native
  installer/frozen executable or clean-host qualification.

Failures remain recorded under `build/sdk-preview-latency`: the first faster
firmware stalled an archive upload, and deterministic tests reproduced its stale
completion flags. The earlier archive trace also found a swallowed cancel timeout
on an already failed session; the final cleanup and transport-error assertions
address that separately. An initial data-IN test expected a refused read, whereas
the actual defect accepted status prematurely; the corrected test checks this
protocol-order violation and reproduces it on the retained baseline. Earlier
profiling attempts failed before VM execution because of a Python module-name
collision or an existing output directory. The first status-race run rejected a
stale eight-instruction disassembly guard; its updated guard still verifies that
SETUPSTAT follows the production COMPLETE read. None of those runs is a pass.

| Artifact/report | SHA-256 |
| --- | --- |
| `dist/lefony-os-prime-g2-preview-poll-v2-physical.elf` | `6f61c6454635164e03980adfe8b7c7dfe862bf3100576c405501964c51eac9a9` |
| `dist/lefony-os-prime-g2-preview-poll-v2-physical.bin` | `8f282202e156fc257511726a26ec2c2a7aed29013bb492512f4dccc918cc65ae` |
| `dist/lefony-os-prime-g2-preview-poll-v2-vm.elf` | `a1a47d993ba6c93f7fb301cf04c24441e26e60377edc88316eddeb3bc3ccf423` |
| `dist/lefony-os-prime-g2-preview-poll-v2-vm.bin` | `04d3ec963070e8f4036169c28456291cfbf0337e0e3dc82a3f13835d134afd5e` |
| `final-profile/report.json` | `76acfd289b1f125d92163e116c8b02779d1b0f3aecc56d7bd8525da4bc230202` |
| `archives-final/report.json` | `efa9f2e7deb8e538236d1a3610aa5f9f23f6e9b0dba8a2202d8876975b774fb4` |
| `channel-final/report.json` | `d5ff41efe59060f8889b204cb9eff5d7dea0d1e5e81e2aef2c5132c2c8de313d` |
| `companion-final/report.json` | `b1164183fe0abf466a9bc758d77a4dc0914aa0ddab0b43625184f9dc09dbb874` |
| `preview-final/report.json` | `92defb1ad6966c28dd6c8a5c3ad2048e0cf71191eac51d4d5ccf18f13153f6b0` |
| `kit-preview-final/report.json` | `69e9e8e28b5a601771e9955b72b727d416113a03157e5beb6a27c9873d33b96c` |
| `source-kit/sdk.tar.gz` | `a876026441e6e4b732d345401c2d8a7fc70b38f24ea7b6395ade6144d286c0fe` |
| `host-final.log` | `00e43a66a46de5012342aaa42785499c7cff704c290d6260f34f6d7c373f18a1` |

Report paths in the table are relative to `build/sdk-preview-latency`.
The final executable SDK identity is
`e3df77b89896f7595e2b49c60a185f3086eec918f1498862ea45b48e24cfcef5`;
QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The source kit predates this ledger entry. No commit, push, deployment, physical
write, new signing identity or expansion of the approved MIT alternative occurred.

This closes the reproduced preview/transfer defects and provides a faster local
ARM authoring loop. The full SDK objective remains active: fuller UI/glyph/gallery
states, library/application/resource and damaged-media coverage, complete native
host bundles, production publication operations, independent trials and physical
qualification remain open. No complete SDK 1.0 milestone is declared qualified.

Read-only evidence in `build/sdk-preview-latency/evidence` retains **712 files, 87,956,665 bytes**, including port/preparation sources, exact firmware candidates,
source kit, test reports, reviewed frames, synthetic storage snapshots and
retained failures. All copied hashes verify. The index SHA-256 is
`456b44f519f78a9aaa8b1c8c93de2159e74719177b4314edb220831f7436fc0c`. Its ledger copy precedes
this annotation. Every check launched for this checkpoint has reached a terminal
result. The full SDK goal remains active.


## Shared menus/dialogs, long fields and UI Gallery — 2026-09-13

This checkpoint finishes a concrete part of the C/C++ component workflow. The
new `ui_patterns.h` owns bounded menu actions and confirmation layout/focus;
`Widgets` renders them using the same palette, OS fonts and inspection records
as other controls. Applications retain their navigation and action handlers.
The `ui-gallery` template exercises these components through public input and
foreground APIs. No external authoring application or generator is introduced.

- Menus own up to 32 labels/actions, skip disabled items during keyboard
  navigation, use stable action IDs and reuse captured list scrolling. Touches
  cancelled by movement, changed contacts, navigation or Home cannot activate
  an old action. Empty menus return no action. The gallery also demonstrates
  loading/ready transitions, theme changes and all four OS fonts.
- Confirmation layout replaces background focus and selects Cancel by default.
  Invalid geometry/IDs or insufficient capacity preserve the existing focus.
  Notebook **0.5.0** uses the shared dialog and pressed slider rendering; its
  document format and data schema are unchanged.
- Widgets retain their original geometry under clipping. Button/choice text,
  slider position, progress fill, field scroll and scrollbar geometry no longer
  reflow into the visible fragment. Large scrollbar ratios use overflow-safe
  arithmetic. Pressed/disabled/invalid colors use the component palette.
- Fields render the full `TextBuffer<1024>` capacity. Font validation is split
  into requests of at most 256 bytes without separating combining marks from
  their base. Unsupported glyphs still fail, and a single cell exceeding the
  request limit is rejected. Only visible cells are drawn. Scalar-based caret
  editing, the pinned glyph set and ordinary label limits remain documented.

Validation on the dirty `codex/sdk-1.0` worktree based on
`91701e213d74918226b3692f570079c2c13d9000`:

- `make test`: **1,089 passed, two expected private-DTB/DTS skips**, 363.80 s.
  The focused UI/preview/Notebook/gallery host subset passes **28 tests**.
  ASan/UBSan model checks cover menu ownership, focus, cancellation, capacity,
  invalid labels and dialog failures. **20,000** independent widened-arithmetic
  oracle vectors verify scrollbar scaling; the host `MenuModel<8>` is 912 bytes.
- `vm/test-sdk-ui-components.py --firmware dist/lefony-os-prime-g2-preview-poll-v2-vm.elf --output build/sdk-ui-components/arm-v2`
  passes **13 kinds × seven clipping regions × two profiles = 182 frames**.
  Every partial/empty viewport equals the corresponding crop of the original
  full painting. The 1023-byte field also equals an independently sized short
  field containing the same visible suffix, across all seven clips/profiles.
- The same ARM test passes **25 gallery states per profile**, with normal
  keypad/Goodix input, disabled actions, changed-contact cancellation, default
  Cancel, confirmed reset, slider rollback/commit, long fields, four fonts,
  dark themes, empty/loading/ready menus, Home and relaunch. Debug inspection
  checks action/focus/state IDs and source locations; release omits the record
  symbol. All **116 component/gallery debug/release frame pairs** match.
  Captured fonts, disabled controls, dialogs, menus, long/clipped text and
  dark/empty/loading states were visually reviewed.
- `vm/test-sdk-notebook.py` passes **24 journeys and 34 matching frame pairs**:
  editing, saves, export, cold reopen, old/malformed documents, math settings,
  clipboard and cancellation. The unchanged host data/schema assertions pass.
- `vm/test-sdk-notebook-upgrade.py`, using preceding Notebook 0.4.0 sources from
  the retained preview-latency source kit, passes **seven 0.4.0→0.5.0 cases**.
  Readable documents accept the update; malformed data keeps the recovery pair,
  survives cold reopen and can roll back to the readable document.
- `vm/test-sdk-ui-kit.py --template ui-gallery` passes with a relocated source
  kit and bundled newlib while macOS outbound networking is denied. It creates
  an external project, previews normal input, checks the edited field and source
  bounds, and exports source format 2. Two kits are byte-identical; all **406
  file hashes** verify. `vm/test-sdk-preview-kit.py` separately passes populated
  Notebook previews before/after a source edit, preserving document/attachment
  bytes, nested/empty directories, handlers and clipped rows while excluding
  private preview archives from publication source.
- The gallery release contains **45,936 code bytes and 2,508 static-data bytes**;
  debug uses 53,544 and 13,796 respectively. These are linked sizes, not heap or
  stack peaks. The 11,288-byte difference is the omitted inspection frame.
- Public source boundary and whitespace checks pass. The changed runtime is
  app-linked C++/host tooling; no firmware source changed in this checkpoint.
  It reuses the exact previously built/qualified local API 11 VM candidate.
  Neither a physical firmware rebuild nor a device operation is claimed here.

The first paint fixture failed compilation because its anonymous namespace was
not closed before `main`. It produced no ARM pass; the corrected complete run
is `arm-v2`. Earlier gallery attempts failed for unavailable `<cstdio>` headers,
a misleading-indentation warning and a replay key named `7` instead of `seven`.
The example now uses the supported C header profile and authoritative key name.
These failed logs are retained separately from successful evidence.

| Artifact/report | SHA-256 |
| --- | --- |
| `arm-v2/report.json` | `bdb45cdef159431b63ced2265e4fb3355bb362dd11ec9f55acd2bd028b34fb96` |
| `notebook/report.json` | `704cd82159dafdd8d26c3b4b3e0be7394f5f1ce9fdedbbda584982518de57995` |
| `notebook-upgrade/report.json` | `8d7bab3e4a28ad5c4257d6c9f1e0c63ec64afa6004d05418a55b86faf2dc9046` |
| `preview-kit/report.json` | `341f5cc480fb1cc93243a97764cbc7b9994137392981fa7e32a042f2df7df14e` |
| `kit-gallery/report.json` | `4f00623769da3443ae03481aa506fc21e6b14dc78aabe9b740bd4c5d4cfc5729` |
| `kit-gallery/sdk-with-newlib.tar.gz` | `8e20a5b2b95e26fec20aa429795085623f8a5ee672f3d3c9b1549db9b31247bc` |
| `host-full.log` | `818d705c28c3140ff872d7489f304ec5f5c0342c34b56fe066862eff1550b6c6` |

Paths in this table are relative to `build/sdk-ui-components`. The executable
SDK identity is `c1985dea3df734d85624869a116e89c006aa8ee496fc676db99b6bb4000235c1`;
the VM ELF remains `a1a47d993ba6c93f7fb301cf04c24441e26e60377edc88316eddeb3bc3ccf423`,
and QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The tested kit predates final README/status/ledger annotations; its executable
SDK and example inputs match the qualified candidate. No native frozen bundle,
new signing identity, license expansion, deployment, commit or push is claimed.

The full SDK objective remains active. This closes these component defects and
adds integrated gallery evidence; broader library/application/resource and media
recovery work, complete native host bundles, production publication operations,
independent trials and physical qualification still require work. The gallery's
local loading simulation does not replace the separate connected-app tests.

Final public checks pass for **1,005 files**, with **146** affected relative documentation targets verified. The executable SDK and qualified source hashes remain unchanged. Read-only evidence at `build/sdk-ui-components/evidence` retains **710 files, 26,989,310 bytes** of sources, reports, frames, symbols, kits and failure logs; every copied hash verifies. Its index SHA-256 is `496c29e1d80357d547e24b041fa99320a63dff122146fb434af276994110b9ff`. The ledger copy precedes this annotation. Every check launched for this checkpoint has reached a terminal result.


## Explicit writer abort and full-quota application saves — 2026-09-13

This checkpoint closes a shared save/cancel gap in the document and connected
apps. A separately named temporary file consumed additional logical quota before
rename, so even equal-size replacement could fail at the full 32 MiB allowance.
The underlying engine already credits an existing destination; the public API
now also lets an app explicitly discard that destination's staged replacement.

- API **12**, capability **8192** (`FileAbort`), adds operation **15** to the
  unchanged file request. ABI 1, old operation meanings, wire sizes, storage
  geometry, trust roots and signing policies are unchanged. Abort invalidates
  only the writer, preserves reader snapshots and the last committed root, and
  drains cleanup without publishing. Previous successful syncs stay committed.
  Permission checks happen before submission; stale/reader handles cannot discard
  another writer. SDK, firmware and website readers/corpora advertise the same
  API 12 / feature mask 16383 candidate.
- The C adapter provides `lefony_file_abort`; the new C++ `FileWriter` stages a
  direct destination and publishes only through explicit commit. It checks abort
  authorization before opening, loops over short writes, and requests discard on
  write failure, cancellation or destruction. Unsupported/unauthorized abort has
  no close fallback. A failed commit can be ambiguous and requires inspection.
  The new C++ header retains CC-BY-NC-SA; the existing scoped MIT alternative is
  unchanged and has not been extended to another file.
- Notebook **0.6.0** uses this helper for document saves and exports. Failed saves
  retain the editing draft. Its shortened uncertainty message fits the actual
  screen. Legacy temporary-file cleanup occurs only after reading the complete
  document and accepting its package/data pair; malformed recovery data remains
  untouched. The document schema and format are unchanged.
- Link Gallery **0.2.0** validates header, dimensions, exact length, reserved
  fields and checksum incrementally in a separate bounded pixel allocation,
  before committing the staged cache. Failed writes, invalid content, cancellation
  and disconnect discard staging. Preparing/Saving disable app controls during
  blocking storage calls; Home remains OS-owned. A failed commit asks the user to
  reopen and inspect the cache. Two 73,728-byte pixel allocations may coexist;
  this bound is not a measured total heap or stack peak.

Executed validation on the dirty `codex/sdk-1.0` worktree based on
`91701e213d74918226b3692f570079c2c13d9000`:

- Physical and VM firmware compile sequentially (`build-physical.log`,
  `build-vm.log`). The physical build uses the existing configured public signing
  key. Output names use `LEFONY_NATIVE_DIST_NAME`; the VM platform is
  `prime_g2_vm`. Existing upstream/linker warnings remain. No device was written
  or used to qualify this change.
- `make test`: **1,094 passed, two expected private-DTB/DTS skips**, 236.12 s
  (`host-full-v2.log`). The final publication/manifest subset passes **217 tests**;
  the earlier production-session/UI/decoder subset passes **130 tests**. Production
  session cases cover snapshots, request/completion ownership, invalid flags,
  failed writers, quota retry, stale descriptors, repeated abort, subsequent
  commit and sync-then-discard. ASan/UBSan image cases cover malformed/truncated/
  extra content, many chunk sizes and allocation failure.
- `vm/test-sdk-file-abort.py` passes **four signed ARM cases**: ordinary work,
  cold reopening, undeclared permission and API 11 fallback. It exercises explicit
  and destructor cancellation, previously synced data, stale handles, buffered
  and already-flushed stdio cleanup, and an independently verified 8,193-byte
  transfer. Denied/unsupported helpers do not create files; Home remains usable.
- `vm/test-sdk-notebook-quota.py` uses the host-compiled production filesystem to
  seed real synthetic NAND to the exact **32 MiB** quota. The six-case baseline/
  current run proves that preceding Notebook 0.5 rejects equal-size replacement,
  while 0.6 replaces successfully, rejects growth without losing the draft,
  retries, shrinks, exports and cold-reopens exact bytes. After shortening the
  error message, the three current cases pass again (`notebook-quota-final`).
  The final app's five save/export waits are **16.807, 7.937, 17.034, 16.721 and
  17.210 seconds** on this local workload. These are observations, not ratified
  preview/save budgets or physical timings.
- The quota test retains a 120-second observation limit with read-only GDB
  progress samples after 15 seconds; ordinary Notebook tests keep their original
  15-second limit. Samples show `Close`/`CheckReferences` and later collection,
  followed by successful completion. No chunk verification, quota, headroom or
  media-integrity check was removed to obtain a pass.
- `vm/test-sdk-link-gallery.py --full-quota` passes **eight debug/release journeys**
  and **13 matching frame pairs**. Normal TLS streaming, disconnect/reconnect,
  cancellation, invalid content and cold cache reopening pass, followed by
  replacement, invalid-content preservation, cancellation and another cold reopen
  at the full quota. Host exports match independent image bytes. Error/cancel
  frames were visually reviewed; no named temporary cache remains.
- `vm/test-sdk-notebook.py` passes **24 journeys and 34 matching frame pairs**.
  `vm/test-sdk-notebook-upgrade.py` passes **seven 0.5.0→0.6.0 cases**, including
  malformed-data cold reopening and rollback. The extended fixture proves legacy
  temporary bytes survive read-only recovery and are removed only by a readable,
  accepted upgrade. Final draft/error and Gallery frames were visually reviewed.
- `vm/test-sdk-ui-kit.py` passes with the final relocated source kit, bundled
  newlib, an external Notebook project, normal-input ARM preview and source-format
  2 export while outbound networking is denied on macOS. Two kits are identical;
  all **407 file hashes** verify, including the new `file_writer.h`. This uses
  installed host compiler/emulator tools and is not a native frozen-host bundle.
- The website passes build/lint and **256** shared manifest/publication/device
  tests with one worker. SDK and website publication corpora now accept API 12
  writer-abort packages and reject API 13. No production store, GitHub account,
  deployment, device operation, commit or push was involved.

Retained failures are separate evidence. The first raw ARM fixture lacked the
`fileno` feature declaration; its corrected run passed. Earlier host fixtures
needed the API constants and pure-model include path updated. The first quota
baseline exceeded its ordinary 15-second readiness limit; later samples and
terminal runs establish progress/completion rather than a reproduced deadlock.
The first progress probe requested a second GDB endpoint while the layout server
was already listening; it now reuses that endpoint. The Gallery quota harness
initially omitted its `subprocess` import. The upgrade harness initially tried to
export over its own input fixture; it now uses a distinct output path, retaining
host overwrite protection. These failures did not qualify application behavior.

The first full host run passed 1,092 tests with one failure because the shared
publication corpus still classified API 12 as future/unsupported. The corpus was
corrected in both repositories and given an explicit accepted API 12 case. A
serialization attempt initially mishandled the corpus's deliberately invalid
Unicode test value; escaped test data was restored before rerunning. Final
contract and full-suite results above pass without weakening their validators.

Exact candidates and reports (report paths below are relative to
`build/sdk-file-abort`):

| Artifact/report | SHA-256 |
| --- | --- |
| `dist/lefony-os-prime-g2-file-abort-physical.elf` | `7af0775934de55eb5c367d8be84406ab5616e52daf2aa05a3e0a280eb2ed3439` |
| `dist/lefony-os-prime-g2-file-abort-physical.bin` | `066b4fff2bb412b2c143ebcaa60ae20688cd7d7556a960a88181352ced7dfde6` |
| `dist/lefony-os-prime-g2-file-abort-vm.elf` | `9efe4a74da490bdde5b667c124e3f1e80e3e0f25b38ab8eb0441f91e24629844` |
| `dist/lefony-os-prime-g2-file-abort-vm.bin` | `45e06bde5db536b2a0986b2047c52a18754089f996126beef00ebca84a5fe8f6` |
| `arm-final/report.json` | `e5f0eb710b197c67bcaae3f2ed831f4563860510c1d4c98593a1fd961b222b47` |
| `notebook-quota-v3/report.json` | `508d1dd358699f884b9ba9b4ae92c1d8ac8807eaa20af7168a6d8fe2013057d3` |
| `notebook-quota-final/report.json` | `8d14f5d539de14ca5e648b4fac36c1d5aa66440965eae167894c0685a1860d89` |
| `link-gallery-v2/report.json` | `998cee41d582282fac09b8ffe199d8f169908a682841f9769e8b5a39dafb83cc` |
| `notebook-regression/report.json` | `ae3496c4e4b2bc33a55dd5bf4a825f7bfa4b70383ac088c3c45c1ad6e8a4dd97` |
| `notebook-upgrade-v2/report.json` | `589e14a39ee83cc616fcf34c21aa4917308509bfb23261f8e1db7925327cf5bb` |
| `kit-final/report.json` | `52c6f4c59c52ac7d378fa8455c72597798b2e2571828bfe859d372f1f2514fca` |
| `kit-final/sdk-with-newlib.tar.gz` | `1a7391f5c5c4ded045a431acd80ff451366206b39530d8c711165435137f328a` |
| `host-full-v2.log` | `861f3df552f83dd5a66ef6477219db292e0546994d530133509aca943083af5e` |
| `sdk-identity-reconciliation.json` | `3a70a88584483103f0293d6694a00c8f8426025945894826e4ff9264577111d5` |

The final SDK identity is
`399b3a28adbea812015143f6240078d47367d102581c3893dd847af3f335a87b`.
QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The final kit includes the corrected publication corpus and predates this ledger
entry and final status annotations. Earlier runtime-report identities are
reconciled exactly in `sdk-identity-reconciliation.json`: Gallery and the first
quota run precede only a comment clarification and the publication-corpus update;
the final ARM/Notebook reports precede only that corpus update. Firmware, runtime
adapter and final application behavior were unchanged by the corpus correction.
The preceding helper/corpus bytes are retained separately; earlier reports have
not been relabeled with the final SDK hash.

This completes explicit app writer cancellation and these full-quota document/
cache workflows. The full SDK objective remains active: broader resource and
unreadable-media recovery, native host/companion bundles, production publication
operations, independent developer trials and physical qualification remain open.
No complete SDK 1.0 milestone is declared qualified.

Public source boundary and whitespace checks pass for **1,009 files**; **190**
relative documentation targets across the SDK and website were checked. Read-only
`build/sdk-file-abort/evidence` retains **792 files, 175,918,844 bytes**, including
source snapshots, firmware/symbols, reports, reviewed frames, two synthetic
recovery-media snapshots, the final kit and retained failures. Copied hashes
verify; index SHA-256 is
`83e3098858aa04a9951520744bde5d1b0c553b4bbe7025f86d7eea0f20ed19e6`.
Its ledger copy predates this annotation. Every check launched for this checkpoint
has reached a terminal result. The full SDK goal remains active.

## Minigzip transaction cleanup and public user files — 2026-09-13

Minigzip 0.2 now uses the public API 12 abort contract to stage its actual
output destination. The prior separately named `.part` approach consumed extra
logical quota and allowed stdio exit cleanup to publish an incomplete temporary
file. The new utility adaptation preserves the previous destination until the
complete stream has been checked. It creates no temporary namespace entry and
leaves existing unrelated partial files alone.

Compression checks input close and `gzflush(Z_FINISH)` before committing the
output descriptor. Decompression checks deferred read errors and input close,
then flushes its output buffer before committing. A checked raw `close` publishes
and invalidates the writer. Only afterward does gzip/stdio cleanup release its
buffers; the adapter checks the expected invalid-descriptor error. The SDK's
non-reused handle contract prevents cleanup from targeting a later writer. This
is an SDK-specific adaptation, not a generic POSIX ownership pattern.

An `atexit` handler discards an uncommitted writer before ordinary stream cleanup
on processing/allocation failures. An abort failure transfers cleanup to the OS
through `_exit`; there is no fallback that closes and publishes partial bytes.
Home/fault cleanup remains OS-owned. Failed commits retain the input because
commit outcomes can be ambiguous. Output commit and input deletion are separate
transactions: failed deletion can leave both files and returns a failure status.
Unsupported stdin/stdout modes now fail before opening any output.

The recipe declares API 12 and mask **8216** (files, foreground execution and
writer abort). There is no new SDK API, firmware change, library source patch or
license expansion. The existing minigzip manifest continues to select CC-BY-NC-SA
with Zlib. All **26 selected upstream library/license files** match their pinned
hashes; only `test/minigzip.c` is adapted. The source archive remains zlib 1.3.2,
SHA-256 `bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16`.
The cleanup design was checked against the pinned `gzwrite.c`/`gzlib.c` and the
[zlib manual](https://zlib.net/manual.html), whose web version still identifies
itself as 1.3.1.

Validation uses the unchanged API 12 VM candidate and custom Prime QEMU:

- `vm/test-sdk-minigzip-workflows.py` passes **15 workloads / 40 signed ARM
  phases**, split into `direct-functional`, `direct-quota` and `direct-lifecycle`.
  User inputs, outputs, repairs and freed-space retries use public file exchange.
  Only the full-quota filler is seeded through the host-compiled production
  filesystem. Each workload reuses its exact signed package through cold runs
  and corrected-input retries; no pending-upgrade import protection is bypassed.
- Ordinary and empty compression/decompression, rejected stdin/stdout, corrupt
  CRC/truncated trailers and corrected-input retries pass. Output is checked by
  independent host decoding/bytes. Full-quota replacement passes in both
  directions, as do a one-byte output shortfall and rejected growth followed by
  public filler replacement and successful retry. Failed/aborted runs preserve
  the input, previous output, root generation and a pre-existing `legacy.part`.
  Cold checks export and compare committed data before allowing another launch.
- Both compression and decompression fail cleanly with **8,323,072 bytes** held
  by real app allocations. A read-only GDB sample checks that value. The Home
  case observes **131,072 staged bytes**, sends normal keypad Home and verifies
  unchanged committed data; a cold run then completes the 2,097,408-byte input.
  GDB only pauses, reads and detaches; it does not alter program or driver state.
- `vm/test-sdk-minigzip.py` passes the **nine original release-profile ARM
  cases**, including large streams, package upgrades, exact failed-package
  retries and source-format-2 extraction rebuilding identical ARM bytes.
  The 262,176-byte input produces 262,274 compressed bytes, identical to the
  earlier sync/abort candidate. Independent stream parsing also confirms one
  gzip member, including the 20-byte empty-file output (`stream-integrity.json`).
- The final focused host suite passes **123 tests**, 15.83 s, covering ordinary
  runtime/source/lock behavior, C/mixed builds, file exchange and publication.
  The earlier full **1,094-test** suite belongs to the preceding API 12 checkpoint;
  no new full-suite or firmware build is claimed for this app-recipe change.
- `vm/test-sdk-main-kit.py` passes with outbound macOS networking denied: two
  deterministic source kits, all **407 file hashes**, bundled newlib, external
  CMake in a relocated Unicode/spaced path, disposable and cold saved visits,
  input-stream execution, and minigzip preparation/package/source export.
  Installed compiler/emulator tools are used; this is not a complete native
  host bundle. The tested kit precedes final evidence annotations.

All commands supply `--firmware dist/lefony-os-prime-g2-file-abort-vm.elf`.
The three workflow commands select `--cases compress decompress empty-compress
empty-decompress stdout stdin corrupt truncated`, `--cases quota-compress
quota-footer quota-replace quota-growth`, and `--cases heap-compress
heap-decompress home`. Evidence is under `build/sdk-minigzip-transactions`.

The initial sync/abort version also passed 26 public-workflow phases and the
original nine regression cases. Its sources and reports remain separately
identified. The final direct-close version removes the unnecessary writer reopen.
Observed full-quota compression/decompression times were **35.214 / 37.572 s**;
the earlier sync version's decompression took **47.566 s**. These are single local
observations with different concurrent host workloads, not a controlled benchmark
or a physical latency budget. Integrity scans, quotas and headroom checks remain.

The minigzip guide documents commands, stream ownership, non-atomic input removal,
error/retry behavior and limits. SDK status text now reflects implemented account,
UI, file and recovery capabilities instead of repeating older missing-feature
lists. Historical checkpoints retain their own exact qualification scope.

Full shared-media exhaustion, injected storage I/O errors in this application,
physical power loss/endurance, complete native bundles and remaining SDK release
acceptance still need evidence. This checkpoint does not qualify stable 1.0 or
finish the full SDK objective. No calculator operation, deployment, commit, push
or new signing identity occurred.

Exact checkpoint reports/artifacts (paths relative to `build/sdk-minigzip-transactions`):

| Artifact/report | SHA-256 |
| --- | --- |
| `direct-functional/report.json` | `823fa43b35f2c0ff4d057f24055e04b7626e0fd7e903542a53944077dc4a7263` |
| `direct-quota/report.json` | `5dc9ddea058e938d27e0bbf1a9491dc4698f70cd30d3e0412403b5a0990d90d5` |
| `direct-lifecycle/report.json` | `bc33b108172957415853a730713827c5040bf191fe7c08281ec2490709ba5483` |
| `direct-regression/report.json` | `c94a53dbb774305bd8d9c2cd49491b7302482accd999cf7b5a2a58fdd80bb047` |
| `direct-kit/report.json` | `e0de7bd5d992630cfdd2fdd39862c82558cb519c5aedb419ca8e214e0ed63746` |
| `direct-kit/sdk-with-newlib.tar.gz` | `a8a645806d1ff915cea74f27cdbb7c8571ef7384a5231ad8d3f79e281efdd314` |
| `final-kit/report.json` | `ca523fa46da670c0f8046dce33c63aaa18e7702e2f8f530838dc2a80e3913266` |
| `final-kit/sdk-with-newlib.tar.gz` | `d12b647233256a8cea38381334873aac49a822b34eefbc2e054f121405f677de` |
| `direct-host-focused.log` | `7e81039ee19607a84687efea38e739891d231b0f05e92eb5c71b162e91b33947` |
| `upstream-integrity.json` | `03b2708f20844d8fc4addfe28ee809652d830edcbb4eb7a5c7d0f101d3404152` |
| `stream-integrity.json` | `c2db9eb489682daf8782a33a87b1fa0083bef2c97e0e33a24fa29cc15828dcee` |

The final source kit is byte-identical across two builds and all 407 file hashes
verify. Compared with the kit exercised offline, it changes only four Markdown
files and their checksums; the exact difference is recorded in
`final-kit/report.json`. Executable SDK, application recipe and runtime inputs
are identical. The final kit includes this checkpoint's prose, preceding its
self-referential artifact-hash table and final evidence annotation.

The executable SDK identity remains
`399b3a28adbea812015143f6240078d47367d102581c3893dd847af3f335a87b`.
The unchanged `dist/lefony-os-prime-g2-file-abort-vm.elf` is
`9efe4a74da490bdde5b667c124e3f1e80e3e0f25b38ab8eb0441f91e24629844`;
QEMU is `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The final recipe hash is
`7d57b9a2cb1189cbab0b10562d09fabd08d63bf68ffaeeeed72e291f207b0391`;
the workflow script is
`14df6dcf2832e81d33b779afa145b98f9e1e0ea0cd199d7878f92671e055a753`.

Final public-source and whitespace checks pass for **1,010 files**; **149**
relative documentation targets were checked. Read-only evidence under
`build/sdk-minigzip-transactions/evidence` retains **626 files, 189,574,173 bytes**,
including sources, pinned zlib, VM firmware/symbols, reports, public file bytes,
kits and the preceding sync-candidate evidence. All indexed hashes verify; the
index SHA-256 is
`092ef83933c4de856370d385be0ac05a9277268a0d0617de4e4259bd72b3b5f5`.
Its ledger copy precedes this annotation. Every check launched for this batch
has reached a terminal result. The full SDK goal remains active.

## Private host transports and macOS offline desktop bundle — 2026-09-13

The host tools now share a bounded private-socket connection helper. The Windows
adapter constructs the documented Winsock AF_UNIX address because CPython lacks
its pathname parser; normal socket I/O and deadlines remain in Python. Windows
requires Python 3.13 or newer for private temporary-directory permissions and a
short enough temporary path. Native Windows execution is still untested. Session
paths are explicit rather than inferred from `getpeername`, and QEMU option paths
escape commas. Failed USB greetings close their connection.

GDB and layout inspection now use an SDK pipe relay on every host. It forwards
binary bytes with bounded buffers/connect/send waits, permits idle breakpoints,
and exits when either peer disconnects, including blocked output. It creates no
TCP listener. Quoting follows GDB 17.2's actual Unix shell and native MinGW
buildargv/pex implementations. Layout dumps use a fixed basename in the private
session because GDB's dump parser cannot quote a filename. `lefony-sdk debugger`
opens the matching project script; frozen subprocesses dispatch CLI arguments
instead of trying to execute a Python filename through the SDK executable.

The desktop packager now requires verified newlib, a pinned GDB build and libusb.
It checks the supplied source manifest and debugger install hashes, includes
GDB notices/source/recipe, and uses an explicit bundled USB-library path. Doctor
loads that library without enumerating devices. CMake uses the frozen executable
when included from a bundle, with no separate Python requirement. The new GDB
recipe builds 17.2 without an embedded Python runtime, avoiding the installed
Homebrew GDB's interpreter dependency. It retains its exact upstream archive,
notices, configuration and install hashes.

Two actual portability defects were fixed: comma-containing project paths were
split by GCC's `-Wl` forwarding (filename arguments now use `-Xlinker`), and
`expression_input.h` had acquired `string.h`/libc dependencies incompatible with
its existing callback users. Bounded byte comparisons and literal lengths now
preserve the same insertion semantics without requiring a foreground runtime.
File-level licenses are retained; no additional MIT grant, firmware/API/ABI,
storage layout or trust-root change occurred.

Validation on macOS 26.6.2 ARM64, Python 3.14.6 and GCC 16.2.0:

- **1,124 host tests passed**, with two expected private-DTB/DTS skips, in
  248.38 seconds before the final callback-header fix. **55 relevant tests**
  passed after that fix, including UI/math insertion, runtime/project integration,
  USB-library discovery and relay/socket lifecycle. Earlier focused runs passed
  79, 89, 105 and 66 tests at their recorded source checkpoints.
- The external main debugger passes its **five ARM developer cases**, including
  the one-shot main breakpoint, arguments, stepping, nonzero exits and callback
  relaunches. Public USB file exchange also passes initial/error/retry and cold
  phases with the shared connection helper.
- The relocated source kit passes offline Notebook preview and source-format 2
  export. A separate ARM stress test uses spaces, Unicode, commas, quotes and
  shell punctuation in project/session paths. Ordinary and unusual sessions
  produce identical frames and layout nodes through actual input/USB/GDB paths.
- A fresh public QEMU build uses neutral paths. All **11,231** inventoried source
  files match the original patched r70 checkout; upstream remains
  `c3d48b7d1e89604920e5b81b91140c2ad39a1943`. It is a different binary build,
  not the historical QEMU hash relabeled as new evidence.
- The **final frozen desktop candidate passes eight templates**: Basic, Pocket
  Lab, Forms/Tables, Graph Explorer, Reference Cards, C Main, Notebook and UI
  Gallery. Its SDK commands run after relocation into a path with spaces/Unicode,
  with network, Homebrew and checkout access denied. Tests include installed
  workspaces, clone/export/restore, source formats 1/2, main source debugging via
  the bundled GDB/relay, and Notebook/UI Gallery ARM layout inspection. The two
  final preview frames were visually inspected.
- A separate external-CMake check builds the frozen C Main project with Python
  discovery explicitly disabled. CMake itself runs outside the SDK sandbox;
  it is an optional host tool and is not bundled or included in the denied-access
  claim. No GitHub login, publication, physical USB operation or device write was
  performed. All processes launched for this checkpoint reached terminal results.

Retained failed attempts under `build/sdk-native-host` include the first path
harness's incorrect keyword, the real comma/linker failure, a relay test that
needed to recognize macOS ENOTCONN on peer shutdown, rejection of a QEMU binary
containing a private build path, a versioned SDL library filename supplied where
SDL2 compatibility loads its unversioned alias, and the first frozen Forms/Tables
build's missing libc header. The SDL failure was diagnosed from a process sample
and the pinned SDL2 compatibility source; the corrected build command supplies
`libSDL3.dylib`. None of these failed candidates is qualified.

Exact final identities (paths relative to `build/sdk-native-host`):

| Artifact/report | SHA-256 |
| --- | --- |
| `desktop-v4/lefony-sdk-darwin-arm64.tar.gz` | `c405219ecbd9b1fac49499793731de01dbe6c398ef2f8ce9f0eb6dfec6567c9c` |
| `desktop-qualification-v2/report.json` | `c393ceb7b264ea4e7a5d0bfaae4d01518a740903f1e8e037a17deb75b58a5a2f` |
| `host-full.log` | `a0d9edb5d5612c8844f3036e13362cb2f6f6e720e01010c27b2efa8a0d83aa0b` |
| `host-header-final.log` | `8bd6fe8253932c65d9b1d1c0f9399821dfff5ee4451752bda01d993c272df667` |
| `developer-relay/report.json` | `a095c18423445e0c1f42f8d887aa9cf99b7c506aa72b6082f5a4675edeabd1bd` |
| `relay-kit/report.json` | `893b949792eb108cec9110b63a5e7dde36cc405aaa6a113d70d34aa99ad9f226` |
| `path-stress-v3/report.json` | `d49d0105d2c34a756f6aec7c24651392c85c8a495fc5919dcbca728d90c35fb8` |
| `gdb-bundle-v1/install/bin/arm-none-eabi-gdb` | `3ed7b3d970df5291156104a678c79b2ed9d6fb01f4daa8bdf28e5bef2c57eba2` |

Final source/frozen SDK identity is
`80fea272a7c256eb739e57ec282610182190b10be2583a2a4a3adeb57c967157`.
The VM ELF remains `9efe4a74da490bdde5b667c124e3f1e80e3e0f25b38ab8eb0441f91e24629844`.
Public QEMU input is `752d0fe63fdb4501750b22b3ecf2cbe0bf4121eee95c3bafe7c936c109e132de`;
QEMU after PyInstaller adjusts its library paths is
`c6e5e83b8e398ebca70fc050ef2675f69321ad57953f43c377ddd67461f90ab2`.
Earlier source-kit/path/debugger reports preserve their preceding SDK identities;
the final desktop report qualifies its recorded offline journeys with the final
executable SDK.
This ledger/status annotation and the final host-guide limitation note postdate
that archive and do not change its executable SDK identity.

The full SDK objective remains active. A concrete next distribution issue is
native TLS trust: `store_client.py` and `https_worker.py` use OpenSSL defaults
that currently point to Homebrew CA files. The offline bundle pass does not prove
those defaults on a clean Mac. Native trust-store integration, frozen HTTPS/
companion and credential-store trials, native Windows/Linux, source-distribution
and release signing audits, broader recovery/resources, independent trials and
physical qualification remain open. The new bundle has not been published and
no complete 1.0 milestone is declared qualified.

Final whitespace and public-boundary checks pass for **1,018 files**. The six
updated SDK/setup guides have **66 checked relative links**. Read-only
`build/sdk-native-host/evidence` retains **103 files, 157,911,906 bytes**, including
source snapshots, reports, reviewed preview frames, the final desktop archive
and retained failures. Its verified index SHA-256 is
`44f2c4548c1cfa9e705dee5848e65ce4af1157626c181ca20562fb7476cc8394`.
The copied ledger predates this annotation. No process from this checkpoint is
still running; the full SDK goal remains active.

## Frozen native HTTPS trust and macOS Keychain — 2026-09-13

The SDK account client and HTTPS companion now share `tls_context.py`. Default
connections use pinned truststore 0.10.4 and the native host certificate store.
Explicit development CA files use a separate standard SSL context, replacing
system trust for that context. Both paths require certificate and hostname
verification, TLS 1.2 or newer and HTTP/1.1. No global SSL monkeypatch or system
certificate-store change is used. Missing native trust fails clearly instead
of falling back to Homebrew CA paths. The companion retains its disposable
worker, streaming protocol, deadlines and cancellation behavior.

`doctor --https-origin ORIGIN` explicitly sends HEAD to the origin root through
that worker. The ten-second probe sends no credentials and downloads no response
body. A verified HTTP error response establishes TLS connectivity, not application
health. Ordinary doctor remains offline. `--https-ca-file` is valid only with an
explicit origin. The host guide documents these distinctions.

The desktop packager includes truststore, requires matching source/version and
license notices before building, checks installed-notice hashes and records the
TLS policy/version in `candidate.json`. Its `network_qualified: false` is build
metadata: subsequent qualification is recorded by the separate exact-hash reports
below, rather than rewriting the tested candidate. The dependency collector can
refresh Python inputs in a copied, hash-checked source manifest and now retains
installed distribution notices, including Pillow's composite wheel license.

Validation on macOS 26.6.2 ARM64:

- **173 focused host tests pass**, 13.41 seconds, covering native trust and
  explicit-CA isolation, certificate/hostname failure before credentials reach
  the HTTP handler, HTTPS streaming/bridge behavior and account/upload/publication
  regressions. Earlier retained runs have 167 and 62 passes. No new full-host-suite
  or firmware-build claim is made for these host-only changes.
- **Eight frozen HTTPS cases pass** after relocation to a path with spaces and
  Unicode. Homebrew/checkout reads and Homebrew execution are denied; OpenSSL CA
  environment paths point to absent files. Default doctor remains offline;
  untrusted local roots and a wrong hostname fail; an explicit localhost CA
  succeeds with HTTP 503 and no body or Authorization header; subsequent native
  trust still rejects that local certificate. A stalled handshake ends at
  **10.200 seconds**, and Ctrl-C ends its worker and observed child processes.
  A read-only public HEAD to `https://www.python.org` succeeds with HTTP 200.
  The full invocation takes 0.318 seconds in the cancellation case; the harness
  also asserts less than three seconds from the actual cancellation signal.
  This is local timing evidence, not a supported-host performance budget.
- **Sixteen frozen account steps pass using actual macOS Keychain** with
  Homebrew/checkout access denied. A controlled local HTTPS service supplies
  synthetic account authorization; the normal CLI performs login, whoami,
  draft/published/withdrawn app listing, origin isolation, replacement login
  with old-session revocation, remote revocation and local credential removal,
  and explicit logout. Each command is a fresh frozen process. The fixture
  refuses a pre-existing credential at its selected origin, retains no token in
  evidence, and verifies final credential cleanup. GitHub OAuth, browser approval
  and the production Worker are not replaced or qualified by this fixture.
- **Eight offline desktop templates pass again** with network, Homebrew and
  checkout access denied, including ordinary main debugging, source formats 1/2,
  workspaces and ARM preview. The separate external-CMake check runs outside that
  sandbox with Python discovery disabled. Notebook and UI Gallery pixels match
  the previously reviewed desktop frames exactly.
- The **source companion command engine passes its signed ARM/USB/TLS journey**:
  normal pairing consent, the narrow channel request set and an independently
  checked 131,073-byte cached response. Its report now includes the shared TLS
  helper's source hash. This uses the unchanged API 12 VM ELF and the original
  developer QEMU; it is not a frozen companion USB-streaming qualification.
- A packaging rejection check confirms a manifest without truststore is refused
  before any candidate directory is created.

The first full native-source collection attempt rejected
`libjpeg.62.4.0.dylib`. Inspection of PyInstaller's actual input table identifies
**13 bundled native library inputs from the Pillow wheel**, rather than the
similarly named Homebrew libraries. Their input and bundled hashes are recorded
in `pillow-native-source-audit.json`. Pillow's sdist and installed composite
notices are retained; the exact dependency-source audit remains open before
distribution. `--refresh-python` updates the copied Python source inputs without
claiming to resolve that native audit. Expected local TLS fixture peer resets
appear in retained test logs; both test processes report passing terminal results.

Exact artifacts/reports, relative to `build/sdk-native-tls`:

| Artifact/report | SHA-256 |
| --- | --- |
| `desktop-v1/lefony-sdk-darwin-arm64.tar.gz` | `c1563729932cddde81117b1b47c32157959ef5ea023c0347f6ef3c3ae7a8c950` |
| `desktop-https-v1/report.json` | `e97b08e6e1ca0fa2705f899b8d590be68975ec9ac1f943477ff7a03138c35118` |
| `desktop-accounts-v1/report.json` | `39d6e705f88edf7e4978ea34fee641518a41f99944a076adcfc5b1fc51f57ff2` |
| `desktop-offline-v1/report.json` | `8659d67c60992955c539ac4d87bbbf71b057725bf7ff59b917bb5bc14746d491` |
| `host-final-focused.log` | `5e8f962116cfaeda37c1333829c0abad8b566847948eb79c0ad174fdf8ea7603` |
| `companion-arm-v1/report.json` | `f0f41b843a4d74c993096d86f1bd30a02cda393ea97eda6f8c108fc6e2e4485e` |
| `desktop-sources/manifest.json` | `8657dcd6cc7dcf3a23e1fd44c9037e0d4dcd4d562681f40189aea84d98d4475a` |
| `pillow-native-source-audit.json` | `a7feb759c7eb862a9082e639299489aed6b02593f9d830a9ee450ac3328ffbb1` |

Source and frozen executable SDK identities both equal
`8bcee820c28d48b2d44c0523f62795197b8ddac9d466a9cf502d1b30055f41d4`.
The VM ELF remains `9efe4a74da490bdde5b667c124e3f1e80e3e0f25b38ab8eb0441f91e24629844`.
The frozen candidate uses the preceding neutral-path public QEMU input; the
source companion test uses `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The later account/channel/top-level notice and status documentation updates
postdate the archive and do not alter its executable SDK identity. The truststore
component's complete license notices are already inside that archive.

The full SDK objective remains active. Remaining work includes frozen companion
USB streaming, real GitHub/production-store and clean-host operation, native
Windows/Linux, full dependency-source/signing/download audits, broader resource
and unreadable-media recovery, independent trials and physical qualification.
The account client's synchronous DNS/native trust verification still lacks a
hard total deadline; its documented socket and polling deadlines do not change
that limitation. No device operation, deployment, commit, push or new release
signing identity occurred.

Final whitespace and public-boundary checks pass for **1,023 files**; **79**
relative documentation targets and all eight checkpoint artifact hashes verify.
Read-only evidence under `build/sdk-native-tls/evidence` retains **138 files,
157,779,742 bytes**, including source snapshots, tested desktop archive,
qualification reports, exact truststore source/notices and the native-source
audit finding. Its verified index SHA-256 is
`208198ae07ea75bd456bc5f8f6933ed1a405199f9ab5dfa469ce51ee6839039b`.
The copied ledger precedes this final evidence annotation. Every process launched
for this batch has reached a collected terminal result; no temporary Keychain
credential remains. The full SDK goal remains active.

## Frozen companion streaming and orderly interruption — 2026-09-13

`companion --emulator-usb SOCKET` now connects to an explicit, exclusive,
already-enumerated QEMU USB endpoint. It uses the same app/signer/package grant,
HTTPS policy, channel client and OS-owned pairing consent as the physical
companion. Its adapter accepts only channel reads `0x78/0x7b` and writes
`0x79/0x7a/0x7c/0x7d/0x7e`, with bounded fields/payloads. It never discovers a
physical device, resets/enumerates USB, or falls back to physical USB after a
model connection failure. `PrimeUSBHost.lend_connection()` temporarily releases
the model socket and restores the same host object after the borrower exits;
it does not reset the emulated bus. Physical firmware has no new test interface.

Pairing and progress output now flush immediately when the CLI is piped or
launched by a GUI. This permits the real external companion to show its consent
prompt while it is still running, instead of waiting for its output buffer or
process exit.

The first frozen candidate passed the download and eight further streaming/error
cases, then failed host interruption: the companion exited successfully while
the ARM probe reached its unexpected-channel-error assertion. An unchanged
repeat passed, identifying a timing-dependent failure. `KeyboardInterrupt` can
interrupt a model socket operation midway through a USB control transfer, leaving
the cleanup channel-close request ambiguous. The CLI now records SIGINT and
observes cancellation at bounded transaction boundaries. It stops before
advancing pairing/connection operations, cancels the worker and closes its
channel, then restores the prior signal handler. It does not retry an uncertain
mutation. Signal tests exercise interruption during status, attachment and
pairing and require transaction completion before cleanup.

The new `vm/test-sdk-frozen-companion.py` qualifies the actual relocated frozen
CLI and spawned network worker. That executable builds every external C project
and runs the companion with Homebrew/checkout reads and Homebrew execution
denied. The harness separately drives synthetic storage and normal KPP/Goodix
input on the bundled ARM guest/QEMU, supplies a controlled local TLS service,
and verifies exported cache bytes. The source harness and executable SDK
identities must match. This is a model-USB integration check, not physical
libusb, electrical-disconnect or GitHub qualification.

Validation on macOS 26.6.2 ARM64:

- The **final frozen candidate passes all ten ARM journeys**: fixed and chunked
  GET, fixed and chunked POST, denied origin, untrusted TLS, response timeout,
  app cancellation, truncated response and host Ctrl-C during an active request.
  The normal pairing screen was inspected and its displayed code matched the
  companion output. Every app exits successfully, the OS remains responsive,
  and observed worker/resource-tracker processes stop.
- Both successful GET cases export exactly **131,073 bytes**; POST cases upload
  and retrieve **70,017 bytes**, checked independently by server and host hashes.
  Error/cancellation cases preserve the prior **31-byte cache**, and the temporary
  download file is absent after cleanup. Denied-origin and TLS cases reach no
  HTTP fixture handler. Explicit error categories and request framing are checked.
- **Three additional independent frozen disconnect runs pass**. Their full
  companion invocations take 1.371, 1.306 and 1.274 seconds, including startup,
  pairing and the intentional handshake. Each sees channel state ENDED/error
  DISCONNECTED, successful app exit, preserved cache and both observed children
  stopped. The harness separately bounds signal-to-exit at five seconds. These
  observations are not physical timing or a ratified host performance budget.
- The full host suite passes **1,135 tests with two expected private DTB/DTS
  skips**, 241.28 seconds, **before** the final signal-handler change. The final
  focused suite passes **54 tests**, 6.93 seconds, after that change, covering
  signal cleanup, model socket handoff, request restrictions, channel ownership
  and HTTPS bridge behavior. No new firmware build or broader final full-suite
  claim is made for these host-only changes.
- An initial unit fixture exceeded macOS's socket-path limit. It now uses the
  SDK's existing private short-session directory; the adapter's bound was not
  weakened. Earlier focused runs and the failed frozen candidate remain retained.
- A first direct invocation of the final executable against a missing model
  socket exceeded an **eight-second subprocess watchdog** and was killed/reaped.
  Its startup stage was not sampled, so this is an unresolved startup observation,
  not a diagnosed connection-loop regression or a pass. With no source/binary
  change, follow-up source/frozen commands returned the expected error in
  **3.111/3.161 seconds**. Those follow-ups verify the missing-socket path; they
  do not qualify cold-launch latency or explain the initial timeout.

Exact reports/artifacts, relative to `build/sdk-frozen-companion`:

| Artifact/report | SHA-256 |
| --- | --- |
| `desktop-v2/lefony-sdk-darwin-arm64.tar.gz` | `4b43ca1457770d82dae4dcf8e57ab88b06a51098bb9758daf6dcb5bc0e1ffc6b` |
| `qualified-v2/report.json` | `5aa86b1f7cb13c3ea54197a569fc9033e95f3290a3a47186ad5e5ff80cf36c7c` |
| `host-full-v1.log` | `b323f4c34b788cff688409edd6c240204509e719b98e2407f33e5aee0c78341c` |
| `host-signal-final.log` | `c418065675c8b56054a149262918bb960639313f6ba28f8de07e256caba8a8c8` |
| `disconnect-repeat-1/report.json` | `f640a68312685967e6193f164c38d522fb46ec617ace33f2d48e7865ff0646a8` |
| `disconnect-repeat-2/report.json` | `67bd1e0f43328263ab44679c5c46cc7bab497f7d243cdbb676c1926865a6fb63` |
| `disconnect-repeat-3/report.json` | `6ca91866e7fab9854203f94d327cf37380ba306ffee0d61e718f9353ac685de7` |
| `missing-model-observed-v2.json` | `856786f75bf0af784a768f9172e5ee4a1ed6fcddc3bc1b32531cc09d2f4c1043` |

Source and frozen executable SDK identities both equal
`eae4eaa3f76d6fb4dba62512e9b536dac0dcab8c2374b02371c0fd9c454a9558`.
The original frozen archive was
`902f80bab2c977d25e57a877d91d5df3658e2714a808ef487667e12f5b65509e`;
its evidence is not relabeled as the final fixed candidate. Firmware, QEMU input,
compiler/newlib/GDB, truststore, USB library, source-material manifest, signatures,
ABI and storage layout are unchanged from the preceding native-TLS batch. The
channel guide is included in the final archive; later host/testing/status/ledger notes
do not change its executable SDK identity.

The complete SDK objective remains active. Remaining work includes physical
companion/USB and supported-host qualification, real GitHub/store operation,
the synchronous account client's total DNS/TLS deadline, source/signing/download
audits, broader application resource and unreadable-media recovery, measured
startup/performance budgets and independent developer trials. No physical device
operation, deployment, commit, push or new signing identity occurred.

Final whitespace and public-boundary checks pass for **1,025 files**; **75**
relative documentation targets and all eight checkpoint table hashes verify.
Read-only evidence under `build/sdk-frozen-companion/evidence` retains **325
files, 170,863,521 bytes**, including the final desktop archive, exact source
snapshots, pre-fix companion code, all completed and failed runs, reviewed
pairing frame and the unresolved first-launch observation. Its verified index
SHA-256 is `6408a0c2c1ea7fdfa43984fc000f43f2dace528b060ace806e1aa6ae36ea1ac0`.
The copied ledger precedes this final annotation. All processes launched for this
batch have collected terminal results. The complete SDK goal remains active.

## Store HTTPS deadlines, frozen accounts and publication regression — 2026-09-13

This closes the synchronous store client's DNS/TLS deadline gap recorded above.
It does not complete the SDK objective or qualify the release on other hosts.

`sdk/tools/store_http.py` owns one HTTPS request in a disposable spawned process.
The parent enforces a 20-second deadline across child startup, IPC, DNS,
certificate setup/verification, request upload and complete response. An IPC
thread prevents a blocked send or partially received process message from
blocking deadline supervision. Requests retain the existing body limits (up to
8 MiB for listing edits); responses remain bounded to 1 MiB. No credential is
written to a file or supplied as a process argument. Redirects are rejected
before reading their bodies, certificate verification stays enabled, and
fixed-length truncation is rejected even when the received prefix is valid JSON.

Ctrl-C during startup is deferred until the parent owns the child handle; during
cleanup it is deferred until termination, bounded joins and pipe cleanup finish.
The child ignores terminal SIGINT and the parent owns cancellation. A failed
worker is terminated and reaped, with at most 0.9 seconds of explicit cleanup
joins under normal scheduling. Unexpected failure to stop the process or IPC
thread is reported. Certificate context setup now occurs on the first network
request, rather than constructing a client for an offline/empty-account command.

The transport never retries. Existing higher-level publication retries for the
same idempotent operation remain, as do saved attempt/status/resume receipts,
bounded sign-in polling and cancellation of an issued authorization ticket.
An in-flight sign-in request or its final cancellation can each use their own
20-second deadline; this is not a promise that an entire multi-request command
finishes within 20 seconds. A failed mutation may already have reached the server.

The process/thread design follows Python's documented
[spawn and connection behavior](https://docs.python.org/3/library/multiprocessing.html)
and [bounded thread waits](https://docs.python.org/3/library/threading.html).
Each pipe is discarded with its child, so termination cannot corrupt a channel
reused by a later operation. Frozen operation is established by the actual
PyInstaller executable tests below, rather than inferred from source execution.

### Validation

- **190 focused host tests pass** in 18.27 seconds. These cover account/upload/
  listing/publication recovery plus real local TLS, exact 8 MiB listing uploads,
  256 KiB binary chunks and 1 MiB JSON responses. Fault tests stall DNS and the
  native certificate-verification hook, stop a child reading an 8 MiB IPC
  request, partially write an IPC response, kill a worker, remove native trust,
  and interrupt normal requests and process-start/cleanup boundaries. Every
  completed case checks process and IPC-thread cleanup. The raw partial-IPC
  fault is POSIX-specific and explicitly skips on native Windows.
- **Seven frozen macOS network cases pass** with Homebrew/checkout access denied:
  ordinary error, stalled headers, slowly delivered body, stalled TLS, Ctrl-C,
  truncated JSON and redirect. Entire command durations are respectively
  0.953, 20.320, 21.028, 20.308, 1.980, 0.530 and 0.853 seconds. Ctrl-C-to-exit is
  0.805 seconds. Each non-TLS case makes exactly one authorization POST; the TLS
  case reaches no HTTP handler. No account is issued or stored. Both observed
  child processes stop after each command. These durations include executable
  startup and are not new cross-host performance budgets.
- **Sixteen frozen native-Keychain account steps pass** against controlled local
  TLS: empty account, login, owned apps, origin isolation, account replacement,
  remote revocation, local cleanup, logout and final empty credentials. The
  harness refuses preexisting credentials at its fixture origin and removes all
  temporary records. This is real macOS Keychain evidence, not real GitHub OAuth.
- **28 actual CLI publication steps and 105 local HTTPS requests pass** against
  the unchanged website Worker with isolated Miniflare D1/R2. Three dropped chunk
  acknowledgements and three dropped listing acknowledgements preserve recovery.
  The journey includes real ARM-tested packages, SDK/website updates, metadata
  edits, pull/merge, stale edits, account separation, withdrawal/republication,
  receipts after staging cleanup and exact signed package/source downloads.
  This runs the SDK source copied from the new bundle using the project's host
  Python; it is separate from the frozen executable checks. Its unchanged
  counter-app guest uses API 11 firmware and the developer QEMU recorded below.

First host runs exposed fixture defects: a one-byte error in the maximum JSON
size, accessing truststore's intentionally hidden module attribute, and trying
to pickle locally replaced `Process` methods. The corrected verification-hook
import and process-owner wrapper exercise the intended stages. Original logs
are retained; the final 190-test pass covers the finished implementation.
The TLS fixture may report an expected peer disconnect when the verification
fault kills its client. No production service or connected calculator was used.

Commands and artifacts are under ignored `build/sdk-store-deadline/`. The new
desktop harness is `vm/test-sdk-desktop-store-deadline.py`; the native account
harness remains `vm/test-sdk-desktop-accounts.py --native-credentials`. The
publication run uses the website's `scripts/test-sdk-publication.ts` with output
under its ignored `.local/sdk-store-deadline-publication/`. Both firmware targets
and the companion are unchanged; no firmware builds or full host-suite rerun
were needed for this store-client change. Earlier offline-template and companion
evidence retains its own candidate identity and is not relabeled here.

### Exact candidate identities

Source and bundled SDK executable inputs both hash to
`f06a4b1cd6df86575b63936f79014df672d110387e648c310d72fbd5547b5cd1`.

| Artifact | SHA-256 |
| --- | --- |
| `desktop-v1/lefony-sdk-darwin-arm64.tar.gz` | `9568f59c07677e1eb560ab1c4537d08a012affed7975ab36a5d1a3f671a956b3` |
| `frozen-deadline/report.json` | `371eecf4dc7be34a84533ec9f4e3c17eb92d5a62809cd5abb395c238149216d2` |
| `frozen-accounts/report.json` | `fa50d4af6cdd7fd5cc7b3f28f75868fa6d703dac9c4e5b1d646458dece6a1c54` |
| `host-verified.log` | `22469de703f25403ae830342af1b6b2e8930bdc36b91fda58e6d99d3f6e10835` |
| Website `report.json` | `efc3822f7353ea2d26236dd1ad0ea9d1f7200a9a7ebb2079de045eb31bfe7856` |
| Website `cli/report.json` | `ccad46cfff3fa9714ca793b146a072c78cfd0ffaf4348e67e34f2f4e182d1934` |

The frozen bundle includes API 12 firmware
`9efe4a74da490bdde5b667c124e3f1e80e3e0f25b38ab8eb0441f91e24629844`
and bundled QEMU
`c6e5e83b8e398ebca70fc050ef2675f69321ad57953f43c377ddd67461f90ab2`.
The separate publication regression uses unchanged API 11 firmware
`b602aa6982ae508bb2bc3f14021971f85e00a186e9beb92a09d344cec3fbd70c`
and developer QEMU
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
Compiler, newlib, GDB, native trust library, source-material inputs, ABI, storage
layout and signing identities are unchanged. The archive includes the revised
account guide; later testing/host/status/ledger notes do not alter its executable
SDK identity. Complete Pillow native dependency-source auditing remains open.

The full SDK objective remains active: native Windows implementation, clean
supported hosts, real GitHub/store operation, general unreadable-media recovery,
production media capacity/reclamation, broader C/UI/application resource cases,
measured performance/startup budgets, independent developers and physical
qualification still require work. No deployment, commit, push or physical
operation occurred.

Final public-boundary checks pass for **1,028 files**; **107** relative
documentation targets, checkpoint hashes and changed-file whitespace verify.
Read-only evidence under `build/sdk-store-deadline/evidence` retains **136 files,
157,053,470 bytes**, including the frozen archive, exact changed sources, website
Worker/migration sources, completed reports and earlier failed fixture runs.
Its index SHA-256 is
`fb9445a2c13a8d7a031cd4d9b98ae88cea24f55bea367f03a853b303bed1c693`.
The copied ledger precedes this annotation. All launched jobs have collected
terminal results; the complete SDK goal remains active.

## Store artifact reservations, cleanup and retained history — 2026-09-13

The website backend now reserves D1 capacity before writing local SDK/browser
publication artifacts or new listing images. Migration `0009` introduces
managed global/account usage, unique `store-stage/UUID` prefixes and immutable
committed allocations. Release/listing references commit in the same transaction
as the allocation, following the existing authorization, ownership, revision,
version and completed-write gates. Duplicate operations cannot retain an unused
competing stage. A stage cannot become deletable after its reference commits,
even if the clock reaches expiry between statements in that transaction.

Initial managed admission policies are 10 GiB total, 512 MiB per account and
three unexpired artifact stages per account. They are configurable maintainer
policies, not Cloudflare platform limits. Raw SDK chunks and sealed files reserve
twice the manifest total; finalization separately reserves the manifest total
plus the 352-byte signature envelope. SQL triggers account for these records and
backfill existing uploads. Cancellation retains the allocation until confirmed
R2 deletion and D1 row removal. Text corrections, reuse of owned images, owner
reads and withdrawal remain available when capacity is full.

Scheduled maintenance handles expired stages and terminal SDK attempts, with
bounded inventory pages catching delayed writes after their records disappear.
Accepted releases and listing history remain immutable and retained, including
withdrawn/hidden versions and historical `sdk-upload/.../ready/...` downloads.
Failed deletions retain their allocation; retries and competing cleaners release
it once. Cleanup counters use returned deleted rows rather than trigger-inclusive
D1 change counts. Aggregate logs omit account identifiers and credentials.

Legacy shared-media cleanup defaults off. It may be enabled only after old
shared-key writers have drained and the store uses local-SDK publication. It
preserves every legacy release/listing reference, regardless of visibility.
Older committed objects and unrelated bucket contents are outside the new
managed counters; production inventory must reserve their headroom separately.
Legacy shared source/package reclamation is not implemented by the media sweep.
The website's `docs/STORE-MAINTENANCE.md` documents costs, retention, scheduling,
inspection queries, rollout requirements and these limits. No production
migration or policy change was executed.

### Validation

- The full website suite passes **548 tests with one conditional fixture skip**
  in 63.50 seconds using `npm test -- --no-file-parallelism`. The skip is the
  optional `LEFONY_SDK_TEST_PROJECT` input, not a claimed ARM pass.
- The final **50 artifact/upload tests pass** in 23.71 seconds. These include
  an additional capacity-parity case plus final cleanup counter changes:
  simultaneous account/global admission, migrated reservations, file readiness,
  expiry during commit, deletion failures before/after acceptance, duplicate
  operations, late writes, multi-page inventory and retained history. Actual
  browser/SDK paths reject new bytes at capacity while allowing owned-image
  reuse, text corrections, reads and withdrawal.
- **28 CLI steps and 105 local HTTPS requests pass** with four actual ARM-tested
  versions, three deliberately lost chunk acknowledgements and three lost
  listing acknowledgements. The journey covers SDK/browser publication, metadata
  edits, pull/merge, ownership isolation, withdrawal/republication and exact
  signed package/source downloads.
- The CLI harness now invokes the **production scheduled handler twice** instead
  of directly deleting upload rows. It removes all three terminal attempts and
  **30 temporary R2 objects**, preserves the identity/size of **19 accepted
  artifacts**, verifies two historical owner-image hashes and the current signed
  package, then completes actual SDK receipt status/cancellation. Reserved bytes
  decrease from **155,757 to 62,601**, exactly the retained committed allocations.
- Website production build and lint pass. No browser UI changed in this batch;
  no new visual acceptance is claimed.

The earlier parallel full-suite run had two 5-second recovery-test timeouts
(544 passed, one skipped). Both affected files pass separately (26 tests), then
the entire suite passes sequentially without changing their tests or timeout
thresholds. Earlier artifact fixtures also exposed D1 trigger-inclusive change
counts, immutable R2 metadata and D1 exec's line handling; corrected fixtures
exercise the intended behavior. Original failure logs are retained alongside
passing results. The first TypeScript failure in source-buffer ownership was
fixed with an owned ArrayBuffer before the successful builds.

The publication runner is the website's `scripts/test-sdk-publication.ts`, using
the OS `vm/test-sdk-store-publish.py` and SDK source copied from the previous
frozen macOS candidate. It does not run the frozen executable or real GitHub.
All accounts, keys, TLS service, D1/R2 and calculator storage are synthetic.
Physical firmware, SDK executable code, signing identities, protocols and
calculator storage layout are unchanged; no firmware rebuild was needed.

### Exact inputs and reports

The website's ignored `sdk-artifact-publication/backend-inputs.json` records 75
source/configuration files. Its canonical file inventory hashes to
`dacf0080dabdb8862bc283d164c7a597ff65c0e2ce0f05566f5b7921a6c6ba4b`.

| Input/report | SHA-256 |
| --- | --- |
| SDK executable inputs | `f06a4b1cd6df86575b63936f79014df672d110387e648c310d72fbd5547b5cd1` |
| API 11 publication fixture ELF | `b602aa6982ae508bb2bc3f14021971f85e00a186e9beb92a09d344cec3fbd70c` |
| Developer QEMU | `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0` |
| Website publication `report.json` | `1b046bd54ad9a88b05180c45b30e48970948fd17af4097a7abf1c22958c1e6a8` |
| CLI `report.json` | `915e0110acec54377ea7dcc48405bfb68b92ccceb9180fe9f279c86ee5e9a869` |
| Full sequential suite log | `e2ef45a0ac9e28a1aebf5f1d2e1a24e8e3ebadd7efb4f6a9dfb5cf937630a38e` |
| Final 50-test log | `5d2471a9c8bedbf1d8b8309a443bd190f26109597b310af91ed43664cc2b8d1c` |

Logs/reports remain under the website's ignored `.local/sdk-media-*` and
`.local/sdk-artifact-publication/`. Production migration and writer cutover,
legacy inventory and load/capacity qualification remain open. Native Windows,
clean supported hosts, real GitHub/store operation, source auditing, unreadable
calculator-media recovery, broader application/runtime cases, independent trials
and physical qualification still require work. The full SDK objective remains
active. No deployment, commit, push or physical operation occurred.

Checkpoint boundary checks pass for **1,028 public files**, **106 relative
documentation targets**, all 75 backend input hashes and changed-file whitespace.
Read-only evidence in the website's ignored `.local/sdk-artifact-storage-evidence`
retains **297 files, 1,958,620 bytes** of sources, test inputs, reports, artifacts
and original failed/passing logs. Its index SHA-256 is
`1ce290c32230816a4f2e747f922a90d6d9d68035fb438dc56bdabb193b540509`.
The copied ledger precedes this annotation. All launched jobs have collected
terminal results; the full SDK goal remains active.

## C library matrix, descriptor width and formatted I/O — 2026-09-13

The ordinary `foreground-newlib-1` runtime now has a selected
[function and behavior matrix](../sdk/C-LIBRARY.md). Its conformance fixture
runs signed, conventionally built C programs with the actual 8,380,416-byte
heap, public file services, normal main/exit and host file exports. It does not
replace the allocator or implement successful fake syscalls.

This work found and fixed two real integration defects:

- Upstream newlib stores `_file` as `short` in both `FILE` variants. Lefony's
  deliberately non-reused handles are positive 31-bit integers; `fdopen` lost
  descriptor 32,768 in the previous frozen SDK. The recipe now applies
  `stdio-descriptor-32-v1`, widening both fields to `int` and preserving every
  other header byte and upstream notice. Exact before/after hashes reject
  unexpected source; repeated preparation is idempotent. The raw file adapter
  and its stale-handle guarantees remain unchanged.
- The earlier newlib configuration left long-long/C99 formatted I/O disabled.
  The ARM fixture failed its `%llu` required-length check. The recipe now
  explicitly enables both options, and tests formatting/scanning with 64-bit
  boundaries, size/offset/intmax formats and hexadecimal floats.

This is an app-local library ABI change. The entire sysroot and all app objects
must use matching rebuilt headers/libraries. The resolver rejects old reports
and incompatible `FILE` headers even when their self-reported inventory matches.
The source adjustment is part of dependency identity; existing projects explicitly
adopt it through `lock --update`. Previously compiled apps retain their older
library behavior until rebuilt. Firmware ABI, capability IDs, storage geometry,
trust roots and upstream archive/compiler pins are unchanged.

### Validation and limits

- **15 source/debug ARM phases pass**, followed by **15 optimized ARM phases**
  using the SDK source and newlib copied from the new macOS bundle. These cover
  actual allocation exhaustion/reuse/overflow, strings and C-locale ASCII,
  formatting/scanning, representative binary64 math/errors, streamed files over
  64 KiB, short transfers/seek gaps/append, directory and access errors, durable
  cold files, unsupported-service errors, sleep/yield, normal and immediate exit.
  The optimized run uses the host Python and developer QEMU, separately from
  the frozen-executable checks below.
- Three cases seed only the synthetic OS handle serial and the fixture gate
  using GDB, then perform ordinary public I/O. They exercise 32,767–32,774,
  65,535–65,542 and 2,147,483,631–2,147,483,638. All descriptors survive stdio;
  closed handles remain invalid. This is numeric-boundary injection, not a
  claim of thousands of opens or physical endurance. The debug ELF's loadable
  bytes match the tested firmware exactly.
- **Four C++ main phases pass** for initializers, arguments, `atexit`, global
  destructors, nonzero exit and cold reopening. **Four existing writer-abort
  phases pass**, preserving stale-handle isolation, normal/cold files, denied
  access and API 11 fallback. Their fixtures keep the original contracts.
- **Eight frozen macOS template journeys pass** after relocation into a folder
  with spaces/non-ASCII characters, with network, Homebrew and checkout reads
  denied. They include offline build/source/test, persistent workspace exchange,
  C-main GDB, external CMake with Python discovery disabled, Notebook preview
  and UI Gallery inspection. CMake's own setup remains outside the SDK sandbox.
- The relocated source kit is byte-identical across two builds and verifies all
  **415 files**. External CMake, C-main relaunch/cold persistence, input-stream
  checks and minigzip build/source generation use its bundled sysroot.
- **Six minigzip regression phases pass** with the rebuilt current library:
  compression, decompression and allocation-failure handling, each followed by
  cold reopening. Public file exchange verifies output and preserves earlier
  data on failure. The pressure fixture retains 8,323,072 real heap bytes in
  both launches. Earlier full-quota/Home/error workloads retain their separate
  candidate evidence; these six cases do not relabel that entire prior matrix.
- **The full host suite passes 1,161 tests with two expected private DTB/DTS
  skips**, in 450.09 seconds. The focused runtime/C/file-session checks also
  pass, including preparation replay and old/mixed-library rejection.

The first fixture build needed parentheses around two classification comparisons
under GCC's warning-as-error rules. Its next run exposed the disabled formatted
I/O options; the retained older SDK reproduces the descriptor failure with
identical C source, manifest and project configuration. All original failure
reports/logs are retained. The all-groups debug fixture's code grows from
107,176 to 116,352 bytes, with static data from 10,768 to 10,780 bytes; the
optimized current fixture uses 112,728 code bytes. These are fixture footprints,
not minimum-app or physical performance budgets. Stack peaks remain unmeasured.

An initial desktop build used a versioned SDL3 filename supplied in this run.
SDL2 compatibility searches for `libSDL3.dylib`; process sampling showed a modal
missing-library alert during `--version`, not a signature-validation stall.
Two bounded probes of that incomplete bundle timed out; signature verification
passed. Rebuilding with the documented unversioned library name succeeded, and
all eight frozen journeys use that corrected bundle. No timeout threshold,
security setting or packaging check was relaxed.

### Exact candidate identities

SDK executable inputs in the checkout and corrected bundle both hash to
`42954442d3457d5183527b94e0f474a41fc08f5f51fc139200b4ec71a7d21342`.
The source pin remains newlib 4.6.0.20260123 with GCC 16.2.0. The newlib header
inventory hashes to `66b8e5d672fcd2c0c3bcb90710791d83949d11f7c183683781b82ab45be443ed`.
Its library hashes are `2a682114e9087f218f3d7058d7d2223cd0668b2fbb86067f7a7dbe1e738ee7b8`
(`libc.a`) and `05d44e396f7b20bf0081b46a3bd628e863c5a0f3336561168e4ca1a53a1df3e8`
(`libm.a`). Complete notices and the unchanged upstream archive accompany the
sysroot; the durable build recipe applies the source adjustment.

| Artifact/report under ignored `build/sdk-c-runtime-profile/` | SHA-256 |
| --- | --- |
| `desktop-v2/lefony-sdk-darwin-arm64.tar.gz` | `4bbfa897943d7f892104f7e748739489cb954919107419ea51af43caba3db182` |
| `source-kit/sdk-with-newlib.tar.gz` | `90418d235e0810730801eae318fb03b41d17479389089b4a0a4a18ee246b1099` |
| `conformance/report.json` | `7bad67a8806a2d901eec5e9a774c6406ae3d34de32994086b3319cee8d209777` |
| `bundled-release/report.json` | `1384a9de4937c46a7dafb06b14f707a32df34445d370a83432721d46e6716bbf` |
| `frozen/report.json` | `ca02d7ea599b2927beefdb5d8bd9dbedc6d71817068298027f55db0a067c6a86` |
| `cpp-main/report.json` | `70c78aca158e93891c9468150de46ff6a9ebecff77aac5b1565c44f39b35ed77` |
| `abort/report.json` | `140c10f6d06f222321e505481c86072207c1dffd8f08e5bed10ede800fb19741` |
| `minigzip/report.json` | `0493106d99a1b6532ab54ae1cddacf7489b61e93b26d211d5de7ec41c8472626` |
| `full-host.log` | `353b3d73db117625e54b7ba2141dc8026976ce1680067e4a93332400bfd10093` |

The firmware stays API 12 ELF
`9efe4a74da490bdde5b667c124e3f1e80e3e0f25b38ab8eb0441f91e24629844`.
The API 11 fallback fixture stays
`b602aa6982ae508bb2bc3f14021971f85e00a186e9beb92a09d344cec3fbd70c`.
Direct ARM tests use developer QEMU
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`;
frozen journeys use the bundle's QEMU, with its identity in `candidate.json`.
Later documentation/ledger annotations do not change executable SDK identity;
these artifact hashes retain their own packaged documentation snapshots.

### Library-comparison input and remaining scope

The isolated Picolibc comparison recipe builds version 1.8.12 at commit
`2ae376c6cdf4fef90ca2388ecf7a07457fa63cff`, with source archive hash
`2946ea55b915f7f4555d60bffbaea6a3edc0b8993b7ded3935be9a15cfb7157b`.
It uses the same Cortex-A7 hard-float compiler, Meson 1.7.2 and no picocrt,
semihosting or TLS. The recipe is `scripts/build_sdk_picolibc_comparison.py`;
inputs and logs are under ignored `build/sdk-library-comparison/`.
Picolibc's [OS integration contract](https://github.com/picolibc/picolibc/blob/1.8.12/doc/os.md)
requires real allocation, file and termination adapters. The
[1.8.12 release](https://github.com/picolibc/picolibc/releases/tag/1.8.12)
also uses 64-bit `off_t`, which must be handled at the adapter boundary.
No Lefony Picolibc app has been linked or run, and no dummy-host/semihost library
is used by the SDK. Raw archive sizes are not a workload comparison. The
library/profile decision remains open; the default SDK stays on newlib.

This completes the selected C matrix's local conformance work, not SDK 1.0.
General unreadable-media recovery, broader runtime/application resource and
lifecycle cases, library comparison, exact native dependency sources, clean
supported hosts/native Windows, production GitHub/store and migration work,
measured performance budgets, independent developers and physical qualification
remain. No firmware change/build, connected-device operation, deployment,
commit or push occurred in this batch.

Final public-boundary validation passes for **1,032 files**. **158 relative
SDK/website documentation targets and anchors**, changed-file whitespace,
Python syntax, exported file bytes and checkpoint artifact hashes verify.
Read-only evidence under `build/sdk-c-runtime-profile/evidence` retains
**823 files, 323,956,294 bytes**, including current/earlier library inputs,
source snapshots, completed reports, both bundle artifacts, synthetic outputs,
original failures and the isolated Picolibc build input. Its index SHA-256 is
`264430a17f5b76d35912316eef4f5a0556267c5c4a8c0e3b7778c5db5c2cdbec`.
Every retained file hash and read-only mode verifies; the copied ledger precedes
this annotation. All launched jobs have collected terminal results. The full
SDK goal remains active.

## C library comparison and ordinary stream cleanup — 2026-09-13

The [library decision](NATIVE-APP-C-LIBRARY-COMPARISON.md) now selects newlib
4.6.0.20260123 for `foreground-newlib-1`. It compares the existing callback
subset, the integrated newlib profile and pinned Picolibc 1.8.12 with two
buffering configurations. The callback alternative is an inventory of actual
memory/math/arena helpers and missing libc responsibilities; it has no invented
equivalent-workload timing or footprint. This closes library selection while
preserving the full SDK objective and remaining qualification work.

The shared C fixture adds unclosed buffered streams at main return and nonzero
`exit`, `_Exit` preservation of prior committed bytes, and repeated
`fflush(NULL)` followed by explicit sync. Its buffer has static lifetime so it
survives main return. A new snapshot assertion checks both global flushes before
exit, independently of automatic close. Stream error assertions now distinguish
an EOF return from the missing error indication. The SDK guide explains that
applications must check saves explicitly to report close errors to their users.

### Completed ARM comparison

All final configurations use identical C fixture and harness source, the same
GCC 16.2.0 Cortex-A7 ARM hard-float target, optimized app objects, foreground
heap/linker and real SDK file services. Synthetic storage imports/exports and
normal exit/error checks exercise actual behavior. The expanded newlib run
passes **23 phases**. Each Picolibc configuration passes **15 phases**, fails
**four initial phases** and leaves their **four cold repeats unattempted**.
Both failed processes return exit status 1 and have collected terminal results.
The experiment is complete; Picolibc itself is not qualified by these failures.

Picolibc's `fputc` returns EOF on a read-only stream but does not set the selected
profile's stream error indication. Normal return and `exit(7)` flush without
closing the staged writer, leaving the baseline exported bytes `before` instead
of `after`. Repeated global flushing destructively consumes Picolibc's stream
list; the baseline export contains only `one`, and the final run independently
fails the pre-exit `onetwo` snapshot assertion. `fast-bufio=true` does not change
those outcomes. Pinned source references and integration limits are recorded
in the decision document. No upstream Picolibc source was patched.

The common all-groups fixture with the `memory` argument occupies **113,552
code / 11,796 static-data bytes** with newlib, **59,828 / 9,740** with Picolibc
default buffering, and **60,660 / 9,740** with faster buffering. Initialized
data is 1,744 bytes for newlib and 52 bytes for Picolibc. These are loaded
segments, not raw library archive sizes, minimum-app sizes or hardware timing.
The shared heap is 8,380,416 bytes; reserved stack is 65,536 bytes. Stack peaks
and physical performance remain unmeasured.

Picolibc's isolated compiler reuses the original SDK startup and OS/file adapter
logic, changing syscall symbol names, the reentrant rename hook and the zero
`O_BINARY` spelling. It uses Picolibc headers/types and never links dummy-host or
semihosting archives. Final experiment manifests explicitly name the unsupported
`picolibc-comparison-1` profile; normal SDK selection remains newlib. The initial
baseline retained the common newlib project label while its build/library
reports identified the experimental override. All versions are retained.

The comparison recipe now requires/copies the actual `COPYING.picolibc` file,
rather than silently looking for newlib-style names. Source archive, installed
files, options and notice hashes are checked. Both default/fast candidates were
built from the exact unchanged source archive. Per-file licenses and original
notices remain intact; neither the auxiliary AGPL cross-file generator nor GPL
printf tests are used. The separate desktop dependency-source audit remains open.

### Exact inputs and validation

The three final ARM reports retain SDK identity
`42954442d3457d5183527b94e0f474a41fc08f5f51fc139200b4ec71a7d21342`.
Recording the choice changes only the descriptive `qualification` string in
`sdk/contracts/newlib.json`, producing current SDK identity
`ed6212eaec7c9c4c3fd31faeda4848e48bc8c7b179177e6e115280f33ba4161c`.
Reconstructing the prior inventory from that one string reproduces its exact
old identity. **All 17 current newlib case projects rebuild to byte-identical
ELFs and packages** compared with the tested artifacts. Library sources,
configuration, headers, compiler, application code and firmware are unchanged
by the selection metadata. Tests retain their actual input identities; existing
project locks must explicitly adopt the new SDK identity.

The common API 12 VM ELF remains
`9efe4a74da490bdde5b667c124e3f1e80e3e0f25b38ab8eb0441f91e24629844`;
matching debug ELF is `a396d1c03765a14b1429f78e6e119581dbc89ae4fc8b36b9d70acc9a7ced3e7b`.
Developer QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The common final fixture SHA-256 is
`f2262184d9456bce2be7ae0171cf9af9c8458ba23e0892039e78eacdb3ffb90a`;
harness is `4cb2538f02560b2f315a2adb6611488ecbb81c6e9fd353c8653b2f9d705035ea`.

| Artifact/report under ignored `build/sdk-library-comparison/` | SHA-256 |
| --- | --- |
| `newlib-final/report.json` | `0507c907cbbf68e30bbba2ed40d3c33bfd587da82ac82e1aeb1c048dbf4874ca` |
| `pico-final/report.json` | `abebfb6e103ce692f9811bebf06dd7dd3a65df8432304f14e9a5afcb451a8327` |
| `pico-fast-final/report.json` | `01d16182046cc780c5deb036c20df4cc865979e8895c75c4e847d16b89a72990` |
| `picolibc-v2/candidate.json` | `1e818eaef4f2d276490cfe0ab8f6b37ef30079dd1659a90d23196ef83d023f89` |
| `picolibc-fast-v2/candidate.json` | `d7c637a1f56ea0c91bac2fbbb52dee6e8650e05da1f188b2b57cf0759e528e50` |
| `identity-rebuild/report.json` | `d33ef0f6ee40ea38cfa5a03aebac86907ad0f40fa9e69a0fb32ab1d610a3a6b0` |
| `focused-host.log` | `8fd1413d08b22f8f730d8e76d38b78ab1de0fd85f6320fe113d6b405af010333` |

The focused runtime/C/file-session host suite passes **nine tests** in 23.08
seconds. Initial source builds, failed/passing reports and exported bytes remain
retained, including the first missing-`O_BINARY` build failure. Prior full-host,
frozen-macOS, C++/Doom/minigzip and source-kit results retain their original
separate candidate evidence; they are not relabeled by this comparison.

Storage ownership recovery on unreadable media, broader runtime/application
resource and lifecycle cases, native Windows/clean supported hosts, complete
desktop dependency sources, real GitHub/store operation and production migration,
independent trials, measured budgets and physical qualification remain. No
production runtime or firmware implementation changed in this batch; no physical
device operation, commit, push, deployment or external communication occurred.

The updated deterministic source kit passes its relocated bundled-runtime
journey: **416 files** verify, two archive builds match, external CMake and
ordinary C saved-visit relaunch/cold persistence pass, public input-stream cases
pass, and the existing minigzip recipe builds and exports source with the
bundled library. The kit includes the final comparison document and current
selection metadata; its ledger snapshot precedes this checkpoint annotation.
`source-kit/report.json` hashes to
`573a3865786145c6fb21dc52583d7314e732babb4c61256f3ac949f9606ab650`;
`source-kit/sdk-with-newlib.tar.gz` hashes to
`045d59a89982f71b995473c154895498232b03950d6c2a5c2ee78e27d79adf83`.
These are local source-kit checks using host tools and developer QEMU, not a new
frozen desktop download or clean-host/physical qualification.

Final boundary checks pass for **1,034 public files**, **199 relative
documentation targets/anchors**, changed-file whitespace and four Python
sources. Read-only evidence under `build/sdk-library-comparison/evidence`
retains **1,969 files, 215,499,344 bytes** of library/source inputs, reports,
artifacts, exports and original failure logs. Its index SHA-256 is
`1b17548f86f333f0ec267537574a57d78e876aabeaa18a2ce5c3252040d14075`.
Every retained file hash and read-only mode verifies. The copied ledger and
validation input hashes precede this final annotation. All launched jobs have
collected terminal results. The full SDK goal remains active.

## Canonical archive read errors and initial media workloads — 2026-09-13

Archive inspection now distinguishes a failed canonical-record read from a
readable malformed record. `Source::inspect` preserves negative littlefs read
results as I/O failures, closes the file, and leaves the caller's output
untouched. The session propagates the existing storage-I/O error instead of
reclassifying every failed inspection as integrity failure. Short reads and
invalid contents still fail integrity checks. Package, ABI, wire and storage
formats are unchanged; this does not permit restore without ownership proof.

The production-filesystem session fixture adds **eight unreadable-media cases**:
FILE2 payload loss and FILE3 inline-root metadata loss, each exercised through
ordinary inspection, repair inspection, repair restore and export. Faults begin
after a successful mount. Every operation fails with I/O, releases the session
and makes no flash writes. Removing the fault restores inspection and preserves
both the affected app's canonical record and an unrelated app. The retained
pre-fix regression reports error 9 (integrity) instead of error 10 (I/O).

The focused archive suite passes **133 tests in 39.77 seconds**, including
44 session cases, 28 repair cases, 74 repair interruption cases and the eight
new unreadable-media cases. Command:

```sh
.venv/bin/python -m pytest -q tests/test_app_archive_session.py tests/test_app_archive_restore.py tests/test_sdk_archive.py tests/test_sdk_archive_device.py
```

Logs remain under ignored `build/sdk-media-recovery/`: `archive-before-v2.log`
retains the original defect, and `archive-after.log` records the passing suite.
`make check-public` passes for **1,035 files**. These are host tests compiling the
production storage/archive code; the diagnostic change has not yet been rebuilt
into either firmware target or checked through a live ARM USB archive session.

The new `vm/test-sdk-minigzip-media.py` separately passes its first **10 ARM
phases** for compression with a modeled uncorrectable input read and actual
shared-filesystem exhaustion. Input and previous output remain intact; cold
reopening preserves them, and retries succeed after removing the fault or
releasing filler files. The fixture changes real synthetic littlefs allocation,
not app quotas. Evidence is `build/sdk-media-recovery/initial/report.json`, using
the unchanged API 12 VM ELF
`9efe4a74da490bdde5b667c124e3f1e80e3e0f25b38ab8eb0441f91e24629844`.
Decompression and corrected-read cases in this new harness remain unrun.

Safe recovery when canonical ownership or key-registry records are unreadable,
broader application/resource/lifecycle coverage, complete native host bundles,
exact desktop dependency sources, production GitHub/store migration, independent
trials, measured budgets and physical qualification remain open. No physical
device operation, commit, push or deployment occurred in this checkpoint.

## ARM archive I/O and complete minigzip media matrix — 2026-09-13

The preceding canonical-read diagnostic change now compiles into both physical
and emulator firmware. Builds ran sequentially through the checked build script
with `LEFONY_NATIVE_DIST_NAME=lefony-os-prime-g2-media-io` for `prime_g2` and
`LEFONY_NATIVE_PLATFORM=prime_g2_vm` plus
`LEFONY_NATIVE_DIST_NAME=lefony-os-prime-g2-media-io-vm` for the emulator. Both
processes completed successfully. This is physical-target compilation only;
no calculator was accessed. Existing build warnings remain in the retained logs.

### SDK archive behavior

The new `vm/test-sdk-archive-media.py` passes **three ARM phases**: signed app
installation/backup, transient canonical-header read failure and a cold repeat.
It exercises the real SDK command parser and USB client with only the transport
directed to the emulator. Across warm and cold runs, **eight commands** report
`Archive: storage I/O failed`: ordinary inspection, repair inspection, export
preflight and repair-restore preflight. Failed commands preserve the complete
synthetic overlay, original archive and pre-existing host export destination.
Clearing the model fault restores identical app metadata and byte-identical
export. Export/restore fail during inspection; they do not reach the streamed
engine or receive commit authority.

The read-only fixture locates a real FILE2 canonical page without changing the
overlay. Fault-register writes have checked readback. Host tests from the prior
checkpoint separately exercise the inline FILE3 metadata-pair case. This
validates accurate diagnosis and safe refusal, not reconstruction of lost
ownership. The existing code-repair ARM suite also passes **ten scenarios and
seven additional cold reopens**, including exact signed-code restoration and
continued refusal of a corrupt canonical root. No package, ABI, wire or storage
format changed.

### Minigzip under media faults and shared-volume exhaustion

The full `vm/test-sdk-minigzip-media.py` matrix passes **23 ARM phases**. Each
compression/decompression read-failure and shared-volume-full case has seed,
initial failure, cold failure, retry and cold-output phases. A corrected-read
compression case adds seed, success and cold-output phases. Uncorrectable reads
target a real input chunk; the corrected-read model supplies original decoded
bytes and does not qualify physical BCH correction.

Every failure preserves the input, prior destination, unrelated sentinel and
committed root generation. Retrying the identical package after removing the
fault or releasing fixture filler files succeeds. Subsequent cold runs retain
the completed output and do not change its generation when the consumed input
is absent. Compression output is independently decompressed and compared with
the original bytes; decompression output is compared directly.

The full-volume fixture allocates actual littlefs blocks, including normally
reserved headroom, in disposable storage. Shared available space is zero while
the app uses less than 1 MiB of its 32 MiB quota. It does not change firmware
admission counters, replace the allocator or stub a successful file operation.
The emulator-only constructor gate releases ordinary `main` after model setup.
These results qualify modeled read errors and full-media behavior in this app;
program/erase failure, physical power loss, endurance and timing remain separate.

### Exact candidate and evidence

All new ARM journeys use SDK identity
`ed6212eaec7c9c4c3fd31faeda4848e48bc8c7b179177e6e115280f33ba4161c`
and developer QEMU
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The prior API 12 ELF and initial ten-phase minigzip report retain their own
identities; no old evidence is relabeled. The compiled archive source/session
copies match the checked-in source hashes. Source and SDK identity guards in
the new harnesses pass.

| Artifact or report | SHA-256 |
| --- | --- |
| `dist/lefony-os-prime-g2-media-io.elf` | `fcab9f64fea1e1a39b9a6118ba33c7b45f65f18de8efce7e11d172327cb2b0ee` |
| `dist/lefony-os-prime-g2-media-io-debug.elf` | `bad94f91e3b94e590186c23a3f64b02e6a0c617255b536501bcfdb6b343b9ab4` |
| `dist/lefony-os-prime-g2-media-io-vm.elf` | `6caef5c84255d2f28e29837e865b1d63dc94cb240d8aba977897b13eebd74717` |
| `dist/lefony-os-prime-g2-media-io-vm-debug.elf` | `3741152311f0ed565dbccd4986df358ff2a16010b3552421fdea83d04ad2b22b` |
| `build/sdk-media-recovery/archive-arm/report.json` | `1f8ba69a0ab926d1777daa4d4c82b17997e4d004704a8024cc51317c4e5d1c78` |
| `build/sdk-media-recovery/code-repair-arm/report.json` | `4a991d0826ff24bea6f81098e6bfa337e33f5d2b167eb97c20efbff5da2c94d3` |
| `build/sdk-media-recovery/minigzip-all/report.json` | `46b72aa5b3327a1dec5b29ba570760d4727af71882cbf5688cb72e79f0906ed1` |

The earlier **133-test archive host suite** remains the host regression evidence
for this unchanged production fix. Current guides describe the new media
coverage, and the 1.0 plan now labels its original baseline as historical rather
than presenting implemented features as absent. Safe unreadable-ownership and
key-registry recovery, broader runtime/app failure cases, native bundles and
dependency sources, production store migration, independent trials, performance
budgets and physical qualification remain. All launched validation jobs have
collected successful terminal results. The full SDK goal remains active.

Final checks verify **1,036 public files**, **133 relative documentation targets
and anchors**, changed-file whitespace, both new harness command lines and
Python syntax. The physical/VM ELF and corresponding debug ELF each contain
identical loadable payloads within their target: 2,101,392 physical bytes and
2,101,432 VM bytes. `candidate-verification.json` rechecks report, source, SDK,
firmware and QEMU identities after the runs.

Read-only evidence under `build/sdk-media-recovery/evidence` retains **1,346
indexed files, 165,216,247 bytes**, including all 1,036 current public source
files, firmware/debug artifacts, QEMU, reports, exported data and original
regression failures. Its index SHA-256 is
`378e455590a669576c1e14a496f5fa8b9cf1f2b00283555e4e357a4cfbb5c883`.
Every indexed hash and read-only mode verifies. Existing compiler/newlib inputs
retain their prior library-checkpoint evidence. The copied ledger precedes this
annotation; no frozen desktop download or physical qualification is claimed.


## Unreadable key-registry payload recovery — 2026-09-13

The private-install candidate now includes `keys backup-unreadable` and
`keys repair-unreadable`. The read-only capture exports a bounded `LFKREAD1`
container with readable fragments and explicit missing regions. Repair creates
its own verified host backup, binds its exact SHA-256 and selected public key
to a fresh nonce, and recaptures before consent and after rendered OS approval.
Changed observations or a now-readable registry refuse replacement. Successful
repair installs only the explicitly approved key at serial 1 through the existing
verified pending-file/atomic-rename/readback transaction. It never imports trust
or revocation state from partial fragments. App ownership, version high-water
marks, installed packages and saved data are unchanged.

This is host hello extension 16384, request operations 6/7 and read commands
`0x87`/`0x88`; existing operations retain their meanings. It does not change API
12, ABI 1, the signed package format, registry format 2 or the app volume geometry.
The [developer guide](../sdk/KEYS.md#rebuild-a-registry-with-unreadable-regions)
and [protocol/format description](NATIVE-APP-DEVELOPER-KEYS.md#partial-backup-of-unreadable-payloads)
state the limits. File metadata must remain readable, the source is bounded to
64 KiB and lost bytes cannot be recovered from a partial backup. Unmountable
volumes and unreadable canonical app ownership are separate unfinished work.

### Failed-read cache prerequisite

The regression exposed a littlefs read-cache bug: after a failed backend cache
load, the next short read returned 64 bytes without rereading the failing media.
The failed buffer could be untouched or partially overwritten. The local fix
invalidates that cache on backend failure. The v2.11.3 upstream pin, BSD notices,
filesystem format and NAND adapter remain unchanged; the exact source change is
recorded in [the vendored change note](../ports/lefony-prime-g2/ion/src/prime_g2/littlefs/LEFONY-CHANGES.md).
`cache-before.log` retains the original failure. Eight production-geometry cases
now cover I/O/corruption failures, both failed-buffer behaviors, repeated reads,
unchanged position/output and correct retry after the fault clears.

Integration also fixed the SDK's new repair-hash request binding and distinguishes
an unsupported snapshot from a fully readable registry. A completed partial
capture now reports unreadable status even when the NAND adapter's original
failed read was surfaced as `LFS_ERR_CORRUPT`. The first integrated-status failure
and subsequent passing reports remain retained.

### Host, firmware and ARM evidence

The full `make test` run passes **1,210 tests with two expected private DTB/DTS
skips in 270.45 seconds**. The focused key suite passes **94 tests**. The full
run's littlefs/production-code fixtures include three partial-capture masks with
independent exact-byte comparison, **48 full/torn write interruptions**,
**36 capture/transaction cancellations**, ten size/export boundary cases,
**13 integrated consent cases** and **20 precommit cancellations**. Snapshot
memory is **2,896 bytes on the host**; this is not an ARM stack-peak measurement.
Malformed host framing, old-firmware discovery, failed backup publication,
changed sessions, lost acknowledgements and actual CLI dispatch are covered.

Both target builds completed sequentially:

```sh
LEFONY_NATIVE_DIST_NAME=lefony-os-prime-g2-key-media ./scripts/build_lefony_prime_g2.sh
LEFONY_NATIVE_PLATFORM=prime_g2_vm LEFONY_NATIVE_DIST_NAME=lefony-os-prime-g2-key-media-vm ./scripts/build_lefony_prime_g2.sh
```

The new `vm/test-sdk-key-media.py` passes **seven cases across three ARM phases**.
It enrolls two actual public RSA identities with different active/revoked states,
installs a privately signed Notebook and imports its document. A read-only
synthetic fixture identifies the registry page; QEMU's existing BCH fault
registers make its payload unreadable. The real SDK CLI exports the partial
backup. Every retained fragment matches independently read original bytes.
Back cancellation, a cleared fault and a moved fault during consent preserve
the complete synthetic volume and host backup. Fresh physical OK rebuilds trust
with the selected original key while the old page is still unreadable. Cold
launch and exact document export pass, and an independent fixture confirms the
app package/data root is unchanged. The approval and cold Notebook frames were
visually inspected; both complete hashes and the omitted-bytes warning fit.

Existing regressions pass on this same firmware: **ten key-maintenance cases**
(including retained-key removal and readable-corrupt repair), **three archive
media phases** covering eight command refusals, and the complete **23-phase
minigzip media matrix** for read faults, corrected reads, shared-volume exhaustion,
retry and cold reopening. These use normal public APIs and model input, not
physical hardware. Commands and reports remain under `build/sdk-key-media/`.

The relocated source kit passes external CMake, bundled-newlib main execution,
saved-visit relaunch/cold persistence, input-stream checks and the minigzip
recipe. **417 files** verify and two archive builds are identical. Its extracted
new command/parser sources match this checkout, both command help paths run,
and its parser validates the ARM-exported backup. This is source-kit evidence,
not a new frozen desktop download. The kit's ledger copy precedes this annotation.

### Exact candidate

SDK identity: `f5997d9182a2bd889360dbf62f7102e7197b8a8b8a92c88ebd8aea5d1a3bba23`.
Developer QEMU: `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.

| Artifact or report | SHA-256 |
| --- | --- |
| `dist/lefony-os-prime-g2-key-media.elf` | `d184b8a4283bd84a13de33f961f96a1b784643e43d3ecc78264d879cdd9eca90` |
| `dist/lefony-os-prime-g2-key-media-debug.elf` | `5acd063a43173a13c3bf894e227d8b4a378fbe5762ff8dd2a3ede4bbb294fc96` |
| `dist/lefony-os-prime-g2-key-media-vm.elf` | `3c0002001b34dbe26ff90ac7d796a267bd0ff82e9ae88c914f77ddf2a6a089e1` |
| `dist/lefony-os-prime-g2-key-media-vm-debug.elf` | `c9f986915b4ac77ab28d3445f20ca4a3f88b414c64ad3c9a802e039b40d34ae2` |
| `build/sdk-key-media/arm/report.json` | `88f89ed00ce68968ad842a8ddc8e9cc37bf8159b50533a149b4e06bd9ba41db8` |
| `build/sdk-key-media/maintenance-arm/report.json` | `182fc7d0e5ec26e4246b23cbf3f8a680aefa72078cc3d1ecf7a4bf7fe5127517` |
| `build/sdk-key-media/archive-arm/report.json` | `7068650b79c95b7914ec163cc5e002264e895682632d037629713806dbdd025f` |
| `build/sdk-key-media/minigzip-arm/report.json` | `4a933d3f1e3e9b69823b9e37675032c72d5ab0f19ddc124fdc2911cf3fe8f44e` |
| `build/sdk-key-media/source-kit/report.json` | `aef00fbd8899835fff02d76d2eb13f6a42d3fca9d1cb6f7455188c165c268cdd` |
| `build/sdk-key-media/source-kit/sdk-with-newlib.tar.gz` | `0f30029a4b6e561fa99835683a6b172ce1827d72b5daffd2891f4cecff58a111` |

`candidate-verification.json` checks report/source identities and exact loadable
payload agreement between each ELF, its debug ELF and its BIN: 2,101,392 physical
bytes and 2,101,432 VM bytes. Earlier artifacts keep their original identities;
none are relabeled by the new host extension or cache change.

Remaining full-SDK work includes safe recovery of unreadable app ownership,
broader runtime/application resource and lifecycle coverage, complete native
host bundles and exact dependency sources, production GitHub/store migration,
independent developer trials, performance budgets and physical qualification.
No physical calculator operation, commit, push, deployment or external communication
occurred. The full SDK goal remains active.

Final public-tree checks pass for **1,048 files**, **125 relative documentation
targets/anchors**, changed-file whitespace and both new command help paths.
Read-only evidence under `build/sdk-key-media/evidence` retains **1,404
files, 181,958,529 bytes** of public source, exact artifacts, reports, backups,
frames and original failure logs. Its index SHA-256 is
`bcfed4faa86c09f9f7fffa2f9ae56c13a0d7a1e879520b92ac7be8a74b12c41a`. Every indexed hash and read-only file mode verifies. The
copied ledger and source kit precede this final annotation. All launched jobs
have collected successful terminal results, except the explicitly retained
pre-fix regression failures described above.

## Replicated ownership roots and signed recovery — 2026-09-13

The local [FILE5 candidate](NATIVE-APP-ROOT-RECOVERY.md) preserves the complete
canonical app root in a separate payload block and littlefs metadata attribute.
Each copy binds the app ID, current and retained package/data pairs, serial and
version high-water mark. Configured littlefs attributes commit with file data;
the existing verified pending-file rename publishes both together. Different
valid copies and self-consistent unsupported/wrong-app records fail closed.
One valid copy can recover from damage to the other, without automatic writes.
Package hashes/signatures, signer ownership and downgrade policy remain required.

Document saves, named-file commits and archive restores now write this versioned
352-byte envelope around the existing logical FILE3/FILE4 root. Healthy older
roots migrate on their next successful root commit; there is no bulk startup
rewrite. FILE2 still converts through the existing document/file path. Older
firmware rejects FILE5, so migrated data requires matching firmware. The public
archive format, API 12, ABI 1, file indexes, per-app quota and volume geometry
retain their meanings. One payload block costs 128 KiB per protected root, plus
metadata; admission budgets account for the pending copy too.

Host hello bit 32768 negotiates archive Inspect flag 8. Only those inspections
receive the additional root-protection bits; old SDK requests keep their original
192/256-byte replies and flag set. `archive info` reports `single`, `both`,
`payload-only`, `metadata-only`, or `null` when unavailable. The documented
[repair workflow](../sdk/ARCHIVES.md#root-protection-and-repair) exports a verified
complete archive and explicitly restores it with `--replace`. It rebuilds both
copies through the existing signed transaction, without new enrollment authority.

### Validation and admission correction

The initial integration run had four failing historical fixtures. They now
construct actual legacy roots and explicitly damage both copies when testing
unrecoverable state. Single-copy corruption retains positive recovery coverage;
rejection assertions were not removed. Original output remains in
`build/sdk-root-recovery/integration-first.log` and `initial-prototype/`.

A subsequent production-geometry regression exposed a remaining streaming
admission budget for the old inline root. With exactly three blocks available
above the maintenance reserve, it admitted an empty-file commit without reserving
the additional FILE5 payload. `headroom-before.log` preserves that failure.
The corrected budget rejects before any write at three blocks, succeeds at four,
preserves private bytes, and retains the 24-block maintenance reserve.
`headroom-after.log` also repeats the complete large-file transaction fixture.
The first firmware/report set is retained; the `-v2` target names and report
folders below identify the corrected candidate.

- **1,222 host tests pass**, with two expected private DTB/DTS fixture skips,
  in 284.49 seconds (`full-host-v2.log`). This includes the two real-space
  admission boundaries, 26 root-envelope full/torn write interruption cases,
  11 root-copy media/conflict cases, 10 signed integrated root-recovery cases,
  and 30 integrated integrity/ownership/version refusals. The archive-session
  fixture also retains 82 code-repair interruption cases and eight unreadable
  legacy-root refusals. Sanitizer-backed storage/document/file tests remain in
  the full suite. Object sizes are host sizes, not ARM stack peaks.
- **Six corrected-candidate ARM cases pass** (`arm-v2/report.json`). Public
  installation, Notebook acceptance, rollback and archive restore establish a
  pending version-2/version-1 pair with a version-3 high-water mark. A read-only
  fixture locates the payload; existing QEMU BCH controls make it unreadable.
  The real SDK CLI reports metadata-only protection and exports bytes identical
  to the original signed whole-app backup. Public installation rejects version
  2.5, cancellation preserves the original generation, and explicit restore
  rebuilds both copies while the original page remains unreadable. Cold export
  preserves both pairs; Notebook then opens the original document and accepts
  the pending upgrade while retaining version-3 history. The cold frame was
  visually inspected: both expressions, results and normal controls remain.
- **Eight corrected-candidate archive ARM journeys pass**
  (`archives-arm-v2/report.json`): initial/cold export/restore, pending/cold-pending
  pairs, rollback, fresh restore and damaged-index/private-data repair.
- The older FILE2 reader rejects a genuine FILE5 payload/attribute fixture
  without formatting or writes. This is a specific retained-source check, not
  qualification of every old firmware release.

Both corrected target builds completed sequentially:

```sh
LEFONY_NATIVE_DIST_NAME=lefony-os-prime-g2-root-recovery-v2 ./scripts/build_lefony_prime_g2.sh
LEFONY_NATIVE_PLATFORM=prime_g2_vm LEFONY_NATIVE_DIST_NAME=lefony-os-prime-g2-root-recovery-v2-vm ./scripts/build_lefony_prime_g2.sh
make test
.venv/bin/python vm/test-sdk-root-recovery.py --firmware dist/lefony-os-prime-g2-root-recovery-v2-vm.elf --output build/sdk-root-recovery/arm-v2
.venv/bin/python vm/test-sdk-archives.py --firmware dist/lefony-os-prime-g2-root-recovery-v2-vm.elf --output build/sdk-root-recovery/archives-arm-v2
```

### Exact candidate

| Artifact | SHA-256 |
| --- | --- |
| `dist/lefony-os-prime-g2-root-recovery-v2.elf` | `09e96c24ad5418fb1d258a4330d63d2e98bc8bac2aee6cc065eddcce77881538` |
| `dist/lefony-os-prime-g2-root-recovery-v2-debug.elf` | `754b31cf2c0ad20a5e992eb00f08b281b375c67dd166ed793e5a4bc295b38310` |
| `dist/lefony-os-prime-g2-root-recovery-v2.bin` | `1d5707d098c5b3ccd245dbd710fe314d1bfe3e17f0de985352f4538c9ff6bb78` |
| `dist/lefony-os-prime-g2-root-recovery-v2-vm.elf` | `778252b471e84b36194d3885e741a11a12272c10619ab98a7a234e8a93633796` |
| `dist/lefony-os-prime-g2-root-recovery-v2-vm-debug.elf` | `2a1470f14e3f583c80095594048f07535e7c8c280471e454a98e90c15f55237e` |
| `dist/lefony-os-prime-g2-root-recovery-v2-vm.bin` | `bdad7b32db9d54b4bfdb13fce4ae1573051cdcbd960aa4e77fc7aed2d7a19782` |
| `build/sdk-root-recovery/arm-v2/report.json` | `cffd449682ab905d5db790c0c54101f0dae6a02f204641b3412240c8e6840662` |
| `build/sdk-root-recovery/archives-arm-v2/report.json` | `8ddf7b9b3a4159b576a432e9cb076507c68fc70b0293b5d562efbe1e332bf886` |

The SDK identity is
`9639f17c29ccdf3f56136aaa5da4ab15815b698ed3f21597cb64e242d88e794b`;
QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
Earlier root-recovery artifacts and their passing reports retain their original
identities. `pre-headroom-fix/` retains the changed source and failing regression
inputs. The full-library/newlib checkpoint and prior key-registry evidence remain
separate. No physical device operation, publication or SDK 1.0 qualification is
claimed.

FILE5 cannot recover already-lost legacy sole roots, two lost/conflicting copies,
unreadable filesystem metadata or an unmountable volume. Those cases stay
occupied and refuse guessed ownership. Complete native bundles, wider resource
and performance budgets, independent trials, store production acceptance and
physical qualification remain separate SDK work. The full goal stays active.

The corrected candidate also passes all **23 minigzip ARM media phases**
(`minigzip-arm-v2/report.json`): compression/decompression under modeled read
errors, corrected reads, actual shared-volume exhaustion, preserved input/output,
retry and cold reopening. This rerun includes the corrected streaming admission
budget. Its report SHA-256 is
`9123c3dc1abff21433167ef02cbbc488492d72972cd620408bf7a4bc14c707f8`.

The final relocated source kit contains **418 checksummed files**, including the
new recovery guide and byte-identical SDK command modules used in the ARM proof.
Two independently generated archives match. External CMake, bundled newlib,
ordinary-main preview, cold saved visits, input reset and the existing minigzip
recipe pass. `source-kit/report.json` hashes to
`1f32abbc1d9a2c4784d81ed2c71fcedfef99967aa4acc6b2a8e384942955f864`;
`source-kit/sdk-with-newlib.tar.gz` hashes to
`e27ad85a64e79a77d0cb5bc180578e48739aa70b5f3c22554ece3358c16cdf3b`.
`source-kit-content.json` verifies the complete checksum manifest, exact command
sources and presence of the format guide. This remains a source kit using local
host tools, not a complete native desktop download. Its copied ledger precedes
this final annotation.

```sh
.venv/bin/python vm/test-sdk-minigzip-media.py --firmware dist/lefony-os-prime-g2-root-recovery-v2-vm.elf --output build/sdk-root-recovery/minigzip-arm-v2
.venv/bin/python vm/test-sdk-main-kit.py --firmware dist/lefony-os-prime-g2-root-recovery-v2-vm.elf --output build/sdk-root-recovery/source-kit
make check-public
```

The physical and VM ELF/debug pairs contain identical loadable payloads within
each target, matching their BIN artifacts: 2,101,392 and 2,101,432 bytes,
respectively. `candidate-verification.json` rechecks these identities, the final
SDK/QEMU/report hashes and the source map. All 11 recorded production source
files also match the generated build checkout. The final Notebook seed/cold
frames are byte-identical and the cold frame was visually reviewed. The public
boundary, changed-file whitespace, command help and 90 relative documentation
targets/anchors pass. No complete SDK 1.0 milestone or physical acceptance is
claimed by this checkpoint.

Read-only evidence under `build/sdk-root-recovery/evidence` retains **1,623 indexed files, 328,738,630 bytes**, including source, both candidate generations, complete reports, original failures, source kits and synthetic captures. Every indexed hash and read-only mode verifies. Its index SHA-256 is `99fd1fcfd51b3dba76660f5decc17ad91eef8a36bbbef32a82a26fda8d404021`. The copied ledger and documentation-check hashes precede the final annotations; no frozen evidence was modified.

## Package-bound ARM resource observations — 2026-09-13

The SDK now accepts `test --measure-resources` and `run --measure-resources`.
The matching VM paints unused stack memory only for validated loads of the exact
inner LFAPP0 package requested by the host. It samples the banked user SP at
SVC, IRQ and fault boundaries, and scans changed stack bytes at explicit snapshots
and before unmapping. Default and physical execution retain their existing
initial stack contents. The instrumentation and UART commands are compiled out
of the physical target; no app ABI, API capability, package schema, firmware
trust root or storage layout changed.

The host negotiates a separate private VM profile version before load. Unknown
firmware, malformed snapshots, wrong package identity and unobserved execution
are errors, never zero-valued success reports. Matching relaunches aggregate;
other packages and rejected loads do not contribute. Completed unloads and fault
PC/reason/event survive later loads. A recorded failure cannot become a passing
measured run when a later app clears the original per-callback diagnostics.

See [the measurement contract](../sdk/TESTING.md#observing-app-resources).
The deepest changed byte and sampled SP are observations, not a proved maximum
stack requirement. Untouched reservations between samples or bytes matching the
paint may be missed. The report retains null worst-case stack and heap peaks;
heap reservation is not allocation consumption. The 90% observation advisory is
not a ratified performance budget. Profiling overhead and Doom's read-only GDB
pauses exclude these runs from timing qualification.

### Actual ARM workloads

| Workload | Passing journeys | Largest observed stack extent |
| --- | --- | --- |
| Notebook debug/release: editing, saved/cold documents, malformed data, validation, settings and clipboard | 24 | 12,976 bytes |
| Minigzip: large compression, cold decompression/update, host gzip, missing/path errors, corrupt/truncated preservation and same-package retries | 9 | 18,368 bytes |
| Link Gallery debug/release: connect/download/cache, reconnect, cancellation, invalid image and cold cache | 4 | 3,132 bytes |
| Doom: normal-input gameplay, save/reload, successful quit and cold saved-state restoration | 2 | 1,568 bytes |

All use the separate 65,536-byte stack. Doom's existing allocator observation
reports a newlib peak `sbrk` arena of 6,643,712 bytes, including allocator-managed
space; it is not peak live requested payload. The current Doom recipe was
rebuilt against its pinned upstream inputs and scoped MIT runtime alternative.
Its prior synthetic WAD/save workspace was cloned, then updated to the local
0.1.2 package. The original workspace was preserved. Both saved-state exports
match at 61,342 bytes. No physical device was accessed.

The diagnostic harness passes **ten cases**: an 8 KiB written frame, a 32 KiB
untouched reservation, a guard fault, uninstrumented zero initialization, a
48 KiB stack reservation in a CPU loop interrupted by the normal IRQ deadline,
ordinary main/exit/relaunch, other-package exclusion, a fault followed by a
successful different app, rejected-load/rearm boundaries, and explicit refusal
by the retained older root-recovery firmware. The old-firmware case deliberately
logs the rejected VM session; it is a passing negative case.

### Validation and retained artifacts

- Both target builds pass. The first VM compile rejected an unavailable
  `UINT32_MAX` macro in the freestanding headers; the corrected source uses its
  explicit 32-bit bound. Existing upstream linker/assembler warnings remain.
- Full host suite: **1,246 passed, two expected private DTB/DTS skips**, 281.91 s.
  The 24 focused snapshot tests cover attribution, unknown versions, corruption,
  absent observations, bounds, fault retention and saturation reporting.
- The **419-file** deterministic source kit passes external CMake, bundled
  newlib, normal/cold visits, input reset and the existing minigzip recipe. Its
  relocated CLI executes the new measurement option on a conventional-main
  startup (672 observed stack bytes). Ordinary uninstrumented runs remain part
  of that journey. This is source-kit evidence, not a native desktop release.
- Notebook's **34 debug/release frame pairs** match exactly. Link Gallery's
  visual comparisons pass with its documented transfer-progress-bar exclusion.
  Notebook options and the saved gallery frame were also visually reviewed.
- `candidate-verification.json` checks current SDK/QEMU/source identities,
  recorded report hashes, each workload's retained LFAPP0 bytes and exact
  signed package identity, and equal ELF/debug/BIN loadable payloads. The three
  changed native files also match the generated build checkout. An initial
  audit tried to sign an already-signed retained package; the corrected audit
  preserves its envelope and separately checks its inner identity.

Commands (all output is retained beneath ignored `build/sdk-resource-profile/`):

```sh
LEFONY_NATIVE_PLATFORM=prime_g2_vm LEFONY_NATIVE_DIST_NAME=lefony-os-prime-g2-resource-profile-vm ./scripts/build_lefony_prime_g2.sh
LEFONY_NATIVE_PLATFORM=prime_g2 LEFONY_NATIVE_DIST_NAME=lefony-os-prime-g2-resource-profile ./scripts/build_lefony_prime_g2.sh
.venv/bin/python -m pytest tests
.venv/bin/python vm/test-sdk-resource-profile.py --firmware dist/lefony-os-prime-g2-resource-profile-vm.elf --old-firmware dist/lefony-os-prime-g2-root-recovery-v2-vm.elf --output build/sdk-resource-profile/arm-final
.venv/bin/python vm/test-sdk-notebook.py --firmware dist/lefony-os-prime-g2-resource-profile-vm.elf --measure-resources --output build/sdk-resource-profile/notebook
.venv/bin/python vm/test-sdk-minigzip.py --firmware dist/lefony-os-prime-g2-resource-profile-vm.elf --measure-resources --output build/sdk-resource-profile/minigzip
.venv/bin/python vm/test-sdk-link-gallery.py --firmware dist/lefony-os-prime-g2-resource-profile-vm.elf --measure-resources --output build/sdk-resource-profile/link-gallery
.venv/bin/python vm/test-sdk-doom-gameplay.py --project build/sdk-resource-profile/doom-project --workspace game --firmware dist/lefony-os-prime-g2-resource-profile-vm.elf --measure-resources --output build/sdk-resource-profile/doom
.venv/bin/python vm/test-sdk-main-kit.py --firmware dist/lefony-os-prime-g2-resource-profile-vm.elf --measure-resources --output build/sdk-resource-profile/source-kit
make check-public
```

### Exact candidate

| Artifact/report | SHA-256 |
| --- | --- |
| `dist/lefony-os-prime-g2-resource-profile.elf` | `03dbe042223e8494846f41edf47bf9c33881187fafd9126f73f5dd558ed42aee` |
| `dist/lefony-os-prime-g2-resource-profile-debug.elf` | `34d8c53466c382cb8bccc3de1c2ed14729c3688e63b76117cdc75bed17064b3b` |
| `dist/lefony-os-prime-g2-resource-profile.bin` | `fcbc44c3ca9ae016aabdb6125a8840554a101bc8f08f233ef5d45852b9184f91` |
| `dist/lefony-os-prime-g2-resource-profile-vm.elf` | `1d95edfd9b3be0b292c06752088fef51c0c35c347957e63941f9b1fbbe17a20b` |
| `dist/lefony-os-prime-g2-resource-profile-vm-debug.elf` | `7ac46739c81649c50b7ca52a5191d068219ce503db7a7eb0a905529f96105b26` |
| `dist/lefony-os-prime-g2-resource-profile-vm.bin` | `30a1deb35dfc5f82fee94767ff7370cb51f27b63276460eb0be1cb578753fea9` |
| `build/sdk-resource-profile/arm-final/report.json` | `87a6e77a99c9b77accf0f21933af71649f6636f460ccd652909be21508f89b02` |
| `build/sdk-resource-profile/notebook/report.json` | `5d58bb23e75daf739de0b29824094d678261fec4e583012e0a0e32e3cc141493` |
| `build/sdk-resource-profile/minigzip/report.json` | `bd7d26d09a5b0151f28e836e7e3be2dae87c343641c37f956a869854c30c7996` |
| `build/sdk-resource-profile/link-gallery/report.json` | `36b5a58e3731750e3ab5336437e9197af6ae9caf8942102fb29c31ba28436892` |
| `build/sdk-resource-profile/doom/report.json` | `c5cd1e64e3f4707f9145d628345727ae311bef06146b40030ceb4461efd5a300` |
| `build/sdk-resource-profile/source-kit/report.json` | `727a8825574fe0bc7fd5dfc7c51c540a9a4e43f9de7292367f3f5577abf6241a` |

SDK identity: `5403d7723219eca484e1841491014488e971df03ff54fc5952c1ac0cb3e84ebe`. QEMU identity:
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`. The source-kit archive hashes to
`9057d5f89f01236143437b2264e670f282c2eaa2cef15b35dd7a6e79c5d2c668`.
The copied ledger predates this final qualification annotation; the tested SDK
code and measurement guide retain their recorded identities. Earlier candidates
and failures remain separate and are not relabeled by this checkpoint.

General live-heap telemetry, broader application exhaustion/lifecycle/security
coverage, supported-host latency and physical budgets remain unfinished. Native
Windows tooling, clean supported-host bundles, exact native dependency sources,
real GitHub/store migration and deployment acceptance, independent developer
trials and physical storage/input/USB/power qualification remain SDK work. No
complete SDK 1.0 milestone is claimed. No commit, push, deployment or external
communication occurred; the full goal remains active.

Read-only evidence under `build/sdk-resource-profile/evidence` retains **3,780 indexed files, 317,516,737 bytes**, including the public source snapshot, both exact targets, QEMU, packages, synthetic workspaces, reports and original failures. Every indexed hash and read-only mode verifies; index SHA-256 is `0c9cea0522bfd93fba0e8d35461bcdef837f441506d2dba407e7bb78a35123c8`. The frozen ledger and documentation-check report precede this final annotation. Final public boundary, whitespace and 112 relative documentation targets/anchors pass.

## Doom configuration, quota failures and resource errors — 2026-09-13

The [Doom recipe](../sdk/ports/doom/README.md) now enables the upstream portable
configuration reader and writer. Both had been disabled by `ORIGCODE`; earlier
clean-quit evidence therefore did not establish settings persistence. The
baseline reproduces that gap by importing sensitivity 7 and observing the
default 5 on both launches. The recipe also corrects configuration filename
joining, retaining existing `.savegame/` paths. Default configuration inputs are
`default.cfg` and `doomgenericdoom.cfg`, with a 64 KiB bound per file. Only an
absent file selects first-run defaults; other read/close errors are visible.

The new GPL-2.0-or-later `output.c`/`output.h` adapter uses the existing public
API 12 writer-abort contract. Game saves stage direct replacements, crediting
the old length against logical quota. Processing failures discard the writer;
a final commit error is explicitly unconfirmed. Failed ordinary saves leave
gameplay available for retry. Configuration writes use the same checked
transaction, and failed configuration saves stop with a visible error. The two
configuration files are separate transactions, not an atomic pair. OS-owned
Home can force exit without running the engine's settings writer.

The recipe checks exit-handler, configuration-directory/string and save-path
allocations, and retains the existing checked screen allocation. Its manifest
is now app version 0.2.0, minimum API 12 and capability mask 8252. Existing 0.1.x
packages are unchanged. The output adapter is included in the standalone source
kit; it does not extend the approved MIT grant or change firmware licensing.

### Functional candidate and failures retained

The first completed candidate has ELF SHA-256
`6a8856d622b74974c71a59755cb833dafd05ecc9d205c276ab3b9689cda002b5`,
debug ELF `799ec4cf0bb9dea2804d43d908f6a5d78445f8780f14596bfa33d59ee6a3e747`,
inner LFAPP0 `e851a48a2b3e1c53b6e7b9f1e3b1f099275fc0fb3bab9711e7fb79e086f5f681`
and emulator-signed package
`5a36b938f2e2244fd10e3df741bfd0e5cec5b572aac94cf15766abbd11dfb598`.
It has 333,686 code bytes, 430,916 static-data bytes, the existing 64 KiB stack
and 8,380,416-byte heap reservation. The functional recipe and its two explicit
allocation fixtures pass **19 ARM journeys**:

- Two full-quota/cold-load cases replace the existing 61,342-byte save at exactly
  32 MiB of logical usage. The older package instead exits with an error while
  retaining the old save. These two completed cases are retained in
  `current-v4/report.json`; its subsequent settings harness failure is not a pass.
- Six settings cases in `current-v5/report.json` change sensitivity 7 to 8 and
  screen size 10 to 9, save through ordinary Quit and reopen cold. At full quota,
  growing the serialized screen value back to 10 fails; the old configuration
  survives byte-for-byte and cold startup restores 9. Freeing space allows the
  same package to retry and cold startup then restores 10.
- Six error cases in `errors/report.json` give a new save slot only 4 KiB of
  quota, observe the error and responsive menu, and verify unchanged generation,
  original save/configuration bytes and no partial slot. Cold loading the original
  save works. After freeing space, retry writes the complete second slot and
  cold load succeeds. A 65,537-byte configuration is rejected visibly without
  changing either save; public restoration of the valid configuration restores
  normal startup.
- Three startup cases in `resources/report.json` reject missing WAD data, a
  real failed 9 MiB zone request and a real failed screen allocation. The latter
  uses an ordinary constructor to allocate 8,250,000 bytes through newlib;
  it does not replace `malloc` or use a private firmware allocation service.
  Each exits with -1, produces the expected reviewed error frame and leaves
  the OS responsive without a runtime fault.
- Two gameplay/cold cases in `gameplay/report.json` retain normal movement,
  held turn/fire, menus, save/reload, saved position/ammunition and clean Quit.
  Both save exports match at 61,342 bytes. The observed newlib arena extent
  remains 6,643,712 bytes; observed stack extent is 2,064 bytes in these runs.
  These are observations, not live heap peaks, worst-case stack or timing budgets.

All reports are under ignored `build/sdk-doom-storage/`. The baseline and failed
attempts are preserved. Initial preparation used a nonexistent include hook and
was corrected before creating a project. The first public import correctly
refused a pending package upgrade. Enabling actual configuration commits exposed
a 20-second test deadline and then the missing filename separator. The corrected
maintainer quit wait is bounded at 180 seconds; it does not change firmware or
USB deadlines. Finally, the settings harness sent Escape twice, reopening the
menu and preventing F10 Quit. It now sends one Escape and observes menu closure.
None of those failed attempts is relabeled as successful qualification.

Visual review also found the initial save warning clipped at the display edge.
The final recipe shortens only that string to
`SAVE UNCONFIRMED: LOAD TO CHECK`. The complete **six-case ARM error repeat
passes** in `concise-errors/`, and the reviewed warning now fits the status line.
Its exact ELF is `562a8b60758e5da1a63d78ee26f7d6137c5b72d1fc94c7c01b55a4eca2210f88`,
debug ELF `f49c8abd5827d511a92f47d2dedbc365d40db6f9c93a4eadd499426aeaa682ab`,
inner LFAPP0 `35334ebafe24a9b170bfa0372f4f2f8f59c7b0dac7b928d414d0a426509c034f`
and emulator-signed package
`dd4ab5f723072de153f67c8ddc71d64250e3bfc267a7970c3c0e3af4ffaa9f96`.
Code size is 333,662 bytes; static data and reservations are unchanged.

Three host tests pass in **49.41 seconds** (`host-doom-kit.log`): deterministic
preparation and a real ARM source-format-2 round trip/rebuild, changed-pin refusal
before project creation, and relocated source-kit preparation plus compilation
using its bundled newlib. That portable package matches the checkout build
byte-for-byte. The SDK/newlib source kit remains distinct from a complete native
desktop release or a clean-host qualification.

`candidate-verification.json` binds all **25 successful current ARM cases** and
the two baseline cases to retained reports and package bytes, checks firmware
and SDK identity, and verifies the one-literal difference between the functional
and final warning candidates. It does not qualify the failed settings attempt
inside `current-v4`, or relabel allocation fixtures as the ordinary package.

| Report under `build/sdk-doom-storage/` | SHA-256 |
| --- | --- |
| `current-v4/report.json` (two completed cases only) | `905ef8d3ab0054a969519f72902d6a7887852033bbf0b6b9809916570a8e4e52` |
| `current-v5/report.json` | `514ee455d9b04cc3bdc84a75ad53b37de83a5e92b27123cb48e2476312c15541` |
| `errors/report.json` | `2dcf496b5b3080a7a090fbea1b12dcd9ddbe7f6ced1d36faedd80b03e397e0ea` |
| `resources/report.json` | `6a7f7644d263bb1df678852a274c2b9673fcb1d73b43bdb6a8ec15a20bf7bea1` |
| `gameplay/report.json` | `e60755f817565688519f32f7e35ae56048d94b02664b78c707b772b2a2d716c5` |
| `concise-errors/report.json` | `2e1f4c4ac99cf74d2c4428025b69095e6461037549b10e4b0172543bc2c2484b` |

The final error repeat used the command below. Its workspace is a clone of the
earlier accepted WAD/save fixture; the harness completes the actual package
upgrade before public imports. Each repetition needs a fresh output directory.

```sh
.venv/bin/python vm/test-sdk-doom-errors.py --project build/sdk-doom-storage/concise-project --seed-project build/sdk-resource-profile/doom-project --output build/sdk-doom-storage/concise-errors --firmware dist/lefony-os-prime-g2-resource-profile-vm.elf
.venv/bin/python -m pytest tests/test_sdk_doom.py -q
make check-public
```

No firmware source changed in this checkpoint. The runs use the previous
resource-profile VM ELF
`1d95edfd9b3be0b292c06752088fef51c0c35c347957e63941f9b1fbbe17a20b`
and SDK identity
`5403d7723219eca484e1841491014488e971df03ff54fc5952c1ac0cb3e84ebe`.
The final recipe retains all 195 prepared engine/adapter source files; compared
with the functional candidate, only the save-warning literal differs.

Interrupted saves/upgrades through Doom, wider control/resource/lifecycle
coverage, general live-heap telemetry and timing budgets remain open, as do
native-host, production-store, independent-developer and physical SDK 1.0
qualification. No hardware operation, commit, push, deployment or external
communication occurred. The full SDK goal remains active.

The final 421-file source kit with newlib hashes to
`fecefdf3380d3882b717ed58722db80878c10d9cb0b31417d18c8d168ef2ec46`.
Every bundled checksum verifies, including both output-adapter files and the
current preparation script. The final public boundary check passes for 1,067
source files; whitespace and 101 relative documentation targets/anchors pass.
One exact upstream match required an escaped trailing space in the preparation
script; regeneration confirms that this formatting correction preserves every
prepared project byte. The kit's ledger precedes this final archive annotation.

Read-only evidence under `build/sdk-doom-storage/evidence` retains **11,700
indexed files, 812,964,281 bytes**, including the source snapshot, exact firmware
and QEMU artifacts, prepared projects, packages, synthetic workspaces, reports
and failed attempts. All indexed hashes and read-only modes verify; index
SHA-256 is `d0f62c324b3d47cb2e40cda98d7be32dbcf9b48d91b6647ef12a046da070531e`.
The frozen ledger precedes this final evidence annotation.

## Doom Home-interruption checks and pending position comparison — 2026-09-13

The new `vm/test-sdk-doom-interruption.py` exercises normal Home input after
an observed staged save prefix and during pre-commit reference verification.
Matching firmware symbols supply read-only observations. The prefix case uses
a temporary hardware breakpoint, queues normal KPP Home input and resumes;
it does not call game/storage functions or mutate guest variables. The observed
prefix is 27,648 bytes, and the verification case observes 61,342 staged bytes
with reference cursor 96,256. These are modeled logical stages, not physical
NAND programming or input-latency measurements.

All six cases in `build/sdk-doom-interruption/current-v2/report.json` pass:
the two Home interruptions, their cold restarts, a successful retry and its
cold load. Public exports confirm unchanged prior save/configuration bytes and
generation for the interruption/cold pairs. Every case leaves the OS responsive,
with no runtime fault and an observed stack extent of 2,064 bytes. The report
SHA-256 is `041c34ef6e6b6053f879eda6b3b8cc11fe8da6bc43d76eddc5420fda508f8ce7`.
The tested helper and harness are retained beside that report.

The subsequent `position-retry` run adds player movement before saving. Its
retry succeeds, but its cold-load coordinate assertion fails; the process exits
1. The saved-completion observation is (-11073861, 16782944), while the later
loaded observation is (-11350756, 16782889). These observations occur at different
game ticks, so the failure alone does not establish a serialization defect.
The comparison requires investigation and is not accepted as position-restoration
evidence. Its partial report retains only the completed retry and still says
`running` because the harness did not finalize on the assertion. The terminal
failure is recorded in `build/sdk-doom-interruption/position-retry.log`; partial
report SHA-256 is `76de6a13c2e2f9e788bb1827da682fb0be3e32c1ee18e19515ff2d8e884facd8`.

Earlier failed attempts remain in `initial/` and `current/`: one needed explicit
C++ language selection for firmware symbols; polling in the other missed the
short prefix stage. Neither is counted as a passing interruption check.

These runs retain the previous final Doom package
`dd4ab5f723072de153f67c8ddc71d64250e3bfc267a7970c3c0e3af4ffaa9f96`
and resource-profile VM ELF
`1d95edfd9b3be0b292c06752088fef51c0c35c347957e63941f9b1fbbe17a20b`.
The matching debug ELF has identical load segments. No production app or firmware
code changes in this checkpoint. Abrupt resets, interrupted upgrades, wider
controls/resources, supported hosts and physical qualification remain open.

## Doom serialization observations, recursive errors and saved controls — 2026-09-13

The prior cold-load coordinate assertion was an observation error. The exported
save stores X = -11399501 and horizontal momentum = 48745. Its observed cold
X = -11350756 is exactly one movement tick later; the saved Y and Y momentum
likewise explain the observed Y. The old save-completion observation
occurred several ticks later. Its failure remains retained in `position-retry/`.

`vm/test-sdk-doom-interruption.py` now uses temporary hardware breakpoints at
`P_WriteSaveGameEOF` and `P_ReadSaveGameEOF`, after serialization and restoration
but before gameplay resumes. Normal KPP input still selects and confirms the
save/load operations; debugger commands only read state and resume execution.
It compares twelve fields, including position, momentum, angle, health, ammo,
level time, episode and map. It also checks that the loaded game resumes and
that public exports remain intact. Failed runs now finalize their report as
failed instead of leaving a misleading running status. Both app and firmware
debug images must have identical load segments to their executable counterparts.

Two moving save/cold-load cases pass in
`build/sdk-doom-interruption/position-boundaries/`, with all twelve fields equal.
The four Home-stage/cold-load regressions pass in `home-boundaries/`. These six
checks retain the previous final 0.2.0 package, signed SHA-256
`dd4ab5f723072de153f67c8ddc71d64250e3bfc267a7970c3c0e3af4ffaa9f96`.
Report hashes are `191f93f9fc70fe1821f048d402da8f4fa54de5ba82ddd60ed2b7dc175f92e9e7`
and `ae4e3b017cb4458206ba2f526c90b1a084fb3dcbbb67ad8173608f2e30633427`, respectively.
The reviewed cold frame shows the restored game. These are model observations,
not physical input timing, NAND programming or abrupt-reset evidence.

### Production fixes in recipe 0.2.1

A separate real engine-exit callback fixture reproduces a recursive-error defect:
missing WAD data invokes `I_Error`; the callback raises another error, and the
disabled recursion guard allows repeated cleanup until an app fault (-14).
The failed baseline and its source remain in `build/sdk-doom-cleanup/baseline/`.
The checked preparation transformation restores the upstream guard outside
`ORIGCODE`. A nested error exits with -1, retaining the first displayed message
and running the registered C output-discard handler. It does not weaken runtime
fault containment or invoke firmware shortcuts.

The first normal-gameplay regression then exposed another existing defect:
configuration writes virtual Fire/Use/strafe keys as values 160–163, while the
upstream loader only translates DOS scan codes below 128 and replaces the rest
with zero. That run turned correctly but retained all 50 bullets while Fire was
held. Its failed evidence remains in `build/sdk-doom-cleanup/gameplay/`.
The recipe now preserves exactly those four Doomgeneric virtual values while
retaining the existing DOS mapping and treatment of other out-of-range values.
Existing files containing the original values load without conversion. The
gameplay test observes all four bindings and adds actual firing after cold load.

Only prepared `i_system.c` and `m_config.c` differ from the preceding engine
candidate. The manifest advances to 0.2.1; API 12, capability mask 8252, firmware,
SDK runtime and licensing boundaries are unchanged. The source-kit host test
now obtains the package filename from the generated manifest.

The final five-case ARM resource run passes missing-WAD, zone exhaustion,
screen exhaustion, recursive cleanup and recursive cleanup with 4 KiB of staged
output. The extra failure callbacks and allocation constructors are explicit
fixture variants, not the ordinary package. Each observes exit -1 before Home,
leaves the OS responsive without a runtime fault and reports an empty file list;
the staged `cleanup.tmp` is absent. Both recursive-error screenshots exactly
match the original missing-WAD error frame. The guard-only intermediate run is
retained separately from the final run with both fixes.

Three final host tests pass in 51.59 seconds: deterministic preparation and ARM
source round-trip/rebuild, changed-pin refusal, and a relocated source-kit build
using its bundled newlib that matches the checkout. Evidence is under ignored
`build/sdk-doom-cleanup/`; these checks do not qualify complete desktop bundles.

The first final-candidate cold-firing attempt also revealed an early load-ready
predicate: `G_DoLoadGame` clears `gameaction` before deserialization, so matching
player fields can appear while loading is still in progress. The harness now
requires the restored level clock to advance past the post-save observation and
holds Fire until it observes a shot, with a bounded deadline and guaranteed key
release. That failed attempt is retained in `final-gameplay/` with its harness.

Both corrected gameplay/cold cases pass in `final-gameplay-v2/`: movement,
turn/fire, menus, save/reload, restored position/angle/ammunition, all four saved
virtual bindings, actual cold firing and ordinary Quit. The cold shot reduces
ammo from 47 to 46. The two exported saves remain byte-identical at 61,342 bytes,
and both runs exit 0 with no runtime fault and a responsive OS. The reviewed cold
frame shows the game after firing. These two cases and the five final resource
cases use the final 0.2.1 recipe; the six corrected interruption cases above
remain explicitly bound to their earlier 0.2.0 package.

| Final artifact/report | SHA-256 |
| --- | --- |
| Ordinary 0.2.1 ELF | `a0dd373610b9432563ca6f8913a70d8323d0d2419d12e48bd9f4c0e6819339bb` |
| Matching debug ELF | `c0513f7d103c7699656cff0e2020c2d1b622b0e0197f29cf76a38ee1c5b2d11f` |
| Raw package | `b833ffe0a01dbe6c538d8f8e265b2246e4d850392fa44082de2060268ba82f78` |
| Emulator-signed ordinary package | `2f76a16205d674561fd060696198dbe2e173db22c1041e6c08994022fb88319f` |
| `final-resources/report.json` | `45904a483b234a0cc65b1fdc5acaf1acea4221fdf39e91a131ab83724f0663f1` |
| `final-gameplay-v2/report.json` | `665f33f44b2328014560b402026acbeeb88402e6f5b09c7079fb9de6561dc301` |

`candidate-verification.json` binds all thirteen completed cases to their exact
reports, sources, package bytes and unchanged resource-profile VM firmware. It
also checks the serialized momentum explanation and retains the recursive-error
baseline as a failure. The source kit with bundled newlib contains 421 verified
files and hashes to `245045f6358a11c7caf98ae1b37801ceb534b68aa0766e7257e1749f3e2820ed`.
Its ledger predates this final validation annotation. Public-boundary, syntax,
whitespace and 96 relative documentation-target/anchor checks pass.

Reproduction uses fresh output directories and retained synthetic workspaces:

```sh
.venv/bin/python vm/test-sdk-doom-interruption.py --seed-project build/sdk-doom-interruption/current-v2/project --output build/sdk-doom-interruption/position-boundaries --cases retry cold-retry --firmware dist/lefony-os-prime-g2-resource-profile-vm.elf --firmware-debug dist/lefony-os-prime-g2-resource-profile-vm-debug.elf
.venv/bin/python vm/test-sdk-doom-resources.py --output build/sdk-doom-cleanup/final-resources --firmware dist/lefony-os-prime-g2-resource-profile-vm.elf
.venv/bin/python vm/test-sdk-doom-gameplay.py --project build/sdk-doom-cleanup/final-retry-project --output build/sdk-doom-cleanup/final-gameplay-v2 --firmware dist/lefony-os-prime-g2-resource-profile-vm.elf --measure-resources
.venv/bin/python -m pytest tests/test_sdk_doom.py -q
make check-public
```

No firmware rebuild is claimed for these app-recipe/test changes. No calculator
operation, deployment, commit, push or external communication occurred. Abrupt
reset and interrupted-upgrade workloads, wider controls/malformed-input/resource
coverage and general live-heap measurements remain. Native Windows and complete
supported-host bundles, production store accounting/migration/acceptance,
independent developer trials, numeric performance budgets and physical SDK 1.0
qualification remain separate unfinished work. The full SDK goal stays active.

Read-only evidence under `build/sdk-doom-cleanup/evidence` retains 12,533 indexed
files, 926,203,720 bytes: public sources, the exact VM/QEMU artifacts, prepared
projects, packages, synthetic workspaces, reports and failed attempts from both
workloads. Every indexed hash and read-only mode verifies. Index SHA-256 is
`8bb472c1c9879198288ce29ca97ff815df67626567711af26ac49ec1355a4c08`.
The frozen ledger precedes this final evidence annotation. All launched jobs
have collected terminal results.

## Explicit newlib heap observations and integrated workloads — 2026-09-14

The SDK now supports an explicit `LEFONY_PROFILE_HEAP: 1` integer define in
schema-2 `foreground-newlib-1` projects. The ordinary build/CMake path propagates
only this diagnostic setting to the newlib adapter. Default builds leave the
hooks off; removing the define rebuilds the original uninstrumented ELF bytes.
The setting remains enabled in a release profile until explicitly removed.
No app API, package/schema version, allocator-library pin, memory reservation or
signing policy changes. Diagnostic packages have their own exact identities.

The adapter samples the pinned allocator's `_mallinfo_r` at completed unlocks,
using a recursion guard and preserving `errno`. This captures transient
old/new allocation overlap during `realloc`, live reductions on free, allocated
chunk peaks and the separate arena extent. Chunk measurements include alignment
and allocator metadata, exclude static buffers, and do not measure usage within
custom suballocators such as Doom's zone. Scanning allocator free lists adds
diagnostic overhead; these are workload observations, not worst-case memory or
physical timing guarantees.

The linker retains a 40-byte app-local diagnostic record. Host tools validate
its initial bytes, ELF section and initialized writable-segment ownership in the
exact package before arming it. A separate VM-only heap-profile version-1
protocol returns an 80-byte snapshot without changing the original stack-profile
version-1 protocol. The VM bounds the address, accepts configuration only before
the first load, validates sequence/header/accounting fields and collects only
matching package loads. Faults, unloads and relaunches preserve peaks; another
package cannot replace or contribute to them. Incomplete records are `partial`,
no allocator observations are `not_observed`, and invalid records fail the
measurement. Only `observed` results populate `heap_peak_bytes`.

### Completed validation

- Full host suite: **1,281 passed, two expected private DTB/DTS skips** in
  334.10 seconds. After adding the relocated source-kit test and app-harness
  options, **72 focused host tests passed** in 29.89 seconds. The original
  focused attempt failed only a test's expected error-message expression;
  invalid boolean configuration was already rejected. That log is retained.
- Both physical and VM firmware compile. The final VM-only boundary checks
  were rebuilt before all integrated runs below. Existing upstream/linker
  warnings remain in the logs; no physical build was installed or qualified.
- Ten heap diagnostic cases pass: allocator transitions, a freed 1 MiB transient
  peak, no-allocation/default builds, relaunches, fault retention, incomplete and
  corrupt records, package attribution and explicit old-VM refusal. The allocator
  fixture exercises failed growth, preserved realloc contents, calloc,
  aligned/fragmented allocations, free/reuse and errno preservation.
- Nine existing stack-profile regressions pass on the final VM: written and
  untouched frames, guard and IRQ faults, default zero initialization, main
  relaunch, package exclusion, retained fault attribution and invalid-load/rearm
  boundaries. The optional old stack-firmware case was not rerun here; the heap
  suite separately checks refusal against the retained stack-only firmware.
- A relocated source kit with its bundled newlib builds an instrumented ARM
  image byte-identical to the checkout; every source-kit manifest hash verifies.
  The test removes ambient newlib/Python-path overrides and confirms linking
  uses the kit's runtime. This does not qualify complete desktop downloads.

All **39 instrumented proving-app cases** pass on the final VM:

| Application | Completed journeys | Largest observed allocated chunks | Largest observed stack extent |
| --- | --- | --- | --- |
| Notebook | 24 debug/release edit, cold reopen, legacy/malformed data, settings, validation and clipboard cases; 34 matching visual frames | 1,464 bytes | 12,976 bytes |
| minigzip | Nine streaming, cold update, corrupt/truncated input, corrected retry and path-error cases; exact source round trip | 294,240 bytes | 18,368 bytes |
| Link Gallery | Four debug/release connected/cache/error/reconnect and cold-cache journeys; eight matching visual frames | 147,904 bytes | 3,132 bytes |
| Doom 0.2.1 | Gameplay/save/load/clean exit and cold restoration with actual Fire input and retained virtual bindings | 6,640,048 bytes | 2,064 bytes |

The minigzip and Doom error/exit paths can still have app allocations when the
OS unmaps the process; reported current bytes describe the last allocator
observation, not memory retained by the OS after unload. Doom's observed arena
peak is 6,643,712 bytes, separate from its 8,380,416-byte OS heap reservation.
Both Doom saves remain byte-identical at 61,342 bytes. Notebook's formatted
document, Link Gallery's cold cached image and Doom's cold firing frame were
visually inspected. These instrumented runs supplement earlier ordinary-app
evidence and do not qualify physical performance.

### Candidate and reproduction

SDK executable identity:
`2dd6bd79a7250fa8e3dc901e7127df93b0401dbb58c47d78e3d73a924a68983a`.

| Artifact | SHA-256 |
| --- | --- |
| VM ELF | `4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14` |
| VM debug ELF | `50903528718ffac7022cdcb30d4d6e00305e61309b0aeac5e062c7d831416ea1` |
| VM binary | `94a2d1ce75eb4428379905f1d8fcdc123c72f2e8eea136bcc0059dccd3206505` |
| Physical ELF | `d7b59c1c62be7ef4228a2c8c5afd76fce8f761a6abd3e7d7d8bc975be8bd3363` |
| Physical binary | `37d29346a929bd9a77ad520a2df78b18a3468ce3f711895f3f210d199495f3da` |

The retained QEMU executable remains
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
Reports and sources are under ignored `build/sdk-live-heap/`. Each runtime
report binds its exact signed package and firmware; final verification records
the report/package hashes and per-workload observations.

```sh
make test
make firmware
make firmware-vm
.venv/bin/python -m pytest tests/test_sdk_heap_profile.py tests/test_sdk_resource_profile.py tests/test_sdk_project.py tests/test_sdk_runtime.py -q
.venv/bin/python vm/test-sdk-heap-profile.py --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --old-firmware dist/lefony-os-prime-g2-resource-profile-vm.elf --output build/sdk-live-heap/arm
.venv/bin/python vm/test-sdk-resource-profile.py --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --output build/sdk-live-heap/stack-regression
.venv/bin/python vm/test-sdk-notebook.py --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --output build/sdk-live-heap/notebook --measure-resources --profile-heap
.venv/bin/python vm/test-sdk-minigzip.py --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --output build/sdk-live-heap/minigzip --measure-resources --profile-heap
.venv/bin/python vm/test-sdk-link-gallery.py --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --output build/sdk-live-heap/link-gallery --measure-resources --profile-heap
.venv/bin/python vm/test-sdk-doom-gameplay.py --project build/sdk-live-heap/doom-project --output build/sdk-live-heap/doom-gameplay --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --measure-resources
make check-public
```

Use fresh output directories. Doom uses a separate prepared 0.2.1 project with
the diagnostic define and a locked copy of the earlier synthetic 0.2.0 game
workspace; `doom-seed.json` records its original overlay/descriptor hashes.
The named candidate ELF copies were preserved after sequential target builds.

The [testing guide](../sdk/TESTING.md#observing-newlib-allocations), project
configuration, C-library guide and capability inventory describe enabling,
disabling and interpreting this opt-in measurement. Native Windows and complete
supported-host bundles, production store accounting/migration/acceptance,
broader recovery/error workloads, independent trials, numeric performance
budgets and physical SDK 1.0 qualification remain unfinished. The full SDK goal
stays active. No calculator operation, deployment, commit, push or external
communication occurred.

The final source kit contains 422 verified files and hashes to
`d943fab5b9d75a0b79432555661f6a9d8412ceb429a9959c904959c86eaa2f7e`.
Its relocated bundled-newlib build reproduces the executed allocator-transition
package exactly (`9c5dca76ac68032f024a19b0927642ed13a243799646449c9b7ca60a033eb01f`).
The kit's ledger precedes this artifact annotation. The final candidate verifier
binds all 58 ARM cases, verifies package identities and matching debug/executable
load segments, and preserves per-app observations. Its initial indexing error
treated raw callback fixtures as signed packages; recording both exact formats
fixed the verifier without changing or rerunning the app/firmware candidates.

Read-only evidence under `build/sdk-live-heap/evidence` retains 4,318 indexed
files, 353,705,274 bytes, including public sources, exact firmware/QEMU inputs,
prepared projects, reports, synthetic media, source kit and failed attempts.
Every indexed hash and read-only mode verifies. Index SHA-256:
`554611c012c148394d7ff12e2e18dac1e59471446268d06f5f6549d3113012a0`.
The frozen ledger precedes this evidence annotation. Final public-boundary
checks pass for 1,072 files, along with 125 relative documentation targets,
Python syntax and changed-file whitespace. All launched jobs have collected
terminal results.


## Native Windows packaging path and desktop dependency gates — 2026-09-14

The desktop packager now accepts native Windows x86-64 Python 3.13+ inputs,
uses `.exe` tool names and the Windows Credential Manager backend, and creates
a ZIP containing the complete SDK folder. The frozen entry point adds bundled
DLL paths for child tools. Public-key validation uses the explicitly supplied
OpenSSL executable, including when OpenSSL is absent from PATH. Existing key
validation, signing policies, compiler/newlib pins and firmware are unchanged.

`scripts/native_desktop_windows.py` checks x86-64 PE inputs, ordinary/delayed
imports and forwarded exports. It collects non-system dependencies from explicit
input directories and audits the final bundle again. Missing DLLs, ambiguous
same-name/different-byte libraries, malformed/partially unreadable tables and
MSYS/Cygwin runtime dependencies fail. Windows system libraries remain external;
redistributable VC runtime DLLs need explicit inputs. Dynamically loaded libraries
still need explicit roots. The dependency record includes hashes and relative
paths, and does not claim native execution or complete corresponding-source
qualification. The implementation follows the Windows PE/DLL specifications and
PyInstaller 6.20.0 subprocess behavior linked in the host guide.

The pinned GDB 17.2 Unix build recipe has an explicit MinGW-w64 cross-build
route requiring Windows GMP/MPFR/Expat inputs and matching cross tools. It records
compiler hashes, retains its recipe/helper, validates the resulting PE and defers
execution to native packaging. No cross compiler is configured on this Mac, and
no completed Windows GDB cross build or native Windows bundle is claimed. Older
GDB candidates must retain the recipe that matches their recorded hash; this
macOS regression uses the original verified GDB binary and original recipe.

All platforms now execute bounded bundled doctor/QEMU/GDB/OpenSSL packaging
checks; doctor loads libusb without enumerating or opening a device. Fresh
staging directories clean up on success or failure. Native Windows tools/source
assembly, Windows execution, Credential Manager, USB drivers and clean-host
journeys remain open. A successful dependency audit cannot replace those checks.
The Homebrew source collector remains specific to its macOS native inputs.

### Validation and retained failures

The final focused suite passes **65 tests**, including actual PE table fixtures,
missing/delayed/transitive dependencies, DLL conflicts, malformed tables, wrong
architectures, ambient-PATH refusal, archive contents, debugger relay shutdown,
USB library selection and explicit OpenSSL key validation. Four actual Windows
bootloaders from the pinned PyInstaller wheel also pass static import inspection;
they were not executed. The first malformed-descriptor test exposed pefile's
silent omission of one broken entry; explicit descriptor validation now rejects
that partial result. The earlier failure log is retained.

An initial macOS packaging attempt omitted the dynamically loaded unversioned
`libSDL3.dylib` input and failed the bounded QEMU smoke check. The corrected
command supplies that dependency. Later, disk exhaustion interrupted a full host
suite and packaging attempt; neither is a pass. Only temporary stages, failed
candidate copies and the interrupted suite's temporary fixtures from this turn
were removed. Existing evidence and unrelated processes were preserved. Stage
cleanup is now automatic; the final successful stage is confirmed absent.

Final macOS desktop archive SHA-256:
`18675b88a2f640728b99029af7fe20d340e94cc3cd05a1bd976b6d46e666260b`.
Both its bundled SDK and the checkout have executable identity
`ab269a7a5505ff56d02ded815175f164e3d6802c5948153464af68392ede8b71`.
The bundled QEMU remains
`c6e5e83b8e398ebca70fc050ef2675f69321ad57953f43c377ddd67461f90ab2`,
from unchanged public input
`752d0fe63fdb4501750b22b3ecf2cbe0bf4121eee95c3bafe7c936c109e132de`.
It uses the retained live-heap VM ELF
`4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14`.
No firmware rebuild or physical operation occurred in this host-only checkpoint.

Reports, commands, failed-attempt logs and exact source hashes are under ignored
`build/sdk-windows-packaging/`. The final relocated offline regression passes all **eight templates**,
including workspaces, source formats, C-main GDB/relay debugging and actual ARM
Notebook/UI Gallery preview. Network, Homebrew and checkout access are denied
for SDK commands. The optional external-CMake check separately passes with
Python discovery disabled, outside that sandbox. Both preview PNGs are
byte-identical to the previously reviewed frozen-candidate frames. Offline
report SHA-256: `a761cfb8dcfe47ef3e434b5d624cf1385fde8a5ada0b4e58b6ef193c5aad22e0`.
The final full host suite passes **1,311 tests and 280 subtests**, with **2 expected private DTB/DTS skips**, in 516.16 seconds. The interrupted earlier run is retained separately and does not contribute to this pass. The full SDK objective remains active:
complete native host bundles/dependency sources, production store acceptance,
broader error/recovery workloads, independent trials, numeric budgets and
physical qualification remain. No deployment, commit, push or external
communication occurred. The desktop archive predates this ledger annotation
and the new build-only pefile notice; its executable SDK identity matches.


The final source kit contains **423 verified files** plus its checksum manifest,
including the GDB cross-build helper and updated notices. Archive SHA-256:
`e0a3282d221f548fd0f5e194ef20054e08ecb724719762d4e9f8d50afff062dc`.
The kit's ledger predates this final artifact annotation. Final executable source
hashes still match the recorded candidate. The public boundary passes for 1,074
files; 127 relative documentation targets and changed-file whitespace pass.

Reproduction uses fresh output directories and the explicit inputs in the host
guide. The successful macOS command includes the unversioned dynamically loaded
`libSDL3.dylib`; no timeout or library check was relaxed.

```sh
.venv/bin/python -m pytest tests -q
.venv/bin/python -m pytest tests/test_sdk_desktop_packaging.py tests/test_native_app_signing.py tests/test_sdk_gdb_transport.py tests/test_sdk_usb_library.py tests/test_sdk_local_transport.py -q
.venv/bin/python vm/test-sdk-desktop.py --bundle build/sdk-windows-packaging/macos-final-v2/lefony-sdk --output build/sdk-windows-packaging/offline-repeat
make check-public
```

A read-only evidence snapshot retains 56 source/report files, with index SHA-256
`1c080096fdcc391394e7a725593a2632409a16335e2a04ea9d9d3cc42522355b`.
Every indexed hash and read-only mode verifies. Bundle/source archives remain
at their original checkpoint paths, recorded by hash without duplicate binary
trees. The frozen ledger precedes this annotation. All launched jobs have
collected terminal results; the full SDK objective remains active.

## Host text encoding and Unicode project workflows — 2026-09-14

SDK-owned metadata, generated source, preview HTML and debugger scripts now use
explicit UTF-8 and LF line endings. Workspace import/restore, local project
indexes, preview receipts and migration receipts no longer rely on the host text
locale. Original user source/asset bytes and the existing permitted manifest/path
character sets are preserved. This changes text handling, not storage geometry,
migration durability or device authorization.

The three CLI entry points configure redirected stdout/stderr as UTF-8, after
multiprocessing dispatch. Interactive consoles and library callers retain their
own stream configuration; the internal GDB relay remains binary. Human tool
diagnostics tolerate invalid UTF-8 with replacement characters, while compiler
path/version output is decoded strictly. Preview captures compiler output as raw
bytes so diagnostic decoding cannot hide the original failed build. See the
[project text contract](../sdk/PROJECTS.md#host-text-encoding) and
[host guide](../sdk/HOSTS.md).

The retained baseline reproduced `UnicodeEncodeError` in preview HTML under
`US-ASCII`, with Python UTF-8 mode and locale coercion disabled. Eight new host
cases cover workspace export/restore, invalid UTF-8 rejection before reset,
HTML escaping, local project paths and all CLI entry points. They also compile
an actual ARM function with a Unicode symbol, symbolize it with addr2line,
generate a debugger script and reproduce the ARM image after source exchange.
A real compiler error containing Unicode preserves the stale preview.

`vm/test-sdk-host-text.py` runs an external Notebook project in a Unicode path,
with the same non-UTF-8 locale and every `EncodingWarning` promoted to an error.
Four ARM phases pass: normal-input document edit, cold reopen after a source
comment edit, intentional compiler failure, and repaired-source reopen. The
signed preview archive contains identical saved document bytes in every phase;
the failed build preserves the archive, receipt and last frame exactly. The
repaired preview matches the preceding successful cold frame. Captured frames
were inspected. A comment-only source change leaves the executable package
unchanged; the intentional `#error` establishes that the new source was compiled.

Validation on macOS 26.6.2 ARM64:

- **144 focused host tests pass**, including eight new locale cases.
- The final full host suite passes **1,319 tests and 280 subtests**, with **two
  expected private DTB/DTS skips**, in 342.06 seconds.
- The rebuilt frozen SDK passes **all eight relocated offline templates** with
  outbound network, Homebrew and checkout access denied. This includes C-main
  GDB/relay debugging, source formats, workspaces and ARM Notebook/UI Gallery
  preview. The optional external-CMake check runs separately outside that sandbox
  with Python discovery disabled. Both preview frames match the previous reviewed
  frozen candidate byte for byte. This frozen regression does not claim that
  PyInstaller honored the source interpreter's forced non-UTF-8 environment.
- The public source boundary passes for **1,076 files**; the affected guides'
  relative targets, Python syntax and changed-file whitespace pass.

Exact inputs and evidence are retained under ignored `build/sdk-host-text/`:

| Artifact/report | SHA-256 |
| --- | --- |
| Source and frozen executable SDK identity | `92b1da3cf439c8c1d32f98aff059a402d7f8cf9ba6e816a539d3235f9233ee95` |
| `desktop/lefony-sdk-darwin-arm64.tar.gz` | `888b42d88daedb9ab84721db4424cd47ed9dca9dd9da269a4156a4d53efc28bc` |
| `arm/report.json` | `c9f279248860678f5a9bf898d8cf1d02c094d0880707d11c7c2022e23d0aeb45` |
| `offline/report.json` | `958024c42733298d2c6fa2cfae97fb7ef785f5a52b83e30a2b2a4efbd5b2235c` |
| `host-final.log` | `c2d4639267b12aa85310ac3074ffc73e90ac3b9a9c56f5aa191afcb0ae84fb34` |

All 1,912 frozen bundle manifest entries verify. Firmware is unchanged: VM ELF
`4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14`.
The source ARM journey uses QEMU
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`;
the frozen bundle uses
`c6e5e83b8e398ebca70fc050ef2675f69321ad57953f43c377ddd67461f90ab2`.
The archive predates this ledger annotation. Reproduce with fresh outputs:

```sh
.venv/bin/python -m pytest tests/test_sdk_text_encoding.py -q
.venv/bin/python -m pytest tests -q
.venv/bin/python vm/test-sdk-host-text.py --qemu build/qemu-prime-g2/qemu-system-arm --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --output build/sdk-host-text-repeat/arm
.venv/bin/python vm/test-sdk-desktop.py --bundle build/sdk-host-text/desktop/lefony-sdk --output build/sdk-host-text-repeat/offline
make check-public
```

Native Windows filesystem/compiler/console behavior, complete supported-host
downloads and dependency-source audits, production store acceptance, broader
recovery workloads, independent developer trials, numeric budgets and physical
qualification remain open. No calculator operation, firmware rebuild, deployment,
commit, push or external communication occurred. The full SDK goal remains active.

The final standalone kit contains **423 verified files** plus its manifest. Two
independent packaging runs produce SHA-256
`d91d2908536f921deff72a5b224c32256b4b60368b41b5a9ea972699993e9fe1`.
An external Notebook project in a Unicode path builds from that kit with UTF-8
mode disabled and its bundled newlib selected explicitly by the recorded link
arguments. Its package is byte-identical to the executed ARM candidate
(`f076d66cc35f4e393d4c838b41eaf1803dab367954de06116112049218f4403f`).
The kit's ledger precedes this artifact annotation. The retained source delta
against the preceding verified kit contains 19 SDK tool files, all scoped to the
text-handling changes described above.

## Pillow native sources and actual desktop input inventory — 2026-09-14

`scripts/pillow_native_sources.py` and its reviewed JSON lock bind the selected
Pillow 12.3.0 CPython 3.14 macOS ARM64 wheel to 138 installed file hashes and
21 source archives. These include the pinned Pillow/multibuild build recipes,
Pillow's TIFF patch, direct library sources and the AOM, dav1d, libyuv and
libsharpyuv sources compiled into AVIF. The original wheel bytes were checked
against the PyPI artifact before deriving the lock. The wheel itself is retained
only as local audit input; corresponding-source downloads do not include it.

The collector keeps original composite notices and Pillow's embedded CycloneDX
inventory. Refreshing copied Python source materials now includes these reviewed
native sources on the selected host. Before a macOS ARM64 build, the packager
requires matching source inputs and installed wheel bytes. After PyInstaller,
it uses the actual analysis table to record input and relocated output hashes
for all **19 native outputs: 13 libraries and six extension modules**. Missing
sources/patches, changed wheel inputs and unrecognized or incomplete native
inventories fail. The full collector checks that record before distinguishing
wheel libraries from Homebrew inputs.

The full inventory replaces stale Homebrew `libxau`, `libxcb` and `xz` source
entries with their actual Pillow-wheel source relationships, and includes the
build-only pefile source. It contains **41 components**. An initial candidate
established the PyInstaller input map; the final candidate uses the resulting
full source inventory. Its predecessor archive and reports remain available;
only that intermediate candidate's recoverable extracted directory was removed
to keep disk usage bounded. No failing package checks were bypassed.

Source correspondence has explicit limits. The upstream wheel build has not been
reproduced. Pillow's recipe fetched an unpinned `pillow-depends` mirror; retained
mirror archives are bound to Git blobs in its final revision before wheel upload,
not described as an attestation of the original builder cache. Different Python
or host wheels need separate reviewed inputs. These records do not qualify every
native dependency or the complete SDK release. The [host guide](../sdk/HOSTS.md)
links the pinned upstream recipes and explains the maintenance workflow.

Validation on macOS 26.6.2 ARM64:

- **93 focused host tests pass**, including source/notice/patch integrity,
  wheel changes, input-table coverage, output/manifest changes and source-path
  rejection, plus existing packaging/project/source-kit regressions.
- All 138 installed wheel files match the original PyPI wheel. The 19 packaged
  native binaries are byte-identical to the preceding tested desktop candidate.
  Its AVIF codec query reports dav1d `1.5.3-0-gb546257` and AOM `3.14.1`, matching
  the selected recipe inputs. A dry run applies the retained TIFF patch cleanly
  to the retained `tif_getimage.c` source.
- The full source collector succeeds on the actual desktop inventory. All
  **1,906 bundle manifest entries** verify, including original component notices.
- **All eight relocated offline templates pass**, with network, Homebrew and
  checkout access denied. C-main debugger/relay, workspaces, source exchange and
  real ARM Notebook/UI Gallery previews pass. The separate external-CMake check
  keeps Python discovery disabled and runs outside that sandbox. Both preview
  images match the preceding reviewed candidate exactly.
- Public-tree, affected documentation-target, Python syntax and changed-file
  whitespace checks pass. This host packaging checkpoint does not claim a new
  full host suite or firmware compilation.

Exact artifacts and reports under ignored `build/sdk-pillow-sources/`:

| Artifact/report | SHA-256 |
| --- | --- |
| `desktop-final/lefony-sdk-darwin-arm64.tar.gz` | `b085a52720c8bc236a63bc8d18646f109acf3fa1549902455852238d1dc8dd54` |
| `materials/manifest.json` | `dc63dc513f8a06f30573d5bd86319291055fe2eacd3ff01297be580cbbce4b41` |
| `desktop-final/lefony-sdk/pillow-native-inputs.json` | `e26ac62efcb1bcff519f4da8b8f730264709e3d988487bbb228addde7821f696` |
| `offline/report.json` | `3732d91f5ae4606abf14781d2c4a620a267ad29ea22bb715f292b03c4028aef2` |

Executable SDK identity remains
`92b1da3cf439c8c1d32f98aff059a402d7f8cf9ba6e816a539d3235f9233ee95`;
VM ELF remains `4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14`.
The frozen QEMU is still
`c6e5e83b8e398ebca70fc050ef2675f69321ad57953f43c377ddd67461f90ab2`.
The binary archive predates this ledger/status annotation. Reproduce using fresh
output paths and the explicit packager inputs in the host guide:

```sh
.venv/bin/python -m pytest tests/test_sdk_pillow_sources.py tests/test_sdk_desktop_packaging.py tests/test_sdk_maturity.py tests/test_sdk_project.py -q
.venv/bin/python scripts/collect_native_desktop_sources.py --bundle build/sdk-pillow-sources/desktop-final/lefony-sdk --output build/sdk-pillow-sources/materials
.venv/bin/python scripts/package_native_desktop_sources.py --materials build/sdk-pillow-sources/materials --output build/sdk-pillow-sources-repeat/source-downloads --group runtime
.venv/bin/python vm/test-sdk-desktop.py --bundle build/sdk-pillow-sources/desktop-final/lefony-sdk --output build/sdk-pillow-sources-repeat/offline
make check-public
```

Native Windows execution and other complete supported-host bundles, remaining
release-source qualification, production store acceptance, broader recovery
workloads, independent trials, numeric budgets and physical qualification remain
open. No calculator operation, deployment, commit, push or external communication
occurred. The full SDK objective remains active.

The runtime corresponding-source archive verifies **255 files across 39
components**, including all 86 declared source/notice inputs and recorded recipe
hashes. Its 24 Pillow entries contain all 21 archives, the reviewed lock, original
notices and dependency inventory. No wheel binary is included. Archive SHA-256:
`001244977f098e72c61e8a9c2f78236c4d7372b387d172c4e8fddc2395b8bd55`.
Toolchain, GDB and Lefony/QEMU corresponding-source groups remain separate
artifacts with their own release requirements.

The standalone SDK kit contains **425 verified files**, including the source
audit helper and lock. Two packaging runs produce SHA-256
`a055b5eb6f7b825cc15c9795c538a3a47ac5362926be77dfe7f2bdcd389fb0cb`.
Its external Unicode-path Notebook build uses bundled newlib and reproduces the
previously executed ARM package exactly. The kit's ledger predates this artifact
annotation. The final public boundary passes for **1,079 files**.


## Doom abrupt-stop save recovery — 2026-09-14

The new `vm/test-sdk-doom-reset.py` runs the existing Doom 0.2.1 ARM image
through selected abrupt-stop boundaries. A test-local runner adapter replaces
installation with signature validation, capability checks, catalogue lookup and
exact public package readback. It rejects host install/import/repair requests;
USB OUT requests are restricted to selecting, acknowledging or cancelling public
read sessions. Every cold boot therefore inspects the existing installation
before launching it. No SDK runtime, firmware or Doom executable change was
needed for this checkpoint.

Normal KPP input loads the retained game, turns the player and requests a save.
Matching app/firmware symbols supply read-only observations at temporary hardware
breakpoints. The test kills exactly its own QEMU process with SIGKILL while the
CPU is stopped; it sends no Home, quit, flush or storage-drain request on that
path. Subsequent boots use the same copied synthetic media. No guest variables,
game functions, filesystem functions or raw NAND bytes are injected by the test.

The nine-phase matrix passes:

| Cut | Witness | Cold recovery and retry |
| --- | --- | --- |
| Save staging | 27,648 bytes staged out of the prior 61,342-byte save; writer active | Exact old save/configuration, generation 29; retry commits generation 30 |
| Reference-verification entry | Complete save staged; file commit waiting in the reference-check phase | Exact old save/configuration, generation 30; retry commits generation 31 |
| Before root rename | Replacement root staged and verified; document store at Commit | Exact old save/configuration, generation 31; retry commits generation 32 |
| After root rename | Rename returned zero; app still saving with its writer active | New save at generation 33; exact newly serialized player state; retry commits generation 34 |
| Final cold load | No reinstallation | Exact retry bytes/state at generation 34; unchanged settings and complete WAD |

The initial verification observer's cursor could still refer to the preceding
metadata check at phase entry. The final harness additionally requires an open
reference file. A separate three-phase run passes an abrupt stop after **2,048
reference bytes have actually been read**, old-save recovery at generation 29,
retry at generation 30 and a final cold load. Its source differs from the matrix
harness only in the additional open-file observation, breakpoint condition and
assertion. Both source versions and their reports are retained; the entry cut is
not described as an in-progress reference read.

All recovery runs compare the 12 serialized/restored player fields at save/load
EOF breakpoints, before resumed gameplay changes them. They compare complete
public save/configuration exports, check generations, retry through ordinary
Doom input, and return to a responsive OS without an app fault. Both final runs
export all **28,795,076 WAD bytes** through the public file API and match the
pinned Freedoom SHA-256
`7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d`.
Retry frames were inspected and show normal gameplay and save confirmation;
load snapshots can capture the engine's normal melt transition. This is not
frame-pacing or input-latency qualification.

Initial harness failures remain under `build/sdk-doom-reset/initial-staging`,
`current-v1`, `current-v2` and `current-v3`, with their adjacent logs. They exposed
premature input before the load had resumed ticking, an unguarded observer read
before player creation, and GDB's combined location/condition parser rejecting
quoted anonymous-namespace expressions. The final harness waits for observed
engine progress and separates breakpoint location from condition. A GDB command
file stops on the first setup error instead of continuing past a rejected
breakpoint. These failed runs are not counted as passing reset cases.

Validation on macOS 26.6.2 ARM64:

- **Nine matrix phases plus three stronger verification-read phases pass.**
  Both processes finish with exit status zero; all five intentional QEMU stops
  finish with SIGKILL and each has a corresponding successful cold recovery.
- **Three Doom host tests pass** in 55.85 seconds.
- Python compilation, CLI help, changed-file whitespace, documentation targets
  and public-tree checks pass. No new full host suite, firmware compilation or
  frozen-desktop rebuild is claimed for this test/documentation checkpoint.

Exact evidence under ignored `build/sdk-doom-reset/`:

| Artifact | SHA-256 |
| --- | --- |
| `current-v4/report.json` | `c6b630ebc0c883dc39add252165327d0b67b3a3a505d57a3fe2ffc8aa4f058e9` |
| `verification-read-v5/report.json` | `f85bbfe786f751fc8fac1146989ab6c8cb6180764dba5a89e9a3aa6951a7c42b` |
| Matrix harness snapshot | `d19dd829a3d212fc5ed3f4d194829c8e3e644dc9c082baf71652685f1e28e6af` |
| Final harness | `802febb33925bed9c8eb004cdfeb439ea3eb4deac3de2dd0c41e42028abe4be0` |
| Executed app ELF | `a0dd373610b9432563ca6f8913a70d8323d0d2419d12e48bd9f4c0e6819339bb` |
| Matching app debug ELF | `2d76249f0103237dd774dc83bbd7a5d05c44e3a3e5ffb5ae02ee15a4f46eb8d0` |
| Signed installed package | `2f76a16205d674561fd060696198dbe2e173db22c1041e6c08994022fb88319f` |

SDK identity remains
`92b1da3cf439c8c1d32f98aff059a402d7f8cf9ba6e816a539d3235f9233ee95`.
VM ELF remains
`4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14`,
with matching debug ELF
`50903528718ffac7022cdcb30d4d6e00305e61309b0aeac5e062c7d831416ea1`.
Developer QEMU remains
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The starting synthetic overlay hash and every source hash are in each report.

Reproduction from the OS checkout, using a previously signed, installed game
workspace with the matching package, saved settings and saved game:

```sh
.venv/bin/python vm/test-sdk-doom-reset.py --seed-project build/sdk-doom-cleanup/final-retry-project --output build/sdk-doom-reset/repeat --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --firmware-debug dist/lefony-os-prime-g2-live-heap-vm-debug.elf
.venv/bin/python vm/test-sdk-doom-reset.py --seed-project build/sdk-doom-cleanup/final-retry-project --output build/sdk-doom-reset/repeat-verification --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --firmware-debug dist/lefony-os-prime-g2-live-heap-vm-debug.elf --cases verification
.venv/bin/python -m pytest tests/test_sdk_doom.py -q
make check-public
```

The checked-in harness now uses the stronger reference-read cut by default.
The recorded nine-phase run used the retained preceding observer, followed by
qualification of that sole conditional-breakpoint change in the three-phase run.
See the [Doom guide](../sdk/ports/doom/README.md) for the workflow.

These cuts model lost guest volatile state between completed NAND operations;
QEMU's append-only overlay replays completed records. They do not establish torn
physical programming, host power loss, electrical behavior or flash endurance.
Interrupted Doom upgrades, wider reset/resource/control workloads, supported
native host bundles, production store acceptance, independent trials, measured
budgets and physical SDK qualification remain open. The full SDK goal remains
active. No physical calculator operation, deployment, commit, push or external
communication occurred.

A read-only snapshot retains 1,455 source, report, breakpoint-log, frame and app
artifact files (10,227,912 bytes). Every indexed hash and file mode verifies;
index SHA-256 is
`3d6099d69d4e5ff81a016e53e3e3fa7c0bc959c82f0e7b32bb4b12c888293eab`.
The snapshot's ledger precedes this annotation. The large synthetic overlays,
WAD exports and existing firmware/QEMU artifacts remain at their recorded paths.
Final checks pass for 130 relative documentation targets and the 1,080-file
public source boundary. All launched jobs have collected terminal results.

## Doom interrupted-update recovery — 2026-09-14

The maintainer harness `vm/test-sdk-doom-upgrade-reset.py` exercises signed
compatible updates of an installed Doom game using copied synthetic media.
Its three packages have fixture versions 0.2.1, 0.2.2 and 0.2.3 and distinct
signed identities, with identical executable/debug ELF bytes. These are local
manifest changes, not a new Doom release or a data-format migration. The public
SDK, firmware, signing policy, storage geometry and Doom engine are unchanged.

Each boot authenticates and reads back the existing signed package before
launching it. The test-local runner adapter never reinstalls to make a cold
boot pass. Public file/data reads inspect saved state; only explicitly selected
install and rollback phases may issue those host mutations. No host import,
firmware, provisioning, key-management or raw-NAND command is allowed.

Normal KPP input loads the saved game. Matching app symbols capture twelve
restored player fields before gameplay advances. The app returns through Home
before an explicit signed update. A partial-upload cut uses QMP stop after a
completed USB acknowledgement; storage cuts use temporary hardware breakpoints.
The test kills only its owned QEMU process while the CPU is stopped, without
guest cancellation, Home, quit or storage drain on that cut path.

**All 17 ARM phases pass**, with four intentional QEMU SIGKILL stops.

| Cut | Witness | Final cold result |
| --- | --- | --- |
| upload | 201,216 of 402,301 signed bytes received; upload state | Version 0.2.2, generation 33; complete WAD verified |
| package-write | 2,048 package bytes written; writer open | Version 0.2.2, generation 33; complete WAD verified |
| before-rename | Complete 402,301-byte package; staged/verified root before rename | Version 0.2.2, generation 33; complete WAD verified |
| after-rename | Root rename returned zero; installation still working | Version 0.2.3, generation 35; complete WAD verified |

The pre-commit cases retain the old package, original data generation and
version floor on a cold boot, then retry the same update successfully. After
the commit rename, the new package and its old recovery pair survive even though
installation has not returned completion. Public rollback restores 0.2.1 while
retaining the 0.2.2 version floor; attempting that retired version fails with
installation error 8 and leaves the OS responsive. Another cold boot verifies
the rollback before a 0.2.3 retry.

Ordinary Doom Quit saves its two configuration files and accepts the compatible
schema-zero update. Home unloads the app and clears its live exit diagnostic,
so the harness records successful ordinary exit before Home and separately
checks the committed package/data state afterward. Acceptance clears the
pending/recovery flags; the final cold load verifies persistence and the same
saved player state.

Every snapshot compares all 61,342 saved-game bytes, both configuration files
(1,463 and 2,947 bytes), root/save directory entries and the empty private-data
snapshot's digest.
Every case's final cold phase exports the full 28,795,076-byte WAD through the
public USB file API and checks its independently pinned SHA-256
`7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d`.

Initial runs remain retained. `post-commit-v1` stopped because GDB's dump-range
parser split an anonymous-namespace symbol containing spaces. The final script
first resolves the address into a debugger convenience variable; it does not
write guest memory. `post-commit-v2` demonstrated cut/recovery/rollback/retry
and accepted storage, then failed an assertion on the already-cleared exit flag.
`matrix-v3` was explicitly interrupted once that assertion error was identified.
These runs are not counted as a complete passing matrix. Their source snapshots,
reports and observations distinguish harness defects from firmware behavior.

Validation and retained evidence on macOS 26.6.2 ARM64:

- **17 upgrade phases and three additional quick-slot sessions pass.** The
  quick-slot checkpoint below records its separate source and results. All five
  complete WAD exports match the pin: **143,975,380 total bytes**.
- **Three Doom host tests pass** in 51.81 seconds.
- Separate artifact audits verify candidate/source hashes, public readbacks,
  preserved saves/configuration, version/generation results and complete WADs.
  For each update case, the final overlay still contains the exact retained
  prefix from its interrupted state and the unchanged original seed prefix.
- Python syntax, both CLI help entry points and changed-file whitespace pass.
  Final documentation/public-tree checks are recorded below. No new full host
  suite, firmware compilation or frozen-desktop rebuild is claimed.

| Artifact | SHA-256 |
| --- | --- |
| `matrix-v4/report.json` | `3c7e57dc50e50b581a56ccc12fca0753bbe9fc9c7a234101262acd977e70ebd2` |
| `audit.json` | `a6ac10bd41d4365ad768fd1bcea6c3433abe77a08b121516e58265c2c7162805` |
| Final harness | `45cf20405c4da15ce688ffd73a48842dc2462c4bc74a9066b668edff70245f43` |
| Signed 0.2.1 fixture | `2f76a16205d674561fd060696198dbe2e173db22c1041e6c08994022fb88319f` |
| Signed 0.2.2 fixture | `a75b37d8843309f494b7759d482a04007af82fd50dc8dc7c2f2e6968e3e42291` |
| Signed 0.2.3 fixture | `3d523133c457a5f85425c3a0fd96a4038eddcfff81d23a3aa69c7faab8e6c341` |

SDK identity remains `92b1da3cf439c8c1d32f98aff059a402d7f8cf9ba6e816a539d3235f9233ee95`.
Executed app ELF remains `a0dd373610b9432563ca6f8913a70d8323d0d2419d12e48bd9f4c0e6819339bb`.
Matching app debug ELF is `2d76249f0103237dd774dc83bbd7a5d05c44e3a3e5ffb5ae02ee15a4f46eb8d0`.
VM ELF remains `4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14`,
with matching debug ELF `50903528718ffac7022cdcb30d4d6e00305e61309b0aeac5e062c7d831416ea1`.
Developer QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
Source snapshots, per-phase observations, captured files and interrupted media
lengths remain under ignored `build/sdk-doom-upgrade-reset/matrix-v4/`.

Reproduction from the OS checkout with a prepared installed game workspace:

```sh
.venv/bin/python vm/test-sdk-doom-upgrade-reset.py --seed-project build/sdk-doom-cleanup/final-retry-project --output build/sdk-doom-upgrade-reset/repeat --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --firmware-debug dist/lefony-os-prime-g2-live-heap-vm-debug.elf
.venv/bin/python -m pytest tests/test_sdk_doom.py -q
make check-public
```

These are selected guest-process-loss cuts between completed modeled NAND
operations. They do not establish torn physical programming, host power loss,
flash endurance, physical USB/input timing or upgrades that change Doom's
executable/data format. Broader reset/resource/control workloads, supported
native bundles, production store acceptance, independent trials, numeric
budgets and physical qualification remain open. No calculator operation,
deployment, commit, push or external communication occurred. The full SDK goal
remains active.

## Doom quick slots, cancellation and cold recovery — 2026-09-14

`vm/test-sdk-doom-quickslots.py` adds a normal-input user-data workflow to the
unchanged Doom 0.2.1 candidate. It selects an unused named-save slot from the
public directory listing, preserving every existing named save and both
configuration files. The recorded seed contains slots 0 and 1; the test uses
slot 2. Bootstrap performs signed readback of the installed package and forbids
host install/import/repair actions. All save mutations originate in the running
game through ordinary KPP input and public SDK services.

**All three ARM sessions pass** on macOS 26.6.2 ARM64. The separate artifact audit also passes.

| Session | Data generation |
| --- | --- |
| `select-load-cancel` | 29 → 30 |
| `cold-replace-load` | 30 → 32 |
| `cold-final` | 32 → 32 |

Both original 61,342-byte saves, the 1,463-byte default configuration and the
2,947-byte additional configuration remain byte-identical. The final 61,342-byte
quick save survives cold loading. All **28,795,076 WAD bytes** are exported
through the public file API and match the pinned asset hash.

The first session selects the quick slot with Plot, saves, turns away, restores
through View, then cancels an overwrite with Back. The next cold boot compares
the restored state at the load EOF breakpoint with the preceding serialized
state. Only one generation was committed, so cancellation did not silently save
the later position. The second session reselects the slot, overwrites it through
quick-save confirmation and quick-loads the replacement; two additional save
generations commit. A final cold launch restores that replacement without another
write. Quick loads and subsequent cold named loads compare all twelve player
fields with the preceding save observations before gameplay resumes.

The original engine deliberately resets `quickSaveSlot` at startup. View after
a cold launch displays its no-selected-slot message; it does not automatically
choose the last saved file. The test dismisses that message and uses Symb to
load the named slot, then Plot to select the session's quick slot when needed.
The save files persist independently of this menu choice. Reviewed captures
show the no-slot message and normal gameplay after cancellation; these are not
frame-pacing or physical-input measurements.

Initial fixture/observer failures remain retained. `current-v1` rejected the
incorrect assumption that the seed had only one saved slot. The final harness
chooses an unused slot and compares every preexisting save. `current-v2` was
stopped after observing that upstream leaves `save_stream` non-null after
closing a loaded game; pointer presence alone cannot identify an active save.
The final observer also requires the save action and waits for advancing game
ticks after the serialization/restoration breakpoint. No engine, firmware or
SDK runtime change was needed to resolve these harness defects.

Exact evidence remains under ignored `build/sdk-doom-quickslots/`:

| Artifact | SHA-256 |
| --- | --- |
| `current-v3/report.json` | `dc857a0d7a5a985a9734a80ffc3981e97648afca70b850680b3070c9f3c49436` |
| `audit.json` | `f005d2feb3932383f915d536938a6716d2199c1d31f9fadfc83f64d370662012` |
| Harness | `1e1414d42735eb0788ec076ad2f97e618ba28d390ba482a479354ec707afbb00` |
| Executed ELF | `a0dd373610b9432563ca6f8913a70d8323d0d2419d12e48bd9f4c0e6819339bb` |
| Matching debug ELF | `2d76249f0103237dd774dc83bbd7a5d05c44e3a3e5ffb5ae02ee15a4f46eb8d0` |
| Final quick save | `29a03c636499ebafa2116ff8c050e084283873b87745a7494de1b4902d8986a6` |

SDK identity remains `92b1da3cf439c8c1d32f98aff059a402d7f8cf9ba6e816a539d3235f9233ee95`.
VM ELF remains `4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14`.
Developer QEMU remains `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The selected source snapshots and normal-input/GDB logs are retained with the report.
This checkpoint changes tests and documentation only; no firmware or frozen SDK
rebuild is claimed. The focused host and final public/document checks are recorded
with the interrupted-update checkpoint.

Reproduction from an installed Doom 0.2.1 synthetic game workspace with at least
one unused named slot:

```sh
.venv/bin/python vm/test-sdk-doom-quickslots.py --seed-project build/sdk-doom-cleanup/final-retry-project --output build/sdk-doom-quickslots/repeat --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --firmware-debug dist/lefony-os-prime-g2-live-heap-vm-debug.elf
```

Wider control combinations, long-running/resource cases, physical input and SDK
release qualification remain open. This adds selected quick-slot and recovery
evidence; it does not qualify the complete Doom control map or physical storage.
The full SDK goal remains active, with no physical calculator operation,
deployment, commit, push or external communication.

Final checks for these two checkpoints pass: both harnesses parse and expose
their CLI help, all 130 relative documentation targets resolve, changed-file
whitespace is clean, and the public source boundary passes for 1,082 files.

To recover local disk space, this run removed only the verified extracted copy
at `build/sdk-host-text/desktop/lefony-sdk`: all 1,931 files (722,970,031 bytes)
matched the retained archive, SHA-256
`888b42d88daedb9ab84721db4424cd47ed9dca9dd9da269a4156a4d53efc28bc`.
Re-extract that archive to repeat the older host-text bundle checks. Its
`extracted-duplicate-cleanup.json` records the verification; the archive and
previous reports remain retained. Native Windows/Linux x86-64 test-host access
has not been supplied. The available local Docker host is Linux ARM64, which
does not satisfy those native host gates.

The read-only snapshot under `build/sdk-doom-upgrade-reset/evidence/` retains
2,572 files (15,453,933 bytes), including both final reports/audits, source
snapshots, captured data/frames, debugger logs and matching app artifacts. Every
indexed size, hash and read-only file mode verifies. Its index SHA-256 is
`1a2edeadcc04cc1c8ed5910f6e29bf96b45bc692070e82ab9f7cb019d329ede8`.
The snapshot's ledger predates this annotation. Large overlays, WADs and the
firmware/QEMU binaries remain at the paths and hashes in its external-artifact
index. All launched jobs have collected terminal results; the unrelated stock
emulator was left running.


## Touch text editing and Notebook field activation — 2026-09-14

This R3 follow-on fixes a reproduced document workflow defect. On the prior
Notebook source, a normal Goodix tap inside the expression field invoked the
same handler as OK: the expression was saved and the editor closed. The ARM
reproduction recorded the title changing to `Notebook` when `Edit expression`
was expected. It used SDK identity
`92b1da3cf439c8c1d32f98aff059a402d7f8cf9ba6e816a539d3235f9233ee95`.

The app-linked `TextFieldModel` now shares rendered-cell geometry with
`Widgets::field`. It provides tap placement, captured drag selection, a retained
horizontal viewport and one-cell scrolling on moves in the horizontal inset.
Cancelled/outside, multi-contact and changed-contact gestures restore the prior
selection and viewport. Keyboard input cancels capture before editing; disabled
fields and clipped-out areas cannot capture. Touch selects base-plus-accent
cells; keyboard movement retains Unicode-scalar boundaries. There is no
stationary-finger scroll timer or general grapheme-segmentation claim.

Notebook **0.6.1** uses this interaction without saving on touch. OK and the Save
button remain explicit commits. UI Gallery **0.1.1** demonstrates accent-aware
selection, empty/disabled fields and a 1023-byte field; OK retains its select-all
action. Other `Widgets::field` callers keep the existing stateless display unless
they opt into the model. The new `TextBuffer::select(caret, anchor)` validates
UTF-8 byte boundaries atomically. These are SDK/header and example changes;
firmware, storage format, ABI and runtime service contracts are unchanged.

Validation on macOS 26.6.2 ARM64:

- `tests/test_sdk_ui_workflow.py`, `test_sdk_notebook_system.py`,
  `test_sdk_maturity.py`, `test_sdk_gallery.py`, `test_sdk_graphics.py` and
  `test_sdk_text_encoding.py`: **56 passed**, 21.83 s. The new model case uses
  address/undefined-behavior sanitizers and 20,000 adversarial contact events,
  plus explicit UTF-8, cancellation, clipping, overflow, empty/full, disabled and
  horizontal-scroll checks. An earlier focused UI run passed eight tests.
- `vm/test-sdk-text-field.py`, `current-v2`: **six ARM sessions**, with **29
  matching debug/release frames**. Notebook performs middle insertion, touch
  selection/replacement, three cancellation cases, keyboard input during capture,
  explicit save/export and Home/relaunch. Gallery exercises accented-cell
  replacement, insertion before pi, disabled/empty fields, selection/replacement
  of the visible `END` suffix in 1023 bytes, whole-field replacement and Home.
- `notebook-readback-v3`: **four additional ARM sessions**, **16 matching frames**,
  strengthening both cold boots with signed-package authentication and exact
  public readback instead of runner reinstallation. The cold host guard permits
  only package/file read sessions; each observes one `0x6a`, four `0x71` and four
  `0x73` requests, no installation/upload/write requests. Both profiles reopen
  generation 5, preserve `2+9*24` in the exact format-3 document and export the
  independently expected result **218**. These four sessions include the two
  setup/edit sessions and the two cold sessions.
- `vm/test-sdk-notebook.py`: all **24 ARM regression cases** pass, with **34
  matching frames**, including old/malformed documents, validation, saved math
  settings, clipboard limits, export and cold reopening.
- `vm/test-sdk-ui-components.py --paint-kinds 6 10`: **four ARM paint sessions and
  two gallery sessions** pass, with **39 matching frames**. Long and short-suffix
  field painting match across seven clips; the existing menu/dialog/font/theme,
  loading/disabled and Home gallery journeys pass.

Total: **40 ARM sessions**. The 118 debug/release frame comparisons include the
repeated Notebook checkpoints in the stronger readback run. Reviewed actual
frames show the middle caret, selected digits, selected composed accent, and
selected/replaced long-field suffix with no field-border overflow. These checks
use KPP/Goodix and normal dispatch; inspection reads debug records without
changing guest state. No physical-input feel or timing claim follows from them.

Reproduce the new and existing ARM checks with:

```sh
.venv/bin/python vm/test-sdk-text-field.py --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --output build/sdk-text-field/recheck
.venv/bin/python vm/test-sdk-notebook.py --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --output build/sdk-text-field/notebook-recheck
.venv/bin/python vm/test-sdk-ui-components.py --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --output build/sdk-text-field/components-recheck --paint-kinds 6 10
```

The final harness includes the stronger readback behavior by default. Reports,
steps, rendered frames, layouts and exact packages are retained under
`build/sdk-text-field/`. Candidate identities:

| Artifact | SHA-256 |
| --- | --- |
| SDK executable inputs | `a5f7b66d621998818dcfa147c1990a8384a897c692dbf6818ba8dc25005c7e3d` |
| Notebook debug raw package | `d01def4746b6a2dcad163b7886bf4b2d0c103e4150de81d9fc2207a71207640b` |
| Notebook release raw package | `6273444242f404ecf9bfe11af8b8d54c9443a2516c22add38f041ae21ba4aa5b` |
| Gallery debug raw package | `c2b05978547704d4f4d5979c3ca1edcbaae4f5b2303684106e721cac25db2b2a` |
| Gallery release raw package | `c094223ad68949dd4a4e1e006cc9c9117503b4da252c896c0ab5b20a491e0389` |
| VM ELF (unchanged) | `4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14` |
| Developer QEMU (unchanged) | `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0` |
| `current-v2/report.json` | `82c617917626d88082bdb2cb7f0957db5aa44600184f883f759af5323ae4350d` |
| `notebook-readback-v3/report.json` | `9fd2cd312c03dabb74f56cbc1b94c976cdbe02acd17d0afe94f6f5aba2a90dd6` |
| `notebook-regression/report.json` | `c17784fd10e3817befd8bd0a3dcb8c83859f8ed930d6f683326619f2c4a0e4cd` |
| `components-regression/report.json` | `5bda162e7b38056dcf2b8b013cb0a7650258949e52291fedad7501fdcc4b90b1` |

Retained harness failures are not passes. The first private reproduction copied
an old generated SDK lock and failed before building; the second excluded
build/workspace/lock outputs and reproduced the defect. `current-v1` passed the
new editing assertions, then incorrectly expected OK to reopen a row while
Export still had focus. `current-v2` explicitly taps the row. Its two cold
sessions still used ordinary runner installation; the later readback-guarded
run supplies the stronger cold evidence. No further product fix was needed for
those harness corrections.

The full SDK goal remains active. This fixes one real UI workflow and adds
qualified interaction behavior; it does not complete broader UI/runtime/resource
acceptance, native Windows/Linux/macOS release qualification, production
GitHub/store integration, severe-media recovery, independent trials or physical
performance/storage/power qualification. Existing downloadable bundles predate
this source candidate.

Final read-only audit checks all 40 runtime results, 118 frame pairs, identical
Notebook artifacts across both harness revisions, both guarded cold readbacks
and exact document/export bytes. It passes in `build/sdk-text-field/audit.json`.
The first audit assumed the older Notebook harness wrote release PNGs; it writes
release PPMs. The corrected audit decodes those original frames and passes.
Final checks also pass: 131 local documentation targets, `git diff --check` and
`make check-public` (1,085 public files). No new firmware build or physical test
was needed for these app-linked header/example changes.

The read-only evidence snapshot contains 1,109 indexed files (71,895,737 bytes) under `build/sdk-text-field/evidence/`; index SHA-256
`468e7a438bada85f782768cfd2db3968e27ab09dd9930017bae330a04c431efc`. Every indexed size/hash and read-only mode passes, and the frozen SDK source identity matches the qualified source. The copied ledger predates this index annotation. All launched jobs have terminal results.


## HTTPS terminal delivery, late fragments and cached images — 2026-09-14

This R4 follow-on fixes a reproduced companion/session bug. `Bridge._finish`
cleared the active request as soon as DONE or ERROR was accepted by the USB
channel. The app could still have a CANCEL or URL fragment in flight before
observing that terminal result. The next bridge step treated the valid trailing
fragment as an unknown request and closed the entire session. Two new host
cases failed with `HTTPS request ID changed`; the actual signed ARM Gallery
reproduced the early-grant-refusal/queued-URL boundary with the same exception.
Those before-fix failures are retained, not counted as passes.

The bridge now remembers the most recently completed ID while idle and drains
its well-formed URL/header/upload/cancellation fragments without producing a
second result or starting network work. The original terminal result remains
authoritative. A newer BEGIN ends that drain window; foreign/reused IDs, unknown
kinds and malformed wire shapes still fail. The change also validates the
shape of discarded fragments while a terminal frame is waiting to be sent.
It does not replay requests, widen host grants or change protocol IDs, app/USB
firmware, signing policy or Gallery's code/data format. See the
[companion contract](../sdk/CHANNEL.md).

The new `vm/test-sdk-https-terminal.py` uses the real Link Gallery package,
normal Goodix/keypad controls and OS-owned consent, public model USB channel,
production `Bridge`/HTTPS worker and controlled localhost TLS service. A test
transport adapter delays reading/acknowledging a real app fragment until its
terminal frame has been accepted over USB. It never invents or modifies frames, and preserves FIFO order within each
direction. This schedules full-duplex transport latency deterministically
without writing guest state or invoking app functions.

Validation on macOS 26.6.2 ARM64:

- **91 unique host cases passed**, 14.12 s, in `test_sdk_https_bridge.py`,
  `test_sdk_https_worker.py`, `test_sdk_channel_device.py` and
  `test_sdk_companion_emulator.py`. Cases cover trailing fragments and the next
  valid request, no extra network operation, malformed/foreign/reused IDs,
  unknown kinds, new-active-request rejection, real TLS/streamed uploads,
  cancellation/deadlines, queue backpressure and companion cleanup. A separate
  collection check confirms 91 distinct node IDs.
- **Six ARM phases**, `current-v1`, pass in debug/release. Each profile preserves
  its cached image through two explicit grant refusals with no HTTP attempt,
  then downloads only after explicit disconnect and corrected host grant.
  HTTP 404 causes the app to cancel; DONE is queued before that CANCEL reaches
  the bridge. The session survives and an explicit Refresh succeeds using the
  same paired session. Both profiles then cold-reopen the resulting exact cache.
- **Four additional ARM phases**, `user-cancel-v2`, exercise normal Back during
  an active valid image download, after the bridge has sent **4,400 bytes** in
  each profile. The bridge continues to send the remaining response and DONE
  before receiving the delayed CANCEL. Gallery discards the staged replacement:
  public export and cold reopening both return the original **73,760-byte**
  image, SHA-256 `e3fa70dec8ed992198aa7e929aa4eba5abbccc1b0051d07171cd4d752f9bafee`.
  This run deliberately ends before a replacement refresh could hide an
  unintended cache commit. The preceding run supplies same-session retry proof.
- Both new harness runs use exact signed-package authentication/readback for
  subsequent boots instead of reinstallation. All six exercised boundaries
  across both profiles record `fragment-held`, `terminal-enqueued`, then
  `fragment-acknowledged` in that order. The host checks also confirm no duplicate terminal is sent.
- **Eight existing Gallery ARM regressions** pass with `--full-quota`, including
  real streamed images, USB reset/reconnect, cancellation, malformed checksum,
  cold cache and replacements with the app's committed usage at **32 MiB**.
- **Ten existing C HTTPS ARM regressions** pass: fixed/chunked GET, fixed/chunked
  POST, policy refusal, TLS rejection, timeout, cancellation, truncated response
  and disconnect. Successful downloaded/echoed data and preserved prior caches
  after errors match exact expected bytes.

Total: **28 ARM sessions** and **26 debug/release frame comparisons**. The new
runs contribute 13 pairs and the existing Gallery contributes 13. Comparisons
exclude only the four-pixel progress bar for existing in-flight downloads and
for the new user-cancel terminal frame, because the already-consumed amount can
vary with scheduling. Full originals are retained. Reviewed refusal, HTTP-error,
user-cancel and refreshed-image frames have readable status/actions and preserve
the expected displayed image. These are model/guest tests, not physical USB or
input/timing qualification.

Reproduce from the checkout:

```sh
.venv/bin/python -m pytest -q tests/test_sdk_https_bridge.py tests/test_sdk_https_worker.py tests/test_sdk_channel_device.py tests/test_sdk_companion_emulator.py
.venv/bin/python vm/test-sdk-https-terminal.py --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --output build/sdk-https-terminal/recheck
.venv/bin/python vm/test-sdk-link-gallery.py --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --output build/sdk-https-terminal/gallery-recheck --full-quota
.venv/bin/python vm/test-sdk-https.py --firmware dist/lefony-os-prime-g2-live-heap-vm.elf --output build/sdk-https-terminal/https-recheck
```

The final terminal harness defaults to policy, HTTP-error cancellation,
user-initiated cancellation and cold phases. The qualified first six phases
used the earlier three-phase harness retained as `current-v1/harness.py`; the
four later phases used `--phases user-cancel cold`. Reports and packages are
under `build/sdk-https-terminal/`. Exact identities:

| Artifact | SHA-256 |
| --- | --- |
| SDK executable inputs | `1cc0aa96c400fa06ac1a1cd3d556d5d839fc0bfcf5edff13eec619fa1f600c7b` |
| `sdk/tools/https_bridge.py` | `75673511b3616a3b620f1ba0e788d1afc2cb9abad46fb80436610452353bf16a` |
| Final terminal harness | `5adae9083a93e25b31302ce6c9f5c6e42462cf87a17f54374153377c904d8b72` |
| VM ELF, unchanged | `4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14` |
| Developer QEMU, unchanged | `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0` |
| `current-v1/report.json` | `321568b24e656ae27d89e3a47bc14a2d574ab52a93088a12d80dcbed23ed4b72` |
| `user-cancel-v2/report.json` | `2fe6783089f0a13076fdb77c8c3a28df1120c7a9eb6d821c0ff346e0cbcc81c6` |
| `gallery-regression/report.json` | `b8f690bd5832c7c4cfe7e50d6eed2ca46244d266806c10bc9d852fea7c509727` |
| `https-regression/report.json` | `79bc2f264b6c166588f96ec41c9b3d8a5722869887e46524f2e5379e12785bca` |

The read-only audit verifies all 28 runtime results, all 26 image comparisons,
SDK identities in every retained build record, full-quota reports, ordered
boundary traces and exact new-harness cache bytes. It passes in
`build/sdk-https-terminal/audit.json`. Earlier frozen desktop binaries predate
this fix: a fresh complete supported-host bundle still needs its own validation.
No firmware rebuild was needed for this host-companion change. The full SDK
goal remains active, including supported hosts, production GitHub/store,
broader resources/recovery/lifecycle and independent/physical qualification.

Final Python syntax/help checks, 132 local documentation targets, `git diff --check`
and `make check-public` (1,086 public files) pass. All launched test jobs have
terminal results; no calculator, deployment or release operation was performed.

The read-only snapshot at `build/sdk-https-terminal/evidence/` contains
660 indexed files (40,191,763 bytes); index SHA-256
`45005ac18bb8732f591ce09220adbacede6e63eea21d9fd15f674d7e914334bb`. All indexed hashes, sizes and read-only modes verify,
and the frozen SDK source identity equals the qualified source. The copied
ledger predates this final index annotation.


## Current macOS desktop bundle, UI and companion — 2026-09-14

The current source is now packaged into a fresh local macOS ARM64 desktop SDK.
This closes the preceding checkpoints' macOS binary gap for the Notebook text
field and HTTPS terminal-delivery fixes. The bundle remains an unpublished
`0.2.0-dev` candidate. Windows/Linux, clean-host, production services and physical
qualification are not inferred from these local checks.

No SDK API, app source, firmware, signing policy or storage format changed in
this batch. The new durable work extends the desktop and frozen-companion
qualification harnesses, adds a signed C terminal-delivery conformance case,
and records a current binary/source pair. `vm/test-sdk-desktop.py` now verifies
its SDK identity, exercises actual touch caret placement/selection/cancellation,
and reads the saved Notebook archive. `vm/test-sdk-frozen-companion.py` adds a
`terminal` mode and observes child processes across multiple requests.

Validation on macOS 26.6.2 ARM64, Python 3.14.6 and GCC 16.2.0:

- **Eight offline template journeys pass** after relocation into a path with
  spaces and Unicode: Basic, Pocket Lab, Forms/Tables, Graph Explorer, Reference
  Cards, C Main, Notebook and UI Gallery. SDK commands have network, Homebrew
  and checkout access denied. Installed workspaces, clone/export/restore,
  source formats 1/2, bundled GDB/pipe debugging and ARM preview/layout inspection
  pass. Optional external CMake passes separately with Python discovery disabled;
  CMake itself runs outside that denied-access sandbox.
- **Two additional frozen Notebook previews pass.** Normal Goodix/keypad input
  inserts within `2+3*4`, replaces a selection, cancels three pointer gestures,
  handles keyboard input during a touch, saves and exports `2+9*24`. The saved
  document and export (`218`) match exact expected bytes. A subsequent preview
  restores the retained snapshot into fresh synthetic media and reopens the same
  expression. Both verified archives have hash
  `7e713b5c9e07480e207b3bdc9a96612313ffbee7f01ed295e4fa3cf6c601a3dc`.
  Input fixtures remain unchanged. The two final frames are identical and were
  visually reviewed; the UI Gallery frame was also reviewed. Total preview
  observations were 22.66 and 12.65 seconds, including these scenarios; these
  measurements do not establish a supported-host latency budget.
- **Eleven frozen companion ARM/model-USB cases pass**: terminal, GET, chunked
  GET, POST, chunked POST, policy refusal, TLS rejection, timeout, cancellation,
  truncated response and host disconnect. The actual relocated CLI builds the
  signed guest and runs its companion/worker with Homebrew and checkout denied.
  Exact cached bytes and removal of staged downloads are checked after every
  case; observed child processes stop after companion exit.
- The new C case deliberately delivers four well-formed URL/header/upload/CANCEL
  fragments after consuming ERROR, then repeats after DONE. This exercises the
  frozen host's late-delivery branch without a mocked bridge or worker. One
  pairing handles policy refusal for ID 1 and successful IDs 2 and 3, with exactly
  **two HTTP GETs**, one error and two completions. Final cached data is exactly
  131,073 bytes. The companion exits normally after 18.3 seconds and all three
  observed child processes have stopped. This conformance ordering is not a
  physical latency measurement or a recommendation for app behavior; the earlier
  Gallery harness retains the actual in-flight-fragment/cache-boundary evidence.
- **Eight frozen native-TLS cases pass**, including explicit CA isolation,
  hostname rejection, a bounded stalled handshake, Ctrl-C cleanup and a read-only
  unauthenticated HEAD to `https://github.com` using native trust (HTTP 200).
  The controlled fixture logs a peer-reset traceback during an intentional TLS
  rejection; the expected refusal and stopped-worker assertions pass. This is
  not GitHub OAuth or production-store qualification.
- **Fifteen native-Keychain account steps pass** against a controlled local HTTPS
  service: login, owned-app listing, origin isolation, account replacement,
  remote revocation, explicit logout and cleanup. The final empty-state check
  verifies removal of the temporary credentials. Existing user credentials are
  not replaced; the harness refuses a preexisting fixture-origin credential.
- **91 focused host tests pass**, 13.65 seconds, covering desktop packaging,
  Pillow source inputs, UI workflow, HTTPS bridge and companion transport.
- The new **426-file source kit** is byte-for-byte reproducible in two builds.
  Every manifest entry and member is verified, and its executable SDK identity
  matches the frozen bundle. The external source kit builds Notebook with its
  bundled newlib, Unicode project paths and ASCII host locale/Python UTF-8 mode
  disabled. Its raw package matches the frozen ARM-preview package:
  `d01def4746b6a2dcad163b7886bf4b2d0c103e4150de81d9fc2207a71207640b`.

Exact reports and inputs live under `build/sdk-desktop-current/`:

| Artifact/report | SHA-256 |
| --- | --- |
| Desktop archive | `8e02e35a24f196160bd4ec6f46c41c6e652517136541bf2a57bfc769fa266f67` |
| Source kit with newlib | `51b730e1bddd8a8e0f4759cec9035716b5d301df0e8f6c6e6e2de486b564944e` |
| Offline templates and Notebook | `26421aa20c1e5a1197f580f7af3de36f60c9433c9636881bc09d4e88c9491c13` |
| Frozen companion | `fe05cc87349a54d9262905b9528d7b74903ceb373dc648f5b049eb0ee9cdd0c1` |
| Native TLS | `ff601c2bfc6f1dc25d9e83f8b590862ad0729ec4ef4d134048d1780f12d152e5` |
| Native Keychain | `49a11d7c555ada3b7a213de3f38c6dd4c3a223575f45451940c623c220d957fe` |
| Source-kit verification | `8a30d886c9835c84ddda76f6909bee20a3d9e60929d45dd1402ccfbf2e80c5c7` |

SDK executable identity:
`1cc0aa96c400fa06ac1a1cd3d556d5d839fc0bfcf5edff13eec619fa1f600c7b`.
VM ELF remains
`4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14`.
Neutral-path QEMU input remains
`752d0fe63fdb4501750b22b3ecf2cbe0bf4121eee95c3bafe7c936c109e132de`;
the packaged executable remains
`c6e5e83b8e398ebca70fc050ef2675f69321ad57953f43c377ddd67461f90ab2`.
The verified source-material manifest is unchanged
(`dc63dc513f8a06f30573d5bd86319291055fe2eacd3ff01297be580cbbce4b41`).
The Pillow native records are structurally identical to the preceding candidate;
their serialized hash differs only because object-key ordering changed. The
original upstream wheel build still has not been reproduced. The exact retained
GDB build recipe was restored to its build-input directory and matched its
candidate hash; no compiler/debugger/source pin changed.

Three older extracted SDK copies were byte-verified against their retained
archives before removal, freeing approximately 2 GiB for this build. Detailed
cleanup receipts remain beside those archives. No source archive or prior
qualification evidence was deleted. The binary and source-kit documentation
precede this qualification annotation; their executable inputs match current
source. No calculator operation, deployment, publication or Git push occurred.
The full SDK goal remains active, including production GitHub/store, remaining
hosts, broader resource/recovery/lifecycle coverage, independent trials and
physical performance/storage/power qualification.


The same bundle also passes **seven frozen store-client deadline cases**: HTTP
error, stalled headers, slow byte stream, stalled TLS, Ctrl-C, truncated JSON and
redirect refusal. Headers/drip/TLS terminate in 20.20/20.20/20.22 seconds; Ctrl-C
completes in 0.33 seconds. These controlled requests issue no accounts and save
no credentials. Report SHA-256:
`2226cdddb1115f7b37acf266fe9e571b00291347cffe8bb4bbb8b2387aeb5091`.

Final syntax/whitespace checks, **138 local documentation targets** and
`make check-public` (**1,087 files**) pass. Every launched packaging/test job has
reached a collected terminal result. No full host-suite or firmware rebuild is
claimed for this packaging and qualification-harness batch.

The final read-only audit verifies all five report groups against the same
bundle, all eleven ARM results and cache bytes, both Notebook snapshots/frames,
the source-kit identity and every desktop archive entry against the tested
extraction (723,055,088 regular-file bytes). It passes in
`build/sdk-desktop-current/audit.json`. No input changed during qualification.

The read-only evidence snapshot retains 522 indexed files (202,233,776 bytes) under `build/sdk-desktop-current/evidence/`. Index SHA-256: `46de0a981a5a4246695f7942bae86c0be840246a59ad60aeb22e77ef3b9cb3df`. All indexed hashes, sizes and read-only file modes verify, and its SDK identity matches the tested bundle. The copied ledger precedes this index annotation. The SDK goal remains active.


## Frozen SDK publication, native credentials and accepted download — 2026-09-14

The current macOS desktop bundle now completes folder publication through its
actual frozen executable against the local website's production handlers. The
previous publication journey called the Python CLI in-process with a memory
credential backend; the new mode exercises the packaged process, native Keychain,
SDK authorization/session endpoints and signed accepted download together.
It uses verified local TLS and isolated Miniflare D1/R2. The website, SDK product
code and firmware are unchanged; durable changes are the two qualification
harnesses and documentation. The website's `docs/SDK-FROZEN-PUBLICATION.md`
describes the optional bundle argument and reproduction command.

The test relocates the bundle and fixture project outside both repositories.
Frozen SDK commands have Homebrew and both checkout reads denied, while the
Node/Python controllers retain access to operate the synthetic service and
inspect evidence. Three logins switch account 1 → account 2 → account 1 through
real authorization, decision and session handlers. Synthetic existing browser
sessions approve the displayed SDK codes; GitHub OAuth and browser interaction
are outside this test. SDK tokens are generated by the actual CLI and stored in
native Keychain, with no injected SDK credential backend or preseeded SDK token.

Final validation:

- **37 frozen CLI steps pass.** Folder icons/screenshots and source snapshots,
  first publication, version update, account separation, website publication,
  conflict review/merge, metadata-only edits, withdrawal and republication all
  use the actual handlers. Three committed chunk acknowledgements and three
  listing acknowledgements are dropped; status/resume resolves saved operations
  without replacing their immutable bytes or reverting newer listing state.
- Four exact release snapshots each pass two normal keypad/Goodix ARM scenarios
  before upload. The submitted source/package/test/media hashes are verified,
  and deliberate private-file/project-path sentinels are absent from uploads.
  Versions 1.0.0, 1.1.0 and 1.2.0 become withdrawn; 1.3.0 remains published even
  after replaying an older withdrawal receipt.
- The exact signed 1.3.0 download passes frozen SDK inspection and normal signed
  installation/launch on the bundled ARM VM. The local store uses only the
  explicitly public emulator fixture signing key, already trusted by that VM.
  This does not alter a release trust root. The unsigned downloaded payload
  equals its ARM-tested submission. The accepted frame was visually reviewed.
  The frozen journey therefore contributes **nine ARM sessions**, eight input
  scenarios and one signed downloaded-package launch.
- Two actual scheduled-handler runs remove **30 temporary objects**, preserving
  **19 accepted artifacts** unchanged. Reserved capacity falls from **155,757 to
  62,601 bytes**; historical images and the current signed download still match.
  This is managed-stage cleanup, not legacy-inventory migration qualification.
- Logout leaves zero active fixture SDK sessions. Native cleanup verifies removal
  of the temporary Keychain credential and fixture-specific host project/operation
  records, retaining their non-secret receipts. Preexisting fixture-origin
  credentials or records cause refusal; unrelated native state is preserved.
- The default source-mode regression also passes **28 CLI steps/eight ARM
  scenarios**, retaining its separate API 11 firmware and developer QEMU. Across
  both final runs there are 17 ARM sessions, not physical-device tests.
- Website build and lint, Python syntax/help, both repositories' whitespace
  checks and the OS public boundary pass. No production Worker source, migration
  or deployment configuration changed; all 34 recorded backend/config inputs
  match the starting inventory. No broad backend-suite or firmware rebuild is
  claimed for these harness changes.

Exact reports are in the website's ignored `.local/sdk-frozen-publication-v4/`
and `.local/sdk-frozen-publication-source-v1/`; OS-side logs and input snapshots
are in `build/sdk-frozen-publication/`:

| Artifact/report | SHA-256 |
| --- | --- |
| Frozen website report | `994525bb341f66230d8b66018854bd481cb088ba00c222fa0a842bb2141b9b4f` |
| Frozen CLI/ARM report | `bff0318e859db84359ecccde2c6ca152be02002f7a91c8b7da7aefdcd20f1276` |
| Source website report | `973ec5e3f854d3c18d7a651b045e6d56bb09f363ab9b94442ab86c34d1aead75` |
| Source CLI/ARM report | `ab29d8a50d530023a66f3cda9d5af996b3f3d1f76ca16de923647a9042762393` |
| Accepted signed 1.3.0 package | `1b1d4adfb454f316188a4ea2a0346c7062d689f40e41678e935f068a847535fe` |

The unchanged desktop archive is
`8e02e35a24f196160bd4ec6f46c41c6e652517136541bf2a57bfc769fa266f67`,
and SDK executable identity is
`1cc0aa96c400fa06ac1a1cd3d556d5d839fc0bfcf5edff13eec619fa1f600c7b`.
Frozen VM firmware is
`4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14`;
packaged QEMU is
`c6e5e83b8e398ebca70fc050ef2675f69321ad57953f43c377ddd67461f90ab2`.

Three earlier attempts are retained as failures: the Node copy initially rewrote
relative symlinks to the denied original bundle, the test service lacked synthetic
OAuth configuration required by authorization, and the controller expected JSON
from login's human-readable confirmation. The final harness preserves symlinks,
configures only the local fixture and verifies login with `whoami`. The latter
failure did issue a fixture session; its native logout/cleanup checks passed.
The first two did not create a credential. No SDK or website production defect
was found or concealed by these harness corrections.

The full SDK goal remains active. Real GitHub OAuth/production-store journeys,
complete browser parity, native Windows/Linux and clean-host qualification,
production capacity/inventory cutover, broader resource/recovery/lifecycle
coverage, independent developers and physical acceptance remain open. No
calculator operation, production publication, deployment, commit or push occurred.

The final read-only audit passes all 17 ARM results, submitted snapshot/file
hashes, accepted signature/payload identity, report bindings and native cleanup.
It is retained at `build/sdk-frozen-publication/audit.json`. All 130 local
documentation targets, public/ignored-output boundaries and whitespace checks
pass. Every launched job has a collected terminal result.


The read-only publication evidence snapshot retains 1,461 files (28,115,889 bytes) under `build/sdk-frozen-publication/evidence/`. Index SHA-256: `6e109d59d0adda406a97fb8d8710ceea6c0b8653da0d09360c45c99c58d6e744`. All indexed hashes, lengths and read-only modes were reverified on 2026-09-14. The copied ledger predates this index annotation.


## Buffered C file lifecycle qualification — 2026-09-14

The selected C file profile now has four additional ordinary-main workflows in
`tests/native/sdk_c_profile.c`, driven by `vm/test-sdk-c-profile.py`. They use
real newlib buffering, normal public file services and exact USB exports; there
are no replacement syscalls, private filesystem edits or synthetic handle seeds
in these cases. SDK executable code, library pins and firmware are unchanged.
The [C library guide](../sdk/C-LIBRARY.md) documents the exercised stream rules.

- `stdio-update` creates 262,175 patterned bytes with a 3,073-byte stdio buffer,
  edits two spans crossing storage-chunk boundaries, switches between reads and
  writes through positioning, commits with `fflush`/`fsync`, restores a saved
  position and verifies every byte on the existing stream and after reopening.
- `stdio-append` reads an append/update stream, seeks before writing, retains
  append behavior through two durable syncs, writes after reaching EOF and
  verifies the complete result. A newly created append stream is sought beyond
  EOF before writing; it contains only the appended bytes, with no seek hole.
- `stdio-snapshots` holds a partly read large file across replacement, durable
  sync and rename, then creates/deletes another file under the original name.
  The old reader still returns every original byte, and the newer reader and
  renamed path return the committed replacement.
- `stdio-position` writes a 262,147-byte zero-filled gap, exercises EOF pushback,
  saved-position restoration and relative/end seeks, and verifies the complete
  file. Positioning discards pushed-back text without modifying file bytes.

All four cases pass initial execution and a cold phase. Before cold execution,
the SDK exports and verifies the previously committed bytes. After execution it
exports every expected file again, verifies exact contents and directory entries,
and checks normal OS responsiveness. Both debug and optimized release builds
pass on two retained firmware candidates: **16 current-VM phases plus 16 earlier
media-I/O phases, 32 ARM phases total**. Within each build profile, identical app
packages were used across both firmware candidates.

The first run used the retained media-I/O VM named by the earlier file-profile
work. The same full matrix was then run on the current VM, byte-identical to the
firmware included in the current desktop SDK. These runs use the source CLI and
developer QEMU; they do not claim a new frozen-host or physical qualification.
No test case failed and no product defect was found in this matrix.

Validation on macOS 26.6.2 ARM64 (25G83), Python 3.14.6 and GCC 16.2.0:

- Four ARM reports pass, eight phases each, with exact retained app sources,
  manifests, locks, ELF/map files, exported bytes and runtime reports.
- `pytest -q tests/test_sdk_runtime.py tests/test_sdk_c.py
  tests/test_app_file_session.py`: **9 passed in 19.71 seconds**.
- Python syntax/help, whitespace and `make check-public` (**1,087 files**) pass.
  No full host-suite rerun or firmware rebuild is claimed for these fixture/docs
  changes. All test processes reached collected successful terminal results.

Reproduce the current debug matrix from the repository root (use a fresh output
path; add `--profile release` for the release matrix):

```sh
.venv/bin/python vm/test-sdk-c-profile.py \
  --firmware dist/lefony-os-prime-g2-vm-native.elf \
  --output build/sdk-stdio-lifecycle/current-debug \
  --cases stdio-update stdio-append stdio-snapshots stdio-position --keep-going
```

The exact reports and audit are retained under `build/sdk-stdio-lifecycle/`:

| Artifact/report | SHA-256 |
| --- | --- |
| Current VM / debug report | `b1d91c9f48bbfd68f27c29eb02aa42568c488eb745d78cb69edaa54a488677a0` |
| Current VM / release report | `c6002376a06da7caff242e7d011d9c3374c8854f674798ad366f260b464b177f` |
| Earlier media-I/O VM / debug report | `d5f40db74d1805bde8360bd211d58089259b590aef4efb8528326852d699c4b6` |
| Earlier media-I/O VM / release report | `c04f991f8568549716c1621d84e6917047b3a826f7eed27c7df747ff4df61225` |
| Audit report | `5205ecdaaf37acad06faa0c82f19ad3a628b4516f8b13b873a777a732b279c1a` |

SDK executable identity remains `1cc0aa96c400fa06ac1a1cd3d556d5d839fc0bfcf5edff13eec619fa1f600c7b`.
Current VM: `4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14`.
Earlier media-I/O VM: `6caef5c84255d2f28e29837e865b1d63dc94cb240d8aba977897b13eebd74717`.
Developer QEMU: `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.

The final audit verifies all 32 phase results, cold pre-run exports, source/lock
identities, library identity, output lengths/digests and public fixture signatures.
Its first attempt incorrectly compared unsigned build packages directly with
runtime hashes of signed envelopes. The corrected audit reconstructs the
runner's deterministic public-fixture envelope, verifies its signature and inner
payload, then matches the runtime hash. Both audit versions/logs are retained;
this was an audit assertion error, not an app or runtime failure.

This closes the selected buffered-stream lifecycle coverage above, not the full
C library or SDK 1.0. Broader malformed-input/resource/lifecycle coverage, severe
media recovery, native supported-host bundles, real GitHub/production-store,
independent developer trials and physical input/performance/storage/power remain
open. No calculator operation, deployment, publication, commit or push occurred.
The full SDK goal remains active.

Final checks verify 136 local documentation targets. The read-only evidence snapshot retains 269 indexed files (41,251,006 bytes) under `build/sdk-stdio-lifecycle/evidence/`. Index SHA-256: `aa9b191798a0e08655ac4f7000f079dd5592eaed1843a99a7e10089b6c876e9d`. Every indexed hash, length and read-only mode verifies; the copied ledger predates this annotation.

## Wrapping paragraphs and readable document recovery — 2026-09-14

The app-linked C++ UI now provides `Widgets::paragraph` and an allocation-free
`ParagraphLayout` iterator. They wrap up to 1,024 UTF-8 bytes using the four
existing fixed-cell OS fonts, preserve LF/CRLF and blank lines, and split long
words between complete base/combining-mark cells. The widget reports required
height and clipping, supports disabled/invalid colors and existing source/layout
inspection, and validates invisible text before changing pixels. It chunks long
lines across the existing typography request limit without splitting a cell.
The [UI guide](../sdk/UI.md#wrapping-paragraphs) states encoding, geometry and
error limits; full Unicode word breaking and arbitrary fonts are not claimed.

Notebook 0.6.2 uses this component for its empty state and unreadable-document
recovery instructions. The complete export/restore guidance fits on screen;
New and Options remain disabled and the original document remains unchanged.
UI Gallery 0.1.2 adds a normal-input Wrapped text screen with accented text,
long words, explicit blank lines and normal/disabled/invalid states. No firmware,
service, package schema, storage layout, library pin or trust root changed.

Source validation on the existing macOS ARM64 toolchain:

- **23 host tests pass**, including the sanitizer-backed paragraph iterator and
  5,000 independently computed greedy word-layout vectors. The focused UI suite
  also passed separately before integration (9 tests).
- **30 ARM paint sessions pass** across debug/release: the 12 new paragraph
  cases and three existing-control regressions, with seven viewport clips each
  (**210 frames**). Cases include all fonts, narrow/empty boxes, long lines,
  invalid gap, malformed UTF-8, unsupported offscreen glyphs and an oversized
  combining cell. Rejected input independently preserves the preexisting frame.
- **Two Gallery ARM sessions pass**, with **52 frames** covering normal keypad
  and Goodix input, navigation, menus, dialogs, fonts, wrapping and existing
  interaction states. All **131 component/Gallery debug-release frame pairs**
  match. The wrapping screen and representative clipped/font frames were
  visually reviewed.
- **24 Notebook ARM phases pass**, including edit/save/cold reopen, old and
  malformed documents, validation, clipboard and preferences. Exact exported
  bytes remain correct; all **34 debug-release frame pairs** match. The recovery
  screen was visually reviewed with the complete instructions visible.
- Syntax/whitespace and `make check-public` pass (**1,089 files**). The first
  paint fixture build failed on misleading-indentation warnings in new test
  lines; those statements were separated and the full selected matrix rerun.
  The failed fixture/log is retained. No product failure was concealed.

The 56 ARM sessions above use the source CLI and developer QEMU; they do not
qualify a new desktop download. Fresh bundle/source-kit checks are recorded
below when complete. No firmware rebuild or full host-suite rerun is claimed.

| Input/report | SHA-256 |
| --- | --- |
| SDK executable identity | `779980cf5ffa47e6e97e043eb4f724b8f8de828340e8ac764ec012bad7b30a25` |
| Component/Gallery report | `43420e53b2a7e59e9bc4583148e9818f66476b11965c239d5ea42f87fb66e017` |
| Notebook report | `ca510267e5ac20279d7ce1dd93434430b16955d7491fe1ceb93e77a2a9fc40f5` |
| VM firmware | `4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14` |
| Developer QEMU | `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0` |

Reports and retained fixtures are under `build/sdk-paragraph/`. This completes
the bounded paragraph component and its application integration; broader SDK
resource/recovery/lifecycle coverage, supported native hosts, real GitHub/store,
independent developer trials and physical qualification remain open. No
calculator operation, deployment, publication, commit or push occurred.

The same executable inputs now have a fresh local **macOS ARM64 desktop bundle**.
All eight templates build, run their tests and export source through its actual
frozen executable after relocation outside the checkout. Network and
checkout/Homebrew access are denied to the SDK. GDB source debugging, the
separate external CMake integration, Notebook touch edit/save/cold preview and
new Notebook/Gallery paragraph previews pass. The two paragraph frames match
the source ARM frames exactly; the frozen recovery checkpoint retains the
original future-format document bytes. Both frozen frames were visually reviewed.
The SDK copies contain the exact current application sources and paragraph header.

A new standalone source kit includes the verified newlib sysroot and produces
identical archives on two builds. All **427 listed files** verify after extraction
outside the checkout. Its actual CLI passes seeded and source-edited Notebook
previews, preserving the document, nested attachment and empty directory and
excluding preview data from source publication. The source edit changes the
title and package while keeping the rest of the rendered screen identical.

| Packaged artifact/report | SHA-256 |
| --- | --- |
| macOS desktop archive | `b456503171b9c0af67b6c56d099f537bddf19b1976aba835d691ca3b6a975955` |
| Frozen offline report | `a5b6a0317f12c1f71a57002e76a423805898cf334e5e0e47213aa5dfbee7904e` |
| Reproducible source kit | `6114d897664ae31d75cb9bebcdff2cd3258aaa9441f264bae929eb222a726306` |
| Relocated source-preview report | `ac439a500e534bd488dbd32503070e4313dc254c80ce933efaef774182626c04` |

The final audit verifies all 56 source ARM results, 165 debug/release frame pairs,
source identities, frozen/source paragraph pixels, saved recovery bytes and
723,091,888 regular-file bytes in the desktop archive against the tested folder.
It is retained at `build/sdk-paragraph/audit.json`. The previous desktop
candidate's TLS/companion/account/publication reports remain attached to that
older artifact; they were not rerun for this UI-only candidate. Native binaries,
firmware, dependency pins and verified source-material inputs are unchanged.
The bundle/source-kit documentation precedes this final qualification annotation.
Clean hosts, production publication, remaining host platforms and physical
acceptance are still open. All launched jobs reached collected terminal results;
the full SDK goal remains active.

Final checks pass all 143 local documentation targets and the public boundary
(1,089 files). The read-only snapshot at `build/sdk-paragraph/evidence/` retains
1,176 indexed files (89,414,139 bytes), with every hash, length and read-only mode
verified. Index SHA-256:
`02ff96a92ede2c44d1af251b158e0ca3b96c897f0b195f234768519422abf6d4`.
The copied ledger predates this snapshot annotation.

## Linux x86-64 compiler build infrastructure — 2026-09-14

`scripts/build_sdk_linux_toolchain.py` now builds the existing GCC 16.2.0 and
binutils 2.47 pins into a dedicated output directory on Linux x86-64. It validates
the complete source hashes before extraction/configuration, rejects oversized
or malformed inputs, records the recipe and command logs, retains notices/source
archives and hashes the installed tree. Its final smoke step compiles C11 and
C++17 with the SDK's Cortex-A7 hard-float flags, relocatably links the objects
with the installed libgcc and checks the ARM ELF output. This is a compiler
candidate, not a complete Linux SDK or a new compiler-version decision.

The new `scripts/sdk-linux/Dockerfile` provides Ubuntu 24.04 build dependencies
from an explicitly supplied base digest. Build outputs can live in a dedicated
mounted folder instead of consuming the container image's layers. The source
kit includes both recipe files, and the [host guide](../sdk/HOSTS.md) describes
native and emulated-container execution records. The existing hosted-validator
recipe remains historical; this work does not restore server-side app builds.

Initial validation and current build state:

- **36 host tests pass**, including seven compiler input/pin tests and the
  existing desktop packaging matrix. Wrong hashes, oversized/non-file inputs,
  unexpected archive roots and traversal are rejected; safe extraction does
  not execute a configure script.
- Source-kit generation passes and includes both new files byte-for-byte.
  That inclusion check omits newlib and is not a full runtime-kit qualification.
  Python syntax/help, whitespace and the public source boundary pass.
- The local ARM64 Linux VM successfully executes the pinned Ubuntu x86-64 base
  using host emulation. Base manifest:
  `sha256:a61567bd31828687156d735ea8eb01ba4e37636e225dd6a48ba94136a70d9d61`.
  The dependency image builds successfully; its package/compiler/Python inventory
  is retained under `build/sdk-linux-host/`.
- A real compiler build has started using the previously verified local source
  archives, with network disabled, a read-only container root, two CPUs and a
  4 GiB memory limit. Only dedicated input/work directories are mounted. Its
  explicit record is `emulated-container`. The image, container ID, input hashes,
  logs and eventual terminal state are in `compiler-job.json` and
  `compiler-v1.log`; no successful compiler result is claimed yet.

Matching Linux QEMU/GDB, native/Python dependency source correspondence, the full
relocated SDK/companion and Secret Service journeys, clean native hosts and
physical USB remain outstanding. The SDK executable identity and firmware are
unchanged. No calculator operation, deployment, publication, commit or push
occurred. The full SDK goal remains active.

The first two emulated compiler attempts have now reached **failed terminal
states**, with no compiler candidate produced. The two-job build failed when
Ubuntu's host GCC segfaulted compiling binutils `libiberty/xmalloc.c`. The exact
compile command then passed ten isolated repetitions. A fresh one-job attempt
failed earlier when host `cc1` segfaulted during a configure check for the size
of `long long`. Neither container reported an OOM kill. Both stopped containers
were removed after their states and logs were retained; neither build was
silently restarted or marked successful.

The local VM's x86-64 interpreter is QEMU user-mode **7.0.0**, not Rosetta. A
separate full dependency-image build also failed when Python 3.12 segfaulted in
a package configuration command. These observations suggest a host-emulation
issue, but the root cause is not established. The workspace filesystem is case
insensitive; a complete archive-name scan found no case collisions in either
pinned compiler source archive. No VM settings or global binary-format handlers
were changed to work around these failures.

The Linux dependency recipe now includes QEMU's required Python setuptools and
wheel packages. A subsequent image built successfully from the already retained
dependency image, adding those packages with the same recipe. Its immutable image
ID is `sha256:eb9f962e2c6e569411868a01e0517d929df3404e50f63a6b4ee8876fd2f6fa0f`.
The original image remains
`sha256:74f19b263ad5b8c4bfab7c4bdd80392e9542c5883c4cdfd3b1446c2751c14e68`.
A separate local copy of the pinned QEMU checkout, cached subprojects and public
Prime patches is prepared, with an input manifest; QEMU compilation was not
started in the failing host environment. This is preparation, not Linux QEMU or
SDK qualification.

The compiler recipe now retains structured per-command passed/failed/timed-out
outcomes and elapsed times. **39 host tests pass**, including actual successful,
exit-7 and timed-out child processes that verify their logs and terminal records.
The two failed builds used the preceding recipe; their original copies remain
unchanged. Current source and exact outcomes are retained under
`build/sdk-linux-host/`, including `outcomes.json`, both `compiler-job*.json`,
build/configure logs and the isolated compiler diagnostic. All launched processes
have collected terminal results. Native-host qualification and the broader SDK
goal remain open.

Final checks pass 83 local documentation targets and the public boundary
(1,092 files). The read-only diagnostic snapshot at `build/sdk-linux-host/evidence/`
contains 55 indexed files (1,556,556 bytes); every hash, length and mode verifies.
Index SHA-256:
`0a933e119b60dc09b38a02267ba97047fbf845e1690feb6333f250acd37aba3f`.
The copied ledger predates this annotation. Failed scratch trees and exact
compiler archives remain available separately; no Linux compiler/bundle success
is asserted by this evidence snapshot.

## Frozen private signing, installation and key recovery — 2026-09-14

The private-install guide exposed a desktop workflow gap: it required invoking
`signing.py` with an external Python interpreter. `lefony-sdk keys generate` and
`lefony-sdk sign` now provide those local operations through both source and frozen
entry points. Frozen commands use the bundled OpenSSL. Generation reserves new
destinations exclusively, never replaces existing keys or symlinks and creates
Unix private files with mode 0600. Signing accepts a bounded unsigned package,
verifies the result and requires a separate new destination. Neither operation
opens USB or the store. Interrupted generation can leave reserved files, which
are documented rather than overwritten by an automatic retry.

`install` now verifies the complete signature before opening any USB transport;
the ordinary client repeats its verification before upload and readback.
Explicit `keys --emulator-usb PATH OPERATION` and `install ... --emulator-usb PATH`
support the same request-family allowlists as their physical transports. The
adapter borrows an already enumerated exclusive QEMU socket, never discovers a
calculator, never falls back to physical USB and exposes no firmware operations.
Existing source-level tests retain their ordinary transport injection. App ABI,
firmware, registry/storage formats and production trust roots are unchanged.

### Actual frozen workflow

`vm/test-sdk-frozen-keys.py` relocates the complete macOS ARM64 bundle outside the
checkout into a path with spaces and an accented character. Every build, new key,
signature, enrollment/revocation, install and repair runs through its actual
executable. Outbound IP networking, Homebrew and checkout access are denied. The
harness creates temporary independent identities only for synthetic media, sends
normal keypad edges for the OS consent screen, and independently reads committed
files/roots. It does not replace the frozen CLI's USB implementation in process.

**29 frozen CLI steps / four ARM sessions pass**, covering:

- Local generation of two identities, refusal to overwrite one, two external
  Notebook packages and verified signatures through bundled OpenSSL.
- Canceled enrollment leaves no key; approved enrollment permits signed install.
  Normal Notebook keypad/Goodix editing saves and exports the exact expression.
- An unrelated enrolled signer cannot perform an ordinary takeover. Revocation
  blocks launch while catalog/data export remain available. Removal refuses a
  key still needed by the installed package.
- Canceled lost-key recovery preserves data. Approved recovery binds the new
  signer and package, retains the pending pair, then lets Notebook accept the
  compatible upgrade. Only then can the unused old key be removed. Canceling
  revocation of the replacement key leaves it active.
- Cold launch retains trust, document and export. A deliberately corrupt readable
  registry requires a verified exact backup before repair; cancellation and
  approval both preserve that backup. Repair restores the explicit public key.
- Another cold launch retains the document/export. Independent production-
  filesystem inspection finds the same complete package/data root, generation,
  ownership and version history before corruption and after repair.

The enrollment, lost-key recovery and registry-repair frames were visually
reviewed. Full fingerprints/package/backup hashes and approval/cancel labels fit.
Temporary private keys are removed with the harness workspace; reports retain
public keys, signed packages, synthetic media and exact saved/exported bytes.

### Validation and exact candidate

The targeted signing, key transport, emulator/companion and desktop-packaging
matrix passes **104 host tests**. It covers immutable identity destinations,
invalid/oversized packages, pre-USB verification, request restrictions and lack
of physical fallback. Python syntax, whitespace and the public boundary pass
(1,094 files). No firmware rebuild or physical operation was needed.

The initial frozen run passed generation/signing but failed its first model
connection: its blanket sandbox network denial also blocked AF_UNIX. The retained
`frozen-v1` report/log and original harness record that failed attempt. The final
harness uses the existing desktop test's outbound-IP denial, retaining local
model IPC. The frozen executable did not change between those two attempts.

| Artifact/input | SHA-256 |
| --- | --- |
| SDK executable identity | `8a950a25a5d6856e0f3d9ca4ddf133ead4df1b29beebe54aaf7e76f39607c111` |
| macOS desktop archive | `49c5a1f3af7d072cc04ec08064dd170fd416f50b2ed1cdc8276f75f085a59d95` |
| Frozen private-install report | `c0c3ba9f57f3d9376d4cf2d3b7fc775ccc772536dc4c39196cebf3f292cbe272` |
| VM firmware | `4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14` |
| Bundled QEMU | `c6e5e83b8e398ebca70fc050ef2675f69321ad57953f43c377ddd67461f90ab2` |

Artifacts and reports are under `build/sdk-private-desktop/`. The full host suite
and the regular frozen offline/template regression were started separately;
their terminal outcomes are recorded below when collected. Earlier HTTPS/account/
publication matrices remain bound to their previous bundles. This checkpoint
does not qualify unreadable-registry recovery through the frozen executable,
Windows/Linux/clean-host behavior, real GitHub/store, physical USB/storage or
independent developer trials. The full SDK goal remains active. No calculator
operation, deployment, publication, commit, push or external communication occurred.

The expanded `--unreadable` run now passes **36 frozen CLI steps / six ARM
sessions / 13 recorded cases**, retaining the full workflow above. It reads a
partial registry backup through the executable with a modeled uncorrectable
payload page. An independent raw-file oracle verifies the preserved 704 bytes
and four missing 512-byte regions. Export and existing-backup refusal leave the
complete synthetic volume unchanged. Canceling repair, clearing the fault during
consent, and moving the fault to another page each preserve the exact original
volume and backup. Cleared/moved faults respectively return
`registry_fully_readable` / `stale_registry` after the approval scan.

Approved repair passes with the original page still unreadable. A further cold
launch, with that old page fault enabled again, authenticates the replacement
registry and opens Notebook with exact document/export bytes. Independent root
inspection remains identical across all six sessions. The partial-backup consent
screen was visually reviewed: it shows the full fingerprint/hash and explicitly
states that unreadable bytes are missing. The `frozen-v2` harness copy remains
beside its earlier four-session report; the current harness and expanded report
are in `frozen-v3`. SDK executable inputs and the desktop archive are unchanged.

Final regression results for that same bundle:

- **1,379 host tests pass**, with two expected private hardware-fixture skips,
  in 350.19 seconds. The complete terminal output is `full-host-tests.log`.
- All **eight relocated offline templates** pass, along with GDB source debugging,
  external CMake without Python discovery, source export, Notebook touch edit/save/
  cold preview and Notebook/Gallery paragraphs. The SDK has no IP-network,
  checkout or Homebrew access during those journeys.
- Two complete source kits including newlib are byte-identical. All **429 files**
  verify after extraction outside the checkout; actual source CLI generation,
  signing and inspection pass there using an explicit host Python/system OpenSSL.
  That is source-kit evidence, separate from the bundled-OpenSSL proof above.
- The audit verifies both private-install reports, all six expanded session roots,
  the offline report, source-kit hashes and all **1,909 regular archive files /
  723,117,897 bytes** against the tested desktop folder.

| Final report/artifact | SHA-256 |
| --- | --- |
| Expanded frozen private-install report | `daca66b14dffd1825bfce0cf6383a2ba6e9023cb4a7f822eb8634613e66876c5` |
| Frozen offline/template report | `5da79928037d9dc09c87ba81f8e5d7b1db0543072869d37a55975804be633f3b` |
| Reproducible complete source kit | `6f6e2945c4b9f4e9805a4a1aa5b78a79e9187c1184b2d214501800e5222d0c62` |

The archive/source-kit documentation predates these final annotations; the
executable identity is unchanged. Supported clean hosts, broader resource and
ownership/metadata recovery, physical USB/storage, real GitHub/store, complete
release source/signing and independent trials remain open. No goal gate is waived
by these local modeled passes.

Final checks pass 189 local documentation targets, Python syntax, whitespace and
the public boundary (1,094 files). All launched jobs reached collected terminal
results. The read-only snapshot at `build/sdk-private-desktop/evidence/` retains
406 indexed files (16,125,350 bytes), with hashes, lengths and read-only modes
verified. Index SHA-256:
`204d181d61acf6619791bc6d3dc36fa933a51fca123b792fc544e5f8e35d03af`.
Its copied ledger predates this final snapshot annotation. Archives remain
separately retained and bound by the audit; no generated private keys are in the
evidence snapshot. The full SDK goal remains active.


## Frozen storage CLI and interruption cleanup — 2026-09-14

The desktop storage workflow now exposes explicit `--emulator-usb` transports
for `files`, `data` and `archive`. Each adapter retains the physical client's
request allowlist and borrows an already enumerated exclusive model socket;
there is no physical fallback. Archive approval reads include request `0x96`.
Successful `files` and `data` commands now return after printing their result,
rather than accidentally entering build dispatch. Private-data restore validates
the complete bounded backup before USB access and retains those exact decoded
bytes if the pathname is replaced afterward.

Actual frozen testing reproduced two interruption failures. Immediate Python
KeyboardInterrupt could leave an unfinished USB control transfer and make the
next command time out. Deferring the signal exposed another race: cleanup sent
CANCEL before firmware consumed an acknowledged chunk, which rejected the request.
The CLI now records Ctrl-C until a safe client checkpoint; repeated signals do
not interrupt cleanup. Cleanup waits for the owned pending operation to settle,
skips completed/failed/changed sessions and then sends the bound cancellation.
No data frame is retried. Once COMMIT starts, bounded receipt/identity checks
finish and report the actual outcome. A verified commit remains success.
Explicit cancellation commands also wait for the current operation to settle.

`vm/test-sdk-frozen-storage.py` runs the actual relocated executable with checkout,
Homebrew and outbound IP access denied. Its relay forwards real QEMU USB replies,
and withholds one reply briefly while sending SIGINT inside the transfer. The
matrix covers file paging/space/quota inspection, large-file and maximum private
backup round trips, canceled imports/exports, accepted commits, whole-app archives,
upgrade rollback, cold reopening and damaged-object repair. It independently
inspects the resulting production filesystem. These are synthetic media and
public signing fixtures, with no physical calculator access.

The original `frozen-v1` stopped at a broken-pipe observation. `frozen-v2` exhausted
local disk before reaching that case. `frozen-v3` reproduced the subsequent
archive-status timeout. `frozen-v4` exposed the pending-command cleanup race during
a file export. Their logs, original harnesses and available synthetic media remain
under `build/sdk-storage-desktop/`. Older expanded bundle folders were removed
only after every file, mode and symlink matched their retained exact archives;
`verified-duplicate-cleanup.json` records those checks.

The first full host suite reported 1,390 passes, two expected private-fixture skips
and one host C++ compiler abort. Its diagnostic input is retained; the isolated
expression recheck passed. The next candidate passed all 1,400 host tests with the
two expected skips. The final pending-command correction passes 224 targeted host
tests, including in-transfer SIGINT, repeated cleanup signals, commit outcomes,
changed/finished sessions and bounded waits. The final source then passed all **1,408 host tests**, with the two expected skips,
in 362.98 seconds.

A separate offline replay on the intermediate bundle stopped with an incomplete
emulator-control response while launching a restored Pocket Lab workspace. Its
log is retained; no cause is asserted. The desktop harness now preserves a failed
command's synthetic project/media and workspace archive before temporary cleanup,
so a recurrence can be diagnosed. This does not change SDK runtime behavior.


### Final storage candidate

**91 frozen CLI steps / eight ARM sessions / 12 cases pass.** Six transfers are
interrupted before commit and exit 130 after cleanup; the four interruptions of
accepted file/private-data/archive/rollback commits return verified success.
Subsequent status and data commands work without resetting USB. Every relay
reports no transport error. Cold reopening, schema-pair export/rollback,
version-high-water preservation, fresh restoration and corrupt index/private/code
repair pass. Independent filesystem inspection confirms the exact signed package
and absence of a pending upgrade in every final phase.

The frozen matrix uses 131,791-byte named contents, 17 additional empty files to
cross a listing page boundary and a full 65,536-byte private snapshot. Host
exports preserve existing destinations when canceled. Whole-app restoration
recovers exact saved bytes; re-export matches the original archive byte for byte.
Code repair requires the original signed package. No firmware, ABI, storage
format, production key or physical device was changed by this batch.

| Artifact/input | SHA-256 |
| --- | --- |
| SDK executable identity | `6f505c31ea58b4be2d6bf60f38ad2a78babb0bdf5f11f3be0c68942e84bbfda5` |
| macOS desktop archive | `1977167e035bfdc78559b92de107d392b1d0f85692f68de9a8fc7fa9d6dc6026` |
| Frozen storage report | `b578ef940b256e0b91742449aa559730f7baca61f265bf0234e3f254ca4a8e10` |
| VM firmware | `4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14` |
| Bundled QEMU | `c6e5e83b8e398ebca70fc050ef2675f69321ad57953f43c377ddd67461f90ab2` |
| Reproducible complete source kit | `966e3b871f87df68b279db0d2151a0acbc6a931e2a61b54d4993c7654aa24cf1` |

Two independent source-kit generations have identical bytes. Extraction outside
the checkout verifies all 429 checksum entries and the exact SDK executable
identity. Eight real source CLI commands create/build a C project, generate a
temporary app identity, sign/inspect its package and expose the storage command
families. Those temporary private keys are removed. The source-kit and desktop
documentation precede these final annotations; their executable inputs match.
Native Windows/Linux, supported clean hosts, broader resource/media coverage,
physical USB/storage/power, real GitHub/store and independent-developer trials
remain required. The full SDK goal is active.


The final bundle also passes all **eight relocated offline template journeys**,
workspace clone/export/restore, bundled GDB and external CMake integration,
Notebook touch editing, exact save/export and cold-preview readback, and both
Notebook/UI Gallery paragraph previews. Report SHA-256:
`ee5a426c243b9b4751105b1e3715d900688124439fca7532f8cb8e99353370d4`.
The replay ran after the storage and full host jobs ended. The prior restored-
workspace failure did not recur; no matching QEMU host crash record was found
within five minutes of that failure log. Its cause remains unconfirmed, and
passing this replay is not presented as a diagnosed fix for that earlier failure.


The final artifact audit passes: all 1,909 regular archive files (723,138,435
bytes), directory membership, modes and symlinks match the tested bundle.
It rechecks source/report identities, signatures, all eight independent roots,
retained private/named bytes, archive structure, six cancellations and four
interrupted accepted commits. Both source kits and all 429 entries verify.
The audit checks 158 local documentation targets. Public-tree and whitespace
checks pass. All launched test/build jobs have collected terminal results.


The read-only evidence snapshot retains 958 files (28,240,530 bytes), with every
hash, length and mode verified. Its index SHA-256 is
`c457beb780e2eb18053700d8f266f65f6dd332ff4a38f9431706c02afd71a8d7`.
The snapshot's ledger predates this annotation. Desktop/source archives remain
separately retained. Final public-tree validation passes 1,096 files; no owned
build, test or emulator process remains running. No commit, push, publication or
physical operation was performed.

## Emulator failure reporting and preview recovery — 2026-09-14

The SDK now drains QEMU stderr while the child runs, retaining only its last
64 KiB. Failed runs retain bounded stderr/UART tails alongside structured input
identities, execution phase, control operation and process outcomes. The report
distinguishes an already-exited child from termination during cleanup. Socket
cleanup errors and diagnostic-file write failures do not replace the original
runtime error. Control requests use complete socket writes.

Failed or cancelled startup attempts replace an older successful `run.json`.
Replay failures retain a structured summary, and the preview page links local
failure details while keeping its last successful frame. A subsequent attempt
clears the old emulator attribution: a new validation/build error cannot display
the previous emulator's logs as its cause. Diagnostic files remain local under
the project's build directory and are excluded from app source archives.

The retained `build/sdk-emulator-failures/` evidence includes the original source
copies, failed/intermediate attempts, exact bundles, logs and qualification
harnesses. Eleven new host cases exercise actual child exits, incomplete control
responses with exited/live children, stderr beyond pipe capacity, bounded UART,
cleanup errors, unavailable diagnostic directories, stale startup passes,
replay summaries and stale preview attribution. The targeted matrix passes
**92 tests**.

The final `desktop-v2` macOS ARM64 bundle passes **18 actual CLI commands across
ten diagnostic/recovery cases** in `frozen-v3`. Its relocated executable cannot
read the checkout or Homebrew and cannot make outbound IP connections. Pocket
Lab installs through modeled USB, clones/exports/restores its workspace, launches
three times, encounters an intentional QEMU startup failure and launches again.
The failure wrapper writes 262,144 bytes before executing the actual bundled
QEMU with an invalid machine selection. The SDK retains a 64 KiB tail, the real
exit code and exact launched-input hashes without hanging on a full stderr pipe.
The wrapper and underlying QEMU identities are recorded separately.

Notebook then edits/saves a document and cold-previews it. Its intentional QEMU
failure preserves the exact saved document, checkpoint receipt, archive and
last frame, with working diagnostic links. A later invalid scenario preserves
those bytes while removing the obsolete emulator attribution. A successful
cold preview reproduces the earlier frame and saved document. These cases
exercise real signed ARM packages and synthetic storage; they are not physical
power-loss or electrical qualification.

| Final candidate/input | SHA-256 |
| --- | --- |
| SDK executable identity | `58f3a21c5890b4c3374af53fcf7d8b970720b88eb09f7e1205f7c1695016491c` |
| macOS desktop archive | `25ed2286aa5976b47be8766949c508fd5ea274d432fb5671657fb950beb40aa1` |
| Frozen diagnostic/recovery report | `70d67c71001d6648cab5db6c59cb3644e1338b94137e807f9b72e28565dc0b6c` |
| VM firmware | `4e45a4dea9aebf6ce27c128d30d57d31851a6148bb45159c2fec57e41ccd2d14` |
| Bundled QEMU | `c6e5e83b8e398ebca70fc050ef2675f69321ad57953f43c377ddd67461f90ab2` |

The first full host run finished with 1,417 passes, two expected private-fixture
skips and one lock-identity rejection in the incremental C build test. The SDK
changed during that run: its retained project lock matches `desktop-v1`'s
`37da9703a5663fb9c49d90020e3a1a9178977fa7c68c43e0d4fc797e08dcaab8`
identity, while the final source and `desktop-v2` match the identity above.
The rejection is not treated as a compiler failure or waived test. The retained
fixture and `full-host-v1-lock-explanation.json` preserve this evidence.

The original storage-bundle replay's spontaneous incomplete control response
has not been reproduced or explained. Passing these deliberate error cases and
restored-workspace repeats does not establish its cause. Native Windows/Linux,
clean supported hosts, physical input/performance/storage/USB/power, real GitHub
and production-store qualification, and independent developer trials remain
open. Storage/private-key/network matrices from earlier bundles remain tied to
their own exact artifacts. No firmware or trust-root change is part of this
diagnostics batch, and the full SDK 1.0 objective remains active.

With the final SDK source held fixed, `make test` passes **1,419 tests with two
expected private DTB/DTS skips** in 356.12 seconds. The previously rejected
incremental C build check passes in that full run. The complete log is
`build/sdk-emulator-failures/full-host-v2.log`; the earlier failed run is retained.

The final bundle also passes all **eight relocated offline template journeys**,
workspace clone/export/restore, GDB and external CMake integration, Notebook touch
editing/exact saves/cold previews, and both Notebook/UI Gallery paragraph checks.
The report is `build/sdk-emulator-failures/offline-v1/report.json`, SHA-256
`76a43a40dab8e922deec768e0e629a5da39d20d92fc389b01bc69d2f3bc99e4f`.

Two source-kit generations are byte-identical, SHA-256
`ae4d8854ba5c4a1116ce9c5ddcbe30af3c0da6c82be800ad6b494604e091bfbe`.
Extraction outside the checkout verifies all 430 checksum entries and the exact
SDK identity. Five real source CLI commands create/package an ordinary C project,
launch it on ARM, replace that pass with an intentional real-QEMU startup failure
and relaunch successfully with the same signed package. The source kits include
newlib and the diagnostic module. Source/bundle documentation precedes these final
evidence annotations; their executable inputs match the qualified candidate.

The final artifact audit verifies all 1,910 regular desktop archive files
(723,163,749 bytes), exact tree membership, modes and symlinks against the tested
bundle. It rechecks both source kits, report/input identities, retained failure
logs, unchanged Notebook frames, expected failed commands and 144 local
documentation targets. Public-tree validation passes 1,099 files; whitespace
and changed-Python syntax checks pass. The audit is retained as
`build/sdk-emulator-failures/audit.json`. Source/evidence copies and their verified
read-only file manifest are retained under that directory's `evidence/`; desktop
and source archives remain separately retained. All launched validation jobs
have collected terminal results. No commit, push, deployment or physical
operation was performed.

## Replay interruption and reserved Shift navigation — 2026-09-14

The replay engine now replaces an older successful `build/run.json` before
validating the selected suite, records the active case before launching QEMU,
and saves completed cases between runs. Ctrl-C preserves the completed prefix,
marks the active case/step cancelled and leaves later cases `not_run`. Unexpected
validation/execution failures also retain an incomplete report. Normal successful
summaries remain compatible with publication validation. An initial report-write
failure refuses execution; a later write failure cannot hide the original error.

Replay, preview and runner input cleanup now preserve the primary interruption
when key release or socket cleanup fails. Secondary ordinary cleanup exceptions
are recorded by type where available. The former behavior was reproduced with
an actual retained frozen executable: after an acknowledged Shift press, the
harness killed only its owned QEMU and interrupted the CLI during the same hold.
Key release raised `BrokenPipeError`, the CLI returned 1, and the third replay ran
after the interrupted second replay. The corrected source and frozen executable
return 130, retain a cancelled second case and never run the third case.

That experiment also exposed normal Shift+Home cleanup being consumed by the
native app. The checked-in native controller now returns Shift+Home (Setup) and
Shift+Apps (Info) to the existing OS Settings navigation, alongside base Home,
Apps and power. Pending archive/developer-key/channel approval is dismissed.
The OS still owns navigation, modifier reset, app close and heap release; no
direct modifier clearing, driver/register change or trust-root change was added.

Evidence is retained under `build/sdk-replay-cancellation/`:

- `frozen-v2`: **12 actual CLI commands, five lifecycle/publication cases**.
  A relocated macOS executable runs with outbound IP, checkout and Homebrew
  access denied. Process-only SIGINT, process-group SIGINT and process-group
  SIGKILL preserve the completed prefix and leave later cases unrun. Four ARM
  cold probes export the actual Notebook archive through modeled USB and compare
  exact saved document bytes. Every owned process group is checked for survivors.
- SIGKILL leaves the existing workspace lock directory. The harness first
  verifies that the SDK refuses another operation, verifies the entire owned
  group has exited, then removes only that fixture's empty lock directory before
  recovery. This does **not** implement or qualify automatic stale-lock recovery.
- Publication uses a freshly built and replayed copied project. Interrupted
  preparation creates neither `submission.json` nor an upload-ready report,
  cannot be resumed as a prepared submission and leaves the original project
  report intact. A fresh preparation succeeds while the earlier attempt stays
  incomplete. This is local dry-run preparation, not a production-store test.
- `key-frozen-v1`: **four CLI commands** with the acknowledged KPP Shift
  press/disconnect/interruption above, followed by a complete normal suite.
  Its qtest trace records the actual model write/acknowledgment before the signal;
  the wrapper only enables QEMU logging. `key-source-v1` passes the same case.
- `navigation-v2`: **five ARM phases** from Notebook's editor through base and
  shifted Home/Apps, with exact exported document hashes across cold boots.
  Heap release and execution reset pass. Reviewed frames show Calculation for
  Home, the launcher for Apps and Settings for both Shift variants.
- `developer-keys-v1`: **23 checks across five ARM sessions**, including both
  Shift shortcuts cancelling enrollment without adding trust, private install,
  revocation, signer recovery and preserved private/named-file data after cold
  boots. `archive-consent-v2`: **12 checks across three ARM sessions**, including
  both Shift shortcuts cancelling before root publication, approved cross-signer
  recovery, exact archive round trip and cold rollback with ownership/history.
- `channel-v1`: **five ARM cases** cover denial, timeout, connected Home and
  both Shift shortcuts during pairing. `compatibility-v1` runs the two unchanged
  ABI 1 Counter/Surface3D packages and checks normal input and differing frames.
- `host-v3.log`: **189 targeted tests pass**. `full-host-v2.log`: **1,441 tests
  pass with two expected private DTB/DTS skips**, 360.99 seconds, with SDK
  executable inputs held fixed. Both physical and VM firmware targets compile;
  existing upstream/linker warnings remain. No physical device was written.

The earlier attempts remain available. `before.json` demonstrates an old replay
pass surviving cancellation; `key-release-before.json` demonstrates interruption
being replaced during release. `key-reference-v1` retains the actual old frozen
failure and trace. `key-before` stopped before interruption on the original
shifted-Home cleanup defect. `source-v1` exposed the existing hard-kill lock rather
than an automatic recovery path; the corrected source/frozen harness retains the
guarded refusal and explicit fixture recovery. `navigation-v1` incorrectly used
diagnostic 0 (retained program counter) as an unload flag; `navigation-v2` checks
the real heap reservation and reset execution result instead. The first archive
rerun stopped on a harness receipt lookup before restoration: its input was an
already verified reused archive. The harness now accepts that receipt only from
a completed qualification and rechecks archive/package signatures and hashes.
None of these failed attempts is counted as a pass.

| Final candidate/input | SHA-256 |
| --- | --- |
| SDK executable identity | `8442ca5b659f4dfee50c93b99bbe311c1d763f2dc2081841f09329df9daa6f3e` |
| macOS desktop archive | `954d6e59a249dc01d2e28cfaad4669af87985c95fa21ae2159763f854245c52e` |
| VM firmware ELF | `f1874e2cb6ece1a18b1dafb1756022563a1d42ab31e97f75ffca0f9b10d45c02` |
| Physical firmware ELF, compile only | `bfe9641653b099a0a4cbca041a4d926c661b05a01b7dec6a9dfbb7a83a704858` |
| Frozen lifecycle/publication report | `3770b5da86449a9e6f5438de73b8a136d19a87f9cce6514b2c48c01fdb749156` |
| Source-kit archive, two identical generations | `972e978cff76c7cf974ecffe1f4312fba2281139f51478eaaeec4bb71c193ac1` |

The source kit includes newlib. Extraction outside the checkout verifies the
checksum inventory and executable SDK identity; six actual CLI commands create
and package an external C project, run startup and replay, replace a pass after
invalid replay JSON and run successfully again with the same package. Archive
documentation precedes these final evidence annotations; executable inputs match.

The original earlier spontaneous emulator control-stream exit remains unexplained.
These deliberate cancellation cases do not establish its cause. Remaining native
Windows/Linux and clean-host qualification, broader runtime/UI/resource coverage,
physical timing/input/storage/USB/power, real GitHub and production-store operation,
and independent developer trials remain open. Earlier network/private/storage
matrices remain bound to their own bundles. The complete SDK 1.0 goal stays active;
no commit, push, deployment, external publication or physical operation is part
of this batch.

The same desktop bundle also passes **all eight relocated offline templates**,
GDB/external CMake, workspace clone/export/restore, both Notebook field edit/cold
previews and both Notebook/UI Gallery paragraph previews. The final artifact
audit checks all 1,910 regular desktop archive files (723,178,648 bytes), modes,
symlinks and exact tree membership, all 430 source-kit checksum entries, input
identities, expected interrupted/failed CLI results and 149 local documentation
targets. `make check-public` passes 1,102 public files; whitespace and syntax
checks pass. Reports are `offline-v1/report.json`, `source-check.json` and
`audit.json` under the batch directory. Read-only source/evidence copies and
their verified file manifest are retained under `evidence/`; the large SDK
archives and original synthetic media remain separately retained.

Core reproduction commands (choose new output directories; do not overwrite
the retained evidence):

```sh
.venv/bin/python vm/test-sdk-replay-cancellation.py \
  --bundle build/sdk-replay-cancellation/desktop-v2/lefony-sdk \
  --output build/sdk-replay-cancellation/repeat-lifecycle
.venv/bin/python vm/test-sdk-replay-cancellation.py --key-only \
  --bundle build/sdk-replay-cancellation/desktop-v2/lefony-sdk \
  --output build/sdk-replay-cancellation/repeat-key
.venv/bin/python vm/test-sdk-system-navigation.py \
  --qemu build/sdk-native-host/qemu-public/qemu-system-arm \
  --firmware dist/lefony-os-prime-g2-vm-native.elf \
  --output build/sdk-replay-cancellation/repeat-navigation
.venv/bin/python vm/test-sdk-desktop.py \
  --bundle build/sdk-replay-cancellation/desktop-v2/lefony-sdk \
  --output build/sdk-replay-cancellation/repeat-offline
```

## Linux x86-64 Canadian compiler build — 2026-09-14

The earlier x86-64 compiler attempts stopped inside emulated Ubuntu GCC/Python.
The dedicated SDK Docker context also retains an ARM64-hosted GCC 16.2 toolchain,
built from the existing pinned GCC/binutils sources. The new
`scripts/build_sdk_linux_cross.py` uses that toolchain and native ARM64 build tools
to produce Linux x86-64 compiler executables targeting `arm-none-eabi`. This is
GCC's [Canadian build model](https://gcc.gnu.org/onlinedocs/gccint/Configure-Terms.html),
with distinct build, host and target systems; the SDK compiler/source pins remain
GCC 16.2.0 and binutils 2.47.

The recipe validates ELF architecture for the native build tools, records their
hashes/triples and preserves the native same-version target compiler selection
through libgcc construction. It checks the resulting x86-64 tools before running
the final mixed C11/C++17 ARM compile/link probe through the environment's existing
binfmt emulation. Output and failed scratch trees are retained, with per-command
outcomes from the existing compiler-build helper. A successful emulated probe
would still not qualify native Linux or a complete desktop bundle.

`scripts/sdk-linux/Dockerfile.cross` adds the x86-64 cross compiler and development
libraries inside a separate ARM64 build image. Its base was independently checked
as ARM64 image `95722b010ad1b71b41ee3004796c5a152961ff8f7ed0171553eead8243267fca`.
The resulting image is
`99dc86f65dfe5a10d90aae5adba0d56a3726f7aa0464b8ca25602cefd2a6fbbf`.
No existing VM settings, global binary-format registration or Docker context
selection was changed. The first image command used an image ID where BuildKit
expected a base reference and failed before building; the corrected command
used the verified local reference. The first compiler launch found that this
SDK VM does not mount the checkout and failed before starting a build. The actual
job uses a dedicated named volume, with only the two build recipes copied in.
Both setup failures remain in `build/sdk-linux-cross/`.

At this checkpoint, the actual build has passed binutils configuration,
compilation and installation, plus GCC configuration. The installed assembler
is verified as ELF64 x86-64, while GCC's build-time generators use the native
ARM64 compiler. **GCC compilation is still running; no completed compiler or Linux
SDK is claimed.** The network-disabled, read-only-root container has two CPUs
and a 3 GiB memory limit. Its exact container/image/volume IDs are recorded in
`build/sdk-linux-cross/compiler-job-volume.json`; stage records live in
`/work/results/compiler-v1/commands.json` inside that job's volume. Logs and
eventual terminal state must be inspected before continuing or reporting completion.

Initial validation passes **47 host tests**, including architecture rejection
and the existing compiler/desktop-packaging cases. Source-kit inclusion verifies
the two compiler recipes, cross-image recipe and host guide byte-for-byte; that
check is recipe correspondence only and omits newlib. Syntax/help, whitespace
and public-source boundary checks pass. The full SDK goal remains active,
including Linux QEMU/GDB/dependency assembly, native host journeys, physical
qualification, production services and independent developer trials.

## Completed Linux compiler and debugger components — 2026-09-14

The compiler job above has now finished with exit 0 and no out-of-memory kill.
All **12 recorded stages pass**, including GCC installation, all selected ARM
libgcc variants and actual C11/C++17 compile/link through the resulting x86-64
compiler. GCC compilation took 585.8 seconds; target libgcc compilation took
971.3 seconds. The mixed probe resolves the installed Cortex-A7 hard-float
libgcc and produces a verified ARM ELF object. This supersedes the initial
running checkpoint above.

The retained compiler archive is
`build/sdk-linux-cross/compiler-candidate-v1.tar.gz`, SHA-256
`a2739ef9a8ce96c12f54410ee902686978b228ffd019cf0bf343bd54d02e5f44`.
Its audit verifies all **1,158 installed files / 623,181,892 bytes** against the
candidate manifest, including archive links. The original container and volume
retain the complete scratch tree; the archive excludes scratch. The resulting
GCC executable is
`da8e336d3a8f3a983d3a9081b28caa326f0f3404ec6baa4f5560a8eb9c994c24`;
the candidate records x86-64-under-binfmt probes and explicitly leaves native
host and desktop-bundle qualification false.

`scripts/build_sdk_gdb.py` now supports an explicit Linux x86-64 cross compiler
and dependency prefixes, validates the output ELF architecture and distinguishes
emulated execution in its candidate. Build and host triplets are explicit.
`--work-parent` puts scratch on an existing disk-backed directory without spaces;
the default remains `/tmp` for GNU make compatibility with checkout paths that
contain spaces. `build-directory.json` identifies scratch retained after a failed
build; successful build/install scratch is removed. The new
`scripts/sdk-linux/Dockerfile.gdb-cross` layers Expat and a separate dependency
prefix onto the recorded compiler image without changing the completed job.

The real GDB build completed with exit 0 under a 1,500 MiB limit. Its dependency
image is `b9af683d014ae4c9ba3b987c1f3d57849f9b064f40815ff59962d9876828f856`;
the exact recipe SHA-256 is
`dae9b7f086ca844050e1742b9c57b46ed13bff4fbe1a8e0ed7113ca05aa0b821`.
All 40 installed-file hashes verify in `build/sdk-linux-cross/gdb-v1/`.
The x86-64 GDB executable is
`6f35e5fc0f5ed041e66340f67fea9eebaf203de23d88b7708431dc4424c46820`.
It reports GDB 17.2, ARM target, Expat support and no embedded Python.

`gdb-remote-v2/` in the same batch passes a real remote-debugger probe: halt at
an ARM C source breakpoint, read argument 35, finish the function, observe return
and global value 42, disassemble and detach. GDB runs as x86-64 under binfmt;
the QEMU component in this probe runs natively on ARM64. Its exact report hash is
`c14587028623d370d98e31fc7ddb6076e48911944e288f8553eda8977e16890a`.
The first probe timed out because its bare C entry had no initialized stack;
the corrected probe supplies explicit ARM startup assembly. The failed attempt
and its commands remain in `gdb-remote-v1/`; this was a harness correction.

The next Linux QEMU input has also been audited: 37 current public build/model
inputs and all four subproject pins match; all 12,253 compared source files in
the retained image archive match the local prepared source. A normalized archive
excludes the extra Python bytecode/cache directories and has SHA-256
`65bc6cc919cabb8387cb4d6201c059ad628ac013927d03d7e1f46c219d0d56b5`.
This is source preparation only; no Linux x86-64 QEMU build is claimed here.

Focused validation passes **50 host tests**, including the existing compiler and
desktop cases, Linux GDB cross-tool rejection and failed-scratch retention.
Whitespace and public-source boundary checks pass (1,106 files). The source kit
includes the new GDB image recipe. Component audits, source correspondence,
commands and both terminal job states are retained in `build/sdk-linux-cross/`.
These changes affect host build recipes and documentation; the prior firmware
and SDK executable identities remain unchanged. Linux QEMU/Python/dependency
assembly, native and clean hosts, complete source/license distribution,
production services, physical qualification and independent trials remain open.

## Linux x86-64 QEMU and integrated component probes — 2026-09-14

`scripts/build_sdk_linux_qemu.py` now builds the existing QEMU 11.1.1 / Prime r70
source with native ARM64 generators and an x86-64 cross compiler. The recipe
checks the supplied archive digest, extraction paths/bounds, source version,
required Prime files and executable architectures. It uses the already pinned
internal DTC subproject for offline configuration and records explicit target
pkg-config, architecture-header and transitive-library paths. The matching
`scripts/sdk-linux/Dockerfile.qemu-cross` extracts target library packages into
a separate sysroot and keeps native Python/build dependencies. Both recipes are
included in the source kit; no firmware, model or upstream pin changed.

The completed candidate is `build/sdk-linux-cross/qemu-v5/`. All five stages
pass: configure, compile, version, SDL display inventory and Prime machine
inventory. Configuration took 11.1 seconds and compilation 187.0 seconds. The
container exited 0 without an out-of-memory kill. Its x86-64 QEMU SHA-256 is
`f2e6cf7c1c212513c734ddaae44ab0ea08057694bb8b44d9fc1715d2c9c14af9`;
the source archive remains
`65bc6cc919cabb8387cb4d6201c059ad628ac013927d03d7e1f46c219d0d56b5`.
The exact build recipe is
`03ceaeea63fa06028f673495415fab7e8006add386584daca6c2853448d1667f`.
Dependency image
`a8f57b4f0028b7b97ccb799da4facdd2127e9f548df6a6e5ad66b5467eb857cc`
retains downloaded package versions and hashes; its Dockerfile hash is
`62ef8868bb6914ca77b183262f76e3d586465e9f8e7eb20405aafe90c85aed82`.

The component integration probe uses the newly built x86-64 GCC, GDB and QEMU
together, rather than the earlier native ARM64 QEMU. It compiles an ARM program,
stops at its C source breakpoint, reads argument 35, finishes the function,
observes return/global value 42, disassembles and detaches. Its retained report
is `qemu-gdb-v1/report.json` in the batch directory, SHA-256
`965c799ec3e30388d474eb8eb37c5175bcfc58f75f1920163db0a0f35bcd4982`.

The current SDK source runner then boots the unchanged VM firmware
`f1874e2cb6ece1a18b1dafb1756022563a1d42ab31e97f75ffca0f9b10d45c02`
and the retained ABI 1 Counter and Surface 3D packages. Both apps pass normal
KPP key dispatch, changed app frames and Home return to Calculation. The same
two journeys also pass with SDL's dummy video/audio drivers, exercising SDL
initialization without a graphical desktop. All 12 captured frames are verified
as 320 × 240; Counter, Surface 3D and the OS-return frame were visually reviewed.
Reports are `qemu-sdk-v1/report.json` and `qemu-sdk-sdl-v1/report.json`, hashes
`74f1b0d260690b65ea4998fa8417950074945369c2bc2548ee58dba3323a060e`
and `6444e2954ffa87a2dd634ba51a7098fa5890adf5ef88615edda31a0b4f88ea9b`.
The SDK executable identity remains
`8442ca5b659f4dfee50c93b99bbe311c1d763f2dc2081841f09329df9daa6f3e`.
The probe source kit predates the final host-recipe edits; its SDK executable
inputs are identical and its exact archive is retained separately.

The first dependency-image attempt installed foreign Python and was rejected
before use as a native build environment. The isolated sysroot fixes that.
Retained QEMU attempts then exposed missing native setuptools/wheel/pip,
offline FDT selection, Debian's architecture-specific SDL header and the private
PulseAudio library directory. Each was fixed in the build environment/recipe;
the final clean build uses the same source pin and preserves SDL support.
These attempts are setup/build failures, not passing emulator runs. Logs,
commands, terminal states and the retained final artifact are in the batch
directory; `qemu-audit.json` binds the component and all successful probe inputs.

Before the QEMU work, disk pressure required removing the completed compiler's
3.9 GiB scratch directory. Its source archives, logs, installed tools and full
candidate archive were verified before cleanup. Only that job's scratch was
removed; `compiler-scratch-cleanup.json` records the retained archive and source
hashes. This supersedes the earlier statement that compiler scratch was still
retained; the completed compiler artifacts remain available.

Focused validation passes **60 host tests**. Public-tree, syntax/help, whitespace
and host-guide link checks pass. These are component and source-runner checks:
the x86-64 tools run under binfmt emulation and the Python runner is native ARM64.
They do not qualify a frozen Linux x86-64 Python bundle, real desktop/window
behavior, Secret Service, physical USB/storage, production services or independent
developer journeys. Complete bundle/dependency/source assembly and the remaining
supported-host and physical gates stay open.

## Linux x86-64 Python component and installed-app failure — 2026-09-14

The completed QEMU checkpoint above now has a read-only evidence snapshot at
`build/sdk-linux-cross/evidence-qemu-v1/`: 104 files / 4,317,956 bytes, index
SHA-256 `4c4f34d921bf457077e87f5cad4a402765526f147755674c505a52153e80d75a`.
Its source kit has 296 verified manifest entries, with the final QEMU recipe,
image recipe and host guide checked against source. It intentionally omits
newlib; the later Python-component input below includes the verified runtime.

`scripts/sdk-linux/Dockerfile.desktop` now builds an Ubuntu 24.04 x86-64
packaging environment with Python 3.12, the SDK's pinned PyInstaller/Pillow/
keyring/truststore inputs and compiler/GDB/QEMU runtime libraries. The new
`requirements-python-x86_64.txt` locks all 18 resolved wheels by version and
SHA-256. The shared SDK requirements constrain those versions; a subsequent
no-index check requires every shared requirement to be installed. The source-kit
allowlist includes both new files. No SDK executable or firmware code changed.

The final image is
`21c441e38704fa3ed4e106c9beeac7025a29e07bed284a23ba41ff2c7b30fe67`,
verified as amd64. Its exact Dockerfile is
`e0bed80830df452a30fef6d169f8621797d3357d62d2bf2c82b4b76c7a6c1514`;
the wheel lock is
`5164099649264cd63ee631211b1f9c1dbd7464d4085448c286b4f565e5ae0baa`.
It uses the previously selected Ubuntu base digest
`a61567bd31828687156d735ea8eb01ba4e37636e225dd6a48ba94136a70d9d61`.
The selected QEMU links `libsndio.so.7`; the initial runtime image omitted it.
Adding `libsndio7.0` fixes that loader failure. A separate failed lock attempt
passed unhashed top-level requirements as installation inputs; using them as
constraints and checking their installed versions preserves hash enforcement.
Both failed attempts and exact image contexts remain under
`build/sdk-linux-desktop/`. BuildKit's required-base-argument lint warning remains.

The first real Python freeze failed when a PyInstaller isolated analysis child
segfaulted. Its log also contains a QEMU `rcu_read_unlock` assertion while
running `ldd`. A diagnostic launcher disabling Python's fast spawn paths then
completed the freeze. Twenty repeated isolated-module probes pass with default
spawning and twenty with ordinary fork, so those narrow checks do not establish
the original crash's cause. The fork-only override applies to the diagnostic
packaging process; the frozen SDK runtime is unchanged.

The retained component is `build/sdk-linux-desktop/python-component-v2/`.
Its executable SHA-256 is
`110f86b65ecbb6a133b7007cd77041adc5dfc1ad4e2716a6726b03600cf91246`.
The component audit verifies 475 regular files / 75,375,064 bytes; its file
manifest hash is
`330918d7c980f6fc1a48bd64688ed5676002326147218b110b5e68ed62a5acd7`.
It retains the current SDK identity
`8442ca5b659f4dfee50c93b99bbe311c1d763f2dc2081841f09329df9daa6f3e`.
The freeze input source archive is
`ec1bbd2321be78f3d265b2a22566b6abc029f5e43c9c9682d9bf6eea593e904c`,
with 436 verified entries and bundled newlib. Later host-recipe/document changes
are not represented as inputs to this already-built component.

The actual executable runs after relocation to a path containing spaces and
accented text. It creates and packages an external conventional C project using
the completed x86-64 compiler. The resulting package is
`c5b81da7664477a7cb1f2bfebde36e013cd89cd9c6b314a37f41c4ceba981f0c`,
matching the earlier macOS source-kit C fixture. Compiler/GDB/QEMU remain
separately mounted components in this probe. `doctor` correctly reports that
QEMU and firmware are not bundled, while finding compiler/binutils, GDB, Pillow
and libusb. The original freeze driver expected exit 0 and stopped at that
incomplete-component report; the follow-on harness explicitly checks this limit.
This is not a standalone SDK download.

Installed-app testing remains **failed**. After fixing the missing library,
signed installation reaches `APP OPEN`, then the control connection returns EOF
while QEMU remains alive. The runner retains the failure and terminates QEMU
for cleanup. Source-mode x86-64 Python reproduces the same failure, including
with the fork-only diagnostic. An instrumented comparison confirms complete
PING/state/input replies followed by zero bytes and EOF at APP OPEN. A native
ARM64 Python source-runner comparison using the same app, VM firmware and x86-64
QEMU passes installed launch, app diagnostics and Home/storage cleanup, with
`result: 1` and `os_responsive: true`. This narrows the investigation but does not
establish its cause. No reconnect/retry workaround or relaxed pass criteria were
added to the SDK. Notebook/Gallery and remaining frozen CLI journeys were not
reached after the first installed C-app failure.

The retained native-input inventory maps all 58 actual PyInstaller binary inputs
to installed Debian/source-package versions or downloaded wheel hashes. Every
input is ELF64 x86-64 and byte-identical to its frozen copy. The final locked
image preserves these 58 input hashes and loads the selected QEMU with SDL
available. This is provenance/integrity evidence, not complete corresponding
source distribution. Pillow's wheel has its own native/static inputs;
cryptography 50.0.1 reports embedded OpenSSL 4.0.2 and a Rust dependency SBOM,
separate from the system OpenSSL 3.0.13. Their retained SBOMs and wheel reports
must guide source collection; the macOS/Homebrew lock cannot substitute for it.

Focused desktop/source regression validation passes **68 host tests** in 8.68
seconds. Source inclusion, documentation links, whitespace and public-boundary
checks are recorded with this batch. Image build logs, terminal job states,
failed and passing comparison reports, the frozen component and its audit remain
under `build/sdk-linux-desktop/`. These are emulated Linux component checks.
The installed-app failure, complete dependency/source assembly, native/clean
hosts, Secret Service, real desktops, physical USB/storage, production services
and independent developer trials remain open. The full SDK objective remains
active.

## Signature-verification progress and Linux installed launch — 2026-09-14

This supersedes the preceding checkpoint's unexplained Linux `APP OPEN` EOF.
The same source and frozen CLI now launch the installed conventional C app with
matching candidate firmware. It is a firmware verification-progress correction;
no SDK transport retry, signature exception or watchdog timeout change is used.
The full SDK objective and all remaining host/release gates stay active.

### Cause and bounded correction

The retained diagnostic comparisons rule out closing QMP/QTest alone and removing
the stderr collection thread as fixes for this case. Parent-side system-call
tracing confirms a zero-byte socket receive. Server-side tracing shows QEMU
closing its channels during shutdown, rather than an isolated control disconnect.
A diagnostic three-second observation window lets the process exit naturally
with status 0; the earlier immediate `poll()` observation occurred before that
shutdown had finished.

Watchdog tracing records `imx2_wdt_expired`, reset action 0 and VM shutdown during
installed launch. Four QMP register samples while the launch is pending resolve
inside the RSA modular arithmetic and its `memcpy` calls, using the exact old
firmware ELF. Its two-second watchdog receives no health-checked progress while
those synchronous verification loops execute. These observations establish this
Linux reproduction's cause. They do not independently establish the cause of the
earlier unrelated macOS control-stream observation.

`native_app_signature.h` now accepts an optional internal progress callback.
The unchanged RSA arithmetic reports after each completed 64-bit iteration batch;
payload hashing reports after each completed chunk of at most 4096 bytes. Compiled
app keys, authorized developer keys and signed icons pass the firmware's health
callback. All envelope, digest, padding, signature, signer and execution-versus-
inspection decisions remain in place. Rejected input never exposes a payload.
The callback does not dispatch events or mutate verifier inputs.

`Services::noteVerificationProgress()` retains the display guards, stack safety
and persistence-commit health checks. It services only an already-enabled
watchdog. The regular event loop still owns first arming: catalog authentication
also runs during board initialization, before `Watchdog::init()`. Review caught
that distinction after the first successful candidate, and the final builds and
runs below include the guard. Real stalls still reset the VM; no unconditional
interrupt feed or increased timeout was added. Physical watchdog policy, app/API
formats, trust roots, storage geometry and pinned QEMU inputs are unchanged.

### Final candidate evidence

- Both `make firmware-vm` and `make firmware` pass. Existing upstream compiler,
  GNU-stack and RWX-segment warnings remain. The physical target was compiled,
  not installed or tested on a calculator.
- Focused signature/developer-key/maturity validation passes **44 tests**. It
  checks the verifier with and without progress, a larger signed payload,
  modified signatures/envelopes, a recomputed forged payload digest, unknown
  keys, revoked execution and permitted retained-package inspection. Rejected
  verification preserves output parameters. A further **15 archive, private
  signing and key-session tests** pass. An initial command named a nonexistent
  icon test and ran no tests; its corrected invocation and both logs are retained.
- `vm/test-native-runtime-hardware.sh` passes on final firmware: normal health
  feeds, MMU/cache/interrupt checks, all three deliberate watchdog hangs
  (`DEADLOCK`, `IRQ_STORM`, `INFINITE`) and a fresh restart.
- `vm/test-sdk-main.py` passes four final ARM cases: clean/nonzero main return,
  initialization/exit/destructor ordering, initial saves and cold reopening.
  Exported cleanup bytes are checked independently. These use native macOS host
  tools and the real ARM guest.
- The unchanged relocated Linux frozen CLI passes installed C startup,
  saved-visits replay with relaunch and format-2 source export on the final
  firmware. The four-command harness also checks `doctor`'s expected exit 1 for
  the incomplete component assembly. Startup and replay take 39.548 and 49.580
  seconds, respectively; these are emulated whole-command timings, not physical
  performance or accepted preview budgets. GCC/GDB/QEMU remain separate mounted
  components. The CLI uses the existing compiled external C project, with spaces
  and accented text in its path, synthetic storage and IP networking disabled.

The broader new-project run remains **failed**: the x86-64 compiler's `cc1`
segfaults while compiling the app-linked `e_atan2.c`, before reaching the UI and
connected examples. The failure, compiler core files and command are retained;
local core copies were compressed only after exact decompressed-hash verification,
with original volume copies preserved. No compiler retry or skipped failure is
counted as a successful fresh-project run. A separate C-only harness first passed
startup/replay but used the wrong source-export format; its failure is retained.
The final harness supplies the required `source --format 2` and exits 0.

The final VM ELF is
`5a0636eb915aaf8ea62b889932ee0538ca20c9371334905a970406bc58680105`,
and VM binary is
`626fe41d6116c85368acfd8df0eb6fac60db9f501b55650bb4fd3b22fa792433`.
The physical ELF is
`0d7303fb8fa9a60d54f0002562a991fc5e010188ba8f6a42c9d8202f3d16f26f`,
and physical binary is
`109715c26858c57c03c230a93b16127009339e7352c6b19a5416401d55678233`.
SDK executable identity remains
`8442ca5b659f4dfee50c93b99bbe311c1d763f2dc2081841f09329df9daa6f3e`;
Linux frozen executable and QEMU hashes remain the preceding component hashes.
Earlier downloads/bundled firmware do not acquire this correction automatically.

Reports, exact diagnostic scripts, source/candidate identities and failed attempts
are retained under `build/sdk-linux-desktop/`. Final individual evidence is in
`cli-v5/report.json`, `native-main-progress-v2/report.json`,
`watchdog-regression-v2.log`, `verification-progress-candidate-v2.json` and
`watchdog-root-cause-v1.json`. The register/trace comparisons use the recorded
older firmware, not the corrected candidate. Complete Linux/Windows bundles,
the emulated compiler failure, dependency/source assembly, clean/native hosts,
credential stores, real desktop/USB operation, production services, physical
qualification and independent trials remain open.

Final repository validation passes **1,463 host tests**, with two expected
private DTB/DTS skips, in 360.77 seconds. Whitespace, 144 local documentation
paths and the public source boundary (1,111 files) pass. The standalone source
kit is `3e8df2c08615f9f032922438ec6755bc1bbca6ec9bbcdf21d95bb09b0f0f2219`;
it intentionally omits newlib and is not a complete desktop/source distribution.
All twelve retained Linux diagnostic/runtime containers for this investigation
are terminal. The earlier read-only Python evidence snapshot remains unchanged.
The new read-only `evidence-verification-v2/` snapshot contains 103 files /
10,019,088 bytes, with index SHA-256
`26154a5ab532f0daf8ea6c22a4cd824f48cedbe408a5170df2a3af4137146a03`.

## Linux source collection and fresh-project failure isolation — 2026-09-14

The unchanged Linux frozen CLI now has fresh C and Notebook release-workflow
passes, plus a separate Link Gallery build/startup/source pass. The complete
matrices remain failed. This batch also adds reusable Ubuntu and Python source
collectors; it does not declare a complete Linux bundle or close the full SDK
objective.

### Source collection

`scripts/collect_native_linux_sources.py` rechecks actual frozen input bytes and
installed Debian binary/source identities. It uses isolated APT state, signed
Ubuntu source repositories and exact versions. It downloads source descriptors,
original archives and distribution changes, verifies the authenticated SHA-256
and size lists, and retains installed copyright files, common license texts,
recipe, inventory and command logs. The process ran with a read-only container
root and a writable SDK volume; no packages were installed or unpacked.

The retained run collects **13 source packages, 41 source files and 171,328,931
source bytes**, with 16 installed copyright notices and 17 shared license texts.
An independent readback verifies 74 source/notice entries, recipe/inventory
identities and all 40 successful APT commands. Its manifest SHA-256 is
`24f9b9000347acf0731ed27ff2339be028a4877fd8382f0b1cd5356259cab748`.
The exact materials remain in the SDK Python volume at
`/work/results/debian-sources-v1/`; local logs/manifests and verification are in
`build/sdk-linux-desktop/debian-sources-v1-evidence/`.

`scripts/collect_native_linux_python_sources.py` binds source selection to the
packaging image's pip report, installed versions and actual native-input wheel
identities/hashes. It reuses the existing source-download/notice collector,
retains installed distribution metadata and SBOMs, and includes nested vendor
metadata and notices. Existing output directories are rejected; failed attempts
retain their inputs and failure manifest.

The final Python run collects **18 exact source distributions, 54,782,249 source
bytes, 34 installed notices and 219 metadata files**. Independent verification
checks 274 entries, including the three recipe files, against current source.
All source archives and installed metadata match the original collection. An
intermediate path-hardening attempt omitted setuptools' nested vendor metadata;
the final collector handles bounded nested metadata paths and includes the
additional vendor notices. All attempts remain separate. The final manifest
SHA-256 is
`0c4107241c38e2e6c7bff82a7d8e8bb2f847710316f44c87ecfdd38517f31c43`;
materials and verification are in `build/sdk-linux-desktop/python-sources-v3/`
and `python-sources-verification-v3.json`.

Both manifests deliberately retain `complete_desktop_sources: false`. This
collects the currently inventoried system and Python sources; Pillow's native
wheel dependencies, cryptography's Rust/static OpenSSL inputs, other embedded
native inputs and the complete compiler/GDB/QEMU bundle closure still require
their matching source audit. These source collections are not SDK downloads.
The collectors, helper and Ubuntu repository configuration are included in the
standalone source kit and documented in `sdk/HOSTS.md`.

### Fresh ARM workflows and unresolved process failures

Both fresh-project runs use the unchanged frozen executable
`110f86b65ecbb6a133b7007cd77041adc5dfc1ad4e2716a6726b03600cf91246`,
final verification-progress VM ELF
`5a0636eb915aaf8ea62b889932ee0538ca20c9371334905a970406bc58680105`
and separately mounted compiler/GDB/QEMU components. The packaging image remains
`sha256:21c441e38704fa3ed4e106c9beeac7025a29e07bed284a23ba41ff2c7b30fe67`.
IP networking is disabled for the CLI/ARM probes. Core output is disabled for
new diagnostics; the original retained cores remain available.

- `cli-v6` passes new C project creation, packaging, installed startup, saved-data
  replay and format-2 source export. A new Notebook project passes creation,
  packaging, installed startup, its bundled normal-input edit replay and source
  export. That edit replay captures UI states and asserts two frame changes; it
  is not an independent byte-level or cold-data oracle. Notebook's debug preview
  then fails compiling generated `runtime-arguments.c`: GCC exits with SIGSEGV,
  and the preview reports 38.228 seconds elapsed. Release passes do not qualify
  this preview. The subsequent gallery steps are not run.
- `cli-v7` independently passes new Link Gallery creation, packaging, installed
  startup and source export. This is an offline startup check, not a connected
  HTTPS/cache journey. UI Gallery creation then exits with SIGSEGV and no output,
  before compilation. Its dependent steps are not run.
- Both runs explicitly expect `doctor` to report missing bundled QEMU/firmware;
  that expected diagnostic exit does not turn this component assembly into a
  complete bundle. The failed matrices remain marked failed.

Direct compiler diagnostics retain the original arguments and separate outputs.
Ten repetitions of the earlier `e_atan2.c` command pass. A further 250-command
comparison has two failures: one generated-argument compilation with system
library search and one with a PyInstaller-style library path. Successful objects
are identical within each source/flag group. A separate 400-command startup
probe (`true` and compiler `--version`) passes; it is not a compilation test.

A 400-compilation syscall-traced comparison reproduces three failures with
Python's default spawn configuration and five with its fork optimizations
disabled. Some traces show GCC spawning `cc1` through `CLONE_VM|CLONE_VFORK`,
then reporting the child's segmentation fault and itself faulting; other failed
launches have empty diagnostics. Thus neither changing the inherited library
path nor disabling Python's spawn optimizations resolves the observed failures.
These diagnostic modes are not SDK fixes or release settings.

Read-only inspection confirms the existing binfmt interpreter is QEMU-user
7.0.0, a static ARM64 executable; its registration and executable hash are
retained. The interpreter, VM settings and global handlers were not changed.
The frozen CLI's independent project-creation crash establishes that failures
are broader than a compiler-only case. The complete underlying cause remains
unresolved; no automatic retry, skipped failure or increased deadline is counted
as a correction. The older firmware watchdog fix remains independently verified.

### Validation and remaining acceptance

The final source-collection, Python identity/path/failure, Pillow source and
desktop packaging checks pass **75 host tests**. The actual Ubuntu and final
Python collection processes exit 0, and their retained source inputs pass
independent hash checks. Firmware and SDK executable inputs did not change in
this batch; earlier full-suite/ARM/firmware results retain their original scope.
Repository whitespace, public boundaries and the final source kit are checked
separately with the retained batch evidence.

Complete Linux/Windows assembly and source closure, the emulated process
failures, native/clean hosts and credentials, real desktop/USB/network/store
journeys, physical qualification and independent trials remain open. The full
SDK objective stays active. No calculator operation or publication is performed.

## Linux native-wheel source packaging — 2026-09-14

The Linux binary and source packagers now require reviewed sources for the
actual frozen wheel inputs. `scripts/linux_wheel_native_sources.py` and its
adjacent JSON lock verify original wheel archives, installed versions/native
bytes, source archive hashes/sizes and original wheel metadata/notices. The
binary packager records the actual PyInstaller native inputs before discarding
its staging tree and includes that report's hash in the candidate. Changed or
new native wheel imports fail packaging until their sources are reviewed.
The helper and lock are included in the standalone SDK source kit.

### Actual source correspondence

The retained freeze uses **21 native wheel files**: 19 from Pillow 12.3.0, one
from CFFI 2.1.1 and one from cryptography 50.0.1. The collection supplies **56
source archives / 409,052,033 source bytes**, with **3,672 source/lock/metadata/
notice entries** in the component. Its manifest SHA-256 is
`a7b031d8660517f00923448dd9ea59d0be6f22538f121265981ec29f9b378c2e`;
the source lock SHA-256 is
`3a4fd5e194b56bde9da8cda3c6af4477ade60dcdc49c3fabe442e2be19f2df03`.

- Pillow's generic dependency SBOM also lists optional libraries. Inspection
  of the selected wheel, Linux recipes and actual freeze establishes the
  narrower bundled set: seven other native files in the wheel are absent from
  this freeze and are explicitly listed as omitted in the lock. Matching source
  archives shared with the macOS collection were reused only after checking the
  Linux recipe; macOS binary qualification is not reused. Linux-specific inputs
  include Zstandard 1.5.7 and AlmaLinux libXau 1.0.9-3.el8's source RPM.
- CFFI's pinned release workflow builds libffi 3.4.6 statically with its renamed
  entry point. The actual extension defines `cffistatic_ffi_call`, matching that
  configuration. Both the CFFI source distribution and release recipes remain.
- All 39 components in cryptography's Cargo SBOM match its source Cargo.lock.
  The collection includes 32 registry crate archives, eight local workspace
  crates supplied by the source distribution (including its root crate), and
  OpenSSL 4.0.2. The binary's Rust 1.98.0 comment matches the full Rust source
  release's commit `88d9e12ae178fab0fb5cc050a94da85685d449ea`.

These are source-correspondence checks, not reproducible builds of the original
wheels. Source archives are read without running their code. The first libXau
source URL returned 404; that failed attempt remains separate. The subsequent
collection uses the exact source RPM in AlmaLinux's official 8.10 vault and
checks its spec/version and archive identity.

### Packaging and validation

The actual check ran in the retained Linux x86-64 Python image against its
installed wheels, existing PyInstaller `Analysis-00.toc` and relocated frozen
CLI. All 21 input/output records match the independent origin inventory. The
container had a read-only root, no network, bounded resources and no checkout
mount; it exited 0. The check did not rebuild or modify the frozen component.
Its executable SHA-256 remains
`110f86b65ecbb6a133b7007cd77041adc5dfc1ad4e2716a6726b03600cf91246`.

Source-material readback passes all 3,672 entries. The updated source packager
also produces a runtime source archive of **410,279,914 bytes**, SHA-256
`39b706b6b33a50283e3b7d364ce3f3b4ca7dceda2bd1e40c52bebbdff0a102e0`.
An independent streaming readback verifies every archived source/notice entry
and confirms that the archive preserves `complete_desktop_sources: false` and
`wheel_rebuild_qualified: false`. Packaging a component does not qualify the
complete desktop source distribution.

The focused source-collection, wheel-input, source-archive and desktop-packaging
suite passes **98 host tests**, including actual archive-byte checks and
rejection of failed collections and altered, omitted, duplicate or unreviewed inputs. This batch changes
packaging/source checks and documentation; earlier firmware, application and
full-suite results retain their original scope. Public-tree, documentation-link,
whitespace and standalone-kit checks are recorded with the batch evidence.

Artifacts, original wheels, inspected recipes, failed attempts and readback
reports are retained under `build/sdk-linux-wheel-sources/`; the exact command
and image/input identities are in `record-frozen-v2.py`, its log and
`linux-wheel-inputs-v2.json`; the first pass is also retained. This closes the reviewed freeze's selected native
wheel source collection. Complete compiler/GDB/QEMU dependency/source assembly,
Linux process crashes, Windows assembly, native/clean hosts and credentials,
real store/network/USB journeys, physical qualification and independent trials
remain open. No physical operation or publication is performed.

## Linux process comparison and preview input readiness — 2026-09-14

The preview investigation found two application-startup races. APP OPEN can
acknowledge before the first draw finishes; Notebook also completes a loading
screen before it can process input. Waiting for any completed frame therefore
does not establish that replay input will reach the interactive screen.

### Interpreter evidence and retained failures

The separate Linux host-process investigation compared the existing QEMU-user
7.0.0 interpreter with explicitly invoked 10.0.4 binaries. A 480-case guest-base
comparison has one baseline compilation crash; its other 479 cases pass. Changing
the guest base is diagnostic evidence, not an adopted correction. A second,
interleaved 480-case comparison runs 200 direct `cc1` compilations and 40 frozen
UI Gallery creations with each interpreter. The older interpreter fails one
compilation with SIGSEGV after 0.0043 seconds; the newer interpreter passes its
240 cases. All 399 successful compilations produce identical assembly, SHA-256
`19c1240d95730ff4d079cd6c9d044886546b625669a4ee33002735ad59f466a4`.
This narrows the observed environment failure without proving a specific upstream
fix or qualifying native Linux execution.

Full CLI probes explicitly invoke the recursive BuildKit variant from
[the upstream 10.0.4 release](https://github.com/tonistiigi/binfmt/releases/tag/buildkit/v10.0.4-57).
Its executable SHA-256 is
`d02e1860d3a9130557e627e11751a7ef82acb985b1db17dc864a9a4cbea79abf`.
The selected ARM64 image manifest, executable, upstream execve patches and
process-tree observations are retained. Global binfmt registration, its older
interpreter, VM settings and the default Docker context are unchanged. This
interpreter is a diagnostic execution environment, not a shipped SDK dependency.

With the original frozen CLI, Notebook's ordinary and debug workflows pass
under this explicit interpreter, but UI Gallery preview fails with an incomplete
layout. A retained raw frame has valid schema 1 and odd sequence 1 with only one
node. The first correction waits for an even sequence and passes Gallery, but a
stronger Notebook test still fails its first scroll assertion. That capture
contains the completed "Opening document..." screen, sequence 2. The touch
input was sent before document loading completed. These failed matrices remain
failed; no delay, retry or relaxed geometry assertion is counted as a fix.

### Debug-layout and preview correction

App-linked debug-layout schema 2 adds an input-readiness field, taking the frame
from 11,288 to 11,292 bytes. `inspectionEnd()` marks an interactive frame;
`inspectionEnd(false)` marks a completed screen that cannot handle input yet.
Notebook uses the latter for its blocking loading/save status screens. Preview
waits for a completed, input-ready frame before replay and final capture. A
hardware watchpoint observes sequence changes, with the existing 30-second GDB
deadline. Initial and final captures reuse one private debugger server; restarting
it between captures failed in an earlier retained attempt.

Timeouts retain debugger output, report the relevant capture log, and preserve
the previous visible frame and committed archive. Raw frames and decoded layouts
are retained for diagnosis. Schema 1 frames remain readable and use their
original completion semantics. The change does not modify a firmware service,
runtime ABI, storage format or release signature policy. Matching app rebuilds
are needed for the new readiness field; inspection remains absent from release
builds.

### Frozen and native-source validation

The final Linux CLI component is frozen from the updated source kit using normal
PyInstaller execution, without Python fork/spawn overrides. All 21 actual native
wheel inputs pass the source-lock/input audit. The relocated executable is
`40aa3b53d5ff378e298f7d47319b0ef2a26ebf936b8ec2da9495e8d29963dcc8`;
SDK executable identity is
`7818a53c8a13f89150657d1a4e1345ef9e145970151990b3c24480506b0458ee`;
the native-input report is
`b7627329f32ba2a62afa40b67ed131ba0f0b7c900354352fd4e4f22c95d30336`.
Its separately mounted compiler, GDB and QEMU remain the preceding component
builds. `doctor` correctly reports that QEMU/firmware are absent from this CLI
component; it is not a complete SDK download.

`vm/test-sdk-preview-kit.py --cli` passes five phases with this executable:
seeded Notebook, source edit, cold reopen, deliberate unfinished-layout failure,
and recovery after restoring the source. Touch starts without a guessed startup
delay and traverses normal Goodix dispatch. Each phase checks the exact clipped
row geometry and the retained 12-expression document, 131,328-byte attachment,
nested directory and empty directory. Source editing changes the title/package
while preserving the document pixels and bytes. Cold reopening reproduces the
frame. The failed inspection reaches its 30-second deadline with a retained
watchpoint log and unchanged frame/receipt/archive; recovery passes. The final
format-2 source export excludes preview data, archives and build outputs.
Initial GDB captures stop at Notebook's interactive sequence 4, rather than the
loading screen's sequence 2.

A separate fresh-project matrix passes all 13 expected CLI outcomes: the
explicit incomplete-component `doctor` diagnostic, plus creation, release
packaging, installed startup, normal-input replay, source export and debug
preview for each of Notebook and UI Gallery. Every observed CLI child uses the
explicit recursive interpreter. The final report is `cli-qemu-v2/report.json`;
the preceding `cli-qemu-v1` matrix retains its failed Gallery preview. This
completes these two projects' component workflows, not the full host matrix.

Native macOS source preview also passes initial editing, an intentional clipped
control, a deliberate compile failure with a stale preserved frame, correction,
and the actual source-save watcher. A separate source-module check against the
older SDK passes schema-1 Gallery capture through both debugger connections.
Its first harness incorrectly expected a precomposed accent; the retained frame
correctly contains the source's decomposed UTF-8 accent, and the corrected exact
oracle passes. The Gallery and Notebook frames were visually inspected.

The focused UI/inspection, GDB and preview-data suite passes 43 tests; the
gallery, maturity, architecture, desktop-packaging and Linux native-source suite
passes another 96. Sanitizer-backed debug/release checks cover the readiness
states and absence of inspection symbols from release code. Earlier full-suite
and firmware results retain their original scope. No firmware rebuild is needed
for this app-linked/host-only change. Both native-source and Linux probes use VM
ELF `5a0636eb915aaf8ea62b889932ee0538ca20c9371334905a970406bc58680105`.

Exact commands, source copies, intermediate failures, interpreter comparisons,
freeze reports and preview evidence are under `build/sdk-linux-process-layout/`.
The successful saved-data report is `frozen-preview-qemu-v3/report.json`; native
source evidence is `macos-source-preview-v1/report.json` and
`macos-legacy-layout-v2/report.json`. Complete Linux/Windows bundle assembly and
source/dependency closure, native/clean hosts, real credentials/store/USB,
physical qualification and independent developer trials remain open. The full
SDK goal remains active.

The batch's final validation record is
`build/sdk-linux-process-layout/validation-final-v1.json`: it binds the tested
source files, matching SDK executable identity, reproducible standalone source
kit, Markdown path checks and public/whitespace checks. The source kit omits
newlib and is not a complete desktop source distribution. Retained test artifacts
and source copies are indexed in `evidence-preview-v1/`; the earlier Linux wheel
source evidence snapshot is unchanged.

## Linux library closure and minimal-image workflows — 2026-09-15

The first full runtime assembly includes the frozen Python CLI, compiler,
binutils, GDB, custom QEMU, VM firmware, newlib, OpenSSL and libusb. Its help and
doctor checks pass in the packaging image, but an unchanged minimal Ubuntu 24.04
image exposes a real omission: QEMU exits 127 because `libdrm.so.2` is absent.
The packaging image's system libraries had hidden this failure. The failed
`desktop-assembly-v1` and `bare-desktop-v1` artifacts remain retained.

### Durable packaging correction

`scripts/native_desktop_linux.py` collects all non-glibc libraries required by
the trusted ELF helper inputs, including transitive graphics dependencies.
Missing libraries, architecture mismatches and conflicting bytes for one library
name fail collection. Libraries are copied under their requested names, retaining
input hashes. The desktop packager explicitly includes them before freezing.

After freezing, `patchelf` replaces absolute build-library paths with relative
paths in ordinary ELF helpers and libraries. It preserves the PyInstaller
launcher and embedded archive. The audit resolves each helper's dependencies
without inherited loader variables, so direct compiler and CMake use do not
depend on the launcher's environment. Non-glibc dependencies must resolve inside
the bundle. Unsafe symlinks are rejected. Input, relocation and dependency
reports are bound to the candidate; native-wheel output hashes are recorded
after relocation. The standalone source kit includes the new helper.

The second diagnostic assembly collects 62 libraries, audits 160 native ELF
files and passes the 21-file native-wheel source/input audit. Its launcher hash
is unchanged because the Python application is unchanged; the full tree and
relocation report identify this different runtime assembly. This is a direct
freeze using the production helper functions. The complete production packager
entry point and all corresponding-source groups have not yet been assembled
and qualified together.

### Minimal Ubuntu execution

The image is Ubuntu 24.04 amd64 at
`sha256:a61567bd31828687156d735ea8eb01ba4e37636e225dd6a48ba94136a70d9d61`.
Its root is read-only, networking is disabled and `PATH` is `/usr/bin:/bin`.
There is no host Python, ARM compiler or QEMU, and the component installations
and packaging Python prefix are not mounted. SDL uses its dummy display/audio
backends. The x86-64 tools run under the separately invoked recursive BuildKit
QEMU 10.0.4 interpreter; no global interpreter configuration changes.

All 45 recorded commands pass: direct compiler/GDB/QEMU/OpenSSL execution, direct
ARM compilation, doctor, and creation/package/installed-startup/source-format-2
journeys for Basic, Pocket Lab, Forms/Tables, Graph Explorer, Reference Cards,
C Main, Notebook and UI Gallery. Pocket Lab additionally passes workspace
clone/export/restore/inspection and cold launch. Both UI applications pass
actual ARM preview with completed, input-ready layouts and no inspection
overflow. Their frames were visually inspected. The first-preview totals are
76.8 seconds for Notebook and 73.6 seconds for Gallery under emulation; these
are observations, not supported-host latency budgets.

A separate fresh C project passes bundled GDB source debugging in the same
minimal image: breakpoint at `src/main.c:16`, `argc = 2`, backtrace, instruction
step and detach. The owned debug session exits after interruption. This is
stronger than a GDB version check; native Linux debugging remains unqualified.
External CMake itself was not installed or exercised in this minimal image.

Final verification rehashes every bundle file and symlink and confirms that the
workflows did not modify the bundle. Each startup report records result 1, no
fault, a responsive OS and completed workspace cleanup. The first evidence
verifier incorrectly expected a replay `status` field in startup reports; its
failure is retained. The corrected verifier checks the actual startup contract
against the same completed runs, without rerunning or changing SDK behavior.

### Source correspondence and checks

The complete freeze inventory identifies 159 native inputs, plus 1,101
non-host/toolchain or ARM firmware inputs. The launcher is the additional ELF
in the 160-file output audit. Firmware is explicitly classified separately from
host executables; this corrects the first inventory harness's failed package
lookup for the staged firmware ELF.

APT collects 44 additional exact Ubuntu source packages and their installed
notices, totaling 105,421,174 archive bytes. Combined with the earlier 13 packages,
57 source packages and 276,750,105 bytes cover all 90 Debian-provided native
inputs. The combined collection rechecks every archive hash and adds the missing
`openssl` and `libsystemd0` installed notices. It shares verified archive files
with the retained collections to avoid duplicate storage, while keeping separate
directory entries and manifests. Built tools/firmware and Python/native-wheel
sources remain separately retained; this does not declare full desktop source
distribution or upstream wheel rebuild qualification complete.

The focused dependency, desktop, native-wheel, maturity and architecture suite
passes 113 tests. The public-tree check passes with 1,121 files. No SDK executable
source or firmware changed, so previous firmware compilation evidence retains
its scope; this batch does not repeat physical or VM firmware builds.

| Artifact/input | SHA-256 |
| --- | --- |
| SDK executable identity | `7818a53c8a13f89150657d1a4e1345ef9e145970151990b3c24480506b0458ee` |
| Frozen CLI launcher | `40aa3b53d5ff378e298f7d47319b0ef2a26ebf936b8ec2da9495e8d29963dcc8` |
| Full assembly report, including every file/link | `afa57f8317a1827e19ef3026d462e47e6c07f5e4e1aa09d35b673ff17d5df082` |
| Bundled relocated QEMU | `0c74e0aa57bd9170ac6160266e15ad442a05d3eeae566cae8b8f624ed96634c1` |
| VM firmware ELF | `5a0636eb915aaf8ea62b889932ee0538ca20c9371334905a970406bc58680105` |
| Linux dependency audit | `9c0492684bfc90c94a9061e1086607f9a02592ff4c3aef2ed78e4fa30267baab` |
| Linux relocation report | `6755e8ade1cd3ed58266d8c5a56b9450853f2ab84dcc1cde1f50be58e54eb6cc` |
| Combined Debian source coverage | `606554112df6a26a9e6b00be3ec7e67d19c295a9c3835f6e3f12072eab663061` |
| Final evidence report | `60bd38f2351f2c1c0ba3ddd0755b66d40fab5ce1a7260f58408b60427653d6a9` |

Drivers, logs, intermediate failures and reports are under
`build/sdk-linux-assembly/`. `evidence-v3/` retains the verified template,
debugger, frame and source-coverage evidence. The original assemblies and source
collections remain in their dedicated SDK volumes. Final production bundle and
source assembly, graphical desktop/native Linux, Windows, credential stores,
real GitHub/store/USB, physical qualification and independent trials remain open.
The full SDK goal stays active. No device operation or publication was performed.

## Linux archive recovery, exact firmware sources and isolated workflows — 2026-09-15

This checkpoint produces and tests an actual Linux binary archive. It supersedes
only the preceding diagnostic assembly's missing binary-archive evidence. Native
Linux desktop/credentials/USB, Windows, real services, independent trials and
physical acceptance remain open. The full SDK goal remains active.

### Durable source and packaging corrections

The desktop packager now distinguishes path components from arbitrary binary
substrings when checking for embedded personal paths. The initial production
attempt rejected QEMU's relative `unspecified/root/aux` string. A later attempt
rejected libsystemd's standalone, NUL-terminated root-account default. The narrow
root-default exception does not allow private directories below that account,
other personal home paths or Windows home paths. Tests retain these distinctions;
no library bytes or environment home were rewritten to bypass the check.

The corresponding-source packager now requires an explicit project manifest
for its `lefony-qemu` group. It binds three existing, hash-checked tar archives
(Lefony public source, patched QEMU and prepared firmware) to the exact firmware
and QEMU binary inputs. Missing, changed, escaping, symlinked or non-tar archives
fail. Dependency-only groups work outside a Git checkout. Missing dependency
material is rejected instead of silently omitted. The schema and extraction
instructions are documented in [HOSTS](../sdk/HOSTS.md).

The prepared VM source was archived, extracted, independently indexed and rebuilt
with the selected GCC 16.2 toolchain on macOS ARM64. Its 4,399 source files produce
byte-identical VM ELF and binary outputs in 41.181 seconds. The first attempt
retained a different physical-target trust header and build timestamp, producing
511 differing bytes. The final preparation uses the checked-in VM trust default,
normal public emulator key generator and the existing settings preparation with
the original build stamp `260915-041224`. Physical signing keys and the original
prepared checkout were unchanged. This is an exact VM-source rebuild, not a
claim that every bundled third-party binary rebuilds identically.

### Interrupted packaging and verified recovery

The final production attempt completed freeze, dependency/source checks and smoke
checks, but host storage exhaustion aborted the SDK VM filesystem journal. The
recovered final checksum file and archive were empty. The retained process report
still said running because its final write was lost; Docker and kernel state
confirmed that the process had stopped. This attempt is not counted as a clean
end-to-end packager pass.

The dedicated SDK VM was stopped and its data disk cloned before recovery.
Offline read-only filesystem checking completed all five passes without structural
errors; a subsequent check cleared the error marker. The profile, image and
explicit interpreter identities remained unchanged. Recovery then checked 16,329
references, hashing 7,834 unique files and 4,376,285,619 bytes of source/component
inputs. Comparison with the preceding fully inventoried failed bundle found
5,499 identical files and unchanged symlinks. The six differing files were
explained by updated source metadata/docs or archive/JSON ordering; all 155
uncompressed Python-library entries were identical. No missing payload was
accepted.

After rechecking every file, mode, link and embedded-path rule, packaging smoke
was repeated and matched its retained result. The production archive routine
then wrote a complete archive, and every tar file/link was checked against the
bundle inventory. The resulting archive is 208,417,270 bytes. Its report records
`original_process_completed: false` and
`archive_recovered_after_storage_failure: true`.

The temporary raw recovery clone was retired only after its hash was rechecked
and the filesystem/input/bundle/archive evidence passed. Its identity and
retirement record remain under `build/sdk-linux-release/storage-recovery-v1/`.
To preserve disk headroom, verified duplicate extracted bundles were removed
while their full archives and inventories remained. The older macOS storage
`desktop-v2` and `desktop-v3` directories now require extraction from their
retained archives. Failed Linux desktop-v2 remains archived in the SDK volume;
the final archive and its independent relocated copy remain available. The
intermediate runtime-source-v1 archive was moved, with matching hashes, to
`build/sdk-linux-release/retained-runtime-source-v1.tar.gz` on the host. No
unrelated VM, device data, source checkout or signing identity was removed.

### Isolated archive workflows and visual review

The archive was extracted into `SDK with spaces é`, and all 5,505 regular files
(excluding the root checksum list) plus 13 symlinks matched the archive report.
That extracted SDK was moved into a separate named test volume containing only
the SDK, explicit interpreter and test drivers. The original source materials,
compiler/GDB/QEMU installations and packaging output were not mounted. Minimal
Ubuntu 24.04 had no Python, ARM compiler or QEMU of its own, and networking was
disabled. The containers used read-only root filesystems and bounded resources.

All 48 commands passed: direct tools/ARM compilation and doctor; external
creation, package/startup/source export for eight templates; workspace
clone/export/restore/cold launch; private key generation, signing and verified
inspection; and actual Notebook/UI Gallery previews. The signing check verifies
private-key permissions and unchanged unsigned package bytes. Every installed
startup reports normal OS responsiveness and Home/storage cleanup. Separate
minimal-host jobs also passed:

- Bundled GDB stopped at C `main`, read `argc = 2`, inspected a backtrace, stepped
  through source and detached.
- External CMake built a fresh C project using the bundle and produced a package
  accepted by the frozen CLI inspector, without an external Python installation.

The verifier rechecked all SDK bytes and symlinks after execution. It also binds
the 160-ELF dependency report and source inventories for 159 native and 1,101
non-host inputs. Notebook's 16 replay actions and Gallery's nine actions match
their actual project scenarios. Both report ready/input-ready layouts without
overflow, and the captured ARM frames were inspected: Notebook's expression,
result and complete export guidance are readable; Gallery's edited field,
focus border, enabled toggle, slider and feedback fit without overlap.

These previews took 77.85 and 70.34 seconds respectively, including debug builds,
under explicit x86-64 interpretation. They are not native-host latency budgets.
The test evidence is retained read-only under `build/sdk-linux-release/evidence-v1/`:
1,310 files, 32,812,528 bytes, including the file index and visual review. Prior
sealed evidence snapshots remain unchanged.

The focused host suite passes 110 tests covering desktop packaging, dependency
resolution, native-input matching, source archives and native-wheel sources.
This batch changes packaging/tests/docs; the exact firmware source rebuild above
adds evidence without changing firmware implementation. Public-tree and final
source-kit checks are recorded after the completed source-archive assembly below.

| Artifact | SHA-256 |
| --- | --- |
| Linux binary archive | `c2988ff0ce506d0f828d11e8ad54a55cc6565f51cf7bfd66e45021c59b7e6749` |
| Bundle candidate | `cd5a83b56b572b36de5a193e56185d8cbbfe32c5576354c30b66c9d78b9a7da3` |
| Source materials manifest | `cbf0d0d53dd5bd793ab728e4c0d05cfa92c9dbebb653eb42d84128f13ba13e9c` |
| Prepared firmware source archive | `3750fdf827e59e23c812d8cced2a31d9b1998a93ac7dd957d2405a357a930c81` |
| Exact rebuilt VM ELF | `5a0636eb915aaf8ea62b889932ee0538ca20c9371334905a970406bc58680105` |
| Exact rebuilt VM binary | `626fe41d6116c85368acfd8df0eb6fac60db9f501b55650bb4fd3b22fa792433` |
| Project/QEMU/firmware source group | `f404ab58ab00d47f0a704d678d2c77469de1e26c63fa8c2ec50a1544378e2db7` |
| Recovery/completed archive report | `2695a24d24b95b43c68d33b30d1866be83268225254e6a64a0ca73f3625da532` |
| Isolated workflow verification report | `3e630f418b3f63cc4c2152c610dedc118f4ca6164fa53c21877c8c0d1d24790b` |
| Sealed evidence index | `1f171965fb8c1a604edfefee662e2ccb43f1a75b9de946602d32327c0e13a1f9` |

Drivers, logs, exact image/interpreter inputs, retained failures, source rebuild
and recovery records are under `build/sdk-linux-release/`. The binary archive is
in the dedicated SDK volume at `results/release-desktop-v3/`; the isolated SDK and
workflow originals are in `lefony-sdk-linux-release-tests-20260915-v1`.

### Completed corresponding-source assembly

The current runtime archive completed in 603.242 seconds after repeating the
native-wheel material checks. The toolchain archive was reused only after its
component records, relevant manifest fields and complete archive hash matched.
A separate 42.156-second verification then read every source tar member and
compared its bytes with the current materials. The toolchain group contains
three components/28 files; runtime contains 79 components/4,244 files. Together
they cover all 82 component records, including every declared source input,
installed notice and installed metadata file. The project group retains three
nested source archives and their exact firmware/QEMU identity manifest.

`results/release-distribution-v1/` in the dedicated SDK volume now groups the
binary archive, all three source archives, packaging recipes, full materials
manifest, candidate, firmware rebuild and workflow/evidence reports. It uses
verified hardlinks to avoid duplicate large files. Its checksum list and report
bind the exact artifacts; the report is also retained locally as
`build/sdk-linux-release/distribution-v1-report.json`. The checked binary is
available locally as `build/sdk-linux-release/lefony-sdk-linux-x86_64.tar.gz`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Toolchain source archive | 180,138,009 | `ecb4163cc2c31da74b41c53789c10745bd41df050670a72c2636a51f2185c6e7` |
| Runtime source archive | 786,641,287 | `d3f6ca153571a36aba9a375478d2a9140180f20b5b521d7972389817dfc14573` |
| Project/QEMU/firmware source archive | 51,836,075 | `f404ab58ab00d47f0a704d678d2c77469de1e26c63fa8c2ec50a1544378e2db7` |
| Distribution verification report | — | `72b8d3d0579e787d12e1988ca5e4b675046d3db33e6cc1ff63b20839ad619b50` |

This completes source-archive assembly and input correspondence for this local
candidate. It does not establish reproducible upstream wheel rebuilds, native
host operation, a clean uninterrupted full packager run or release qualification;
the report retains those limitations explicitly. Historical materials manifests
and earlier sealed reports are unchanged. Final documentation/source-kit checks
are retained in `build/sdk-linux-release/final-validation-v1.json`; the source kit
is generated twice after these documentation updates, with identical bytes and
an independently checked content manifest. No physical device operation or
publication was performed.

## Linux companion shutdown, USB stalls and SDK VM recovery — 2026-09-15

This checkpoint continues the launcher-isolation work above. The existing Linux
archive is unchanged; the newer diagnostic bundle described here is not a release
or a replacement for native-host and physical acceptance.

### Control-endpoint stall regression

The companion's completed-response journey exposed an emulator limitation:
an unprimed stalled EP0 returned NAK, making the host retry until its deadline.
The checked-in model now reports direction-specific STALL without consuming
descriptors or modifying buffers. An accepted new SETUP clears the protocol
stall, following the behavior documented in the
[Linux ChipIdea correction](https://github.com/torvalds/linux/commit/56ffa1d154c7e12af16273f0cdc42690dd05caf5).
Malformed SETUP packets do not clear it. This changes the emulator model only.

The firmware-free `vm/test-prime-g2-usb-stall.py` uses the bounded SDK cable
transport, QTest registers and public OCRAM. It checks independent IN/OUT stalls,
unchanged primed DMA descriptors/buffers/completion, explicit clearing and new
SETUP recovery. The smoke suite now includes this regression; the standalone
command is in [the emulator guide](../vm/README.md). The current test fails the
old macOS QEMU at its first unprimed-IN assertion and passes all three groups
against the corrected macOS and relocated Linux binaries. The unrelocated Linux
binary failed to load `libcap.so.2` in the native-ARM harness container; that
attempt remains separate from the passing relocated bundle check.

The source companion test now waits for normal peer closure through the USB
protocol instead of ending the host loop from a guest diagnostic. Its bounded
journey passes normal keypad pairing, an exact 131,073-byte TLS download, normal
connection-end reporting, successful app exit, Home and exact public cache
readback. It records firmware/QEMU and channel/transport source hashes. The
old-model macOS comparison also passes this timing-dependent journey; the
standalone stalled-endpoint check provides the deterministic regression.

Native macOS QEMU compiles successfully; the Linux incremental build completes
in 4.514 seconds with all original build inputs restored and the prior installed
binary unchanged. The DDR/ROM USB checks also pass rejection while DDR is
unavailable, download after DCD setup, and self-refresh/wake preservation.
`make test` passes **1,610 tests with two expected private-fixture skips** in
393.32 seconds. Focused batches pass 83 packaging/adapter tests and 114
channel/bridge/adapter tests. Public-tree checking passes with 1,127 files.

### Recovery of the interrupted SDK build environment

The prior Linux build stopped with filesystem I/O errors. Before continuing,
both stopped VM disks were checked against their pre-recovery hash records.
The root filesystem passes read-only checking. The data snapshot has a pending
journal and directory/bitmap inconsistencies; the initial whole-disk check also
records that its filesystem is inside GPT partition 1.

Journal replay and automatic filesystem repair were applied to a separate APFS
clone. Its subsequent read-only five-pass check succeeds. A new input audit
checks 21,846 references, hashing 12,088 unique files and 3,847,748,294 bytes:
source materials, all distribution artifacts, the compiler/GDB/QEMU/newlib
inputs, the public source checkout, base native/target inputs and all 5,506
corrected-launcher bundle files. Earlier audit attempts stop at historical paths
whose extracted directories had already been retired; the successful audit
uses the retained distribution and isolated bundle paths.

Only after those checks was the repaired data copy installed in the dedicated
SDK VM. The original root disk and both pre-recovery snapshots remain retained.
The VM restarts successfully and completes the Linux QEMU build. This recovers a
development environment; it is not calculator power-loss evidence.

Five older macOS extracted SDK folders were retired after comparing their full
contents and modes with retained archives: native-TLS desktop-v1, store-deadline
desktop-v1, replay-cancellation desktop-v2, C-runtime desktop-v2 and
Windows-packaging macOS-final-v2. Extra generated Python caches were archived and
verified separately. Their original archives, hashes and restoration records
remain under their existing build paths and `storage-recovery-v2/`. Disk
headroom remains limited; large release/source rebuilds require another capacity
check before starting.

### Refrozen Linux diagnostic bundle

The retained launcher candidate predates the companion's exact-peer closure
handling. A new offline freeze uses the current source kit, the retained native
Python image and the explicitly invoked recursive x86-64 interpreter. It
preserves the complete embedded archive during launcher relocation, incorporates
the corrected QEMU, and passes a 160-ELF dependency audit without an injected
library path. All parent bundle checksum entries remain unchanged. Old metadata
is retained under `parent-metadata/`; the new candidate explicitly leaves native
source correspondence and production/source distribution unfinished.

The corresponding QEMU source archive is assembled separately and independently
checked member by member. All 13,092 entries retain their contents, types, links
and modes except the intended `hw/arm/prime_g2_peripherals.c` replacement. Its
SHA-256 is `8a4c141c2dd6e72ea3bc080fdd301809e3860c189d8b79fbec45e34bd421e076`.
The report binds the archive to the successful incremental build and unrelocated
binary. A fresh full source rebuild and combined production source-material
refresh remain pending.

The first frozen GET run completes the response and reports normal connection
end with exit code zero, then fails the harness's descendant-process disappearance
check. That container did not run an init process. Its exact evidence is retained;
the subsequent init-enabled matrix is recorded separately below. No failed
attempt is counted as a complete companion pass.

| Input/candidate | SHA-256 |
| --- | --- |
| Prime peripheral source | `b9b915c5f699e09e4d3c2b7867f2f034656e270ce735cac16eae039ea5ec4670` |
| Corrected macOS QEMU | `e1e86a5f56465a7b67c5e472e19e1b96481e7bb685b91251874c882b8b4863f4` |
| Corrected Linux QEMU before relocation | `58e8f5f8eedba30d1c0e66690ec9189e52d0bf9792d40a38204f67637437a0cc` |
| Corrected Linux QEMU in diagnostic bundle | `b8bdc792f02b154a3e1fed872a52fb1f015386fa98b44c5867b14599e39d70ff` |
| Current source kit used for freeze | `ddbce6162dc8de6a1a377693a61f7fc7a3dee58e141deb0c394fdc39dc277fd8` |
| Refrozen SDK executable | `f54c346ea9b162ef56e2c7eb763f51ef046f4b9dc545022339cb3650a3936230` |
| Refrozen SDK source identity | `6a2d04e691a47eb4e428ce90cdc6eb95b8ea86f0b21e084a30adbc3bff24e4fb` |
| Diagnostic bundle checksum list | `4500cd6dd691b805aab24fac2f6122241224510f67283280893aa75f03dd6ba5` |

Recipes, retained failures, local test reports and recovery records are under
`build/sdk-linux-companion/`. The corrected bundle and harness are in the
dedicated `lefony-sdk-linux-release-tests-20260915-v1` volume under
`results/closure-refreeze-v2/`. The separate Linux QEMU candidate is in the
QEMU-v5 volume at `results/qemu-stall-v4/`. These remain x86-64 tools executed
under ARM-host interpretation. Native supported hosts, credential stores, real
GitHub/store/USB, physical qualification, Windows distribution, independent
trials and final release integration remain open.

### Completed frozen companion matrix and read-only device discovery

The init-enabled Linux run passes all eleven cases: GET, chunked GET, POST,
chunked POST, denied origin, rejected TLS certificate, timeout, cancellation,
truncated response, host disconnect and terminal fragments followed by two
successful requests under the same pairing. These use the actual frozen CLI,
spawned network worker, signed ARM app, normal keypad consent and modeled USB.
Successful transfers preserve the exact 131,073-byte or 70,017-byte cache;
failed/cancelled transfers preserve the prior 31-byte cache. The harness also
checks removal of temporary download files, app exit, Home, storage cleanup and
disappearance of observed descendants. All 5,499 bundle checksum entries still
match afterward. The report hash is
`7c94bdeb564f1ff9497f1cc14a6770cede7bbea6c7140ebbb60bb36387f73172`.

The restrictive `doctor` invocation also passes. Both invalid isolation setups
(explicitly granting source access, or using a nonexistent negative-control
path) refuse execution with code 125. The tests use a read-only container root,
no external network, explicit x86-64 interpretation and Landlock protection
against source/host-Python and non-glibc system-library access. Docker's init
process reaps orphaned descendants; the earlier no-init failure remains recorded
without being counted as a pass. This is not native Linux or physical USB
qualification.

Physical activity after the emulator matrix was limited to read-only discovery.
The system-profiler USB query returned no device nodes; the direct IOUSB registry
did identify the connected Lefony diagnostic device. It answers diagnostics and
app-status reads, reporting storage protocol 2 and ABI 1 without the capability
negotiation flag required by current SDK projects. The unsupported capability
request was therefore not sent. Its updater reports idle state and the recovery
install path. Exact captures stay private under ignored build output. No firmware
was staged or installed, and no device storage was written. A matching physical
candidate, verified backup/recovery preparation and authorized update are still
required before the current SDK can receive device acceptance.

The local `build/sdk-linux-companion/evidence-v1/` copy retains the diagnostic
candidate, dependency report, source archive, doctor/stall checks and both frozen
attempts. The source archive and original build inputs are retained separately
from the diagnostic bundle; assembling updated production artifacts and their
full source groups remains the next Linux release-integration step.

## Linux production bundle and refreshed sources — 2026-09-15

The Linux distribution now has an uninterrupted production-packager pass with
the launcher, companion and QEMU fixes from the preceding diagnostic checkpoint.
This replaces the pending production-assembly step; it does not complete SDK 1.0
or native-host, physical, upstream-rebuild or release qualification.

### Public source snapshot and build inputs

Added [package_native_public_source.py](../scripts/package_native_public_source.py)
to create a deterministic archive of actual tracked and non-ignored working-tree
bytes. It applies the repository boundary checks, omits tracked deletions and
ignored build/device/key material, records normalized modes and per-file hashes,
and rejects concurrent content, mode or file-selection changes. The manifest
labels the source as a working-tree snapshot and records the base commit
separately. Existing output directories are rejected. Its
[tests](../tests/test_native_public_source.py), public-tree tests and desktop
source-archive tests pass: **21 tests**. Both actual snapshots contain 1,129 files
and produce the same archive SHA-256:
`2f56a8576743cebf17d154d7f0924fdcf48e61639ef649f5b8b3145d821459c8`.
These archives capture the source at assembly time; later qualification notes
are separate records.

A fresh full Linux x86-64 QEMU cross build passes configure, compilation,
version/display/machine probes and all three deterministic EP0 stall groups.
The checked source archive is
`8a4c141c2dd6e72ea3bc080fdd301809e3860c189d8b79fbec45e34bd421e076`.
The new input executable is
`440da313e664335914bab7cfc2680d1b052b7493acdf081e64fa6528e7576e73`;
it differs from the preceding incremental executable. Its source and build
records are retained explicitly; no byte-identical QEMU rebuild claim is made.
The relocated executable is
`dd03333a421386cbdf0066f00d8e5aa928e2b10bb77588b7b0b49df69611648e`.
The same stall groups pass again against that relocated binary.

The refreshed materials retain all 82 component records, replace the public
source/QEMU inputs, and update the QEMU freeze-input hash. Every input/notice and
the retained parent materials are rechecked; the parent is unchanged. The new
materials manifest is
`3bdfbdd906dc67d0edb281ec454c4473bc7ae3d9fe2558af1937dc178bfa2a63`.
The full packager enforces the original 159 native, 1,101 target and pinned
bootloader inventories. Its 160-ELF dependency audit includes the launcher,
without inherited or injected library paths. The exact prepared firmware source
and earlier byte-identical VM rebuild remain bound to ELF
`5a0636eb915aaf8ea62b889932ee0538ca20c9371334905a970406bc58680105`.

### Completed artifacts and runtime checks

The actual `package_native_desktop.py` invocation exits 0 in **930.007 seconds**,
including source checks, full freeze, relocation, smoke checks and final archive
creation. This run does not resume an interrupted archive. The candidate JSON is
`da52cb23fbe63b1411386e578b62c39b9d5e9659df50619d7ac28c2944b55a62`.
The four completed artifacts are:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Linux x86-64 SDK | 208,432,416 | `f5df7a687789250ab1b62de1358c4490d7a4552a934ec8da15ab26003bf87841` |
| Toolchain sources | 180,138,009 | `adbac52c1f9a089ca9c524dbbf7a8ce5a139cdeabc4338d690008804e1efcc66` |
| Runtime sources | 787,380,542 | `12f9f3f17fa719e9e5ca43590cac34e25a8cd4959ca1dea556f55cabce9e7531` |
| Lefony/QEMU/prepared-firmware sources | 51,857,549 | `a6b548708487881fde6723111b6b292b9612d378b81195245ed863cf7302580a` |

All four are copied back to ignored workspace output and independently checked
against these hashes and sizes. The source verifier checks every archived file,
not only listed source inputs: 28 toolchain files, 4,254 runtime files and three
nested project-source archives. It also verifies the complete manifests. The
original post-generation verifier repeatedly sought through compressed archives;
a stronger sequential check passed in 3.993 seconds, after which the redundant
verifier was stopped (exit 137). Source generation had already completed, and
no archive bytes were changed. That interruption is retained rather than counted
as an uninterrupted verifier pass. The production binary packager completed
normally and independently.

After extraction into a separate volume under a path containing spaces and an
accented character:

- **48 minimal-Ubuntu commands pass:** direct helpers and ARM compilation, eight
  external templates, startup/source export, temporary private signing,
  workspace clone/export/restore/cold launch and Notebook/UI Gallery previews.
  The image has no system Python, ARM compiler or QEMU, no network and no mounted
  source/build/component trees. Both preview frames were inspected; the Notebook
  expression/result and Gallery editing controls are legible.
- Bundled GDB reaches the source breakpoint, reads `argc = 2`, steps and detaches.
  External CMake configures/builds/inspects a C project using the bundle.
- **All eleven frozen companion cases pass:** GET, chunked GET, POST, chunked
  POST, policy, TLS, timeout, cancellation, truncation, disconnect and repeated
  requests. Commands and spawned workers use the actual frozen CLI, normal
  keypad pairing and model USB. The terminal case observes one policy error
  followed by two successful requests within one pairing. Successful cache bytes,
  previous-cache preservation, temporary-file removal, app/Home cleanup and
  disappearance of observed workers are checked. The report is
  `377c3a8f841ecc4e19e98158ed7eecbb6b8c6e9043f5b14a22f2ed66886b2059`.
- Strict Landlock doctor passes with only system glibc/loader access permitted.
  Both wrongly granted source access and a missing negative-control path refuse
  execution with code 125. The companion uses the same restriction, a local TLS
  fixture, no external network and Docker init for descendant reaping.
- All **5,505 bundle checksum entries and 13 symlinks remain unchanged** after
  the complete workflow matrix. Final distribution assembly checks source and
  binary identities against the same candidate and source manifest.

These are explicit x86-64 interpreter runs on Linux ARM64 in the dedicated SDK
VM, not native x86-64 desktop or physical-USB measurements. The interpreter hash
remains `d02e1860d3a9130557e627e11751a7ef82acb985b1db17dc864a9a4cbea79abf`.
The SDK remains an experimental `0.2.0-dev` candidate; no stable version or
release trust root was silently changed.

### Capacity and physical preparation

Before building, the dedicated SDK VM had about 200 MiB free. Its stopped data
and root disks were cloned and their hashes checked against the originals.
Only that VM's data disk was expanded from 32 to 48 GiB; it then had about 16 GiB
available. The default VM/context remains separate. Retained snapshots and
capacity records are under `build/sdk-linux-production-v2/capacity/`.

Physical preparation was offline. The retained physical firmware and verifier
inputs still match their earlier build checkpoint. A new recovery capsule wraps
that exact physical payload, with no payload changes, and passes installer image
size/magic checks. Its SHA-256 is
`89561df0ba972e1ca7265849ee8a34c8e26d3650a62346c75663b08edd415dd8`
(2,105,488 bytes). It is unsigned and is not ready for running-device update.
All four existing recovery assets and UUU are available. This checkout has no
U-Boot history; the migration notes lead to the original checkout's retained
`lefony-nand-boot-verified` baseline, whose hash and boot contract pass inspection.
No history or release identity was regenerated. No calculator command, reset,
flash, provisioning, restore or physical readback was performed in this batch.
Verified backups, signing/version preflight and authorization for the concrete
physical operation remain required.

Local scripts, logs, artifacts and the evidence snapshot are retained under
`build/sdk-linux-production-v2/`. Physical preparation records stay separate
from the source/distribution evidence. Windows distribution, native desktops and
credential stores, upstream binary rebuilds, coordinated website/download/signing
release work, real GitHub/store journeys, physical USB/input/performance/power-loss
and durability acceptance, and independent developer trials remain open. This
checkpoint is verified progress; the SDK 1.0 goal remains active.

The retained evidence snapshot contains 273 files / 15,066,222 bytes. Its index
SHA-256 is `7dc4d9eb908a919d18000e2ae606f7a1920e9f89f9feb1b7afe1e5ff5edcbe58`.

## Installer qualification guard and physical read-only capture — 2026-09-15

Physical preparation exposed an installer gap: when the U-Boot catalog had no
qualified entry, its fallback selection could pass image/hash/boot-contract
checks and reach installation staging. Manual selection had the same gap.
`validation_errors("install")` now requires the existing qualified-status set
before staging a write operation. Read-only U-Boot comparison remains available
for unqualified entries. No qualification status, boot contract, signature rule
or release identity changed.

Regression coverage checks the fallback and manual-selection routes, each
unqualified status and every accepted existing qualified status. The retained
pre-fix run reached the mocked staging path and failed eight cases. After the
fix, the installer/history subset passes **55 tests and 10 subtests**.

### Bounded OS capture

The new `scripts/prime_g2_readonly_os_capture.py` wraps the existing physical
slot-A page-read protocol in a transport allowlist. Only updater status, page
status/data and zero-payload page-read triggers are accepted. It validates the
zImage header and slot bounds, rejects a busy updater, pending boot, active slot
B, bad-block marker or changed updater state, and reads the declared capsule
length twice. Each USB transfer is bounded and each page checks the total
deadline. Two matching hashes are required before the completed output directory
appears; failures retain private partial data and an error report.

The connected Prime G2 still runs an older capsule, with updater version
`1.0.0+1789107216`, active slot A, no pending boot and idle state. Its app status
does not advertise current SDK capability negotiation. Read-only diagnostics
remain responsive before and after capture. The exact command was:

```sh
.venv/bin/python scripts/prime_g2_readonly_os_capture.py \
  --output build/sdk-physical-preflight-v1/os-capture-v1 --timeout 600
```

Both physical reads and an independent host byte comparison pass:

- **2,103,248 bytes**, SHA-256
  `f84dd8fd1cdd3a6ec5fa4564f95285a9fab658a1298a0a5f5ae07a31891a9978`.
- **1,027 pages per pass**, 2,055 page-read triggers including the initial
  header probe, **189.855458 seconds**, zero reported corrected bits.
- Updater state unchanged; no NAND programming, staging, reset, provisioning,
  restore or migration was performed.
- No matching artifact was found in either retained OS build catalog. The
  capture was not imported or promoted into a qualified build history.

These are BCH-corrected installed OS bytes, excluding OOB, bootloader and
app/user data. They establish a successful physical read-only USB path for the
older installed image. They do not qualify the current SDK candidate or prove
power-loss recovery, endurance, electrical behavior, input feel or performance.
The raw captures remain private under ignored `build/`.

### Validation and next physical gates

The new capture tests cover exact rereads, partial-output handling, cancellation,
timeouts, changed media/state, malformed headers, short data, active slot B,
bad-block markers, disallowed USB requests and output conflicts. The first
attempt used a reserved pytest parameter name; after that fix, a test comparing
a tuple-valued in-memory report with its JSON list representation failed. The
assertion now compares JSON-normalized values; neither issue changed the device
capture logic. The final capture/USB subset passes **53 tests**.

`make test` passes **1,640 tests, 2 skipped in 348.97 seconds**. Both skips require
private hardware-reference fixtures. Firmware/driver code is unchanged in this
checkpoint; the retained physical and VM candidate hashes remain the earlier
builds. Public-tree, whitespace, documentation and source-snapshot validation
are recorded alongside the test logs in `build/sdk-physical-preflight-v1/`.

Full NAND/OOB and app-data backups still precede any update. The existing
recovery assets and return-from-recovery helpers are available, but macOS UUU
requires administrator access and a noninteractive `sudo -n true` probe reports
that a password is required. No recovery transition or administrator dialog was
started. Candidate signing/version checks, verified full backups and explicit
authorization for the concrete installation remain outstanding. The earlier
Linux production archive/source artifacts retain their own source checkpoint;
these later host-tool changes are not silently attributed to that bundle.

Windows/native-host distribution and credentials, coordinated release/download
and real store/GitHub journeys, physical SDK/input/performance/power-loss and
durability acceptance, and independent developer trials remain open. This is
verified progress; the full SDK 1.0 goal remains active.

## Windows GDB component and dependency sources — 2026-09-15

The existing Windows GDB cross-build route now completes. GDB 17.2 builds on
the dedicated ARM64 Linux VM with MinGW POSIX cross tools, targeting a native
Windows x86-64 host and ARM app debugging. The combined successful dependency
and debugger job exits zero in about 338 seconds. The original GDB recipe,
version and archive pin are unchanged. Windows execution was not attempted.

`scripts/build_sdk_windows_gdb_dependencies.py` and its checked
`scripts/sdk-windows/gdb-dependencies.json` provide the missing GMP/MPFR/Expat
build step. All nine exact retained Ubuntu source inputs pass SHA-256 checks
before extraction. `dpkg-source` applies the original downstream patches.
GMP regenerates its configure files; Expat uses upstream `buildconf.sh`.
The build retains sources, notices, hashes, commands and recipes; output and
scratch paths are explicit, and no system installation or download occurs.
The standalone source kit now includes the new recipe, source pins and
`scripts/sdk-windows/Dockerfile.gdb-cross`.

### Exact component and checks

- Windows executable: **12,530,535 bytes**, SHA-256
  `51147d86b6f9ddebe8188a193e729686141882382c2ad00e56607b8dc1273568`.
  Its GDB candidate manifest is
  `538c6c4e35fb0d6b8ce9bc7e8296c7319df2675ef8cb1779b4e2f8a99e9fe089`.
- The PE audit checks GDB and its three required MinGW DLLs:
  `libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll`. Their non-system
  imports resolve within that retained set. Windows system imports are explicitly
  recorded as declarations awaiting verification on Windows; no system directory
  or loader is simulated to manufacture a native pass.
- All **790 static-library members** are x86-64 COFF: GMP 530, MPFR 257,
  Expat 3. Each library has identical bytes from two complete builds. Their
  SHA-256 values are respectively
  `026efe038fd9192dc4f2a436e3dd4d788b23c957109eba85dbeea0075bb04eec`,
  `6de813b7dc582e86609fff8599143f51cc3ffbb0d0f745f5fe739429bfbe495b`,
  `45cbd6e62c069e03bcf4b80a5f5b0a02390266b9a0871913444009577af66bd4`.
  GDB itself was built once; no repeated GDB byte-identity claim is made.
- The build-input archive contains **214 verified files / 161,093,575 bytes**,
  SHA-256 `7416b08b65632fcd3f88aeb0c7794e5ff4fb2b80a67ccd6a1ad025ee28b035f4`.
  Its executable/DLL folder, original GDB candidate, dependency inputs and
  notices, runtime sources and source-collection records are retained. This
  archive is one component, not a Windows SDK release.

The MinGW runtime source packages are `gcc-mingw-w64` 26.1 and `mingw-w64`
11.0.1-3build1. The compiler/runtime package version identifies GCC
13.2.0-6ubuntu1 as its separate base source. That exact descriptor, original
archive and Ubuntu patch archive were retrieved from the official Launchpad
source record, checked against the descriptor hashes and extracted successfully.
Both MinGW source packages also extract successfully. A source descriptor's
hash check is not represented as a signature-verification or upstream
reproducible-build result. The ARM app compiler pin remains 16.2.0.

### Retained failures and validation

The first image attempt passed a local image ID as Docker's `FROM` reference;
BuildKit treated it as a registry name and rejected it. The second attempt used
the retained tag with its resolved image ID recorded and completed. The first
dependency attempt stopped at GMP's excluded documentation reference in the
shipped configure script. Regenerating configure, as the Debian recipe does,
fixed that failure. The second attempt compiled GMP/MPFR but Expat rejected
plain autoreconf because its configuration-header adjustment was missing.
Using Expat's own `buildconf.sh` fixed that failure. Each failed attempt retains
its source inputs, commands and scratch tree; later attempts use fresh outputs.

A subsequent recipe-retention correction preserves the source-pin subdirectory,
so the copied recipe can locate its own pins independently of the checkout.
The corrected recipe completes a second dependency build with the matching
library bytes recorded above. GDB's original candidate retains its actual first
successful dependency-build provenance; it is not silently rebound to a later
recipe. Tests cover the independent retained recipe, changed/missing/symlinked
source inputs, a source-copy race and preservation of exact source inputs.

**66 focused host tests pass** for dependency/source retention, desktop
packaging, source-archive validation and public-tree handling. The real build
and component audit pass with network disabled. Source collection uses separate
network-enabled jobs. Public-tree, whitespace, document-link and reproducible
source-kit checks are retained with local artifact verification under
`build/sdk-windows-gdb-v1/`. The component archive is under its `artifacts/`
directory. Neither firmware target changed in this checkpoint.

Native Windows GDB startup, source/pipe debugging, compiler/QEMU/OpenSSL/libusb
inputs, complete frozen Windows packaging and clean-host/credential tests remain
open. The Linux production bundle remains at its prior checkpoint. Coordinated
publication/download/signing, real store/GitHub journeys, physical SDK and
power-loss/durability acceptance, and independent developer trials remain open.
The full SDK 1.0 goal remains active.

## Windows compiler prerequisites and initial build — 2026-09-15

The Windows compiler dependency build now completes using the retained Windows
GMP/MPFR candidate and twelve exact Ubuntu source files for MPC 1.3.1, ISL 0.26,
zlib 1.3 and zstd 1.5.5, including their recorded downstream patches. The new
`scripts/build_sdk_windows_compiler_dependencies.py` verifies the selected base
candidate and each copied file, then builds the additional static libraries.
`scripts/sdk-windows/compiler-dependencies.json` holds their source pins.

The first attempt compiled MPC but failed to link it because copied libtool
metadata still referenced the prior installation prefix. The corrected recipe
relocates only `.la` and `.pc` text metadata, retaining before/after hashes for
six files. All base library bytes remain unchanged. The failed output/scratch
tree remains separate from the successful second attempt.

The successful dependency candidate is
`458161ef0a898c4552b9e57a8392f09139ef2bf6dee411dda75c6c9836b00b18`.
Its parent is the verified Windows GDB dependency candidate
`47bbf8dffaa5646a38f88cb66ebfacd63e27df291bdd4e6ee5ca4eee49774239`.
Independent inspection verifies all **114 installed files**, all twelve source
archives and the retained recipes. All **1,005 archive members** are x86-64
COFF: GMP 530, MPFR 257, Expat 3, MPC 86, ISL 81, zlib 15 and zstd 33.
The zstd archive includes its multithreading implementation. No Windows program
was executed to establish these results.

`scripts/build_sdk_linux_cross.py` now accepts `--windows-host` and an explicit,
checksum-selected Windows dependency candidate. The Linux default preserves
its existing configuration. The Windows route keeps native ARM64 build tools,
Windows host executables and ARM runtime objects distinct. GCC 16.2.0,
binutils 2.47 and the existing ARM multilib selection remain pinned. The new
branch checks produced PE binaries and records its native-tool ARM runtime link
probe separately from Windows execution.

At this checkpoint, the first full Windows compiler build is **running** in
`lefony-sdk-windows-compiler-v1` on the dedicated SDK Docker context. Binutils
configure/build/install and GCC configuration/frontend build/install have passed.
All **46 installed Windows executables**, including 16 binutils programs, pass
PE inspection. Their imports are limited to `advapi32.dll`, `kernel32.dll`,
`msvcrt.dll`, `ws2_32.dll` and the retained `libwinpthread-1.dll`. The ARM multilib
runtime build is still active. Compiler completion, runtime-library completion
and Windows frontend execution are not inferred from those PE results. Continue
by inspecting the actual container state and existing job handle; an earlier
snapshot alone does not establish whether that job is still running.

**38 focused host tests pass** for source/base-candidate validation, metadata
relocation, build-host separation and existing toolchain/source helpers. The
source kit includes the new dependency recipe and pins. Evidence, source-kit
and public-tree checks are retained under `build/sdk-windows-compiler-v1/`.
The build volume had about 7 GiB free at the start of runtime compilation; no existing
candidate, VM disk snapshot or private recovery artifact was removed.

The pinned QEMU sources contain the Windows AF_UNIX implementation used by the
SDK's local-socket adapter. That source inspection is not native socket testing;
Windows QEMU and complete frozen SDK assembly remain unfinished. A Windows
x86-64 execution environment is still needed for actual packaging, compiler,
debugger, credential-store and clean-host acceptance. No physical operation,
publication, firmware pin, storage layout or release identity changed in this
checkpoint. The full SDK 1.0 goal remains active.

## Windows compiler and host-library components — 2026-09-15

The compiler job from the preceding checkpoint completed successfully. Separate
libusb and OpenSSL components now also build from retained source packages.
These are inputs for Windows distribution; no native Windows program ran and
no full Windows SDK, signing or physical USB qualification is claimed.

### Compiler completion and exact audit

The existing GCC 16.2.0/binutils 2.47 job completed all configure, compiler,
installation and ARM runtime phases, using the same verified dependency candidate
`458161ef0a898c4552b9e57a8392f09139ef2bf6dee411dda75c6c9836b00b18`.
The final compiler candidate manifest is
`b040c8dabe495588ef89045affd886738f4e3fdbf7f150168d0e7c3db379e3d6`.

- All **550 installed files / 648,566,713 bytes** match the final manifest.
  All source archives, retained recipes, dependency/base candidates and command
  records also verify against their hashes.
- The audit covers **46 compiler PE files**, plus the three retained MinGW
  runtime DLLs. Non-system imports resolve to that retained runtime set.
  Windows system imports remain declarations awaiting an actual Windows loader;
  no synthetic system-directory check was used.
- All **78 ARM archives** (libgcc and libgcov for **39 multilib variants**) contain
  **70,105 ARM ELF objects**. The Cortex-A7 hard-float probe links the newly built
  libgcc with native ARM build tools. An independent symbol check confirms
  `__aeabi_uldivmod` is defined, rather than left unresolved in the relocatable
  output. The selected libgcc SHA-256 is
  `17159bd2c85b639648f541dd4ad99bef5fccf1382d81fad618c9887fa20627c8`.
  This proves the selected target-runtime link, not Windows C/C++ compilation.
- The component archive has **912 verified files / 452,146,169 bytes**, SHA-256
  `3e43b03bd33d5aff05ab5d6ad07a89e33b6eb1e997d1170a3af2583c3c20ff5a`.
  It retains the original compiler installation, exact build records, compiler
  dependency inputs, base dependency sources, MinGW runtime DLLs and sources,
  matching GCC 13 base sources, source-collection recipes and notices. Scratch
  compilation trees stay outside the archive. An independent macOS extraction
  rechecks every archived file against its manifest without executing PE files.

Compiler audit report SHA-256:
`81a1d292b31471c99c1c4811dc78aeb1660d1ed40247e590a3442d8089845715`.
Local evidence and the archive are under `build/sdk-windows-compiler-v1/`, with
`artifacts/` and `component-extracted-v1/` retaining the transferred results.
The original build and dependency candidates remain unchanged.

### libusb and OpenSSL

The new [libusb recipe](../scripts/build_sdk_windows_libusb.py) uses Ubuntu's
`1.0.27-1` source package. Extraction, autoreconf, cross configuration, shared
and static builds, and installation pass. All six installed files and four
source files verify; the DLL exposes 154 exports including the required USB
entry points. It imports only declared Windows system DLLs. Its SHA-256 is
`3efa44d0ebc93f8dc851e7a1ecbbad5fbb9d5f64309b56a2cb3beabe4be1c5dd`;
the candidate JSON is
`18f7a56124cebd1391e96802fbc845581483d0779e8914d3bb4b564e5b7ad0af`.
No device was enumerated or accessed.

The new [OpenSSL recipe](../scripts/build_sdk_windows_openssl.py) retains the
same security-patched Ubuntu `3.0.13-0ubuntu3.15` source package as the Linux
production materials. Two real cross-build failures were resolved, with each
failed output and scratch tree retained and each retry using a fresh candidate:

1. The first build failed on AVX-512 unwind-label decoration. The unmodified
   upstream [OpenSSL commit 224ea84](https://github.com/openssl/openssl/commit/224ea84b4054de105447cde407fa3d39004a563d)
   fixes six lines in the assembly generator/translator. Its exact patch is
   checked in and copied into each subsequent candidate.
2. The second build passed assembly but failed linking Ubuntu's added
   `crypto/fips_mode.c`, which calls glibc-only `secure_getenv`. A retained
   three-line adaptation includes the existing OpenSSL declaration and uses
   `ossl_safe_getenv` for both calls. That existing wrapper provides the
   platform-specific privilege/environment behavior. No FIPS qualification is
   implied. The third build passes configure, build, install and PE/export audit.

Both patches require exact source/patch hashes before modification and exact
result hashes afterward. Already prepared inputs are accepted without reapplying;
unknown or mixed contexts fail. Source versions and Ubuntu security patches stay
pinned. The [patch notes](../scripts/sdk-windows/README.md#openssl-patches),
Apache-2.0 text and component notices are included in source distribution.

All **157 OpenSSL installed files** and three source archives verify. The audit
checks the executable, both main DLLs, three engine DLLs and the legacy provider.
The crypto/SSL DLL export tables contain 5,376 and 517 named exports respectively.
Required APIs are present, and all non-system imports resolve within the retained
component. The executable SHA-256 is
`23ff19d7430d5d8b71be78f0f3c47760cb7210a574bb5ca5b90acf1095c4e622`;
the candidate JSON is
`3ee40dd1e882a1d058d0dec4719c765f2d289f54d68a989511139737b2bc1033`.

The combined library component archive contains **206 verified files /
23,147,111 bytes**, SHA-256
`df4ec78b438374b955b25d74a659eabaf23b9d25faa63e144619f6f0c4685845`.
It includes both original candidates, source archives, notices, actual recipes,
patches, logs and complete installations. Its independent audit report is
`bcc2060c9ae3e6cdbcaddabf2b26c704f3fb99c2ae7127be577b20b96d26f172`.
The archive and exact independent extraction are retained under
`build/sdk-windows-openssl-v1/`; original libusb logs remain under
`build/sdk-windows-libusb-v1/`.

OpenSSL's configuration, provider and engine files are retained, but its configured
prefix is `/opt/lefony-sdk/openssl`. Relocated Windows configuration/module paths
still need desktop integration and native private-signing checks. No keys were
generated. The compiler similarly requires runtime DLL placement and native
relocation/CMake/app-build checks before desktop acceptance.

### Validation and remaining work

**91 focused host tests pass**, covering source-copy failures/races, checked
patch contexts and repeated preparation, dependency/source retention, compiler
build-host separation and desktop packaging. The real builds and component audits
run with network disabled; the upstream patch was fetched separately and pinned.
Both transferred archives pass an independent exact-file extraction check.
Source-kit reproducibility, extracted recipe checks, public-tree, whitespace and
document links are checked in the checkpoint validation retained alongside the
library evidence. No firmware target changed, so neither firmware was rebuilt.

Windows QEMU and its native dependencies, complete frozen desktop assembly,
native Windows execution/credential stores, native Linux/macOS clean-host checks,
coordinated release/download/store/GitHub journeys, physical input/USB/performance,
power-loss/flash durability and independent developer acceptance remain open.
No publication, connected-device write, storage layout, trust root or release
identity changed. The full SDK 1.0 goal remains active.

## Windows QEMU dependency build — 2026-09-15

The new [Windows QEMU dependency recipe](../scripts/build_sdk_windows_qemu_dependencies.py)
completes all nine libraries: libiconv, gettext, libffi, PCRE2, zlib, GLib,
SDL2, pixman and libusb. Its final candidate manifest is
`6ea2750750dc8f61630a065def34574a7125c2ea9e9bc7ad57555ef1aba5a9b5`.
An independent audit verifies all **935 installed files**, **38 Windows PE
binaries**, exact sources/recipes, required public exports and the final file
hashes supplied by each component. Non-system DLL imports resolve to retained
libraries or the existing MinGW runtime. The Windows system DLL declarations
still require native loader checks. No Windows executable ran and no USB device
was accessed.

The [source pins](../scripts/sdk-windows/qemu-dependencies.json) retain these
existing Ubuntu packages:

| Component | Retained source version |
| --- | --- |
| libffi | 3.4.6-1build1 |
| PCRE2 | 10.42-4ubuntu2.1 |
| zlib | 1.3.dfsg-3.1ubuntu2.2 |
| GLib | 2.80.0-6ubuntu3.8 |
| SDL2 | 2.30.0+dfsg-1ubuntu3.1 |
| pixman | 0.42.2-1build1 |
| libusb | 1.0.27-1 |

GNU libiconv **1.19** and gettext **1.0** are additional Windows source inputs.
Their archives and signatures were fetched from the GNU release server and
retained. Both signatures verify against Bruno Haible's key
`E0FFBD975397F77A32AB76ECB6301D9E1BBEAC08` in the GNU keyring. The gettext
release announcement identifies that fingerprint; this is source-input
verification and does not change calculator/app signing identities.

- libiconv archive SHA-256:
  `88dd96a8c0464eca144fc791ae60cd31cd8ee78321e67397e25fc095c4a19aa6`.
- gettext archive SHA-256:
  `71132a3fb71e68245b8f2ac4e9e97137d3e5c02f415636eb508ae607bc01add7`.

GLib requires gettext even when translation catalogs are disabled. This build
uses real libintl with libiconv and **native language support enabled**; the
proxy-libintl fallback is not used. It retains normal GLib guards/assertions,
Windows threading, all three PCRE2 character widths/JIT, SDL's Windows backends,
pixman and libusb. zlib uses the previously proven static MinGW build path.
Build-time tests, introspection and generated API documentation are omitted;
this is not native runtime qualification. Exact archives, downstream patches,
notices and the actual build recipes accompany the dependency candidate.

### Build corrections and evidence

Three failed dependency attempts remain under the ignored build volume, with
source inputs, commands, logs and scratch trees. Each retry used a fresh output:

1. The first attempt built libiconv, then failed locating gettext's `config.guess`.
   The recipe now searches the complete source root, since gettext-runtime uses
   the parent's build utilities.
2. The second built libiconv/gettext, then libffi's autoreconf failed because
   `LT_SYS_SYMBOL_USCORE` was unavailable. Adding the build-host `libltdl-dev`
   package supplies the required libtool macro without modifying libffi.
3. The third completed through GLib, then generic autoreconf failed on SDL's
   manually maintained configuration-header template. Using SDL's own
   `autogen.sh`, which deliberately avoids autoheader, resolves that failure.
   The fourth attempt completes all nine libraries and installation steps.

Pixman's cross build emits libtool diagnostics about uninstalled executable
wrapper paths. The build and installation exit successfully; its temporary test
programs were not run. Those messages do not establish native test success.
The installed library passes PE/export checks. Native Windows tests remain open.

The dependency audit report SHA-256 is
`1879a0b8c9114f19eb46acc389ad9789d0636f470921f8eee25f9469c33657a1`.
Evidence is retained under `build/sdk-windows-qemu-v1/`, including the final
candidate, independent report, GNU downloads/signature records, build-image
identities and failed-attempt logs. The recipe, source pins and build image
are included in the standalone SDK source kit. The host guide documents the
[dependency and QEMU commands](../sdk/HOSTS.md#windows-qemu-cross-build-recipes).

The prepared QEMU archive is exactly the Linux production input, SHA-256
`8a4c141c2dd6e72ea3bc080fdd301809e3860c189d8b79fbec45e34bd421e076`.
Its Prime model, header and BCH source hashes independently match the current
repository files. An initial audit lookup missed the archive's leading `./`
member names; normalizing member paths resolves that lookup and all three
source comparisons pass. This was a verifier path error, not a source mismatch.

The new [Windows QEMU build recipe](../scripts/build_sdk_windows_qemu.py) verifies
the dependency candidate's hash, exact file set and content before using its
pkg-config metadata. It consumes the prepared source archive, enables ARM
softmmu/internal FDT/SDL/pixman/libusb and records native build-tool identities.
The first QEMU attempt stopped during offline Python bootstrap because the
image lacked wheel/pip. The second reached Meson but needed an explicit native
pkg-config executable. Adding those build tools and setting `PKG_CONFIG` with
the isolated Windows metadata directory resolves both configuration failures.
The third attempt reaches actual Windows compilation. Native Windows execution,
complete frozen packaging, credential stores, publication/download journeys,
physical qualification and independent developer acceptance remain open.

### Completed Windows QEMU component

The third QEMU attempt finishes all **2,014 Ninja build steps** and
links `qemu-system-arm.exe`. Its final candidate manifest is
`05ee0a95441450de0e812152e2c2c349862e4b3ba9b44dc1c0fd82daa21903e1`.
The executable is **104,723,486 bytes**, SHA-256
`5b499b64a5a8e8d833a387bff549cc6f72fa17ee6c29c7b6bb1cbf791dc22a76`.
No Windows process was executed by this cross build.

The independent component audit verifies the executable, source archive,
actual build recipes, command records and matching dependency candidate. Its
configuration defines Windows, SDL, pixman, libusb and FDT; the linked binary
contains the Prime machine identifier. The dependency audit covers **43 PE
binaries** across QEMU, its library installation and MinGW runtime inputs.
Non-system imports resolve within the retained component. These checks do not
substitute for native machine/display listings, guest boot, local sockets or
physical USB tests.

The first component audit incorrectly expected numeric `1` values in QEMU's
boolean definitions and used the wrong libusb macro name. The generated header
uses defined/undefined macros, including `CONFIG_USB_LIBUSB`; the corrected audit
checks that actual format. The second correctly found an additional dependency,
`libssp-0.dll`, for the enabled stack protector. The third includes it and passes.
Its SHA-256 is
`7fcc5573b9d6023dc28d7a53e188829230d81915bbb47b56bc3d5ab296b2f201`.
The DLL's package is `gcc-mingw-w64-x86-64-posix-runtime`
`13.2.0-6ubuntu1+26.1`; its source is `gcc-mingw-w64` 26.1 with GCC base
`13.2.0-6ubuntu1`. Those exact source inputs are already retained and verified.
It is included as a third-party runtime, not classified as a Windows system DLL.

The resulting archive has **1,161 verified files / 249,842,124 bytes**, SHA-256
`cab5e0ba68b6e6fa51c5afabd5be0a4cecf6af42d0dad6e0e0b729a03251e38b`.
It retains QEMU, the complete dependency installation, original source archives,
patches, notices, MinGW runtime binaries and corresponding source inputs, GNU
source-signature evidence and actual build/audit recipes. Original candidates
remain unchanged. Audit report SHA-256:
`4606869f636950f082d0b0a81e56686918561002a9b325767b78a0f47492e71c`.

**113 focused host tests pass**, covering source bounds/paths/copy races,
independent retained recipes, dependency identity/content/file-set rejection,
missing required metadata and existing packaging/library checks. The transferred
archive also passes an independent exact-file macOS extraction. Source-kit
reproducibility, extracted recipe entry points, document links, public-tree and
whitespace checks are retained under `build/sdk-windows-qemu-v1/`. The archive is
under `artifacts/`; its verified extraction is `component-extracted-v3/`.
All compilation/audit jobs use disabled networking. GNU source collection and
build-image package installation use separate network-enabled steps.

Windows compiler, debugger, QEMU, libusb and OpenSSL component archives now
exist with source records. Full frozen Windows assembly, OpenSSL runtime-path
integration, actual native Windows execution/credential stores and clean-host
acceptance remain open. Linux/macOS native qualification, matching releases,
real GitHub/store/download journeys, physical input/USB/performance/power-loss/
flash durability and independent developer trials also remain open. Neither
firmware target, storage layout, release identity nor a connected device was
changed. Nothing was committed, pushed or published. The full SDK 1.0 goal
remains active.

## Windows OpenSSL runtime packaging — 2026-09-15

Windows packaging now requires the complete OpenSSL build candidate through
`--openssl-runtime`, alongside its `install/bin/openssl.exe`. The new
`native_desktop_openssl.py` verifies every installed file, the original source
archives and actual build recipes before staging. The corresponding-source
manifest must bind a `windows-openssl` component to those exact inputs/version.
Configuration, providers and engines retain their original bytes under
`_internal/openssl`; dynamic DLLs participate in dependency collection, and the
resource file set/hashes are checked again after freezing. A separate runtime
record is hashed into the desktop candidate.

Frozen Windows signing selects the absolute bundled executable and supplies
configuration/include/provider/engine paths derived from the extracted location.
The paths affect the OpenSSL child process. Source-host configuration and Python
HTTPS trust configuration retain their existing behavior. Missing bundled data
fails before launching OpenSSL. The implementation uses the documented
[OpenSSL environment overrides](https://docs.openssl.org/3.0/man7/openssl-env/).

The native Windows packaging smoke check now loads default/legacy providers,
creates a CSR in memory using the existing public emulator fixture key, signs
and verifies a message, and rejects a changed message. It generates no key or
certificate. This check is implemented but has not run on Windows. The initial
macOS negative-control attempt incorrectly assumed `dgst` would reject malformed
configuration. It succeeds on that host, so the corrected control uses `req`,
which actually consumes the configuration file. The failed attempt is retained.

The real retained Windows OpenSSL candidate passes the new verification:
**157 installed files and 11 copied runtime-resource files**. The resources also
pass after moving to a directory containing spaces. A distinct native macOS
OpenSSL 3.6.3 run exercises the same smoke function, using the retained Windows
configuration with native macOS providers/engines. It passes provider loading,
CSR creation, 256-byte RSA signing, verification, changed-message rejection and
the malformed-config negative control. This is host logic/configuration evidence;
no Windows PE executable or DLL was executed. Verification report SHA-256:
`9195350d78bd7689c0e390339045e29f2353add72675c39e00195df24a713364`.

**321 focused tests pass**, including candidate/source/recipe tampering,
missing/extra files, path and symlink escapes, copy races, post-freeze changes,
relocation, child-only environments, real host signing, private-key/output
boundaries, SDK package/archive contracts, text encoding and GDB transport.
The standalone source-kit allowlist now includes the runtime helper and both
desktop binary/source packagers. Exact repeated source archives, extracted
entry-point checks, public-tree and document-link checks are recorded under
`build/sdk-windows-openssl-runtime-v1/`, alongside both smoke attempts.

Full frozen Windows assembly, its Python/native source inventory, native host
execution and credential-store checks remain open. The Windows host request
has no answer yet. Real publication/download journeys, physical USB/input/
performance/power-loss/durability and independent developer acceptance also
remain open. This checkpoint changes host packaging and signing tools only;
firmware targets, source pins, storage layouts and release identity are unchanged.
No connected-device write, commit, push or publication occurred. SDK 1.0 remains
an active goal.

## Windows Python wheel and source inputs — 2026-09-15

The new Windows Python source lock selects **CPython 3.14.7 / x86-64** as the
reviewed packaging environment. This is a new Windows input selection; existing
macOS/Linux Python installations, firmware pins and component candidates remain
unchanged. The five desktop requirements keep their existing versions. Explicit
Windows marker evaluation resolves 14 packaging wheels, including
`pywin32-ctypes` for Credential Manager, without selecting the Linux credential
backend or importing/executing a Windows wheel.

`windows_python_sources.py` verifies archive hashes/sizes, compatible wheel tags,
metadata and dependency closure, the complete wheel RECORD, case/path/link
boundaries, native file mappings and copied source/license inputs. It collects
14 Python source distributions and 17 embedded Pillow library/build archives.
Pillow's wheel license inventory, SBOM and complete Windows build recipe identify
its static libraries; the source maps also include libavif's AOM/dav1d/libyuv/
sharpyuv inputs and the FreeType/HarfBuzz/Brotli/PNG inputs. PyInstaller's sdist
contains its bootloader and bundled zlib source, and setuptools retains launcher.c.
Source notices and patent files accompany the archives. Optional runtime-loaded
FriBiDi is absent from this wheel and its dynamic loading is not qualified.

The original resolver selected nested setuptools vendor METADATA files as if
all were the distribution metadata. The corrected resolver selects the single
root dist-info METADATA and preserves nested metadata/notices separately. The
first embedded-source collection also stopped on three changed Gitiles archive
hashes. Fresh AOM, libyuv and libwebp archives have different container bytes but
match the retained sources' complete file contents and modes (1,445, 187 and
343 files respectively). The candidate uses the original hash-pinned copies;
fresh downloads and the comparison remain retained. The HarfBuzz source comes
from its upstream 14.2.1 release. No source hash gate was bypassed.

Both desktop binary/source packagers require the Windows Python source records.
Before freezing, the binary packager requires the reviewed native CPython
version and verifies installed wheel bytes, including Python code and native
files; pip's rewritten top-level RECORD is excluded from the installed-byte
comparison. A hashed `windows-python-inputs.json` records this pre-freeze input
check. It does not claim a complete frozen CPython/tool dependency inventory.
Extra symlink directories in source materials are rejected before notice copying.
The source-kit allowlist includes the collector, lock and offline requirements.

The final materials contain **344 recorded files** plus their manifest, across
15 source components. A separate offline wheel layout has **1,922 files**;
**1,908 installed input files** pass the byte comparison, and a changed
`PIL/Image.py` fails it. The **20 PE files** comprise 14 x86-64 files plus four
x86 and two ARM64 setuptools build launchers. Pillow and PyInstaller are all
x86-64. The audit records native imports and source identities without executing
any PE input. `python314.dll` and `vcruntime140.dll` are explicit remaining
runtime inputs. CPython and Microsoft runtime source/license inventory remains
open, as do native Windows APIs, Credential Manager and full frozen assembly.

The Windows input archive has **349 files / 187,472,637 bytes**, SHA-256
`72811e7d4cb90e569e660a6d0cadd31add9e5e1f24cf037ca3b3c0f157dca26e`.
It passes a separate Python extraction and exact-file hash comparison. Input
verification report SHA-256:
`6c18e24030d1c458b3e4ae7d156dcfebbc4bc74fae42c1bc7316c2c6e15ac0dc`.
The corresponding-source runtime archive has **329 files / 177,523,386 bytes**,
SHA-256 `292ce8bc2c201a62e013a9cd2086477d060b7843ddaadd55be1041b8e772e465`.
Its archived component files match the source materials exactly. These archives
are under `build/sdk-windows-python-v1/final-v2/`; earlier attempts remain intact.
The archive retains the exact collector used; a subsequent verifier-only check
adds rejection of extra linked source directories without changing input bytes.

**356 focused host tests pass**, including Windows dependency markers, source
and wheel identities, archive/RECORD/case/path checks, metadata/native mapping,
source notices, installed code changes, extra links and cache/copy races, plus
existing SDK signing, archive, GDB, encoding and desktop/source packaging tests.
Final source-kit reproducibility, isolated extracted collector/packager entry
points, source-material revalidation, document links and public-tree checks are
recorded in the same checkpoint directory. The Windows host request remains
unanswered. Upstream wheel rebuilds, real publication/download journeys, native
host acceptance, physical testing and independent developer trials remain open.
No connected-device write, key generation, commit, push or publication occurred.
The complete SDK 1.0 goal remains active.

### Windows CPython runtime inputs and QEMU DLL isolation — 2026-09-15

**Local input and packaging checks pass; no Windows executable was run.** The
full SDK 1.0 goal remains active. Native Windows assembly, supported-host and
credential-store acceptance, real publication/download journeys, physical USB,
input/performance/power-loss/durability and independent developer trials remain
open. EEZ remains excluded.

The original full CPython 3.14.7 x64 ZIP, source tarball, release manifest,
Sigstore bundles and runtime/source SBOMs are retained. The full ZIP hash is
`ac1a727a71738e11de80b76e975f9b8a258aea6412bfc31696b929d59c6aafd0`;
the source tarball hash is
`3b48dac8fb59f62eaa67ac83c1eb12bda1b7a08406dd286e252c11a66be27f81`.
The release manifest hash is
`b70dda5471def7e41e8cae246ff2394d92fb9b918c381ce2f357649dcae53008`.

Sigstore 4.5.0 verified the release manifest and source signatures with Python's
published `hugo@python.org` identity and GitHub OAuth issuer. Offline verification
also passed; wrong-identity and modified-manifest controls failed as expected.
The ZIP is bound by the signed release manifest: a direct ZIP `.sigstore` request
returned 404. No individual Authenticode verification is claimed. Exact commands,
results and metadata remain under `build/sdk-windows-cpython-v1/`, including
`signature-verification-v1.json`. These are upstream source-input signatures;
calculator/app signing keys were not accessed or changed.

[The CPython collector](../scripts/windows_cpython_sources.py) and its
[reviewed lock](../scripts/windows_cpython_sources.json) now retain:

- All 2,730 original runtime files, including 45 PE files. Core binaries are x64;
  pip's bundled launchers also contain x86/ARM64 inputs and are not executed.
- CPython source and all 33 dependency source archives referenced by its runtime
  SBOM. Wheel references resolve to the corresponding exact-version source
  distributions; referenced macOS wheels are not installed or executed.
- 112 source notice files and three original runtime notices. The historical
  macholib source lacks a standalone license; CPython's original
  `Lib/ctypes/macholib/README.ctypes` is retained. SQLite's original `sqlite3.h`
  contains its copyright disclaimer and is retained verbatim.
- The Microsoft distributable-code terms from the original runtime `LICENSE.txt`.
  Microsoft runtime DLLs are not classified as open source and no corresponding
  source availability is asserted. Distlib's source includes its launcher C code;
  Tcl's source includes libtommath. No upstream binary rebuild is qualified.

Collection checks archive sizes/hashes, release-manifest binding, SBOM source
references, native file identities and original notice bytes. ZIP extraction is
bounded and rejects traversal, Windows device aliases, case collisions, links
and file/directory collisions. Both source and binary packaging now require the
matching `windows-cpython` component. Binary packaging additionally requires
`--cpython-runtime` pointing to the original ZIP, compares base-interpreter and
stdlib files before freezing, checks frozen CPython DLL hashes, and records
`windows-cpython-inputs.json`. [Host instructions](../sdk/HOSTS.md#windows-packaging-inputs-and-checks)
use the extracted full runtime to create a separate packaging virtual environment.

The actual inputs exposed a DLL collision: CPython's `libffi-8.dll` is 39,696
bytes, hash
`eff52743773eb550fcc6ce3efc37c85724502233b6b002a35496d828bd7b280a`;
QEMU/GLib's file has 114,254 bytes, hash
`ef601add83f3d690f4734d7224e2ec0de5c3ff89f2f5370dc270e31c9f8a3f5b`.
The Windows packager now keeps QEMU and its full DLL closure in
`_internal/runtime`, outside PyInstaller input analysis. The final dependency
audit checks QEMU separately from the SDK process. Windows `--runtime-library`
inputs now explicitly belong to QEMU. The loader comment was corrected to account
for a parent's `SetDllDirectory`; application-directory DLL precedence is
specified in [Microsoft's search-order documentation](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order).

The real retained binaries pass a 60-PE audit with 39 CPython files and QEMU's
separate dependency scope. Removing QEMU's libffi fails rather than using the
Python copy; the old flat layout reproduces the collision. System DLL names in
this cross-host audit are explicit fixtures: actual Windows availability and
loader behavior are unqualified. Evidence is
`build/sdk-windows-cpython-v1/isolation-v1/report.json`, hash
`e9c2f3b49969f85443a2d1bf43e69183b68fb2008af2e15d6c91998d3494a8e7`.

The full runtime/source input archive is retained at
`build/sdk-windows-cpython-v1/final-v2/lefony-windows-cpython-3.14.7-x86_64.tar.gz`:
2,889 files, 204,455,316 bytes, hash
`9b18a77eca667b4aec7e58f508c9837cf6a74d6a992c8928e05a37817e921fa7`.
Every archived file was independently read and compared with its source bytes.
The offline installation check compares 809 interpreter/stdlib files; a changed
`pathlib` file is rejected and the original bytes were restored and rechecked.

Combining this source component with the previously retained Windows packaging
wheels produces a 16-component runtime-source archive with 486 files and
311,110,514 bytes, hash
`267a75e427f782b17e0f37d5ca43d83d65cc5d9e3dfde45cbc8eaad4996b1cf6`.
It remains a partial Windows source group: native tool/project components must
be assembled separately. All extracted member hashes were checked. The retained
report is `build/sdk-windows-cpython-v1/final-v2/report.json`, hash
`400cc6600afb0c5849ebc2bfa34b3890abd147a3ae35d99f3ebd3fda8f2d2443`.

Validation: 251 relevant host tests pass, including 35 new CPython runtime/source
cases and the real-PE collision regression. Public-tree checks pass for 1,160
files. Firmware was not changed, so neither physical nor emulator firmware was
rebuilt for this host-only change. Source-kit reproducibility, extracted CLI
checks and local documentation links are recorded in this checkpoint's
`checkpoint-validation-v1.json` under the same ignored build directory.

Earlier attempts remain retained: two notice scans stopped on absent standalone
macholib/SQLite licenses; the first collector attempt was interrupted after that
scan failed. A first archive audit used an incorrect expectation of over 1,000
selected interpreter files and stopped before creating an archive; the corrected
check records the actual 809. These were input/verification assumptions, not
successful packaging results. No failure was relabeled as native qualification.

### Windows native source assembly and bundled-input correspondence — 2026-09-15

**The compiler/debugger/QEMU/library sources now assemble with the Python
materials. No Windows executable was run.** The full SDK 1.0 goal remains
active. Native freezing/execution, clean-host and credential-store acceptance,
release/project/firmware integration, real publication/download journeys,
physical USB/input/performance/power-loss/durability and independent developer
trials remain open. EEZ remains excluded.

[The native source assembler](../scripts/collect_native_windows_sources.py)
checks the exact original artifact checksum inventories pinned in
[the component lock](../scripts/sdk-windows/native-components.json). It checks
every extracted file, rejects extra/missing/changed files and links, then retains
source archives, original recipes, build records and notices. The 16 Python
source components join five native groups: compiler/toolchain, GDB, Prime QEMU,
libusb and OpenSSL. The resulting 21-component manifest records 1,702 installed
tool inputs, including ARM libraries and supporting files. These are source
correspondence records, not an assertion of Windows execution or a full release.

Compiler, GDB and QEMU runtime records include GCC 13 source nested inside its
Ubuntu original archive. The assembler now reads the exact `COPYING`, `COPYING3`,
`COPYING.LIB`, `COPYING3.LIB` and `COPYING.RUNTIME` members and preserves them as
runtime notices. GDB's retained common-license directory also supplies the
complete texts referenced by Debian copyright files, including LGPL 2.1.
Original file-level licenses and the core's licensing remain unchanged.

[The final Windows source audit](../scripts/native_desktop_windows_sources.py)
binds every bundled PE binary and copied toolchain/OpenSSL file to a verified
input provider. The generated launcher separately records its reviewed
PyInstaller bootloader and final output hash. Unknown or changed inputs fail
packaging. The existing Windows dependency audit still checks imports, delayed
imports and forwarded exports; QEMU keeps its own DLL scope. The complete native
material verifier now gates Windows binary packaging. Source groups preserve
the selected input catalogs and lock identity for independent checks.

An offline layout combines the real compiler, GDB, QEMU, OpenSSL, libusb and
CPython files. It passes a 119-PE dependency audit and source correspondence for
627 files. A modified compiler and an unknown DLL are rejected; original bytes
were restored and checked. The launcher in this layout is an **unfrozen**
reviewed bootloader. Windows system DLL availability is represented by declared
fixtures. This is not a frozen SDK, native Windows execution, compiler/debugger
behavior, credential-store or USB qualification.

Local evidence is retained under `build/sdk-windows-assembly-v1/`:

- `materials-v3/`: current 21-component source assembly and 1,702-input catalog.
- `layout-v1/` and `layout-audit-v1.json`: real input layout and negative controls.
  The latter hash is
  `74548757da72e043aada808d53daa738e6b1a7bbe60032b4263b1c4fbf1751e9`.
- `revalidate-inputs-v1.py` / `layout-audit-v2.json`: original archive/checksum
  identity checks and current source-manifest correspondence, preserving the
  earlier audit and its negative controls.
- `source-distribution-v2/lefony-sdk-source-toolchain.tar.gz`: 395 files,
  two components, 599 installed-input records, 445,116,054 bytes; SHA-256
  `ffd2870bae2af558adaa123bc94dcdbf179334f09219889f6f89af02a2cb4b39`.
- `source-distribution-v2/lefony-sdk-source-runtime.tar.gz`: 827 files,
  19 components, 1,103 installed-input records, 511,662,975 bytes; SHA-256
  `8f9eb0a686692d50ce17a5a927ae1ea7a20966e74ccdd3c6375d9eaff41d020a`.
- `source-distribution-v2/verification.json`: every archive member was read,
  hashed, independently extracted and verified against its selected source group.
  The source material manifest hash is
  `89ebf960a56fee29b1613027eb680696ae43f7fc9201ba36c965879c1ec04f60`.

The first archive comparison correctly failed: three original artifact records
contained Python bytecode caches, which the source archiver intentionally omits.
The durable collector now excludes generated caches while preserving the original
artifact inventories. Earlier materials and failed archive outputs remain
retained. The final collection used APFS copy-on-write copies to conserve local
disk space, with all original input and post-copy hash gates still enforced.
No retained original artifact was rewritten or deleted.

Validation: 267 relevant host tests pass, including 16 new assembly/source-audit
cases. The final focused check also covers multiple matching input providers.
Public-tree, local document links, extracted CLI checks and deterministic
standalone source-kit checks are recorded in `checkpoint-validation-v1.json`.
No firmware changed or calculator operation occurred during this host-only work.

Next assembly inputs remain explicit: the current `build/sdk-newlib` candidate
passes the SDK runtime contract and its 139-file bundle check. The separately
retained `sdk-main-newlib-full-repeat` candidate fails the current configure-option
contract and must not replace it. Matching newlib and firmware/project source
records must join the release inputs before final native Windows assembly and
qualification. No newlib rebuild or runtime qualification is claimed by these
read-only checks.

### Windows project sources and newlib correspondence (2026-09-15)

This checkpoint joins the retained Windows native/Python materials with the
selected ARM newlib sysroot and explicit public/QEMU/VM firmware source inputs.
It completes this source-assembly step; it does not qualify a frozen Windows SDK
or SDK 1.0 release. The full goal, with EEZ excluded, remains open.

Durable changes:

- `scripts/native_desktop_project.py` collects newlib sources/notices/recipe and
  checks the selected 139-file bundle before and after copying. Windows binary
  packaging requires matching newlib material records and `--project-sources`.
- The project manifest binds exact VM ELF and Windows QEMU input hashes to
  prepared sources. QEMU must match its verified native build record. Firmware
  must have a retained successful, byte-identical VM rebuild report and log;
  every prepared source member must match its recorded hash, size and mode.
- Public source checks compare staged and final SDK data and current host
  recipes to the selected working-tree snapshot. The final bundle records
  `newlib-inputs.json` and `project-source-inputs.json`, bound by candidate hashes.
- The native source collector accepts `--newlib`; the dependency source packager
  verifies that component. Project source archives retain firmware report/log
  evidence alongside the three source archives. Earlier source-only manifests
  remain readable, but Windows binary packaging requires the new evidence.
- The standalone source kit includes the helper, and the
  [host instructions](../sdk/HOSTS.md#windows-packaging-inputs-and-checks)
  document assembly and the new required Windows input.

Newlib was actually rebuilt with native GCC 16.2.0 using the pinned
`newlib-4.6.0.20260123.tar.gz` and `scripts/build_sdk_newlib.py --jobs 4`.
All **139 selected files are byte-identical** to the previous candidate,
including libraries, headers, license, source archive and candidate record:

| Input | SHA-256 |
| --- | --- |
| newlib source | `6ff27e3bf022666f43f7802255be680eeff722ac181b1725d21e2e8318604ee3` |
| candidate record | `17e1f6adf827b00d5e5222f84d62b8cfd82e91eee08e5a3830545448ebb10449` |
| libc.a | `2a682114e9087f218f3d7058d7d2223cd0668b2fbb86067f7a7dbe1e738ee7b8` |
| libm.a | `05d44e396f7b20bf0081b46a3bd628e863c5a0f3336561168e4ca1a53a1df3e8` |
| selected VM ELF | `5a0636eb915aaf8ea62b889932ee0538ca20c9371334905a970406bc58680105` |
| selected Windows QEMU | `5b499b64a5a8e8d833a387bff549cc6f72fa17ee6c29c7b6bb1cbf791dc22a76` |

Firmware was not rebuilt in this checkpoint. Its retained proof checks all
**4,399** prepared source files and the same selected ELF, with source archive
`3750fdf827e59e23c812d8cced2a31d9b1998a93ac7dd957d2405a357a930c81`.
The selected prepared QEMU source is
`8a4c141c2dd6e72ea3bc080fdd301809e3860c189d8b79fbec45e34bd421e076`.
The 1,166-file public snapshot is
`a33dc98a0ee881c8c6a5f91fdaede86bb468a5d52c3c97aa2c4d1a515fd4cf9c`;
it captures SDK/recipe changes before this evidence entry was appended.
The real staging check binds **350 SDK/host source files** and rejects altered
SDK code and an altered newlib library; both staging files were restored and
rechecked. No original candidate was modified.

The new materials set contains **22 components**, **1,702 installed native tool
records**, and the separate **139-file newlib record**. All three source archives
were reopened and every member was hashed against its selected inventory.
Project sources and the added newlib component were also extracted separately
and reverified. The unchanged runtime archive was reused only after comparing
its selected component records and tool inventory, then verifying all members:

| Archive | Files | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| `lefony-sdk-source-toolchain.tar.gz` | 401 | 454,138,241 | `1c4f3c19554fe95a0b7bb75ec4a89de8b51f2b95c9455f7572820273dc8bf612` |
| `lefony-sdk-source-runtime.tar.gz` | 827 | 511,662,975 | `8f9eb0a686692d50ce17a5a927ae1ea7a20966e74ccdd3c6375d9eaff41d020a` |
| `lefony-sdk-source-lefony-qemu.tar.gz` | 6 | 52,215,442 | `fc5b117f23d4e1677b66b19608f38d6bed4d13adecb0184752fdff0ceceec96c` |

Local evidence is under ignored `build/sdk-windows-project-v1/`:
`newlib-rebuild-proof-v1.json`, `materials-v1/`, `project-sources-v1/`,
`real-inputs-v1.json`, `source-distribution-v1/verification.json`, and retained
build/test/assembly logs. Earlier snapshots and failed fixture-test attempts
remain retained. APFS cloned copies preserve the previous source materials.

Validation: **293 focused host tests passed**, covering desktop packaging,
Windows sources/dependencies/runtime, Linux source/dependency regressions,
Pillow, TLS/OpenSSL, and newlib/project correspondence. The final argument-gate
change also passed the **47 desktop packaging tests**. The final checkpoint
record adds public-boundary, documentation-link and deterministic standalone
source-kit checks; exact results are recorded locally rather than inferred.

Remaining acceptance: assemble and execute the full frozen SDK on native Windows;
qualify clean supported hosts and credential stores; complete real GitHub/store
publication and download journeys; physical USB/input/performance/power-loss and
flash durability; independent developer trials and final compatibility review.
No Windows executable ran, no device was written, and no signing identity,
publication or release action occurred in this checkpoint.


### Store-key correspondence and reproducible VM candidate (2026-09-15)

Live download qualification exposed a release-assembly defect: the existing
SDK VM ELF has no compiled store roots, although the SDK bundles the store's
correct public key. Host inspection accepts the unchanged published Surface 3D
package, but that VM rejects it during installation. Retained failure evidence
is under the website repository's ignored `.local/sdk-downloads-v1/live-app-v1/`.
The published app was not re-signed, and no signing identity was replaced.

The [desktop packager](../scripts/package_native_desktop.py) now checks the VM
before staging and again against the actual final bundle's public keys.
[The verifier](../scripts/native_desktop_firmware.py) parses initialized ARM ELF
objects and requires every compiled store-key table to match the explicitly
selected public keys. It checks the separate emulator fixture, rejects that
fixture as a store root, and rejects stripped, unmapped, writable-section or
malformed key objects. Raw matching bytes outside those objects are insufficient.
The final `firmware-trust-inputs.json` is bound into the candidate record.
This structural check complements signature execution; it does not prove it.

The VM was separately configured with the **existing public store key** through
`LEFONY_APP_PUBLIC_KEYS`. Its earlier website trial passed unchanged signed app
installation through modeled USB, normal keypad rotation, Home/relaunch and a
second cold boot. Captured initial/rotated frames were reviewed, and restored
frames matched exactly. The unconfigured original, failed attempt and configured
candidate remain separate retained artifacts. Physical build defaults and release
trust roots are unchanged.

A fresh extraction and GCC 16.2.0 rebuild now reproduce that configured VM's ELF
and binary exactly. All **4,399 prepared source files** match before and after
the build; the successful build took 38.12 seconds:

| Input | SHA-256 |
| --- | --- |
| configured VM ELF | `195913e780bf8e4f67c35ef82f9cb90733b9af458d4cad901b19ffa2020b33ff` |
| configured VM binary | `5a89f4e685181964d598157829a47ff385af6fde7663a546af9a1e3eb21f557c` |
| prepared firmware source | `79951093d0cc0d64c2a911ca9c8e9435cba253dc819e3f4e65d98b5da6a1b479` |
| retained build log | `749ece375b274fcc0b7592a6ec4666f21ff9b17c7226a2e03fa93b1c0a4f765e` |
| existing store key identity | `422e6537d044dfea26dd01ce63dd0374f4eeaee8e9328aae2c0d332d7996d003` |
| unchanged Surface 3D download | `3cc519f2bd76ffc0f916e3ad3871f0b5f08dd2d84cbb12e412e06edcc661014f` |

The real compiled image has two matching store tables and two matching emulator
tables. Negative checks reject both the original unconfigured VM and a separate
copy with one altered compiled modulus. No original input was modified.

A **1,168-file public snapshot** captures the current SDK/packager source before
this ledger entry, SHA-256
`ead5413dd0a3e351b51aae5b1032dd7714543bd5b68764afc9bdc364ebfe3fea`.
The real staging comparison checks **351 SDK/host source files**. The updated
Windows project source packet combines this snapshot, unchanged Windows QEMU
sources, configured VM sources and its exact rebuild report/log. Its six-member
`lefony-sdk-source-lefony-qemu.tar.gz` is **52,211,276 bytes**, SHA-256
`e4229939f80688833ef34886ed62fd8dbcb666dad3488755fb494a150fd8c403`.
Every member was rehashed; a separate extraction passes project correspondence
against the real Windows QEMU and configured VM. This replaces only the project
source group for the next assembly, not a complete Windows distribution.

Validation: **321 focused host tests pass**, including 28 new ELF/key cases and
regressions for desktop/project/source packaging, Windows dependencies/sources,
Linux dependencies/sources, newlib, Pillow and TLS/OpenSSL. Two standalone
source-kit runs produce the same **335-file** archive, SHA-256
`ebaf1931ee99913b8d189b4dd2e10041c3e668041542f5838499a419dee470bc`.
All members/checksums match their source; extracted packager CLIs load in isolated
Python, and the extracted verifier accepts the actual configured VM. This kit
also precedes this evidence entry.

Evidence is retained under ignored `build/sdk-store-trust-v1/`: `rebuild-v1/`,
`real-inputs-v1.json`, `windows-project-sources-v1/`,
`windows-source-distribution-v1/`, `source-kit-verification-v1.json` and test logs.
The website's prior checkpoint separately records all five published SDK/source
download hashes and the actual GitHub release-list/capsule verification. The
production account route returned 404; new account/publication routes and the
larger Windows download limit remain local website changes awaiting integration.
No new release, store submission or production website deployment is claimed.

The existing frozen Linux SDK, mounted read-only in minimal Ubuntu with no
system Python/compiler, passes **44 commands and 18 ARM startup runs** with an
explicit override to this configured VM. The unchanged published app passes
inspection and two independent launches with identical captured frames. All
eight templates pass creation, packaging, installed-workspace startup, cold
startup and validated source-format-2 export. The original bundle checksum list
passes before and after. Logs and reports are in `linux-result-v1/`; originals
and synthetic workspaces remain in the separate retained Docker volumes.

These startup checks do not establish interactive rendering for foreground
`main` applications: their startup frames were still blank. Their later preview
checks must be assessed separately. The published app's repeated disposable
launches also do not establish persistence; the earlier website trial covers
its modeled installed/cold path. All Linux commands here use explicit x86-64
emulation on an ARM64 host, not native Linux qualification.

The subsequent **three normal preview scenarios pass** with the same frozen SDK
and VM override. C main waits for successful program exit, relaunches and shows
**2 saved visits**. Notebook passes editing/saving, theme and export actions;
UI Gallery passes checkbox/focus/text editing. All replay steps pass, the OS
remains responsive, and bundle checksums still match. Captured frames were
reviewed: text/actions are legible without visible clipping. Notebook and
Gallery PNG hashes exactly match their earlier production-bundle reference
frames. Reports, normal-input steps and visual review are retained in
`linux-preview-result-v1/`. These bring this checkpoint to **47 successful Linux
CLI commands**, including the 18 startup runs and three interactive previews.

Public-tree and whitespace checks pass. `checkpoint-validation-v1.json` records
final local-link checks and binds the exact tests, source files and evidence.
Full desktop distributions still need reassembly with this VM and its matching
sources. The host had only about 1.2 GiB free; a storage-location/cleanup-scope
question is pending, and retained artifacts/recovery snapshots were preserved.
Native Windows assembly/execution, clean-host credentials, coordinated production
publication, physical USB/input/performance/power-loss/durability and independent
developer acceptance remain open. No physical target code changed or device was
written during this checkpoint. SDK 1.0 is not declared complete.


### Unix source-packaging regression after Windows integration (2026-09-15)

The Windows newlib source integration introduced a regression in the shared
source archiver: it applied the Windows `bundle` manifest check to retained
Linux catalogs, which use `inputs` and `installed_notices`. Running the previous
packager against the complete retained Linux materials reproduces
`KeyError: 'bundle'` before output creation. The earlier already-built archives
remain valid; this was a defect in the subsequent packaging recipe.

[Source packaging](../scripts/package_native_desktop_sources.py) now applies the
structured newlib/sysroot check to Windows while preserving the Linux/macOS
catalog format and their existing source checks. Common validation also checks
installed notice hashes and rejects linked notices before opening the output.
Windows still rejects a mismatched selected sysroot. Nine regression cases cover
the two Unix formats, changed sources/notices, linked notices and Windows gating.

**137 focused host tests pass**, covering source/project/desktop packaging,
Linux source/dependency checks and Windows native source records. The real Linux
trial uses its original production material volume mounted read-only with the
current scripts copied into a separate output volume. It first reproduces the
previous failure, then successfully packages the toolchain group and verifies
**3,917 source inputs and 119 notices across 82 components**. All **29 archive
members**, including the component manifest, have the same bytes and modes as
the retained toolchain source archive. No original material or distribution was
modified. Archive container hashes can differ with packaging metadata; this is
member correspondence, not an assertion of byte-identical tar/gzip output.

| Input/output | SHA-256 |
| --- | --- |
| production material manifest | `3bdfbdd906dc67d0edb281ec454c4473bc7ae3d9fe2558af1937dc178bfa2a63` |
| retained toolchain source archive | `adbac52c1f9a089ca9c524dbbf7a8ce5a139cdeabc4338d690008804e1efcc66` |
| repackaged toolchain source archive | `af086200a3eb2cf79cae5d4efa1dfe8f9512175d40798d554f1628d3d563e25f` |

The new archive is **180,138,009 bytes**, retained in the dedicated
`lefony-sdk-unix-source-regression-20260915-v1` Docker volume under
`distribution-v1/`. Local evidence is in ignored
`build/sdk-unix-source-regression-v1/real-linux-report-v1.json`, the retained
before/fixed recipes, test log and checkpoint record. The initial host-bind
setup failed because this Docker VM does not share the checkout path; no
container was created for that attempt. The successful second attempt uses
copied scripts and an isolated volume; its process terminated with exit 0.

The final checkpoint records public-tree, whitespace, local documentation links
and deterministic/extracted standalone source-kit checks. This repairs source
assembly without rebuilding a binary SDK. Native Windows, native Linux/clean-host
credentials, full distribution reassembly, coordinated publication, physical
qualification and independent developer trials remain open. Available host disk
space is now about 1.0 GiB; the pending storage question and retained-artifact
constraints still apply. No device access, key change or publication occurred.


### Linux project-source gate and relocated QEMU correspondence (2026-09-15)

The Windows project-source gate was previously unavailable to Linux: desktop
packaging rejected `--project-sources` there. Both hosts now require the explicit
public SDK, prepared QEMU and prepared VM source packet with its matching retained
firmware rebuild report/log. [The shared helper](../scripts/native_desktop_project.py)
reads Linux's existing `qemu-prime` input/notice catalog, checks every component
input, and binds its successful Linux x86-64 build record to the selected QEMU
and source archive. Windows retains its existing collector and selected-sysroot
checks. Unknown hosts, duplicate inputs/components, changed notices or sources,
failed builds and unrelated build records are rejected.

The Linux final-bundle check accounts for required library-path relocation.
It binds the selected QEMU input to the source archive and compares the actual
bundled bytes with `linux-native-source-inputs.json`. Both identities and the
audit hash are retained in `project-source-inputs.json`; unknown audit schemas
or mismatched providers/hashes fail. Firmware must match exactly. Windows QEMU
still requires unchanged input/output bytes. Public SDK and host recipe checks
run before and after freezing on both hosts.

The actual retained Linux QEMU/source materials and the store-enabled VM now
produce a verified Linux project-source packet. A separate extraction rechecks
all six packet members and all **4,399 prepared firmware files** against the
retained byte-identical rebuild report. The VM was not rebuilt this turn.
A fresh public snapshot contains **1,168 files**; it precedes this evidence entry
and the status summary. The actual desktop staging selection checks **351 SDK
and host recipe files** against it. A separate standalone-kit selection checks
336 files. These are different selection sets, not missing desktop inputs.

| Input/output | SHA-256 |
| --- | --- |
| public source snapshot | `b8b5d6ca0a59bfbaec6c4528c673aa0971d9373e8026d630b77fa2c06b8f1c93` |
| selected store-enabled VM | `195913e780bf8e4f67c35ef82f9cb90733b9af458d4cad901b19ffa2020b33ff` |
| selected Linux QEMU input | `440da313e664335914bab7cfc2680d1b052b7493acdf081e64fa6528e7576e73` |
| retained relocated Linux QEMU | `dd03333a421386cbdf0066f00d8e5aa928e2b10bb77588b7b0b49df69611648e` |
| retained Linux source audit | `dc8e826f2c5fcdff4917b2416f1d085ad86d27be8d37e8822f1ff2246e2cd081` |
| final Linux project manifest | `0e895e5d2b521e42b9cb29f536ad69644050c466ac4d4e0aa84996f411eab629` |
| final project source archive | `c8666f0de107cabf1895c6d5deb59abec8c16cd20cbe66449e66b9391702666c` |

The six-member archive is **52,217,609 bytes**. The real existing Linux SDK is
rejected against this project packet because it contains the older unconfigured
VM. Checking its QEMU relocation separately with its original firmware identity
passes. This is an explicit negative control plus retained-bundle correspondence;
it is not a newly frozen bundle containing the new VM. The retained Windows
project packet also passes the updated helper against its actual QEMU and VM.

**170 focused host tests pass**, including 27 new Linux project/CLI and
final-byte/relocation cases. Coverage includes source/project/desktop packaging,
compiled firmware keys, Linux source records and Windows native materials.
Public-tree, whitespace, local-link and final deterministic/extracted source-kit
checks are bound by the checkpoint record. No native Windows or calculator
execution occurred during these source-assembly checks.

Local evidence is in ignored `build/sdk-linux-project-sources-v1/`:
`real-inputs-v2.json`, `desktop-staging-v2.json`, `windows-compatibility-v1.json`,
`host-tests-v3.log`, container records and the final checkpoint. Docker volume
`lefony-sdk-linux-project-sources-20260915-v1` retains `project-sources-v2/`,
`source-distribution-v2/` and separately extracted verification inputs. The first
packet and reports remain retained; the second includes the final audit-schema
check. Both source assembly processes exited 0. Original production/QEMU input
volumes were mounted read-only.

Remaining: update complete native source inventories for the chosen new freeze,
assemble complete binary/source distributions, qualify native hosts and
credential stores, coordinate real publication, and finish physical and
independent-developer acceptance. Host free disk is about 780 MiB; the pending
storage-location/cleanup-scope question remains unanswered. No retained artifacts
were deleted, no release identity changed and nothing was published. These gates
make the next Linux assembly stricter; they do not complete SDK 1.0.


### Source archive streaming integrity and construction failures (2026-09-15)

Two regression tests exposed a source-assembly race: after preflight checked the
source hashes, the archiver reopened the files and could embed changed bytes
without rejecting the mismatch with its recorded manifest. Both the project
archive and dependency-input cases failed before the fix, demonstrating that a
valid outer archive alone did not prove source correspondence.

[The source packager](../scripts/package_native_desktop_sources.py) now hashes
the bytes actually consumed by tar for every recorded input, including source
archives, rebuild evidence and installed license notices. A changed digest or
appended tail fails construction; short reads also fail. It stages all selected
archives and their new catalog before replacing previous outputs. Ordinary
construction errors, injected disk-full failures and cancellation leave the
previous archive set and catalog intact. Refreshing one group still retains
unselected groups and writes their valid catalog entries.

**153 focused host tests pass**, including eleven new cases for mutation between
preflight and copy, changed/appended/truncated data during streaming, late-source
failure, archive/catalog disk-full errors, cancellation, successful group refresh
and a real subprocess kill during construction. After that killed process, the
old archives/catalog remain byte-identical and a retry succeeds. The abandoned
staging directory remains separate; the retry does not silently delete it.
The first midstream fixture was too small: read-ahead had already captured all
original bytes, so accepting that original stream was correct. The final case
changes a tail outside the read-ahead buffer and verifies rejection. That failed
fixture attempt and the initial before-fix failures remain in local logs.

A separate real-artifact trial uses APFS clones of the retained Windows project
source packet. It first packages the unchanged inputs, then changes one cloned
source archive after preflight. The copy-time check rejects it and preserves the
previous archive and catalog exactly. Restoring that cloned input and retrying
succeeds; every member of the six-file output matches the selected hashes. The
original source packet remains unchanged. The altered clone is retained as
negative evidence. No Windows executable or firmware was run.

| Retained input/output | SHA-256 |
| --- | --- |
| original project manifest | `524e9e66d4f3534b050612dd26937605f4e5a09e541a1f9c3f32c0f14896a360` |
| original public source snapshot | `ead5413dd0a3e351b51aae5b1032dd7714543bd5b68764afc9bdc364ebfe3fea` |
| successful historical source repack | `17c67f39a093463cf50bc64c7a083de983dcf54bcbd9f4ceb97fa8ee415574a6` |

The repack is **52,211,276 bytes**, with six members. It intentionally contains
that earlier source snapshot; it is not a current release source packet or a new
binary SDK. Evidence is under ignored `build/sdk-source-stream-check-v1/`:
`before-tests.log`, `host-tests-v4.log`, `real-packet-v1.json`, cloned inputs,
retained altered input and `historical-project-repack-v1/`. The final checkpoint
binds public-tree, whitespace, document links and deterministic/extracted current
source-kit checks. All work processes terminated; no deployment, signing-identity
change or calculator operation occurred.

Final archive/catalog replacement still spans several files; this checkpoint
does **not** establish a multi-file power-loss transaction or concurrent-writer
coordination. Use a fresh output directory per release candidate and verify its
complete catalog before publication. Native-host, full binary/source assembly,
real publication, physical durability and independent-developer acceptance remain
open. Host free space is about 729 MiB; the pending storage/cleanup-scope question
still needs an answer before larger builds can proceed.


## Linux store-enabled distribution reassembly (2026-09-15)

The complete Linux x86-64 packager now finishes with the store-enabled VM,
current SDK/host recipes, strict project-source and firmware-trust gates, and
fresh matching source archives. This supersedes the earlier statement that
Linux still needs a complete reassembly with its configured store key. It remains
a development candidate; Windows, clean native hosts, real publication,
physical qualification and independent trials are separate gates.

### Storage and preserved inputs

A read-only audit found unused blocks still allocated in the SDK VM's data disk.
`fstrim --verbose /mnt/lima-colima-lefony-sdk`, run through the SDK
profile's `colima ssh`, discarded only filesystem-free blocks. It reported
3,004,280,832 bytes trimmed; host available space rose from 754,143,232 to
2,809,364,480 bytes. No files, Docker objects, keys or recovery snapshots were
deleted. All four retained disk snapshots kept their size, inode and modification
time; this was a metadata check, not a new full snapshot hash verification.
The exact record is `build/sdk-storage-audit-v1/trim-v1.json`.

A second read-only audit found free blocks in the default Colima data disk.
Trimming `/mnt/lima-colima` reported 2,478,964,736 unused bytes; allocated host
disk space decreased by 1,695,375,360 bytes. This likewise removed no files or
Docker objects. `build/sdk-storage-audit-v1/default-trim-v1.json` records the
operation. Host available space rose to 2,049,216,512 bytes after the binary
archive had already been retained locally, allowing matching source artifacts
to be copied out without removing recovery history.

The preparation verifies all 5,505 files in the preceding frozen SDK and every
recorded original source/notice input. A separate material tree shares unchanged
files by hardlink and unlinks each changed destination before replacement.
The original material manifest remains
`3bdfbdd906dc67d0edb281ec454c4473bc7ae3d9fe2558af1937dc178bfa2a63`;
all parent inputs pass verification again after preparation. The new source
manifest is
`9c7646d288caf47c3e7760acedcb62c61666f8dc98963101e7bd56a9cc8a412b`.

Temporary binary staging uses bounded tmpfs inside the 5 GiB SDK VM. New output
lives on the VM's root filesystem, avoiding the nearly full Docker data
filesystem. The complete retained output is under
`/opt/lefony-sdk-store-assembly-v1` in the `lefony-sdk` Colima VM; original build
volumes and recovery evidence remain intact. Local recipes/reports are under
`build/sdk-linux-store-assembly-v1/`.

### Exact binary and source artifacts

The uninterrupted packager exits zero after 942.380 seconds. Its 5,510 listed
bundle files pass checksums. An independent streaming archive check also verifies
`SHA256SUMS`, every file's mode and all 13 symlink targets: 5,511 regular archive
files total. The dependency/source audits, newlib copy, selected store and
emulator key tables, final project-source correspondence and packaged doctor,
QEMU, GDB and OpenSSL smoke commands all pass.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `lefony-sdk-linux-x86_64.tar.gz` | 208,471,835 | `7cdf903b53a6748979928377b829fe5735fb6dfbd6fd627c5563ac7fd63ec01f` |
| `lefony-sdk-source-toolchain.tar.gz` | 180,138,009 | `be5786ad45c710bf44bef496f730babeb4aedb342abbbd73bcc6e0c034dff581` |
| `lefony-sdk-source-runtime.tar.gz` | 787,523,227 | `3a519b96677fe85b865dd431c04a5977ae5cb12da58b6357f65a5e328e43519f` |
| `lefony-sdk-source-lefony-qemu.tar.gz` | 52,222,892 | `c044a003c3b283d84d5b56c0363547cfeb83afb51b308c235e84124a5b49fd4f` |

The three source groups independently verify 4,287 payload files and their three
manifests. The project group includes the retained firmware rebuild report and
build log. The public source snapshot contains 1,168 files, SHA-256
`1e8dd452ec642a4b25916eaa53410078f4e4109216947c11517ab9574d3daf44`.
It records the working tree at freeze time, before these post-build qualification
notes. Prepared firmware source SHA-256 remains
`79951093d0cc0d64c2a911ca9c8e9435cba253dc819e3f4e65d98b5da6a1b479`;
all 4,399 source members match the retained byte-identical build evidence.

Candidate SHA-256 is
`03fc9a57a626d71c73dc5479d34546c9479afbc1b4b39404286c46df61b06e2b`.
The default bundled VM is
`195913e780bf8e4f67c35ef82f9cb90733b9af458d4cad901b19ffa2020b33ff`.
Its two store-table copies contain the existing published public key
`422e6537d044dfea26dd01ce63dd0374f4eeaee8e9328aae2c0d332d7996d003`;
the separate public emulator fixture remains unchanged. QEMU's original
`440da313e664335914bab7cfc2680d1b052b7493acdf081e64fa6528e7576e73`
and relocated
`dd03333a421386cbdf0066f00d8e5aa928e2b10bb77588b7b0b49df69611648e`
are bound through native-source audit
`341aed67c95c93607a64b8a5eb32522f8b29c19e8f778388b23ddc542663d259`.
No signing identity, upstream pin or signature policy changed.


### Extracted archive and frozen workflow qualification

Two fresh extractions into `SDK with spaces é` use temporary memory-backed
filesystems, preserving disk capacity. The minimal Ubuntu image has no system
Python, ARM compiler or QEMU. All 59 commands pass: eight external templates,
startup and cold installed-workspace runs, source-format-2 exports, private-key
signing/inspection, clone/export/restore and cold recovery, Notebook editing and
UI Gallery previews, and unchanged published Surface 3D inspection plus two
independent default-firmware launches. Those two launches are not a claim that
Surface 3D saves state. No firmware override appears in the trial driver.
Nineteen explicit startup/cold ARM reports verify successful results, no faults,
OS responsiveness and the selected bundled firmware hash.

Bundled GDB stops at `main` in the C source, reports `argc = 2`, steps and
detaches. A separate CMake image builds and inspects its package without system
Python. Notebook and Gallery preview frames are visually reviewed; Notebook
exactly matches its earlier reference. All bundle checksums pass after these
workflows. The independent archive check covers the symlinks as well.

All eleven actual frozen companion cases pass on the same candidate: GET,
chunked GET, POST, chunked POST, policy denial, TLS failure, timeout,
cancellation, truncated response, disconnect and terminal/repeated requests.
The harness verifies cache bytes, failure preservation and worker cleanup.
Landlock denies checkout and external Python access to frozen commands and
permits only bundled libraries plus the declared glibc/loader boundary. The
isolated doctor succeeds; granted-access and missing-control negative probes
both return the expected 125. No physical USB is involved.

The assembled qualification report is `qualification-v1.json`; source and
binary archive checks are `sources-report-v1.json` and
`archive-verification-v1.json` under the local evidence directory. Complete
binary and source archives are retained locally as well as in the SDK VM.
The actual Unix source payload comparison, firmware trust objects, original and
relocated QEMU, reviewed frames and command logs retain their exact hashes.
All build/test containers exit zero without OOM kills. No process is left running.
The failed early attempt to create a test container before its archive directory
existed created no container; it was retried only after that directory appeared.

This checkpoint changes assembly/evidence/documentation, not SDK API behavior.
The artifacts remain SDK `0.2.0-dev` candidates, not a declared stable 1.0 release.
All x86-64 runs use explicit emulation on ARM64; native Linux/Windows/macOS
clean hosts and credential stores, complete Windows freeze, real GitHub/store
publication, upstream binary rebuild acceptance, physical performance/USB/power
loss/flash durability and independent developer trials remain open. No commit,
push, deployment, production signing operation or calculator write occurred.


## Frozen Linux Secret Service account qualification (2026-09-15)

The store-enabled Linux archive now passes 20 real frozen account commands with
GNOME Keyring 46.1 over D-Bus 1.14.10. The archive remains
`7cdf903b53a6748979928377b829fe5735fb6dfbd6fd627c5563ac7fd63ec01f`;
its candidate remains
`03fc9a57a626d71c73dc5479d34546c9479afbc1b4b39404286c46df61b06e2b`.
No SDK API, runtime binary, release key, physical device or publication changed.
This checkpoint adds durable qualification harnesses and evidence.

The existing macOS account harness now also supports Linux with its mandatory
native Landlock launcher, explicit interpreter and an already relocated bundle.
The SDK executes actual login/whoami/apps/logout commands and its real built-in
Secret Service backend; no in-memory credential replacement is used. Both source
checkout and external Python access are denied to these frozen commands. The
local HTTPS server supplies synthetic GitHub-shaped account records, not real
OAuth authorizations or production Worker responses.

The 20 passing cases cover initially empty/origin-isolated records, first login,
account identity and owned apps, missing session bus, bus reconnection, locked
read failure, password unlock, daemon restart, origin isolation, replacement
login/old-session revocation, remotely revoked session cleanup, a new login,
explicit logout, local empty-store verification and final cleanup. Three issued
test sessions, including replaced/revoked tokens, are checked for command-output
leaks. Server actions confirm missing-bus, locked and other-origin failures do
not send the active credential to the fixture service.

The dedicated Secret Service fixture starts with a new empty, non-symlink
session directory, a nonempty random password and private XDG directories. It
precreates `data/keyrings` to prevent GNOME's legacy home-directory fallback.
It never changes HOME or reads a real desktop keyring. Audit controls verify
one stored SDK record, mode-0600 files and absence of plaintext test tokens.
Both the token digest and encrypted files remain identical after daemon restart.
Revocation and logout leave zero matching records. The final shutdown checks
that the entire fixture collection is empty, stops all owned processes and
removes its temporary keyring/config/runtime directories. Startup, control and
lifetime waits are bounded. The session marker and non-secret audit receipts
remain as evidence.

The locked read deliberately has no graphical prompter and returns a bounded
credential error. Unlock uses the fixture's own password through GNOME's
[encrypted internal master-password method](https://raw.githubusercontent.com/GNOME/gnome-keyring/46.1/daemon/dbus/org.gnome.keyring.InternalUnsupportedGuiltRiddenInterface.xml).
That GNOME-specific method exists only in the test controller; no SDK backend or
product flow depends on it. Interactive prompt approval/cancellation and other
Secret Service implementations remain unqualified.

The initial direct probe verified backend storage/removal and the frozen
empty-account error, then failed when x86 emulation tried to execute the ARM
isolation launcher. Two separate containers resolved this architecture boundary.
The first full attempt passed through locked-read but its fixture's ordinary
`gnome-keyring-daemon --unlock` invocation started a second daemon; unlock and
restart failed. The original attempt terminated and removed its private keyring
directories. The corrected controller uses the existing daemon's encrypted
method, and later complete runs pass. None of those setup failures was counted
as a successful SDK credential journey. Source and failed/passing reports are
retained under `build/sdk-linux-accounts-v1/` and the same named root directory
in the SDK Colima VM.

The final run uses a native ARM harness and Linux Landlock ABI 4 with explicit
x86-64 interpretation of both the frozen SDK and the separately owned GNOME
service. It is real Secret Service integration under emulation, not native
clean-host acceptance. Both final containers have read-only roots, no external
network and zero exit status; their owned processes and temporary credential
directories are gone. The original 5,510 bundle checksums pass before and after.

Final account report SHA-256: `5958f3d488259a5ddb761decbc655cf845e2fa8922656ac7377a6c9613ce6137`.
Final service report SHA-256: `1fbe29609adf7f37868324686c2dabfcdd174f165822c62b3cb1ce304dc2547b`.
Harness SHA-256: `9906122e9fd0f41ba8c250f238650da488622e474cd865031dbf87ef93637ce9`.
Fixture SHA-256: `4bc08a40568e437dd3008dcb1b71740fc2582b6ea7ea2ad56e1996abb120fa3b`.

Validation also passes 25 host tests: 22 account tests and three refusal checks
that preserve pre-existing or symlinked directories. The earlier native macOS
Keychain path was not rerun. Native/graphical Linux, Windows Credential Manager
and full Windows freeze, other clean hosts, real GitHub/store publication,
physical USB/input/performance/power-loss/durability and independent developer
acceptance remain open. No commit, push, deployment or calculator operation
occurred. See the [credential runbook](../sdk/HOSTS.md#linux-credential-qualification).


## Frozen Linux publication and accepted-download qualification (2026-09-15)

The unchanged store-enabled Linux archive passes **37 actual frozen CLI steps**
against the current website Worker/D1/R2 handlers through verified local TLS.
The archive remains
`7cdf903b53a6748979928377b829fe5735fb6dfbd6fd627c5563ac7fd63ec01f`,
candidate
`03fc9a57a626d71c73dc5479d34546c9479afbc1b4b39404286c46df61b06e2b`,
and VM ELF
`195913e780bf8e4f67c35ef82f9cb90733b9af458d4cad901b19ffa2020b33ff`.
All 5,510 listed bundle hashes pass before and after. This is another Linux
qualification gate; it does not complete R5/R6 or declare stable SDK 1.0.

### Workflow and containment

Three real authorization/decision/session sequences switch synthetic browser
accounts 1, 2, then 1. The frozen SDK stores credentials in actual GNOME Keyring
Secret Service. No in-memory credential backend supplies these commands. Linux
requires the explicit new private fixture, checks its empty store before login,
and keeps its registry under the new output directory. The preflight reads the
fixture directly rather than using a whoami request that could clear an existing
revoked session. HOME is never changed.

Four immutable project snapshots each rebuild and pass two ARM input scenarios.
Three committed upload acknowledgements and three committed listing
acknowledgements are dropped. Status/resume recovers the saved operations;
account separation, stale receipts, website publication, conflicting listing
pull/merge, browser metadata correction, withdrawal and republication all pass.
Two ordinary Counter frames were inspected: normal input changes 0 to 1 and
keeps both action buttons intact. Private-file and project-path exclusion checks
pass for every uploaded snapshot.

Two real scheduled-handler runs remove 30 temporary objects, retain all 19
accepted objects, and reduce reserved bytes from 155,757 to 62,601. Both historical
owner images and the current signed download remain exact. The final download
is 9,108 bytes, SHA-256
`1b1d4adfb454f316188a4ea2a0346c7062d689f40e41678e935f068a847535fe`.
Frozen inspection verifies it, and normal signed installation/launch on the
bundled VM returns result 1 with the OS responsive. This is also byte-identical
to the earlier macOS fixture download. Its reported callback timing is emulation
evidence, not a physical or native-host performance measurement.

The local store signs only with the explicitly public emulator fixture key
`18f925810bc262e8fccb42db1168b8265df6b3f6f6f7d94232b0b5924e6ebebb`.
The first journey reached accepted-download inspection but correctly failed:
the Linux bundle's selected store key does not trust that fixture by default.
Its logout, registry cleanup and service shutdown still passed. The corrected
harness verifies the known fixture public key and passes it through the existing
`--public-key` option for inspection/launch only when absent from bundled trust.
The failed and passing downloads are identical. No default key, signature rule,
SDK binary, firmware or production signing identity changed. The previous
unchanged Surface 3D/default-store-key launch evidence remains separate.

The native ARM controller and Landlock ABI 4 invoke the frozen x86-64 SDK through
the retained explicit interpreter. A second container owns the x86-64 GNOME
service. Both have read-only roots and external networking disabled. Unchanged
TLS passes through a private SSH Unix-socket forward and a loopback byte relay
to the macOS Node/Miniflare controller. Worker outbound requests are rejected.
Frozen commands cannot read the checkout or external Python and can use only
bundled libraries plus the declared system glibc/loader boundary. This validates
real Secret Service and local Worker behavior under emulation, not a native
clean-host installation or real GitHub OAuth.

Final logout revokes all test sessions. Three credential audits are empty; the
SDK retains then removes fixture-specific registry/operation records and
requests service shutdown. The service verifies an entirely empty collection,
stops its own processes and removes the temporary keyring/config/runtime
directories. Both final containers exit zero without OOM. No test container,
SSH forward or Worker process is left running.

### Durable changes and evidence

`vm/test-sdk-store-publish.py` now supports Linux with mandatory native isolation
and an explicit private credential fixture, optional interpretation, immutable
bundle verification, cleanup receipts and explicit test-key handling. The website
controller accepts a trusted external test-driver configuration for in-place
bundles and synchronized stdin/stdout/file handshakes. Malformed configuration
is rejected before creating a fixture; an unavailable driver records failure
and disposes its service without sending a request. Production handlers are
unchanged. The [Linux runbook](../sdk/HOSTS.md#linux-publication-qualification)
and website publication notes describe the interface and limits.

Evidence is retained under `build/sdk-linux-publication-v1/`: both journeys,
executed source copies, container identities, verified source/controller hashes,
TLS transport recipe, cleanup reports, frames and the accepted package. The
website source binding covers 41 controller/Worker/migration/package inputs.
The discovery containers found no usable Node runtime in the existing validator
image; one initially invoked that image's validator entrypoint and was retried
with the explicit shell entrypoint. Neither discovery was counted as a passing
publication run. The invalid/missing-driver negative probes and the first
fixture-key rejection are also retained.

| Final evidence | SHA-256 |
| --- | --- |
| Local Worker journey report | `2b09e1e15b1ea4e21452c7b0691887a4a6f1ff0a5551becc0c84db34d8ac82e5` |
| Frozen CLI/ARM report | `99319c9a16c62d0e0675d644030ec8186b6c6bc80d262f5535e169ff7090728b` |
| Secret Service cleanup report | `99f3de02b926e23e45d8cc6722c6166f8b6503a4da9e6dd7bc53101ab0f73d30` |
| OS publication harness | `e5f1de332ff58111834cb2c3a657eba3cbba7facd8407b7de374aee450584ca6` |
| Website publication controller | `b2d9f2f6df98fbbd17f0ead0eaafeaf330589c52b3a3adc60b363ecab0af7fb5` |

Validation passes **149 focused host tests**, the website production build and
controller lint, source syntax, documentation links/commands and public-tree
checks. Native macOS publication was not rerun. Remaining gates include native
Linux/Windows/macOS clean hosts and interactive credentials, full Windows freeze,
real GitHub/production publication and downloads, physical USB/input/performance/
power-loss/durability, upstream rebuild acceptance and independent developer
trials. No commit, push, deployment or calculator operation occurred.


## Windows inputs aligned with the store-enabled VM (2026-09-15)

The retained Windows project-source set still selected VM ELF
`5a0636eb915aaf8ea62b889932ee0538ca20c9371334905a970406bc58680105`.
Actual initialized-ELF verification rejects it because it contains no compiled
store keys. Pairing the older project manifest with the new VM also fails the
binary-identity gate. These are real-input failures, not invented native Windows
execution results. The checks prevented an inconsistent Windows package.

The refreshed Windows inputs now select the same `prime_g2_vm` ELF as the
store-enabled Linux distribution:
`195913e780bf8e4f67c35ef82f9cb90733b9af458d4cad901b19ffa2020b33ff`.
Its selected store key is
`422e6537d044dfea26dd01ce63dd0374f4eeaee8e9328aae2c0d332d7996d003`;
the separate emulator fixture remains
`18f925810bc262e8fccb42db1168b8265df6b3f6f6f7d94232b0b5924e6ebebb`.
Both compiled copies of each key table match. No key, firmware byte, storage
layout, signature policy or production signing identity changed here.

The VM/public-key files and matching prepared firmware sources, rebuild report
and log were extracted from the previously verified Linux binary/source archives.
The archive hashes were checked before selecting those members. The new Windows
project manifest combines them with the retained Windows QEMU
`5b499b64a5a8e8d833a387bff549cc6f72fa17ee6c29c7b6bb1cbf791dc22a76`
and its exact prepared source archive. All 4,399 prepared firmware files match
the retained byte-identical rebuild inventory. No fresh firmware compilation or
Windows runtime execution is claimed by this source assembly.

A fresh public snapshot contains 1,170 files, including the current SDK/host
recipes and revised Windows host guidance. The staged-source check matches all
351 selected SDK/recipe files and 139 newlib files. Changed staged `cli.py` and
`libc.a` bytes are rejected, restored and checked again. The first staging helper
referenced a nonexistent materials directory and failed; the corrected v2 check
uses the retained verified 22-component materials. The original attempt remains
retained and is not counted as a pass.

Three matching corresponding-source archives are assembled and independently
verified: 401 toolchain members, 827 runtime members and six project members,
including each group's manifest. The two unchanged groups use APFS clones of
the retained artifacts and preserve their exact hashes. Every outer member,
selected component/catalog record, embedded project archive and firmware source
inventory is verified again. The project group is newly assembled with the
current public snapshot and matching store-enabled firmware proof.

| Final input/artifact | SHA-256 |
| --- | --- |
| Public source archive | `f8a91f91e9b66974043ab88f4c97c36ac7fdaea0d23ba5d4ff65c8af0a27a739` |
| Windows project manifest | `e1d9004e4db8878115a6df40624352483c42771e3ed26b682fff3c0f2446c8f8` |
| lefony-sdk-source-runtime.tar.gz | `8f9eb0a686692d50ce17a5a927ae1ea7a20966e74ccdd3c6375d9eaff41d020a` |
| lefony-sdk-source-toolchain.tar.gz | `1c4f3c19554fe95a0b7bb75ec4a89de8b51f2b95c9455f7572820273dc8bf612` |
| lefony-sdk-source-lefony-qemu.tar.gz | `a426a65b14e9b797c733ff367948af8a8bc77cb458cedb57e93accbe32ef3307` |

The exact selection, files, source downloads and verification reports are under
`build/sdk-windows-store-inputs-v1/`, with a local README and
`input-selection-v1.json` for handoff. Use its explicit VM, public key and project
manifest together with the retained Windows components/materials and pinned
CPython/wheels; the older default ELF is not a substitute. Earlier source sets
and failed attempts remain untouched. The public snapshot precedes this ledger
annotation; all source inputs used by the packager are checked against it.

Validation passes 103 focused host tests for project/newlib correspondence,
firmware trust and source archive assembly, plus actual archive/input checks.
Documentation links/commands, whitespace and the public-source boundary are
checked before closing this checkpoint. A native Windows build/test host has
been requested; no complete Windows SDK, Credential Manager, native debugging,
clean-host or physical qualification is claimed. Real GitHub/production-store,
physical USB/input/performance/power-loss/durability, independent developer trials
and final release acceptance remain open. No commit, push, deployment or
calculator operation occurred.


### Bounded Windows-runtime compatibility experiment

A separate attempt tested whether the already retained Windows CPython could run
in an isolated Wine environment to enable intermediate freezing. The pinned
[PyInstaller 6.20 changelog](https://pyinstaller.org/en/v6.20.0/CHANGES.html)
documents exclusion of Wine substitute DLLs, but that does not establish that
this ARM host can execute the build. No macOS Wine app was installed and no host
security setting was changed.

Ubuntu Wine `9.0~repack-4build3` installs and its Linux launcher prints its version.
The original CPython 3.14.7 Windows ZIP remains hash-verified. Under the default
x86 interpreter, the actual Windows probe repeatedly reported `unexpected trap
-1` and was explicitly stopped (exit 137, no OOM). The retained explicit BuildKit
QEMU 10.0.4 interpreter avoided that repeated trap, but did not complete the
probe within 60 seconds. A fresh prefix with a private Xvfb display also failed
to complete within 150 seconds, with Wine device-service/threadpool waits. Even
a minimal `python.exe --version` against that warmed prefix failed to complete
within 60 seconds. None produced a Windows Python success record or SDK freeze.
The supervising scripts returning zero do not make their JSON `failed` results
successful runtime checks.

These probes used new private Wine prefixes in network-disabled, read-only-root
containers. Windows runtime ZIP extraction and all dependency installations were
kept separate from SDK release artifacts. Wine libraries, prefixes, package
receipts and failed logs remain retained; Wine DLLs were not added to an SDK.
Ten experiment containers are terminal without OOM, and owned Wine/Xvfb processes
were stopped. Exact commands, versions, image identities and all outcomes are in
`build/sdk-windows-wine-v1/checkpoint-v2.json`. Native Windows execution remains
an external requirement; the independent store-enabled source/input alignment
above is the completed progress from this checkpoint.

## Production-store migration rehearsal and repository cleanup (2026-09-15)

Read-only production inspection confirms migrations 0001–0005, one account,
one app, one published release and no build jobs. The deployed Worker is
`842577ed-7b27-4a5a-a4a0-2c31035f1b2e` from September 11. Wrangler reports 19
bucket objects totaling approximately 1.2 GB. SDK account access still returns
404 through curl; a separate Python-default-user-agent request received
Cloudflare error 1010. Neither qualifies a real SDK login. GitHub and Wrangler
authentication are available; existing secret names were checked without reading
their values. No production migration, deployment, publication or device write
occurred.

A limited read-only capture retains seven account/app/release tables and the
four public Surface 3D artifacts, totaling 109,890 bytes. Sessions, OAuth states,
rate-limit keys and secrets were not queried. Review, abuse-report and build-job
tables were checked empty by count. This is a rehearsal input, not a database
backup or whole-bucket inventory. All four downloaded hashes match their database
references, and SDK inspection verifies the 17,345-byte package with store key
`422e6537d044dfea26dd01ce63dd0374f4eeaee8e9328aae2c0d332d7996d003`.

The current Worker and migrations run against this input in isolated Miniflare
D1/R2 with outbound requests rejected. Ten checks pass: exact baseline schema,
seeded records/artifacts, rejection of unmigrated catalogue access, migrations
0006–0010 with valid foreign keys, preserved old rows and synthetic browser/OAuth
credentials, disabled legacy deletion/incomplete initial inventory, unchanged
catalogue/downloads, synthetic SDK account/owned-app/publication reads, two
scheduled-handler accounting passes, and D1 `quick_check`. The two passes charge
exactly 109,890 bytes globally and for the owner, with no deletion or pending
owner accounting. All copied records and download hashes remain unchanged.

The first run passed the functional checks but failed its final unsupported
`PRAGMA integrity_check`. The corrected run uses D1's documented `quick_check`;
both outcomes are retained. The passing report SHA-256 is
`7e615452f9e8872bbe91f26f656d945c220d0cffe82119a070f78591036ca648`, and the limited
snapshot SHA-256 is
`8d761d0d5ce6528c0e63417d46ce1c375566705c8ece9749dba9f34e874a58d4`.
Inputs, public artifacts, read-only receipts and both reports are in
`build/sdk-production-migration-v1/`; the website's
`docs/STORE-PRODUCTION-PREFLIGHT.md` records the remaining rollout. Postchecks
still show migrations 0001–0005, one published release, no build jobs, zero D1
rows written and a successful remote `quick_check`.

### User-authorized cleanup

After disk space fell to approximately 165 MB, the user requested removing
repository junk before further builds. Three older unpacked SDK copies were
compared completely against their retained archives and removed:
`sdk-maturity-release2`, `sdk-maturity-release3` and `sdk-shared-storage` under
`build/`. Every file, link and mode matched; generated Python caches, where
present, were separately archived and checked. The original SDK archives remain
at their original paths. Restore an old extracted path by unpacking its archive
at the original parent; the cleanup records contain the complete file inventory.

Another 259 byte-identical archive copies (9,900,692,988 logical bytes) now use
APFS copy-on-write clones. All archive paths and contents remain available;
future writes remain independent because these are not hard links. Final checks
verify every clone's hash, mode, modification time and independent inode, and
reverify all three retained SDK archives. A read-only evidence directory refused
one further clone operation; it stayed unchanged and its permissions were not
relaxed. The completed cleanup leaves approximately 8 GB free, with background
disk usage accounting for measurement variation.

Source changes, release keys, calculator backups, VM recovery snapshots and
final qualification reports remain retained. Git status was identical immediately
before and after cleanup. Exact removed paths, archive hashes and clone records
are in `build/sdk-cleanup-20260915/verification-v1.json` and its companion
receipts. Public-tree and whitespace checks pass. This resolves the immediate
host capacity constraint; SDK release, native Windows/clean-host, real OAuth,
physical and independent-developer acceptance remain unfinished.

## Real GitHub authorization and production SDK publication (2026-09-16 UTC)

The production website now runs the SDK account/publication implementation with
migrations through 0010. A full private 7,370-byte D1 export was verified through
both SQLite and the actual Wrangler local-D1 importer before migration. Both
restores preserve every original row/column and pass integrity/foreign-key
checks. The export SHA-256 is
`b6fe71956840a7a714d2b6388c9bf2b4d4ec4de7cfc0bce94abc8f9aaf09dbd8`.
The export, restored databases and Time Travel bookmark are private website
`.local/sdk-production-rollout-v1/` evidence, excluded from public source/assets.

The tested Worker/assets were sealed before deployment. Compiled Worker SHA-256
`aae728862f510b53c26ef59f2f4bac096e279f814291b5b75bdab9956d0c9116` also passes the
ten-check retained-record rehearsal. Initial production version
`719c53a3-05b9-4b6a-9453-de4b284a0a3d` held new submissions while inventory ran.
All four existing Surface 3D source/package/media downloads stayed byte-identical.

The real minute-17 schedule completed successfully: 24 ms CPU, 9,238 ms wall time,
no exceptions and no deletion. It inventoried four objects and four owner charges,
accounting exactly 109,890 bytes globally and for the existing owner. All namespace
and owner cursors completed; no pending owner charges remained. The initial
00:17:28 read preceded completion; all nine inventory checks pass at 00:18:34 UTC.
The database defaults remain 10 GiB managed total and 512 MiB per account. The
whole bucket reports 19 objects/about 1.2 GB, mostly SDK downloads outside the
managed namespace contract; retain a separate 2 GiB allowance and review before
publishing more SDK archives. Both legacy deletion gates remain NULL. No old-writer
drain or destructive legacy-cleanup qualification is asserted.

The same sealed code/assets were redeployed with only the publication flag enabled.
Version `0f6f59f8-41ee-43f3-8e63-cfff70ad65f2` receives 100% of traffic and public
capabilities confirm submissions enabled. Seven non-HTML public assets match
sealed hashes. Root HTML references the matching script/style but includes a
Cloudflare analytics injection; its raw bytes differ from the local HTML asset.

### Actual account, publication and download

The user completed GitHub sign-in, and the requested terminal code connected the
source SDK to the existing owner account. CLI login completed successfully and
stored the session in macOS Keychain. Separate CLI processes passed `whoami`,
`apps list` and `apps show surface-3d`; the signed-in production developer page
also shows the existing app and SDK access controls. GitHub repository scopes were
not requested. The SDK retains only its own scoped store credential in Keychain.
This is the working macOS host, not a clean-host or newly frozen-bundle result.

A separate [SDK Counter 0.1.0](https://lefony.com/#apps/sdk-counter) development
example was built from the basic SDK template. Its actual normal-input ARM replay
checks OK increment, touch reset and Back to the app menu. Two reviewed screenshots
come from that exact replay. The listing explicitly labels physical behavior
unqualified and permits source distribution under CC-BY-NC-SA-4.0. Archive review
finds only the app manifest, SDK lock, source and input test; no local paths,
credentials, build files or unrelated calculator data are included.

`publish --dry-run` independently rebuilds/tests the snapshot. The real
`publish --resume` uploads the six reviewed files (17,421 bytes total) and receives
an accepted release with publication revision 5. Saved-attempt status and owned-app
history reads return the same release. Public browser inspection displays its
actual owner, version, description, source/package links and two screenshots.

| Artifact | Exact identity |
| --- | --- |
| Release | `677f2f97-90aa-43a5-b576-c7c5881a9ce5` |
| Submission | `5b8aa9d74be302c0a05c558b1ffd5ad86927f942ad0fae47448f4fa863fe93bd` |
| Source, 2,519 bytes | `35a45a1fdf5d52d5db6c04bcf1403fcb307f6077fb1b3ff33a2315e05bfb34c7` |
| Unsigned package, 8,755 bytes | `33b31fb3f124473157749e48031bbaf94169068d38fd133ab757cf8af2bcc47b` |
| Signed download, 9,107 bytes | `9ce22623543aaa5252946914fa361a743774cb240ecf36f02eb95e9ec98e4e8a` |
| Existing store SPKI | `422e6537d044dfea26dd01ce63dd0374f4eeaee8e9328aae2c0d332d7996d003` |
| VM firmware | `195913e780bf8e4f67c35ef82f9cb90733b9af458d4cad901b19ffa2020b33ff` |
| Native macOS QEMU | `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0` |

Five public artifact downloads match the accepted hashes and exact submitted
source/media. The signed envelope contains the unchanged tested unsigned package,
verifies against the existing production key, and rejects a damaged signature.
Extracting the public source and rebuilding/tests produces the identical unsigned
package and passes the input replay. The unchanged signed download launches in
the matching VM through `launch --headless --test`. No re-signing or trust-root
replacement was used. The source checkout supplies the existing public PEM
explicitly because it does not contain a bundled desktop trust directory.

Post-publication D1 checks show two apps/two published releases and reconcile
162,505 bytes: 109,890 legacy bytes, 17,773 committed artifact bytes and 34,842
retained temporary upload reservation bytes. Accepted upload cleanup awaits its
normal expiry/schedule; these conservative charges are intentionally retained.
Foreign keys and `quick_check` pass. The older published SDK download catalogue
is unchanged, and no connected calculator was written.

### Validation and limits

Website build and lint pass. The full unit suite passes with two workers:
561 passed and one skipped. The initial unconstrained run overlapped other heavy
checks and had twelve five-second timeouts. The full browser run initially passed
60 of 61 cases; its app-removal fixture still expected DELETE. The fixture now
models revision-checked POST withdrawal and accepted receipts, verifies a cancelled
review sends no mutation, and asserts retry preserves the exact request ID/body.
All six affected app-manager/listing-editor cases pass in a focused rerun, with
reviewed desktop/mobile captures. These tests remain synthetic local tests.
Public-tree and whitespace checks pass.

Root evidence is `build/sdk-live-publication-v1/`, including the prepared immutable
attempt, non-secret account/publication receipts, downloaded artifacts, source
rebuild/input reports and `download-verification-v1.json`. Website rollout evidence
is `.local/sdk-production-rollout-v1/`. The website maintenance and preflight docs
record the same deployed state. The earlier cleanup receipts continue to retain
all SDK archives, release keys, calculator backups and VM recovery data.

This completes a real GitHub-authenticated source-SDK publication/download path.
It does not qualify every live conflict/revocation/recovery case, native Windows
or Linux, clean macOS hosts, new downloadable SDK assemblies, coordinated GitHub
release publication, physical USB/input/performance/power-loss/durability, or
independent developer trials. SDK 1.0 remains incomplete and the goal stays active.


## 2026-09-16 UTC — public Linux SDK and verified installer

The [Linux release record](SDK-LINUX-RELEASE.md) binds the four exact published
SDK/source archives, unchanged production Worker, eight-entry download catalogue,
full R2/public readbacks, default-trust SDK Counter execution and installer tests.
Website validation passes 566 unit tests with one skipped and all 62 browser tests,
plus build/lint. This supersedes the preceding checkpoint's older-download and
partial browser-suite status. Real GitHub publication still uses the macOS source
SDK; this Linux public journey validates download/inspection/launch, not real OAuth.

Root evidence: `build/sdk-linux-web-install-v1/`. Private website evidence:
`.local/sdk-linux-release-v1/`. Multipart transport emitted internal proxy warnings,
but completed uploads and every full readback/public hash matched. No claim of
injected retry qualification is made. The initial inventory summary is retained
in its log; the later metadata file is explicitly the post-rollout inventory.

Authorized repository cleanup additionally consolidated 44 duplicate artifact
files using APFS copy-on-write clones, preserving paths, hashes, modes, times,
xattrs and independent inodes (385,016,636 logical bytes across the selected
copies). Eleven unsuitable candidates were skipped. The test's redundant SDK
extraction was removed only after exact archive and delta verification; its
1,050,008 KiB allocation and stopped container are recorded. Thin VM/APFS storage
may delay host-visible reclamation. Existing artifacts, keys and recovery data
remain retained.

The user selected maintainer macOS trials. This is the active trial scope;
independent developer acceptance and native Linux/Windows qualification are not
claimed. Windows freeze, clean-host acceptance, physical USB/input/performance,
power-loss recovery, flash durability and complete release integration remain.
SDK 1.0 is incomplete and the goal remains active.


## 2026-09-16 UTC — current macOS bundle and maintainer trial

The new local macOS ARM64 **0.2.0-dev** bundle finishes full packaging with the
current SDK, new native QEMU build and the same store-enabled VM used by the public
Linux archive. It remains a development candidate. The earlier public macOS
archive has not been replaced by this checkpoint.

### Durable packaging changes

Every supported packaging host now requires explicit `--project-sources`.
The shared project validator supports Darwin/arm64 QEMU source/build records and
binds the selected VM to its retained byte-identical rebuild and all 4,399 prepared
source files. The actual staged and frozen SDK/host recipes match 351 public
source inputs. macOS QEMU's actual PyInstaller input records bind the selected
binary to its relocated/signed output; repeated identical input records are
accepted, while conflicting sources, missing binary classification, wrong host,
changed firmware/source and altered final output are rejected. Its report is
explicitly scoped to QEMU; separate dependency checks remain required.

The packager also includes `SDK-*.md` reference documents used by the new release
links. Host/setup documentation describes the new required source argument.
All 134 relevant packaging/project/source tests pass. The first test run had one
outdated parser-error expectation, corrected for the shared required argument.

### Exact local artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| macOS SDK | 156601379 | `60e42ad1a99b3fd783df65f57548af078e5f1c981d1ba829c402477870e89d2f` |
| Toolchain sources | 180139527 | `c811be8b913920cc3ee0ca7a4147c0c8d092d2c90a1f7f7838ee7a6f3bae9150` |
| Runtime sources | 396258029 | `5c37fb6a3bfe443a7648bec5c38dd08babb61bc165eb8b39f70a33a76c016d2d` |
| Lefony/QEMU/VM sources | 51684117 | `be2dc3cab881c52c46ce2b3e1c2742075f239961df7b2b322b88098ad9a02cc8` |

The archive matches all 1,930 regular files and 18 symbolic links, including
modes and the complete member set; internal checksums pass. The three source
archives independently match every file against retained materials and their
manifests (47 toolchain, 312 runtime and five project/evidence files). The native
source catalog contains 46 components. All 33 top-level Homebrew dylibs map to
retained component sources/recipes; Pillow's reviewed wheel/native source and
installed/frozen byte checks pass separately. The latest retained Pillow component
was added after the initial freeze correctly rejected the older source catalog.

QEMU was rebuilt natively from the pinned 11.1.1/r70 checkout, including the
current EP0-stall peripheral code, without private home paths. Input SHA-256 is
`d23e8442c1ad3e33cb55865dbd636644a42992d7db0c4bf828977c43c01105b7`;
relocated output is
`d96f54b6fda100d9b7f8667954f6cc9b9058a6e04a1926947ae870909ec0190d`.
Its source archive is
`daafdda3543867ab0216a450c9e4585f3d85ca6421379e5f65bffb13b9db92d2`,
with 12,267 inventoried file/link entries. Existing build pins and release trust
roots are unchanged. VM ELF remains
`195913e780bf8e4f67c35ef82f9cb90733b9af458d4cad901b19ffa2020b33ff`.

### Native executable evidence

- Eight external templates pass from a relocated path with spaces/Unicode,
  with network, Homebrew and checkout access denied. Actual normal-input ARM
  tests, source export, workspace clone/export/restore, source-level GDB and
  external CMake with Python discovery disabled pass.
- Notebook touch editing saves exact expression/export bytes. Cold preview
  retains the same bytes and identical frame pixels. Notebook and UI Gallery
  paragraph/layout cases pass; representative frames were visually reviewed.
  Recorded scenario durations include deliberate input/save/replay work:
  Notebook edit 22.616 s, cold replay 12.772 s, Notebook paragraphs 12.098 s and
  UI Gallery paragraphs 15.976 s. These are individual scenario measurements,
  not an interactive latency distribution or an accepted performance budget.
- Eight native HTTPS cases pass, including the real lefony.com public-root
  check, explicit trust isolation, timeout/cancellation and worker cleanup.
- Fifteen local fixture account cases use actual frozen CLI processes and native
  Keychain with denied checkout/Homebrew access. Final logout/empty-store checks
  remove temporary fixture credentials. The user's production session is retained.
- All eleven isolated companion cases pass, including request/response streaming,
  policy/TLS errors, deadline/cancellation, truncation, disconnect and repeated
  same-session requests. USB traffic uses the QEMU model; this is not physical USB.
- The frozen CLI reads the existing real GitHub-authorized Keychain session,
  account and owned apps. Exact public SDK Counter and Surface 3D packages pass
  signature inspection and two independent launches each with default bundled
  trust/firmware. No re-signing or explicit trust override is used. The initial
  Python urllib package request returned HTTP 403; the ordinary public curl
  download succeeded and matched the original hash. This does not qualify every
  HTTP client or a new frozen-executable browser login.
- The launcher and bundled QEMU pass strict local code-signature verification.
  This does not establish Developer ID signing, notarization or a clean Mac.

### Trial and retained evidence

`build/sdk-macos-store-assembly-v1/` retains the candidate, source groups,
matching manifests, logs, failure archives and qualification reports. Failed
freezes exposed duplicate DATA/BINARY and repeated input records in PyInstaller's
analysis table; no failed candidate was published. Their full trees were archived
and every member/hash/mode verified before the duplicate folders were removed.
The new QEMU scratch tree was removed only after full source-archive verification,
with the binary, original log and selected build metadata retained. The public
build log redacts only local checkout/build paths. Older evidence, keys and
calculator recovery data remain intact.

The [maintainer trial guide](SDK-MACOS-TRIAL.md) identifies the exact archive and
commands. A separate Notebook 0.6.2 project is prepared under
`build/sdk-macos-maintainer-trial-v1/Notebook/`. Its native Cocoa emulator was
launched with the synthetic `trial` workspace; user feedback is pending. The UI
automation provider does not select this unbundled QEMU application, so native
window interaction is not claimed as an automated visual/input pass. Guest
frames and the separate normal-input tests retain their stated scope.

Public macOS installer/download rollout, clean hosts, native Windows packaging,
physical input/USB/performance/power-loss/durability and full SDK 1.0 acceptance
remain unfinished. Current user trials are maintainer macOS trials; independent
feedback remains absent. No commit, push, GitHub release or calculator write
accompanies this checkpoint. Later status/trial documentation postdates the
archived source snapshot without changing its executable SDK identity.

## 2026-09-16 UTC — interactive emulator keypad and larger display

Maintainer feedback on the macOS trial identified a concrete usability failure:
the native QEMU display was too small and had no clickable HP Prime keyboard.
Current source `run` and interactive `launch` now open a loopback browser panel
with all 50 keys in the SDK matrix contract beneath a 640×480 display by default.
The Screen selector offers 480×360, 640×480 and 960×720, constrained by the browser
width. Canvas clicks scale to native 320×240 Goodix coordinates. Keypad clicks,
held keys and computer keyboard shortcuts use emulated KPP edges and normal OS
dispatch. Headless tests and the native debugger display retain their paths.

The panel binds a random-token session on an ephemeral loopback port. It checks
Host/Origin, limits request sizes and input values, uses no external assets and
exposes no arbitrary monitor command or file endpoint. Input is serialized;
short presses and repeated-key release gaps cross guest debouncing. Browser
blur/cancellation releases input and a bounded lease handles a disconnected
browser. Stop closes through the existing Home and storage-drain sequence.

Validation for this source revision:

- 43 focused panel, replay-lifecycle and emulator-failure host tests pass.
- A real ARM Notebook session in Chrome accepts clickable Enter, digits,
  Backspace from the computer keyboard, Esc and directional navigation. The
  temporary test edit was discarded, leaving the original trial list empty.
- A separate synthetic QA workspace passes browser-driven Goodix opening,
  select-all, clickable/physical-keyboard expression entry, all three exact
  screen sizes, normal stop and cold restart. The saved `1+2` expression and
  result `3` have identical content pixels on cold start. Selection borders and
  status text appropriately differ after restarting; full-frame equality is
  not claimed. Startup/saving progress frames require readiness waits in the
  browser harness. Final evidence has no browser script errors.
- The current CLI's separate headless Notebook startup passes, including Home
  and storage drain. Public source boundary and diff whitespace checks pass.

Private local evidence and the restart launcher are retained under
`build/sdk-emulator-panel-v1/`. The original
`build/sdk-macos-maintainer-trial-v1/Notebook/` project and its `trial` media are
retained; its prior SDK lock is preserved and explicitly updated for the source
revision. QA media uses separate workspace names. The updated source panel is
reopened for the maintainer's trial.

The macOS `distribution-v4` archive, its matching source groups and public
downloads are unchanged and do not include this panel. Refreezing/distributing
the UI and further human feedback remain open, as do native clean-host,
physical and final SDK 1.0 qualification. No calculator write, commit or push
was performed for this fix.

## 2026-09-16 — Browser emulator bundles and local cleanup

Published the frozen macOS ARM64 and Linux x86-64 SDKs with the current local
browser panel, all 50 Prime keys and larger selectable screen. Matching sources
and the source kit were refreshed; full R2 hashes, public binary/source-kit
downloads and corresponding-source routes verify. Windows source
inputs were updated locally; a complete Windows executable remains unavailable.
Exact hashes, validation, deployment identity, deletion receipts and limitations
are in [SDK-EMULATOR-RELEASE.md](SDK-EMULATOR-RELEASE.md). No physical calculator
writes, Git commit or push accompanied this refresh.

## 2026-09-24 — Website release and macOS compatibility

The current published macOS SDK matches the checkout's executable source and
passes Notebook replay against freshly built calculator OS VM version
`1.0.0+1790259014`. The full public SDK archive hash verifies. The calculator
release is now published, and the website selects and serves its verified
signed update and recovery assets. See [the release record](SITE-RELEASE-20260924.md)
for source provenance, artifact hashes and validation. The SDK remains
`0.2.0-dev`; this publication does not close SDK 1.0 or physical qualification.
