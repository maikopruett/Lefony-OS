# Browser dual-boot development release

This release installs the shared layout on **HP Prime G2** and updates existing
layout-5 installations entirely in desktop Chrome or Edge. No desktop companion,
Python, UUU or account is required for the browser installation.

The startup screen has a three-second progress bar. Press the calculator's
**Enter** key to choose HP OS, Lefony OS or a saved priority; otherwise the
priority OS boots. Up, Down, Left, Right and touch work in the menu. After manual
Off/On in either OS, the normal startup screen appears again. Switching OSes
restarts the calculator.

## Installation

Open [the website installer](https://lefony.com/#install), choose **Install or
update dual boot**, and prepare the signed release. Choose a new local recovery
folder with at least 1 GB free. The full raw backup alone is 553,648,128 bytes.
Keep this folder after installation; it contains the signed release, original
NAND, before/after block hashes, planned writes and a restartable transaction.
None of these local files is uploaded.

For first installation, provide your own exact **HP V15751 HPPrime.img**:
8,192,864 bytes, SHA-256
`25d3d2d27e45fc3ce7dc8c4a111b31f8aefc14c4b21e8d8ee4b32251e31c1b82`.
HP firmware is not distributed by Lefony. Existing shared-layout updates use
the authenticated HP image already installed.

- A stock source must have the supported ROM geometry and readable HP filesystem,
  with free staging blocks and sufficient good blocks in every destination.
- Adding HP to the supported Phase 1 Lefony bootloader requires the retained raw
  stock HP backup from that same calculator. Other legacy bootloaders are refused.
- Existing shared layouts must have two matching signed descriptors, intact
  signed images, matching boot copies and an equal or newer release generation.

With Lefony running, select **Lefony is running** to start verified RAM recovery,
then **Connect recovery**. A stock calculator starts from the hardware ROM
recovery procedure described in website Connection help. Select the ROM device,
let the browser load RAM recovery, then connect to the recovery device again.
The browser checks recovery geometry, RAM staging and the recovery time budget.

Choose **Back up and review installation**, review the proposed changes and
confirm installation. Keep USB connected and the page open while it writes.
The browser verifies the saved full backup and the calculator again before any
NAND erase. Each block is staged, erased, programmed and read back; completion
requires all 4,096 block hashes to match. Written/verified and actual startup
confirmation are separate states.

If USB or the page is interrupted, keep the folder, reconnect recovery and use
**Resume from recovery folder**. The browser authenticates the retained signed
release and checks mirrored NAND journals and untouched blocks before resuming.
It never automatically retries an ambiguous erase or program. The full original
backup also remains usable by the guarded host restoration tools; a browser
button for restoring arbitrary original layouts is not part of this release.

## Scope and limits

This is a user-authorized development release, not completion of every Phase 7
hardware qualification item. The accepted physical candidate supports both OSes,
saved priority, Enter interruption and Off/On startup. Tests were performed on
one calculator; its battery was disconnected during the recorded USB-powered
checks. Broader battery, real power-loss, long-duration and board-variant testing
remain open. Do not infer these properties from emulator fault injection.

HP factory reset, maintenance reload and official HP updates are blocked by the
exact V15751 confinement profile. Do not use the official updater on this shared
layout. Lefony's legacy single-slot writers also refuse layout 5. The shared
update preserves HP storage, Lefony apps and saved priority. Lefony calculation
history is not currently persisted to NAND; this release does not add that feature.

The immutable layout digest and the research contract's
`physical_migration_allowed: false` are unchanged. This public development route
uses its own RSA-signed `lefony-browser-dual-development` manifest and explicit
review. It does not silently enable the separate research contract.

## Build and distribution

`scripts/package_prime_dual_release.py` accepts paired boot/recovery IMX and BIN,
Lefony capsule, DTB and a signed layout descriptor. It signs the public manifest
with the existing release identity. Keys remain private. The eight public
artifacts, `release.json`, checksums, license notices and corresponding source
are distributed separately from user-provided HP images.

Release generation **3** retains the physically accepted OS and countdown
bootloader bytes from generation 2; it advances the signed descriptor to exercise
the public browser update path. The release tag is `dual-boot-20260927`.

| Component | SHA-256 |
| --- | --- |
| Boot IMX | `89fc97004c5dc8c1605ae6cc103e8ae358e67a11770d4d6b28060cf651d7882d` |
| Boot BIN | `b2eb3246db39b2214df4c8e222b9778c3a2c541f3f2416980c3c4b2c8d5f9ec3` |
| Lefony capsule | `ef6a0b26fd309b664ad77e048e1d7caab66d32774fb8cdb757654654be21f515` |
| RAM recovery IMX | `cfb8406c34ed23fb4afbca7159e1f893c3b119be75b39ed77711cee4bd5ddc07` |

The website pins the signed manifest and downloads only its exact named assets
at build time. Its public WASM NAND codec has matching GPL source and a checked
source/hash manifest. The browser verifies all hashes and RSA signatures before
it offers a device operation. See the website repository's
[installer architecture](https://github.com/maikopruett/Lefony-OS-Website/blob/main/docs/INSTALLER.md).

## Release validation

The browser codec matches synthetic Python vectors, including error correction.
On the retained private stock fixture, all 100 HP logical objects, 80 file hashes,
five reconstructed filesystem blocks and four FCB pages match the Python
implementation. All 564 browser stock-migration changes match the existing
Python planner byte-for-byte. The browser-created fixture passes all seven
actual ARM ROM/menu cases: both OSes, saved priority, one-time override and
missing-layout/image refusal. Private fixture inputs are not distributed.

Physical browser installation and publication results are recorded in the
[Phase 7 qualification ledger](HP-LEFONY-PHASE7-QUALIFICATION.md).

Maintainers build the paired loaders with `scripts/build_prime_dual_boot.sh`
and `scripts/build_prime_phase6_recovery.sh`, and the physical firmware with
`LEFONY_DUAL_BOOT=1 scripts/build_lefony_prime_g2.sh`. Keep the existing release
public/private key pair; signing is separate from compilation. The exact prepared
Upsilon and both U-Boot trees, configurations and repository sources accompany
the public binaries. `scripts/package_prime_dual_sources.py --help` documents the
explicit source/config inputs. Its source manifest hashes each distributed file;
it never reads ignored device backup directories. The codec's complete C source
and licenses are included under the website tree in that same archive.
