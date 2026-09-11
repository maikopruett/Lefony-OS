# Lefony native SDK — ABI 1 development candidate

Build C++ apps, package them as ARM executables, and run the same package inside
Lefony's Prime G2 emulator. SDK source lives alongside the firmware so its API,
loader and tests change together. A source archive can be distributed separately.

The SDK supports signed ABI 1 apps on the emulator and compatible physical
firmware, including app-private data and USB installation. Physical NAND
migration remains a development candidate awaiting hardware qualification.
The SDK is a small supported API; it does not expose the complete Escher or
Poincare feature set used internally by built-in applications.

## Quick start

Install Python 3.11+ and `arm-none-eabi-g++` / `arm-none-eabi-objcopy` from
**GCC 16.2.0**. The SDK checks that exact compiler version. QEMU must be the
Prime-specific build from this repository; a stock system QEMU is insufficient.

From the OS checkout:

```sh
make emulator firmware-vm
export PATH="$PWD/sdk/tools:$PATH"
lefony-sdk doctor
lefony-sdk new /tmp/my-native-app
cd /tmp/my-native-app
lefony-sdk build
lefony-sdk test
lefony-sdk run
lefony-sdk source
```

`run` opens the emulator until its window closes or you press Ctrl-C. `test`
executes the startup callback, saves `build/app.ppm` and `build/run.json`, and
stops the emulator. Use `--headless` for a machine without a desktop. Both accept
`--qemu /path/to/qemu-system-arm --firmware /path/to/firmware.elf` when the runtime
is outside the OS checkout. Unix-domain sockets currently require macOS or Linux;
Windows is not qualified.

`build` writes `build/app.elf` and a compiler/hash report. `package` also creates
`build/<id>-<version>.lfapp`. Debug symbols remain in `build/app-debug.elf`.
`source` writes `build/app.lfsrc`, containing only the manifest and native files
under `src/`. It excludes local instructions, build products, and other files.

To inspect or run a downloaded native package without rebuilding:

```sh
lefony-sdk inspect example-0.1.0.lfapp
lefony-sdk launch example-0.1.0.lfapp --test
lefony-sdk launch example-0.1.0.lfapp
```

These commands never flash hardware or upload anything. Python implements the
host tooling; Python application packages are not accepted.

## App project

`app.json` contains exactly `id`, `name`, `version`, `abi` and `license`. IDs are
lowercase letters/digits/hyphens, starting with a letter, at most 48 characters.
Versions use `major.minor.patch`; new apps use ABI `1`. Source lives under `src/` in `.cpp`
and `.h` files. Source bundles allow 64 files, 64 KiB per file, 512 KiB of text,
and 1 MiB encoded. Symlinks, binaries, custom build hooks and path traversal are
rejected. The store recompiles source using its trusted SDK build command.

Read the generated [AGENTS.md](templates/basic/AGENTS.md) before editing. It is
included in every new project. Examples:

- [Counter](examples/counter/src/main.cpp): button capture, touch and Confirm.
- [Form](examples/form/src/main.cpp): a bounded numeric text field.
- [Graph](examples/graph/src/main.cpp): drawing and arrow-key interaction.

## Implemented API

Include `lefony/app.h` and optionally `lefony/ui.h`. Export
`lefony_event(Event, uint32_t first, uint32_t second)`. The app returns after each
callback. App data persists between callbacks; the stack is reset each time.
Only one app can be loaded at a time. There is no allocator, libc, exceptions,
RTTI, dynamic global initialization, general filesystem, network or Poincare API.
Installed apps can use `readData` and `writeData` for their private 64 KiB store,
at most 4096 bytes per call. Writes commit with the package on normal exit;
callback faults discard staged changes. Version the data yourself, handle a
missing/older record, and never store raw pointers. Direct `run`/`test` previews
do not mount an installed app namespace; data calls return an error there.

The canvas is 320 × 240 RGB565. `fill`, bounded ASCII `text`, and monotonic
`millis` are system calls. Drawing composes into a private surface and presents
once after a successful callback. Helpers provide labels, unsigned number
formatting, basic buttons, a digit field and a quadratic plot; these are small
app-side helpers, not the complete Escher widget library.

The Native apps launcher emits Start, logical Key, Touch, Tick and Close.
It keeps Home/Back and power handling in the OS. Tick delivery follows the OS
300 ms timer; use `millis()` for elapsed time instead of counting callbacks.
Touch coordinates are canvas coordinates. Down, Move, Up and Cancel use the low
byte of `second`; the contact count uses the next byte. Multi-contact input
cancels basic button capture; this API does not yet expose both touch positions.

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
[full development plan](../docs/NATIVE-APP-SDK-PLAN.md) for the remaining gates.

## Automatic store publication

Sign in with GitHub on the website's Developers page, select `app.lfsrc`, enter
the matching app name, a description, an icon and at least one screenshot, then confirm permission to share the included source and license.
When the deployment's build service is enabled, passing submissions publish
without manual approval. Compatible calculators install the signed package through the app store.
People can leave one thumbs-up/down vote per app and an optional comment tied
to the version reviewed. Ratings supplement technical checks.

[Publisher setup](publisher/README.md) documents the isolated validator and
queue consumer. The website and storage are provisioned and a Linux validator
image is qualified locally. GitHub OAuth and a dedicated continuously running
consumer must be configured before public submissions open.

## Distribution and licensing

Run `python3 scripts/package_native_sdk.py --output dist/lefony-native-sdk-source.tar.gz`
from the OS root to create the standalone source kit. It includes templates,
examples, guidance, component notices and SHA-256 checksums. It excludes build
products, toolchain binaries, firmware, QEMU binaries and private files. A
macOS ARM64 desktop candidate can be built with `scripts/package_native_desktop.py`. It bundles Python, QEMU, the compiler and runtime libraries. See the setup runbook for qualification and redistribution requirements.

Original host tools are GPL-3.0-or-later; runtime/API/example fragments carry
CC-BY-NC-SA-4.0 notices. The complete firmware retains its upstream noncommercial
restriction. See the repository [license](../LICENSE.md). An app's manifest
license does not override the terms of code it incorporates.

See the [complete setup runbook](../docs/NATIVE-APP-SETUP.md) for the provisioned services, GitHub OAuth, private-key backup, validator service and remaining physical work.
