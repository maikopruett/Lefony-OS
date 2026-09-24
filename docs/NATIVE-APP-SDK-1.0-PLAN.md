# Lefony OS SDK 1.0: a general application platform

Status: **revised development plan, 2026-09-12**. This document defines the
intended 1.0 scope and acceptance criteria. The released SDK remains
`0.2.0-dev`; planned capabilities below are not claims about that release.
SDK product versions and runtime ABI versions are separate contracts.

Read [scope](#2-required-scope-and-deliberate-deferrals),
[the C runtime](#4-c-and-c-portability-and-execution),
[UI authoring and preview](#6-ui-authoring-graphics-and-emulator-preview),
[the four proving apps](#9-four-proving-applications), and
[milestones](#10-milestones-and-dependencies) for the main decisions.

## 1. Product goal and planning authority

SDK 1.0 should let developers port suitable existing C programs and build
polished games, tools, document applications and connected clients using public
APIs, without modifying Lefony firmware for each app. Developer freedom comes
from dependable computation, graphics, input, storage and communication, with
convenient UI tools layered on top.

A developer must be able to install the SDK, create an external C/C++ project,
preview its real UI in the ARM emulator, debug and test it, install privately,
and publish a reproducible package. Custom rendering and custom data formats
are first-class choices. Using the supplied widgets is optional.

"Complete" means this supported platform works coherently, with explicit limits
and a path for extensions. It does not promise desktop OS compatibility or that
any conceivable app fits the calculator. An Instagram-like client also needs a
reachable service and an appropriate external API; an SDK cannot supply missing
hardware or access that a service does not offer.

This plan governs SDK 1.0 scope and release acceptance. The earlier
[maturity roadmap](NATIVE-APP-SDK-MATURITY-PLAN.md) remains a detailed backlog and
record of prior proposals. Only requirements retained here are 1.0 gates; its
broader math inventory and earlier milestone list do not add hidden gates.
Current implementation and evidence remain in the
[capability inventory](NATIVE-APP-CAPABILITIES.md) and
[evidence ledger](NATIVE-APP-MATURITY-EVIDENCE.md).

Maintainer scope update, 2026-09-12: the external visual-editor integration and
its generated-screen development have been removed. UI work now centers on
C/C++ components, source editing and actual ARM preview. Adding an authoring
application requires a separate product decision; it is not a 1.0 dependency.

## 2. Required scope and deliberate deferrals

| Area | Required for 1.0 | Deferred or conditional, with reason |
| --- | --- | --- |
| C/C++ development | Conventional C execution, qualified library profile, allocation, files, timing, reusable build/platform adapters | Full POSIX, processes, general threading and dynamic linking expand the OS architecture beyond the proving apps |
| Execution | One foreground app with resumable execution, OS interruption, cancellation and resource recovery | Cross-app background jobs, daemons and powered-off wakeups add scheduling and power contracts without proving basic portability |
| Graphics/input | Efficient app-owned pixels, images, fonts, complete app-visible keys/touch and frame timing | A custom 3D engine is an optional library/sample; ordinary software rendering must already be possible |
| Storage | Large named files, streaming, random access, durable saves, quotas, safe package/data upgrades | Repartitioning and a universal shared-document/sync framework are separate projects |
| UI development | Cohesive C/C++ components, layout and actual ARM emulator preview/inspection | An external visual editor, code-generation pipeline, bespoke designer, IDE and arbitrary live C patching are outside the current SDK scope |
| Existing calculator services | A documented useful subset of existing math, expression editing, plotting and system services | New CAS capabilities or parity with every internal calculator feature must justify their own scope |
| Connectivity | App-scoped USB messaging and a small companion HTTPS bridge, including bounded streaming and disconnect handling | Universal OAuth/account vault, synchronization/conflict engine, persistent sockets and direct wireless support are not core release gates |
| Ecosystem libraries | Small, varied conformance cases and the four real proving apps | SQLite, Lua, SDL and zlib integrations are optional maintained recipes; no requirement to adopt all of them |
| Hosts/distribution | Qualified Windows x86-64, macOS ARM64 and Linux x86-64 developer journeys; private install and public distribution | Additional architectures follow demonstrated demand and available qualification capacity |
| Stability | Legacy compatibility, reproducible bundles, independent developer trials and physical qualification | A larger feature count cannot substitute for a dependable supported surface |

Deferral applies to first-party implementation and support commitments. Developers
may build their own libraries or services on the public primitives. Optional
packages have separate versions, declared dependencies and honest support status;
experimental declarations do not count as stable capabilities.

## 3. Baseline and early architecture decisions

Reuse the signed package system, protected ARM runtime, compiler tooling,
workspaces, resource conversion, UI/math helpers, debugger, normal-input replay
and publication workflow where they meet the new contracts.

The starting [ABI 1 contract](../sdk/contract.json) has a 1 MiB code region,
roughly 952 KiB of data space, a 64 KiB stack and a 64 KiB private byte store.
At the start of this plan, user projects targeted C++ sources and bounded
callbacks; conventional `main`, allocation/stdio, durable named files and app
networking were missing. These now have local implementations through negotiated
extensions, alongside the original ABI 1 contract. The
[capability inventory](NATIVE-APP-CAPABILITIES.md) and
[implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md) describe their current
evidence and remaining work. This starting baseline is not a list of today's
missing features. Native Windows and physical SDK/storage qualification remain
incomplete.

R0 must resolve these choices before dependent contracts freeze:

- **Runtime and memory:** demonstrate a resumable foreground C program, a
  practical larger app allocation and OS responsiveness. Measure code, heap,
  stack, graphics buffers and OS reserves together. Select a supported profile
  from actual workloads rather than promising several arbitrary memory sizes.
- **C library:** compare reuse of a maintained embedded library with extending
  the current subset; select by correctness, footprint, integration and terms.
  Linking a library with syscall stubs is insufficient. For example,
  [newlib documents OS integration hooks](https://sourceware.org/newlib/libc.html#Syscalls)
  that need real implementations for the claimed behavior.
- **UI authoring:** reuse the existing Lefony/Escher components and SDK source
  tooling; validate the two-screen ARM proof in section 6.
- **Storage:** prove data-only commits and streamed files within the current
  reserved region, with a versioned migration and recovery design.
- **Math boundary:** test ownership, cancellation and resource limits around
  the existing engine; decide which services can be safely shared or app-linked.
- **Licensing:** inventory the exact headers, inline code, startup objects,
  libraries, generators, outputs, example sources and assets delivered to apps.
  Existing [licenses](../LICENSE.md) and [notices](../THIRD_PARTY_NOTICES.md)
  constrain these decisions; some app-linked material is CC-BY-NC-SA. Resolve
  distribution of the selected GPL and other reference programs at the actual
  linking boundary, including any required grants or independently implemented
  interfaces. Do not infer an app's terms solely from the firmware's license,
  promise unrestricted commercial distribution, or silently relicense upstream
  code. An unresolved distribution path blocks release of the affected artifact.
- **Qualification:** assign owners, identify physical calculators and native
  test hosts, choose exact supported OS versions, and pin the four reference
  apps and their permitted data/assets. Record workload baselines early.

Decisions include alternatives considered, measurements, maintenance ownership
and the acceptance test. A prototype may reject an approach without committing
the SDK to supporting it permanently.

## 4. C and C++ portability and execution

### Runtime and standard library

Support `.c`, `.cpp` and mixed projects, separate compile/link flags, conventional
source trees and reusable Make/CMake integration. Keep C++17 as the initial
language baseline; document supported C99/C11 language features separately from
library coverage. Do not promise a complete hosted C/C++ environment by name.

Publish a function and behavior matrix covering the chosen profile: startup and
static initialization, `main` arguments, exit/cleanup, `malloc`/`calloc`/`realloc`/
`free`, string/memory functions, required formatting/parsing and math, file I/O,
errors and time. Specify alignment, exhaustion, integer overflow, locale and
encoding behavior. State any limits on C++ exceptions, RTTI, standard containers
and other library facilities; test every advertised facility on ARM.

Provide normal `fopen`/`fclose`, read/write, seek/tell, EOF/error and descriptor
semantics needed by the selected programs. Cover short transfers, invalid
handles, failed allocation and error propagation. Distinguish buffered `fflush`
from a durable filesystem sync. File waits and timers need real OS integration;
returning a successful stub is not compatibility.

Run conventional `main` once per launch on an app stack that survives waits.
An app may use its own loop and call sleep, input or file adapters without
rewriting every library into callbacks. The OS must regain control independently
of app cooperation, preserve execution state and reclaim resources on exit,
fault or termination. Specify deadlines, Home/power behavior and foreground
suspend/resume. This is one foreground resumable task, not a background service
framework. CPU-bound and blocked programs must not trap the user inside an app.

### Compatibility and resource control

Keep ABI 1 layouts, limits and meanings unchanged for old apps. Introduce a new
ABI or explicitly negotiated extension if execution/memory changes require it;
SDK 1.0 must not silently reinterpret old packages. Preserve legacy fixtures and
publish supported OS/ABI/package/SDK combinations, rejection behavior and the
policy for future incompatible changes before freezing 1.0.

Expose app memory usage, allocation limits and predictable exhaustion. Maintain
isolation, floating-point state, handle ownership and cleanup. App pixel buffers
are ordinary writable memory; the OS retains LCD/DMA, flash, clock and peripheral
ownership. Complete application control does not require raw MMIO or raw NAND.
Driver development remains a documented firmware-source workflow.

Update compiler, linker, loader, manifest, source archive, package resource and
website limits together. Real ports need more than one flat source directory and
small embedded asset arrays. Builds must work outside the OS checkout and record
tool versions, dependency pins, license notices and reproducible source inputs.

### Portability evidence

Use a small set of allocation, stdio, math, timing and error conformance cases,
then the real Doom and non-game C workloads in section 9. Record upstream source
pins, platform adapter size, changes to the portable core, build steps and all
workarounds. Shared gaps are fixed in the SDK or a reusable adapter, not copied
into each example. A program linking successfully or showing its first frame is
insufficient.

Optional library ports can expose specific gaps. SQLite requires a real
[VFS contract](https://www.sqlite.org/vfs.html), including the selected locking
and durability behavior; it must not be declared supported from a compile test.
Lua, SDL, zlib and other libraries likewise get explicit profiles and evidence
if shipped, but they do not block the C foundation or UI milestones.

## 5. Storage and assets

Provide app-private named files/directories, arbitrary byte formats, streaming
and random access, metadata and space queries, quotas, import/export, deletion
and explicit durable commits. Support files larger than the legacy 64 KiB byte
store without loading them whole. Games need streamed assets and save files;
a document app needs reliable edits and schema upgrades.

Keep the existing 64 MiB reserved app region and legacy data contract. Larger
storage capacity is a separate migration project. New file objects must use an
appropriate versioned representation rather than stuffing document contents
into the legacy byte store or an oversized metadata record.

Complete the production integration described in
[document transactions](NATIVE-APP-DOCUMENT-TRANSACTIONS.md): data-only saves must
not rewrite unchanged app packages. Bound metadata and write amplification;
reserve real headroom for durable replacement and recovery. Define atomic
commit points, reader snapshots, interrupted writes, cancellation and recovery
on full or damaged media. Unknown formats must not be silently reformatted.

Package updates and data migrations must preserve a recoverable, compatible
package/data pair and existing anti-downgrade policy. Test failures before,
during and after a migration commit; an app upgrade must not orphan the last
readable user data. Define export/restore and uninstall data behavior clearly.
Cross-app document providers and generic synchronization can follow later.

Asset tools must produce the exact fonts/images used by the runtime, support
streamed assets, validate dimensions/sizes and report memory cost. Package
resources remain separate from mutable app data. Decoders and import paths need
malformed-input and exhaustion tests, not only successful sample conversion.

## 6. UI authoring, graphics and emulator preview

### Graphics and components

Provide efficient pixel presentation, clipping, image blits, text/fonts,
transparency where supported, reusable drawing buffers and frame/timer queries.
Define buffer ownership, pixel formats, completion and tearing behavior. Measure
full-screen updates on hardware. Software-rendered games should use these public
primitives without a special firmware path for a particular game.

Expose key down/up, held state, combinations, modifiers and repeat rules, plus
supported touch contacts and cancellation. Document system-reserved keys and
focus transitions. Support math/text entry without forcing all applications
into a calculator screen. Preserve driver debouncing and normal event dispatch.

Deliver one coherent widget/layout system: buttons, labels, menus, dialogs,
scrolling lists, text/expression fields, focus navigation and reusable screen
patterns. Include typography, spacing, pressed/disabled/focused states, theme
customization and a defined glyph/encoding policy. Review touch and keypad
usability, long labels, empty/loading/error states and constrained layouts.
Custom canvas code must coexist with widgets and developer-owned screens.

### C/C++ UI authoring

Build on the existing Lefony/Escher work and public SDK components. Keep screen
layout, real data/actions, reusable components and custom drawing in inspectable
C/C++ project sources. Measure footprint, rendering/input integration, math
entry, native appearance and maintenance as the document app develops.

Prove a two-screen application with navigation, a list, editing, validation and
custom drawing. Edit its source, incrementally rebuild the ARM package and
inspect a layout defect. Preserve developer-owned handlers and keep the workflow
usable offline after dependency setup. A separate visual-editor application and
its generator are not required for this proof.

### Actual emulator preview and inspection

Provide a save-to-preview loop: validate source, incrementally build the ARM
app, install into a synthetic workspace and relaunch a selected scenario. Retain
or reset fixture data explicitly. A failed build leaves a visibly stale preview
with actionable diagnostics. Automatic preview operates on synthetic emulator
storage, never a connected calculator.

The acceptance preview runs the real ARM package with the actual fonts, assets
and rendering/input backend. Reloading at a defined scenario is sufficient; arbitrary
live replacement of running C code is outside scope.

Expose useful bounds, clipping, focus/state and source location information.
Connect layout inspection, source-level debugging, symbolized faults and memory/
frame diagnostics to the same external project. Strip instrumentation for a
release build and confirm that its behavior matches the previewed application.

Provide normal-input replay scenarios, screenshots and reviewed visual baselines
for the component gallery and document app. Emulator touch tests must traverse
Goodix and normal dispatch. Include loading, empty, error, keyboard, long-text and
custom-theme states; visual review is required alongside interaction assertions.
Measure build/install/relaunch latency on the supported hosts before setting a
numeric preview target. Do not equate a host mockup with working ARM UI tools.

## 7. Existing calculator and system services

Inventory useful functionality the current hardware and OS actually provide.
For 1.0 expose a qualified subset covering expression input, evaluation and
formatting, supported numeric/matrix operations and plotting helpers, plus
version/capability queries, clocks with validity, battery state, theme, basic
clipboard/user-initiated exchange and supported settings requests such as
brightness. Define units, ownership, errors and lifecycle behavior consistently.

Choose the exact existing math operations during R0 using the document app and
current SDK helpers as acceptance cases. Address the shared Poincare allocation
pool and cancellation/ownership before exposing broader engine operations.
App-linked helpers or bounded service calls are possible implementations; an
uninterruptible privileged computation is not acceptable. Validate results
against independent cases and report unsupported operations clearly.

A comprehensive new CAS, every internal dataset/statistics feature and a custom
3D API are not prerequisites. The inventory must make omissions visible and
prioritize important existing gaps. Apps can supply their own algorithms.
Do not advertise unavailable audio, camera, GPU or wireless facilities through
successful stubs. Peripheral extensions require their own implementation and
hardware qualification. Restore temporary app settings when their contract
requires it, including after faults and forced exit.

## 8. Thin USB and HTTPS connectivity

Provide one app-scoped bidirectional USB channel and a small desktop companion
that forwards HTTPS requests. Support bounded messages and streaming uploads/
responses, timeouts, progress, cancellation, backpressure and disconnect errors.
The calculator can remain useful offline; the bridge is available only with a
connected, running companion and suitable host networking.

Retain identity/session isolation, pairing and explicit host access controls.
App channels cannot acquire installer, diagnostics or firmware-update authority;
firmware operations take exclusive ownership through their existing safeguards.
Handle malformed frames and host/device disconnects without wedging USB or the
foreground app. Keep debug-only controls out of physical builds.

The companion validates HTTPS certificates and supports the basic request/
response behavior needed by the connected reference app. Specify redirects,
response limits and how cancellation or disconnect can leave a mutation's
outcome unknown. Do not silently retry non-idempotent operations. Use a controlled
test service plus deterministic fixtures to test these cases.

Applications choose their own backend, payloads and authentication. If an example
needs credentials, use an appropriate host secret store and app-scoped access;
credential separation and TLS correctness are required. A universal account
vault, OAuth SDK, durable sync queue or conflict-resolution framework is not.
The sample demonstrates a simple local cache and reconnect policy at app level.
No hosted Lefony backend or third-party social API is a prerequisite for 1.0.

## 9. Four proving applications

The SDK account and publishing requirements below are also required 1.0 scope;
they apply to these apps and to ordinary community projects.

### GitHub accounts and publishing from a project folder

Developers must be able to sign into their GitHub account in the SDK, list all
owned apps (including drafts and withdrawn listings), create local projects and
new store apps, link existing projects, and publish updates without filling out
the website form. Website submission remains supported against the same app
identities, ownership, media rules and release history.

Use the detailed [account, folder and update contract](NATIVE-APP-SDK-MATURITY-PLAN.md#113-github-sign-in-and-the-developers-app-library)
as the required specification for this workflow. It includes proposed CLI
commands, secure revocable sessions, `store/` metadata/icon/screenshots,
allowlisted folder uploads, locally tested exact-byte submissions, immutable
versions, resumable/idempotent publication and conflicts with website edits.
This specifically retains those publication requirements from the maturity
roadmap; it does not reinstate that document's other superseded scope choices.

Listing source comes from project files: identity/name/version in `app.json`,
description and release notes under `store/`, required `store/icon.png`, and at
least one image under `store/screenshots/`. One explicit SDK publish operation
prepares and uploads the submission, creating the listing or a new version of
the existing app. Developers need not select each file manually in the browser.
Local-only testing, automatic publication and server integrity/ownership checks
remain unchanged. Store publication does not silently install device updates.

### Proving app requirements

These are integrated release evidence, not four new product businesses. Pin
sources, permitted assets/data, workloads and expected behavior in R0. Each must
build from a documented external project using public interfaces, exercise real
errors and run on qualified hardware as well as the emulator.

| Application | What it must prove | Required evidence |
| --- | --- | --- |
| Classic Doom port | Existing C code, useful memory, public graphics/input/timers, streamed WAD assets and reliable saves | Playable fixed workload, loading/saving, held keys and combinations, Home/exit responsiveness, measured frame/memory behavior, reusable adapters and explained upstream patches |
| Polished document/calculator app | Good UI authoring and actual preview, useful existing math, custom appearance, durable user data | Multi-screen editing/navigation, expression or plot workflow, visual/state review, debugged layout issue, save/reopen/export and compatible data upgrade |
| Existing non-game C tool | Generality beyond a game-specific adapter | Pin a real text/data/archive-processing program; process streamed files larger than 64 KiB, verify useful output, exercise errors and conventional startup/I/O with limited explained platform changes |
| Small connected app | App USB/HTTPS, streaming images/data, local cache and reconnect | Controlled service and offline fixtures, loading/error/cancel states, disconnect/reconnect, cache reopen, bounded memory and correct credential/session separation |

For Doom, a maintained platform-hook approach such as
[doomgeneric](https://github.com/ozkl/doomgeneric) is a candidate. Its source,
SDK-linked components and chosen game data need a distributable combination.
Graphics/input/storage/timing are the benchmark; unavailable sound hardware and
multiplayer are not release requirements. Record any omitted features honestly.

A full Instagram clone, social backend, browser, or whole desktop environment is
not needed to prove the connected primitives. Likewise, a bespoke toy replacing
an existing C tool would not prove general program portability. Add other ports
when they expose a specific gap; do not grow an unbounded mandatory corpus.

## 10. Milestones and dependencies

These milestones replace the earlier V1 milestone draft. Dependencies describe
what must be complete for acceptance; independent prototypes can overlap. Assign
actual owners before implementation rather than assuming a particular team size.

| ID | Deliverable | Completion dependencies | Responsibility | Exit evidence |
| --- | --- | --- | --- | --- |
| R0 | Scope, licensing, host/hardware baselines and architecture proofs | None | Platform, release and component owners | Recorded runtime/library/UI/storage/math decisions, four pinned apps, license paths, host matrix, measured budgets and assigned qualification access |
| R1 | Foreground C/C++ foundation, larger memory contract, graphics/input/timing and existing system/math adapters | R0 | Runtime and SDK | Conventional main/waits, allocation and non-file C profile tests, basic resource reads, legacy binaries, responsive OS and useful public service examples on ARM |
| R2 | Production durable files, assets and C file adapters | R1 | Storage and SDK | Large streaming files, data-only commits, qualified stdio profile, quotas, interrupted saves/migrations and package/data compatibility |
| R3 | C/C++ UI components and actual emulator preview/debug | R1 | UI and developer tools | Two-screen source workflow, preserved handlers, visual/input cases, source inspection and measured preview loop; persistent document acceptance additionally uses R2 |
| R4 | App USB channel and small HTTPS companion | R1 | USB and host tools | Scoped messages, request streaming, cancellation, isolation and deterministic failures; integrated caching/UI acceptance additionally uses R2 and R3 |
| R5 | Four integrated applications, complete developer bundles, GitHub SDK accounts/folder publishing and beta trials | R2, R3, R4 | SDK, application and release owners | Four public-API journeys, clean-host tools/private install, SDK first publication/update and website parity, measured independent feedback and resolved shared SDK gaps |
| R6 | Stable contracts, hardware/host qualification and coordinated 1.0 release | R5 | Platform and release | All section 11 gates, compatibility corpus, exact downloadable artifacts and website verification |

UI work depends on the minimum working runtime, graphics and input foundation;
it does not wait for SQLite, Lua, SDL or the complete optional library ecosystem.
Its durable document scenario converges with storage later. Connectivity can
likewise be prototyped before the connected application's cache and UI are ready.
Basic developer tooling, compatibility and physical measurements begin in R0/R1
and continue throughout; R5/R6 are integration gates, not their starting dates.

Implementation belongs in `sdk/`, the native adapters under
`ports/lefony-prime-g2/ion/src/prime_g2/`, app integration under
`ports/lefony-prime-g2/apps/`, and tests under `tests/` and `vm/`. Keep durable
upstream changes in checked preparation scripts or versioned patches. Give companion
sources a dedicated module and coordinate website schemas in its repository.
Shared public contracts need one assigned owner. Firmware and VM builds share
a generated checkout and must run sequentially.

## 11. Acceptance, qualification and release

Every advertised stable capability needs documentation, limits, errors, examples,
compatibility fixtures and tests that exercise behavior beyond startup.

1. **Usable platform:** all four proving applications and the supported C/C++
   function matrix pass on the real ARM guest and qualified hardware. Resolve
   shared SDK gaps rather than retaining private firmware shortcuts in examples.
2. **Independent developers:** have developers unfamiliar with the internals
   complete a new C-port task, a custom UI workflow and a bug reproduction using
   release bundles. Rebuilding our examples alone is insufficient. Record elapsed
   effort, assistance, patches and friction. Fix blocking issues and repeat with
   fresh participants where prior coaching would mask the problem.
3. **Runtime and compatibility:** unchanged legacy apps run; unsupported versions
   fail clearly. Test isolation, CPU loops, blocked waits, cancellation, faults,
   handle lifetimes, exhaustion and malformed packages/assets/messages. Publish
   the supported old/new SDK, firmware, package, companion and website matrix.
4. **Durable data:** exercise modeled interruption points, full/damaged media,
   repeated saves, data migrations, export/restore and package/data recovery.
   Record write amplification and headroom. Physical power-loss and save-cycle
   evidence are necessary; emulator passes do not qualify flash endurance.
5. **Input, performance and power:** measure input-to-frame latency, frame-time
   distribution/worst stalls, launch time, memory peaks, save latency and write
   volume, USB throughput, Home/power response and battery/idle behavior. Define
   workloads, sample counts and numeric budgets from early measurements and
   ratify them before qualification. Emulator wall time is not hardware timing.
6. **UI tools:** C/C++ source authoring, preview and source/layout inspection
   work from the released bundles. Developer-owned logic remains inspectable;
   reference screens pass normal-input and reviewed visual tests. Release builds
   reproduce expected behavior without debug instrumentation.
7. **Hosts and distribution:** qualify Windows x86-64, macOS ARM64 and Linux
   x86-64 on documented OS versions. Test clean installation, offline build after
   dependency setup, preview/debug, tests, companion operation and update/removal.
   Native Windows evidence cannot be replaced by WSL. Extra architectures are
   explicit additions with owners and evidence, not automatic release blockers.
8. **Private and public installation:** provide a reviewed developer app-key
   enrollment/revocation and recovery path without weakening package verification
   or changing firmware trust roots. Test private install and store publish,
   install, update and withdrawal, including ownership and immutable releases.
   Developers build/test locally; store ingestion/signing checks remain required,
   but server-side builds and manual submission approval are not prerequisites.
   Qualify SDK GitHub login/logout, all-owned-app listing, project creation/linking,
   required icon/screenshots from the project folder, first publication and
   subsequent version updates. Exercise interrupted uploads, version/ownership
   conflicts and alternating website/SDK edits. The website form must remain
   usable, with identical account identity and publication rules.
9. **Release evidence:** resolve artifact licensing, notices/source packaging,
   host signing requirements and maintenance owners. Bind qualification to exact
   candidate hashes, board/build targets and commands. SDK downloads and website
   must agree on versions, capabilities, firmware requirements and limitations;
   verify the downloaded artifacts and installation journey after deployment.

Stable 1.0 has no unresolved blocking defects in these required journeys.
Previews may ship with clearly stated omissions; they do not turn missing
qualification into a pass. The earlier decision to release `0.2.0-dev` without
physical/Windows qualification does not qualify stable 1.0. Any later scope or
release exception must be recorded explicitly with its remaining limitations.

## 12. Estimates and first implementation batch

There is no defensible completion date yet. The earlier calendar ranges and
claims about one-day ports, one-hour UI work or fixed preview latency are
withdrawn as acceptance promises. Keep the usability ambition, measure it, and
set budgets against representative workloads before evaluating the beta.

Estimate R1–R6 after R0 identifies reusable components, resolves app distribution
terms, measures the runtime/UI/storage proofs and confirms contributors and
test equipment. Separate implementation effort from elapsed qualification time;
state assumptions, uncertainty and the critical path. Re-estimate after the four
applications work together and after independent trials. Do not let optional
libraries or background systems quietly re-enter the required schedule.

The first batch is:

1. Assign the capability inventory to required, conditional or deferred scope;
   pin reference programs/data, inventory app-linked licenses and select host
   versions, owners and physical qualification resources.
2. Measure the current runtime and prototype conventional C execution, allocation,
   waits, a larger memory budget and public Doom-style display/input hooks while
   keeping ABI 1 fixtures unchanged.
3. Prove a data-only save and streamed file beyond 64 KiB, including interruption
   recovery and the C I/O adapter. Use the selected non-game tool as a consumer.
4. Extend the existing C/C++ UI components using the two-screen proof, real ARM
   preview and source/layout inspection. Record fit and measured latency.
5. Test bounded existing math operations and an app-scoped USB/HTTPS image fetch
   with a controlled service and disconnect fixtures.
6. Review the evidence, settle contracts and estimates, and implement the R1–R4
   foundations. Integrate the four apps and conduct independent trials before
   freezing stable interfaces and declaring 1.0 qualified.

## 13. Validation for this document

This is a planning-only change. Check relative links/anchors, referenced paths
and commands, Markdown whitespace and the public source boundary. Later
implementation uses the repository checks, scaled to each change:

```sh
make test
make check-public
make firmware
make firmware-vm
make emulator
./vm/test-native-comprehensive.sh smoke
```

Follow [AGENTS.md](../AGENTS.md) for source durability, build ordering, physical
operation authorization and evidence. Planning updates do not perform a firmware
build, device operation, release or deployment.
