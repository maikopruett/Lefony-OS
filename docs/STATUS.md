# Development status

Lefony targets the **HP Prime G2** (i.MX6ULL). It is a native, bare-metal Upsilon
port, not a Linux desktop. Prime G1 and stock NumWorks hardware are not targets
of these build scripts.

## Firmware and applications

Development release [`1.0.0+1790319519`](https://github.com/maikopruett/Lefony-OS/releases/tag/build-20260925-1790319519)
adds Maiko Pruett (`@maikopruett`) first in Settings → About → Contributors.
The name uses Lefony Light's green accent; the handle retains the common
secondary-text color. Physical and VM compilation completed; tests were skipped
at the user's request. The signed package and uploaded assets were verified,
and the website's live manifest selected the new version. No calculator was
flashed. Build/publication records are under ignored
`build/contributors-release-20260925/`.

Development release [`1.0.0+1790315562`](UI-STARTUP-RELEASE-20260925.md) publishes
the installed-app launch optimization and touch-only Home highlight suppression.
Both target builds, 1,981 host tests, emulator regressions, signed package checks
and live website release discovery passed. Hardware timing/touch qualification
remains open; no calculator was flashed for this release.

The [one-shot U-Boot recovery implementation](UBOOT-ONESHOT-RECOVERY.md) replaces
the unsuccessful native-to-ROM handoffs. Settings → About → Enter recovery mode
confirms the restart and explains rear RESET or the three-minute timeout.
The native firmware writes a one-use SNVS request; U-Boot consumes it before
starting its own SDP endpoint (`cafe:5053`). The enumeration and transfer phases
share one 180-second window, followed by normal Lefony startup.

The failed ROM-entry stubs, SRC-override probes, ROM-reading endpoint, timeout
reset experiment and inactive launcher recovery app have been removed. The
ordinary watchdog reset, the successful SNVS initialization, RAM U-Boot migration,
and legitimate hardware ROM recovery/emulator tests remain.
[Earlier investigation notes](FULL-INSTALL-RECOVERY-20260924.md) are historical.
The website now supports both ROM and U-Boot SDP and an explicit protocol-2
bootloader/OS/DTB install. The release workflow uses the pinned one-shot bootloader
for subsequent packages. See the recovery record for exact validation limits.

Candidate `1.0.0+1790287024` adds a white app-install/update progress screen
that dismisses automatically, plus long-press dragging on the Apps grid.
Ordering is saved by stable app identity in the existing app filesystem and
survives a cold emulator boot. Physical and VM builds, storage interruption
checks and normal Goodix/USB integration tests pass; physical input and
power-loss qualification remain open. See the
[installation and Home ordering record](APP-INSTALL-AND-HOME-ORDER.md).

The local Home feedback follow-up hides app-label highlighting during touch
use, including scroll release and cancellation, and restores it for keypad
navigation. Both targets compile and normal KPP/Goodix screenshot, drag, launch
and cold-order checks pass. It is not installed or published; qualification is
recorded in the same [Home record](APP-INSTALL-AND-HOME-ORDER.md#touch-selection-feedback--local-follow-up).

The published storage-speed release `1.0.0+1790277950` has physical Prime G2 measurements:
Doom installs in 105.6 s versus 735.1 s, the 1 MiB file test takes 44.8 s
versus 221.8 s, and the native OS writer finishes byte verification in 4.9 s
versus 21.7 s. Both firmware builds, VM fault/protocol checks and a
byte-identical VM source rebuild passed. The installed firmware rebooted to
the expected version. The SDK and website release retains verified downloads
and improves installation progress. See the [release record](STORAGE-SPEED-RELEASE-20260924.md)
and [measurement plan](FAST-STORAGE-PLAN.md) for scope, evidence and limitations.

Physical native boot, display and keyboard have bring-up evidence in the
hardware notes. Calculator touch history and Functions touch use the normal
Goodix report/event path. Functions supports tapping tabs and controls,
one-finger graph panning, and two-finger pinch zoom. The graph's on-screen OK
button is removed; its bottom banner and physical OK key still open options.
Gestures cancel across modal/tab transitions and recover after contact loss.

The emulator target includes UART/QTest controls that are compiled out of the
physical target. Automated UI checks establish behavior in the model; graph
feel, contact tracking and responsiveness on the physical touchscreen still
need hands-on acceptance for each release candidate.

Drivers include display presentation, brightness, keypad, touch, timers, PMIC,
USB and storage integration. Some hardware models remain provisional. Detailed
notes under `hardware/prime_g2/` record observations and failures at particular
revisions; historical success does not qualify every later build. Do not infer
physical power-loss safety or battery calibration from an emulator pass.

Built-in calculator application persistence remains RAM-only on physical hardware; VM persistence uses atomic
SD-backed slots. Saving an expression in the UI is not yet a promise that it
will survive a physical power cycle.

## Native SDK preview

The local installed-app launch candidate reuses the executable loader's
authenticated manifest, removing a duplicate signature check and two repeated
package hashes per launch. Both firmware targets compile; signed-package
rejection, saved-data/upgrade and OS smoke regressions pass in the emulator.
Every launch still verifies the installed package. This candidate has not been
installed on hardware or published; see the
[launch performance record](APP-LAUNCH-PERFORMANCE.md) for measurements and scope.

The published Doom startup fix (`1.0.0+1790281237`, app 0.2.3) is installed on the
maintainer’s Prime G2 with firmware/package readback and retained-data checks.
It caches verified snapshot bytes and removes unnecessary cached-I/O yields.
Cold emulator startup to first game pixels measures 2.2–2.5 seconds; observed
physical launches measure 15.114–15.229 seconds, with user confirmation that the game
appeared quickly. This improves the minutes-long wait but is not instantaneous.
The website discovers the new OS release; Doom 0.2.3 is available in the store.
See the [Doom startup qualification record](DOOM-STARTUP-PERFORMANCE.md).

[Doom 0.2.3](https://lefony.com/#apps/doom-proof) is published through the
updated source terminal SDK under the maintainer's profile. Freedoom Phase 1
is included in the complete download and installed automatically by the website;
no separate WAD download or import is needed. Fresh installation, upgrades,
gameplay/save/cold-reload checks and an exact source rebuild pass in the ARM
emulator. Public package/data signatures and hashes verify. The old frozen SDK
cannot install the new `.lfbundle`; use browser installation or the updated
source CLI. Physical startup has the limited measurements above; full hardware
gameplay/storage qualification remains open. See the
[Doom release record](DOOM-STORE-RELEASE.md).

The public macOS ARM64 and Linux x86-64 SDK bundles now include the browser
emulator with all 50 clickable Prime keys below a larger, zoomable touchscreen.
Frozen CLI tests pass normal KPP/Goodix input and saved/cold Notebook behavior.
Both archives, matching source groups and the standalone SDK source kit passed
full R2 checksum verification. Public binary/source-kit downloads and all
catalogue routes also verify. The public installer selects
these refreshed candidates. See the [browser emulator release record](SDK-EMULATOR-RELEASE.md)
for exact hashes, commands, cleanup receipts and limits, and the
[macOS trial guide](SDK-MACOS-TRIAL.md) for the hands-on workflow.

Current trials are scoped to maintainer macOS feedback. Independent feedback,
clean hosts, Developer ID/notarization, native Linux/Windows and physical
qualification remain open. Windows source inputs are refreshed locally, but a
complete native Windows executable remains unavailable.

The following paragraphs retain earlier candidate qualification evidence; a
historical pass applies to the exact artifact recorded in the SDK ledger.

The current Linux x86-64 packager completes with the store-enabled VM, exact
firmware/project-source gates, launcher library-path correction, companion
shutdown handling and the full QEMU build containing the EP0 stall fix. Its
160-ELF audit binds 159 native and 1,101 target inputs. Three matching source
groups verify 4,287 payload files plus manifests; all 4,399 prepared VM source
members retain byte-identical rebuild evidence.

Fresh archive extractions pass 59 minimal-Ubuntu commands, all eight templates,
warm/cold starts, workspace recovery, private signing and reviewed Notebook/UI
Gallery previews. The unchanged published Surface 3D package launches twice
with the bundled default firmware. GDB/CMake, all eleven isolated frozen
companion cases and the restrictive doctor/negative controls pass. All 5,510
listed files remain unchanged; the archive also verifies its checksum file and
13 symlinks. These are x86-64 tools under explicit ARM-host emulation. Native
desktops, credential stores, physical USB, Windows distribution, upstream
rebuilds and complete release qualification remain open. Exact artifacts and
retained history are in the [SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).

The same Linux archive now passes 20 frozen account CLI checks with real GNOME
Keyring Secret Service: login, account/app lookup, origin isolation, replacement,
revocation, logout, missing-bus failure, lock/unlock and daemon-restart persistence.
The isolated keyring's encrypted files and session survive restart unchanged;
no plaintext test tokens are present, and final cleanup removes credentials and
fixture processes/directories. These are synthetic HTTPS accounts under
emulation, not interactive desktop, native clean-host or real OAuth acceptance.

The Linux archive also passes all 37 frozen publication CLI steps against the
actual local Worker/D1/R2 handlers: four tested source snapshots, upload recovery,
listing conflicts/merges, withdrawal/republication, accepted-artifact retention,
and exact signed download/ARM launch. An explicit public emulator test key is
used for that fixture download; default bundle trust stays unchanged. Logout,
private registry cleanup and credential-service shutdown pass. Real production publication, native clean-host and physical acceptance remain
separate from that local fixture.

Production migrations through 0010 and the matching website Worker are now live.
A private database export passes both SQLite and actual Wrangler/D1 restore and
migration checks, preserving every original row and column. Existing Surface 3D
downloads remain byte-identical. Real GitHub login, macOS Keychain storage and
separate-process source-SDK account/owned-app reads pass. Initial production
namespace and owner inventory has passed and submissions are enabled. Both
legacy deletion gates remain disabled. This does not qualify older SDK downloads or
clean native hosts. A separate SDK Counter development app now passes real
production publication, exact public artifact download, existing-key signature
verification, identical source rebuild/input tests and signed ARM launch.
Its public listing and retained hashes are recorded in the SDK ledger.

Windows compiler, GDB 17.2, Prime QEMU 11.1.1/r70, libusb and OpenSSL cross-build
components now have retained archives and corresponding sources. QEMU's archive
passes a 43-PE dependency audit and an independent extraction check. Windows
packaging also retains OpenSSL's configuration/providers/engines and computes
their paths from the relocated bundle. A separate Windows Python input archive
retains 14 reviewed wheels, their sources and 17 embedded-library/build archives;
installed wheel byte checks now gate packaging. The full CPython runtime and
SBOM-referenced sources/notices are retained, with installed and frozen runtime
byte checks. QEMU now keeps its DLLs beside its executable, avoiding a real
libffi collision with CPython. A 22-component source assembly now checks 1,702
installed tool inputs and 139 newlib bundle files; an offline layout passes a 119-PE dependency audit and
source correspondence for 627 files. A fresh GCC 16.2.0 newlib build reproduces
all 139 selected files. Windows project gates bind public SDK/recipe sources,
prepared QEMU and the retained byte-identical VM firmware rebuild to their
selected binary inputs. The refreshed Windows project-source set selects the same store-enabled VM as
the Linux archive. Its compiled store-key checks and 4,399-file source/rebuild
inventory pass; the older VM and mixed old/new source selection are rejected.
All three source archives verify, with 351 current SDK/recipe inputs and 139
newlib files checked. The complete frozen Windows SDK, native
execution, credential stores and debugging remain open. The
[host build instructions](../sdk/HOSTS.md#windows-packaging-inputs-and-checks)
describe the remaining inputs and qualification scope.

A live Surface 3D download exposed missing compiled store keys in earlier
SDK VM images. Desktop packaging now rejects mismatched SDK/VM public keys.
The new complete Linux distribution includes the reproducible configured VM
and passes unchanged store-signed app launches without a firmware override.
Other retained desktop artifacts keep their original hashes and qualification;
this does not qualify a real OAuth/publication journey or physical installation.

Linux and Windows binary packaging require explicit project sources and retained
matching VM rebuild evidence. The current Linux archive binds QEMU's original
input and relocated output through its native source audit, verifies all 4,399
prepared firmware members and includes both rebuild report and log in the
project-source download. Native host execution remains separately unqualified.

Read-only physical USB preparation now includes two identical captures of the
older installed OS capsule, with no reported corrected bits and unchanged
updater state. The installer also rejects unqualified U-Boot selections before
preparing installation. This is backup/preflight evidence; current SDK firmware,
full NAND/app-data recovery and physical acceptance remain unqualified. See the
[capture command and scope](LEFONY-INSTALLER.md#capture-the-running-os-without-entering-recovery).

The local preview candidate now waits for a completed screen that can accept
input. Debug-layout schema 2 distinguishes Notebook's loading screen from its
interactive screen; a bounded debugger watchpoint prevents replay input from
being lost during startup. The newly frozen Linux CLI passes populated-data,
source-edit, cold-reopen, unfinished-layout timeout and recovery phases, retaining
exact document/attachment bytes and excluding them from source uploads. A separate
13-command matrix passes fresh Notebook/Gallery creation, packaging, startup,
replay, source export and debug preview, plus the expected incomplete-component
diagnostic. Native
macOS source preview and legacy-layout capture also pass. These are component
and source checks, with complete host bundles and physical qualification still
open; see the [SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).

The Linux installed-app connection failure is traced to the guest watchdog
expiring during RSA verification. Matching candidate firmware now checks health
after bounded verification work, without arming the watchdog during startup or
changing its timeout or signature policy. The relocated frozen x86-64 CLI passes
installed C startup, saved-data relaunch and source export with that firmware;
both targets compile and deliberate watchdog hang resets still pass. A separate
emulated process crash prevented the earlier fresh-project matrix from completing.
Later fresh C and Notebook build/startup/input-replay/source journeys pass, as does
Link Gallery build/startup/source export. Notebook debug compilation and UI
Gallery project creation failed under the original Linux emulation environment.
An explicit 480-case old/new interpreter comparison reproduces a crash only with
the older interpreter; its global registration remains unchanged. The later
preview checks above use a separately invoked recursive interpreter and do not
qualify native Linux or establish a specific upstream crash fix. The initial
Ubuntu/Python source collectors retained 13 inventoried system source
packages and 18 Python packages, including nested vendor notices. A separate
native-wheel source lock now maps the actual 21 Pillow/CFFI/cryptography files
to 56 verified source archives. Packaging checks reject missing sources or
unreviewed wheel inputs; the check passes against the retained Linux freeze.
Complete compiler/debugger/emulator dependency and source assembly, upstream
wheel rebuilds and native/clean-host qualification remain open. Exact attempts
are in the [SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).

The Linux x86-64 compiler, GDB and custom QEMU components now have completed
cross builds. Together they pass a source breakpoint/argument/return-value test
against an ARM guest. The current SDK source runner also boots the firmware and
unchanged Counter/Surface 3D packages, with normal key input, changed frames and
Home exit in both headless and SDL dummy-display modes. The x86-64 tools ran
under emulation with native ARM64 Python. Complete bundles, graphical desktop
operation and native/clean-host qualification remain open.
Exact inputs and retained artifacts are in the [SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).

The current local macOS replay candidate passes 12 frozen CLI commands covering
Ctrl-C, hard process loss, cold document preservation and interrupted publication
preparation. Incomplete replays replace older passes; cancelled preparation cannot
produce a ready submission. Native apps now return Shift+Home/Shift+Apps to OS
Settings, including key/archive/channel approval screens. Normal-input and cold
storage regressions pass, both firmware targets compile, and the full host suite
passes 1,441 tests with two expected private-fixture skips. Exact bundles and
remaining qualification are in the [SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).

The newer local macOS diagnostics bundle passes 18 actual CLI commands for
restored-workspace launches, QEMU startup failure reporting and Notebook preview
recovery. It preserves bounded stderr/UART logs and replaces stale startup passes.
Notebook retains its saved document and frame through emulator/validation errors,
then reopens successfully without attributing a new error to an old emulator exit.
The earlier spontaneous control-stream exit remains unexplained. Exact artifacts
and further qualification are in the [SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).
The same bundle passes all eight relocated offline templates, GDB/CMake and
Notebook/Gallery previews. Final host validation passes 1,419 tests with two
expected private-fixture skips; the extracted source kit also builds and executes
startup failure/recovery on the ARM VM.

The current macOS storage bundle passes 91 actual frozen CLI steps across eight
ARM sessions, including large-file/private-data round trips, cancellation during
USB transfers, accepted commits, archive repair, upgrade rollback and cold data
preservation. Ctrl-C now lets the active transfer finish and waits for firmware
to consume a pending chunk before cancellation. The final host suite passes
1,408 tests with two expected private-fixture skips. Eight relocated offline
templates, GDB/CMake, workspace restore and Notebook editing/save/cold previews
also pass. Exact candidate hashes and retained failed attempts are in the
[SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md). Native host, production-service and
physical qualification remain open.

The selected C file profile now passes four additional buffered-stream workflows:
edits across storage chunks, append through durable saves, readers retained across
replacement/rename, and seek gaps with pushback/position restoration. Debug/release
and cold-readback checks pass on the current VM and retained media-I/O candidate
(32 ARM phases). This adds conformance evidence without changing SDK or firmware
code; broader runtime and physical qualification remain in the
[SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).

The current macOS SDK bundle now passes a 37-step publication journey against
the actual local website handlers, with frozen CLI execution and native Keychain.
It covers sign-in, interrupted uploads, updates, account separation, website/SDK
listing edits, withdrawal, republication and launch of the exact signed store
download. The source-mode regression passes 28 steps. Synthetic accounts, local
TLS/D1/R2 and the public emulator signing fixture keep this separate from real
GitHub OAuth, production publishing and physical installation. Exact evidence
and cleanup results are in the [SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).

A fresh local macOS ARM64 desktop bundle includes the current text-field and
HTTPS companion fixes. Eight relocated offline template journeys pass, including
bundled GDB, external CMake, source export and ARM preview. Frozen Notebook touch
editing, exact saved/exported bytes and cold preview reopening pass; eleven
frozen companion ARM/model-USB cases include late fragments after ERROR/DONE
and subsequent requests in the same paired session. The source kit reproduces
and builds the same Notebook package. See the [SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md)
for the exact candidate and host, production-service and physical limitations.
This candidate has not been published.

The HTTPS companion now preserves paired sessions when trailing request metadata
or cancellation arrives after DONE/ERROR was sent. It drains only the most
recently completed request's well-formed fragments, without another network
operation; malformed/foreign/reused messages still fail. Link Gallery passes
normal-consent ARM boundary checks, same-session refresh and cold cache readback.
Existing HTTPS and full-quota Gallery regressions also pass. Exact candidates
and qualification limits are recorded in the [SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).
The local macOS bundle above includes this fix; published downloads and the
remaining native host matrix require separate qualification.

Notebook 0.6.1 keeps its editor open when the expression field is tapped.
The shared field model adds touch caret placement, selection, retained horizontal
scrolling and cancellation; UI Gallery 0.1.1 exercises accented and 1023-byte
text. Normal Goodix/keypad debug/release journeys, exact Notebook saves/exports
and cold package readback pass on the ARM VM. See the
[SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md) for the exact candidate, regression
results and remaining host, UI and physical qualification.

Doom 0.2.1 now passes four selected interrupted compatible-update cases
(17 ARM phases) plus three quick-slot sessions. Cold inspection, rollback,
retired-version rejection, higher-version retry and ordinary acceptance preserve
the tested game data. Quick-save selection/overwrite/cancellation and cold
named-slot recovery preserve both original saves and settings. Five complete
WAD exports match the asset pin. The update fixtures change manifest versions
only; they do not qualify a changed engine or data format. Exact results and
retained harness failures are in the [SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).
Broader SDK/native-host and physical qualification remain open.

Doom 0.2.1 now passes selected abrupt-stop save-recovery checks on the ARM VM:
old saves survive pre-commit stops, and the new save survives a stop after the
commit rename but before the app receives completion. Public readback replaces
reinstallation during cold boots; save retries, exact restored game state,
unchanged settings and the complete pinned WAD pass. Nine matrix phases plus
three stronger reference-read phases are recorded in the
[SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md). These are synthetic process-loss
checks, not physical power-loss or torn-NAND qualification. The later checkpoint
above adds selected compatible-update cuts; broader SDK release acceptance remains open.

The macOS desktop packager now checks the selected Pillow wheel's installed
inputs and records the actual 13 native libraries plus six extension modules
from PyInstaller. The source collector retains 21 source archives, including
static AVIF codecs, the TIFF patch and build recipes, with original wheel notices
and its dependency inventory. The binaries match the preceding tested candidate;
source collection no longer confuses these wheel inputs with Homebrew libraries.
The original wheel build has not been reproduced. See the [host guide](../sdk/HOSTS.md)
and SDK ledger for the exact candidate and remaining release qualification.

SDK metadata, preview HTML and debug scripts now use explicit UTF-8, and
redirected CLI output preserves Unicode paths even under an ASCII text locale.
The actual ARM Notebook edit/cold-reopen/failing-build/repair workflow passes
with Python UTF-8 mode disabled, preserving the saved document and stale frame
through a failed build. See [project text handling](../sdk/PROJECTS.md#host-text-encoding)
and the SDK ledger for evidence and remaining native-host qualification.

The desktop packager now includes a native Windows x86-64 candidate path with
explicit DLL collection, PE import/delay-import checks, Credential Manager
selection and ZIP output. The GDB recipe also has an unexecuted MinGW cross-build
route. This implementation does not establish a complete Windows download:
native tool/source assembly, Windows execution, USB and clean-host qualification
remain open. See the [host guide](../sdk/HOSTS.md) and SDK ledger for exact
validation and the macOS regression candidate.

The Doom 0.2.1 recipe fixes recursive exit-callback errors and preserves virtual
Fire/Use/strafe bindings when loading saved configuration. The interruption
harness now compares serialized and restored state before gameplay resumes;
its exact candidate and subsequent regression evidence are recorded in the SDK
ledger. These changes do not alter firmware or the public SDK API.

The preceding Doom 0.2.0 candidate added configuration loading/saving, direct game
save replacements, failed-output discard and resource errors. Its
functional candidate passes 19 ARM quota, settings, recovery, allocation and
gameplay journeys; six error/recovery cases also pass on the final shorter-warning
build. The source kit builds Doom with bundled newlib and matches the checkout.
Normal Home interruption after staged output and during pre-commit verification
also preserves the old save/settings through cold restart, with a successful retry.
These checks use public APIs and synthetic storage. Wider interruption/control
coverage, physical timing and stable SDK qualification remain open; exact
candidates and the historical configuration-I/O gap are recorded in the SDK ledger.

The SDK now has opt-in [`test --measure-resources`](../sdk/TESTING.md#observing-app-resources)
for package-bound ARM stack observations, reservations and execution counters.
The original stack candidate passed ten diagnostic/lifecycle cases and instrumented
journeys for all four proving apps. Measurements survive faults and relaunches
and exclude other packages; default execution retains zero-initialized stack
memory. These are observed extents, not worst-case stack requirements.
The later explicit `LEFONY_PROFILE_HEAP=1` newlib build adds allocated-chunk and
arena measurements with matching VM firmware. Ten allocator/lifecycle diagnostic
cases and nine existing stack regressions pass. The hooks include allocator
padding/metadata, exclude custom suballocator usage and static buffers, and add
scanning overhead. Ordinary builds leave them off; see
[heap diagnostics](../sdk/TESTING.md#observing-newlib-allocations) and the SDK
ledger for exact candidates, proving-app evidence and remaining qualification.
The controls compile only into the VM; physical and release qualification remain
separate. Exact artifacts and results are in the SDK implementation ledger.

The local store backend now reserves account/global artifact capacity before
writing files, protects accepted release/listing history in the publication
transaction, and reclaims abandoned stages and late upload writes. The actual
CLI/ARM publication journey passes with two production-handler cleanup runs:
30 temporary objects are removed while 19 accepted artifacts remain unchanged.
The later website legacy-storage candidate also inventories older committed
artifacts, charges shared ownership and adds separately enabled source/package
cleanup. Its local suite passes 558 tests and the CLI publication journey passes
28 steps. Initial inventory/owner accounting is incremental, and unrelated bucket
contents need separate headroom. Production migration, writer shutdown and
workload qualification remain open; the website's
`docs/STORE-LEGACY-STORAGE-VALIDATION.md` records that later checkpoint.

The latest store-client candidate moves DNS, native certificate verification and
HTTP transfers into disposable workers with a 20-second total request deadline.
Seven frozen macOS network cases pass, including slow responses, stalled TLS,
Ctrl-C, redirects and truncated JSON; sixteen native-Keychain account steps also
pass. Tests use controlled local services, and observed workers stop after every
command. The SDK ledger records the exact candidate and broader release gaps.

The current macOS desktop SDK uses native certificate trust for the account
client and HTTPS companion. Its relocated frozen candidate passes eight TLS
checks with checkout/Homebrew access denied, eight offline template journeys
and 16 account steps using a local TLS service and real macOS Keychain. The
temporary credentials are removed after qualification. This is local host
evidence, not real GitHub/production-store, complete companion, clean Windows/Linux
or physical qualification. Exact hashes and the remaining native dependency-source
audit are recorded in the SDK implementation ledger.

The later frozen companion candidate passes ten signed ARM/model-USB journeys
covering streamed uploads/downloads, denied origins, TLS failures, timeout,
cancellation, truncated data and host disconnect. Three independent disconnect
repeats pass after fixing Ctrl-C cleanup at USB transaction boundaries. Prior
cache bytes are checked after errors and worker processes stop. The explicit
emulator transport has no physical USB fallback; physical USB and native host
release qualification remain open.

The local [API 12 file-abort candidate](../sdk/FILES.md#explicit-writer-cancellation)
adds explicit writer discard and the C++ `FileWriter` adapter. Notebook 0.6 and
Link Gallery 0.2 stage direct replacements, crediting the old file's length
against the logical quota. Both firmware targets compile; basic signed ARM
abort/cold/fallback and full-quota application cases pass. Notebook also passes
24 document journeys and seven package-upgrade/recovery cases; Gallery passes
eight debug/release journeys with 13 matching frames. Broader resource/native-host
and physical qualification remain open. Existing downloads do not contain this
extension; exact candidates are recorded in the SDK ledger.

The local [whole-app archive candidate](NATIVE-APP-ARCHIVES.md) now has a portable
host validator, streamed export/restore engines, exclusive USB sessions and
[SDK commands](../sdk/ARCHIVES.md). Production-filesystem and host tests cover
interruption/cancellation, signatures, atomic output and damaged-data repair.
Eight signed ARM/USB journeys pass; exact evidence is in the SDK ledger. A new
explicit consent candidate supports restoring a pending pair signed by different
developer keys onto a fresh calculator, with complete archive verification and
OS-owned approval before commit. Its evidence is recorded separately. An explicit
code-repair candidate now uses surviving canonical identity to restore the exact
original signed package when installed code is unreadable. Damaged/unreadable
canonical roots, complete host bundles and physical qualification remain open. Existing downloads do not
include these commands.

The local [FILE5 root-recovery candidate](NATIVE-APP-ROOT-RECOVERY.md) stores
complete app ownership, package/data pairs and version history in separate
payload and metadata copies. Both targets compile; 1,222 host tests and six ARM
SDK recovery cases pass. An unreadable payload can be backed up and explicitly
restored without losing retained pairs or bypassing the version high-water mark.
`archive info` reports negotiated root protection. Healthy old roots migrate on
their next save/restore; matching firmware is required. Both copies lost,
unreadable filesystem metadata, complete desktop bundles and physical durability
remain unqualified. Exact candidates and further regressions are in the ledger.

The local [ARM preview data workflow](../sdk/UI.md) retains committed files and
private bytes between source edits, supports nested fixtures, and provides reset
and disposable modes. Notebook accepts package upgrades only after reading
the document; malformed data retains the recovery pair. Exact checks and limits
belong in the SDK ledger; native bundles and physical qualification remain open.

The local [private-install candidate](../sdk/KEYS.md) implements durable developer
public-key records, OS-owned enrollment/revocation consent, USB/SDK commands and
catalog/export-versus-execution trust. Explicit per-app lost-key replacement
retains saved data and signer ownership. Both targets compile; exact host/ARM
validation is recorded in the SDK ledger. Unused revoked keys can now be removed
without discarding keys needed by installed recovery pairs. A verified host
backup and OS approval can rebuild a readable corrupt registry around one
explicit public key, preserving installed apps and data. A separate partial-backup
candidate now repairs unreadable registry payloads with readable file metadata.
It preserves readable fragments, marks missing bytes and repeats the scan after
OS approval. Both targets compile, and an ARM CLI/consent/cold-Notebook journey
passes. Unreadable ownership roots or filesystem metadata, complete host bundles
and physical qualification remain open; exact evidence is in the SDK ledger.

A new local macOS bundle makes private key generation and package signing
available directly through `lefony-sdk`, using bundled OpenSSL. Its 36 frozen
CLI steps across six ARM sessions pass enrollment, cancellation, signed Notebook
installation, revocation, lost-key replacement, old-key removal and backed-up
readable-corrupt registry repair and partial-backup repair of unreadable payloads.
Changed or cleared read faults invalidate approval without modifying storage.
Cold launches preserve exact document/export
bytes, and independent root inspection confirms unchanged installed ownership
and data after registry repair. These use synthetic USB and normal OS keypad
consent with IP network, checkout and Homebrew access denied. Complete supported
hosts, unreadable ownership/filesystem metadata and physical qualification remain open.

The local [SDK account candidate](../sdk/ACCOUNTS.md) adds browser GitHub
authorization, expiring/revocable store sessions, owned-app listing/history and
local project links. A relocated source kit passes a two-account CLI/Worker/TLS
journey with controlled GitHub and browser fixtures. The local
[folder publication candidate](../sdk/PUBLISHING.md) adds offline
`publish --dry-run`, exact-package ARM tests, explicit `publish` and saved-attempt
status/resume/cancellation. The CLI and local Worker pass an isolated TLS/D1/R2
journey with SDK and website ARM-tested releases, lost acknowledgements, signed
downloads, stale revision rejection and listing pull/merge. Browser listing review
preserves form edits and reuses selected saved media. SDK withdrawal and metadata-only
listing revisions now have local implementations with saved operation receipts;
their current evidence is recorded in the SDK ledger. Real credential-store,
clean-host qualification and deployment remain open; existing downloads do not
contain this candidate.

The local [API 11 channel candidate](../sdk/CHANNEL.md) implements app-scoped
USB messages, OS-owned pairing and bounded session/queue lifetimes. Both targets
compile; signed ARM transport, consent, timeout and cleanup cases pass. A
USB/HTTPS bridge and `companion` command now pass signed ARM/local TLS journeys.
Link Gallery passes debug/release download, disconnect/reconnect, cancellation,
invalid-image preservation and cold-cache reopening. That checkpoint's host suite has
722 passes and two expected private-fixture skips. These are local candidates;
complete host bundles, broader resource qualification and physical acceptance
remain open. Exact reports are recorded in the SDK implementation ledger.

The local [API 10 system candidate](../sdk/SYSTEM.md) exposes clock/battery
validity, OS palette/locale/math preferences, temporary brightness and normal
Copy/Cut/Paste exchange. Both targets compile and signed ARM boundary/lifecycle
cases pass. Notebook 0.2 now integrates the OS palette, clipboard and saved
angle/format/digit choices, while old documents retain their original math
settings. Its exact evidence is in the SDK implementation ledger; physical
qualification and broader SDK acceptance remain open.

The local [C++ UI candidate](../sdk/UI.md) adds API 9 OS fonts, Notebook and
actual ARM source/layout preview. Its evidence is in the latest
[implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md); the earlier downloads
do not contain these changes. Full SDK 1.0 and physical qualification remain open.
Notebook 0.5 uses shared confirmation dialogs and pressed slider rendering,
building on 0.4's captured pixel scrolling, partially clipped rows and scrollbar.
The new UI Gallery exercises menus, disabled/cancelled actions, 1023-byte fields,
four OS fonts, dark themes and empty/loading states. The component checkpoint
passes 182 clipping frames and 116 debug/release frame comparisons, plus Notebook
and package-upgrade regressions. Exact evidence is in the SDK ledger. Broader
document resource/recovery coverage, native host bundles, supported-host latency
budgets and physical input acceptance remain open.

Notebook 0.6.2 now wraps its empty/recovery instructions so the complete export
and restore guidance is visible. UI Gallery 0.1.2 demonstrates wrapping, retained
blank lines and long words with the shared fonts and states. The paragraph
component passes sanitizer-backed layout tests, 210 ARM clipping frames and
52 Gallery frames; Notebook's 24 ARM regression phases also pass. Debug/release
pixels match. Exact candidates and current packaging evidence belong in the
SDK ledger; this is app-linked UI work, with unchanged firmware.

The current local preview candidate reduces a populated Notebook profile from
109.5 to 19.1 seconds with identical rendered pixels. It includes a USB completion
handoff fix with 12 passing deterministic status/data/reset cases, plus bounded
polling of active app transfers. Archive cleanup now avoids cancelling a finished
or different session. See the [preview measurement guide](../sdk/UI.md#measuring-preview-time)
and the SDK ledger for exact candidates and regression evidence. These changes
are absent from earlier downloads; supported-host latency budgets and physical
USB qualification remain open.

The local SDK maturity candidate adds normal-input replay tests, persistent
synthetic workspaces, GDB/source diagnostics, pinned incremental builds and
bounded app-side UI, math, matrix and graphics helpers. Forms/Tables and Graph
Explorer add normal-input reference replays. See [the capability inventory](NATIVE-APP-CAPABILITIES.md)
and [current evidence](NATIVE-APP-MATURITY-EVIDENCE.md). This is an early roadmap
implementation, not completion of the full SDK beta/1.0 plan.

The [native SDK](../sdk/README.md) builds C++ packages for an experimental
user-mode runtime with installed apps in the main menu on both targets. Physical
firmware requires signed ABI 1 apps and provisioned app storage. Drawing, bounded callbacks,
fault recovery, independent app signatures and source-based publication tooling
are implemented. A macOS desktop candidate and read-only website deployment
are available; see the [setup runbook](NATIVE-APP-SETUP.md). ABI 1, signed packages, paired app/data transactions and USB installation are
implemented. [Storage migration](NATIVE-APP-STORAGE.md) intentionally retires
part of the stock filesystem. OS-startup reservation needs no browser command or backup; the older SDK backup/migration command remains available. Physical migration,
restore, power-loss behavior and flash endurance still require qualification. See [SDK implementation status](NATIVE-APP-SDK-STATUS.md).

The current source replaces profile-1 fixed app banks with a shared littlefs
filesystem (storage profile/USB protocol 2). Existing apps migrate at OS startup;
the region remains 64 MiB, with roughly 60 MiB initially available after metadata
and update headroom. SDK and website support both protocol versions. This is a
local development candidate pending physical migration/power-loss qualification;
see [storage details](NATIVE-APP-STORAGE.md).

The working tree also integrates a [FILE3 document transaction engine](NATIVE-APP-DOCUMENT-TRANSACTIONS.md).
Converted apps save data without rewriting their package and retain compatible
pairs during upgrades. The [FILE4 file engine](NATIVE-APP-LARGE-FILES.md) adds
internal streaming and partial edits, including the pinned 28.8 MB WAD. Four
internal snapshot readers now preserve file contents while writes and collection
advance, with incremental chunk verification. The internal writer also grows
files without a declared size and supports append, seek/backpatch and zero-filled
gaps. The [API 2 file session](../sdk/FILES.md) now connects authenticated apps to
that engine, with bounded requests and owned handles. Real newlib stdio passes a
signed ARM streaming/backpatch/replacement and cold-output proof using the
public API 3 foreground candidate. The ordinary SDK now has an explicit
conventional startup/newlib profile; broader libc qualification and damaged-media
recovery remain unfinished; the ABI 1 byte
store retains its 64 KiB limit.

The selected [C library matrix](../sdk/C-LIBRARY.md) now passes 15 ordinary-main
ARM phases, including allocation failures, 64-bit/C99 formatting/scanning,
selected math, stream/descriptor errors, cold data and exit cleanup. The pinned
newlib build fixes its narrow `FILE` descriptor fields without recycling OS
handles; seeded emulator cases cross 32,767 and exercise values near `INT_MAX`.
Library and app objects must be rebuilt with matching headers. Existing compiled
apps retain the earlier behavior. The later
[library comparison](NATIVE-APP-C-LIBRARY-COMPARISON.md) selects newlib after
23 expanded ARM phases pass. Picolibc uses less code/static data but fails
stream errors, normal unclosed-stream cleanup and repeated global flushing
with both tested buffering configurations. Full profile qualification remains open.

The [API 3 foreground candidate](../sdk/FOREGROUND.md) now compiles into physical
and VM firmware. It explicitly negotiates resumable execution, a guarded heap,
yield/sleep/exit and copied RGB565 presentation. ARM cases pass for register
preservation, allocation, minimum sleep, Home and memory isolation. The
[implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md) records exact candidates
and validation. Existing SDK projects still use callbacks; project schema 2 can
select [conventional main startup and newlib](../sdk/C-RUNTIME.md). The library
selection is recorded in the comparison; physical input/timing remain
unfinished. No SDK 1.0 milestone has met all its exit criteria.

The ordinary main profile now passes a relocated bundled-runtime SDK journey,
main-entry GDB, saved-visit relaunch/cold persistence and mixed-language cleanup.
The existing [minigzip C tool](../sdk/ports/minigzip/README.md) now uses API 12
to discard failed output and commit verified direct replacements. Its nine
original ARM cases and 40 public-file workflow phases pass, including empty
files, full-quota replacement, rejected growth and retry, corrupt/truncated
input, real heap exhaustion, Home and cold reopening. Exact source rebuilds and
the relocated offline source kit pass. A later media matrix passes 23 ARM phases
for compression/decompression under modeled read faults and actual shared-volume
exhaustion, with preserved input/output, retry and cold reopening. Physical
testing, broader damaged-media recovery and full SDK qualification remain open.

The [API 4 input stream](../sdk/INPUT.md) now compiles on both targets and passes
ordinary C ARM checks for held/down/up chords, ordered touch, overflow during
sleep, Home and focus reset. Legacy input and scheduling regressions pass. This
extends the negotiated capability set without changing existing ABI 1 layouts.

The [Doom port](../sdk/ports/doom/README.md) now passes normal-input gameplay,
save/reload, cold saved-state restoration and clean exit in the ARM emulator.
Pending storage work advances without an artificial idle sleep while normal
input and UI timers continue. The [scoped app-side MIT alternative](NATIVE-APP-LINKED-LICENSE-REVIEW.md)
is approved and applied. The large WAD also has a completed public USB
import/export round trip in the SDK ledger. Full error/resource coverage,
source-distribution audit and physical qualification remain open.

The [API 5 live file sync](../sdk/FILES.md) candidate adds checked `fsync` after
`fflush`, preserving the open stream for further edits. Both targets compile;
installed ARM saves survive Home, fault and immediate exit followed by cold
reopen. Host fixtures cover snapshot readers, resumed writes, I/O failure and
44 simulated interruption points. Physical durability and broader damaged-media
recovery remain unfinished. Exact candidate hashes
and evidence are recorded in the implementation ledger.

The [API 6 directory and usage queries](../sdk/FILES.md#directory-listing-and-storage-usage)
add bounded listing with change detection, committed/staged app-data usage and
shared free-space reporting. Metadata inspection preserves legacy storage.
Both targets compile, and signed ARM checks cover paging, cold reopening,
buffer ownership, capability denial and older-firmware fallback. Per-file USB
exchange and the API 7 per-app quota addition have separate checkpoints below.

The [API 7 quota candidate](../sdk/FILES.md#per-app-quota-policy) enforces 32 MiB
of current mutable data per app, including private bytes, and reports committed
versus staged usage and remaining logical allowance. Existing oversized roots
remain readable/editable without growth; shrinking commits reduce their ceiling.
The independent shared-space admission and maintenance reserve still apply.
An ARM recovery test also exposed and fixed a stale writer-failure flag affecting
independent snapshot readers. Current validation is recorded in the SDK ledger;
broader damaged-media recovery and physical qualification remain open.

The [SDK file exchange candidate](../sdk/FILE-EXCHANGE.md) now provides explicit
per-file USB import/export, directory listing and app-data inspection. Imports
validate identity, schema, root generation, quota and the complete content hash
before commit. Exports publish a local file only after size/hash verification.
Cancellation, timeout and USB reset release uncommitted sessions. Whole-app
archives and the large-asset round trip have separate checkpoints in the SDK
ledger. Broader damaged-media recovery and physical durability remain open;
consult that ledger for exact candidates and evidence.

The [API 8 private-data controller](../sdk/DATA.md) is implemented alongside
named files. It snapshots live private bytes, exposes explicit migration and
upgrade acceptance, and retains the previous compatible package/data pair until
acceptance. Both targets compile; final API 8 ARM cases cover normal exit, Home,
fault, cold reopen, migration across an update and older-firmware fallback.
Explicit [host private-data backup/restore and retained-pair rollback](../sdk/DATA-RECOVERY.md)
are implemented in the new hello-128 recovery extension; the SDK ledger records
its validation separately. The separate whole-app archive candidate now includes
damaged-data repair with intact signed code; broader recovery remains unfinished.
This is a local candidate, not physical qualification.

## Installer and recovery

The installer supports detection, build selection/history, backup and readback,
RAM/recovery workflows and signed updates. A/B installation requires a
provisioned and qualified layout. A normal update rejects an unprovisioned
layout instead of creating one. Recovery assets and private backups are
maintainer/device-specific and are not shipped in this repository.

Building the physical target creates a local signing identity if none was
supplied. Keep it under ignored `build/lefony-update-signing/`, or set
`LEFONY_UPDATE_KEY_DIR` / `LEFONY_UPDATE_PUBLIC_KEY`. Existing installed devices
must retain their matching trust root. Emulator fixture keys are deliberately
public and must never sign a physical release.

## Public and private tests

`make test` runs host tests without a calculator, firmware dump or network
access. `make firmware`, `make firmware-vm`, and the direct emulator/touch
workflow use only publicly fetched upstream sources and this repository.

Two optional device-tree tests require privately supplied files:

```sh
LEFONY_PRIVATE_HARDWARE_DIR=/path/to/private/reference make test
```

The directory must contain `imx6ull-14x14-prime.dtb` and its matching `.dts`.
Without the environment variable, these tests report explicit skips. Do not
copy the files into the public repository.

Stock boot, retained-DMA replay and exact NAND research under `vm/` require
private local captures and sometimes a qualified U-Boot/capsule. Consult each
script's inputs, including `PRIME_G2_EXACT_NAND` and
`PRIME_G2_CURRENT_CAPSULE`. Retained-DMA replay also requires
`LEFONY_PRIVATE_ROM_DMA_CAPTURE` pointing to an original private JSON capture. They are not part of default public CI.
The public `rom-dma-buffers-20260907.json` is an analyzer fixture whose payload
words are synthetic zeroes; it is not evidence of captured firmware content.

Full boot-media/storage/fault suites additionally use Docker, U-Boot and
`qemu-img`/`qemu-io`. See [the emulator guide](../vm/README.md).

Installed app menu icons now have a signed store-to-calculator attachment path.
The icon is bound to the exact signed package and stored atomically outside app
private data. Existing app versions can receive their icon without reinstalling.
See [icon format](NATIVE-APP-PACKAGE-FORMAT.md#signed-calculator-icon-attachment).
Icon support requires matching firmware and website versions; physical icon
behavior is not yet qualified.
