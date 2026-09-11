> Historical profile 1. New firmware uses [profile 2](NATIVE-APP-STORAGE.md).

# Native app storage profile 1

Profile 1 retires the stock HP UBI filesystem in favor of Lefony app storage.
Lefony initializes it during OS startup, before the event loop accepts browser
commands. This is the maintainer-requested OS storage policy. The browser does
not prepare space, generate volume identities, save backups or prompt for storage
setup. No physical calculator was written during development.

The fixed region is **432–496 MiB**, NAND blocks **3456–3967** inclusive.
It does not overlap firmware mtd1, boot/DTB/misc, proposed A/B slot B, rescue,
or the Linux flash bad-block table. The existing A/B migration remains disabled.
The checked contract is [app_layout.json](../native/prime_g2/app_layout.json).

Physical I/O reuses the existing captured GPMI/APBH/BCH configuration, with
separate app-region range checks. It does not reset clocks, retime NAND, change
the ECC layout, or expose arbitrary NAND writes. The VM uses its synthetic
NAND interface; a VM result does not qualify physical electrical behavior.

## Migration and recovery

### OS startup

`Board::init()` invokes `AppManagement::init()` after persistence initialization
and before watchdog/runtime startup. Existing valid app volumes mount unchanged.
Only an unprovisioned volume can be initialized. First pages of every usable
block must be erased or have a stock UBI erase-counter header (`UBI#`). Unknown
contents, unreadable pages, damaged volume markers and surviving app records
reject initialization before erasing anything. No automatic recovery reformat is
attempted. Errors leave the OS usable and are reported to the browser.

The OS derives the volume identity by hashing a domain separator and the scanned
metadata pages. This identity is not a backup receipt or signing secret. The
existing `LFAVOL1` layout remains unchanged. Only the two marker blocks are
initialized; app-bank erases happen during normal verified transactions.
The stock filesystem is retired without a backup. The firmware install screen
explains that before upgrading. A partial first marker requires recovery; real
power-loss and restore qualification remain outstanding.

Legacy requests `61`/`62` retain their receipt requirements for older SDK tools;
the website never calls them. On newly booted firmware the volume is already
initialized, so these unprovisioned-only commands are unavailable. A backup made
after OS startup cannot recover the overwritten stock pages.

## App transactions

The first two blocks contain redundant volume markers; the next fourteen are
reserved. Eight app slots each have two banks of 31 erase blocks. A slot stores
one signed package (maximum 2,101,664 bytes) and up to 65,536 bytes of private
data. Factory bad blocks are skipped within each bank; insufficient usable
space fails before erasing. The active bank is never erased by an update.
Only blocks needed by the next record are erased, limiting needless wear.

A bank header records the volume identity, slot/bank, nonwrapping generation,
lengths, explicit block map and combined package/data SHA-256. The first usable
block is metadata-only; payload begins in the next mapped block. The writer:

1. Erases the inactive bank's required blocks.
2. Writes the header and package/data pages.
3. Reads back every page and compares exact bytes.
4. Programs the commit record in metadata page 1 and reads it back.

This preserves increasing program-page order within each erase block. The
commit record binds the header hash and has its own SHA-256. Mount rejects torn
headers, commits, out-of-range maps and corrupt payloads. It chooses the newest
complete generation; an intact older bank can recover from a damaged newer one.
A deletion is a committed empty record, so an old bank cannot resurrect an app.

App updates match authenticated app IDs. A lower version or different bytes
under the same version are rejected; repeating the same package is idempotent.
Private data travels with the package transaction. ABI 1 services stage writes
in RAM, and normal app exit commits them. A callback fault discards staged
changes. The app must version its own data representation and handle missing
or older data. Abrupt power loss can lose changes not yet committed on exit.

## USB protocol 1

All commands use device-recipient vendor EP0 transfers, VID/PID `CAFE:5052`.
Arguments are little endian `wIndex:wValue`; transfers are at most 512 bytes.
No app command is a firmware update command. The transport serializes NAND
ownership and rejects competing firmware requests while app work is active.
Deferred mutations begin only after the USB status stage has completed.

| Request | Direction | Meaning |
| --- | --- | --- |
| `60` | IN / OUT | 64-byte status / mount storage |
| `61` | OUT / IN | Start raw backup / next sequential raw fragment |
| `62` | IN / OUT | Complete backup SHA-256 / provision with matching receipt |
| `63` | OUT | Begin upload, argument = exact signed package length |
| `64` | OUT | Sequential package fragment, argument = byte offset |
| `65` | OUT | Authenticate, select matching/free slot, install transaction |
| `66` | OUT | Remove installed slot with a tombstone |
| `67` | OUT | Abandon backup/upload; does not cancel a NAND commit |
| `68` | IN | 168-byte catalog entry for a slot |
| `69` | — | Unsupported; no browser reservation command |
| `6a` | OUT / IN | Select installed package / read its bytes back |
| `6b` | IN | Read 40-byte storage summary; no mutation |

Status is sixteen LE uint32 values: magic `0x3141464c`, protocol 1, state,
error, received bytes, expected bytes, profile 1, eight slots, ABI 1,
backup byte count, backup progress, storage engine state, engine progress,
target slot, pending command, capability bits (bit 1: OS-owned storage and summary).
Older protocol 1 firmware has no summary capability; its existing catalog can
still be read when mounted. Uninitialized older firmware needs an update. Wire
states: 0 cold, 1 unprovisioned, 2 ready, 3 backup, 4 receiving, 5 working,
6 complete, 7 error. The browser does not send the OUT mount request on refresh.

Storage summary: ten LE uint32 values: magic `0x5341464c`, version 1, reserved
region bytes, usable package capacity, installed package+data bytes, available
package capacity in empty slots, occupied slots, slot count, maximum package
bytes, maximum private-data bytes. Capacity accounts for bad blocks, metadata,
full private-data space and both update banks. Available bytes exclude unused
space inside occupied slots; those slots can update their own app but cannot
hold an unrelated additional app. The 64 MiB raw region is not 64 MiB of package
capacity. Metrics are cached from the OS-owned fixed geometry, never invented
from browser download sizes.

Catalog fields: package bytes at 0, generation at 4, ABI at 8, NUL-terminated
ASCII ID at 12 (49 bytes), name at 61 (81 bytes), version at 142 (24 bytes),
and two padding bytes. Firmware compile-time assertions protect these offsets.

A lost write acknowledgement is an unknown result. Neither host nor browser
retries it or sends an automatic abort after the install boundary. Reconnect
and inspect the catalog, then verify package readback. The host tool and browser
require signed ABI 1 packages; unsigned packages and ABI 0 remain VM-only.

## Evidence and limits

`tests/native/app_storage.cpp` runs the actual firmware engine under host ASan
and UBSan. It injects power cuts and torn writes at every transaction mutation,
checks paired app/data recovery, deletion, cancellation, corrupt-payload fallback,
bad blocks, capacity limits and migration interruption. The USB integration test
boots the guest against synthetic blank NAND (or a legacy pre-provisioned
fixture with `--preprovisioned`), checks storage is already ready before any host write, uploads and
reads back a signed app, cold-restarts, verifies persistence and removes it.
It does not substitute for a complete physical backup/migration/restore test.


### OS-owned storage candidate — 2026-09-11 UTC

Local source based on `7418a42` plus these pending changes passed:

- `make test check-public`: 387 tests passed, two private-fixture skips; public
  boundary passed. Host storage tests include bad-block capacity, unknown data,
  missing/damaged markers, paired transactions and torn-write injection.
- Physical build with the existing release/app public roots passed. BIN SHA-256:
  `56dfaef2b746f9a28949d5b5d9370556196e520a716cc5a8993af936b9403c61`.
- VM build with the existing app public roots passed. ELF SHA-256:
  `ddf77be311a9d1e9d3f533c217fafc9304aab59106b1f1dc70cfa282ef3fe3b5`.
- `vm/test-native-app-storage.py --signing-key <private-app-key>
  --public-key ports/lefony-prime-g2/app-signing.pub` passed with blank synthetic
  NAND: storage was already ready before any host mutation; inventory reported
  capacity; signed upload/readback, normal keypad data save, cold restart and
  removal passed. The restart checked occupied slots and available bytes too.

Local build logs are ignored under `build/os-owned-app-storage-*`. These are
candidate hashes, not released firmware. Existing GNU-stack/RWX linker warnings
remain. No physical device was accessed. Electrical behavior, boot timing on real
NAND, stock-layout acceptance, power-loss recovery and endurance remain unqualified.


## Main-menu integration

Installed apps appear as individual tiles after the built-in applications. The
native runtime remains an internal container and is omitted from the home grid.
Existing built-in snapshot indices and hardware shortcuts are preserved; Settings
skips the hidden runtime. The grid refreshes on catalog revision changes after
install, update or removal and clamps selection when the selected app disappears.
Both normal keyboard activation and Goodix touch open the selected storage slot.
Back returns directly to the main menu and commits normal app-exit data.

Installed apps cannot launch in exam mode. Faulted apps retain the runtime's
existing recovery path. The SDK's emulator-only launch command can still display
a staged development package without requiring installation.

Current signed packages carry the app name but not the website icon. Menu tiles
therefore use the app name and the existing default external-app icon; long names
are abbreviated to fit a cell. Store icons require a separate signed-package
extension and are not claimed to transfer with the current package format.


Main-menu candidate validation (2026-09-11 UTC): host suite 387 passed with two
private-fixture skips; both target builds passed. The checked menu preparation
was run twice on the compiled upstream tree without changing its bytes. The
USB/emulator integration installed a signed Counter app, observed its new tile
while the menu remained open, launched it with the physical keypad, saved data,
returned directly with Back, restarted, launched through a Goodix touch on the
menu tile, verified saved data, removed it and checked selection moved to the
remaining Settings tile. The physical Settings shortcut opened Settings. Captured
menu frames were visually inspected. The original test initially compared the
USB modal rather than the menu; dismissing it with the normal Back key corrected
the test, without changing the USB connection behavior.

Candidate physical BIN SHA-256:
`caef3aa853c2dd7ba8b4ab2b5cf75094f5d47a9543f862224aba5f97d59de82d`.
Candidate VM ELF SHA-256:
`87563db85c5f8eaf6510efed7036c8a318e81a2717ef76de912d74c4d60fc234`.
These local candidates supersede the hashes in the startup-only section above.
No physical calculator or published release was changed. Logs are ignored under
`build/main-menu-apps-*`; screenshots are under `build/sdk-installed-counter/`.
