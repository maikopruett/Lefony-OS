# SDK plans: implementation review and validation

Follow-on implementation has fixed the relaunch defect described below and
added main-entry debugging and a working ARM minigzip proof. See the
[implementation batch](NATIVE-APP-SDK-1.0-PROGRESS.md#conventional-main-developer-workflow-and-minigzip).
This review retains its original observations and failed reproduction.

Review date: 2026-09-12. Scope: read both plans, inspect the current SDK and
website candidates, consult upstream documentation, and validate representative
developer behavior. This review does not implement the roadmap or qualify a
release. The working tree is dirty on `codex/sdk-1.0`, based on
`91701e213d74918226b3692f570079c2c13d9000`; that commit alone does not identify
the tested source.

The [1.0 plan](NATIVE-APP-SDK-1.0-PLAN.md) is implementable as a staged program,
but **no R0–R6 milestone has met all its exit criteria**. Runtime and storage
have substantial working implementation. Complete developer journeys and
qualification lag behind the component proofs. The SDK remains `0.2.0-dev`.

The 1.0 plan supersedes the maturity roadmap's earlier exclusions and milestones.
It explicitly retains [maturity sections 11.3–11.5](NATIVE-APP-SDK-MATURITY-PLAN.md#113-github-sign-in-and-the-developers-app-library):
GitHub SDK sessions, all-owned-app listing, folder publication and updates,
recoverable uploads and website parity are required. The earlier broad math
inventory does not add release gates. Visual authoring and thin USB/HTTPS are
required despite the older roadmap's deferrals.

## Current implementation against acceptance

| Area | Verified source or retained evidence | Remaining acceptance |
| --- | --- | --- |
| Conventional C/C++ | Project schema 2 selects `foreground-newlib-1`; SDK startup calls main, handles initializers and exit; mixed C11/C++17 builds exist | Qualified function matrix, libc comparison, complete external-project/debug/bundle journey and workload budgets |
| Execution/memory/graphics | Public API 3 provides resumable foreground execution, guarded 8,380,416-byte heap, waits/exit and copied RGB565 pixels; legacy ABI 1 limits remain separate | Complete lifecycle/power and blocked-wait coverage, integrated memory peaks, frame pacing and physical timing |
| Files | Production FILE3/FILE4, owned asynchronous file sessions, snapshot readers, growing writes and real stdio; retained ARM cold-output oracle passes | Live durable sync/checkpoints, quotas/usage/enumeration, import/export, public migration/recovery, complete interruption matrix and physical durability |
| Input | Versioned key/text/two-contact snapshots and normal-input tests | Complete held/down/up key state and combinations for Doom; physical interaction qualification |
| UI/calculator services | Manual app-side controls, math/plot helpers, replay and debugger baseline | Selected visual editor/backend, deterministic generation, preserved handlers, actual ARM save-to-preview/layout inspection and a polished document app |
| Accounts/publication | Website has GitHub identity, an owned-app pagination route, submissions/signing and withdrawal; candidate source readers accept configured C projects | CLI login/logout, secure SDK sessions, local project links, folder metadata/media, idempotent/resumable updates and stale-edit handling across SDK/website |
| Connected apps | Installer/management USB and host infrastructure exist | App-scoped USB transport and HTTPS companion with streaming, cancellation, credential separation and disconnect behavior |
| Four proving apps | Doom engine/assets pinned; all 80 selected engine units compile; component/reference fixtures exist | Playable/saveable Doom, document/calculator app, existing non-game C program and connected app completing their plan scenarios |
| Distribution | Source/desktop packagers and optional bundled newlib support exist | Qualified complete bundles, native Windows/macOS/Linux journeys, physical measurements, independent developers, license paths and exact released/downloaded artifacts |

Sources: [runtime profile](../sdk/C-RUNTIME.md),
[startup](../sdk/lib/newlib/start.c), [builder](../sdk/tools/build.py),
[file contract](../sdk/FILES.md), [input wire](../sdk/include/lefony/input_wire.h),
[CLI](../sdk/tools/cli.py), [runner](../sdk/tools/runner.py), and
[Doom inputs](../sdk/ports/doom/README.md). Website observations refer to the
local sibling candidate's `worker/store.ts`, `worker/store-publication.ts`,
`worker/store-source.ts` and `src/source-contract.ts`, not deployed behavior.

The existing research and progress documents still describe reusable main
startup as missing in their opening summaries. Source and `sdk/C-RUNTIME.md`
show that this integration now exists as an explicit candidate. Reconcile those
summaries during implementation; do not infer either absence or qualification
from an older status paragraph. C++ language support also does not imply a
complete C++ library: this profile has no libstdc++ headers/library, general
new/delete, standard containers, exceptions or RTTI.

## Reproduced developer-journey defect

A freshly generated `c-main` project builds and exits with status zero, but its
default saved-visits replay fails at the first `relaunch` action with
`app relaunch failed`. Both preceding assertions pass. Reproduction:

```sh
.venv/bin/python sdk/tools/cli.py new build/sdk-plan-review/review-c-main --template c-main
.venv/bin/python sdk/tools/cli.py --project build/sdk-plan-review/review-c-main test
```

These commands use a new folder and synthetic emulator storage. The second
command returned 1. The original report is retained at
`build/sdk-plan-review/original-run.json`; original frames/step evidence are in
`build/sdk-plan-review/original-replay-evidence/`.

A controlled experiment changed only the generated project's replay: inserting
`{"key":"home"}` before relaunch made both exits and the changed saved-visit
frame assertion pass. The SDK implementation and template were not changed.
The passing experiment report is in the generated project's `build/run.json`;
its log is `build/sdk-plan-review/c-main-home-experiment.log`.

The evidence points to a missing leave/re-entry transition in the replay
lifecycle. [Controls.run](../sdk/tools/replay.py) issues `APP OPEN` directly;
[launchInstalled](../ports/lefony-prime-g2/apps/native_apps/app.cpp) must open
the installed app and switch the container. The lower-level main proof already
sends Home after checking exit. Fix and test the public relaunch behavior for
both callback and foreground apps, including failed exit and active-app cases,
then run the relocated kit workflow. The passing Home experiment is diagnostic
evidence, not a qualified fix or a reason to remove the default test.

## Validation performed for this review

| Check | Result | Limit |
| --- | --- | --- |
| `.venv/bin/python -m pytest tests -q` | **573 passed, 2 skipped, 280 subtests passed**, 187.95 s | The two skips require private DTB/DTS inputs |
| Fresh `c-main` default test | **Failed**, exit 1 at relaunch | Main exit and first frame assertions passed; repeated-launch acceptance failed |
| Copied replay with normal Home before relaunch | **Passed**, both exit-status checks and changed visit frame | Diagnostic change only in ignored generated project |
| Website `npm run build` and `npm run lint` | **Passed** | Local candidate only |
| Website `npm test -- --maxWorkers=1` | **418 passed, 1 skipped**, 49.64 s | One-worker result; historical default-parallel timeouts were not reassessed |
| Optional real-SDK store fixture supplied separately | **1 passed**, 22 unrelated tests filtered out | Mocked service, synthetic signing key; validates exact ARM payload through ingestion/signing/download, not live authentication/publication |
| Prior foreground evidence integrity | **245 retained files and 102 source snapshots match** their recorded hashes | Historical candidate, not automatically transferable to current binaries |
| Retained current main/stdio reports | **4 main and 2 stdio cases passed**; all 15 recorded source-hash entries match current files and both reports match current VM ELF | Reports inspected and hashes rechecked; those six cases were not rerun in this review |

The real-package store test used the fresh project's source-format-2 bundle and
ARM package with `LEFONY_SDK_TEST_PROJECT`, then ran:

```sh
npm test -- --maxWorkers=1 tests/app-store.test.ts -t 'accepts a real SDK build'
```

It verifies payload preservation and signing. Its implementation submits a
developer-local testing declaration; it does not independently validate the
developer's report or prove source/binary equivalence.

Current VM ELF SHA-256:
`95b7bcdcdb2c8b61d5dfe4106ca28af3a9552797addb079a45376dd7bbaf9d84`.
Developer QEMU SHA-256:
`2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
Retained current stdio output is 261,932 bytes, SHA-256
`dc8b637fd01afaf5634fd712b511d88bdd6b651e59b5edf6478e2b02994dd2c0`.

New logs are under `build/sdk-plan-review*` and the website's
`.local/sdk-plan-review-*.log`. Hash verification is recorded in
`build/sdk-plan-review/evidence-verification.json`. No firmware rebuild, physical
device operation, deployment, commit or push was performed for this review.
The relocated main-profile kit test and physical/native-host journeys remain
unqualified by this work.

## Research-backed implementation sequence

1. **Finish the ordinary C developer journey and settle R0 choices.** Fix
   relaunch, qualify the relocated bundle and source/debug workflow, then compare
   the pinned newlib profile with Picolibc using identical ARM allocation,
   formatting, error, startup and file workloads. Both libraries require actual
   OS integration; successful linking cannot establish those semantics.
   Document the selected function matrix and full-reentrancy configuration,
   footprint, maintenance owner and distribution inputs.
   [Newlib OS hooks](https://sourceware.org/newlib/libc.html#Syscalls),
   [Picolibc OS integration](https://github.com/picolibc/picolibc/blob/main/doc/os.md).

2. **Use real C programs to close runtime/storage/input gaps.** A pinned
   upstream minigzip is a suitable non-game proof: stream input larger than
   64 KiB, independently decompress/hash output, and test truncated input,
   allocation/full-media failures and checked close. Complete public key
   transitions and connect Doomgeneric's display/timer/input hooks to the
   shared SDK. Measure total memory beyond Doom's zone allocation, stream the
   pinned 28.8 MB WAD, and qualify gameplay, Home, save/load and cold reopen.
   Preserve a save until its replacement commits; inspect upstream close and
   rename error handling. Littlefs supplies useful commit/rename primitives,
   while Lefony must define application durability and NAND synchronization.
   Resolve the actual Doom/app-linked license path before distributing a port.
   [Pinned minigzip source](https://github.com/madler/zlib/blob/v1.3.1/test/minigzip.c),
   [Doomgeneric hooks](https://github.com/ozkl/doomgeneric/blob/dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284/README.md),
   [Littlefs synchronization](https://github.com/littlefs-project/littlefs#usage).

3. **Validate UI authoring with the plan's two-screen proof.** Reuse the
   existing Lefony/Escher components and SDK source tooling. Require custom
   drawing, preserved developer handlers, normal Prime input and actual ARM
   preview with a debugged layout defect. Measure the source-edit, build and
   preview workflow before setting latency targets.

4. **Implement connectivity and SDK publishing as separate contracts.** Give
   app messages no installer authority; test HTTPS streaming, limits, TLS,
   disconnect/cancel and ambiguous mutations using a controlled service.
   For SDK login, GitHub documents a CLI device flow without a distributed
   client secret, with explicit polling and expiration behavior. It still needs
   integration with revocable store sessions and the website's stable account
   identity. Reuse existing owned-app routes, then implement the folder snapshot,
   immutable versions, upload recovery and metadata-conflict contract. Validate
   with two accounts, two releases and alternating website/SDK edits.
   [GitHub authorization flows](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps#device-flow).

5. **Qualify the integrated release.** Bind all acceptance to exact SDK,
   firmware, companion and website candidates. Require all four app journeys,
   legacy compatibility, malformed-input/resource/lifecycle coverage, physical
   input/frame/save/power measurements, native Windows/macOS/Linux hosts and
   unfamiliar-developer trials. Test downloaded artifacts after coordinated
   release. No defensible completion date follows from component test counts;
   estimate after the remaining R0 comparisons, owners and physical/host access
   are resolved.

UI and connectivity proofs can proceed once their minimum public foundations
work. Final acceptance converges on durable files and the four real apps; it
does not require implementing every optional library or deferred CAS feature.
