# Private-data checkpoints and app migrations

The development candidate adds a data controller alongside named files. It
uses the existing 64 KiB private byte store and FILE3/FILE4 transactions. It
does not change the app region, package signature policy or ABI 1 read/write
service numbers. Both targets compile and installed ARM journeys pass; see the
[implementation ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md) for exact candidates
and remaining qualification.

Include `lefony/data.h`. Require API revision 8 and capability 512 in a schema-1
manifest. A main program that also uses named files requires mask 536 (16+8+512).
The controller uses service 14. Undeclared access is denied; earlier firmware
rejects a required API-8 package. An explicit optional-feature probe receives
the ordinary unsupported-service error on earlier firmware.
Only the currently installed foreground app can access its own controller.
Disposable direct-memory previews have no installed data namespace.

All file descriptors and pending file completions must be closed/consumed before
a data operation. A data operation blocks named-file requests while it advances.
Private byte writes may continue after a checkpoint is submitted. Callback apps
poll on later events; conventional main programs yield between polls. Neither
the request nor status query performs filesystem work inside the app syscall.

## Submit and complete an operation

Create each request with `lefony_data_request(operation)`. Set only its documented
input fields, then call `lefony_data(&request)` once. A return of 1 supplies a
nonzero token. Poll using a **fresh** request with operation `LEFONY_DATA_POLL`
and that token. A return of 1 is pending; 0 delivers a terminal state/error and
consumes the completion. Negative returns reject the request. They are distinct
from the error field of an asynchronously failed operation.

Do not submit a second save to wait for the first one. Tokens are never reused
during the controller's lifetime. An invalid poll preserves the completion.
Every request is a zero-initialized 64-byte, schema-1 record; reserved and output
fields must be zero on input.

| Operation | Inputs | Result |
| --- | --- | --- |
| `LEFONY_DATA_INSPECT` | None | Committed generation, data/app schemas, private length and current edit state |
| `LEFONY_DATA_CHECKPOINT` | Observed `generation`, target `dataSchema`, private prefix `bytes` | Snapshot and durably save that prefix without accepting an upgrade |
| `LEFONY_DATA_BEGIN_MIGRATION` | Observed `generation`, installed app's `dataSchema` | Permit this app to stage private changes and mutate named files during its pending upgrade |
| `LEFONY_DATA_ACCEPT` | Observed `generation`, installed app's `dataSchema` | Release the retained recovery pair after a completed compatible migration |
| `LEFONY_DATA_CANCEL` | Active `token` | Request cancellation; continue polling the original token |

Inspect before a generation-checked operation. File commits can change the
generation, so inspect again after changing named files. A stale generation
returns the file-service `CHANGED` error before publication.

The result includes `generation`, committed `dataSchema` and private `bytes`,
plus `appSchema`, `stagedBytes`, `editRevision` and `snapshotRevision`. Flags are:

- `DIRTY`: staged private bytes still differ from the saved checkpoint.
- `PENDING_UPGRADE`: the previous complete package/data pair is retained.
- `MIGRATING`: this app explicitly entered migration for the current launch.
- `COMMITTED`: this operation reached successful durable publication.
- `COMMIT_UNCERTAIN`: storage failed after the transaction began; the actual
  outcome requires recovery inspection.

States are pending, complete, failed and cancelled. Errors 1–16 reuse the file
service meanings; error 17 denotes cancellation. An INSPECT or BEGIN_MIGRATION
completion does not set COMMITTED because it does not save data. CANCEL returning
0 means the cancellation request was accepted, not that rollback is complete.

## Live save ownership

The controller copies the requested private prefix into its own snapshot before
submission returns. A checkpoint can save at most the staged length and at most
64 KiB. A shorter prefix explicitly requests truncation, including an empty
store. A successful checkpoint updates the committed snapshot used by the file
session. It preserves existing named files and obeys the app's mutable-data quota.

Writes after submission update the live staging store, never the submitted
snapshot. They retain DIRTY on completion and have a different edit revision.
If no later edit occurred, success clears DIRTY and adopts the checkpoint's
length. A cancelled or failed truncation does not shorten the live staging store.

Normal successful Close drains an acknowledged checkpoint and saves later dirty
private edits. Faults, forced Home termination and unsuccessful program exit
discard uncommitted edits; a checkpoint already published remains durable.
Storage cleanup can continue after app execution stops. An uncertain checkpoint
failure prevents further writes and automatic Close saves in that session.
No completion implies that later staged edits were saved.

## Explicit migrations

The installed package's signed `data_schema` is the only permitted target.
Mismatched saved data remains readable, but ordinary writes are refused until
the app explicitly enters migration. Migration is available only during a pending
package upgrade, with all file handles closed.

After BEGIN_MIGRATION, the app can transform named files using the normal file
API and stage its private data using ABI 1 writes. File commits and checkpoints
continue to retain the previous package/data pair. CHECKPOINT commits the new
private bytes and target schema; it does **not** accept the upgrade. An interrupted
migration must be resumable using the app's own saved progress/schema markers.
Multiple file commits are not a single namespace transaction.

ACCEPT requires the saved schema to match the installed app, no unsaved private
edits and no open files. Explicit data-controller users do not implicitly accept
a schema-0 upgrade on normal Close. Existing apps retain their earlier schema-0
Close behavior. Acceptance drops the recovery pair and cannot be undone through
the retained-pair mechanism; request it only after validating the migrated data.

The production engine preserves the highest installed package version during
rollback. A failed immutable release requires a higher version for another
installation. Explicit [host backup/restore and retained-pair rollback](DATA-RECOVERY.md)
are separate SDK commands requiring the app to be closed. They are not supplied
by an app's ACCEPT operation. Whole-namespace restore and general damaged-data
recovery remain open.

These are development contracts. Emulator and synthetic-NAND evidence do not
qualify physical power-loss behavior, endurance or save latency.
