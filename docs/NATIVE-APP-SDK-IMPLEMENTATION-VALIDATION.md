# SDK 1.0 implementation and validation research

Historical research: 2026-09-11 through 2026-09-12. The findings below describe
those candidates, not today's missing features. Storage controls, C/C++ UI and
ARM preview, system APIs, USB/HTTPS, SDK accounts/publication and private signing
now have local implementations. Consult the
[current capability inventory](NATIVE-APP-CAPABILITIES.md) and
[implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md) for their evidence and
remaining qualification. Dated failures remain evidence for their original
inputs; later passes do not rewrite them.

This research assessed the working tree at that time against the
[1.0 plan](NATIVE-APP-SDK-1.0-PLAN.md), including the retained
[SDK account and publishing requirements](NATIVE-APP-SDK-MATURITY-PLAN.md#113-github-sign-in-and-the-developers-app-library).
It does not change scope or qualify a stable release. Dependency experiments
and pinned application inputs are distinguished from supported SDK contracts.

The implementation supports further development: mixed C/C++ compilation works,
and the [API 3 public foreground candidate](../sdk/FOREGROUND.md) now compiles on
both targets with passing ARM execution, guarded-memory, wait and copied-pixel
evidence. Production FILE3/FILE4 engines support data-only transactions and
large streamed files with independent snapshot readers. The [API 2 session and
newlib adapter](../sdk/FILES.md) connect real ARM stdio to those files using public
foreground yields. Reusable startup/libc build integration now exists as the
explicit `foreground-newlib-1` profile, with main-entry debugging and a relocated
bundled-runtime proof. A pinned minigzip consumer exercises actual streams.
The [API 4 input stream](../sdk/INPUT.md) now has ARM evidence for held/down/up
chords, ordered touch, overflow and focus reset. The next dependencies are full
libc/error qualification, complete storage controls and integrated applications.
C/C++ UI authoring, connectivity, account publication and release qualification
were substantial work at this snapshot. No R0–R6 milestone had met all its exit criteria.
See the [implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md) and the
[latest foreground validation](#14-public-foreground-candidate-and-validation-2026-09-12).
The subsequent [ordinary main/minigzip batch](NATIVE-APP-SDK-1.0-PROGRESS.md#conventional-main-developer-workflow-and-minigzip)
records actual main-entry debugging, relaunch fixes, standalone bundles and nine
ARM cases for the existing non-game C tool. Dated prototype findings below
remain evidence for their original candidates.

The [latest validation](#16-doom-savecold-reload-storage-scheduling-and-license-grant-2026-09-12)
records successful Doom gameplay, save/load, cold saved-state restoration and
clean exit after fixing idle delays between storage-verification steps. The
scoped app-side MIT alternative is now approved and applied. The failed update
in section 15 remains historical evidence; its workspace/root was reconciled
before testing the fix. These results do not complete the full Doom or SDK gate.

Configured C/C++ projects and coordinated source format 2 readers are now in the
working tree. See [the current ledger](NATIVE-APP-SDK-1.0-PROGRESS.md#configured-projects-and-coordinated-c-source-exchange)
for the recorded host/website qualification and actual Doom source bundle
checks. Section 1 reflects the current implementation; dated sections retain
their historical evidence. Section 9 separates new executions from retained
reports. The new readers still await coordinated release.

## 1. Source findings and implementation consequences at the research snapshot

| Area | Observed implementation | Consequence for 1.0 |
| --- | --- | --- |
| C execution | Builder supports C11/C++17, mixed linkage and an explicit conventional main/newlib profile. API 3 negotiates foreground entry, preemption, yield/sleep, exit and memory/frame queries on both targets | Complete library/function qualification and supported-host journeys; retain legacy behavior |
| Memory | Public ABI 1 retains 1 MiB code, 974,848 writable-data bytes and a 64 KiB stack. Explicit foreground entry adds 8,380,416 guarded bytes; clearing runs over 128 deferred events | Measure integrated application/OS peaks and physical behavior; the reservation reduces OS capacity even with legacy apps |
| C library | The explicit main profile integrates pinned newlib, real descriptors/stdio, initializer/exit handling and public foreground yields into ordinary developer builds | Finish library comparison, complete the function matrix and qualify real workloads/bundles across hosts |
| Graphics/input | Public API 3 copies RGB565 frames and exposes presentation counters; API 4 adds held/down/up keys and ordered touch with overflow/focus recovery, passing ordinary C ARM probes | Qualify input in integrated workloads and measure physical frame pacing before accepting Doom or a UI backend |
| Storage | `writeData` stages up to 64 KiB; converted FILE3/FILE4 apps use production data-only checkpoints on successful Close, while legacy FILE2 apps retain package-plus-data replacement | Public live commits, migration/recovery controls, quotas and import/export remain required |
| Large files | Production FILE4 now has an authenticated API 2 session, four snapshot readers, one growing writer and atomic replacement; signed ARM stdio matches an independent cold-output oracle | Complete bounded open/waits, quotas, metadata/enumeration, import/export and physical qualification |
| UI tools | App-side controls, references, replay and GDB exist | C/C++ source authoring, save-to-preview orchestration and layout inspection remain integration work |
| Source/build exchange | Configured projects select up to 256 C/C++ units; source format 2 carries C and the measured Doom tree with matching candidate website readers | Complete coordinated rollout; source exchange does not supply streamed runtime assets or account publication |
| Accounts/publishing | CLI has no login, owned-app library, link, publish or withdraw commands; `store/` is outside the source archive allowlist | Implement scoped SDK sessions and a separate coordinated listing/submission contract with the website |
| Connectivity | Inspected runtime services expose no application USB channel; existing USB management controls installation | Introduce an app-scoped transport and companion; installation transport is not an app networking API |
| Hosts | Runner uses Unix sockets, Unix QEMU socket arguments and `/dev/null`; recorded desktop bundle requires external GDB | Qualify native Windows control, host packaging and debugger setup explicitly |

Source anchors: [builder](../sdk/tools/build.py),
[startup](../sdk/lib/start.s),
[context entry/exit](../ports/lefony-prime-g2/ion/src/prime_g2/native_app_context.s),
[runtime](../ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp),
[memory mapping](../ports/lefony-prime-g2/ion/src/prime_g2/system.cpp),
[contract](../sdk/contract.json), [screen batches](../sdk/include/lefony/graphics_screen.h),
[storage integration](../ports/lefony-prime-g2/ion/src/prime_g2/app_management.cpp),
[document root codec](../ports/lefony-prime-g2/ion/src/prime_g2/app_document_root.h),
[file engine](../ports/lefony-prime-g2/ion/src/prime_g2/app_file_store.cpp),
[source validator](../sdk/tools/source.py), [CLI](../sdk/tools/cli.py),
[runner](../sdk/tools/runner.py).

Source formats 0/1 retain 64 files, 64 KiB per file and 512 KiB combined contents.
Format 2 raises these to 512 files, 256 KiB per source/notice file and 4 MiB
combined contents, with an 8 MiB encoded limit. Individual assets remain limited
to 64 KiB. Discovery still caps compilation at 64 units; `project.json` explicitly
selects up to 256. These bounds are tested against the real Doom source tree,
but the 28.8 MB WAD requires a separate streamed-asset contract.
See [configured projects and rollout](../sdk/PROJECTS.md).

The public foreground candidate uses nominal 10 ms user slices and resumes through a
low-priority foreground event after normal input dispatch. Its former dependency
on the 300 ms UI timer is removed. Unchanged surfaces no longer repaint after
every yield. The [current scheduling evidence](NATIVE-APP-SDK-1.0-PROGRESS.md#foreground-scheduling-and-redraw-integration)
does not qualify physical frame pacing or complete blocked-wait behavior.
Heap clearing now advances 64 KiB per event; heap setup and privileged work still
need explicit physical budgets.

`Volume` still configures littlefs `file_max` as
`MaximumPackage + MaximumData + 64`. FILE4 addresses this bound with an index
referencing immutable chunks of at most 130,944 bytes, rather than one
WAD-sized littlefs object. The host production engine has streamed the pinned
WAD successfully. The conventional guest adapter passes an independent streaming
oracle, and an earlier local Doom candidate consumed the WAD to render E1M1.
The latest package-upgrade/save/load attempt fails before launch. Quotas,
replacement headroom, integrated recovery and physical behavior still require
qualification.
Source: [production storage configuration](../ports/lefony-prime-g2/ion/src/prime_g2/app_storage.cpp).

## 2. External research and recommended proofs

### Runtime, libc and Doom

Newlib documents OS hooks and reentrancy requirements; its minimal examples
permit linking while some operations fail. Picolibc likewise requires allocation
and descriptor adapters for file streams. Neither library supplies Lefony's
execution, isolation or durable storage policy. Compare them with identical
allocation, formatting, startup, file and error workloads on ARM before choosing.
[Newlib system calls](https://sourceware.org/newlib/libc.html#Syscalls),
[Picolibc OS integration](https://github.com/picolibc/picolibc/blob/main/doc/os.md).

The researched Doomgeneric source defaults its zone allocation to **6 MiB**, in
addition to other allocations. Its default pixel buffer is 640 × 400 × 4 bytes;
resolution is configurable. Its WAD adapter uses `fopen`, `fseek` and `fread`.
These concrete requirements exceed the legacy callback memory profile. The
[pinned port and compile probe](../sdk/ports/doom/README.md) use 320 × 200 pixels; the
6 MiB zone is only part of the finished port's RAM requirement. The larger-heap
experiment proves capacity for that allocation, not the integrated peak.
[Zone allocation](https://github.com/ozkl/doomgeneric/blob/master/doomgeneric/i_system.c),
[display/input interface](https://github.com/ozkl/doomgeneric/blob/master/doomgeneric/doomgeneric.h),
[WAD I/O](https://github.com/ozkl/doomgeneric/blob/master/doomgeneric/w_file_stdc.c).

Doomgeneric's platform hooks and create/tick loop make it a useful early consumer.
Its tick structure could help a prototype, but adapting this one program to
callbacks would not prove conventional C execution for the platform.
[Porting instructions](https://github.com/ozkl/doomgeneric#porting).

First runtime acceptance: a mixed-source program enters `main` once, retains
stack/local and floating-point state across repeated waits, allocates and frees
memory, and recovers from exhaustion. A CPU loop and a blocked I/O call must both
allow OS termination. Test faults, cancellation and cleanup during every wait
state, and run unchanged ABI 1 packages afterward. Long privileged calls need
their own bounded execution path; current user-code deadlines do not provide it.

The current app-linked startup/helpers carry CC-BY-NC-SA notices; Doom sources
carry GPL notices. Resolve the exact linking and distribution path before
releasing a port. This research does not establish permission to relicense those
components. Game data is now pinned separately to the unmodified Freedoom Phase 1
0.13.0 WAD, 28,795,076 bytes, plus its license and credits. E1M1 is the selected
fixed workload; gameplay, saves, performance and the complete distribution path
still require qualification.
[Local licenses](../LICENSE.md),
[Doom source notices](https://github.com/ozkl/doomgeneric/blob/master/doomgeneric/w_file_stdc.c),
[Freedoom](https://freedoom.github.io/about.html).

### Storage and a non-game consumer

Littlefs documents atomic rename and file commits on sync/close, with correctness
depending on the block adapter's synchronization semantics. Those primitives
support the existing root-swap experiment, but do not establish an application
transaction contract, bounded latency or physical NAND qualification.
[Littlefs usage and synchronization](https://github.com/littlefs-project/littlefs#usage).

Keep the successful generation-pair experiment. Before enabling a production
format, resolve whether its data object becomes a bounded index referencing
separate large file objects, or a different versioned representation is needed.
Define quota and recovery headroom for old/new file sets and retained upgrades.
Do not embed large file contents in the legacy data record.

A useful acceptance workload streams a deterministic file larger than 64 KiB,
seeks across transfer/page boundaries, modifies a small range, commits, cold
restarts and verifies the exact result against a host oracle. RAM must stay
bounded independently of file size. Interrupt every modeled write/erase in the
production path, including conversion, commit, upgrade acceptance, deletion and
cleanup. Exercise full media and corrupt referenced objects. Confirm unchanged
packages are not rewritten and measure metadata/write amplification.

Zlib's existing `minigzip` is a candidate non-game consumer: it exercises real
compression/decompression and ordinary streams. Use a pinned existing program,
known gzip fixtures, independent decompression/hash checks, truncated inputs and
output exhaustion. Choosing it would make a limited zlib recipe part of that
proving app; it need not create a general optional-library support commitment.
[Upstream minigzip](https://github.com/madler/zlib/blob/develop/test/minigzip.c).

### UI authoring and graphics

Use the existing Lefony/Escher components and public SDK graphics/input services
for the two-screen app. Keep layouts and actions in C/C++ sources, with custom
drawing and normal Prime key/touch behavior. Rebuild the actual ARM package and
relaunch a selected synthetic-workspace scenario after source edits. Show a
stale-preview state on build failure. Capture and review long-text, keyboard,
modal, empty and error states, with source/bounds inspection. Measure the entire
edit/build/install/relaunch loop before setting a target.

### SDK accounts, folder publication and connected apps

GitHub documents a device authorization flow for CLI applications, enabled in
the application's settings, without a client secret in the client. It specifies
polling intervals, slowdown, cancellation and expiration handling. A
store-mediated browser flow using the existing website identity is another
candidate. Choose the flow with the website implementation, then issue scoped,
revocable store sessions rather than treating GitHub repository access as store
authorization.
[GitHub authorization flows](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps#device-flow).

Implement local `store/` scaffolding and deterministic submission snapshots
alongside the server session/listing/submission APIs. Keep listing files separate
from installed runtime assets. Define revision conflicts, version immutability,
upload retention and finalization before adding retries. The same submission
must produce one release; different bytes at an existing version must conflict.
Record unsigned payload and signed-envelope digests separately: the current
workspace signs local packages with an emulator fixture, while distribution
adds a different signature. Exact-byte testing must identify which bytes each
hash binds, and verify the published inner payload matches the tested payload.

Validate with two accounts, paginated owned listings including drafts/withdrawals,
login/logout/expiration, missing media, excluded private files, interrupted
uploads, repeated finalization and alternating website/SDK edits. Local dry runs
must remain offline. These backend/browser journeys were not rerun in this review;
the website is a separate repository.

The app HTTPS bridge is a different capability from SDK publishing. Design
bounded framed messages with app/session/request identities, flow control and
explicit installer exclusion. Use a controlled HTTPS endpoint to test streamed
responses, certificate failure, redirects, cancellation, disconnect and slow
consumers. A lost response after a mutation can leave the outcome unknown;
automatic retry must respect idempotency.
[HTTP retry semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2).

## 3. Initial validation and evidence limits (2026-09-11)

This section preserves the original research candidate and executions. They are
historical results for these exact hashes; section 5 identifies the newer build.

Validation host: macOS 26.6.2 ARM64, Python 3.14.6, pinned SDK GCC 16.2.0.
Base commit: `91701e213d74918226b3692f570079c2c13d9000`, with pre-existing
tracked and untracked changes. That commit alone does not identify the candidate.

| Identity checked during this review | SHA-256 |
| --- | --- |
| SDK source identity from the SDK's own identity function | `ede3ee906cdb651e472d052f82c0628062f313e8b23f6b10ae15f33d8a45f335` |
| Existing `prime_g2_vm` ELF | `b94460e09d9ac1170a5cd9f499c401ea1d7756c02d545a8ba059f55b3bb1d2c8` |
| Existing physical `prime_g2` BIN | `c26af5f8b7a709ef6bd0c2f90a6e0e4a83d83cbf6ce0886b49bb4412c0177a1b` |
| Development QEMU | `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0` |

These match the recorded source/firmware/development-QEMU candidate. The packaged
desktop QEMU has a separately recorded identity. No firmware or QEMU rebuild was
performed in this research pass; hash agreement is not a fresh source-to-binary
reproducibility proof.

| Fresh check | Result |
| --- | --- |
| `make test` | 547 passed; two documented private DTB/DTS fixture skips; 86.36 seconds |
| Host storage experiment, included in `make test` | 860 modeled interruption cases; a 65-byte checkpoint programmed 10,240 bytes and wrote zero package bytes |
| FILE3 codec/preserved-reader tests, included in `make test` | Passed; this is codec/old-reader qualification, not a production large-file test |
| `make check-public` and `git diff --check` before the report | Passed |
| `.venv/bin/python sdk/tools/cli.py doctor` | Passed tool availability; host/device qualification correctly remains not checked |
| `.venv/bin/python vm/test-sdk-developer-loop.py` | Passed: external path with spaces/Unicode, normal key input, cold restart/export/restore, real GDB breakpoint/step, source-located fault and failure not masked by relaunch |
| `.venv/bin/python vm/test-sdk-compatibility.py --corpus build/sdk-maturity-corpus` | Passed unchanged Counter and Surface 3D ABI 1 package checks and interactions |
| `.venv/bin/python vm/test-native-app-sdk.py` | All 38 ARM cases passed with OS responsiveness, including isolation, invalid pointers, timeout, stack overflow, service validation and syscall flooding |
| Report links/whitespace and final public-tree check | 17 relative links/anchors passed; public boundary passed with 712 files; `git diff --check` passed |

Fresh logs, copied JSON reports and their checksums are retained locally under
`build/sdk-implementation-validation-20260911/`. This evidence includes synthetic
workspace/app results and remains outside the public source tree.

The developer-loop test deliberately induces an app fault and verifies a failed
replay report; that nested failure is expected and its outer test passes. The
isolation suite uses VM ABI 0 fixture packages; installed developer-loop and
preserved ABI 1 checks provide different coverage. None alone qualifies the full
signed-install, storage, input and lifecycle matrix.

The compatibility fixtures are preserved local binaries, not a complete public
released-binary corpus. Existing broader math/graphics/input, signed storage,
coordinate-touch, smoke, website and distribution results remain historical
[candidate evidence](NATIVE-APP-MATURITY-EVIDENCE.md); they are not reported as
new executions here. No physical device was accessed. Native Windows/Linux,
physical power loss/endurance, actual touch feel, timing and independent
developer trials remain unqualified in this review.

## 4. Recommended implementation order and gates

1. **Close R0 decisions with executable proofs.** Pin the four apps/assets;
   compare libc and UI candidates; specify runtime/memory, large-file roots and
   SDK/store schemas; assign host/hardware qualification resources. Record
   rejected options and measured budgets. This research does not close R0.
2. **Deliver the shared C/graphics/input foundation.** Support mixed C/C++,
   persistent execution across waits, bounded allocation, pixel transfer,
   held/released keys and OS termination. Keep ABI 1 binaries unchanged.
3. **Integrate storage and stdio.** Use the selected real non-game consumer and
   WAD reads to expose missing semantics. Complete interruption/full-media and
   package/data compatibility tests in production code, then qualify hardware.
4. **Integrate authoring and preview against those interfaces.** Prove the
   document app's UI first, then its durable workflow. Start native Windows
   runner/debugger packaging now rather than deferring discovery until R5.
5. **Implement accounts/publishing and the app bridge as separate workstreams.**
   Account/folder tooling can progress before R1–R4 integration finishes. Both
   require shared contracts and independent failure tests; store publication
   does not imply device installation or app network permissions.
6. **Converge on four complete applications and release bundles.** Run clean-host
   journeys, mixed website/SDK publication, independent developers and physical
   qualification on exact candidate artifacts before freezing 1.0.

For each implementation change, preserve evidence tying test cases to SDK,
package, firmware and QEMU identities. Runtime/shared UI changes need sequential
physical/VM builds and relevant emulator regressions; normal touch acceptance
must traverse Goodix and normal dispatch. Freeze physical performance budgets
from early measurements, and keep documented remaining limitations with every
release candidate. See [repository instructions](../AGENTS.md).

## 5. Implementation evidence update (2026-09-12)

The later runtime/memory batch rebuilt both firmware targets sequentially. This
review checked their hashes against the ARM reports, checked all recorded source
digests in the execution, memory/pixel and libc reports, and reran the full host
suite. Earlier results above do not stand in for checks against this candidate.

| Evidence | Result and limit |
| --- | --- |
| Fresh `make test` | **551 passed, two expected private DTB/DTS skips**, 89.09 s on macOS ARM64 |
| Execution ARM report | Passed one-main execution, register/VFP/flags/stack preservation through 52 preemptions and one yield, exit, infinite-loop Home interruption and relaunch; VM-only opt-in |
| Memory/pixel ARM report | All five installed cases passed: allocation/copy/save/relaunch, unnegotiated access, both guard pages and heap execution rejection; OS responsive |
| Memory measurement | 6 MiB allocation plus 153,600-byte pixel buffer; usable heap 8,380,416 bytes; reserved kernel heap 20,080,608 bytes; setup 17 model ms on each of two launches |
| Non-file newlib ARM report | Allocation/exhaustion, realloc preservation, formatting/parsing, sort/search, math and explicit unsupported-file errors passed; stdio is not implemented |
| Preserved ABI 1 packages | Counter and Surface 3D unchanged bytes passed interaction checks on the current VM |
| Firmware builds and smoke | Both targets compiled; current VM direct ELF, verified U-Boot boot and protocol checks passed; physical target not flashed or tested |
| Doom compile proof | All 80 portable translation units compiled without portable-core edits; 274,047 code/constants, 59,995 initialized data and 243,608 BSS bytes before dead-code elimination; no runnable port yet |

Current VM ELF SHA-256:
`e123b09c22ef980079c49a5a87d687ef652d95cfb0014d81cd6bad9187e914f5`.
Physical-target BIN SHA-256:
`b139e260da2f390ea3abc777d1fa8e12109660c1ed5a7cbffc01c3dc916015e8`.
Development QEMU retains the identity in section 3. Source checks cover 19
recorded memory/pixel digest entries, eight execution entries and three libc
entries, with no mismatches. These counts include repeated probe sources across
test variants; they are not a complete clean-rebuild reproducibility audit.

The original memory test initially misinterpreted a signed negative fault value;
the corrected test passed. Existing firmware compiler/linker warnings remain
recorded in the ledger. Logs, reports, hashes and that initial failure are kept
under ignored `build/sdk-memory-pixels/evidence/`; the fresh full host log is
included there. No website changes, deployment, Git push or physical-device
operation was performed as part of this review.

Implementation priority is now concrete: finish the library/profile decision;
make streamed file/stdio and data-only recovery work with the pinned WAD and a
real non-game C consumer; coordinate the larger C source/project format with the
website; finish frame/input integration. Extend the existing UI components with
the two-screen ARM proof while the document workflow converges on storage. Keep
SDK/store authentication distinct from the app USB/HTTPS bridge. Native Windows
and Linux journeys, independent developers, physical durability/performance and
the final linked-artifact license inventory remain release gates.

## 6. Working-tree review before production transactions (2026-09-12)

This research pass reread both plans and checked the current compiler, source
archive, CLI, startup, runtime services, storage integration and runner. The 1.0
plan remains authoritative, including maturity sections 11.3–11.5 for SDK
accounts and folder publication. No implementation or release scope was changed.

The current work is a useful foundation, with no fully accepted R0–R6 milestone.
Source format 2 has closed the earlier C source-exchange gap in the candidate.
The remaining critical path is a supported execution/library profile, production
streamed files and stdio, then complete application workloads. UI integration
and the separate account/companion contracts can be developed alongside it.

### Fresh validation

Host: macOS 26.6.2 ARM64, Python 3.14.6, GCC 16.2.0. SDK identity:
`058cdbab689add148fba9b4c415c6e8108b0ff01419dab3efc34983a795bd0a0`.
The existing VM ELF, physical-target BIN and QEMU hashes match section 5.
No firmware or emulator rebuild was performed in this research pass.

| Executed check | Result and qualification limit |
| --- | --- |
| `make test` | **560 passed, two documented private DTB/DTS skips**, 105.31 s |
| `vm/test-sdk-c.py` | Passed configured C11/C++17 source-2 extraction and identical rebuilt package bytes, signed synthetic installation, normal key input, checked services and cold persistence |
| `vm/test-sdk-execution.py` | Passed one-main execution, integer/VFP/flags/stack preservation through 39 preemptions and one yield, exit, CPU-loop Home interruption and same-OS relaunch; VM-only opt-in |
| `vm/test-sdk-memory-pixels.py` | All five installed cases passed: 6 MiB allocation/pixels/save/relaunch, unnegotiated access, both guard pages and heap execution rejection; OS remained responsive |
| `vm/test-native-app-sdk.py` | All **38 ARM isolation/service cases passed on the current VM ELF**, including invalid pointers, privileged access, timeouts, stack overflow and syscall flooding |
| CLI `doctor` and `--help` | Required tools found; host/device qualification correctly remains not checked; proposed account/publish commands are absent |
| `make check-public`, `git diff --check` | Passed; 741 public files checked |

The memory proof measured 8,380,416 usable heap bytes and 20,080,608 bytes
reserved for the kernel heap. Setup took 18 and 16 model milliseconds on its
two launches. The Home replay's 1,021 ms includes deliberate held/released-key
waits and is not input latency. Neither measurement qualifies physical timing.
The 38-case isolation suite uses VM ABI 0 fixtures; signed installed C/runtime
tests cover different paths and do not replace a complete legacy/release corpus.

Thirty source-digest entries in the retained execution/memory/libc reports
matched the working tree. All 26 files in the sealed source-2 evidence index
matched their hashes. Its 401 website tests, ten browser tests and Doom compile
result remain previously recorded executions, not fresh results from this pass.
No website deployment, Git push or physical-device operation was performed.

Logs, pre-review reports, fresh ARM reports and hashes are retained under
`build/sdk-implementation-review-20260912T090522Z/`. The edited research document
is the only source-tree change made by this pass; existing work is preserved.

### Next implementation acceptance cases

These are proposed tests to close the remaining implementation gaps, not claims
that the behavior already exists.

| Work | Required next proof |
| --- | --- |
| Runtime/library decision | Compare newlib, Picolibc and the current subset on identical ARM workloads; define supported functions, startup/cleanup, errors and allocation limits. Exercise real timer/input/file waits and forced exit with resource cleanup |
| Files and stdio | Stream the pinned WAD and a deterministic file beyond 64 KiB with bounded RAM, random seeks and partial edits; verify a host hash after durable commit and cold restart. Small saves write zero unchanged package bytes |
| Recovery and upgrades | Interrupt the actual production write/erase/commit/cleanup paths, fill or damage media, and fail first-launch migration. Retain a readable compatible package/data pair, the anti-downgrade watermark and unrelated apps |
| Doom and non-game C | Run the fixed Doom workload with saves, held keys/combinations, Home exit and measured frame/memory behavior. Pin an existing tool such as minigzip and compare streamed output with an independent oracle, including failures |
| UI authoring | Reuse existing Lefony/Escher components in the two-screen ARM app; edit C/C++ sources, reproduce/debug a layout defect and review normal-input screens |
| App connectivity | Exercise an app-scoped USB/HTTPS stream against controlled fixtures: bounded buffers, backpressure, timeout/cancel, TLS/redirect errors, disconnect and isolation from installer authority |
| SDK account publication | Use two accounts and multiple releases to test login/logout/expiry, all-owned-app pagination, linking, required folder media, private-file exclusion, retry/finalization, immutable-version conflicts and alternating website/SDK edits |
| Release qualification | Use exact bundles on native Windows x86-64, macOS ARM64 and Linux x86-64; complete independent developer trials, hardware power-loss/performance tests, app-key enrollment/revocation, artifact licensing and post-deployment download verification |

The external references in section 2 were rechecked for library OS hooks,
littlefs commit semantics, Doom's platform/file interface, GitHub device
authorization and HTTP retry behavior.
They support the proposed integration choices; they do not demonstrate those
integrations running on Lefony. Close R0 decisions and obtain measured workloads
and qualification access before assigning a defensible completion estimate.

## 7. Production transaction implementation and validation (2026-09-12)

The next implementation batch moved the FILE3 design into the real shared
littlefs/NAND volume. It now supports verified immutable package/data objects,
atomic roots, first FILE2 conversion, data-only checkpoints, retained upgrade
pairs, schema-matched acceptance and rollback, and interrupted-uninstall cleanup.
App management loads converted apps, saves on normal Close and performs signed
package upgrades through that path. The older FILE2 path remains available for
apps that have not opted in. See [implementation details and limits](NATIVE-APP-DOCUMENT-TRANSACTIONS.md).

This closes part of the earlier transaction-integration gap, not R2 as a whole.
No public checkpoint/migration/rollback service is advertised. Data objects are
still limited to 64 KiB; streamed large-file objects, descriptors, stdio, live
snapshots, quotas and guaranteed recovery headroom remain required. The VM-only
resumable runtime's forced-exit ownership policy also needs integration; it
currently treats OS-owned Home/Close termination as successful.

Final `make test` passed **561 tests with two expected private DTB/DTS skips**
in 112.54 seconds. The scoped storage checks passed six tests, including **512 modeled
interruption cases** in the production engine. A measured checkpoint programmed
10,240 NAND bytes with a 131,333-byte unchanged package and zero package-object
bytes written. Corruption, full media, repeated saves, maximum IDs, empty data,
generation exhaustion, cancellation and multiple interrupted uninstalls also
passed. The separate preserved old-reader test still rejects FILE3 without
changing synthetic NAND. These model results do not qualify physical NAND.

Five installed ARM cases passed on the final VM: normal data-only Close and cold
reopen, signed USB upgrade with dirty schema-0 acceptance, clean root-only
acceptance, rejection of writes against a mismatched schema, and retention of
the pending pair after an app fault following a staged write. First conversion
is seeded by the host-compiled production engine; it is not evidence of a public
guest checkpoint syscall. Configured C/source-2 persistence, unchanged Counter
and Surface 3D ABI 1 packages, legacy storage/icons with nine apps, and direct
ELF/verified U-Boot/protocol smoke also passed.

Both firmware targets compiled sequentially. The VM ELF is
`76d2ad67687a49c20ac5762550d1fcf53bbed7b19728e51e1de7879f8f0e0d63`;
the physical-target binary is
`cb67703cf073c2304cf6ad9e441567bd36fe2544747b2620213c15a44a2358dd`.
The physical target was not flashed or tested. Existing upstream compiler/linker
warnings remain. QEMU and the SDK identity remain those recorded in sections
5–6. Exact logs, reports, source hashes and intermediate test failures are
retained under `build/sdk-production-documents/evidence/`.

No milestone is declared complete. Large files and real stdio remain the next
storage dependency for the pinned WAD and non-game C consumer. Doom is still a
compile proof, not a runnable or release-qualified port. Website publication,
account workflows, UI authoring, connectivity, host/hardware qualification and
the other proving applications retain their full planned scope. No physical
operation, website deployment or Git push was performed in this batch.

## 8. Production streamed files (2026-09-12)

The [FILE4 engine](NATIVE-APP-LARGE-FILES.md) now adds real chunked files to the
same volume, with directories, seek/read, replacement, partial edits, rename
and deletion. Its bounded index preserves ABI 1 private bytes separately and
uses the existing atomic package/data root transaction. Capacity admission
follows orphan collection so an interrupted large stream cannot prevent retry.
The earlier statement that there is no production streamed-file engine is now
historical. Public descriptors, app scheduling, stdio, quotas and import/export
remain unfinished; no public file capability is advertised.

Fresh local evidence includes **564 passing host tests with two expected private
DTB/DTS skips**, and a subsequent final six-test storage run. The latter includes
**630 FILE4 interruption cases**, plus full-media, corrupt-chunk, unavailable-block,
directory, cancellation/retry, abandoned-stream and file-restoring package-rollback
checks. FILE3 retains its separate 512-case matrix. The exact retained FILE3
reader and the preserved base FILE2 reader reject FILE4 without NAND mutation.

The pinned **28,795,076-byte** WAD was streamed with 2048-byte buffers and
cold-read to its original hash. A 37-byte edit rewrote one 130,944-byte chunk,
programmed **159,744 NAND bytes**, and matched a separately computed Python hash
for the entire edited file. Unchanged package bytes were not rewritten. The host
volume object occupies 262,416 bytes; the small stream buffer is not its total
memory cost. These results prove the internal storage workload, not guest stdio
or a runnable Doom port.

Five signed ARM save/upgrade cases passed with FILE4 and preserved a streamed
asset's complete hash. The corresponding five FILE3 cases also passed on the
new VM. Initial file seeding uses the host-compiled production engine; the guest
tests exercise normal byte-store saves, cold reopening and signed upgrades.
The five memory/pixel cases, configured C/source-2 persistence, unchanged ABI 1
packages and direct ELF/verified U-Boot/protocol smoke passed. The VM reports
19,818,464 bytes reserved for the kernel heap and the unchanged 8,380,416-byte
experimental app heap. Its 18/14 ms heap setup timings are model measurements.

Both firmware targets compile. VM ELF:
`ff260fae1538d9dabef120be6cd6731331b5ed52961e65a73827b11341168798`.
Physical-target BIN:
`d7cecf31f527cabf8ff786c55a03f0d4baf334395b86b2e7954e228d49250132`.
Missing minimal-libc string functions were replaced with bounded scans/copies
after the initial target failures; final builds retain the existing upstream
warnings. Exact logs, source hashes, reports and earlier failures are retained
under `build/sdk-large-files/evidence/`. No physical operation, website deployment
or Git push was performed, and no SDK 1.0 milestone is declared complete.

## 9. Current integration findings and validation refresh (2026-09-12)

Both plans were reread against the current sources. The 1.0 plan governs;
maturity sections 11.3–11.5 remain required through its explicit reference.
The code now supports the internal large-file architecture, but a successful
host WAD workload is not evidence of conventional ARM stdio or playable Doom.
No R0–R6 milestone has all its acceptance evidence.

### Concrete implementation dependencies

1. **Make file sessions usable by conventional programs.**
   `AppFileStore::Store` has one reader or writer, and `begin` requires the final
   output length. It cannot yet represent an input stream kept open while an
   unknown-length output grows. Add bounded app-owned descriptors, independent
   reader positions/snapshots and a growing writer. Preserve chunks referenced
   by open readers during collection and define rename/unlink visibility.
   The namespace must come from the verified running app, not a caller-supplied
   app ID. Test stale handles, simultaneous input/output, relaunch cleanup,
   seek/tell/EOF and failures on full media. The real
   [minigzip 1.3.1 source](https://github.com/madler/zlib/blob/v1.3.1/test/minigzip.c)
   opens input and output together, closes both, then unlinks the input; use
   synthetic copies for its qualification. This is a candidate to pin, not an
   already selected or working port.
2. **Integrate bounded waits with execution and lifecycle.**
   A read at a new chunk currently verifies up to 130,944 bytes synchronously,
   even though it returns at most 2048 bytes. Small transfer buffers alone do
   not bound privileged latency. Move verification and file work through bounded
   steps, with copied request ownership and completion/error delivery. Give
   foreground resumption its own normal-dispatch scheduling path; the existing
   300 ms timer is insufficient for the intended frame loop. Preserve keyboard,
   Goodix, Home and power priority. Test termination during preparation, reading,
   writing and commit, including the point after which cancellation cannot
   undo a durable result.
3. **Specify exit and stdio together.**
   The newlib experiment's `_open`, `_read`, `_write`, `_lseek`, `_close` and
   `_fstat` still return `ENOSYS`. Implement their real error/descriptor behavior,
   buffering and documented durability semantics. Home currently returns the
   same successful runtime result used by app management to save staged private
   bytes; distinguish clean program exit, forced termination and fault before
   relying on automatic cleanup for file transactions. Both
   [newlib](https://sourceware.org/newlib/libc.html#Syscalls) and
   [Picolibc](https://github.com/picolibc/picolibc/blob/main/doc/os.md) require real
   OS adapters for file streams. Keep newlib as the measured integration candidate;
   the comparative library/profile decision remains open.
4. **Finish accounting and promote contracts coherently.**
   Current catalog logical usage sums package/private-data bytes and icons,
   omitting named-file contents. Physical allocated/available accounting is
   separate. Add named-file metadata/enumeration, logical usage, quotas and
   replacement/recovery headroom before exposing file capacity to apps or hosts.
   Promote execution, heap, pixels and file services through negotiated contracts
   with matching loader, SDK, package/manifest and website readers. ABI 1 meanings
   remain unchanged. See [file sessions](../ports/lefony-prime-g2/ion/src/prime_g2/app_file_store.h),
   [read verification](../ports/lefony-prime-g2/ion/src/prime_g2/app_file_store.cpp),
   [lifecycle/accounting](../ports/lefony-prime-g2/ion/src/prime_g2/app_management.cpp)
   and [runtime](../ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp).

The next integrated acceptance case should run ordinary C `main` on ARM, keep
an input file larger than 64 KiB open while producing a growing output, close
and cold-reopen the output, and compare it with an independent host oracle.
Include allocation failure, short/error transfers, full storage, cancellation
and an interrupted save. Then use the same public adapters for the pinned WAD
and Doom saves. Gameplay, held keys/combinations, Home response, frame-time
distribution and integrated memory peaks remain required; linking or a first
frame does not complete the Doom gate.

### Other work that can proceed alongside the C/file integration

| Area | Recommended implementation proof | Acceptance still required |
| --- | --- | --- |
| UI authoring | Reuse existing Lefony/Escher components and SDK source tooling in the two-screen app | Preserved handlers, actual ARM preview, source/layout inspection and reviewed normal-input states |
| SDK accounts/publication | Shared listing/submission contract, scoped revocable store sessions, offline folder snapshots and immutable publication attempts | Two accounts, all-owned pagination, first release/update, upload recovery, ownership/version conflicts and alternating SDK/website edits |
| App HTTPS bridge | App/session/request framing, bounded streaming, backpressure and exclusive firmware-operation ownership | Controlled TLS/redirect/timeout/cancel/disconnect fixtures, bounded cache, credential isolation and unknown mutation outcomes |
| Release qualification | Exact supported host/board matrix, artifact inventory and independent external-project trials | Native Windows/macOS/Linux journeys, physical performance/durability, compatible distribution terms and downloaded artifact verification |

For accounts, [GitHub device authorization](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps#device-flow)
provides polling, expiry and slowdown behavior but does not supply store ownership
or SDK session policy. For the HTTPS companion,
[HTTP retry semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)
require care with non-idempotent requests after uncertain completion.

### Fresh checks and retained evidence

| Check executed in this refresh | Result |
| --- | --- |
| `make test` | **564 passed, two documented private DTB/DTS skips**, 123.68 seconds |
| `.venv/bin/python vm/test-sdk-execution.py` | Passed installed ARM one-main execution, integer/VFP/flags/stack preservation through **38 preemptions, one yield and 39 resumes**, CPU-loop Home interruption and same-OS relaunch |
| `.venv/bin/python scripts/fetch_sdk_doom.py --offline` | Verified pinned engine, WAD, license and credit inputs; did not run Doom |
| SDK `doctor` and `--help` | Required local tools found; physical/host qualification remains not checked, and proposed SDK account/publish commands remain absent |
| Retained large-file evidence hashes | All **72 entries** matched: 24 source files, five artifacts, eight old-reader sources and 35 sealed evidence files |
| Sources embedded in retained FILE3/FILE4 and memory ARM reports | All **43 entries** matched; repeated source entries are included in this count |
| `make check-public`, `git diff --check`, document checks | Passed; **62 local links/anchors** checked across both plans and this report, with no trailing whitespace |

The ARM refresh used VM ELF
`ff260fae1538d9dabef120be6cd6731331b5ed52961e65a73827b11341168798`.
Its Home replay took 1,032 ms including intentional held/released-key waits;
that is not a measured physical input latency. The earlier firmware builds,
website tests, WAD workload, memory/isolation cases and smoke reports remain
retained executions, not fresh runs. Matching hashes establish identity, not
additional behavior coverage or a complete reproducibility audit.

Fresh logs, reports and digest checks are retained under
`build/sdk-research-refresh-20260912/`. This refresh changes this research document
only. No firmware rebuild, website deployment, Git push or physical-device
operation was performed. The four application journeys, independent trials,
host/hardware qualification and app-linked distribution review remain open.

## 10. Foreground scheduling implementation (2026-09-12)

The scheduling work identified in section 9 is now integrated: foreground wakes
follow normal input dispatch, preserve the last real input snapshot and redraw
only changed surfaces. Key repeat survives frequent wakes, and UI timers include
time spent executing app work while retaining their 300 ms interval. Full input
queues, supported sleep/file waits, frame pacing and public execution negotiation
remain separate requirements.

The final candidate measured 32 guest yields in **45 model ms**, compared with
**10,810 ms** on the preserved prior firmware. Host tests, installed scheduling,
execution preservation, memory/pixel isolation, normal input, the 38-case ARM
service suite, unchanged ABI 1 packages, both target builds and boot/protocol
smoke passed. See the [implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md#foreground-scheduling-and-redraw-integration)
for exact hashes, commands, limits and the corrected compatibility invocation.

This removes a shared throughput obstacle for conventional C/file adapters; it
does not connect descriptors or stdio to the FILE4 engine. Simultaneous readers
and a growing writer, app-owned handles, bounded storage work, error mapping,
quotas and import/export are still the next file-integration work. Doom remains
unimplemented beyond its core compile and internal WAD-storage proofs. The full
1.0 scope is unchanged, and no release or physical qualification is claimed.

## 11. Independent file readers (2026-09-12)

The file-session dependency in section 9 now has its first production piece:
four independent, owner-checked snapshot readers coexist with the existing
known-length writer. Each reader preserves its immutable chunks across later
namespace commits. Collection reclaims obsolete chunks after close, and
uninstall refuses an app with live readers. Pending chunk verification advances
in 2048-byte content steps without retaining the caller's output pointer.
The [file contract](NATIVE-APP-LARGE-FILES.md#transactions-and-readers) describes
token lifetime, visibility and the remaining synchronous-open limitation.

Fresh validation:

| Check | Result |
| --- | --- |
| Production snapshot fixture under ASan/UBSan | Simultaneous 261,925-byte input/output, cold output oracle, independent positions, token ownership/exhaustion, stale handles, close during verification, replacement/rename/unlink, reclamation, corruption and full-media reads passed |
| Pinned WAD through the new reader | 28,795,076 bytes; original SHA-256 matched after 14,294 bounded verification steps; partial-edit whole-file oracle and zero unchanged package writes still pass |
| Final `make test` | 564 passed, two expected private DTB/DTS skips, 127.66 seconds; includes 630 FILE4 and 512 FILE3 interruption cases |
| Final ARM compatibility/storage/memory | Five signed FILE4 save/upgrade cases, five memory/pixel cases and unchanged Counter/Surface 3D packages passed |
| Firmware/boot | Both targets compiled sequentially; direct ELF, verified U-Boot and protocol smoke passed |

The larger fixed volume exposed a stack overflow in the FILE3 host fixture,
which placed many volume instances on the test stack. The fixture now uses
heap ownership for those instances, preserving its assertions and sanitizers.
The final host volume is 378,464 bytes; the physical-target symbol is 377,992
bytes. VM kernel heap reserve is 19,703,776 bytes, with the experimental app heap
unchanged at 8,380,416 bytes. Exact candidate hashes and limitations are in the
[implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md#independent-snapshot-readers);
logs and sealed reports are under `build/sdk-file-snapshots/evidence/`.

The upstream interfaces still make growing output and real stdio necessary:
[Doom's standard-C WAD backend](https://github.com/ozkl/doomgeneric/blob/dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284/doomgeneric/w_file_stdc.c)
uses file open/read/seek, and [minigzip](https://github.com/madler/zlib/blob/v1.3.1/test/minigzip.c)
keeps input and output open during processing. The next acceptance case must
exercise an output whose final length is not supplied in advance through real
[newlib OS hooks](https://sourceware.org/newlib/libc.html#Syscalls), on ARM, with
clean/forced/faulted exit cleanup and explicit errors/durability. The current
known-length host copy does not satisfy that gate. Public descriptors, quotas,
import/export and the supported execution profile remain unfinished; Doom is
still not playable. No release, deployment, Git push or physical operation was
performed, and all R0–R6 acceptance requirements remain in scope.

## 12. Growing files and random access (2026-09-12)

The writer no longer requires a final output length. Its production volume API
supports truncate/update/append, staged reads, random seeks/backpatches and
zero-filled gaps, alongside independent committed snapshot readers. Only the
current uncommitted generation can be rewritten. The existing root transaction
publishes the final result atomically; failed or cancelled staging preserves
the prior root. A bounded chunk cache shares space with the final index buffer.

The host fixture adds **718 interruption cases**, a simultaneous input and
variable-length output workflow with an independent cold-output SHA-256 oracle,
520 staged-chunk rewrites, EOF/size errors and full-media abort/retry. Growth
preserves the 24-block maintenance reserve; a maximum-size package upgrade and
compatible rollback pass after the full-output failure. It also
writes the pinned WAD through the growing API and cold-reads its original hash.
`make test` passes 564 tests with two documented private-fixture skips, and the
final scoped file/oracle test passes. Both firmware targets compile. The five
signed FILE4 ARM byte-store/upgrade cases and five memory/pixel cases pass.
See [exact measurements and candidate identities](NATIVE-APP-SDK-1.0-PROGRESS.md#growing-files-append-and-backpatches).

The next integrated work is the app-owned file facade and C adapters: derive
the namespace from the authenticated launch, copy bounded request data, deliver
completion/errors, preserve OS input priority while waiting, and close or abort
handles appropriately on clean exit, Home and faults. Distinguish libc buffering
from durable commit and retain package/data compatibility during initial file
conversion and upgrades. Public metadata/usage, quotas, import/export and
negotiated execution still need implementation. The current transformation is
a storage fixture, not a substitute for the required existing non-game C tool.
Doom remains an engine-compile and internal WAD-storage proof, not a playable port. No public file
capability, release, deployment, push or physical qualification is claimed.

## 13. Authenticated files and current validation (2026-09-12)

This review reread both plans, traced the current file service through the
authenticated loader, OS polling, storage engine and newlib adapter, checked
the ARM reports against their recorded source hashes, and repeated website
validation. The 1.0 plan remains authoritative, including maturity sections
11.3–11.5 for SDK accounts and folder publication. Its deliberate deferrals
still apply. No R0–R6 milestone is complete.

The new [file session](../ports/lefony-prime-g2/ion/src/prime_g2/app_file_session.cpp)
connects the production engine to installed apps through API 2, capability bit 8
and service 10. It captures identity at launch, retains only OS-owned request
copies and exposes four snapshot readers plus one writer. Completion tokens
prevent accidental mutation replay. Initial conversion uses committed private
bytes; Home/fault cleanup aborts unclosed staging and drains committed operations
before other storage users can proceed. Both firmware targets compile this
service. The [newlib adapter](../sdk/experiments/newlib_files.c) has real
descriptor I/O and errno mapping, but its waits still invoke VM-only resumable
execution. This distinction prevents a passing experiment from being advertised
as a supported physical C runtime.

The signed ARM workload creates a 261,925-byte input, processes it with an output
stream open simultaneously, backpatches its header, checks close, atomically
replaces a destination and cold-reopens the result. An independent Python oracle
checks 261,932 exported bytes from the guest's synthetic NAND against SHA-256
`dc8b637fd01afaf5634fd712b511d88bdd6b651e59b5edf6478e2b02994dd2c0`.
All four Home/fault/normal-exit/nonzero-exit relaunch cases pass. These remain
platform fixtures; the required existing non-game program is not implemented.

Current evidence, bound to VM ELF
`2352761f5183ccc40472a22dba5c0e769b36dbf76c2bccbafe88d9e0d1f23b3a`:

| Check | Result and limit |
| --- | --- |
| OS host suite | 566 passed, two expected private DTB/DTS skips; 143.31 s |
| Production storage interruption fixtures | 648 FILE4 cases including 18 atomic replacements, 718 additional growing-file cases, 512 FILE3 cases; host model evidence |
| Signed ARM files/lifecycle | Two streaming/cold-oracle cases and four same-OS cleanup/relaunch cases pass |
| ARM regressions | 38 isolation cases, five FILE4 save/upgrade cases, five memory/pixel cases, schema rejection, unchanged Counter/Surface 3D and three smoke paths pass |
| Firmware builds | VM and physical compilation pass sequentially; existing upstream linker warnings remain |
| Website scoped tests/build/lint | 166 scoped tests pass; build and lint pass |
| Website full suite | Default runs fail with two, then seven five-second timeouts; one-worker run passes 401 tests with one skipped in 51.56 s |
| Documentation/public boundary | 141 local links/anchors across 11 documents, whitespace checks in both repositories and `make check-public` pass |

The website failures vary across recovery and firmware tests. The one-worker
run retains their assertions and the same five-second limit; no test or product
code was altered to obtain that pass. Contention sensitivity is an inference,
not a proven root cause. The default parallel command remains a validation issue.
The skipped real-SDK store test requires `LEFONY_SDK_TEST_PROJECT`; this review
does not count it as a completed publication journey. Recorded local evidence
and source snapshots are in `build/sdk-file-sessions/evidence/`. Earlier evidence
directories remain historical; their source hashes must not be relabeled as
this candidate. The physical binary is
`8d2cfd85e42ab8cb7c8b2bf919c7f966fe502206f4355a7c4cd9e120952ccde1`;
it has compilation evidence only.

### Source research that affects the next implementation

- **Close and exit have observable durability semantics.** Newlib's normal
  `exit` performs stream cleanup before `_exit`. The ARM cases confirm that a
  nonzero exit can therefore commit a file while discarding staged private
  bytes. Define the public runtime's behavior explicitly; do not promise that
  nonzero exit rolls back already completed closes.
  [Newlib exit](https://sourceware.org/newlib/libc.html#exit).
- **Doom needs a save-path change.** The pinned `G_DoSaveGame` ignores close and
  rename results and removes the previous save before replacing it. Use checked
  close followed by the new atomic replacement, retain the prior save on failure,
  and show success only after completion. Test this through the actual game,
  including full output and interruption, rather than relying on the storage
  fixture alone.
  [Pinned Doom save code](https://github.com/ozkl/doomgeneric/blob/dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284/doomgeneric/g_game.c#L1570).
- **A library choice still needs measurement.** Newlib now has working file
  integration; Picolibc documents the OS adapters it would also need. Compare
  the same startup/allocation/formatting/stream/error workload before selecting
  the shipped profile. Pin a real non-game consumer; zlib 1.3.1's `minigzip`
  remains a candidate, not an implemented port or a newly adopted dependency.
  [Picolibc integration](https://github.com/picolibc/picolibc/blob/main/doc/os.md),
  [versioned minigzip source](https://github.com/madler/zlib/blob/v1.3.1/test/minigzip.c).
- **UI reuse still needs integrated qualification.** Measure the existing
  components' footprint, keypad/Goodix behavior and actual ARM preview latency
  with the document app. Review its layouts and error states alongside its
  interaction assertions.
- **Publishing and app connectivity remain separate contracts.** GitHub device
  authorization supports CLI login without a client secret and requires polling,
  slowdown and expiry handling; the store still needs scoped, revocable sessions
  and revision/idempotency checks. For the HTTPS bridge, a lost response to a
  mutation must not cause an unconditional retry.
  [GitHub device flow](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps#device-flow),
  [HTTP retry semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2).

### Remaining implementation and acceptance order

1. Finish the supported negotiated foreground runtime, allocation, waits,
   exit status, held/released input and pixel/frame contract. Preserve legacy
   packages and qualify cancellation in CPU loops and blocked file operations.
   Measure integrated OS/app/stack/frame memory and privileged latency. Current
   2048-byte content steps do not bound synchronous index/allocation traversal.
2. Complete live sync, enumeration, logical usage/space, quotas, import/export
   and package/data migration/recovery controls. Extend full-media, corrupt-data,
   failed-close and cancellation cases through the actual stdio/ARM boundary.
   Littlefs's atomic operations and sync contract support the design, but the
   NAND adapter and hardware still need qualification.
   [Littlefs durability contract](https://github.com/littlefs-project/littlefs#usage).
3. Integrate the pinned non-game C consumer and playable Doom on those public
   interfaces. Test useful output and errors; for Doom include WAD streaming,
   gameplay, save/load, key combinations and Home. Resolve the exact app-linked
   distribution path before publishing the affected artifacts. Engine compilation
   and an internal WAD hash do not meet this gate.
4. Complete the two-screen authoring comparison, select the useful existing
   math/system subset, and implement app USB/HTTPS. Their document and connected
   applications converge on the same runtime, files and preview tooling.
5. Implement SDK login, all-owned-app listing, project linking and folder
   publication/update with website parity. Qualify immutable versions, ownership,
   upload recovery and stale edits; then validate exact released bundles on
   native Windows x86-64, macOS ARM64 and Linux x86-64.
6. Run independent-developer trials and actual physical performance, power,
   storage and recovery qualification. Complete coordinated documentation,
   downloads and release verification against exact candidate hashes.

The runtime and file foundations now support concrete port integration work.
They do not justify a completion date or a stable SDK 1.0 claim. No physical
operation, publication or deployment is part of this research refresh.

## 14. Public foreground candidate and validation (2026-09-12)

The runtime dependency has progressed from private VM services to an explicitly
negotiated public candidate. API 3/capability 16 is compiled into both targets;
services 11/12 provide foreground entry, yield/sleep/exit, a guarded heap and
copied RGB565 pixels with presentation counters. The [contract](../sdk/FOREGROUND.md)
defines bounds, ownership and errors. The [latest implementation evidence](NATIVE-APP-SDK-1.0-PROGRESS.md#public-foreground-runtime-and-file-waits)
records exact candidates and measurements.

The implementation leaves legacy ABI 1 layouts and behavior intact. Larger
memory is mapped only after explicit entry and incremental clearing. Normal OS
input continues while clearing and sleeping; ordinary input does not shorten a
sleep. A source review found that the initial sleep deadline could round down
with the coarse IRQ clock. The final candidate uses the same monotonic clock as
the public time query and passes the minimum-duration ARM assertion.

| Validation layer | Evidence on the final candidate | Limit |
| --- | --- | --- |
| Public runtime ARM | Eight variants pass: allocation/registers/sleep/pixels, undeclared capability, CPU loop, long sleep, pre-entry access, both guards and heap execution | Model behavior; full held/released input and physical timing remain open |
| Public file waits | Two real newlib stream/backpatch/cold-output and four lifecycle cases pass through public yields | Maintainer adapter/fixtures; default developer builds still use callbacks |
| Regression | 38 isolation, five older memory/pixel, seven current schema/USB cases, unchanged Counter/Surface 3D and boot/protocol smoke pass | Optional pre-schema-1 loader check skipped without its ELF; unchanged package checks did run |
| Host suite | 567 passed, two expected private DTB/DTS skips | macOS host, synthetic fixtures |
| Firmware | VM and physical target builds pass sequentially | Compilation does not qualify a physical calculator |
| Website | Build/lint, 167 scoped tests and one-worker full suite (402 passed, one skipped) pass | Default parallel timeout failures remain unresolved; real-build store test requires its project fixture |
| Documentation/public boundary | 174 local links/anchors in 13 documents, both whitespace checks and public-source boundary (775 files) pass | Local working tree; no deployment or push |

The final VM ELF is
`846c594e6a9a3bd8506713fe00f9ca3377fba3066283bf42a9d746c68f8d303c`;
the physical BIN is
`303a40d1ab1cf9f59ee90b2cb88a67020f25b535ec250c5994c89ab1e3fc9128`.
Memory allocation succeeds for the 6 MiB test zone, but this does not prove Doom's
integrated peak. The 8 MiB reservation reduces OS capacity on both builds;
measured application peaks, worst service stalls and physical budgets are still
required. Evidence is retained under `build/sdk-foreground/evidence/`, separately
from the sealed older API 2 evidence.

The next concrete implementation is reusable startup/library and build/bundle
integration around these services, plus complete held/released input. Newlib and
Picolibc both still need actual OS adapters for the claimed file/error behaviors;
the comparison should use identical ARM workloads, not just library sizes.
[Newlib OS hooks](https://sourceware.org/newlib/libc.html#Syscalls),
[Picolibc integration](https://github.com/picolibc/picolibc/blob/main/doc/os.md).

Doom remains an 80-unit compile proof. Its pinned save path still needs checked
close and atomic replacement without first deleting the old save. Verify the
change through actual gameplay/save/load, full-output errors and interruption,
then measure WAD streaming, input combinations, frames and memory. The file
engine's durable rename is a prerequisite, not evidence that this application
uses it correctly. The exact app-linked license/distribution path remains open.
[Pinned save implementation](https://github.com/ozkl/doomgeneric/blob/dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284/doomgeneric/g_game.c#L1570),
[littlefs synchronization contract](https://github.com/littlefs-project/littlefs#usage).

R0–R6 remain incomplete. UI authoring, quotas/recovery/import-export, connectivity,
account/folder publication, the other proving apps, clean-host bundles and actual
physical/independent-developer qualification retain their plan gates. The new
public runtime makes port integration concrete; it does not establish stable 1.0.

## 15. Doom integration and validation refresh (2026-09-12)

Both plans were reread against current source, retained reports and upstream
documentation. The 1.0 plan governs; maturity sections 11.3–11.5 remain required
for accounts/folder publishing. Its superseded math inventory and proposed
numeric targets do not become additional gates. No R0–R6 milestone is complete.

### Current evidence and a failed integrated test

The [Doom adapter](../sdk/ports/doom/platform.c) now uses ordinary main/newlib,
public file/foreground/input services and copied RGB565 frames. The earlier
launch report and inspected images show Freedoom E1M1, a changed view after
movement/turning, game menus and ammunition falling from 50 to 47 after firing.
The full 28,795,076-byte WAD is streamed from FILE4. This establishes useful
execution beyond compilation or a title screen, with normal KPP input. It does
not establish completed save/load, error handling or physical playability.

The current preparation script adds checked save close and atomic replacement
without deleting the previous save first. It also restores a successful Quit
path when the upstream SDL-only block is disabled. These changes are in the
prepared portable engine and public adapter, with hashes/notices retained;
there is no special Doom syscall. Their intended behavior still needs execution
evidence on the changed candidate.

The stronger `vm/test-sdk-doom-gameplay.py` run **failed before launch**, in
`Client.install` → `Client.wait(timeout=120)`, after sending the installation
commit request. The terminal error was `App operation timed out`; the test did
not reach main-entry GDB, movement/save/load assertions, cold reload or clean
quit. No final success report exists. The log is
`build/sdk-doom-gameplay.log`; the failed project/workspace is under
`build/sdk-doom/gameplay-project/`. The cause and final committed catalog state
are unresolved. Reconcile package/root state from the preserved synthetic
workspace before another write. A larger timeout alone would not demonstrate
recovery, bounded progress or correct update semantics.

Candidate separation matters: the successful image hash is
`f54fa57270dfd2bb773bb811f509b3e62045e491ccbdfcd0495872323d19ff69`;
the newer, installation-failing image is
`aa3b6e7f976001189a482b96d43d47329049d19d8b455439a5f8ede5762e2405`.
The launch report's platform, preparation and runner hashes differ from current
source. Its file adapter and test-script hashes still match. The newer image
contains 315,758 code bytes and 430,904 static-data bytes; the 64 KiB stack and
8,380,416-byte heap are reservations, not measured high-water marks. Debugger
pauses and emulator wall time cannot qualify frame timing.

Two smaller retained ARM proofs match their recorded current source inputs:
relative-path stdio/backpatch/replacement with an independent cold-output oracle,
and automatic SDK Home cleanup for an app that owns Back. The latter asserts
leaving the native container and draining storage, then confirms saved visit
counts 1 and 2 across cold launches. These do not substitute for Doom recovery.
The [file guide](../sdk/FILES.md) now documents the adapter's bounded leading
`./` handling and mkdir-only trailing slash.

### Checks executed for this research refresh

| Check | Result | Scope |
| --- | --- | --- |
| SDK runtime/C/input/contract/project tests | **120 passed**, 33.40 s | Fresh host tests, including real ARM compilation and sanitized input logic; not a fresh guest run |
| Website SDK contract/device/store tests | **206 passed, one skipped**, 7.30 s, one worker | Fresh structural/ownership/mock transport checks; optional real-SDK project fixture absent |
| Sealed input-stream evidence | **440 artifact/source entries hash-match** | Integrity of retained evidence; not re-execution |
| Sealed main/minigzip evidence | **906 artifact/source entries hash-match** | Integrity of an older firmware candidate; not current-firmware requalification |
| Current Doom save/load test | **Failed during installation** | Gameplay and cold-save assertions not reached |
| Documentation/public boundary | **110 local links/anchors pass; 813-file public boundary passes** | Six documents checked; whitespace checks pass in both repositories |
| Physical devices and native host matrix | **Not run** | No physical durability, timing, Windows/Linux or independent-developer acceptance claimed |

Executed commands:

```sh
.venv/bin/python -m pytest -q tests/test_sdk_runtime.py tests/test_sdk_c.py tests/test_sdk_input_stream.py tests/test_sdk_contracts.py tests/test_sdk_project.py
# In the website repository:
npm test -- tests/sdk-contract.test.ts tests/app-device.test.ts tests/app-store.test.ts --maxWorkers=1
```

The inspected firmware hashes remain VM
`501abb1fd60d8afcc66a5c4cb54106664340d0451f34e85e634a1c209cea8e7e`
and physical
`8995689fa449d355d448d9951990ab50d29f05467551ee36bfb8c4653367461d`.
The QEMU hash remains
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
No firmware was rebuilt for this refresh. Prior full-suite counts belong to
their recorded batches; the focused tests above are the fresh results.

### Source research and implementation decisions

- **C library:** retain newlib as the working candidate while comparing the
  same startup/allocation/stdio/error workload with a maintained alternative.
  Both newlib and Picolibc document OS integration requirements. Select from
  actual ARM behavior and footprint, then publish the supported function matrix.
  [Newlib OS hooks](https://sourceware.org/newlib/libc.html#Syscalls),
  [Picolibc OS integration](https://github.com/picolibc/picolibc/blob/main/doc/os.md).
- **Storage:** littlefs documents atomic namespace operations and commit through
  sync/close, conditional on correct device synchronization. Lefony's layered
  file index, package/data roots and NAND adapter need their own integrated
  interruption/full-media tests. Short transfers do not bound index traversal.
  [Littlefs durability](https://github.com/littlefs-project/littlefs#usage).
- **UI:** use existing Lefony components and public copied-pixel/input services
  for the two-screen workload. Measure footprint and actual ARM preview latency;
  retain developer-owned C/C++ handlers and inspect a layout defect.
- **Publication:** GitHub device authorization is a viable CLI option with no
  embedded client secret; honor expiry, cancellation and polling slowdown.
  Store-scoped revocation, stable ownership, complete owned-app pagination,
  immutable versions and stale website edits remain separate implementation.
  [GitHub device flow](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps#device-flow).
- **Connectivity:** implement a distinct app channel with bounded streaming and
  a paired HTTPS companion. Preserve TLS identity checks and an explicit unknown
  outcome after a lost mutation response; do not retry it unconditionally.
  [HTTP retry semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2).
- **Distribution:** the GPL engine, SDK CC-BY-NC-SA headers/inline functions,
  startup/newlib adapters and linker inputs require a resolved artifact-level
  licensing path. Freedoom's BSD asset terms address game data only. Audit the
  actual link map, generated inputs and notices; obtain applicable grants or
  implement an independent compatible interface before releasing the affected
  binary. No license was changed or grant inferred in this review.
  [Repository terms](../LICENSE.md),
  [CC-BY-NC-SA conditions](https://creativecommons.org/licenses/by-nc-sa/4.0/),
  [Freedoom data terms](https://freedoom.github.io/about.html).

### Remaining work in acceptance order

| Work | Next concrete acceptance |
| --- | --- |
| R0 decisions | Resolve linked-artifact inventory, libc/UI/math choices, all four pinned workloads, actual host versions/owners and hardware access |
| R1 foundation | Complete function/error coverage, integrated OS/app memory peaks, qualified useful system/math adapters and physical input/timing |
| R2 files | Reconcile the failed large-data package update; add live sync, enumeration/usage, quotas, user import/export and recovery controls; test interruption/full media through actual C apps |
| R3 UI | Visually edit and regenerate the two-screen app without losing handlers; run/debug the real ARM package and inspect states/layout defects |
| R4 connectivity | Exercise isolated streaming, cancellation, disconnect/reconnect, malformed messages and TLS failures against a controlled service |
| R5 integration | Complete Doom saves/errors/resources, minigzip resource/data exchange, document and connected apps; qualify SDK login/folder publish/update and website parity |
| R6 release | Run exact bundles on native Windows/macOS/Linux, independent developer trials and physical power/storage/performance tests; verify deployed docs/downloads against those artifacts |

UI and connectivity prototypes can proceed alongside storage recovery once the
minimum public runtime is available. SDK publication is retained required scope;
optional libraries and the old broad math inventory do not re-enter as hidden
requirements. The evidence supports continued implementation, not stable 1.0 or
a defensible completion date. This refresh changes research/developer documents
only; it performs no device write, release, deployment, commit or push.

## 16. Doom save/cold reload, storage scheduling and license grant (2026-09-12)

The unchanged save/load image from section 15 now passes the strong workload
on updated firmware. A read-only inspector using the production volume/root
code first verified that the failed update retained the old package and data
pair without a pending upgrade; the original workspaces were preserved.
A cloned workspace reproduced the timeout on the older API 4 ELF.

The storage engine verifies immutable extents in 2 KiB steps. The pinned WAD
requires 14,294 reader steps. The event loop inserted a 10 ms idle sleep
between steps, adding more than 140 seconds before the actual verification
work. Read-only GDB samples during the reproduced timeout repeatedly located
execution in `Ion::Timing::usleep`; private phase inspection was unavailable
without firmware debug types and is not claimed as evidence.

The [scheduling transformation](../scripts/prepare_prime_native_scheduling.py)
now checks whether platform storage has runnable work after normal input
scanning. It returns through the ordinary run loop without sleeping when a
step can advance. Input and elapsed-time UI timers still run; completed tokens
waiting for app acknowledgement and USB transfers waiting for the host do not
request this wake. Integrity checks, 2 KiB transfers, USB deadlines, signatures,
protocol IDs and physical timing registers are unchanged. The transformation
passes repeated-run and unexpected-context checks.

### Executed evidence

| Check | Result | Limit |
| --- | --- | --- |
| `make firmware-vm`, then `make firmware` | Both compile | Existing upstream warnings remain; no physical execution |
| `make test` | 580 passed, two private-fixture skips; 147.84 seconds | Host suite on macOS ARM64 |
| `vm/test-sdk-doom-gameplay.py --workspace scheduled --output build/sdk-doom/gameplay-scheduled` | Normal-key movement, turning/firing, menus, save, move away, restore, clean quit and cold restore/quit pass | GDB reads game state; debug pauses exclude performance qualification |
| `vm/test-sdk-scheduling.py --output build/sdk-doom/scheduling` | 32 yields in 60 modeled ms, max gap 39 ms; 14 UI timer ticks over 4,142 modeled ms; repeat, Home and relaunch pass | Model regression measurements, not physical latency |
| `vm/test-sdk-input-stream.py --output build/sdk-doom/input-stream` | Declared API 4 input and undeclared-capability cases pass | Normal KPP/Goodix model input |
| `vm/test-sdk-input.py` | Legacy key/text/modifier and two-contact input pass | Existing service-8 behavior |
| `vm/test-sdk-compatibility.py --corpus build/sdk-maturity-corpus` | Preserved Counter and Surface 3D ABI 1 packages pass unchanged | Corpus hashes verified before and after execution |
| `pytest tests/test_sdk_runtime.py -q` after the grant | Three pass, including actual ARM source roundtrip and runtime lock/content checks | No new libc function claims |

The 61,342-byte saved game has SHA-256
`063fad32c346033280621e8412126ab5e2f9d985ddd2ef3496d7e892686476e9`.
The cold VM restored the recorded position, angle and ammunition, and its
exported save remained byte-identical. GDB only read engine state; normal keys
drove every game action. World, fire, menu, saved and quit frames were inspected.
The immediate load captures show the engine's wipe transition, so they alone
are not proof of a completed load; the state comparison and subsequent quit
frame provide that evidence.

Observed newlib maximum sbrk extent is **6,643,712 bytes**. This is allocator
arena growth, not live-allocation or stack peak. Reserved app heap remains
8,380,416 bytes; static data 430,904 bytes; code 315,758 bytes; stack 65,536
bytes. Frame timing, peak stack/OS memory, all control bindings and Doom-specific
full-media/interrupted-save/configuration-error recovery remain open.

Candidate identities:

- VM ELF: `c35211650212ca9227b1b27c49bb20decd764efd3848669a1ae26fb17dd65110`.
- Physical BIN: `4796f63db57854945d1f3b0acd633a25e3cf3e4cf426d9893b3622072423d6d9`.
- Doom image: `aa3b6e7f976001189a482b96d43d47329049d19d8b455439a5f8ede5762e2405`.
- QEMU: `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.

The pre-grant evidence is sealed under `build/sdk-doom/evidence-gameplay-pregrant/`:
887 artifact/source entries, index SHA-256
`cd0d3f0f3c79066635d6fdf32b51d888653ee126e223aa5824c979b76adaa726`.
Earlier sealed evidence and failed workspaces remain separate.

### Approved app-side license grant

The copyright holder confirmed ownership and explicitly approved an additional
MIT alternative for the twelve original app-side runtime/interface/linker files
and startup-argument template. The [license review](NATIVE-APP-LINKED-LICENSE-REVIEW.md)
records the precise scope. Existing CC terms remain an alternative, and the
host generator remains GPL. Firmware and third-party code retain their terms.

A newly prepared Doom project includes the engine GPL text, MIT text, scope and
component notices. Rebuilding it produces the exact gameplay-tested image;
the debug ELF differs because source lines/notices changed. The final map
contains no allocated `lefony_math_*` symbol and records 35 discarded math
function sections. It pulls six GCC runtime, 103 libc and one libm archive
members before section collection. A final distribution still needs the full
corresponding-source/toolchain notice audit and qualified bundle identities.

The first source-export attempt rejected the preparation log's
`notices/port.json` path: source format 2 permits text/Markdown notices.
The recipe now emits the same JSON content as `notices/port.txt`; source-format
limits and website readers are unchanged. A fresh **200-file**, 1,892,685-byte
Doom source bundle extracts and rebuilds with a relocated **332-file** SDK kit,
using its bundled newlib. Every kit checksum verifies, including the complete
MIT grant/scope and exact newlib notice. The generated startup notice is present,
the host generator retains GPL-3.0-or-later, and the final ARM image matches the
gameplay candidate byte for byte.

- App source SHA-256: `c34fcde910da9c1662232a6ed6cd6275c11747145832331d269c470600cf1d64`.
- SDK archive SHA-256: `3f2be541b343810c2dfa785f0032e49dd0dcf01f3f4c6ea041c6c61839312189`.
- Report and exact artifacts: `build/sdk-doom/mit-bundle-check/`.

Final source-kit SHA-256:
`ef2bab2324403792bf2ca084b99129dc899833f8805e2124b8489115f90dcbb6`.
Two documentation links were changed to explicit maintainer-checkout paths,
and the preparation tool now explicitly records that embedded Doom adaptations
retain GPL-2.0-or-later while its host code remains GPL-3.0-or-later. Archive
comparison verifies that only those documentation/license notes and checksums
changed; all executable build inputs match the relocated-build-tested kit.
All 332 file hashes and 32 local links in the changed kit documents verify.
The repository check passes 816 public files; 163 local documentation targets
across eleven edited documents resolved before the final link-text cleanup,
and whitespace checks pass in both repositories.

The broader smoke suite's first attempt passed direct ELF boot but failed
`OK input did not open the Calculation app` after verified U-Boot loading.
An unchanged rerun passed direct ELF, U-Boot/input and protocol checks. Both
results remain at `build/prime-g2-native-suite-20260912-125953/` and
`build/prime-g2-native-suite-20260912-130342/`. This is an intermittent result,
not proof that its cause is known or that the first failure can be discarded.

The next acceptance work is complete libc/storage error and resource coverage,
live file controls and user data import/export, UI authoring, app connectivity,
the remaining proving apps, account/folder publishing and host/physical release
qualification. No R0–R6 milestone is complete. This batch performs no physical
write, release, deployment, commit or push.
