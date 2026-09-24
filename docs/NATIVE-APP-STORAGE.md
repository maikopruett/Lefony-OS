# Native app filesystem (profile 2)

Apps are named files in a shared littlefs filesystem. There are no fixed app
slots or permanently paired app banks. Apps consume flash blocks according to
the size of their signed package and saved data. The website displays installed
apps, available space and usage; OS startup owns storage initialization.

The reserved region remains **432–496 MiB**, NAND blocks **3456–3967** inclusive:
64 MiB of payload flash. Firmware, boot/DTB/misc, proposed A/B slot B, rescue and
the NAND bad-block table are unchanged. The A/B migration remains disabled.
The checked geometry is [app_layout.json](../native/prime_g2/app_layout.json).

## Filesystem and accounting

The local [FILE5 root-recovery candidate](NATIVE-APP-ROOT-RECOVERY.md) stores
complete canonical document/file roots in separate payload and metadata copies.
It adds one 128 KiB payload block per protected root plus metadata, with matching
admission headroom. Healthy legacy roots migrate on their next successful root
commit; there is no startup bulk conversion. Matching firmware is required.

Pinned littlefs **v2.11.3**, commit
`6cb4e86540eca0d9ba62500a298385c9d863c8be`, is vendored with its BSD-3-Clause
license under `ports/lefony-prime-g2/ion/src/prime_g2/littlefs/`.
The [local change note](../ports/lefony-prime-g2/ion/src/prime_g2/littlefs/LEFONY-CHANGES.md)
records cache invalidation after a failed backend read; the upstream pin and
filesystem representation are unchanged.
The wrapper supplies static caches, aligned 2 KiB NAND page transfers, bounded
hardware operations, bad-block rejection and the existing GPMI/APBH/BCH driver.
No hardware timing, ECC layout or register definitions change. When the existing
ECC reader rejects an unwritten page, the app backend accepts it as erased only
if a separate raw read confirms every payload and spare byte is `FF`. Other
ECC damage and transport/geometry errors remain failures. This exact-erased-page
rule is conservative about worn pages and needs physical qualification.

The first two blocks are version/volume anchors. The remaining 510 blocks form
littlefs. Each erase block is 128 KiB. Twenty-four blocks (3 MiB) remain reserved
for atomic replacement of the largest supported app plus filesystem metadata.
Factory bad blocks reduce capacity. Filesystem metadata and the rounded physical
allocation of app files count as used allocation. `available` is usable capacity
minus allocated blocks, including metadata; it is never estimated from downloads.

On healthy, empty synthetic flash, approximately **60.25 MiB is available**.
A 17 KiB app normally consumes one 128 KiB data block, rather than a multi-MiB
slot. This is flash allocation granularity: files do not reserve space for their
maximum future size. Removing a file releases its blocks for other apps.
Signed package and private-data limits remain 2,101,664 and 65,536 bytes per app.
The in-memory directory bound is derived from the region's 512 physical blocks;
each accepted package exceeds the inline limit and consumes at least one block,
so usable flash is exhausted before that bound. There is no eight-app limit.

Files are `apps/<authenticated-app-id>.app`. The file's 64-byte `LFAFILE2` header
contains format version, generation, package/data lengths and combined SHA-256,
followed by the package and private data. Startup checks every package signature,
metadata and ID against its filename before exposing the catalog. App ABI 1 and
the signed package format/trust roots are unchanged.

## Atomic installation, replacement and removal

The OS writes a temporary file, closes/syncs it, reads back its complete contents
and checks its digest, then atomically renames it over the app's named file.
Until rename commits, the previous app and saved data remain intact. Removal
uses an atomic file deletion. Abandoned temporary files are cleaned on startup.
Littlefs supplies copy-on-write metadata, bounded allocation and wear leveling.
Reserved headroom allows same-size replacement even when new installs cannot fit.

Version checks remain: a lower version or changed bytes at the same version are
rejected; reinstalling identical bytes is idempotent. Normal app exit commits
staged private-data changes with the package. Faults discard staged changes;
power loss can lose changes that had not yet been committed on normal exit.

## Startup and migration

Existing profile-1 volumes migrate automatically in the OS. Their old storage
engine is retained only for layout recognition and reading verified legacy
records. Every live legacy extent remains protected against erase/program while
apps are copied into named files. Copies preserve app IDs, generations and data.
Each copy is read back and verified before a durable completion marker is written.
Only then are both old anchors replaced with sealed `LFAVFS2` anchors and the
legacy extents made reusable. An interrupted migration resumes from the verified
legacy records or completed filesystem. No browser setup command is required.

Old firmware fails closed on profile-2 anchors; downgrading cannot reinterpret
filesystem blocks as old banks. Downgrading storage requires a separate,
explicitly authorized recovery procedure. A damaged completed filesystem is
never automatically reformatted. Errors leave the OS available for recovery.

Unprovisioned stock volumes retain the existing startup policy: scan the region
and initialize only recognized erased/UBI layouts. Unknown or unreadable data is
rejected before erasing. The stock HP filesystem is retired without creating a
backup, as requested by the maintainer. This is distinct from migration of
existing Lefony apps, which preserves their data. The initial legacy marker
creation boundary retains its existing recovery limitations; the new migration
power-cut tests start from a valid profile-1 volume. Legacy backup requests retain
their receipt checks; the website never sends them. Physical qualification is
still required for first-use setup and migration.

## USB protocol 2

VID/PID `CAFE:5052`, vendor EP0, little-endian arguments `wIndex:wValue`, maximum
512 bytes per transfer. Command IDs are preserved, but **protocol and storage
profile are now 2**. Both current SDK and website also accept older protocol 1.
An old client must reject protocol 2 instead of interpreting its counts as slots.

| Request | Direction | Meaning |
| --- | --- | --- |
| `60` | IN / OUT | 64-byte status / legacy explicit remount |
| `61`, `62` | mixed | Legacy receipt-checked backup/provision path |
| `63`, `64`, `65` | OUT | Begin upload, sequential fragment, authenticate and install |
| `66` | OUT | Remove app at current catalog index |
| `67` | OUT | Abandon unfinished backup/upload, never cancel a committed write |
| `68` | IN | 168-byte entry at current catalog index |
| `69` | — | Unsupported; no browser reservation command |
| `6a` | OUT / IN | Select installed package / read back package bytes |
| `6b` | IN | 48-byte shared filesystem accounting |
| `6c` | OUT | Commit a signed icon from the upload buffer (capability bit 3) |
| `6d` | IN | 32-byte verified icon SHA-256 for catalog index; zero if absent |

Status is sixteen LE uint32 values: magic `0x3141464c`, protocol 2, wire state,
error, received bytes, expected bytes, profile 2, **actual catalog entry count**,
ABI 1, legacy raw-backup byte count, backup progress, internal engine state,
engine progress, target index, pending command, capability bits (bit 1: storage
summary; bit 2: shared filesystem; bit 3: signed menu icons). States remain 0 cold, 1 unprovisioned, 2 ready,
3 backup, 4 receiving, 5 working, 6 complete, 7 error.

Storage summary is twelve LE uint32 values:

| Offset | Meaning |
| --- | --- |
| 0 | Magic `0x5341464c` |
| 4 | Summary version 2 |
| 8 | Reserved region bytes (64 MiB) |
| 12 | Capacity after anchors, bad blocks and update reserve |
| 16 | Actual installed package + saved-data bytes |
| 20 | Available capacity after physical allocation |
| 24 | Installed app count |
| 28 | Allocation unit (131,072 bytes) |
| 32 | Maximum signed package bytes |
| 36 | Maximum private-data bytes |
| 40 | Allocated filesystem bytes, including metadata |
| 44 | Region bytes excluded from usable capacity |

Accounting is refreshed outside USB request handling. Inspection only copies
cached metrics and directory entries; it does not start flash writes or scans.
The 168-byte catalog entry layout is unchanged. Catalog indices identify the
current enumeration, not physical storage locations, and may change on mutation.
Clients obtain a fresh catalog before acting and match apps by authenticated ID.

Deferred mutations still begin only after USB acknowledgement and serialize NAND
ownership against firmware updates. Lost write acknowledgements have unknown
outcomes: hosts never retry or automatically abort. Reconnect and verify catalog
and package readback. The browser displays actual app count without a slot limit.

## Menu and qualification

Apps continue to appear beside built-in apps in the main menu; the internal
runtime container remains hidden. Keyboard and Goodix touch launch named apps
through the current catalog. Exam-mode and callback-fault behavior are unchanged.
Signed packages still lack embedded store icons, so menu tiles use the existing
external-app icon and authenticated app name.

The real storage engine is tested with ASan/UBSan on sparse synthetic NAND,
including torn writes/erases during app replacement, deletion and every measured
legacy migration mutation, interrupted-update recovery, bad blocks, more than
eight apps, full-volume replacement, reclamation and rejection of damaged or
unknown volumes. The VM test covers USB install/readback, app launch, saved data,
cold restart and removal. Exact candidate build/test evidence is recorded below
when complete. These checks do not qualify physical NAND behavior, real power
cuts, startup latency, endurance or restoration. No connected calculator is
written by these development tests.

## Rollout

Deploy the compatible website and distribute an SDK containing protocol-2
support before releasing the new physical firmware. Older websites/SDKs reject
protocol 2; rerunning an installer that still serves an older SDK is insufficient.
Rebuild the SDK firmware/emulator artifacts and corresponding source together.
The ABI-1 app package/signing identity does not change, so store apps do not need
new signatures solely because their storage changes. Firmware startup performs
the storage migration; publishing the website alone cannot expand an old volume.

## Candidate evidence

2026-09-11 UTC, local source based on OS `91dbd0705486` plus the shared-filesystem
changes; website based on `fdc4f39`. No physical device was accessed or written,
and these artifacts have not been published.

- `make test check-public`: **390 passed**, two expected private DTB/DTS fixture
  skips; public boundary passed. Host C/C++ storage tests use ASan/UBSan, simulate
  torn erase/program operations, enforce one program per page and increasing
  page order, migrate all eight maximum-size legacy apps, fill shared storage,
  replace at capacity, reclaim deletion space, and reject non-erased raw pages.
- `make firmware` with the existing release and app public roots passed for
  `prime_g2`. BIN SHA-256:
  `87ca9f23aca840220189ca3a6b371175645c59a1468528449ec61f752a88b53d`.
- `make firmware-vm` with those public roots passed for `prime_g2_vm`. ELF SHA-256:
  `6bbb02a07d2eee1b4216b1b84915210182805dd4be5916f7fd4222b58b54dacb`.
  Existing GNU-stack/RWX linker warnings remain.
- `vm/test-native-app-storage.py --signing-key <private-app-key> --public-key
  ports/lefony-prime-g2/app-signing.pub` passed for blank synthetic NAND and
  with `--preprovisioned` for legacy empty-volume migration. A final run with
  `--many-apps` passed cancelled-upload recovery without remount, signed install
  and exact USB readback, keypad and Goodix menu launch, saved-data cold restart,
  removal, nine simultaneous installed apps, ninth-app launch/data save, and
  correct directory reindexing after deleting another app. The ninth-app menu
  and running counter frames were visually inspected.
- `vm/test-native-app-ui.py` passed SDK staged-app launch, keypad and Goodix
  controls. Its first attempt missed the initial Confirm event while other VM
  checks ran; an unchanged rerun passed. This timing sensitivity is not claimed
  as a resolved input issue.
- Website: **239 unit tests passed**, one skip; build and lint passed. The broad
  browser run had 50 passes and one failure waiting for the firmware recovery
  handoff button; that unchanged test passed in isolation. Both app-install
  browser checks passed again after the final transport changes. Desktop and
  mobile inventory screenshots were visually inspected, including no overflow.

Local logs are ignored under `build/shared-storage-*` and the website's `.local/`.
Physical migration, ECC/erased-page behavior, actual interrupted power, NAND
endurance and startup time remain unqualified. Root/anchor damage fails closed;
the payload bad-block tests do not qualify every factory-bad-block placement.

## Optional menu icons

Icons are independent `icons/<authenticated-app-id>.app` files using the same
LFAFILE2 header, full-content digest, bounded write/readback and atomic rename
as executable files. Their signed attachment occupies the package field; the
private-data field is empty. This is an additive namespace on profile 2 and
requires no reformat or migration. App catalog count and executable generations
exclude icons; allocated storage includes them, and logical usage includes
stored attachment bytes. The filesystem's 128 KiB allocation unit still applies.

At catalog refresh the OS authenticates each optional icon and matches its
embedded package hash against the installed executable. It caches validated
pixels and attachment digests before serving USB queries or drawing the menu.
An icon for an older executable version is ignored until replaced. Private-data
writes preserve the separate icon file. App removal deletes its icon first,
then the app: an interruption can leave the app with the default icon, but
cannot lose app data through an icon update. Interrupted icon replacements
leave either the old complete icon or the new complete icon.

Connecting and refreshing inventory only read icon digests. Installation sends
the app and then its icon; an already installed matching release offers an
explicit **Update app icon** action. Each commit is verified and is never
retried after an ambiguous USB result. Older firmware keeps accepting normal
app installation; the website offers a firmware update for icon support.

### Icon candidate checks (2026-09-11 UTC)

Source based on `4e99fa053ecd` plus the icon changes. Local physical Prime G2
BIN SHA-256:
`3b12f9bbb9b5b4d17b298fb52e5ea10ae443fa60ce138e92282ecf7fe0f19923`.
Local Prime G2 VM ELF SHA-256:
`2a03f4d50652280a7f89bd68f838cb1571d53cd7279c4fb32cc9a0d025da9124`.

Both `make firmware` and `make firmware-vm` passed with the existing public
firmware and app roots. `make test`: 390 passed, two optional private fixtures
skipped. `make check-public` passed. Storage tests run the actual littlefs engine
under ASan/UBSan with torn writes during initial icon creation and replacement;
apps, generations and private data remain unchanged.

`vm/test-native-app-storage.py` with the existing local app signing key and
public root passed: signed app USB readback; bad icon signature and wrong-package
rejection; signed icon readback; exact RGB565 colors in the home menu; replacing
a cached icon redraws without key input; app data and icon survive a cold restart;
removal clears the catalog. Captured synthetic VM frames were inspected locally.
This does not qualify physical USB/flash behavior or physical power-loss recovery.

Matching website checks: 250 unit tests passed, one optional SDK fixture skipped;
four browser installation cases passed (older firmware, unready storage, a new
app with its icon, and updating an existing app's icon). Build/type checks, lint
and Worker dry-run passed. No firmware release or live website deployment was
performed for this candidate.
