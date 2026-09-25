# Native host tooling candidate

The current public macOS ARM64 and Linux x86-64 SDK candidates include the
browser emulator, all 50 clickable Prime keys and larger selectable touchscreen.
Frozen commands, normal KPP/Goodix input, saved/cold Notebook, complete archive
and matching source checks, R2 readback, public binary/source-kit hashes and
corresponding-source route checks pass. See the
[current release record](../docs/SDK-EMULATOR-RELEASE.md) for exact artifacts and evidence.
Current developer trials are scoped to maintainer macOS feedback; clean hosts,
Developer ID/notarization, native Linux/Windows, independent feedback and
physical qualification remain open. Windows source inputs are refreshed locally;
a complete Windows executable remains unavailable.

Windows x86-64 GCC 16.2.0/binutils 2.47, GDB 17.2, Prime QEMU 11.1.1/r70,
libusb and OpenSSL now have
cross-built component archives with verified source/build inputs. The compiler
audit covers 550 installed files, 39 ARM multilib variants and a Cortex-A7
hard-float link probe using native build tools. OpenSSL retains its configuration,
provider and engine DLLs. QEMU's nine dependency libraries, DLL closure and
corresponding source inputs are audited. The Windows Python input archive adds
14 reviewed wheels and matching source/license records. OpenSSL configuration
and module relocation is implemented. The full CPython 3.14.7 Windows runtime,
SBOM-referenced sources and original Microsoft runtime terms are now retained
and checked. QEMU uses its own DLL directory to avoid its libffi colliding with
CPython. A 22-component assembly now binds the Python and native tool source
records, 1,702 installed tool files and 139 newlib bundle files. A fresh native
GCC 16.2.0 newlib rebuild reproduces all 139 files exactly. Project source gates
also bind selected Windows QEMU and VM firmware bytes to retained build inputs. Native Windows execution, frozen SDK
assembly, credential stores and clean-host acceptance remain open.
Exact hashes and checks are in the [SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md).

Desktop packaging now requires the VM's compiled store keys to match every
`--public-key`. Build the VM with an explicit `LEFONY_APP_PUBLIC_KEYS` JSON list
of public PEM paths (the repository's existing store list is
`ports/lefony-prime-g2/app-trust-roots.json`). The default unconfigured firmware
has no store keys and cannot run an unchanged store-signed download. Do not fix
that mismatch by re-signing the download or replacing a signing identity.

The packager checks initialized app-key objects in the unstripped ARM ELF both
before staging and in the final bundle, including every compiled table copy.
It separately checks the public emulator fixture and forbids it as a store key.
Keep VM ELF symbols; a stripped or mismatched image fails packaging. The final
`firmware-trust-inputs.json` records identities and structural checks; it does
not claim signature execution or physical qualification. Store-app execution
must also pass with the chosen bundle and matching firmware/source artifacts.

The current Linux x86-64 archive includes the configured store-enabled VM,
corrected launcher library path, companion shutdown handling and QEMU
control-endpoint stall fix. The full packager finishes with firmware-trust and
project-source gates. Its 160-ELF audit binds 159 native and 1,101 target inputs.
The three freshly assembled source groups verify 4,287 payload files plus their
manifests across 82 components and explicit project archives. All 4,399 prepared
VM source members match the retained byte-identical rebuild evidence.

Fresh archive extractions into a path containing spaces and an accented character
pass 59 minimal-Ubuntu commands: eight external templates, warm/cold starts,
source exports, workspace recovery, private signing and reviewed Notebook/UI
Gallery previews. The unchanged published Surface 3D package passes signature
inspection and two independent launches using the bundled default firmware.
Bundled GDB and external CMake pass. All eleven frozen companion cases pass,
including streaming, errors, cancellation, disconnect, repeated requests, exact
cache readback and worker cleanup. Restrictive doctor and both isolation negative
controls pass. All 5,510 listed bundle files remain unchanged; the archive audit
also verifies SHA256SUMS itself and all 13 symlinks. Exact artifacts and the
freeze-time source snapshot are recorded in the SDK ledger.

These runs use explicit x86-64 emulation on an ARM64 host. Graphical/native Linux,
interactive credential-store prompts, physical USB, other clean supported hosts, upstream binary
rebuilds and coordinated release qualification remain open. Earlier failed and
recovered archives retain their original scope; exact candidates and evidence
are in the [SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md).

A later run of this same Linux archive passes 20 actual frozen CLI account
commands against an isolated GNOME Keyring 46.1 Secret Service and local HTTPS
fixture. Login, account/app lookup, origin isolation, replacement/revocation,
logout, missing-bus handling, lock/unlock and daemon-restart persistence pass.
Encrypted keyring files remain byte-identical through restart, contain no
plaintext test token and use mode 0600. All temporary credentials and owned
fixture processes/directories are removed. This validates the real credential
backend under emulation; it does not qualify interactive desktop prompts, native
clean hosts, another Secret Service implementation or real GitHub OAuth.
See [Linux credential qualification](#linux-credential-qualification).

The source SDK and frozen desktop SDK share the build, preview and debugger
entry points. `debug` prepares the emulator and matching symbols; `debugger`
opens that project's generated script with ARM GDB. `debugger --batch` and
repeatable `--execute` arguments also support scripted debugger checks.

The current macOS replay candidate passes 12 frozen CLI commands for interruption,
cold document preservation and publication preparation. Cancelled or hard-killed
replays cannot retain an earlier successful report, and interrupted preparation
does not create a ready submission. The matching firmware returns Shift+Home and
Shift+Apps to Settings, with normal-input app/consent regressions. A hard kill can
still leave the workspace's existing lock directory: the harness verifies refusal,
checks its owned process group is gone, then explicitly removes that fixture's
empty lock before recovery. This is not automatic stale-lock recovery. Exact
candidate and final bundle checks are in the
[SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md).

The newer local macOS diagnostics bundle passes 18 frozen CLI commands covering
repeated restored-workspace launches, a real QEMU startup error with more than
a pipe of stderr, and Notebook preview recovery. Failures replace old successful
startup reports and retain bounded host logs. Notebook preserves its saved
document/frame, clears obsolete failure attribution on the next attempt and
reopens successfully. Exact candidate hashes and the broader desktop/host results
are recorded in the [SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md).
The same bundle passes eight relocated offline templates, GDB/CMake, Notebook
touch/save/cold previews and both paragraph previews. The final host suite passes
1,419 tests with two expected private-fixture skips; the reproducible source kit
also builds and runs the same diagnostic/recovery entry points outside the checkout.
This does not establish the cause of the earlier spontaneous control-stream exit.

The newest local macOS ARM64 storage bundle passes 91 actual CLI steps across
eight ARM sessions. File/private-data/archive transfers handle Ctrl-C inside a
USB transfer, drain pending acknowledgments before cancellation, preserve prior
destinations and report accepted commits correctly. Cold reopening, upgrade
rollback with version history, fresh restore and damaged index/private/code
repair pass with independent filesystem inspection. The full host suite passes
1,408 tests with two expected private-fixture skips. Exact artifacts and the
desktop replay are recorded in the [SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md).
The same bundle passes all eight relocated offline templates, GDB/CMake, workspace
clone/export/restore and Notebook editing/save/cold-preview plus both paragraph
previews.
This is local modeled evidence; native supported hosts and physical operation
remain separate qualification.

The preceding private-signing bundle adds `keys generate` and `sign`, using its
bundled OpenSSL without an external Python installation. It passes 36 frozen
CLI steps across six ARM sessions for key enrollment/cancellation, signed
Notebook install, revocation, lost-key replacement, unused-key removal and backed-up
repair of a readable damaged registry. Partial backups also preserve independently
verified readable fragments; changed/cleared read faults invalidate pending repair.
Approved repair and a subsequent cold launch pass with the original page still
unreadable. Cold launches preserve the exact document
and export. Independent raw-filesystem inspection confirms repair changes no
installed package/data root. IP networking, checkout and Homebrew access are
denied to these commands; synthetic USB uses an explicit exclusive local socket.
The same bundle passes eight relocated offline templates, GDB/CMake integration,
Notebook touch editing/save/cold preview and Notebook/Gallery paragraphs.
This is local macOS evidence; clean supported hosts, unreadable ownership/metadata
and physical devices still require qualification.

The preceding local macOS ARM64 bundle includes the wrapping paragraph component,
Notebook 0.6.2 and UI Gallery 0.1.2. Eight relocated offline template journeys,
GDB/CMake integration, Notebook touch edit/save/cold-preview and both applications'
paragraph previews pass with checkout/Homebrew access denied. The paragraph
frames match the source ARM runs, and Notebook preserves unreadable input.

The preceding bundle passes eleven frozen companion ARM/model-USB cases,
including trailing fragments after ERROR and DONE followed by successful requests
under the same pairing. Its native TLS, account and publication evidence remains
bound to that retained artifact; those matrices were not rerun for the paragraph
bundle. Exact artifacts and further host/network checks are recorded in the
[SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md). This is a local development
candidate, not published or native Windows/Linux/physical qualification.

The [project text contract](PROJECTS.md#host-text-encoding) fixes metadata,
generated files and redirected CLI output to UTF-8, independently of the host's
default text locale. Source/debug/workspace checks and the real ARM Notebook
preview loop exercise this with Python UTF-8 mode disabled. Native Windows
path/console/compiler behavior still needs qualification on that host.

Emulator control, QMP, input, synthetic USB and GDB use private local sockets.
The debugger connects through a small SDK pipe relay. This supports spaces in
socket/install paths and avoids exposing an unauthenticated TCP monitor. The
relay uses binary I/O, bounded connection/send waits and exits when either peer
disconnects. GDB may remain idle at a breakpoint without an idle timeout.

The Windows connection adapter uses Winsock AF_UNIX because CPython lacks the
pathname parser on that host. Windows sessions require Python 3.13 or newer for
private temporary-directory permissions, and a temporary path short enough for
the 108-byte sockaddr field. This source path still requires execution on native
Windows. The desktop packager now has a native Windows x86-64 candidate path,
alongside macOS and Linux. Its dependency gates have host tests, but creation and
execution of a complete bundle on native Windows remain unqualified.

GDB's pipe launch differs by host: native MinGW GDB parses an argument vector;
Unix GDB invokes a shell. The SDK quotes each form separately, based on the
pinned GDB 17.2 `ser-mingw.c`, `ser-pipe.c` and libiberty sources. GDB's
[connection guide](https://www.sourceware.org/gdb/current/onlinedocs/gdb.html/Connecting.html)
documents the pipe protocol. Layout inspection uses a fixed dump basename in
the private session because GDB's dump filename parser does not handle quotes.

## Building a desktop candidate

### Linux shared libraries

The Linux packager explicitly collects the non-glibc libraries required by its
native helpers, including transitive graphics dependencies excluded by
PyInstaller's default selection. Missing dependencies and conflicting bytes for
the same library name fail packaging. Libraries loaded dynamically by name
still require explicit `--runtime-library` inputs and separate runtime checks.

After freezing, `patchelf` replaces build-directory library paths with paths
relative to each ELF helper or library. For the launcher, the packager first
checks and removes PyInstaller's `pydata` ELF section with `objcopy`, patches
the executable's library path, then reattaches exactly the same section. It
checks every embedded archive entry before atomically replacing the launcher.
Every native ELF, including the launcher, must resolve non-system dependencies
inside the bundle without inherited or injected `LD_LIBRARY_PATH`. The initial
ELF loader runs before PyInstaller can change its own environment. Direct
compiler use through CMake is also checked.
`linux-library-inputs.json`, `linux-relocation.json` and
`linux-dependencies.json` record input/output hashes and dependency paths;
the candidate binds these reports. Native-wheel output hashes are recorded
after relocation. Host glibc and its loader remain system requirements.

Linux source materials must also include `linux_native_inputs`,
`linux_non_host_inputs` and the pinned `linux_bootloader` record. Packaging
compares the actual freeze inputs with these inventories, including ARM target
archives such as `libgcc.a`, and checks each source provider's version and
collected inputs. Changing a library while keeping the same compiler executable
does not pass this check. `linux-native-source-inputs.json` binds input and
relocated output hashes to the source manifest. Correspondence checks do not
establish a reproducible rebuild of the upstream binaries or firmware.

Linux binary packaging also requires `--project-sources`, as Windows does.
The project manifest binds the selected VM and QEMU to explicit public SDK,
prepared QEMU and prepared firmware archives, with a retained successful,
byte-identical firmware rebuild report and log. The Linux assembler reads the
checked `qemu-prime` component's original input/notice catalog and build record;
it does not require the Windows component format. For example, after creating
the public snapshot below:

```sh
python3 scripts/native_desktop_project.py \
  --output build/linux-project-sources \
  --public-source build/sdk-public-source-v1/source.tar.gz \
  --prepared-source build/firmware-source/prepared-firmware.tar.gz \
  --rebuild-report build/firmware-source/report.json \
  --build-log build/firmware-source/build.log \
  --firmware dist/lefony-os-prime-g2-vm-native.elf \
  --qemu build/linux-qemu/install/qemu-system-arm \
  --source-materials build/linux-source-materials
```

Use the actual retained candidate directories. Pass the resulting
`build/linux-project-sources/project-sources.json` to both binary packaging and
the `lefony-qemu` source group. SDK/host recipe changes require a fresh public
snapshot. The final `project-source-inputs.json` binds bundled firmware and
QEMU bytes; Linux's QEMU check retains both its original input identity and the
relocated output identity from `linux-native-source-inputs.json`. This does not
qualify a native host or replace the firmware/store-key check.

Create the Lefony public working-tree archive before assembling source materials:

```sh
.venv/bin/python scripts/package_native_public_source.py \
  --output build/sdk-public-source-v1
```

The output contains `source.tar.gz` and a per-file `manifest.json`. It includes
the actual tracked and non-ignored working-tree files, applies the public-tree
boundary checks, and rejects concurrent changes. Ignored build inputs and Git
metadata are excluded. Repeated runs into new directories produce identical
archives for unchanged inputs. The manifest identifies this as a working-tree
snapshot and records the base commit separately; it does not claim a clean
committed release. Use the resulting archive as `lefony-public-source` in the
materials and as `lefony` in the project-source manifest below.

`scripts/package_native_desktop_sources.py` packages the toolchain and runtime
groups from their checked materials. The separate `lefony-qemu` group requires
`--project-sources path/to/project-sources.json`; it does not read whichever
generated firmware tree happens to be present. This schema-1 manifest contains
`firmware_sha256`, `qemu_input_sha256`, and an `archives` object with exactly
`lefony`, `qemu-prime` and `prepared-firmware` entries. Each entry supplies a
relative `file` and its `sha256`. All three tar archives must exist and match.
The output retains each original archive under its component directory and
includes a manifest with the adjusted paths. Extract those nested archives to
obtain the actual source trees. Runtime/toolchain-only packaging needs no Git
checkout or project-source manifest. Binary identities bind the declared inputs;
a separate rebuild report must establish whether those sources reproduce them.

Source packaging checks both source inputs and installed license notices against
their recorded hashes. Linux/macOS newlib components retain their original
`inputs`/`installed_notices` format; Windows components additionally require the
selected-sysroot `bundle` correspondence record. Do not convert a retained Unix
catalog into the Windows format merely to repackage its source archives.

The archiver also hashes the bytes it actually copies for every recorded input,
so changes after preflight cannot produce an archive whose contents disagree
with its manifest. It finishes all selected archives and the catalog in a
temporary directory before replacing existing outputs. Construction errors,
disk-full errors and cancellation therefore preserve the previous set. A hard
kill during construction can leave a `.source-stage-*` directory; a retry uses
a fresh staging directory. Remove abandoned staging only after checking that
its process has stopped. Final replacement spans several files and is not a
power-loss transaction; use a new output directory for each release candidate
and verify its complete catalog before publication.

This follows the Linux loader's [relative path and RUNPATH rules](https://man7.org/linux/man-pages/man8/ld.so.8.html)
and PyInstaller's [subprocess environment behavior](https://pyinstaller.org/en/v6.20.0/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application).
The checks do not establish graphical plug-in support, source completeness or
native-host qualification. The original minimal Ubuntu assembly failed to
start QEMU because `libdrm.so.2` was missing; retained attempts and subsequent
workflow evidence belong in the SDK ledger.

### Linux compiler inputs

`scripts/build_sdk_linux_toolchain.py` builds the existing GCC 16.2.0/binutils
2.47 pins for a Linux x86-64 host. It accepts locally retained, checksum-verified
source archives and installs only below a fresh output directory. For example,
on a native Linux x86-64 build machine with the required build dependencies:

```sh
python3 scripts/build_sdk_linux_toolchain.py --output /work/compiler-v1 \
  --execution native --jobs 2 \
  --gcc-archive /work/inputs/gcc-16.2.0.tar.xz \
  --binutils-archive /work/inputs/binutils-2.47.tar.bz2
```

The archives can be omitted to download the exact pinned inputs. Python 3.11 or
newer is required. `scripts/sdk-linux/Dockerfile` supplies Ubuntu 24.04 build
dependencies when given an explicit `BASE_IMAGE` digest. Builds executed in an
x86-64 container on another CPU must record `--execution emulated-container`.
That evidence does not qualify native-host performance or desktop integration.
Only a dedicated work folder needs to be mounted; do not mount private keys or
device archives. The source archives, recipe, notices, logs and installed-file
hashes are retained. Successful builds also compile and relocatably link a mixed
C11/C++17 ARM probe using the SDK's Cortex-A7 hard-float flags and installed
libgcc. Failed builds preserve their work for diagnosis.
Each command also records its status, elapsed time and exit code or timeout in
`commands.json`, alongside its complete log. Failed host tools are build failures;
their output is never promoted to a compiler candidate.

This is compiler build infrastructure. The resulting `install/` directory is
the compiler/binutils input to desktop packaging; it does not contain a complete
SDK. Matching Linux QEMU, GDB, Python/native dependencies and corresponding
sources, followed by the actual bundle/credential-store/device journeys, remain
required. The implementation ledger records completed and running candidates.
The first local emulated x86-64 attempts failed inside the host GCC before a
compiler candidate was produced. A separate image build also encountered a host
Python fault. Their exact reports are retained in the ledger; native Linux
qualification remains open.

### Building Linux x86-64 tools on Linux ARM64

`scripts/build_sdk_linux_cross.py` provides a Canadian cross-build route: native
ARM64 build tools produce a compiler that runs on x86-64 Linux and emits ARM app
code. GCC documents these separate [build, host and target roles](https://gcc.gnu.org/install/configure.html).
It requires an existing ARM64-hosted `arm-none-eabi` toolchain at the exact
GCC pin, an ARM64-hosted `x86_64-linux-gnu` C/C++ compiler, and the x86-64 development
libraries. It records and checks each tool's executable architecture, source
hashes and build/host/target triples. The native target compiler remains selected
for libgcc even after the new x86-64 host tools have been installed.

```sh
python3 scripts/build_sdk_linux_cross.py --output /work/compiler-x86-v1 \
  --build-toolchain /opt/toolchain --jobs 2 \
  --gcc-archive /work/inputs/gcc-16.2.0.tar.xz \
  --binutils-archive /work/inputs/binutils-2.47.tar.bz2
```

The optional `scripts/sdk-linux/Dockerfile.cross` assembles these dependencies
from an explicitly selected Ubuntu 24.04 ARM64 base that already contains
`/opt/toolchain`. Verify and record the base image identity. Its APT architecture
configuration applies only inside the build image. A dedicated Docker volume can
hold inputs/results when a VM does not mount the checkout; no host-wide mount or
binary-format configuration change is required by the recipe.

The recorded compiler build now passes configuration, compilation, installation
and the final mixed-language ARM probes. This is a completed compiler component;
the full Linux SDK and native-host qualification remain open.

The recipe retains scratch/output and failed command logs. Its final C11/C++17
ARM compile/link checks execute the resulting x86-64 compiler using the build
environment's existing binfmt emulation. These checks are labelled emulated and
cannot qualify native Linux execution. This is an implementation/build candidate;
consult the SDK ledger for actual build outcomes. Matching QEMU/GDB, Python/native
dependency sources, relocated bundles and the supported native-host journeys
remain required.

### Building Linux QEMU on ARM64

`scripts/build_sdk_linux_qemu.py` uses native ARM64 generators and an x86-64
cross compiler with the existing QEMU 11.1.1 / Prime r70 source. Supply a prepared
archive containing the Prime changes, pinned subprojects and offline Python
wheels. Verify it against the normal `vm/build-prime-g2-qemu.sh` inputs before
recording its hash. The build recipe checks that hash, archive paths, version,
required Prime files and tool architectures; the hash identifies your selected
input and does not independently establish its provenance.

`scripts/sdk-linux/Dockerfile.qemu-cross` downloads and extracts target library
packages under `/opt/lefony-qemu-sysroot`. It preserves native Python/build tools
and retains package names, versions and archive hashes inside the image. Native
Python packaging dependencies support QEMU's offline configuration. Select and
record the base and resulting image identities.

```sh
python3 scripts/build_sdk_linux_qemu.py --output /work/results/qemu-x86-v1 \
  --archive /work/inputs/qemu-prime-source-clean.tar.gz \
  --archive-sha256 SOURCE_ARCHIVE_SHA256 \
  --cross-prefix /usr/bin/x86_64-linux-gnu- \
  --sysroot /opt/lefony-qemu-sysroot \
  --pkg-config-libdir /opt/lefony-qemu-sysroot/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/share/pkgconfig \
  --jobs 2
```

Replace `SOURCE_ARCHIVE_SHA256` with the verified archive digest. Use a fresh
output path without spaces on a disk-backed volume. The selected pkg-config
directories and sysroot choose target libraries; build generators remain native.
Scratch, source, recipes and command outcomes are retained after failures. Final
version, SDL and Prime-machine probes execute x86-64 QEMU through existing binfmt
emulation with the target library path. Those checks do not qualify firmware
execution, a relocated bundle or native Linux. Actual outcomes belong in the
[SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md).

The completed component has additional ARM guest evidence: the new x86-64
compiler, debugger and QEMU work together at a source breakpoint; the current
SDK source runner passes unchanged Counter/Surface 3D normal-key, frame-change
and Home-exit checks using both headless and SDL dummy backends. The runner is
native ARM64 Python and the x86-64 tools use emulation. These checks leave the
complete Linux bundle, real desktop and native-host journeys unqualified.

### Linux Python packaging environment

`scripts/sdk-linux/Dockerfile.desktop` prepares Ubuntu 24.04 x86-64 Python,
PyInstaller, the credential-store dependencies and the libraries needed by the
completed compiler/GDB/QEMU components. Its CPython 3.12 wheel lock is
`scripts/sdk-linux/requirements-python-x86_64.txt`. Pip checks all 18 wheel hashes
alongside `sdk/requirements-desktop.txt`; incompatible changes to the shared
SDK pins must be resolved in the Linux lock too. The selected QEMU also needs
`libsndio7.0`, which SDL's runtime dependencies alone do not provide.

Create a dedicated context containing only these three inputs:

```sh
LEFONY_IMAGE_CONTEXT=$(mktemp -d)
cp scripts/sdk-linux/Dockerfile.desktop "$LEFONY_IMAGE_CONTEXT/Dockerfile"
cp sdk/requirements-desktop.txt scripts/sdk-linux/requirements-python-x86_64.txt "$LEFONY_IMAGE_CONTEXT/"
docker build --platform linux/amd64 \
  --build-arg BASE_IMAGE=ubuntu@sha256:a61567bd31828687156d735ea8eb01ba4e37636e225dd6a48ba94136a70d9d61 \
  --tag lefony-sdk-linux-desktop:candidate "$LEFONY_IMAGE_CONTEXT"
```

Retain the resulting image identity and `/usr/share/lefony-python/` inventories:
installed Debian/source-package versions, wheel URLs/hashes and resolved Python
versions. The image is a packaging environment, not an SDK download. PyInstaller
[bundles the interpreter that executes it](https://pyinstaller.org/en/v6.20.0/operating-mode.html),
so the native ARM64 source runner used for earlier component probes cannot
substitute for the x86-64 Python freeze.

The current diagnostic freeze produces a relocated x86-64 CLI. With matching
verification-progress firmware, fresh C and Notebook projects pass creation,
packaging, installed startup and format-2 source export. C also passes its
saved-visits replay; Notebook passes its bundled normal-input edit replay.
Link Gallery also passes fresh creation, packaging, installed startup and source
export. The earlier installed-app EOF was traced to a guest watchdog reset
during RSA verification. Verification
retains its signature checks, watchdog timeout and health checks; progress does
not arm the watchdog before the event loop starts. Existing bundled firmware
does not acquire this fix automatically.

The earlier fresh-project matrices remain failed: Notebook debug preview stopped
at a compiler segmentation fault, and a separate UI Gallery creation command
crashed the frozen CLI before compilation. These ran under QEMU-user 7.0.0
binfmt interpreter. Direct compiler failures occur with and without the bundled
library path and with Python's fork optimizations disabled. Traces include
failures after GCC spawns `cc1`; other failures have no diagnostic output. No
complete cause or correction is established. Earlier PyInstaller/QEMU failures
remain separate evidence. Exact inputs and outcomes belong in the SDK ledger;
these are component checks under emulation, not native Linux qualification.

A later interleaved 480-case comparison reproduces one `cc1` crash with that
interpreter; all 240 cases under explicitly invoked QEMU-user 10.0.4 pass.
The global interpreter and VM configuration remain unchanged. Subsequent CLI
checks invoke a recursive BuildKit variant explicitly and record its executable,
patches and process trees. This diagnostic environment is not bundled into the
SDK and does not prove native-host reliability or a particular upstream fix.

The new Linux frozen preview component waits for a completed screen that can
accept input, distinguishing Notebook's loading screen from its interactive UI.
Its five-phase saved-data test passes seeded preview, a title/source edit, cold
reopen, bounded unfinished-layout failure and recovery. It preserves exact
document/attachment bytes, asserts normal-touch scrolling without a startup
delay, and excludes private preview state from source export. A separate
13-command matrix passes fresh Notebook/Gallery creation, release packaging,
installed startup, replay, source export and debug preview, plus the expected
incomplete-component diagnostic. All 21 native
wheel inputs pass the source-lock audit after the new freeze. The component uses
separate mounted compiler/GDB/QEMU inputs and correctly reports incomplete
bundled tooling in `doctor`. Exact candidates and retained failed attempts are
in the SDK ledger; complete Linux assembly and clean/native hosts remain open.

The actual freeze has 58 verified x86-64 native inputs mapped to Debian packages
or downloaded wheels. The Linux wheel lock below now covers its 21 wheel inputs,
including Pillow's selected dependencies, CFFI's static libffi and cryptography's
Rust/static OpenSSL sources. Its check passes against the retained PyInstaller
input table and frozen output bytes. This does not reproduce upstream wheel
builds or cover a later freeze that adds native imports. Complete tool/dependency
assembly, relocation, Secret Service, desktop/USB operation and native clean-host
acceptance remain required.

#### Exact Ubuntu source collection

`scripts/collect_native_linux_sources.py` collects the Debian source packages
selected by an actual frozen-binary input inventory. Run it in the same Linux
x86-64 packaging environment that supplied those inputs. The inventory records
each original file/hash and its installed binary/source-package identity; the
collector rechecks those bytes and identities before downloading anything.

```sh
python scripts/collect_native_linux_sources.py \
  --inventory /work/results/python-native-inputs.json \
  --output /work/results/debian-sources
```

The default `scripts/sdk-linux/ubuntu-noble.sources` selects the signed Ubuntu
24.04 source repositories. `--repositories` accepts an explicit replacement for
a different packaging baseline. APT lists and caches are isolated inside the
new output directory. The collector uses exact source versions and downloads
without installing or unpacking packages, following the
[APT source command](https://manpages.ubuntu.com/manpages/noble/man8/apt-get.8.html).
Run with a read-only container root and a writable output volume to enforce
that boundary. Existing output directories are rejected so failed attempts
remain available for inspection.

The output retains authenticated source metadata, selected download URLs,
SHA-256/size checks, installed copyright notices, shared license texts, recipe,
input inventory and command logs. The current component run collects all 13
selected Ubuntu source packages. Its manifest deliberately sets
`complete_desktop_sources` to false: Python source distributions, wheel-embedded
libraries, compiler/debugger/emulator inputs and complete-bundle dependency
closure still need their own evidence. These archives alone are not a complete
desktop corresponding-source distribution.

`scripts/collect_native_linux_python_sources.py` collects the exact Python
source distributions from the image's pip installation report. It checks the
installed versions and matches wheel identities and native input bytes against
the same inventory before collecting sources. It also preserves installed
license files and distribution metadata, including wheel SBOMs and RECORD files.

```sh
python scripts/collect_native_linux_python_sources.py \
  --install-report /usr/share/lefony-python/install-report.json \
  --inventory /work/results/python-native-inputs.json \
  --output /work/results/python-sources
```

This collector uses `collect_native_desktop_sources.py` for source downloads and
notice extraction. Both scripts and their helper are in the source kit. The
current Linux image selects 18 Python packages. Their Python source archives do
not replace the separate native-wheel sources below; this manifest also remains
explicitly incomplete for desktop distribution.

#### Native libraries embedded in Linux wheels

`scripts/linux_wheel_native_sources.py` and its adjacent JSON lock bind the
actual Linux freeze's 19 Pillow files, CFFI extension and cryptography extension
to their original wheel hashes, metadata/notices and 56 source archives. Sources
include static dependencies, exact Rust crates/toolchain source and the relevant
Pillow/CFFI build recipes. The collector checks the original wheels and frozen
files before collecting source archives; it reads archive metadata without
executing upstream code. Existing output directories are rejected.

```sh
python scripts/linux_wheel_native_sources.py \
  --wheel-directory /work/inputs/original-wheels \
  --inventory /work/results/python-native-inputs.json \
  --bundle /work/results/lefony-sdk \
  --source-cache /work/inputs/cached-source-archives \
  --offline --output /work/results/linux-wheel-sources
```

Use the exact wheel filenames in the lock. `--source-cache` may be repeated;
omit `--offline` to download missing source archives from their pinned HTTPS
locations. Archive hashes and sizes must match. The result keeps complete
archives, original wheel metadata, extracted notices and a manifest whose
`complete_desktop_sources` remains false. It covers only the selected native
wheel inputs. Pillow's generic SBOM includes optional libraries absent from
this freeze; the lock identifies those omitted wheel files explicitly.

For complete source assembly, retain the `linux-wheel-native/` directory and its
component entry in the combined Linux manifest alongside the exact Python,
Ubuntu and compiler/debugger/emulator materials. Both desktop packagers verify
the wheel component against the checked-in lock, rejecting altered, missing or
unlisted files. Before freezing, the binary packager also verifies installed
wheel versions and bytes. After freezing, it records the actual PyInstaller
inputs in `linux-wheel-native-inputs.json` and binds that report to the candidate.
New native wheel imports require a source review and lock update.

The runtime source packager preserves scope/qualification fields in its archive
manifest, so packaging these materials alone cannot turn them into a complete
desktop-source claim. Original wheel builds, the rest of the tool dependencies
and complete host qualification remain separate work.

### macOS dependency inputs

macOS binary packaging now requires `--project-sources` with matching public SDK,
prepared QEMU and VM sources plus the retained exact firmware rebuild report/log.
The QEMU source component uses `qemu-prime/candidate.json` and `source.tar.gz`,
with platform `Darwin`, architecture `arm64` and checked build/source hashes.
After freezing, `macos-qemu-source-inputs.json` records the actual PyInstaller
QEMU input and its relocated, signed output. This scoped QEMU check does not
replace the dependency source/notice audit or native runtime tests. Changed or
missing source, wrong architecture and mismatched final binaries fail packaging.

The selected macOS ARM64 candidate uses the reviewed Pillow 12.3.0 CPython 3.14
wheel. The maintainer's `scripts/pillow_native_sources.json` binds its installed
files to the original wheel hash and records the source archives, native-library
versions, static AVIF codecs and Pillow's TIFF patch. The source collector retains
the pinned Pillow/multibuild recipes, composite notices and embedded dependency
inventory. It keeps the wheel itself out of corresponding-source downloads.

Before packaging, refresh a copied source-material directory with
`scripts/collect_native_desktop_sources.py --refresh-python --output DIRECTORY`.
Packaging verifies those inputs and records the actual PyInstaller source and
relocated output hashes in `pillow-native-inputs.json`. The full collector then
uses that verified inventory to distinguish wheel libraries from Homebrew
libraries. Changed inputs, missing sources/patches and unrecognized bundled
libraries fail. Other Python/platform wheels require separate reviewed inputs.

This is source correspondence for the selected binaries, not a byte-identical
rebuild of the upstream wheel. Pillow's original recipe used an unpinned source
mirror; retained mirror archives are pinned to Git blobs from before wheel
publication, rather than presented as an attestation of the builder's cache.
Source and host release qualification remain separately recorded in the SDK
ledger. The upstream [wheel recipe](https://github.com/python-pillow/Pillow/blob/bb1d8e8ab8d29048624d96e3ee53cecf7c13d13d/.github/workflows/wheels-dependencies.sh)
and [AVIF codec configuration](https://github.com/AOMediaCodec/libavif/tree/v1.4.2/cmake/Modules)
explain the source relationships.

The maintainer's `scripts/build_sdk_gdb.py` builds pinned GDB 17.2 on a Unix
host, without embedded Python/Guile or host Python paths. It verifies the source
archive, retains notices and records the install-tree hashes. For example:

```sh
.venv/bin/python scripts/build_sdk_gdb.py --output build/sdk-gdb \
  --gmp-prefix /opt/homebrew/opt/gmp --mpfr-prefix /opt/homebrew/opt/mpfr
```

Those two dependency-prefix options are optional when native configure already
finds GMP and MPFR. A native compiler, make and Expat are also required. An exact
`--archive` enables an offline build. The source pin does not change the SDK ARM
compiler, firmware, ABI or QEMU pin.

Build scratch uses `/tmp` by default because GNU make needs paths without spaces.
Use `--work-parent` with an existing directory on a disk-backed volume when a
container's `/tmp` is a small memory filesystem. The recipe records the scratch
path in `build-directory.json`, retains it on failure and removes it after a
successful build/install. Output directories can still contain spaces.

For Linux x86-64 GDB on an ARM64 build host, use `--linux-host` and explicit
x86-64 compiler/dependency prefixes. `scripts/sdk-linux/Dockerfile.gdb-cross`
extends the compiler cross image with Expat and an isolated dependency prefix:

```sh
python3 scripts/build_sdk_gdb.py --output /work/results/gdb-x86-v1 \
  --archive /work/inputs/gdb-17.2.tar.xz --work-parent /work/scratch \
  --linux-host --cross-prefix /usr/bin/x86_64-linux-gnu- --jobs 2 \
  --gmp-prefix /opt/lefony-cross-deps --mpfr-prefix /opt/lefony-cross-deps \
  --expat-prefix /opt/lefony-cross-deps
```

The recipe selects distinct build/host systems and checks the resulting ELF64
x86-64 program before executing its version/configuration probes. On ARM64 these
require the environment's existing x86-64 emulation; the candidate explicitly
records emulated execution. A completed build does not qualify native Linux
debugging. The recorded GDB build passes its version/configuration checks and a
source breakpoint, argument and return-value probe against native ARM64 QEMU.
This does not qualify Linux x86-64 QEMU or a complete bundle. Exact build and
debugger evidence are recorded in the SDK ledger.

For Windows GDB, the same Unix recipe accepts `--windows-host` with an explicit
`--cross-prefix` ending in `x86_64-w64-mingw32-`, plus Windows `--gmp-prefix`,
`--mpfr-prefix` and `--expat-prefix` directories. The build records the cross-tool
hashes and checks the resulting x86-64 PE; native execution is deferred to the
desktop packager. GDB 17.2 now has a completed Windows x86-64 cross build with
its three MinGW runtime DLLs and retained corresponding-source inputs. Its
static GMP, MPFR and Expat libraries have matching bytes from two builds.
PE/import and COFF checks remain separate from native execution. Each new
candidate retains its exact recipe and helper;
packaging an older candidate requires the original recipe matching its hash.

Build its Windows GMP, MPFR and Expat dependencies with the retained Ubuntu
source-material directories:

```sh
python3 scripts/build_sdk_windows_gdb_dependencies.py \
  --materials /work/source-materials --output /work/windows-deps-v1 \
  --work-parent /work/scratch --cross-prefix /usr/bin/x86_64-w64-mingw32- \
  --jobs 2
```

The checked `scripts/sdk-windows/gdb-dependencies.json` selects the same exact
GMP 6.3.0, MPFR 4.2.1 and patched Expat 2.6.1 source inputs retained for Linux.
The material root must contain `debian-gmp/archives`, `debian-mpfr4/archives` and
`debian-expat/archives`. All nine files are checked before extraction.
`dpkg-source` applies the downstream patches, GMP regenerates its configure
files and Expat runs its upstream `buildconf.sh`. Static libraries, sources,
notices, build commands and recipe inputs are retained. Failed scratch trees
remain available. The recipe makes no downloads or system installation.

`scripts/sdk-windows/Dockerfile.gdb-cross` supplies MinGW POSIX cross tools,
Autotools and pefile on a retained Linux build image. Record the resolved image
ID. Create `/work/scratch` before running; it must have a path without spaces.
Pass `/work/windows-deps-v1/install` to all three prefix options of
`build_sdk_gdb.py --windows-host`. Building on Unix produces a Windows executable;
execution, pipe transport and debugging still require native Windows tests.

The MinGW C++/GCC and threading DLLs have separate corresponding-source inputs.
Keep their exact installed package sources and the GCC base source used by that
MinGW package. Package metadata for `gcc-mingw-w64` alone does not include the
GCC base source. The ARM app compiler remains pinned independently at 16.2.0.

`scripts/package_native_desktop.py` requires the existing firmware, QEMU,
compiler, binutils, OpenSSL, trusted public keys and corresponding-source inputs,
plus `--newlib`, `--gdb-runtime`, `--libusb`, `--project-sources` and
`--emulator-window`. Build the native window first with
[`scripts/build_emulator_window.py`](../docs/EMULATOR-DESKTOP.md). The packager
checks source hashes, debugger build identity and the window bundle manifest. Build QEMU from neutral source/build paths as described
in the maintainer setup notes; binaries with private home paths are rejected.

The resulting folder includes the compiler, newlib, GDB, Python host runtime,
emulator, USB library and companion code. GDB's exact upstream source archive
and build recipe are copied beside the candidate. Other corresponding sources,
including patched QEMU and firmware, must accompany an actual distribution.
`doctor` loads the USB library without enumerating or opening a calculator.
Frozen USB commands use only their bundled library and fail clearly if it or a
dependency is missing.

### Windows compiler inputs

The Windows compiler uses the same GCC 16.2.0/binutils 2.47 source pins and ARM
multilib selection as Linux. Build it on Linux ARM64 with the existing native
ARM compiler and MinGW tools. The Windows executables are not run during this
build; native tools build and check the ARM runtime objects.

First extend the verified Windows GDB dependency prefix with MPC, ISL, zlib and
zstd. Set `WINDOWS_GDB_DEPENDENCY_SHA256` to the selected base candidate JSON's
verified SHA-256 before running:

```sh
python3 scripts/build_sdk_windows_compiler_dependencies.py \
  --base /work/windows-gdb-deps --base-sha256 "$WINDOWS_GDB_DEPENDENCY_SHA256" \
  --materials /work/source-materials --output /work/windows-compiler-deps \
  --work-parent /work/scratch --cross-prefix /usr/bin/x86_64-w64-mingw32- \
  --jobs 2
```

The checked `scripts/sdk-windows/compiler-dependencies.json` selects twelve
retained Ubuntu source files under `debian-mpclib3`, `debian-isl`, `debian-zlib`
and `debian-libzstd`, each with an `archives` subdirectory. The base candidate's
files are verified before copying. Copied libtool/pkg-config text metadata is
relocated to the new prefix, with before/after hashes; base library bytes stay
unchanged. Source archives, patches, notices and commands remain with the output.
The zstd static build includes multithreading support.

Set `WINDOWS_COMPILER_DEPENDENCY_SHA256` to the resulting verified candidate
JSON's SHA-256, then build the compiler in a fresh directory:

```sh
python3 scripts/build_sdk_linux_cross.py --windows-host \
  --output /work/windows-compiler-v1 --build-toolchain /opt/toolchain \
  --host-dependencies /work/windows-compiler-deps \
  --host-dependencies-sha256 "$WINDOWS_COMPILER_DEPENDENCY_SHA256" \
  --binutils-archive /work/inputs/binutils-2.47.tar.bz2 \
  --gcc-archive /work/inputs/gcc-16.2.0.tar.xz --jobs 2
```

The native build compiler must be ARM64 Linux GCC for `arm-none-eabi`, with
the exact 16.2.0 version. Windows host tools are checked as x86-64 PE binaries.
The ARM runtime link probe uses native build tools and is recorded separately
from Windows execution. Neither this probe nor PE inspection qualifies native
Windows compilation, relocated compiler paths, CMake or source debugging.

### Windows libusb and OpenSSL inputs

Use the same MinGW build image as the compiler/GDB components, an existing
scratch directory without whitespace, and fresh output directories:

```sh
python3 scripts/build_sdk_windows_libusb.py \
  --source-directory /work/source-materials/debian-libusb-1.0/archives \
  --output /work/windows-libusb --work-parent /work/scratch \
  --cross-prefix /usr/bin/x86_64-w64-mingw32- --jobs 2
python3 scripts/build_sdk_windows_openssl.py \
  --source-directory /work/source-materials/debian-openssl/archives \
  --output /work/windows-openssl --work-parent /work/scratch \
  --cross-prefix /usr/bin/x86_64-w64-mingw32- --jobs 2
```

These recipes verify exact retained Ubuntu source inputs (`libusb 1.0.27-1`
and `OpenSSL 3.0.13-0ubuntu3.15`) before extraction. They retain source archives,
downstream patches, notices, actual recipes, command logs and installed-file
hashes. OpenSSL also applies the two checked
[Windows adaptations](../scripts/sdk-windows/README.md#openssl-patches).
Both builds audit PE imports and required exported APIs; neither executes a
Windows program, generates a key or accesses USB devices.

The DLL is under `windows-libusb/install/bin`. OpenSSL's executable and main
DLLs are under `windows-openssl/install/bin`; the installation also retains
`ssl/openssl.cnf`, `lib/ossl-modules` and `lib/engines-3`. Its configured prefix
is `/opt/lefony-sdk/openssl`. Windows desktop packaging requires
`--openssl-runtime /work/windows-openssl` together with
`--openssl /work/windows-openssl/install/bin/openssl.exe` (use the corresponding
native Windows paths after transfer). It verifies the complete candidate file
set, source archives and actual build recipes, and copies configuration,
providers and engines into `_internal/openssl`. The source-material manifest
must contain one `windows-openssl` component with the candidate's exact version
and all source/recipe hashes in its `inputs`.

Frozen Windows signing selects the bundled executable by absolute path and sets
OpenSSL's configuration, include, provider and engine paths for that child only.
These [OpenSSL environment overrides](https://docs.openssl.org/3.0/man7/openssl-env/)
are computed from the current extracted location. Missing resources fail before
OpenSSL starts. Packaging checks copied bytes again after freezing, audits the
dynamically loaded DLLs, and runs provider loading plus an RSA sign/verify and
changed-payload rejection check with the public emulator fixture. Native Windows
execution of those checks and the complete frozen bundle remain unqualified.
The source pins and security patches remain unchanged.

### Windows packaging inputs and checks

The current reviewed packaging inputs require native x86-64 CPython 3.14.7 on Windows. PyInstaller
does not cross-package a Windows application from macOS/Linux. Supply native
GCC 16.2.0/binutils, the patched Prime QEMU, OpenSSL, libusb and the pinned GDB
candidate, plus the same ARM newlib, firmware, public keys and verified source
materials as other hosts. These Windows binaries and their exact corresponding
sources still need to be assembled and qualified. The existing Homebrew source
collector cannot produce a Windows native dependency inventory.

The Windows Python input lock now supplies 14 exact packaging wheels, their
Python source distributions, 17 embedded Pillow library/build source archives,
and wheel/source notices. It evaluates dependencies for Windows explicitly,
including `pywin32-ctypes` for Credential Manager. The binary and source packagers
require these matching materials; the binary packager additionally compares the
installed wheel files before freezing and records `windows-python-inputs.json`.
The separate CPython collector supplies the reviewed full interpreter ZIP,
CPython source, all 33 SBOM-referenced source archives and original notices.
Microsoft runtime DLLs retain their original distributable-code terms and have
no corresponding source claim. Reviewed upstream binaries have not been
independently rebuilt.

Collect on any host without installing or executing the Windows wheels:

```sh
python3 scripts/windows_python_sources.py \
  --output build/windows-python-materials \
  --cache /path/to/retained-archives
```

The optional cache is a flat directory of original hash-pinned archives.
Preserve the retained AOM, libyuv and libwebp Gitiles archives: fresh downloads
can have different archive bytes even when their file contents and modes match.
The collector rejects changed archive hashes. Exact retained source archives
accompany the Windows Python input artifact.

Collect the full [CPython 3.14.7 release](https://www.python.org/downloads/release/python-3147/)
on any host. The optional cache contains the exact runtime ZIP, metadata and
source archives named in [the lock](../scripts/windows_cpython_sources.json):

```sh
python3 scripts/windows_cpython_sources.py \
  --output build/windows-cpython-materials \
  --cache /path/to/retained-cpython-archives
```

The output retains the original ZIP and an extracted `runtime/` tree, plus a
`windows-cpython/` source component and manifest. The release manifest and source
signatures were verified with Python's published release identity; the collector
checks their reviewed hashes and retains the Sigstore bundles. It does not rerun
signature verification or claim individual Authenticode verification.

On Windows, use this extracted runtime to create the packaging environment
outside the runtime directory, then install the reviewed packaging wheels:

```powershell
build/windows-cpython-materials/runtime/python.exe -m venv build/windows-sdk-venv
build/windows-sdk-venv/Scripts/python.exe -m pip install --no-index --require-hashes --find-links build/windows-python-materials/wheels -r scripts/sdk-windows/requirements-python-x86_64.txt
```

Combine these source-component directories and manifest records with the
separate Windows compiler/QEMU/GDB/libusb/OpenSSL, CPython/runtime and firmware
materials before running the complete desktop packager. Pass
`--cpython-runtime build/windows-cpython-materials/python-3.14.7-amd64.zip`.
The packager compares the base interpreter, standard library and frozen CPython
DLLs against the original ZIP and records `windows-cpython-inputs.json`. It
rejects missing sources/notices and changed runtime bytes. A layout check on
macOS proves matching bytes and source coverage; native Windows startup, APIs,
credential storage and the final frozen dependency inventory remain unqualified.

The [native source assembler](../scripts/collect_native_windows_sources.py)
consumes the retained, extracted component artifacts and the combined 16 Python
source components. Its [reviewed component lock](../scripts/sdk-windows/native-components.json)
binds each original artifact's checksum inventory. Collection checks every file,
retains recipes and source archives, extracts GCC 13's nested runtime license
texts, and excludes generated Python caches from corresponding-source inputs.

```sh
python3 scripts/collect_native_windows_sources.py \
  --python-materials build/windows-python-combined \
  --compiler build/windows-components/lefony-windows-compiler \
  --gdb build/windows-components/lefony-windows-gdb \
  --qemu build/windows-components/lefony-windows-qemu \
  --libraries build/windows-components/lefony-windows-libraries \
  --newlib build/sdk-newlib \
  --output build/windows-source-materials
```

The result has 22 source components, a catalog of 1,702 installed tool files,
and a separate 139-file newlib bundle record. Newlib sources include the exact
upstream archive, license, candidate, reproduction recipe and SDK contracts.
Use it as `--source-materials` for native Windows packaging. The final packager
records `windows-native-source-inputs.json`, requiring every bundled PE binary
and copied toolchain/OpenSSL file to match its verified input providers. The
launcher separately records the reviewed PyInstaller bootloader and generated
output hash. Toolchain and runtime source archives preserve their selected
catalog entries and the native component lock identity for independent checks.

An offline assembled layout passes a 119-PE audit and source correspondence for
627 files, with changed-compiler and unknown-DLL rejection. It uses an unfrozen
bootloader and declared Windows system DLL fixtures; it is not a frozen SDK or
native Windows execution evidence.

The current Windows project-source set now selects the same store-enabled VM
ELF as the complete Linux archive, with its matching prepared sources and
retained byte-identical rebuild evidence. The older Windows source set points
to a VM without compiled store keys and fails the current selected-key gate.
Use the matching VM and project manifest together; replacing only the ELF also
fails source verification. The refreshed inputs preserve the existing Windows
QEMU and all 22 dependency source components. Exact hashes are in the SDK ledger.

A bounded isolated Wine 9 experiment did not complete the retained Windows
CPython 3.14.7 probe on this ARM host. It supplies no Windows freeze or native
acceptance evidence. A native Windows build host is still required for the
complete executable distribution and its qualification.

Windows binary packaging also requires `--project-sources`, containing public
Lefony sources, the exact prepared QEMU source, prepared VM firmware sources,
and the retained byte-identical firmware rebuild report and build log. Create
the public snapshot from the repository after finishing SDK/recipe changes:

```sh
python3 scripts/package_native_public_source.py --output build/windows-public-source
python3 scripts/native_desktop_project.py \
  --output build/windows-project-sources \
  --public-source build/windows-public-source/source.tar.gz \
  --prepared-source build/firmware-source/prepared-firmware.tar.gz \
  --rebuild-report build/firmware-source/report.json \
  --build-log build/firmware-source/build.log \
  --firmware dist/lefony-os-prime-g2-vm-native.elf \
  --qemu build/windows-components/lefony-windows-qemu/qemu/install/qemu-system-arm.exe \
  --source-materials build/windows-source-materials
```

Use the actual retained firmware rebuild directory in those three arguments.
The assembler checks all prepared firmware source members against the rebuild
inventory and binds the chosen QEMU executable to its source/build record.
It does not rerun either build. Pass the generated `project-sources.json` to
both desktop packaging and the `lefony-qemu` source archive group:

```sh
python3 scripts/package_native_desktop_sources.py \
  --materials build/windows-source-materials \
  --project-sources build/windows-project-sources/project-sources.json \
  --output build/windows-source-distribution
```

The desktop packager checks SDK and host recipe bytes against the public archive
before and after freezing. It checks all selected newlib files after staging and
in the final folder, then records `project-source-inputs.json` and
`newlib-inputs.json`. Changed SDK/recipes require a fresh public snapshot.
These source checks and the retained firmware proof do not establish Windows
execution or physical qualification.

The packager uses `.exe` names, the Windows Credential Manager backend and a
`lefony-sdk-windows-x86_64.zip` folder archive. `--dll-directory` adds explicit
dependency search directories; ambient `PATH` does not supply dependency-audit
inputs. Imported DLLs, delayed imports and forwarded exports are checked with
pinned pefile. Missing dependencies, non-x86-64 binaries, conflicting DLL bytes,
malformed tables and MSYS/Cygwin runtime dependencies fail packaging. Windows
system components remain external; VC runtimes require redistributable inputs.
On Windows, `--runtime-library` supplies QEMU libraries loaded dynamically by
name. QEMU and its complete DLL closure are copied beside its executable in
`_internal/runtime` after freezing, outside PyInstaller dependency collection.
CPython and QEMU require different `libffi-8.dll` builds; a flat DLL directory
is invalid. The final audit checks each process separately and rejects a
missing QEMU DLL even if a same-named CPython DLL exists.

The collected DLLs are audited again in the final folder, with hashes and
relative dependency paths in `windows-dependencies.json`. Every platform runs
the bundled `doctor`, QEMU, GDB and OpenSSL with bounded subprocess waits before
producing its archive. This smoke check loads libusb without enumerating or
opening a device. The final folder records `packaging-smoke.json`; it does not
qualify clean-host installation, Credential Manager operations, dynamic plug-ins
or physical USB. Keep `_internal` beside `lefony-sdk.exe` after extraction.

The loader treatment follows [PyInstaller's subprocess documentation](https://pyinstaller.org/en/v6.20.0/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application)
and [Windows DLL search rules](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order).
The SDK keeps bundled DLL search paths for its bundled helper processes.

Qualification requires the actual relocated bundle with checkout, package-manager
and network access denied, followed by native supported-host, credential-store,
companion/device and release-signing trials. Source-kit or emulator passes alone
do not qualify native Windows, clean-host installation or physical behavior.

The macOS offline checkpoint passes eight templates, source debugging, CMake
without Python discovery and Notebook/UI Gallery preview. Later HTTPS changes
use the host's native certificate store through pinned `truststore`, shared by
the account client and companion. Certificate and hostname verification remain
required. An explicit development CA file replaces system trust for that request
context and never changes the host's trust store. A missing native-trust runtime
fails clearly instead of falling back to build-host CA paths.

`doctor` performs no network request by default. An explicit read-only probe
uses the actual spawned companion worker, with a ten-second deadline:

```sh
lefony-sdk doctor --https-origin https://www.python.org
lefony-sdk doctor --https-origin https://localhost:8443 --https-ca-file dev-ca.pem
```

The probe sends HEAD to the origin root, downloads no response body and uses no
account credentials or calculator connection. A verified HTTP response, including
an HTTP error status, establishes TLS connectivity; it does not qualify the
service's application behavior. Redirects are not followed. Cancellation stops
the worker. Current bundle and native-host evidence belongs in the SDK ledger.

The later frozen companion checkpoint exercises the real ARM guest through an
explicit, exclusive `--emulator-usb` model socket, including fixed/chunked
uploads and responses, failed requests, cancellation and prior-cache preservation.
It also checks worker shutdown and ordinary OS pairing consent. See
[the channel guide](CHANNEL.md) for the narrow model adapter and socket handoff.
Physical USB, supported-host release qualification and cold-launch timing budgets
remain separate from these local modeled journeys.

Store HTTPS calls also use disposable spawned workers. The parent enforces a
20-second request deadline across DNS, certificate verification and transfers,
including IPC; cancellation stops the worker. The frozen macOS store deadline
check covers stalled TLS/headers, a slowly delivered body, Ctrl-C, truncated JSON
and redirect rejection. The account workflow separately checks native Keychain
replacement, revocation and cleanup. See [accounts](ACCOUNTS.md) for deadline and
unknown-mutation semantics.

### Windows QEMU cross-build recipes

The [Windows dependency pins](../scripts/sdk-windows/qemu-dependencies.json)
select source inputs for libiconv, gettext, libffi, PCRE2, zlib, GLib, SDL2,
pixman and libusb. Ubuntu archives retain the existing Linux-material versions;
libiconv/gettext are additional Windows inputs. Read the
[source and license notes](../scripts/sdk-windows/README.md#qemu-dependency-sources).
These build recipes are development candidates; their current result and
qualification scope are in the SDK ledger.

Use the MinGW image with native Meson, gettext and libtool macro prerequisites
from `scripts/sdk-windows/Dockerfile.qemu-cross`, and retain its resolved image
identity. Supply the pinned GNU archives/signatures under `/work/gnu-inputs`
and the existing `debian-*/archives` folders under `/work/source-materials`:

```sh
python3 scripts/build_sdk_windows_qemu_dependencies.py \
  --materials /work/source-materials --gnu-inputs /work/gnu-inputs \
  --output /work/windows-qemu-deps --work-parent /work/scratch \
  --cross-prefix /usr/bin/x86_64-w64-mingw32- --jobs 2
```

Both libraries and source inputs are retained in the candidate. GLib uses real
libintl, with native language support enabled. Cross builds omit host tests,
introspection and generated API documentation; native acceptance remains a
separate step. No Windows executable is invoked by the recipes.

After the dependency candidate passes, independently verify its files and set
`WINDOWS_QEMU_DEPENDENCY_SHA256` to its exact `candidate.json` hash. Use the
prepared QEMU source archive whose provenance matches the current Prime patch
set, and set `PREPARED_QEMU_SOURCE_SHA256` to that archive's verified hash:

```sh
python3 scripts/build_sdk_windows_qemu.py \
  --archive /work/prepared-qemu-source.tar.gz \
  --archive-sha256 "$PREPARED_QEMU_SOURCE_SHA256" \
  --dependencies /work/windows-qemu-deps \
  --dependencies-sha256 "$WINDOWS_QEMU_DEPENDENCY_SHA256" \
  --output /work/windows-qemu --work-parent /work/scratch \
  --cross-prefix /usr/bin/x86_64-w64-mingw32- --jobs 2
```

The recipe verifies the entire dependency installation, requires GLib/SDL/
pixman/libusb/zlib metadata and retains the dependency manifest. The resulting
QEMU component requires DLL collection and actual native Windows checks before
SDK desktop acceptance. A successful cross build cannot qualify the native
loader, private sockets, display, USB or guest execution.


## Linux credential qualification

`vm/test-sdk-desktop-accounts.py` exercises the actual frozen login, whoami,
apps and logout commands with synthetic accounts served over local HTTPS.
It refuses an origin that already has a credential and checks all issued test
tokens for output leaks, including replaced or revoked sessions. Linux requires
an explicit D-Bus session and a native `vm/linux-sdk-access.c` launcher; commands
cannot silently fall back to unrestricted execution. The bundle is verified
before and after testing. `--bundle-in-place` avoids a large duplicate copy.

The optional `vm/sdk_test_secret_service.py` fixture requires a new empty,
non-symlink session directory and `--isolated-test-service`. It creates a private
D-Bus/Keyring session with a nonempty random password, precreates the XDG keyring
directory to prevent legacy-home fallback, and never changes HOME. Its
GNOME-specific test control uses an encrypted session to unlock its own keyring;
the SDK continues using the ordinary Secret Service interface. This is not a
qualification of the desktop unlock dialog. The fixture bounds startup,
control operations and total lifetime and removes only its newly created
keyring/config/runtime directories during cleanup.

On native Linux, install the desktop Python requirements plus GNOME Keyring and
D-Bus, set `SDK_BUNDLE` to the absolute path of the extracted candidate, and use
new output directories for each attempt. A kernel with Landlock ABI 3 or newer
is required. The following runs an isolated fixture and stops it automatically
after the final empty-store check:

```sh
mkdir -p build
cc -O2 -Wall -Wextra vm/linux-sdk-access.c -o build/linux-sdk-access
(
  set -eu
  SDK_CREDENTIAL_SESSION=$(mktemp -d /tmp/lefony-sdk-credentials.XXXXXX)
  export DBUS_SESSION_BUS_ADDRESS="unix:path=$SDK_CREDENTIAL_SESSION/bus"
  .venv/bin/python vm/sdk_test_secret_service.py \
    --session "$SDK_CREDENTIAL_SESSION" \
    --output build/sdk-secret-service-qualification --isolated-test-service &
  SDK_CREDENTIAL_FIXTURE_PID=$!
  trap 'kill -TERM "$SDK_CREDENTIAL_FIXTURE_PID" 2>/dev/null || true; wait "$SDK_CREDENTIAL_FIXTURE_PID" 2>/dev/null || true' EXIT
  SDK_CREDENTIAL_WAIT=0
  until test -f "$SDK_CREDENTIAL_SESSION/ready.json"; do
    kill -0 "$SDK_CREDENTIAL_FIXTURE_PID"
    SDK_CREDENTIAL_WAIT=$((SDK_CREDENTIAL_WAIT + 1))
    test "$SDK_CREDENTIAL_WAIT" -lt 300
    sleep 0.1
  done
  .venv/bin/python vm/test-sdk-desktop-accounts.py \
    --bundle "$SDK_BUNDLE" --output build/sdk-account-qualification \
    --native-credentials --bundle-in-place \
    --access-launcher build/linux-sdk-access \
    --isolated-secret-service "$SDK_CREDENTIAL_SESSION"
  wait "$SDK_CREDENTIAL_FIXTURE_PID"
  trap - EXIT
)
```

The recorded ARM-host run instead uses two disposable containers sharing only
the fixture session directory: native ARM Python/Landlock controls the frozen
x86-64 SDK through its explicit interpreter; a separate x86-64 GNOME daemon owns
the encrypted keyring. Both containers deny external networking. The existing
native macOS/Keychain path remains supported by the harness but was not rerun in
this checkpoint. Windows Credential Manager and native clean-host acceptance
remain separate gates. Exact commands, versions, failures and passing reports
are in the [SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md).


## Linux publication qualification

The store-enabled Linux archive passes all 37 frozen CLI publication steps with
real local Worker/D1/R2 handlers and GNOME Keyring. Four source snapshots pass
two ARM input tests each; interrupted upload/listing acknowledgements, account
separation, website conflicts, withdrawal/republication and accepted signed
download/launch pass. Cleanup removes 30 temporary store objects while retaining
all 19 accepted objects, then logs out and stops the credential fixture. This is
x86-64 execution under ARM-host emulation, with an explicit public emulator test
key for the local download. It is not real GitHub/production-store acceptance.


`vm/test-sdk-store-publish.py` supports the frozen Linux SDK against the website's
isolated Worker/D1/R2 publication journey. It requires `--native-credentials`, a
native `--access-launcher`, an explicit D-Bus session and
`--isolated-secret-service` pointing to the new private GNOME fixture described
above. `--interpreter` is optional for native execution. The harness verifies the
bundle before and after the journey, requires the selected SDK/QEMU/firmware
identities to match, and keeps the temporary project registry under its new
output directory. It does not change HOME.

Credential preflight reads the private fixture directly and refuses an existing
record before login. The actual frozen commands then use their built-in Secret
Service backend. Final logout verifies empty credentials, retains then removes
fixture-specific project/operation records, and requests fixture shutdown. The
controller must verify the service's terminal cleanup report as well.

The website's `scripts/test-sdk-publication.ts` accepts an optional final JSON
configuration after the bundle argument, describing a trusted test driver:

```json
{
  "command": ["/absolute/path/to/publication-driver.sh"],
  "bundlePath": "/absolute/path/to/extracted/lefony-sdk"
}
```

This mode verifies the already extracted bundle through the Python harness and
keeps journey files under the requested output directory. On native Linux the
adapter can execute the supplied Python arguments while adding the required
fixture/access options:

```sh
#!/bin/sh
exec "$SDK_TEST_PYTHON" "$@" \
  --access-launcher "$SDK_ACCESS_LAUNCHER" \
  --isolated-secret-service "$SDK_SECRET_SERVICE"
```

Set these three environment variables to absolute paths before starting the
website controller. Pass the OS root, retained seed attempt, new output directory, matching SDK
source and bundle as the first five positional arguments after the script; add
the driver configuration last.
A driver on another host must map paths, preserve the controller's stdin/stdout
handshake, and make project files visible before forwarding each `READY_FOR_`
marker. It must copy the accepted package to the guest before forwarding
`cleaned`, retain the completed CLI report before exiting, and stop its owned
processes on errors. Network containment belongs to the test environment;
Landlock enforces frozen-command file access.

The local store signs with the explicitly public emulator fixture key. The
controller passes `--fixture-public-key` for accepted-download verification;
the Python harness verifies that it is exactly the repository's emulator public
key and adds it through the existing CLI option only if absent from the bundle's
trust directory. The bundled default keys and firmware remain unchanged. A
candidate containing only the selected store key correctly rejects this fixture
package without that explicit test public key.

This journey exercises real local publication handlers and signed ARM downloads.
It does not contact GitHub OAuth or a production store and does not establish
native clean-host, interactive prompt or physical USB acceptance.


## Real production account/publication on the working Mac

The source SDK now completes real GitHub authorization with native macOS Keychain,
separate-process account/owned-app reads, and SDK Counter 0.1.0 publication. Public
source/media match the submitted bytes; the unchanged store-signed package verifies
with the existing public key and launches in the matching store-enabled VM. The
public source also rebuilds to the exact unsigned package and passes its normal
key/touch input replay. See the [SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md)
for artifact hashes, deployment/inventory evidence and retained reports.

This result uses the existing development Mac, source Python tools and an explicitly
selected public PEM/runtime. It does not qualify a clean machine, the older public
macOS bundle, a new Windows bundle or native Linux. The SDK session remains in
Keychain for continued authorized work; no token is saved in project/evidence files.
