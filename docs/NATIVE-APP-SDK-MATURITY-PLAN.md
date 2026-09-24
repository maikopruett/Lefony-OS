# Lefony OS native SDK maturity plan

The [SDK 1.0 development plan](NATIVE-APP-SDK-1.0-PLAN.md) is the current authority
for 1.0 scope, milestones and release acceptance. It prioritizes C/C++ portability,
durable storage, polished UI authoring/ARM preview and basic USB/HTTPS connectivity,
proved by four applications. Its scope replaces this document's earlier release
requirements and exclusions, including the larger math feature inventory.

Status: **earlier detailed backlog, 2026-09-11**. Some implementation is in
progress; see [candidate evidence](NATIVE-APP-MATURITY-EVIDENCE.md). The technical
detail below remains useful, but only requirements retained by the current 1.0
plan are release gates. References below to "complete," "required" and SDK 1.0
describe the earlier proposal. No milestone is complete merely because it appears
here, and this document does not change runtime or release contracts.

This roadmap previously superseded the [original SDK/store plan](NATIVE-APP-SDK-PLAN.md).
Older status reports remain historical evidence for their exact candidates.
The current plan retains local developer builds/tests and the store's ingestion,
ownership, package and signing checks; server rebuilds, always-on submission
validation and manual approval are not prerequisites.

## 1. Outcome and definition of complete

A developer should be able to install a released SDK from the Developers page,
create a standalone C++ project, build a polished native calculator application,
debug and test it locally, publish it through GitHub sign-in, and install it
through the website. Ordinary development must not require an OS checkout,
firmware rebuild, private hardware files or access to signing keys.

The SDK should support the breadth needed for calculator, graphing, statistics,
scientific, educational, reference, productivity and modest graphical apps.
Developers should have supported equivalents for useful built-in capabilities:
native-looking controls, expression editing, mathematical evaluation, plotting,
datasets, persistent documents, images, input, diagnostics and integration with
the main app menu. Exposing arbitrary internal OS classes is not the objective.

SDK 1.0 is complete when all required milestones in section 15 pass and:

- The reference applications in section 12 work using public SDK APIs only.
- Independently built older apps remain compatible with supported newer OS
  releases, with a published compatibility and deprecation policy.
- Linux, macOS and Windows developer journeys have qualified release artifacts
  and tested installation instructions on the website.
- A developer can reproduce an interaction bug, inspect a symbolized failure,
  test persistence and migration, and identify memory/performance problems.
- Installed apps retain the native ARM execution and isolation model, while
  runtime, USB and storage have explicit model and physical acceptance evidence.
- Every stable API has contracts, examples, error behavior, limits and tests.
- Store submission, installation, updating and developer withdrawal form a
  supported, documented journey without routine manual approval.

“Complete” is a release bar, not a promise to implement every desktop API or
freeze development forever. Advanced extensions have a separate post-1.0 list.

## 2. Decisions carried forward

1. **Native C++ apps.** Executables contain ARM machine code. Python remains
   host tooling only; Python app submissions are unsupported. This work does not
   remove the existing built-in Python application.
2. **SDK source stays in this OS repository.** Firmware, ABI, SDK, examples and
   contract tests evolve together. Publish standalone, independently versioned
   SDK artifacts. App authors keep their own repositories. A separate SDK source
   repository is unnecessary until there is a demonstrated maintenance benefit.
3. **One foreground third-party app initially.** Keep Home, power handling,
   drivers, interrupts, flash and USB under OS control. No kernel extensions,
   direct peripheral access or app-supplied background services for 1.0.
4. **Main menu integration.** Each installed app has its own name and icon beside
   built-in apps. The internal runtime container stays hidden.
5. **Shared app storage.** Preserve the reserved 64 MiB region and profile-2
   shared filesystem. Apps consume allocated storage according to size, with
   metadata and reliable-update headroom. Do not reintroduce fixed app slots.
6. **OS-owned setup.** The browser lists apps and capacity and performs requested
   installation, update and removal. It does not reserve space or require a
   storage backup as part of an ordinary app install. Existing firmware-update
   and recovery safeguards remain separate.
7. **Local developer validation.** Build and emulator testing happen on the
   developer's computer. The public service does not execute uploaded code or
   rebuild it. A local report is developer-supplied evidence, not remote proof.
8. **Automatic publication and GitHub accounts.** Keep required app name,
   description, icon and at least one screenshot. Preserve thumbs up/down and
   optional comments, immutable release versions and developer withdrawal.
9. **Trust domains remain separate.** App signatures authenticate distributed
   bytes; they do not certify quality. Firmware trust roots and update signatures
   must not change as a side effect of SDK work.
10. **Licenses remain explicit.** Follow [LICENSE.md](../LICENSE.md) and existing
    notices. Do not promise permissive SDK or app licensing without establishing
    the obligations of the exact headers, libraries and assets involved.

Platform maintainers may use CI to build and test the SDK itself. That is distinct
from introducing hosted validation of community submissions.

## 3. Starting point: implemented versus missing

This inventory is based on checked-in code, not solely on older deployment
instructions. It is not a new qualification of released binaries.

| Area | Current implementation | Work needed for maturity |
| --- | --- | --- |
| Build | [CLI](../sdk/tools/cli.py) uses pinned GCC 16.2.0, C++17, freestanding Cortex-A7 hard-float output; stripped distributable plus debug ELF | Release locks, incremental builds, editor integration, resource/dependency pipeline and complete diagnostics |
| App contract | [ABI 1 headers](../sdk/include/lefony/app.h), restricted ELF, signed packages, frozen service/event numbers | Capability discovery, extensible contracts, documented compatibility and richer services |
| Execution | [Runtime](../ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp) provides user mode, checked service pointers, protected mappings, timeouts and fault return | Adversarial service coverage, bounded extended services, resource accounting and diagnostic tooling |
| UI | [Helpers](../sdk/include/lefony/ui.h) provide basic labels, button, number field and quadratic plot | Layout, focus, navigation, text/expression editing, tables, menus, dialogs, themes and accessible interaction |
| Graphics | 320 × 240 RGB565 rectangle fill and bounded ASCII text | Efficient image/primitives/batch drawing, text layout, clipping and explicit performance budgets |
| Input | Start, Key, Touch, Tick, Close; limited logical keys; touch phase/contact count | Full Prime key semantics, both touch coordinates, gestures, repeat, lifecycle cancellation and text composition |
| Math | No public Poincare interface | Supported numeric, expression, symbolic, matrix, statistics and plotting facilities |
| Persistence | [Profile-2 storage](NATIVE-APP-STORAGE.md), signed apps/icons, private 64 KiB data; saves rewrite package plus data on normal exit | Persistent SDK workspaces, named documents, explicit atomic commits, efficient data writes, migration and export/import |
| Testing | [Runner](../sdk/tools/runner.py) launches the ARM package in QEMU; default test executes startup and captures a frame/report | Public interaction-test API, persistence fixtures, debug sessions, replay and benchmark reports |
| Distribution | Source kit and macOS ARM64 desktop candidate; other host paths require qualification | Clean-machine matrix, native Windows runner, signed/verified portable releases and SDK release maintenance |
| Store integration | Separate website repository implements local-SDK publication, GitHub login, listing media, ratings, signed icons and owner withdrawal | Schema synchronization, submission preflight, truthful test labels, compatibility filtering and release lifecycle tooling |

ABI 1 currently has no general allocator/libc, exceptions, RTTI, dynamic global
constructors, general filesystem, networking or public Poincare services. Its
linker reserves at most 1 MiB of code, bounded data below a separate 64 KiB stack;
the loader enforces the actual segment bounds. Private data is limited to 64 KiB
with 4096-byte transfers. Package and flash accounting limits are specified in
the [storage contract](NATIVE-APP-STORAGE.md). Do not advertise larger limits
until the corresponding runtime, parser and storage changes are qualified.

Documentation debt to resolve early: the SDK README, template instructions,
implementation-status and setup documents still include older server-validator
or backup/setup assumptions. The CLI's `doctor` also reports a hard-coded
`physical_install: false`; replace that with version/capability-aware reporting,
including “not checked” when no device was inspected.

## 4. Public architecture and compatibility

### 4.1 Layer responsibilities

| Layer | Responsibility | Boundary |
| --- | --- | --- |
| App source | App-specific behavior, models, rendering decisions and tests | Includes public SDK headers only |
| App-side libraries | Layout/widgets, algorithms, formatting, bounded containers, plotting and asset access | Run in the app's protected address space; statically linked and dead-code eliminated |
| Stable service boundary | Drawing submission, events, storage, OS integration and selected shared math operations | Versioned fixed-width wire types; checked copies, handles and quotas |
| Lefony OS | Isolation, scheduling/deadlines, driver ownership, persistence and shared engine adapters | No internal object pointers or privileged framebuffer/flash access exported |
| Host SDK | Cross-compilation, packaging, emulator/debugger, local testing and submission preparation | Does not flash devices or publish as a build/test side effect |

Use an ABI defined with C-compatible fixed-width structures and a C++ convenience
layer. Do not expose Escher/Poincare C++ layouts, STL types, exceptions, allocator
ownership or vtables across the system-call boundary. Port or wrap useful
built-in functionality deliberately; the developer-facing experience can be
consistent without inheriting every internal dependency.

### 4.2 Versioning rules

- Version the SDK release, app ABI, package schema, storage profile and USB
  protocol independently. Publish a matrix tying supported combinations together.
- Keep ABI 1 service numbers, event numbers and structures unchanged. An initial
  discovery extension must return an explicit unsupported result on older
  firmware, allowing a tested fallback. Do not probe by issuing mutations.
- Add versioned, size-tagged request/response structures with reserved fields,
  feature identifiers, explicit string encodings and stable error codes.
- Apps declare required and optional capabilities plus minimum supported OS/ABI
  metadata through an intentionally versioned manifest/package extension. Current
  strict parsers must not silently accept extra ABI 1 fields.
- The packer, SDK, store and firmware must agree on the new schema before an app
  can depend on it. Deploy compatible readers before publishing new writers.
- Negotiate compatibility before installation, then enforce it again in the
  loader. Unknown required features fail with an actionable message. Optional
  features have documented fallbacks.
- Keep a checked corpus of released ABI 1 packages, including Surface 3D, and
  test them unchanged against every stable candidate. New app-side libraries may
  require a rebuild; old binaries must not be silently broken.
- Proposed deprecation policy: retain documented stable interfaces throughout
  the SDK major line, publish migration guidance at least two stable SDK releases
  before removal, and use a new major ABI for incompatible removal. Security
  exceptions require a documented incident and recovery policy.

Each API specification records thread/callback context, ownership, lengths,
lifetime, quotas, cancellation, failure codes, worst-case work and compatibility.
All opaque handles are app-scoped, generation checked and invalidated on exit.

## 5. Runtime, language support and resource control

Keep C++17 as the first stable language baseline. Evaluate compiler changes as
SDK release changes; do not unpin the compiler to whatever happens to be on PATH.

Required work:

- Ship a documented supported standard-library subset: memory/string routines,
  numeric limits, safe formatting, spans/views, bounded containers and selected
  algorithms. Specify each component's provenance, footprint and failure model.
- Provide an app-local bounded allocator/arena with observable capacity and
  deterministic allocation failure. Any `new` support must define failure
  behavior; exceptions and RTTI remain unsupported unless a separate measured
  proposal justifies them. Reject unsupported global initialization at build time.
- Report code, static data, heap, stack, surfaces and resource usage separately.
  Derive legal memory layouts from a shared contract rather than duplicating
  unexplained constants across linker, loader and docs.
- Add cooperative task helpers for multi-step work, cancellation and progress.
  Computation must yield between callbacks. Timer events are not a precision
  clock; document monotonic time, rollover and requested scheduling behavior.
- Specify launch/restore, focus, close, suspend/resume and low-memory behavior.
  OS termination and Home/power handling must work even if an app ignores them.
  A close event must never be the sole mechanism for durable saves.
- Bound every extended syscall by input size and work. An IRQ deadline on user
  code alone does not make a long privileged math/storage call interruptible.
  Split expensive operations or implement a bounded cancellable execution path.
- Produce structured crash reports: app/package/OS identity, reason, event,
  program counter, fault address and resource summary. Avoid including saved
  user content by default. Symbolization happens locally using matching symbols.
- Review memory protections, ARM floating-point state, exception return paths,
  handle reuse, syscall flooding and cleanup across repeated launch/fault cycles.

Acceptance: invalid pointers, stack overflow, exhausted heap, illegal instructions,
privileged accesses, infinite loops and expensive-service abuse leave the OS
responsive, reclaim app resources and preserve previously committed app data.

## 6. UI, graphics and input SDK

### 6.1 Consistent native UI

Build a supported app-side UI library with Lefony theme tokens and behavior.
Prototype extraction/adaptation from Escher against a small implementation;
choose using footprint, API clarity, dependency and license evidence. Do not
require app authors to include private OS headers.

Stable 1.0 controls and services:

| Group | Required capability | Reference behavior |
| --- | --- | --- |
| Layout | Rows/columns, constraints, padding, clipping, scrolling, measured text, consistent spacing | Forms remain usable at 320 × 240 without off-screen actions |
| Navigation | Screens, tabs, focus groups, menus, dialogs, back stack, action labels | Keyboard and touch expose the same actions; Home remains OS-owned |
| Controls | Labels, buttons, toggles, choices, sliders, lists, tables, progress and empty/error states | Disabled/focused/pressed states and capture cancellation are consistent |
| Editing | Text/numeric fields, selection, caret, validation, scientific notation and expression field | Prime Shift/Alpha and mathematical input work without app-specific key hacks |
| Text/theme | UTF-8 policy, math glyph coverage, line wrapping, localization resources, theme metrics | Missing glyphs are predictable; contrast and focus remain visible |
| Accessibility | Keyboard-only navigation, clear focus, readable layouts, non-color-only status | Every reference app works without touch; text enlargement strategy documented |

Expression rendering/editing must use a documented expression representation
and math service/library contract. Shared clipboard access is mediated by the
OS and explicit user actions; no access to another app's private memory.

### 6.2 Graphics and assets

- Add clipped lines, polylines, polygons, circles, image blits and text layout.
- Add bounded drawing batches or copied pixel buffers so graphs do not require
  one syscall per point. Preserve private composition and OS-owned presentation;
  never expose DMA or the physical framebuffer to apps.
- Define transparency, scaling, stride, color conversion, overflow checks,
  dirty-region behavior and completion/presentation semantics.
- Supply deterministic asset conversion for images, fonts and data tables.
  Keep runtime decoders small and bounded; expensive conversion runs on the host.
- Version resource tables with offsets, sizes, encoding and integrity checks.
  Validate all offsets and decompression limits in the package/loader path.
- Use the same source icon to preview store and calculator variants. Preserve
  the existing signed icon attachment and package binding until an explicit
  versioned replacement is implemented across firmware and website.
- Provide a small software 3D example/library for transforms, projection,
  clipping and surface rendering. This is CPU rendering, with measured budgets;
  no GPU or desktop graphics API is promised.

### 6.3 Complete input model

Define all supported Prime keys, modifiers, repeat, press/release semantics and
text composition. Give both touch contacts stable identities and coordinates
in a versioned event structure. Implement pan, pinch, tap and long-press helpers
with capture, cancel, modal transition and lost-contact rules. Deliver input
through the same normal keyboard/Goodix path in emulator acceptance tests.

Acceptance: a form/table app and Surface 3D support keypad-only use, touch, modal
cancellation, focus restoration and repeated app exit/relaunch without stuck
controls. Inspect frames, then separately record physical interaction evidence.

## 7. Mathematics, expressions, datasets and plotting

### 7.1 Math architecture decision

Prototype two paths before committing the stable API: an app-side subset of
Poincare or reusable algorithms, and OS-managed shared math services. Measure
package/RAM cost, cancellation, engine reentrancy, performance and licensing.

Preferred starting design: small numeric operations and plotting algorithms
run app-side; expensive shared expression facilities use an OS-owned adapter
with app-scoped contexts and bounded calls. If an operation cannot be bounded
safely in privileged code, move it to app-side execution or a separately
interruptible design before shipping it. Do not export a synchronous unbounded
“evaluate anything” syscall.

### 7.2 Required capability families

| Family | SDK 1.0 target | Required semantics/tests |
| --- | --- | --- |
| Numeric foundation | Floating-point math, complex values, formatting, constants and units supported by the pinned engine | Precision, rounding, domain errors, NaN/infinity, angle modes and display preferences |
| Expressions | Parse, edit, format, evaluate, variables and scoped functions | Parse locations, unbound names, size/depth limits, cancellation and versioned serialization |
| Symbolic operations | Supported simplification, differentiation and supported exact arithmetic from the engine | Explicit supported subset; exact versus approximate results; unsupported operation errors |
| Numerical methods | Roots, numerical derivatives/integrals and bounded solver helpers | Tolerances, iteration limits, convergence failure, discontinuities and cancellation |
| Matrices/vectors | Construction, arithmetic and supported linear-system operations | Dimension/size limits, singularity, numeric conditioning and out-of-memory behavior |
| Statistics/probability | Descriptive statistics, regression and supported distributions | Empty/missing data, sample/population definitions, invalid parameters and known-answer fixtures |
| Plotting | Cartesian, parametric, polar, scatter and histogram plots, trace, axes, pan/zoom and curve sampling | Adaptive sampling limits, discontinuities, clipping, labels, invalid values and responsiveness |
| Datasets | Typed columns, validation, bounded iteration, CSV import/export through host exchange | Encoding, size limits, malformed input, deterministic round trips and document persistence |
| 3D helper | Surface mesh generation, camera transforms and software rendering | Near-plane clipping, degenerate geometry, bounded mesh size and cancellable sampling |

Inventory actual upstream operations before promising exact parity. Publish a
feature matrix with supported operations and limits; omissions in the required
families must be explicit scope decisions, not silent stubs returning plausible
answers. General computer algebra beyond the pinned engine is not a 1.0 goal.

Math contexts must isolate app variables from built-in app state by default.
Changing global angle/unit preferences is an explicit OS-mediated action;
read-only preference queries and app-local overrides are separate operations.
Stored expressions include a schema and migration policy, never engine pointers.

Acceptance: public-only expression, graph and statistics examples pass curated
known-answer tests, invalid/domain cases and resource/cancellation cases. Compare
results to the relevant built-in behavior where semantics match; comparison
alone is not an independent correctness oracle.

## 8. Durable data, documents and system integration

### 8.1 Persistence redesign inside the existing shared region

Separate immutable installed package bytes from frequently changing app data.
The current package-plus-data replacement rewrites the app for ordinary saves.
Design the next data format to update data without rewriting the package, while
retaining recoverable package/data generation pairing during app upgrades.

Required design and implementation:

- App-private named files/documents or records, directory enumeration, lengths,
  deletion, quota queries and bounded reads/writes. No raw host/OS paths.
- Explicit atomic commit/checkpoint, close and sync semantics; the UI may show
  “Saved” only after durable completion. Define what survives every interruption.
- Retain ABI 1's 64 KiB byte-store behavior through a compatibility adapter.
  Larger document quotas require measured RAM/flash/update-headroom budgets and
  a versioned capability; do not simply remove the limit.
- App/package upgrade transactions select compatible data generations atomically.
  Failed migration preserves the old app/data pair. An app migration runs in the
  constrained app runtime, never as privileged arbitrary code during installation.
- Distinguish install success from first-launch migration success. Keep enough
  recovery state for the defined rollback policy and report failures clearly.
- Do not introduce general version downgrades by bypassing current anti-downgrade
  checks. Specify recovery authorization and schema compatibility before adding
  any rollback command.
- Preserve existing profile-2 apps/icons and test any new format migration from
  actual old-format fixtures. No geometry, partition or trust-root change is
  assumed. Damaged/unrecognized volumes must never be automatically reformatted.
- Measure allocation amplification for small files/icons and write amplification
  for frequent saves. Consider bounded packing or inline-data changes only after
  profiling; each optimization must preserve atomicity and recoverability.
- Define file-descriptor counts, path grammar, maximum file count/size, quotas,
  headroom reservation and full-media failure behavior before freezing the API.

### 8.2 User-controlled exchange and system services

Add explicit per-app export/import through the host SDK and website where
supported. This is an optional data-management action, not an installation
backup requirement. Validate identity, schema, sizes and integrity on import;
cancelled or failed imports preserve existing data. Do not export other apps'
data or calculator identifiers implicitly.

Provide read-only OS version/capabilities, locale/theme/math preferences, battery
status when reliable, monotonic time and available app resources. Wall-clock
time must report validity and timezone assumptions; do not invent accurate time
when the platform cannot provide it. Document exam-mode access and OS restrictions.

Structured clipboard/document sharing uses explicit OS-mediated user actions.
Networking, arbitrary USB access and cross-app private-file access are excluded
from 1.0. A future host communication channel needs its own permissions and
transport proposal, not an escape hatch around the app sandbox.

Acceptance: a document survives clean exit and cold restart; a checkpoint
survives interruption; uncommitted work has documented loss behavior; a failed
update/migration/import leaves a usable prior state. Full-store replacement,
bad blocks and read-only recovery are exercised with model and physical evidence.

## 9. Build system, packaging and project tooling

Keep the simple CLI as the default entry point and offer a documented CMake
integration for larger apps. Both must use the same compiler flags, linker
contract, resource pipeline and package validator.

Deliverables:

- SDK lock file pinning SDK/toolchain/ABI/resources/dependencies and reproducible
  build inputs; distinguish source identity from output package identity.
- Incremental compilation and debug/release profiles with compiler invocation,
  map file, symbol file, dependency graph and size breakdown available locally.
- `compile_commands.json`, editor tasks and debugger launch configuration,
  including paths containing spaces and Unicode. An editor extension is optional;
  no proprietary IDE is required to use the SDK.
- Explicit supported dependency model: versioned or vendored source/static
  libraries, hashes and notices. No automatic arbitrary install/build hooks in
  the default template, and no hidden host dependency on Homebrew/system SDKs.
- Extend `.lfsrc` intentionally to include declared assets, tests, lock data and
  permitted dependencies. The current source-only `.cpp`/`.h` restrictions cannot
  support richer projects unchanged. Update host and store validators together.
- Deterministic packages and resources, bounded archive parsing, traversal and
  symlink rejection, and readable errors for oversized/unsupported content.
- Package inspect/explain output for compatibility, resource use, signature
  status and storage requirements. Distinguish download size from allocated
  flash usage; accounting comes from the OS when a device is connected.
- Local manifest/media validation: required name, description, icon and at least
  one screenshot; icon crop/conversion preview and screenshot capture helpers.
- SDK dependency/notice inventory and matching source distribution for bundled
  tools. An app manifest license never overrides incorporated component terms.

Proposed future commands, **not available merely because they appear here**:

```text
lefony-sdk sdk list | install | use | update
lefony-sdk new my-app --template graph
lefony-sdk build --profile debug
lefony-sdk run --workspace default
lefony-sdk debug
lefony-sdk test --suite all
lefony-sdk benchmark
lefony-sdk assets build
lefony-sdk package --check
lefony-sdk publish --dry-run
lefony-sdk login
lefony-sdk whoami
lefony-sdk apps list
lefony-sdk apps show APP_ID
lefony-sdk project link APP_ID
lefony-sdk publish
lefony-sdk logout
lefony-sdk app withdraw APP_ID
lefony-sdk device list
lefony-sdk device install APP_PACKAGE
lefony-sdk data export | import
```

Finalize syntax with implementation and `--help` tests. Building, testing,
packaging and dry runs never authenticate, publish or write to a calculator as
a side effect. Device mutations and withdrawal remain explicit commands with
clear targets; ambiguous USB results must be reconciled, not blindly retried.

## 10. Emulator, debugger and local test framework

### 10.1 Realistic persistent development

Create per-project emulator workspaces using synthetic public storage fixtures.
Install apps through the normal app-management path so private storage works
during ordinary `run` and `test`. Preserve workspace data between runs, with
explicit reset, clone, export and restore operations. Keep a fast disposable
preview mode, clearly distinguished from installed-mode persistence tests.

Use the same ARM app payload for emulator and physical execution. VM firmware
may expose test/debug facilities; those facilities must remain compiled out of
physical builds. Do not distribute real NAND/ROM captures as emulator assets.

### 10.2 Debugging and diagnostics

- Local GDB integration with matching ELF symbols, breakpoints, stepping,
  call stacks, register inspection and app-memory inspection.
- Debugger ports/sockets bind locally with controlled session lifetime. A full
  system emulator debugger is a host development facility, not a physical app
  capability or a production sandbox exception.
- Debug pause behavior is explicit: wall-clock pauses must not masquerade as
  normal timeout validation. Run deadline tests outside paused debug sessions.
- Bounded app logs with levels and overflow policy; source-located faults,
  resource inspectors and reproducible bug bundles without user data by default.
- Profile event/call duration, draw workload, allocation high-water marks,
  package size and flash write counts. VM timing is diagnostic, not a physical
  performance claim.

### 10.3 Tests developers can actually write

Provide a documented declarative input/replay and assertion API. It should
support launch, keys/modifiers, touch paths, time advancement, scene/screenshot
checks, data checks, close/relaunch, update and controlled interruption.

Separate test layers in reports:

1. Host logic tests for portable app algorithms, optionally with sanitizers.
2. Actual ARM package tests for ABI, lifecycle, interaction and resource bounds.
3. Installed-workspace tests for persistence, data migration and updates.
4. Platform adversarial tests for loader, syscalls, fault handling and storage.
5. Developer-recorded physical checks for input feel and hardware behavior.

Use platform-owned local test cases alongside author tests. A developer can
still modify their local environment/report; never describe either as independent
certification. Publish report schema versions, exact package/SDK/firmware hashes,
executed cases, skipped cases and failures. Do not silently equate the existing
startup-only test with the future comprehensive suite.

Acceptance: a new project outside the OS checkout can reproduce a key/touch bug,
save a screenshot, debug the source line, exercise saved data across restart and
export a redacted report through documented commands on every supported host.

## 11. Developer downloads and store integration

### 11.1 Host distribution matrix

| Host | SDK 1.0 requirement | Qualification |
| --- | --- | --- |
| macOS ARM64 | Self-contained compiler, host tools and desktop emulator | Fresh account/machine, signing/notarization, offline rebuild, relocated paths |
| macOS x86-64 | Supported bundle or explicit evidence-based support decision before 1.0 | Published minimum OS and tested install/build/debug flow; never silently serve ARM64 |
| Linux x86-64 | Portable artifact with declared minimum system dependencies and desktop/headless modes | Clean supported distro matrix, display backend, offline build and dependency checks |
| Windows x86-64 | Native installation and desktop emulator/debug workflow | Replace Unix-only control assumptions; test PowerShell, paths, firewall/session cleanup and tool discovery |
| Linux ARM64 | Secondary target with an explicit support decision | Qualify separately before displaying it as supported |

WSL2 can remain an interim Windows route, labeled as such. It does not fulfill
the native Windows 1.0 gate. Host support decisions include artifact ownership
and maintenance cost; do not leave ambiguous download buttons.

The Developers page provides copyable Linux shell, macOS shell and Windows
PowerShell commands, GUI/archive alternatives, version selection, checksums,
release notes and uninstall/update instructions. Installers verify authenticated
release metadata and artifact hashes, install atomically, handle interrupted
downloads and coexist with older SDK versions. Display only tested commands.

Release manifests pin the SDK, compiler, emulator, VM firmware, schema versions,
source revision, signatures/checksums and notices. Release SDKs independently
of routine OS builds, while publishing the compatible firmware range.

### 11.2 Local-only publication flow

```text
Developer source + declared assets + lock file
    -> local build and tests
    -> package + source bundle + local report + required listing media
    -> GitHub-authenticated submission
    -> server ownership/schema/size/package/integrity checks (no code execution)
    -> signature over accepted bytes and atomic publication
    -> website install -> calculator verifies -> main menu launch
```

The service must continue treating source, binary, tests and media as untrusted
input. Local reports can be forged and do not prove that source matches the
binary. Retain the actual artifact hash and label evidence “Developer tested
locally,” with SDK/OS versions where supplied. Do not claim a server rebuild,
independent passing tests or automatic safety certification.

Improve preflight so a submission error identifies the exact metadata, media,
compatibility or package issue. Keep source disclosure/permission and notices
explicit. CLI login must use a supported GitHub/browser OAuth flow without
embedding a client secret or signing key in SDK downloads; specify token
storage, scopes and logout before shipping it.

Keep immutable versions and publisher ownership. An owner can withdraw an app;
public downloads stop, installed copies remain usable, and feedback/identity
are retained according to the existing policy. A later new version can publish
again. Account compromise, key rotation and exceptional abuse takedowns need
documented recovery paths, without introducing routine manual review.

Acceptance: from a clean SDK install, a test publisher creates a listing with
all required media, publishes locally tested bytes, downloads/verifies/installs
them, publishes a data-preserving update and withdraws the listing. Ordinary
catalog viewing and refresh must perform no calculator mutations.

### 11.3 GitHub sign-in and the developer's app library

SDK publishing is a required first-class workflow. A developer must be able to
manage their apps without repeatedly filling out the website form. The website
submission option remains fully supported and uses the same accounts, app IDs,
validation rules and release history as the SDK.

- `lefony-sdk login` opens browser-based GitHub sign-in and returns an SDK session
  associated with the same stable GitHub account identity as the website. Choose
  a supported authorization flow during implementation; provide a copyable URL
  for terminals where opening a browser fails. Never ask for a GitHub password
  in the CLI or embed an OAuth client secret in distributed tooling.
- Use scoped, revocable SDK credentials, platform credential storage, expiration
  handling and explicit logout. Avoid tokens in project files, shell arguments,
  logs or uploaded archives. Sign-in grants store access, not blanket access to
  the developer's GitHub repositories. Repository integration is optional.
- `whoami` shows the active account; `apps list` lists **all** apps owned by that
  account, following pagination, including drafts and withdrawn listings.
  `apps show APP_ID` displays metadata, released versions, publication status and
  app-specific next actions. Never filter out an app just because its source is
  not present on this computer.
- Distinguish local projects from store apps and GitHub repositories. The SDK
  remembers local project locations per account without uploading absolute paths.
  Signing in on another computer retrieves the owned app library, not unuploaded
  local files. A registered store draft preserves identity/listing metadata; it
  is not an automatic cloud backup of the source tree.
- `new` scaffolds a project locally and works offline. First publication can
  create its store identity automatically, or an explicit proposed
  `apps create --draft` can reserve an ID for the signed-in owner without making
  the listing public. Define draft quotas and cleanup before enabling reservation.
- `project link APP_ID` associates an existing folder with an owned store app,
  verifies ownership and rejects a conflicting manifest ID. It never overwrites
  source. A proposed metadata pull command can import website-edited listing
  fields and media through a previewed merge; it must not discard local edits.

App IDs remain stable across releases, display-name changes and GitHub username
changes. Authorization is enforced on the server for every mutation, not inferred
from a local link file. Account switching invalidates cached ownership assumptions.

### 11.4 Publish directly from the project folder

The developer edits ordinary project files and drops listing images into a
conventional folder. Templates include this structure and explain each field:

```text
my-app/
  app.json                     # Existing package identity, name, version, ABI, license
  src/
  assets/                      # Resources used inside the installed application
  tests/
  store/
    listing.json               # Versioned listing schema and optional repository URL
    description.md             # Required app description
    release-notes.md            # Notes for the next release
    icon.png                   # Required app/store icon
    screenshots/
      01-main.png              # At least one screenshot; filename order is display order
      02-settings.png
  build/                       # Generated outputs; not indiscriminately uploaded
```

`app.json` is the single source of the app ID, name and release version; do not
ask the author to retype them into listing metadata. The listing schema records
its own version and any required source-publication permission. Define text
lengths, optional fields, supported image formats/dimensions/count and screenshot
ordering from a shared SDK/server contract. Preflight identifies the exact file
and remedy when the name, description, icon or screenshots are missing/invalid.
Markdown descriptions need a defined safe rendering or plain-text conversion
policy shared with the website.

`publish` consumes the project folder as one workflow: collect declared source
and resources, build/test locally, validate metadata/media and prepare the exact
submission. It uploads an allowlisted snapshot, not a recursive copy of every
file. Include the intended source bundle, package, local report and listing media;
exclude `.git`, credentials, caches, device captures and unrelated build outputs.
Reject escaping paths, symlinks, oversized content and unsupported archive entries.
This requires a versioned submission manifest and coordinated SDK/server schema;
it does not change the signed app envelope without a separate format decision.

All inputs are snapshotted and hashed before testing/upload. The uploaded package
must match the local test report's package hash. Changes made after the snapshot
belong to the next attempt. Server-side checks remain structural/integrity checks,
not execution or proof that a local test report is trustworthy.

Proposed first-publication and update journey:

```text
lefony-sdk login
lefony-sdk apps list
lefony-sdk new my-app
cd my-app
# Edit source/app.json and place description, icon and screenshots under store/.
lefony-sdk publish --dry-run
lefony-sdk publish
# Later: edit the app, raise app.json's version and update release notes/media.
lefony-sdk publish
lefony-sdk apps show my-app
```

Commands are proposed, not a claim that they exist in the released SDK. A dry
run creates a local submission summary/preview without authenticating or uploading.
An authenticated preflight may additionally check ownership and remote versions.
An explicit publish command creates a release without a separate mandatory website
form or routine approval step. Return the release status, version, package hash
and public app URL; distinguish received/processing from actually published.

### 11.5 Updates, recovery and website parity

- The same `publish` command handles first publication and subsequent releases.
  A linked project keeps its app ID and owner; updates require a higher immutable
  version and preserve listing history and ratings. Do not silently bump versions
  or create a second app because a name or directory changed.
- Repeated publication of the exact accepted submission returns the existing
  release. Different bytes at the same version produce an actionable conflict.
  Bind idempotency to account, app, version and submission digest; retain the
  attempt ID locally so interrupted uploads can query status or resume safely.
- Partial uploads never expose a public release. Staging objects have bounded
  retention; finalization checks every declared digest, ownership and version
  atomically before signing/exposing the release. Recheck authorization at commit.
- Publishing an update makes it available in the store. It does not install
  silently onto disconnected calculators. Preserve the explicit website/device
  update action and app-data compatibility checks.
- SDK and website can create listings, submit updates and withdraw owned apps.
  Both see the same release state and feedback. Website edits are versioned;
  SDK pushes based on stale listing revisions show a conflict/diff rather than
  silently overwriting newer text or images. Offer a metadata/media pull-and-merge
  path. Define metadata-only revisions separately from immutable executable bytes.
- Keep required media rules on both paths. The CLI may reuse unchanged uploaded
  assets by digest, but a complete release still references an icon and at least
  one screenshot. Deleting a local file must not silently delete remote media.
- Add template/`AGENTS.md` instructions for account identity, folder conventions,
  local checks, immutable versions, release notes and exact publishing commands.

Acceptance requires two accounts and at least two releases of one app: GitHub
login/logout/expiration, all-owned-app pagination, local project creation/linking,
folder-based first publication, version update, invalid/missing media, no private
file leakage, interrupted upload/retry, stale metadata and same-version conflicts,
unauthorized-owner rejection, withdrawal and re-publication as a new version.
Test switching between website and SDK editing on the same listing. Complete the
journey on Linux, macOS and Windows without manually selecting upload files or
re-entering project metadata in the website form.

## 12. Reference applications and developer documentation

Ship buildable standalone references that are also platform acceptance cases:

| App | Capabilities demonstrated | Required acceptance scenario |
| --- | --- | --- |
| Hello / Counter | Lifecycle, controls, basic input and theme | New developer reaches a working app without OS checkout |
| Forms and Tables | Navigation, editing, validation, focus, lists and dialogs | Complete flow by keypad and touch; cancellation never strands focus |
| Expression Notebook | Math editor/evaluation, documents and clipboard | Save/reopen expressions; handle invalid input and schema migration |
| Graph Explorer | Cartesian/parametric/polar plotting, tracing, pan/pinch | Discontinuities, domain errors and expensive sampling stay responsive |
| Statistics Lab | Datasets, regression, distributions and CSV exchange | Import malformed/valid data, compute known results, export and reopen |
| Surface 3D | Image/icon assets, numeric sampling, software 3D and profiling | Rotate/zoom using keys and touch; bounded mesh work and visible errors |
| Reference Browser | Searchable text/images, localization and scrolling | Asset bounds, search cancellation, readable layout and missing resources |
| Persistence Lab | Commit, interrupted save, quota exhaustion, upgrade migration | Old/new state consistency and exact documented rollback behavior |

Keep fault/abuse fixtures in developer tests, separate from consumer catalog
apps. Reference applications must not gain private exceptions or depend on
hidden emulator controls to implement user-visible functionality.

Documentation deliverables:

- A ten-minute quick start, app anatomy and beginner-to-reference-app tutorials.
- Versioned, searchable API reference bundled offline, with copyable examples.
- UI conventions, input mapping, math semantics and persistence/error guides.
- Debugging, testing, performance and migration cookbooks; troubleshooting by
  actual error code and symptom, including calculator connection failures.
- Package/signing/compatibility explanations and accurate store publication,
  update, withdrawal and local-evidence guidance.
- A generated per-project `AGENTS.md` covering supported commands/APIs, lifecycle,
  ownership, budgets, data schemas, normal input tests, frame inspection,
  licensing and explicit publication/device operations. It must not describe
  proposed APIs as shipped or claim VM evidence proves physical behavior.
- A feature matrix mapping built-in capabilities to public equivalents, planned
  gaps and deliberate exclusions. Review this with each stable SDK release.

Build snippets and freshly generated projects in SDK release checks. Keep one
canonical template in this repository; generate any standalone starter repository
from it. Preserve contributor instructions separately from app-author guidance.

## 13. Quality, performance and physical qualification gates

Create a baseline before optimizing and ratify numeric budgets in milestone M1.
The following are **proposed physical targets**, not measured current results:

| Metric | Initial target to validate | Method |
| --- | --- | --- |
| Key/touch response | Visible response within 100 ms at p95 in reference interactions | Defined physical input-to-frame measurement; record sampling method |
| App launch | First usable frame within 1 second at p95 for reference apps | Cold/warm launches with package identity and media state |
| Interactive plotting/3D | 20 fps at a documented representative workload | Physical frame timing, scene/mesh size and power configuration recorded |
| Responsiveness under long work | Home/cancellation remains available; no callback exceeds its enforced budget | Adversarial model tests plus hardware confirmation |
| Small data save | No rewrite of unchanged package; write count/bytes bounded and reported | Storage instrumentation on repeated representative checkpoints |
| Clean installation | Install to first sample run within 15 minutes, excluding download time | New-user/clean-host trial; list prerequisites and errors |

If measurements invalidate a target, revise the workload/target in a decision
record before calling the milestone complete. Never substitute VM wall-clock
numbers for calculator performance or claim flash endurance from a short test.

Required regression matrix:

- **ABI/parser:** supported-old/new binaries, malformed ELF/packages/assets,
  truncation, integer overflow, unknown features, invalid signatures and keys.
- **Runtime/services:** pointer permissions and boundaries, handles after exit,
  stack/heap exhaustion, floating-point state, timeouts and privileged-call work.
- **UX/math:** normal key/Goodix dispatch, focus/cancel, Unicode/maths input,
  numeric edge cases, error rendering, long computations and theme bounds.
- **Storage:** full media, fragmentation, bad blocks/ECC failures, every modeled
  transaction interruption, legacy migration, data-schema migration, read-only
  recovery and preservation of unrelated apps.
- **Transport:** partial replies, stale enumeration, disconnects, ambiguous
  acknowledgements, concurrent tools and mutual exclusion with firmware updates.
- **Distribution/store:** fresh host workflows, archive integrity, authentication,
  ownership, media requirements, immutable versions, exact-byte signing,
  withdrawal races and review retention.

Platform physical qualification records board identity/build target, candidate
and package hashes, repeat counts, commands, outcomes and remaining limitations.
Include actual power interruption, cold boots, full-volume updates, recovery and
repeated data-save behavior on suitable hardware. Keep device captures private.
Physical operations follow existing authorization/recovery rules; writing this
plan does not authorize a flash, erase or migration.

## 14. Operational and maintenance requirements

Give the SDK/API, runtime, storage, distribution and website contracts named
maintainer ownership before implementation. Changes spanning repositories need
a coordinated compatibility issue and rollout order, not simultaneous untracked
edits. These are responsibilities, not instructions to spawn agents.

- Run platform SDK release CI from public source and synthetic fixtures; archive
  immutable release manifests, compatible firmware and example package corpus.
- Keep signing keys outside app projects/releases. Rehearse app-key rotation and
  release-metadata recovery without replacing firmware trust roots accidentally.
- Back up store metadata and artifact indexes; rehearse a restore preserving
  ownership, withdrawn releases and reviews. Define artifact/source retention.
- Add actionable release/download/publication error monitoring and cost limits.
  No mandatory calculator telemetry is required to build, run, install or rate.
- Publish support channels, reproducible bug-report format and a security report
  path. Triage platform defects separately from app-specific incorrect results.
- Review dependencies, license notices and corresponding-source bundles on
  compiler/emulator/library updates. Preserve the repository's license model.

## 15. Milestones, dependencies and exit evidence

Each milestone needs an owner, reviewable changes, test evidence and updated
docs. Dates and effort estimates follow the prototype results; this document
does not invent a delivery deadline. Existing functionality is the baseline,
not work to reimplement from scratch.

| Milestone | Scope and deliverables | Depends on | Completion evidence |
| --- | --- | --- | --- |
| M0 — Current contract | Reconcile stale docs/doctor, inventory built-in capabilities, record package/ABI/storage limits and host matrix | Existing implementation | Code-linked capability matrix; commands match help; local-only publication documented consistently |
| M1 — Architecture prototypes | UI extraction, bounded math adapter, allocator, batched drawing, data-only transactions; baseline metrics and license inventory | M0 | Reproducible prototype reports and decisions; approved budgets/schema strategy with no silent ABI/layout changes |
| M2 — Compatibility foundation | Capability discovery, extensible wire/manifest/resource contracts, app-local runtime support, limits and errors | M1 | Old ABI 1 corpus unchanged; unsupported features rejected safely; coordinated host/store/firmware schema tests |
| M3 — Daily developer loop | Persistent emulator workspaces, GDB, logs/crash reports, editor files and public input-test API | M0; M2 for new diagnostics | Fresh external project builds, debugs, tests interaction/persistence and emits exact-hash reports |
| M4 — Full native interaction | Layout, controls, navigation, text/input, theme, assets, batched graphics and system queries | M2, M3 | Forms/Tables and Reference Browser pass public-API keypad/touch tests and frame review |
| M5 — Calculator capabilities | Expression editing, bounded math contexts, datasets, statistics, plotting and 3D helpers | M1 math decision; M2–M4 | Notebook, Graph Explorer, Statistics Lab and Surface 3D pass correctness, cancellation and measured workload cases |
| M6 — Durable documents | Data-only commits, named storage, quotas, migration/recovery, host export/import and ABI 1 adapter | M1 storage decision; M2, M3 | Persistence Lab passes interruptions/full-store/migration matrix; physical evidence required before stable durability claim |
| M7 — Distribution and publication | Qualified host bundles/installers, version manager, GitHub SDK login, owned-app library, folder-based creation/updates, website parity and Developers docs | M2–M6 | Linux/macOS/Windows clean-host journeys; sections 11.3–11.5 pass including mixed website/SDK edits, upload recovery and publish/install/update/withdraw |
| M8 — Public SDK beta | Stable-candidate APIs/docs/AGENTS.md, reference app suite, compatibility corpus, support and operational recovery | M4–M7 | At least two independent developers build different app types without private APIs or maintainer-only tools; blockers tracked |
| M9 — SDK 1.0 | Freeze stable contracts, close critical defects, qualify physical/runtime/storage behavior, finalize support matrix | M8 and physical gates | All required feature families accounted for; signed reproducible artifacts; rollback/restore drills; release checklist evidence |

M3 can begin while M1/M2 are designed; UI, math and storage work can proceed
independently once their interfaces are agreed. M7 installer prototypes can also
start early, but host qualification must use final candidate artifacts. These
dependencies are release gates rather than a requirement for strictly serial work.

Beta may identify experimental capabilities explicitly. SDK 1.0 must not claim
stable physical durability while corresponding physical gates remain pending.

## 16. First implementation backlog

Each item below should become a scoped change with its own acceptance evidence.
Role names identify ownership areas to assign, not currently assigned people.

| ID | Change | Primary owner area | Acceptance |
| --- | --- | --- | --- |
| MAT-001 | Reconcile SDK/status/setup/template docs with current local publication and OS-owned storage; fix doctor capability reporting | SDK/docs | No server-validation prerequisite or false capability claim in supported developer flow |
| MAT-002 | Check in API/built-in capability inventory, released app corpus and baseline resource report | SDK/runtime | Public feature matrix and reproducible current limits with ABI 1 fixtures |
| MAT-003 | Add installed, persistent synthetic emulator workspace support | SDK/emulator | Save through public API, exit, cold restart and recover exact data via normal app loader |
| MAT-004 | Expose public key/touch replay tests and structured report schema | SDK/tests | Newly generated app tests behavior beyond startup, with failures/skips represented accurately |
| MAT-005 | Add matching-symbol debugger configuration and structured app fault records | Runtime/SDK | Source breakpoint and symbolized crash reproduced outside OS checkout |
| MAT-006 | Prototype UI library footprint and full key/touch event contract | UI/runtime | Form navigable by keys/touch; compatibility decision recorded before ABI changes |
| MAT-007 | Prototype bounded math contexts and cancellation | Math/runtime | Correct representative expressions; resource exhaustion/cancellation never strands OS |
| MAT-008 | Prototype data-only atomic save and upgrade generation pairing | Storage | Interruption tests preserve a valid prior/new pair; package bytes not rewritten for data-only save |
| MAT-009 | Design capability discovery and versioned manifest/resource extension | Runtime/SDK/website | Shared contract fixtures exercise old/new parsers and safe deployment sequence |
| MAT-010 | Implement bounded app allocator/library subset and size reporting | SDK/runtime | Exhaustion errors and peak resource reporting verified on ARM guest |
| MAT-011 | Add bounded blit/batch rendering and deterministic asset compiler | Graphics/SDK | Surface 3D workload measured; malformed buffers/resources rejected |
| MAT-012 | Build cross-platform runner/installer prototype, especially native Windows | Distribution/emulator | New project runs with no undeclared development environment dependencies |
| MAT-013 | Add GitHub SDK sessions, owned-app library, draft creation and local project linking | SDK/website | Login/logout/expiration, pagination, account switching and server-enforced ownership pass |
| MAT-014 | Add store-folder scaffolding, listing/media schema, local preview and upload snapshot | SDK/website | Required files yield one validated submission; invalid media and undeclared/private files are rejected or excluded |
| MAT-015 | Implement folder-based publish/update, recoverable uploads and website metadata synchronization | SDK/website | First release and update work from CLI; interrupted retries, immutable versions, stale edits and website parity pass |

Start with MAT-001 through MAT-005 to make the existing SDK honest and convenient
to use daily. Use MAT-006 through MAT-009 to resolve the highest-impact design
questions before committing broad APIs. Then deliver complete vertical slices,
not a large collection of untested header declarations.

## 17. Deferred features and scope control

Post-1.0 candidates include background tasks, richer inter-app services, remote
host connectivity, a visual UI designer, live code replacement, additional host
architectures, package registries and new language front ends that emit the
supported native ABI. None are required to produce polished native C++ apps.

Explicit exclusions: Python app publishing, Linux/POSIX compatibility, arbitrary
kernel modules, unrestricted peripherals, automatic execution of uploaded source
on the public service, payments and removal of the OS's existing built-in apps.
Any change to these choices requires an explicit product/architecture decision.

Do not enlarge package/RAM quotas, add permissions or weaken signature checks
simply to make an example pass. First measure, optimize or narrow the operation;
then propose a versioned change if the required capability still cannot fit.

## 18. Validation when implementing this plan

Use the repository virtual environment and [contribution instructions](../AGENTS.md).
Existing commands to extend, choosing checks appropriate to each change:

```sh
make test
make check-public
make firmware
make firmware-vm
make emulator
./vm/test-native-comprehensive.sh smoke
```

Run physical and VM firmware builds sequentially because the generated upstream
checkout is recreated. SDK-specific coverage starts in
[host tests](../tests/test_native_app_package.py),
[ARM SDK tests](../vm/test-native-app-sdk.py),
[normal input tests](../vm/test-native-app-ui.py) and
[installed storage tests](../vm/test-native-app-storage.py).
Use each script's documented inputs rather than fabricating a command or signing
key. The public test key is never a production trust root.

For the original plan-only change, check Markdown links, command references,
`git diff --check` and `make check-public`. No build, hardware operation,
publication or store change is necessary to deliver the roadmap.
