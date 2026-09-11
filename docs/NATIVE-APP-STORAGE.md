# Native app storage profile 1

Profile 1 intentionally retires the stock HP UBI filesystem in favor of a
Lefony app partition. It is an explicit migration, never a side effect of
installing firmware or submitting an app. The maintainer approved this design;
no physical calculator was written during development.

The fixed region is **432–496 MiB**, NAND blocks **3456–3967** inclusive.
It does not overlap firmware mtd1, boot/DTB/misc, proposed A/B slot B, rescue,
or the Linux flash bad-block table. The existing A/B migration remains disabled.
The checked contract is [app_layout.json](../native/prime_g2/app_layout.json).

Physical I/O reuses the existing captured GPMI/APBH/BCH configuration, with
separate app-region range checks. It does not reset clocks, retime NAND, change
the ECC layout, or expose arbitrary NAND writes. The VM uses its synthetic
NAND interface; a VM result does not qualify physical electrical behavior.

## Migration and recovery

Before provisioning, the device must serve all **69,206,016 raw bytes** in
sequence: 32,768 pages of 2,048 payload + 64 spare bytes. The host saves them,
flushes/closes the backup, rereads and hashes the saved bytes, and compares the
device's SHA-256 receipt. Only then may it send the provisioning command.
No receipt is available for a partial backup. A new connection cannot guess a
receipt or format an already provisioned volume through the ordinary installer.

The command-line installer creates a new private directory containing
`app-region.raw`, `backup.json` and, after success, `migration-complete.json`.
The browser saves `.lfbackup`: a 4,096-byte zero-padded JSON recovery record,
followed by the same raw bytes. Its checksum covers the raw bytes only.
Backups remain on the user's computer and never enter the store API.

Preserve the backup if power fails during migration. One valid marker is enough
to mount the new volume; an interrupted marker write is rejected by its hash.
There is no unattended attempt to restore stock NAND. Restoring stock requires
an independently reviewed recovery path which writes these exact raw bytes
(including spare bytes) back to this fixed region. **That physical restore path
and a physical power-loss qualification have not been run.**

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
| `6a` | OUT / IN | Select installed package / read its bytes back |

Status is sixteen LE uint32 values: magic `0x3141464c`, protocol 1, state,
error, received bytes, expected bytes, profile 1, eight slots, ABI 1,
backup byte count, backup progress, storage engine state, engine progress,
target slot, pending command, reserved zero. Wire states: 0 cold,
1 unprovisioned, 2 ready, 3 backup, 4 receiving, 5 working, 6 complete, 7 error.

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
boots the guest against a synthetic pre-provisioned NAND fixture, uploads and
reads back a signed app, cold-restarts, verifies persistence and removes it.
It does not substitute for a complete physical backup/migration/restore test.
