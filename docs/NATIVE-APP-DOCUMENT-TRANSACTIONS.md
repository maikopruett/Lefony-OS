# Data-only transactions: implementation and remaining integration

Status: the production volume now reads and writes LFAFILE3 roots, immutable
package/data objects, upgrades, acceptance and rollback. Converted apps save
through this path on normal Close; existing apps remain LFAFILE2 until explicitly
converted. The codec, preserved old reader, real storage interruption tests and
signed ARM save/upgrade path have passed local qualification. This is a storage
foundation, not the completed SDK file service: no public conversion/checkpoint,
migration/rollback syscall, named-file API or USB capability is advertised yet.

The follow-on [large-file layer](NATIVE-APP-LARGE-FILES.md) adds explicit FILE4
roots and immutable chunk indexes to the same volume. FILE3 remains the byte-store
representation; public SDK file/stdio integration is still unfinished.

## Layout and compatibility

Preserve the profile-2 shared littlefs, LFAVFS2 anchors, identity and migration
markers, reserved 64 MiB region, caches, inline limit 256, name limit 53 and
24-block update reserve. Version the per-app root explicitly as LFAFILE3, with
240 bytes. Old profile-2 readers must reject the app root/catalog without
formatting or touching its committed data. Qualify their actual preserved
implementation before enabling a writer.

Keep the canonical root at `apps/ID.app`. Store immutable package/data objects
under an app-specific directory, with short type/generation filenames. The
existing 53-character component limit precludes appending generation suffixes
to a maximum-length 48-character app ID. Directory metadata consumes actual
allocated flash and must be included in capacity accounting; it is not free.
Icons retain their signed-package hash binding and existing wire contract.

The codec in `app_document_root.h` specifies the candidate root. Its 32-byte
header is magic LFAFILE3, uint32 version 3, serial, flags (bit 0 pending upgrade),
and three numeric highest-accepted version components. Two 88-byte pairs follow:
current then previous. A pair has package generation, data generation, package
bytes, data bytes, data schema, reserved zero, package SHA-256 and data SHA-256.
A final SHA-256 covers the preceding 208 bytes. The current pair is mandatory;
the previous pair may be zeroed. A pending upgrade requires a complete previous
pair. Version components retain the existing 0–999999 range. Serial/object
identifiers are nonzero uint32 and fail at exhaustion. Referenced objects and
the signed package must also be verified; a root checksum is not authenticity.

The production `AppDocumentStore::Store` uses the volume's existing littlefs
instance and NAND backend. First conversion verifies the entire old combined
FILE2 hash before mutation, then copies its package once through a separate
2048-byte file cache. Later checkpoints write a new data object and atomically
replace the root without rewriting unchanged package bytes. Each write/readback
hash step processes at most 2048 object bytes. Filesystem metadata operations can
perform multiple NAND operations; this is not a qualified latency bound.

The engine verifies both retained pairs before mutation, verifies new object
lengths/hashes and the staged root before rename, and reclaims only objects
unreferenced by the committed root. Cancellation is allowed before root commit.
Uninstall removes the canonical root before pruning objects, after which it
cannot be cancelled. Startup continues interrupted uninstall cleanup only for
app directories whose canonical root is absent; corrupt live roots are preserved.
Unknown directory entries fail closed. No app is reconstructed from orphan objects.

Admission counts actual allocated blocks, including retained generations, plus
new object blocks, two metadata/recovery blocks and four directory blocks on
conversion. The existing 24-block update reserve can fund this transaction.
Repeated saves and completely full synthetic media are tested, but final per-app
quotas, guaranteed rollback headroom and physical endurance remain open.

## Runtime transaction ownership

The remaining public checkpoint integration must snapshot the staged 64 KiB byte store into a distinct
OS-owned buffer. It reports pending, durable generation, failure and actual data
schema. Data written after the snapshot stays dirty; a completion cannot report
those later bytes saved. Filesystem/hash work advances through bounded poll
steps, outside the app callback. Status queries cannot mutate storage.

The current internal Volume API requires its caller's input buffers to remain
stable until completion or cancellation. App management calls it after normal
Close, when the app can no longer mutate those buffers. Current `refresh()`
reuses the loaded-package/data scratch buffers. Do not call
it unchanged during a live checkpoint. Update cached accounting safely or defer
refresh until the foreground app closes. Resolve Close, fault, cancellation and
an in-flight checkpoint explicitly; preserve acknowledged durable snapshots,
discard uncommitted faulted-app edits, and never silently lose dirty data on a
normal Close. Preview mode reports that installed storage is unavailable.

Do not advertise a checkpoint capability until the production path and these
failure cases pass. ABI 1 read/write/Close numbers, structures and 4096-byte
transfer limit remain unchanged. An app cannot choose raw filesystem paths,
partitions, package identifiers or other apps' data.

## Upgrade and document layer

Retain complete previous package/data pairs through first-launch migration.
Block a second upgrade from evicting the retained pair. An explicit acceptance
must match the app's declared target schema; unknown data remains read-only.
Recovery selects a retained pair without lowering the highest accepted version
watermark or enabling arbitrary package downgrades. Define a compatibility path
for existing schema-0 byte-store apps before enabling upgraded roots for them.

Named files follow the atomic commit path through FILE4, with bounded names,
counts and separate indexes/chunks. The ABI 1 private byte store retains its own
64 KiB allocation within that index; it does not hold named-file contents.
Public schemas, enumeration, quotas and per-app import/export need integration.
Import and migration must validate a complete candidate before replacing a
committed document set. Host exchange needs separate bounded, authenticated
identity checks and must remain unavailable during conflicting foreground or
USB work. No browser storage provisioning or firmware-update shortcuts follow
from this feature.

## Qualification and integration choices

`tests/test_sdk_document_root.py` tests exact serialization, a Python SHA-256
oracle, truncation/bit corruption, rehashed invalid fields, limits and output
preservation under ASan/UBSan. It also compiles the exact FILE2 storage reader
from revision `91701e213d74918226b3692f570079c2c13d9000`. A separate littlefs
mount seeds a future root into synthetic NAND; the old reader then mounts,
refuses that app/catalog, and initializes without any flash-page or write-count
change. No parser or private member of that reader is patched for this test.

Expose first conversion through an explicit checkpoint, retaining ordinary
FILE2 behavior for apps that have never opted into it. Once an app has a FILE3
root, its later writes and upgrades must stay in the versioned transaction path.
Do not automatically convert every installed app during OS startup.

Object paths should be `objects/ID/pXXXXXXXX` and `objects/ID/dXXXXXXXX`, using
eight lowercase hexadecimal generation digits. Each path component fits the
existing name limit. A shared `apps/.pending` root is safe only because the
volume permits a single operation at a time. Checkpoints retain the current
package object, write/verify the new data object in page-sized chunks, then
write/verify/rename the root. Pending upgrades preserve their prior pair across
checkpoints. Catalog reads and foreground app state must not race that process.

The highest version means the highest authenticated package accepted for
installation, which is distinct from accepting its data migration. After a
rollback, permit idempotent installation of the active bytes but require any
different release to exceed this watermark. This avoids needing to store an
additional failed-package hash or allowing changed bytes at an existing
version. Failed immutable releases need a higher version for a retry after
rollback. Interrupted installs that never committed leave the old watermark.

A converted schema-0 app accepts a pending upgrade on a successful normal Close,
atomically with dirty data if present or through a root-only commit otherwise.
Faulted callbacks do not accept or save. The VM-only resumable runtime still
treats OS-owned Home/Close termination as successful; its forced-exit and live
checkpoint ownership policy remains part of runtime integration. If a FILE3 app's authenticated target
schema differs from the saved schema, existing byte-store writes are rejected;
reads remain available. Declared schemas above zero still require a future
explicit migration/acceptance interface. The internal Volume API implements
schema-matched acceptance and rollback with a preserved version watermark;
these operations are not yet user-facing recovery controls.

## Production qualification

`tests/test_app_documents.py` compiles the checked-in volume, transaction engine
and littlefs under ASan/UBSan against the maintained synthetic NAND backend.
It interrupts every modeled program/erase boundary, both before the operation
and after a torn operation, across conversion, checkpoint, package upgrade,
migration checkpoint, rollback, acceptance and deletion: **512 cases passed**.
Every interruption retains an old or new complete pair and preserves another
app. Corruption, generation exhaustion, full media, cancellation, empty data,
48-character IDs, repeated-save allocation and interrupted-uninstall siblings
are covered separately. The unchanged FILE2 storage and preserved-reader codec
tests pass alongside it.

The independent NAND counter measured **10,240 programmed bytes** for a checkpoint
with a **131,333-byte unchanged package**, with zero package-object bytes written.
This fixture is not a general write-amplification or timing guarantee. The host
`Volume` object occupies 21,608 bytes; ARM ABI layout and physical working-memory
budgets need their own measurements.

`vm/test-sdk-documents.py` installs a signed ARM app in synthetic NAND, seeds
the first conversion using the host-compiled production engine, then exercises
actual guest loading, normal keypad input, data-only Close, cold reopen, signed
USB upgrade and schema-0 acceptance. It checks exact package hashes and object
generations. Additional installed cases verify root-only acceptance after a
clean Close, read-only behavior for a schema mismatch, and preservation of the
pending pair after a fault following a successful staged write. Conversion
itself is not invoked through a guest checkpoint API.
Reports and captured frames are under `build/sdk-production-documents/`.

Run the scoped checks with:

```sh
.venv/bin/python -m pytest -q tests/test_app_documents.py tests/test_native_app_storage.py tests/test_sdk_document_root.py
make firmware-vm
.venv/bin/python vm/test-sdk-documents.py
make firmware
```

Build the targets sequentially because they share the generated upstream tree.
Neither target compilation nor modeled interruption proves physical NAND,
power-loss recovery or endurance. Public byte-store data remains limited to
64 KiB. The internal FILE4 chunk/index engine is implemented separately; public
descriptors, real stdio, app-visible snapshots, quotas and import/export remain
required by SDK 1.0.
