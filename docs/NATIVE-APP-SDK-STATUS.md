# Native SDK implementation status

The native SDK, signed ABI 1 runtime, persistent app storage, USB app installer
and public website are implemented as a **development candidate**. SDK source
stays with the OS; the website owns accounts, listings, publication and ratings.
See the [setup runbook](NATIVE-APP-SETUP.md) for the remaining account/host setup.
This does not mark every future milestone in the [full plan](NATIVE-APP-SDK-PLAN.md)
complete or qualify migration on physical hardware.

The [SDK 1.0 plan](NATIVE-APP-SDK-1.0-PLAN.md) governs current acceptance,
including the account/folder publishing requirements retained from the
[maturity roadmap](NATIVE-APP-SDK-MATURITY-PLAN.md).
The current source includes conventional C/C++ execution, newlib and streamed
files, document/connected apps, C++ controls and actual ARM preview, system/math
helpers, USB/HTTPS, SDK GitHub accounts and folder publication, private developer
keys and whole-app archives. These are local candidates with different evidence
from the earlier downloadable `0.2.0-dev` bundles. The
[capability matrix](NATIVE-APP-CAPABILITIES.md) describes current limits; the
[SDK 1.0 ledger](NATIVE-APP-SDK-1.0-PROGRESS.md) binds each validation checkpoint
to its exact sources and artifacts. No full 1.0 milestone is qualified.

The current C runtime fixes truncation of file handles above 32,767 by rebuilding
newlib with full-width `FILE` fields, and explicitly enables 64-bit/C99 formatted
I/O. The [selected library matrix](../sdk/C-LIBRARY.md) has 15 passing source/debug
and 15 bundled-sysroot/optimized ARM phases,
including real heap exhaustion, formatting/scanning, math errors, cold files,
exit handling and synthetic descriptor boundaries near `INT_MAX`. Matching
headers and library/app objects are required; older sysroots fail validation.
The earlier SDK reproduces the descriptor failure. Broader library, host and
physical qualification remain separate work.

The corresponding macOS bundle passes all eight relocated offline template
journeys, including C-main debugging and Notebook/UI Gallery preview. The full
host suite passes 1,161 tests with two expected private-fixture skips. These
results qualify the local candidate inputs recorded in the ledger; public
downloads, clean machines and complete native dependency sources remain separate.

## Implemented

| Area | Available behavior |
| --- | --- |
| SDK | Pinned GCC, external C11/C++17 projects, ordinary `main`/newlib or callbacks, configured source trees/CMake, reproducible incremental builds, locks, normal-input tests, GDB and source exchange |
| ABI 1 | Frozen package/service/event contract, drawing, keypad/touch/timers, bounded private data calls, normal start/close lifecycle |
| Runtime | ARM user mode, RX code, guarded non-executable data/stack/heap, copied graphics/input, validated pointers, resumable foreground execution and OS-owned Home/fault cleanup; installed-app tiles |
| Signing | Separate RSA-2048 app identity, LFAPP1 signatures checked by host, guest and website, bounded public key ring and retired-key rejection |
| Storage | Shared littlefs profile 2 at 432–496 MiB; streamed named files, snapshot readers, live sync, explicit writer abort, directory/usage queries, per-app quotas, USB import/export, checkpoints/migrations, retained-pair rollback and signed whole-app archives |
| UI and services | C++ controls/fonts/layout, menus/dialogs, scrolling and long fields, retained-data ARM preview and source inspection; selected expression/matrix/plot helpers, palette/preferences, valid clock/battery queries, clipboard and temporary brightness |
| Connected apps | App-scoped USB channel and consent, bounded HTTPS companion, streaming/cancellation/disconnect handling and Link Gallery cache/reconnect example |
| Private install | Developer-key enrollment/revocation, protected unused-key removal, per-app lost-key replacement and backed-up repair of a readable corrupt registry |
| USB | Dedicated app protocol, OS-startup reservation, read-only inventory/capacity, install/readback/remove, bounded sequential uploads, reconnect status and no retry of ambiguous writes |
| Website | Catalog, Developers page, required name/description/icon/screenshots, GitHub-only OAuth, thumbs up/down and optional versioned comments |
| Publication | SDK GitHub sessions, owned-app library and project links; folder metadata/media, exact-package tests, resumable publication/update, listing pull/merge, metadata-only edits and withdrawal; matching website ownership/signing rules |
| Distribution | Current relocated source kits with optional verified newlib; earlier macOS ARM64 desktop bundle with compiler/Python/OpenSSL/QEMU and corresponding source. Current complete native bundles remain unfinished |
| Operations | Cloudflare D1/R2 and GitHub accounts in the website; legacy validator retained for historical reproducibility, not required for local-SDK publication |

OS startup reserves the fixed app region before browser connection. The browser
only reads inventory/capacity or installs/removes apps. It retires the
stock HP filesystem; the legacy backup/receipt protocol is retained for compatibility with older tools.
The firmware update partition, signature policy and bootloader stay unchanged.
No connected device was written.
The [storage contract](NATIVE-APP-STORAGE.md) documents the exact boundaries and
why physical recovery qualification is still required.

Storage has separate [qualification evidence](NATIVE-APP-STORAGE.md#candidate-evidence)
and later file/archive checkpoints in the SDK 1.0 ledger. The earlier SDK/package
qualification below is historical; it does not qualify later source or downloads.

## Earlier SDK verification — 2026-09-11 UTC

- Host suite: **387 passed**, two expected private DTB/DTS fixture skips.
  Storage tests execute the actual C++ volume engine under ASan/UBSan and inject
  interrupted/torn writes, bad blocks, capacity failure and corrupt generations.
- Physical target compilation passed. BIN SHA-256:
  `ef773362718c4c3ab25767468321c1c1624c6da86dc1c9f5f6a0339fb3fc3268`.
  This is build evidence only. Existing GNU-stack/RWX linker warnings remain.
- VM target compilation passed. ELF SHA-256:
  `fa91adc1349d670510a5db0f9c4c20623610ddf4ee17c0a7c8870e41c10aaeeb`.
  All 12 isolation cases and the normal keypad/Goodix app UI check passed.
- The VM USB test installed a signed ABI 1 app, read back the exact package,
  changed/saved app data through the normal launcher and keypad, cold restarted,
  verified the restored frame, and removed the app. It uses a synthetic
  preprovisioned volume; it does not qualify a physical NAND migration.
- Browser/host transport tests cover complete raw backup and disk reread before
  provisioning, signature mismatch, altered packages, interrupted uploads and
  ambiguous commit acknowledgements. These use mock devices only.
- Linux validator image
  `sha256:5585bc06476d05efb819b47221924e0ba663f5f20d80ad7d0958de4dbb50ea91`
  passed return, compile-error, hang, privileged-memory and malformed-source
  qualification cases. The passing app built identically twice and completed
  nine guest callbacks. Report: ignored `build/validator-qualification.json`.
- The macOS bundle passed doctor/new/build/test and signed-package launch after
  relocation into a folder with spaces, with system-only PATH and all Homebrew
  reads/execution denied. This is local macOS 26.6.2 ARM64 qualification, not
  clean-machine testing, notarization or Windows/Linux desktop qualification.
- Website build and **213 unit/integration tests** passed, including ABI 1
  automatic publication, required images, signatures, download allowlists,
  OAuth/reviews and mock USB migration. Final browser/deployment evidence is
  recorded separately with the deployment output. The browser suite passed
  44 of 45 checks on its first run; the existing recovery-expiry test timed
  out before its permission prompt, then passed separately without code changes.
  All four companion tests passed. Desktop/mobile download and install screens
  were visually inspected.

Local logs and frames are under ignored `build/sdk-*` and the website's
`.local/`. Public-tree checks exclude private keys, backups and generated trees.
The download API publishes the current artifact checksums; old candidate hashes
must not be used to qualify later binaries.

## Setup and qualification still required

The current macOS ARM64 desktop candidate now includes newlib, ARM GDB and
libusb. Eight relocated offline template journeys, main debugging, CMake without
Python discovery and Notebook/UI Gallery preview pass. This is local bundle
evidence, not clean-host or full companion qualification. The new native-trust
candidate passes eight frozen HTTPS checks with Homebrew/checkout access denied,
including public roots, rejected certificates, deadlines and worker cancellation.
Sixteen frozen account steps pass against a controlled local HTTPS service using
the actual macOS Keychain, including replacement, revocation and credential
cleanup. Real GitHub/browser and production-store operation remain unqualified.
See the latest SDK implementation ledger checkpoint for exact artifacts.

The later frozen companion candidate passes ten signed ARM/model-USB/TLS
journeys with Homebrew/checkout access denied, plus three independent host
disconnect repeats. It fixes a Ctrl-C transaction-boundary race and flushes
pairing/progress output immediately. This qualifies the explicit emulator
transport, not physical libusb transfers. An initial direct-launch watchdog
timeout remains a host startup measurement to investigate; the unchanged
candidate subsequently reports the expected missing-socket error in 3.2 seconds.

The later store-client candidate enforces each HTTPS request's 20-second total
deadline in a disposable process, covering DNS, native trust and blocked response
reads. Its relocated frozen macOS bundle passes seven network-failure cases and
the sixteen native-Keychain account steps. Failed requests are not retried by the
transport; saved mutation receipts remain the recovery path. This is local
qualification against controlled services; real GitHub/store and other supported
hosts remain separate gates.

The later website backend candidate reserves shared account/global capacity for
SDK uploads, browser submissions and new listing images. Unique object prefixes
and transactional release/listing references protect accepted history during
cleanup. The real CLI/ARM publication journey passes through scheduled cleanup,
retaining signed downloads, owner historical images and SDK receipts. Legacy
bucket inventory, migration/writer cutover and production capacity qualification
remain open; older committed artifacts are outside the new managed counters.

1. Verify GitHub OAuth sign-in, logout, cancellation and expired sessions in staging.
2. Exercise the complete staging local-package/source/media submission, exact-byte
   signed download, data-preserving update and owner withdrawal. No hosted
   consumer or approval queue is needed. New schemas need coordinated readers
   before new writers are enabled.
3. Install a compatible firmware candidate through the existing installer when
   deliberately testing a recoverable calculator. Qualify raw backup and restore,
   migration, real power loss, bad blocks, cold boot, endurance and input feel.
   A general physical restore implementation is not supplied by this SDK.
4. Complete native Windows support and the current native SDK/companion bundles.
   Qualify clean Windows x86-64, macOS ARM64 and Linux x86-64 journeys, including
   platform credential stores, offline build, preview/debug, installation and
   removal. Resolve host signing/notarization requirements for release artifacts.
5. Finish remaining application resource/error, UI and damaged/unreadable-media
   recovery cases. Set measured
   performance budgets and conduct independent developer trials using the actual
   release bundles. Verify the coordinated website and downloaded artifacts.

## Remaining scope and deliberate limits

The [C-library comparison](NATIVE-APP-C-LIBRARY-COMPARISON.md) selects newlib.
Its expanded fixture passes 23 ARM phases, including automatic stream cleanup
and repeated global flushing. Picolibc is smaller but fails four cases with
both default and faster buffering; it remains an isolated experiment. This
closes the library-choice work, not full C/runtime or SDK qualification.

General damaged/unreadable-media recovery and broader resource/security/lifecycle
coverage remain open. Store allocation/reclamation has local implementation
evidence; production migration, legacy inventory and workload qualification still
require acceptance. The full desktop
source audit also needs the native libraries vendored by the Pillow wheel;
similarly named Homebrew libraries are not proof of matching sources. Existing archive
code repair requires an intact canonical ownership record and the original signed
package proof; it cannot infer ownership from unreadable roots. Real GitHub/store
operation, clean native hosts, independent trials and physical
storage/input/performance qualification require separate evidence.

The selected SDK math and C++ UI subset is implemented; full internal
Escher/Poincare parity is not a 1.0 prerequisite. General STL, POSIX processes,
background services, wireless hardware and a visual editor are outside the
required profile. Follow the 1.0 plan's explicit scope rather than treating every
older roadmap proposal as a release gate. The built-in Python app is preserved;
Python application submissions are not supported.
