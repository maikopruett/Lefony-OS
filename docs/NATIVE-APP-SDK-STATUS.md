# Native SDK implementation status

The native SDK, signed ABI 1 runtime, persistent app storage, USB app installer
and public website are implemented as a **development candidate**. SDK source
stays with the OS; the website owns accounts, listings, publication and ratings.
See the [setup runbook](NATIVE-APP-SETUP.md) for the remaining account/host setup.
This does not mark every future milestone in the [full plan](NATIVE-APP-SDK-PLAN.md)
complete or qualify migration on physical hardware.

## Implemented

| Area | Available behavior |
| --- | --- |
| SDK | Pinned GCC, project generation, AGENTS.md, native C++ examples, deterministic packages, inspect/build/run/test/source commands |
| ABI 1 | Frozen package/service/event contract, drawing, keypad/touch/timers, bounded private data calls, normal start/close lifecycle |
| Runtime | ARM user mode, RX code, non-executable data/stack, guard pages, validated pointers, callback timeout/fault recovery; launcher on both targets |
| Signing | Separate RSA-2048 app identity, LFAPP1 signatures checked by host, guest and website, bounded public key ring and retired-key rejection |
| Storage | Explicit profile at 432–496 MiB; eight app slots, paired package/data banks, 64 KiB private data, bad-block handling, readback and commit records |
| USB | Dedicated app protocol, backup-gated provisioning, install/readback/remove, bounded sequential uploads, reconnect status and no retry of ambiguous writes |
| Website | Catalog, Developers page, required name/description/icon/screenshots, GitHub-only OAuth, thumbs up/down and optional versioned comments |
| Publication | Source-only uploads, immutable versions/ownership, queued leases/retries, isolated rebuild/test, automatic host signing and publication without manual approval |
| Distribution | macOS ARM64 desktop candidate with compiler/Python/OpenSSL/QEMU, checksums, notices and three corresponding-source archives; standalone source kit |
| Operations | Cloudflare D1/R2 provisioned; Linux validator image qualified locally; consumer service/timer and authenticated health command |

The migration intentionally retires part of the stock HP filesystem, only after
the host saves and rereads the entire selected raw NAND range and the device
verifies the backup receipt. It does not alter the existing firmware update
partition, signature policy or bootloader. No connected device was written.
The [storage contract](NATIVE-APP-STORAGE.md) documents the exact boundaries and
why physical recovery qualification is still required.

## Verification — 2026-09-11 UTC

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

1. Create the GitHub OAuth app and configure its credentials.
2. Run the qualified consumer on a dedicated always-on Linux host, qualify its
   exact image there, and exercise the complete staging login/submission/signing/
   download/review flow. Then enable public submissions. There is no approval queue.
3. Install a compatible firmware candidate through the existing installer when
   deliberately testing a recoverable calculator. Qualify raw backup and restore,
   migration, real power loss, bad blocks, cold boot, endurance and input feel.
   A general physical restore implementation is not supplied by this SDK.
4. For normal desktop releases, complete clean-machine testing and macOS
   signing/notarization. Other desktop platforms need separate qualification.

## Later full-plan milestones

The small SDK API does not yet expose full Escher widgets or Poincare math.
Data export/import, richer rollback/migration tooling, expanded fuzzing/security
review, store pagination/search, publisher metadata management, a moderation
console, automated SDK release CI, and operational backup/retention/monitoring
remain follow-up work. Ratings are implemented and do not replace runtime or
storage qualification. The existing built-in Python app is preserved; Python
application submissions are not supported.
