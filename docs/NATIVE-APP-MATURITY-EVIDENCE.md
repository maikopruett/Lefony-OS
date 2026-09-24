# SDK maturity candidate evidence — 2026-09-11

This is an **incomplete implementation of the maturity roadmap**, not SDK beta
or 1.0. It delivers developer-loop foundations, experimental UI/math/graphics
libraries, versioned package/source/USB contracts, app-local assets, and four
additional example apps.
The maintainer authorized an experimental SDK-download and website release
with native Windows and physical qualification pending. This exception permits
0.2.0-dev publication; it does not qualify the unfinished roadmap as beta/1.0. No calculator was flashed,
provisioned, erased or restored; firmware/app production identities are unchanged.

## Implemented candidate

- Reconciled supported docs with local publication and OS-owned storage.
  `doctor` reports actual tool availability and says device/host qualification
  is not checked. Historical validator instructions are explicitly archived.
- Pinned SDK lock, incremental translation-unit builds, debug/release profiles,
  compiler/source/image hashes, map files, memory accounting, editor compilation
  database and CMake integration through the same CLI.
- A real linker rejection for unsupported global constructors, including
  constructors that section garbage collection previously discarded silently.
- Public bounded JSON replays through normal KPP/Goodix dispatch, frame/color
  assertions, failure/skip reporting and exact package/SDK/firmware/QEMU hashes.
  Key tests synchronize on delivered guest events. Faults are not hidden by a
  subsequent exit/relaunch. Test controls are absent from physical builds.
- Persistent per-project synthetic NAND workspaces, normal signed modeled-USB
  installation/readback, normal installed loader, cold restart, clone/reset and
  integrity-checked export/restore to a new workspace. The deliberately public
  fixture is accepted only by emulator app verification, not physical firmware.
- Matching debug symbols, source mapping, private-session GDB socket, real
  source breakpoint/stack/register/step qualification and symbolized faults.
  Startup CFI terminates backtraces at the app entry. No user content is collected
  in fault reports; fault addresses and stack peaks remain unavailable.
- App-local arena, checked fixed-capacity vector, cooperative task helper and
  compiler memory routines. Experimental finite-sample statistics and bounded,
  cancellable bisection execute in app space.
- Bounded scalar expression contexts with isolated variables, checked handles,
  arithmetic, real powers, trig/log functions, local angle modes and per-node cancellation.
  Host known-answer/error cases and 10,000 arbitrary-text cases pass under
  sanitizers; real ARM evaluation/cancellation/domain cases pass.
- App-linked pinned OpenBSD/fdlibm sources retain original per-file notices and
  exact hashes. 760 high-precision reference cases and helper/domain cases pass
  on host/ARM. Bounded dense matrix solve/inverse/multiply/transpose pass 120
  constructed systems, invalid/overflow/singularity and cancellation cases.
- A test-only data-only transaction prototype on the real littlefs engine passed
  860 modeled interruption cases, retained package/data upgrade pairs and wrote
  zero package bytes for a small checkpoint. It is not enabled in firmware.
  See [architecture measurements and remaining decisions](NATIVE-APP-ARCHITECTURE.md).
- Optional size/version-tagged discovery and validated rectangle batches.
  Old ABI 1 firmware returns unsupported, and the sample uses the original
  drawing services as fallback. Schema-0 manifests retain optional-only use; the
  explicit schema-1 contract described below can require these features.
- Optional copied input snapshots include fuller Prime keys, modifiers, bounded
  UTF-8 and two stable touch IDs/coordinates. Optional bounded navigation lets
  apps consume Back within their own screen stack; Home/Apps/power remain OS-owned.
- App-side row/column layout, clipping, focus, capture cancellation, UTF-8
  selection/caret fields, buttons/toggles/progress, and expression key composition.
  [Forms and Tables](../sdk/examples/forms-tables/README.md) passes keypad/touch,
  nested dialog, focus restoration, row editing and staged-save scenarios.
- Clipped lines/circles/RGB565 images, coalesced screen batches and resumable
  adaptive curve sampling. [Graph Explorer](../sdk/examples/graph-explorer/README.md)
  passes sine/reciprocal/parametric-circle, key/touch pan/zoom, trace, hold/reset
  and multi-contact cancellation scenarios. Captured frames were inspected.
- [Pocket Lab](../sdk/examples/pocket-lab/src/main.cpp), a small public-API
  sample-entry/statistics app with graph bars, keypad/touch controls, cancellation,
  staged persistence and read-only handling of unsupported saved schemas.
- Standalone source-kit packaging includes the contracts, API/replay guides,
  templates, examples and explicitly public emulator fixtures. Generated locks,
  compile databases, workspaces, outputs and private signing material are excluded.

## Earlier UI/math candidate identities (before schema/resource work)

Base revision: `91701e213d74918226b3692f570079c2c13d9000` with the local source
changes in this worktree. The dirty base revision alone does not identify these
binaries; use the exact artifact hashes below. Pinned Upsilon revision remains
`f36520e0ed5faabbfea8a2b9f4e1309edc077927`.

| Artifact / target | SHA-256 |
| --- | --- |
| Physical `prime_g2` BIN | `1cc2620b7aeedd89ad2b2f2fe6d7ff1672a9b30d7278a0f2882ac127b2cb2fb4` |
| Emulator `prime_g2_vm` ELF | `f7af7483da34d178ed179ee7b109ad1265a7239799c51d84e6ef213bea94eb72` |
| Existing custom QEMU used for tests | `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0` |
| SDK build/runtime/test source identity | `9d716ba03a077540b2ca76c8c376b23f97208214364f12163c3f815dabd703c0` |
| Forms and Tables unsigned development package | `d86167d88eab2501bcb0f6cda10f973049902ec3ce843cd74b2b83e59b364a9c` |
| Graph Explorer unsigned development package | `90be5a4b998759ed332bae66497c4bc5d5fdc95a6db4cec3067a2a6bb2eb27c8` |

Forms/Tables uses 27460 code/constant bytes, 5956 static bytes and 5088 initialized
bytes. Graph Explorer uses 20952 code/constant bytes, 1104 static bytes and 928
initialized bytes. The existing 64 KiB stack reservation and
153600-byte OS composition surface are unchanged. These are measured build
sizes, not physical launch/input/frame-rate or stack-high-water measurements.

The earlier physical image was checked for absence of the emulator app-key identity
and test command strings. A host C++ test signs with the public fixture and
proves physical verifier rejection and emulator verifier acceptance.

## Earlier UI/math validation

Host: macOS 26.6.2 ARM64; Python 3.14.6; SDK compiler GCC 16.2.0; GDB 17.2.
No fresh-machine, Linux desktop or native Windows qualification is inferred.

| Check | Result |
| --- | --- |
| `make test` | 428 passed; two expected private DTB/DTS fixture skips |
| `make check-public` | Passed |
| Physical firmware build with existing public firmware/app keys | Passed; compilation only |
| VM firmware build with existing app roots plus guarded synthetic fixture | Passed |
| `vm/test-native-app-sdk.py` | 38 ARM cases passed: old isolation, discovery/bounds, batch atomicity/work limits, input/navigation wire validation, arena exhaustion, numeric/expression/memory behavior, stack overflow and syscall flooding |
| `vm/test-sdk-math.py` | Passed: 760 high-precision scalar cases, domain/helpers and 120 matrix systems with error/cancellation checks |
| `vm/test-sdk-graphics.py` | Passed: portable raster/sampler/gesture cases in ARM, coalesced drawing and 11 exact screen-color assertions |
| `vm/test-sdk-input.py` | Passed: normal KPP key/text/modifier composition and Goodix two-ID/reorder/change/cancel/release behavior |
| Forms and Tables public replay | Passed from a newly generated external project, using an installed synthetic workspace |
| Graph Explorer public replay | Passed: visible curve samples, key and touch pan/zoom, reset, trace, false-bridge rejection and button cancellation; frames inspected |
| `vm/test-sdk-compatibility.py --corpus build/sdk-maturity-corpus` | Both preserved pre-existing ABI 1 packages passed unchanged: Counter and Surface 3D |
| Pocket Lab public replay, including installed workspace | Passed; known sample graph colors, correct visible mean 55 for 12 and 99, multi-contact cancellation, clear and exit; frames inspected |
| `vm/test-sdk-developer-loop.py` | External project with spaces/Unicode, saved sample 123 across cold restart and export/restore, actual GDB breakpoint/step, exact source-line fault reporting, replay fails immediately on fault before a later relaunch |
| Standalone source archive | Passed: deterministic archive/checksums, extraction outside the checkout with spaces/Unicode, CLI/CMake Debug builds and installed Pocket Lab/Graph Explorer replays |
| `vm/test-sdk-fallback.py` with preserved older VM firmware | Passed: new Forms/Tables app handles unsupported input/navigation and works via base input plus software Back/Cancel |
| `vm/test-native-app-ui.py` | Passed: normal keypad/Goodix interaction and return to OS |
| `vm/test-native-app-storage.py --preprovisioned --many-apps` with public emulator fixture | Passed: signed install/readback, cancellation, icons, cold restart, removal and nine-app shared storage |
| `vm/test-prime-coordinate-touch.py --functions` with VM ELF | Passed after guest-timer synchronization; isolated recheck retained; original failure recorded in the work transcript |
| `vm/test-prime-coordinate-touch.py --calculation-history` with VM ELF | Passed on the earlier UI/math candidate with guest-timer synchronization |
| `DOCKER_CONTEXT=colima-lefony-sdk ./vm/test-native-comprehensive.sh smoke` | Passed on the earlier UI/math candidate: direct ELF, U-Boot/native smoke and protocol, with boot media rebuilt from the exact VM ELF |

Initial broad smoke attempts failed before guest execution because the default
Docker context was stopped, then because dependency construction exceeded its
ten-second boot wait. The running isolated context also did not expose host bind
mounts. The exact pinned/patched U-Boot and deterministic boot-media recipes were
run in temporary copied-source containers, then smoke passed with those cached
artifacts. No upstream pin, boot defaults or test acceptance assertions changed.
Existing firmware GNU-stack/RWX and U-Boot OF_EMBED warnings remain recorded in
build logs; successful compilation is not physical qualification.

The earlier smoke evidence is `build/prime-g2-native-suite-20260911-132657/`.
Its rebuilt synthetic boot media hash is
`c3866f791a70b401aaaf75f37dfaadbdb9566cf15e7075c3ca10a5783b0bf35a`.

The current coordinate-touch regression exposed a test timing issue: its fixed
host waits could expire before normal guest key handling. The captured frame was
still in the Axes menu when navigation panning was asserted. An isolated repeat
passed. The harness now waits for normal guest GPT time (with a bounded host
deadline), following the existing display-settings test's approach. It neither
advances time nor bypasses normal KPP/Goodix dispatch or acceptance assertions.

Ignored evidence is under `build/sdk-maturity-*`, `build/sdk-developer-loop/`,
`build/sdk-qualification/`, `build/sdk-compatibility/` and the app's `build/`.
Workspace archives include synthetic app data; they are not public artifacts.
The pre-existing app corpus hashes are checked in
[compatibility.json](../sdk/contracts/compatibility.json); the bytes stay in
ignored build storage. This does not yet establish a maintained released-binary
corpus or a public stable download identity.

## Package/source/resources follow-up candidate

This follow-up adds strict schema-1 manifest parsing shared by installation and
launch, read-only USB capability negotiation, source format 1, and app-local
resource conversion. The website repository now has compatible browser/Worker
readers and matching fixtures for the development rollout.

| Current artifact | SHA-256 |
| --- | --- |
| Physical BIN | `c26af5f8b7a709ef6bd0c2f90a6e0e4a83d83cbf6ce0886b49bb4412c0177a1b` |
| VM ELF | `b94460e09d9ac1170a5cd9f499c401ea1d7756c02d545a8ba059f55b3bb1d2c8` |
| SDK source identity | `ede3ee906cdb651e472d052f82c0628062f313e8b23f6b10ae15f33d8a45f335` |
| Reference Cards unsigned package | `0c89a221aaa285c06130396373f80ef0b9c66cb04f722184d17b679920b00e3f` |
| Shared 77-case manifest corpus | `256b1833647a14e5f0415151afa328fced70206636abd3c46fd5261c76f8fdb4` |

QEMU remains the same hash as above. Reference Cards uses 11925 code/constant
bytes (including 4913 resource bytes), 208 static bytes and 56 initialized bytes.
Its read-only bundle contains original PNG converted to RGB565 plus card text;
source-1 retains the PNG, text, converter settings, notices, replay and SDK lock.
The normal signed installed app passed key, pixel, Goodix touch, page wrap and
multi-contact cancellation assertions. Its captured 320×240 screen was inspected.

| Follow-up check | Result |
| --- | --- |
| `make test` | 547 passed, two expected private-reference skips |
| `make check-public`, `git diff --check` | Passed |
| Physical and VM builds | Passed with unchanged production trust identities |
| Physical/VM test-key and UART-command boundary | Passed; `build/sdk-contract-trust-boundary.json` |
| Host contract tests | 99 passed, including 77 shared cases and actual firmware parser under sanitizers |
| `vm/test-sdk-contracts.py --old-firmware …` | Passed: old reader rejection, current loader, negotiated signed install/readback, malformed manifests, unsupported required features/API, noncompliant host rejection and preserved app after cold boot |
| Resource host tests | 18 passed: exact RGB565, deterministic source roundtrip, invalid inputs, corruption, rehashed malformed tables, read-only placement and incremental rebuild |
| `vm/test-sdk-resources.py` | Passed: maximum 524288-byte bundle validation/lookup and cancellation in 10 modeled callback milliseconds; no physical timing claim |
| Reference Cards installed replay | Passed; captured frames inspected |
| Repacked source kit | Passed: reproducible archive, checksums, external CLI/CMake builds and installed Pocket Lab, Graph Explorer and Reference Cards replays |
| Website `npm ci`, build, lint, tests, Wrangler dry-run, companion unit tests | Passed: 352 tests plus one real-build test initially skipped, four companion tests |
| Real Reference Cards source-1 publication in Miniflare | Passed: all 22 store tests, including real local build signing/download byte verification |
| Website browser end-to-end tests | 55 passed; desktop/mobile developer screenshots inspected |

Earlier broad UI/math/storage checks above are baseline evidence, not a claim
that they ran on this follow-up hash. The follow-up hash has also passed the 38-case ARM isolation/service suite,
760 scalar/120 matrix tests, raster/plot/gesture and input suites, unchanged
Counter/Surface 3D compatibility, old-service fallback, GDB/developer loop and
native UI checks. Storage (nine installed apps), Functions and history coordinate-touch, and
broad direct/U-Boot smoke and protocol checks also passed on this hash.
The storage test retains two failed timing attempts: one captured before the
300 ms menu refresh, and one released Confirm before normal event delivery.
It now observes guest time for redraw and the native event counter for Confirm,
with bounded host deadlines and normal driver debounce. No acceptance assertion
or production redraw/input code was weakened.
Broad smoke evidence: `build/prime-g2-native-suite-20260911-143145/`. Ignored follow-up evidence is `build/sdk-contract-*`,
`build/sdk-contracts/`, `build/sdk-resource-*`, and website `.local/sdk-*`.
Release packaging records the exact downloadable identities separately. Full
remaining implementation, independent developers, host matrix and physical
qualification remain stable-release requirements.

## Roadmap status and stable-release requirements

| Milestone | Status / remaining work |
| --- | --- |
| M0 current contract | Docs, doctor, inventory and current limits implemented; release support remains provisional |
| M1 prototypes | Arena, batching, UI, scalar/matrix/graph libraries and data-only transaction experiment implemented; Escher comparison, shared Poincare prototype, production storage migration design and ratified physical budgets remain |
| M2 compatibility | Schema-1 manifest, source-1 and read-only USB negotiation locally tested across SDK/firmware/website; coordinated rollout and release matrix remain |
| M3 developer loop | Persistent workspaces, GDB, faults and input tests implemented; app logs, fuller crash/resource inspection, interruption/update replay and native Windows control remain |
| M4 full interaction | Tested layout/focus/navigation/text/gestures and Forms/Tables; generalized choices/sliders/lists/tables/scrolling, glyph/localization/font conversion, system queries and full Reference Browser remain; PNG/blob pipeline and Reference Cards implemented |
| M5 calculator capabilities | Scalar math/expressions, matrix operations, basic statistics/root and adaptive plotting with Graph Explorer; complex/units/scoped functions/symbolic methods, distributions/datasets, full plot/3D integration and remaining references are open |
| M6 durable documents | Existing ABI 1 staging preserved; data-only checkpoints, named documents, migration/rollback pairing and per-app host exchange remain |
| M7 distribution/publication | Source kit and packaging adaptations implemented; qualified binary host matrix/installers/version manager, CLI account flow and complete staging lifecycle remain; schema/source preflight and real-build local store signing/download tested |
| M8 public beta | Blocked by earlier open milestones and independent-developer acceptance |
| M9 SDK 1.0 | Blocked by earlier open milestones, signing/reproducibility/recovery drills and physical runtime/storage/input qualification |

No physical latency, 20 fps, flash-endurance, power-loss, migration/restore or
durability claim is made. Linux/macOS/Windows clean-host journeys, macOS
signing/notarization, two independent developers and the complete staging
publish/install/update/withdraw journey have not been performed. The development rollout includes the website contract readers and download
metadata. Public download hashes identify the exact released artifacts.

The next storage codec/old-reader tests are separate from the linked firmware:
`tests/test_sdk_document_root.py` passed both tests under sanitizers, including
the exact preserved FILE2 implementation refusing a synthetic future root with
no flash changes. The codec is not a production writer. See
[NATIVE-APP-DOCUMENT-TRANSACTIONS.md](NATIVE-APP-DOCUMENT-TRANSACTIONS.md).

The packaged desktop startup/workspace check found a QMP connection ownership
bug: screenshot capture retained the sole monitor connection before workspace
cleanup opened another. The SDK now closes capture’s connection first. This
host-only correction leaves the qualified firmware hashes unchanged and is
covered by `vm/test-sdk-desktop.py` after a workspace export/restore.

## Published development release

SDK **0.2.0-dev** and the compatible website were deployed to
[Developer downloads](https://lefony.com/#developers) on 2026-09-11.
Cloudflare Worker version: `842577ed-7b27-4a5a-a4a0-2c31035f1b2e`.
This publication record was added after creating the immutable archives.
The full maturity roadmap remains unfinished; this is the explicitly authorized
experimental release with Windows and physical qualification pending.

Final validation: 547 host tests passed (two private-reference skips), 354 website
tests passed including real Reference Cards source-1 publication, four companion
tests and 55 browser tests passed. Both firmware targets compiled. The current
VM passed the SDK, math, graphics, input, compatibility, debugger, storage,
coordinate-touch and broad smoke checks listed above.

The frozen macOS ARM64 bundle passed basic, Pocket Lab, Forms/Tables, Graph
Explorer and Reference Cards replays from a relocated path with spaces/Unicode,
with network, Homebrew and checkout access denied. Workspace clone/export/restore
and startup capture passed after the QMP fix. The source kit passed reproducible
packaging, checksums, external CLI/CMake builds and installed reference replays.

All five live archive downloads returned the exact expected bytes and SHA-256.
The published macOS installer downloaded the real public archive, verified it,
passed the starter replay, created its command link and passed repeat installation.
Live desktop/mobile pages were inspected and had no overflow or browser exceptions.
No calculator was written, and no Git commit or push was performed.

| Published archive | SHA-256 |
| --- | --- |
| `lefony-sdk-darwin-arm64.tar.gz` | `8011b30c262aea969b98ee807e5bbfb89e6a54fa59bb2e0e474c143779f0d1bf` |
| `lefony-sdk-source-toolchain.tar.gz` | `c0f9b938c6ca552dec5eb816acd26b46b0ac4e4c3375006e247105b9059578b8` |
| `lefony-sdk-source-runtime.tar.gz` | `627b68089ee79c77e62eb4d6db4032f8d5489fef797a374babece04a98019db3` |
| `lefony-sdk-source-lefony-qemu.tar.gz` | `0632769771b528bc93b8ed055f519c3676e6f7fe3b8ff1089d32b5d58a79fe84` |
| `lefony-native-sdk-source.tar.gz` | `cfa1454b43a8b88a6ca76d71e4c27fbf38747fb120d5fdfe61050bdf943da236` |

The packaged QEMU hash is `d90bdfbc4edfacd5f015932d6b387899e82384fdf9ae39fcc5f95c3851e53d14`; its neutral input build matches all patched QEMU source files. The complete local release record is `build/sdk-release-qualification.json`. Native Windows, clean-host Linux/WSL, notarization, physical acceptance and the unfinished milestones above remain open.
