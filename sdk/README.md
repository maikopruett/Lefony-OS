# Lefony native SDK — 0.2.0-dev / ABI 1 candidate

Build C++ apps, package them as ARM executables, and run the same package inside
Lefony's Prime G2 emulator. SDK source lives alongside the firmware so its API,
loader and tests change together. A source archive can be distributed separately.

The SDK supports signed ABI 1 apps on the emulator and compatible physical
firmware, including app-private data and USB installation. Physical NAND
migration remains a development candidate awaiting hardware qualification.
The SDK is a small supported API; it does not expose the complete Escher or
Poincare feature set used internally by built-in applications.

The [SDK 1.0 development plan](../docs/NATIVE-APP-SDK-1.0-PLAN.md) defines the
current scope and release gates: dependable C/C++ support, durable files,
polished UI authoring and actual ARM emulator preview, useful existing device
services and basic USB/HTTPS connectivity. Doom, a document/calculator app, an
existing non-game C tool and a small connected app prove the platform together.
UI authoring uses C/C++ components and actual ARM preview. Optional library
ports and cross-app background jobs are not 1.0 gates.

The earlier [maturity roadmap](../docs/NATIVE-APP-SDK-MATURITY-PLAN.md) remains a
detailed backlog. The [capability matrix](../docs/NATIVE-APP-CAPABILITIES.md)
records actual availability and remaining gaps. This candidate does not qualify
SDK 1.0; the development plan does not add features to this release.

The local [account candidate](ACCOUNTS.md) adds browser GitHub authorization,
revocable SDK sessions, owned-app listing/history and local project links.
It requires matching website changes. The [folder publication candidate](PUBLISHING.md)
adds `publish`, with snapshot/build/ARM testing, resumable upload and exact-package
signing. `--dry-run` prepares an offline preview; `--status`, `--resume` and
`--cancel` use saved attempts. `listing pull` merges saved store changes;
`listing push` edits metadata without a release, and `apps withdraw APP_ID`
withdraws owned store versions. Native host and coordinated distribution remain
in development. The matching backend is deployed, and these commands are in the
public macOS ARM64 and Linux x86-64 bundles. See the
[current release record](../docs/SDK-EMULATOR-RELEASE.md).

The local [private-install candidate](KEYS.md) adds OS-approved developer-key
enrollment/revocation, signed installation and explicit per-app lost-key
replacement. Local `keys generate` and `sign` now work directly in the desktop
executable. A local macOS bundle passes key/install/recovery and cold Notebook
journeys with exact data preservation. The public macOS and Linux bundles include these
commands. Clean-host and physical qualification
remain open.

The local [whole-app archive candidate](ARCHIVES.md) adds signed package/data
backup and restore, including pending recovery pairs. It includes explicit
replacement, cancellation, generation checks and damaged-data repair when the
installed signed package is intact. Explicit `--repair-code` can also restore
unreadable code when the surviving canonical record proves the exact original
signed package. Damaged canonical roots, broader resources, native-host and physical
qualification remain open. This is included in the public macOS and Linux bundles.

The local [ARM preview](UI.md) retains committed files and private data between
source edits, supports nested fixtures, and offers explicit reset/disposable
data modes. Notebook integrates package-upgrade acceptance after reading its
document; malformed data remains available for recovery. These changes require
the current archive-capable emulator firmware, included in the public macOS and Linux
bundles.

The local [API 11 channel candidate](CHANNEL.md) implements app-scoped USB
messaging and OS-owned pairing. A bounded HTTPS worker has local TLS tests;
the `companion` command now joins it to the USB channel. The
[Link Gallery](examples/link-gallery/README.md) candidate demonstrates streamed
images, a checked offline cache and explicit reconnect/cancel behavior.
Broader host, app and physical qualification remain in development.

The local [API 12 writer-cancellation candidate](FILES.md#explicit-writer-cancellation)
adds explicit discard and the C++ `FileWriter` helper. Notebook 0.6 and Link
Gallery 0.2 stage direct replacements, avoiding the extra logical quota of a
named temporary file. Basic ARM abort/fallback and full-quota app journeys pass,
including cancellation, rejected growth and cold reopening. Broader resource,
native-host and physical qualification remain open.

The current working tree additionally builds pure C11 and mixed C/C++ projects.
Use [`lefony/app_c.h`](include/lefony/app_c.h) for the existing ABI 1 callback
interface from C. See [C development status](C-DEVELOPMENT.md) for the supported
language profile and remaining runtime work. [Configured projects and source
format 2](PROJECTS.md) support larger C/C++ trees, with matching website reader
changes awaiting coordinated deployment. This addition
is not yet part of the downloadable `0.2.0-dev` artifacts.

The working tree also has an [experimental API 2 file service](FILES.md), with
authenticated handles, streamed writes, seeks and atomic replacement. Real
newlib stdio passes ARM file and lifecycle tests using the [API 3 foreground
candidate](FOREGROUND.md). Its execution, guarded heap, waits and copied-pixel
services compile into both firmware targets. The explicit [conventional runtime
profile](C-RUNTIME.md) now supplies `main`, allocation/stdio and C++ global
initialization/cleanup through the normal builder. Existing projects retain the
callback runtime. The [library comparison](../docs/NATIVE-APP-C-LIBRARY-COMPARISON.md)
selects newlib. Broader runtime/input and physical qualification remain open.

## Quick start

Install Python 3.11+ and `arm-none-eabi-g++` / `arm-none-eabi-objcopy` from
**GCC 16.2.0**. The SDK checks that exact compiler version. QEMU must be the
Prime-specific build from this repository; a stock system QEMU is insufficient.
Interaction tests and PNG resource conversion additionally require Pillow (`python -m pip install Pillow==12.3.0`).

From the OS checkout:

```sh
make emulator firmware-vm
export PATH="$PWD/sdk/tools:$PATH"
lefony-sdk doctor
lefony-sdk new /tmp/my-native-app --template pocket-lab
cd /tmp/my-native-app
lefony-sdk build
lefony-sdk test
lefony-sdk test --workspace development
lefony-sdk run
lefony-sdk source
```

`run` opens a local browser emulator with a larger touchscreen and all 50 Prime
matrix keys underneath. Choose 1.5×, 2× (default), or 3× screen zoom; the panel
fits narrower windows. Click the screen for touch input, click the keypad, or
use your computer's arrows, digits, Enter and Backspace. Shift and Alpha use
the calculator's normal behavior. The panel's **Stop emulator** button or Ctrl-C
closes the app and drains workspace saves. Closing the browser tab releases
input; the terminal session stays available at the printed local URL.
Use `run --workspace development` to keep saved app data between runs.
This panel is included in the current public macOS and Linux bundles. The legacy
ARM64 Linux source installer retains its older window. `debug` retains its native window.

`test`
runs bounded JSON keypad/Goodix replays below `tests/` (including nested folders), stores frames under
`build/tests/` and writes `build/run.json`. If no author tests exist, it runs
startup and explicitly records the skipped interaction suite. `test --suite startup`
selects the original startup-only check and writes `build/app.ppm`.
Use `--headless` for a machine without a desktop. Both accept
`--qemu /path/to/qemu-system-arm --firmware /path/to/firmware.elf` when the runtime
is outside the OS checkout. Unix-domain sockets currently require macOS or Linux;
Windows is not qualified.

`build` writes `build/app.elf` and a compiler/hash/resource report. `package` also creates
`build/<id>-<version>.lfapp`. Debug symbols remain in `build/app-debug.elf`.
`source` writes `build/app.lfsrc`, containing only the manifest and native files
under `src/`. Source format 0 excludes tests, assets, lock data, local instructions
and build products. Opt-in `source --format 1` retains hashed assets, local
replay JSON, lock data and notices with strict file and total size limits.
Format 1 or 2 is required for schema-1 manifests. `source --format 2` additionally
supports C, larger trees and optional `project.json` configuration. None of these
formats executes build hooks.
See the [contract extension](../docs/NATIVE-APP-CONTRACT-EXTENSIONS.md).

Builds create `sdk.lock.json` and reject a different SDK identity. Explicitly
run `lefony-sdk lock --update` when upgrading the project to a changed SDK.
Keep the lock in the app repository. `build --profile debug` uses `-Og`; release
uses `-Os`. Both keep debug symbols, `build/app.map`, resource counts and
`compile_commands.json`. Unchanged translation units are reused. The callback
profile rejects dynamic global constructors; the explicit
[main/newlib profile](C-RUNTIME.md) runs them before main.

For CMake projects, the generated `CMakeLists.txt` delegates to the same pinned
CLI, compiler flags and package validator:

```sh
cmake -S . -B build/cmake -DLEFONY_SDK_ROOT=/path/to/installed/sdk -DCMAKE_BUILD_TYPE=Debug
cmake --build build/cmake
```

To inspect or run a downloaded native package without rebuilding:

```sh
lefony-sdk inspect example-0.1.0.lfapp
lefony-sdk launch example-0.1.0.lfapp --test
lefony-sdk launch example-0.1.0.lfapp
```

These commands never flash hardware or upload anything. Python implements the
host tooling; Python application packages are not accepted.

The development candidate also provides explicit [app file import/export](FILE-EXCHANGE.md)
with `lefony-sdk files info`, `list`, `import` and `export`. Close the app before
transferring files. Replacement requires `--replace`; imports verify the complete
hash before committing. This feature needs matching file-exchange firmware and
remains unqualified on physical hardware.

The [API 8 private-data controller](DATA.md) adds live checkpoints, explicit
schema migration and acceptance of a completed upgrade. Saved checkpoints remain
separate from later unsaved edits, and migration retains the previous compatible
package/data pair until acceptance. Explicit [private-data backup/restore and
retained-pair rollback](DATA-RECOVERY.md) use `lefony-sdk data` and require firmware
advertising the recovery extension. [Whole-app archives](ARCHIVES.md) additionally
repair damaged data and unreadable code when original package identity survives;
unknown/unreadable canonical roots remain outside that repair contract.

## App project

`app.json` contains exactly `id`, `name`, `version`, `abi` and `license`. IDs are
lowercase letters/digits/hyphens, starting with a letter, at most 48 characters.
Versions use `major.minor.patch`; new apps use ABI `1`. Source lives under `src/` in `.cpp`
and `.h` files. Source bundles allow 64 files, 64 KiB per file, 512 KiB of text,
and 1 MiB encoded. Symlinks, binaries, custom build hooks and path traversal are
rejected. The website accepts the locally built package and accompanying source;
it does not recompile or execute submissions.

Read the generated [AGENTS.md](templates/basic/AGENTS.md) before editing. It is
included in every new project. Examples:

- [Counter](examples/counter/src/main.cpp): button capture, touch and Confirm.
- [C Main](examples/c-main/README.md): ordinary main, checked stdio saves and
  installed replay/cold persistence through the newlib profile.
- [Minigzip](ports/minigzip/README.md): a pinned existing C file-processing tool
  using the same startup, allocation and file adapters, with public user-file
  exchange and checked commit/abort workflows for quota, input and memory errors.
- [Form](examples/form/src/main.cpp): a bounded numeric text field.
- [Graph](examples/graph/src/main.cpp): drawing and arrow-key interaction.
- [Pocket Lab](examples/pocket-lab/src/main.cpp): numeric sample entry, bounded
  statistics, arena-backed batched graph drawing, persistence and touch cancellation.
- [Forms and Tables](examples/forms-tables/README.md): focus, UTF-8 selection
  editing, bounded scalar expressions, toggles, table rows, nested dialogs,
  Back navigation and staged data with keypad/touch acceptance.
- [Graph Explorer](examples/graph-explorer/README.md): adaptive Cartesian and
  parametric curves, clipped drawing, trace, keypad/touch pan/zoom and hold/reset.

## Implemented API

Include `lefony/app.h` and optionally `lefony/ui.h`. Export
`lefony_event(Event, uint32_t first, uint32_t second)`. The app returns after each
callback. App data persists between callbacks; the stack is reset each time.
Only one app can be loaded at a time. `runtime.h` adds an app-owned bounded arena,
checked fixed-capacity vector and cooperative task helper. Compiler-required
`memcpy`, `memset`, `memmove` and `memcmp` are statically linked when used.
This callback profile has no general libc or dynamic global initialization.
The [main/newlib profile](C-RUNTIME.md) supplies startup and a candidate C library.
The [function matrix](C-LIBRARY.md) defines its tested behavior and limits.
[Named files](FILES.md) and [USB/HTTPS connectivity](CHANNEL.md) use explicitly
negotiated services. General STL, exceptions and RTTI remain unsupported; the
selected expression/math helpers are described in the [API guide](API.md).
`ui_model.h` and `ui_controls.h` provide bounded rows/columns, focus/capture,
UTF-8 text selection, theme drawing and a screen stack. The stack requests Back
delivery through optional service 9; default Back behavior and Home/power control
are unchanged. Use software Back/Cancel controls on older firmware.
Installed apps can use `readData` and `writeData` for their private 64 KiB store,
at most 4096 bytes per call. Writes commit with the package on normal exit;
callback faults discard staged changes. Version the data yourself, handle a
missing/older record, and never store raw pointers. Direct `run`/`test` previews
do not mount an installed app namespace; data calls return an error there.
`--workspace NAME` instead installs a fixture-signed package through the modeled
USB path, launches it through the normal app loader, and preserves synthetic NAND
between sessions. Back exits and commits staged writes. An interrupted callback
does not commit; closing/killing QEMU before a normal exit can lose staged changes.
Changing installed bytes requires a new app version, just as on physical firmware.
The public emulator fixture is accepted only by VM builds, never physical builds.

```sh
lefony-sdk workspace info development
lefony-sdk workspace clone development experiment
lefony-sdk workspace export development saved-workspace.zip
lefony-sdk workspace restore restored saved-workspace.zip
lefony-sdk workspace reset experiment
```

Reset affects only the named synthetic workspace. Export is an explicit action
that includes saved app content; restore requires a new name and verifies hashes.
Concurrent sessions cannot mutate the same workspace. Workspace media is never
included in source packages or local test reports.

The canvas is 320 × 240 RGB565. `fill`, bounded ASCII `text`, and monotonic
`millis` are system calls. Drawing composes into a private surface and presents
once after a successful callback. Helpers provide labels, unsigned number
formatting, basic buttons, a digit field and a quadratic plot; these are small
app-side helpers, not the complete Escher widget library.

The Native apps launcher emits Start, logical Key, Touch, Tick and Close.
Home and power remain OS-owned; optional navigation depth lets the app handle
Back inside its own screens. Tick delivery follows the OS
300 ms timer; use `millis()` for elapsed time instead of counting callbacks.
Touch coordinates are canvas coordinates. Down, Move, Up and Cancel use the low
byte of `second`; the contact count uses the next byte. Multi-contact input
cancels basic button capture. Optional `input.h` snapshots add both stable touch
IDs/coordinates, fuller key tokens, modifiers and bounded UTF-8 text. Read-only
service 8 returns `-3` on older firmware; preserve the ABI 1 fallback. Raw key
release events and full mathematical layout remain planned. The UI model adds
bounded UTF-8 selection/caret editing, focus, capture cancellation and navigation;
`expression_input.h` composes supported Prime math keys into scalar grammar.

`extensions.h` provides optional capability discovery and atomic rectangle
batches (64 rectangles / 76800 total pixels). Older firmware returns `-3`, so
apps must provide original-service fallbacks. `numeric.h` provides an experimental
app-side statistics accumulator and bounded bisection solver. The solver requires
a continuous sign-changing bracket, rejects non-finite values, bounds iterations,
checks cancellation and requires a small residual before reporting convergence.
`expression.h` adds a bounded app-side scalar parser with independent variables,
arithmetic, real powers, angle-aware trig/log functions and per-node cancellation.
The app-linked OpenBSD/fdlibm subset retains exact source hashes and notices.
`linear.h` adds bounded dense matrix multiplication, transpose, solve and inverse.
These APIs have explicit limits and do not expose Poincare or symbolic operations. See the
[API guide](API.md) for grammar, error and ownership contracts.

`graphics.h` rasterizes clipped lines, circles and bounded RGB565 images.
`graphics_screen.h` coalesces/batches spans with old-firmware fallback. The
resumable `plot.h` sampler limits evaluation/depth and leaves unresolved segments
as gaps. [Graph Explorer](examples/graph-explorer/README.md) demonstrates sine,
reciprocal and parametric curves, keypad/touch pan and zoom, trace and reset.
[Forms and Tables](examples/forms-tables/README.md) demonstrates editing, focus,
table navigation and dialogs. Both have public interaction replays.

Every callback has a bounded one-second *modeled* budget, including syscall
work. The runtime returns to the OS on timeout, undefined instruction or memory
fault. Negative service returns indicate unsupported calls (`-3`) or invalid
arguments (`-4`). Callback result `1` means it returned normally; `-2` is timeout,
`-11` undefined instruction, `-13` prefetch abort and `-14` data abort. Success
is not a guarantee that an app calculates correctly or feels good to use.

## Package and isolation

`LFAPP0` has a 64-byte header, canonical manifest, restricted ELF32 ARM image,
and SHA-256 corruption check. The hash is **not a signature**. No physical
firmware accepts an unsigned container directly. Runtime access is user mode:
read-only executable code, writable non-executable data/stack, stack guards,
and validated service pointers. OS and peripheral mappings remain privileged.
The firmware, compiler and custom QEMU form part of the test trust boundary.

Store downloads use the authenticated [LFAPP1 envelope](../docs/NATIVE-APP-PACKAGE-FORMAT.md), verified independently by the host, website and guest. Physical installation requires a signed ABI 1 package and a provisioned [app storage profile](../docs/NATIVE-APP-STORAGE.md). ABI 0 remains emulator-only compatibility.

Current source supports USB protocol 2 and named files in the shared app
filesystem, as well as legacy protocol 1. OS startup migrates existing apps and
saved data; the SDK does not reserve app space when connecting to protocol 2.
Use an SDK build containing this support with profile-2 firmware; older published
SDKs may reject the new protocol until updated.

See [implementation status](../docs/NATIVE-APP-SDK-STATUS.md) and the
[maturity roadmap](../docs/NATIVE-APP-SDK-MATURITY-PLAN.md) for remaining gates.

## Automatic store publication

The matching local [folder publication candidate](PUBLISHING.md) also supports
`lefony-sdk login` followed by `lefony-sdk publish`, including update versions and
interrupted-upload recovery. Its website/SDK conflict merge workflow remains open.

Sign in with GitHub on the website's Developers page, select the local `.lfapp`
and `app.lfsrc`, enter
the matching app name, a description, an icon and at least one screenshot, then confirm permission to share the included source and license.
Confirm that you tested the exact submitted package locally. The website checks
ownership, schema, package structure, required media and integrity before signing
and publication. Compatible calculators install the signed package through the app store.
People can leave one thumbs-up/down vote per app and an optional comment tied
to the version reviewed. Ratings supplement technical checks.

No hosted validator, remote build, GitHub Actions submission test or manual
approval is required. The label is **Developer tested locally**; a signature does
not certify app quality or prove that binary and source correspond. Owners can
withdraw apps in their developer account. [Store setup](../docs/NATIVE-APP-SETUP.md)
describes staging/release checks; `publisher/` retains the historical validator.

## Testing and debugging

Read [the replay guide](TESTING.md) for the versioned input/assertion format.
Tests drive the actual keypad matrix and Goodix model, not direct controller
calls. Reports record exact package/SDK/firmware/QEMU hashes and executed,
failed and skipped checks. Model timing is not calculator performance.

`lefony-sdk debug` builds matching symbols, loads the app and pauses QEMU.
Run `lefony-sdk debugger` from that project in a second terminal to break at
`main` or `lefony_event`, step, inspect registers or view the stack. The current
desktop candidate bundles ARM GDB 17.2; source-kit users supply it separately.
See [native host tooling](HOSTS.md). The socket exists only within
the private local session directory and is removed on exit. Debug pauses must
not be used to qualify callback deadlines.

`lefony-sdk symbolize build/pocket-lab-0.1.0.lfapp 0x10000000` resolves a fault
PC with matching `build/app-debug.elf`; mismatched symbols are rejected. Reports
include callback reason/event/PC and draw/service counters; fault addresses and
stack peaks remain unavailable. User data is excluded from these reports.

## Distribution and licensing

Run `python3 scripts/package_native_sdk.py --output dist/lefony-native-sdk-source.tar.gz`
from the OS root to create the standalone source kit. It includes templates,
examples, guidance, component notices and SHA-256 checksums. It excludes build
products, toolchain binaries, firmware, QEMU binaries and private files. A
macOS ARM64 desktop candidate can be built with `scripts/package_native_desktop.py`. It bundles Python, QEMU, the compiler and runtime libraries. See the setup runbook for qualification and redistribution requirements.

Original host tools are GPL-3.0-or-later. Twelve original conventional app-side
runtime/interface/linker files and the startup-argument template offer
CC-BY-NC-SA-4.0 OR MIT; the exact scope and full MIT text are included in
`LICENSE.md` and `LICENSES/MIT.txt`. Other runtime/API/example fragments retain
their file-level notices. The complete firmware retains its upstream noncommercial
restriction. See the repository [license](../LICENSE.md). An app's manifest
license does not override the terms of code it incorporates.

See the [setup runbook](../docs/NATIVE-APP-SETUP.md) for GitHub sign-in,
local publication, key preservation and remaining physical/release work.

The `reference-cards` template demonstrates schema-1 requirements and app-local
PNG/text resources. Run `lefony-sdk new Cards --template reference-cards`, then
build/test in that directory. `lefony-sdk source --format 1` retains original
assets, conversion settings, replay tests and lock data. See [resources](API.md#lefonyresourcesh-and-assetsjson--local-resources)
for limits and ownership.

The local [C/C++ UI candidate](UI.md) adds OS fonts, configurable widgets, shared
menus/dialogs, the `ui-gallery` template and the Notebook document/calculator
example. `preview` incrementally builds the actual
ARM package and captures source-linked bounds in synthetic storage; it marks a
failed rebuild's retained frame stale. This requires the local API 9 firmware,
not the previously published SDK runtime.

### Faster USB transfers

Updated SDK builds negotiate the native LFB1 bulk transport for signed app
packages, bundled data and readback. Files are received in RAM, then installed
and verified through the existing file transaction. Old firmware automatically
uses the legacy transfer path. A failed transfer is never silently retried.
See [the protocol and limits](../docs/USB-BULK-PROTOCOL.md). Physical throughput
remains unqualified; installing the new OS once enables bulk for future work.
