# App file exchange protocol 1

Development candidate. This is an additive host-management protocol, independent
of the app API revision, package signatures and USB storage protocol 2. It uses the
same reserved 64 MiB app region and production file transactions. No trust root,
partition layout or app sandbox permission changes are introduced.

App hello (`IN 0x60`, 64 bytes) flag 32 advertises this protocol. Flag 64 reports
an open foreground app. A host checks support and closes the app before BEGIN.
Firmware also enforces exclusive ownership against app execution, package
installation, recovery operations and another file transfer. Signed installed
metadata authenticates the selected app; caller-supplied paths never choose a
filesystem or raw flash address. Missing/invalid installed identities fail closed.

All records use little-endian uint32 fields and zero-padded ASCII. Transfers use
control endpoint vendor requests, with `wIndex:wValue` forming the uint32 argument.
The existing hello and storage/profile versions retain their layouts.

| Request | Direction and payload | Meaning |
| --- | --- | --- |
| `0x70` | IN, argument 0, exactly 96 bytes | Cached transfer status; no filesystem I/O |
| `0x71` | OUT, argument 0, exactly 224 bytes | Begin one selected-app operation |
| `0x72` | OUT, argument 0, token/offset plus 1–504 bytes | Queue the next import frame |
| `0x72` | IN, argument is token, exactly `available` bytes | Read the current export/query chunk without consuming it |
| `0x73` | OUT, argument 0, token/end-offset (8 bytes) | Acknowledge and consume exactly that output chunk |
| `0x74` | OUT, argument is token, no payload | Verify received import hash and commit |
| `0x75` | OUT, argument is token, no payload | Cancel an uncommitted session |

An OUT frame is copied and queued, then acted on only after successful USB status
acknowledgement. A superseding SETUP abandons an unacknowledged frame. Chunk tokens
and offsets must match exactly; no implicit duplicate-write retry or offset skip
is accepted. IN data remains available until its explicit ACK. BEGIN's queued
status is visible before authentication/polling finishes, so it cannot be confused
with the preceding completed session.

The EP0 driver also rechecks a completed status IN after observing a new SETUP,
before dropping unacknowledged state or reusing its descriptor. Without this
check, the status ACK and next SETUP can arrive between the poll loop's initial
completion read and its SETUP read, incorrectly discarding an acknowledged
frame. `vm/test-sdk-usb-status-race.py` schedules this interleaving with GDB on
the real ARM driver while all bytes traverse modeled USB. It retains a positive
acknowledgement case and an abandoned-status negative case. The test does not
patch guest memory or emulate filesystem completion.

Bus reset can clear ENDPTCOMPLETE before the driver reads it. Before flushing
or rebuilding descriptors, reset handling inspects the DMA-written status-IN dTD:
only a zero-byte completion with Active, error and remaining-byte bits clear can
acknowledge a pending app request. Firmware update/reboot handling retains its
existing reset behavior. The exchange controller preserves an acknowledged COMMIT
even when reset precedes the next OS poll. The same test's `--commit-reset` mode
checks both acknowledged completion and an unacknowledged request that must cancel.
This is model/guest evidence; physical reset timing remains a qualification gate.

BEGIN has eight words (`size=224`, `schema=1`, operation, flags, generation,
data schema, length, cursor), followed by `id[64]`, `path[96]` and SHA-256 `[32]`.
The ID uses the signed app-ID grammar (at most 48 characters). File paths use the
existing strict relative-name grammar; unused text padding must be zero.

Base operations: 1 INSPECT, 2 EXPORT, 3 IMPORT, 4 LIST. INSPECT requires all fields
except ID/size/schema/operation to be zero. Other operations require the observed
root generation and data schema. EXPORT/IMPORT require a file name; LIST may use
an empty directory for the root. Only IMPORT permits flags (1 = replace) and
length/hash. Only LIST permits a cursor. Its generation is retained across pages.
Imports require compatible installed/saved schemas and no pending upgrade.

Status contains sixteen words followed by SHA-256 `[32]`: magic `0x5841464c`,
size 96, schema 1, state, operation, error, sequence token, accepted offset, total
length, available output bytes, root generation, saved data schema, frame size
512, flags, two reserved zeros. States are 0 idle, 1 working, 2 readable, 3 writable,
4 complete, 5 failed and 6 cancelled. Flags are 1 committed and 2 commit outcome
uncertain. Tokens do not wrap. A completed status remains available until another
BEGIN. The hash is finalized only when the transfer finishes successfully.

Errors 1–16 use the public file-service errors. Additional errors are 17 import
hash mismatch, 18 cancellation and 19 host inactivity timeout. Every file write
and hash/metadata check runs in OS polling, never inside a USB request callback.
Status polling alone does not extend an idle transfer's 30-second progress lease.
A bus reset cancels uncommitted exchange. An acknowledged commit is drained to its
actual result; it is never automatically repeated or reported cancelled merely
because the cable disconnected. The commit boundary is successful USB OUT status
acknowledgement, including the interval before OS polling starts the transaction.
Reset and host inactivity cannot cancel an already-acknowledged COMMIT.

EXPORT returns snapshot data. INSPECT returns a 144-byte record: eight words
(size 144, schema 1, app version triple, saved data schema, installed app schema,
pending-upgrade flag), then the existing 64-byte SPACE and 48-byte QUOTA records.
LIST returns the existing 1,688-byte directory page over multiple output chunks.
All output is verified by the host against the completed length and digest.
Inspection of legacy storage is read-only; a first import may perform the existing
versioned conversion while preserving its private bytes and package.

Import length/quota checks precede writing; the supplied hash is checked before
CLOSE publishes a replacement. Chunk and root verification remain in the existing
storage engine. Exports and failed imports do not replace a package or alter its
release watermark. Atomicity is per file. App-side byte-store checkpoints and
schema migration use [API 8](../sdk/DATA.md). Namespace archives, website UI and
physical qualification remain open.

## Private-data recovery extension

App hello flag 128 advertises operations 5 INSPECT_DATA, 6 EXPORT_DATA,
7 IMPORT_DATA and 8 ROLLBACK. Require both flags 32 and 128 before these requests.
The base wire sizes, protocol/storage versions and API 8 feature mask are unchanged.
The new SDK still supports base operations on flag-32 firmware. Older SDK status
readers may reject an extension operation left in cached status; use the matching
SDK for recovery sessions. Beginning a fresh base operation retains its old format.

INSPECT_DATA has the same zero-field rules as INSPECT. All other extension
operations require the observed generation/schema, empty path and zero flags.
EXPORT_DATA has zero length, digest and cursor. IMPORT_DATA permits a length of
0–65536 and the SHA-256 of that payload, with cursor zero. ROLLBACK has zero length
and digest; its nonzero cursor is the observed retained package generation.

INSPECT_DATA returns 176 bytes: twenty words followed by three 32-byte hashes.

| Word offset | Meaning |
| --- | --- |
| 0–3 | Size 176, schema 1, current root generation, flags |
| 4–9 | Current version triple, installed schema, saved schema, private byte length |
| 10–14 | Retained version triple, retained schema, retained private byte length |
| 15–19 | Highest installed version triple, retained package generation, reserved zero |

The hashes are current signed package, retained signed package and current private
bytes. Flag 1 means pending upgrade. Flag 2 means the retained package passed
signature, app identity, supported-runtime and schema checks. Without flag 2 the
retained version/length are not an authenticated rollback offer. Stored data is
verified again by the commit transaction; an offer is not a damaged-media health
certificate. No caller-supplied trust or compatibility bit is accepted.

EXPORT_DATA streams the captured committed byte store, including a valid empty
export. IMPORT_DATA stages all bytes in a bounded OS RAM buffer, checks the final
hash and generation, then makes one data-only checkpoint through the volume.
It preserves named files and code, honors quota, and refuses pending upgrades or
schema mismatch. ROLLBACK also prepares a writable, zero-length session. COMMIT
selects only the authenticated retained pair, restoring code and data together
while preserving the highest installed version. Its completion reports the new
root generation, restored schema and committed flag. Cancellation before COMMIT
changes neither package nor data.

The [SDK recovery guide](../sdk/DATA-RECOVERY.md) defines the bounded private-backup
format and user commands. Recovery still requires a readable current package,
root and private store; it is not whole-namespace restoration or damaged-media
repair. Referenced objects must pass the existing storage checks before rollback.

Validation: `tests/test_app_file_exchange.py` runs the production exchange/session/
file/volume stack under sanitizers on synthetic NAND. `tests/test_sdk_file_exchange.py`
covers host validation and local publication boundaries. `vm/test-sdk-file-exchange.py`
uses the actual USB device model, signed installed app and SDK FileClient.
`tests/test_sdk_data_exchange.py` covers the backup/client boundary, and
`vm/test-sdk-data-recovery.py` exercises signed ARM private-data restore, reset,
cold reopen and authenticated rollback. Controller tests inject clean/torn writes
at restore and rollback commit points. Consult the ledger for completed candidates.
`vm/test-sdk-doom-exchange.py` adds a separate long-running qualification journey
for the pinned 28,795,076-byte WAD: USB import, quota refusal, partial replacement
cancellation, real game launch and cold USB export. It preserves its synthetic
workspace on failure and requires a fresh output directory for a repeat run.
The existence of this harness is not a passing qualification result; consult
the implementation ledger for completed runs. Hardware power-loss/disconnect
behavior must be qualified separately on exact candidates.
