# Experimental named files

The working-tree SDK adds app-private files through service 10, API revision 2
and capability bit 8 (`NamedFiles`). Use a schema-1 manifest with `minimum_api: 2`
and required bit 8, or declare it optional and check discovery before use.
Firmware, SDK and website readers must ship together before distributing apps
that require it. Existing ABI 1 callbacks, memory limits, signatures and the
64 KiB private byte store retain their meanings.

The asynchronous service compiles into both firmware targets. The current real
newlib adapter uses the [public API 3 foreground candidate](FOREGROUND.md) for
waits, requiring minimum API 3 and capability bits 8 + 16 (mask 24). Select the
[foreground-newlib-1 profile](C-RUNTIME.md) for conventional `main`/stdio in the
ordinary SDK builder; existing callback projects keep their current startup.
Physical storage and timing remain unqualified. See [the 1.0 plan](../docs/NATIVE-APP-SDK-1.0-PLAN.md).

## Request lifecycle

Include [files.h](include/lefony/files.h); fixed-width types and errors live in
[files_wire.h](include/lefony/files_wire.h). Initialize with
`lefony_file_request(operation)` and call `lefony_files(&request)`.

1. Return 1 accepts the operation and supplies a nonzero token. Paths and write
   bytes have been copied. Do not resubmit that operation.
2. Poll using a fresh `LEFONY_FILE_POLL` request with that token. For read/stat
   output, supply a writable `buffer` and `capacity`. Return 1 means pending.
3. Return 0 delivers `result`, `error` and output `length`. A completed failure
   has result -1 and a file error. Zero error means success.
4. Negative service returns reject a request; the magnitude is a file error.
   Invalid poll buffers preserve the completion for a corrected poll. Consumed
   tokens cannot be replayed. One pending request or completion is allowed.

Callback apps return to the OS between polls; foreground programs yield. The OS advances storage outside
user execution and retains no app pointers during waits. The namespace comes
from the authenticated installed app. No caller-supplied app ID, raw flash or
other app's handle is accepted. Raw uninstalled VM loads have no file session.
Handle and request counters do not wrap/reuse tokens within an OS instance.

## Operations

| Operation | Inputs | Successful result |
| --- | --- | --- |
| OPEN | `path`/`pathBytes`, access/creation `flags` | Handle greater than 2 |
| CLOSE | `handle` | 0; a writer's staged replacement is now durable |
| SYNC (API 5, bit 64) | `handle` | 0; publishes a writer while retaining its handle, position and access flags; committed readers are unchanged |
| LIST (API 6, bit 128) | Optional directory `path`/`pathBytes`, `offset` cursor, `flags` generation | 0 plus a `LefonyDirectoryPage` of at most 16 committed children |
| SPACE (API 6, bit 128) | No arguments | 0 plus a `LefonyFileSpace` usage report |
| QUOTA (API 7, bit 256) | No arguments | 0 plus a `LefonyFileQuota` logical allowance report |
| ABORT (API 12, bit 8192) | Writer `handle` | 0; discards edits since the last commit and invalidates this writer; committed files and snapshot readers remain intact |
| READ / WRITE | `handle`, `length`; WRITE supplies `buffer` | Short byte count; READ returns 0 at EOF |
| SEEK | `handle`, absolute `offset` | New position; seeking alone does not extend a file |
| STAT | Either `handle` or `path`/`pathBytes` | 0 plus a 16-byte `LefonyFileInfo` |
| MKDIR / UNLINK | `path`/`pathBytes` | 0; removal requires an empty directory |
| RENAME | Source and destination paths/lengths | 0; atomic replacement |
| FINISH | No arguments | 0; closes readers and commits an open writer |

Unused fields are zero. Requests are 64 bytes, schema 1; transfers are at most
2048 bytes. Relative ASCII paths have at most 95 bytes overall and 48 per
component, following the [index grammar](../ports/lefony-prime-g2/ion/src/prime_g2/app_file_index.h).
Absolute paths, empty components, dot/dot-dot and embedded NUL are rejected.

Four snapshot readers and one writer may be open. A read/write handle reads its
own staging. Other readers retain their original contents and positions across
replacement, rename and unlink, pinning their chunks until closed. Additional
mutations while a writer is open fail with `BUSY`. Creation/truncation/append
requires writable access; exclusive creation also requires the create flag.

The index holds 128 entries including private bytes and 512 shared extents.
A file's nominal 64 MiB limit is further constrained by extents, the shared
64 MiB app region, other apps and retained data. Growing output preserves all
24 maintenance-reserve blocks. The quota policy below also limits growth.
Explicit host [file import/export](FILE-EXCHANGE.md) uses the same transactions.
See [storage limits](../docs/NATIVE-APP-LARGE-FILES.md).

## Directory listing and storage usage

API 6 adds declared capability 128 (`FileCatalog`) to named files. A main
program requiring these queries declares minimum API 6 and required mask 152
(8 + 16 + 128). Add bit 64 as well when live sync is required. The existing
64-byte request, transfer limit, file handles and storage representation remain
unchanged. These queries do not convert legacy storage or write flash.
An app that supports older foreground firmware can instead require API 3/mask
24 and declare bit 128 optional; the helpers then report `ENOSYS` when absent.

LIST starts with `offset=0`, `flags=0`. An empty path selects the app-private
root. A nonempty path must identify a directory. The 1,688-byte reply contains
`size`, `schema=1`, committed-root `generation`, `next`, `count`, a zero reserved
word and 16 entries. Each entry has a NUL-terminated 96-byte `path`, `kind`
(1=file, 2=directory) and logical `bytes`. Paths are relative to the app root;
only immediate children appear. Directory sizes are zero. Unused entries and
path padding are zero. The private byte store and internal storage objects are
never listed. Ordering follows the current index; alphabetical order is not
promised.

For another page, retain the same directory and pass the preceding `next` as
`offset` and `generation` as `flags`. Zero `next` ends enumeration. A nonzero
offset requires a generation. A commit or other root change invalidates earlier
pages: the request returns `CHANGED` without new entries. Restart from zero
instead of mixing generations. Staged writes do not alter the committed
listing; close/sync publishes them. Invalid directory paths return `INVALID`,
missing directories `NOT_FOUND`, and file paths `NOT_DIRECTORY`. A corrected
poll buffer retrieves the same pending reply without repeating the query.

SPACE returns 64 bytes with `size`, `schema=1`, `flags` and `generation`, then:

| Field | Meaning |
| --- | --- |
| `packageBytes` | This app's committed signed package size |
| `privateBytes` / `fileBytes` | Committed legacy-byte-store / named-file logical bytes |
| `files` / `directories` / `extents` | Committed named file/directory counts; index extents include the private byte store and are zero for unconverted legacy storage |
| `capacityBytes` | Shared allocatable capacity after excluded blocks and maintenance reserve |
| `allocatedBytes` | Shared allocated/protected flash, including metadata, retained versions, snapshots and staging already written |
| `availableBytes` | `max(capacityBytes - allocatedBytes, 0)`; not a reservation or promised write size |
| `reservedBytes` | Bytes of the fixed app region excluded from reported capacity |
| `writerBytes` / `writerCommittedBytes` | Open writer's staged logical length / previous committed length at that name |

`flags & LEFONY_FILE_SPACE_WRITER_OPEN` identifies a writer; both writer fields
are zero when none is open. Committed usage excludes its replacement until
close/sync. Available flash is shared across apps and differs from logical
bytes because copy-on-write, snapshot retention, recovery and filesystem
metadata consume space. Extent limits and commit headroom further constrain a write;
these reports do not guarantee that a proposed allocation will succeed.

The conventional runtime supplies `lefony_file_list(directory, offset,
generation, &page)` and `lefony_file_space(&space)` from `<lefony/files.h>`.
They yield while waiting and return 0 on success or -1 with `errno` on error.
Old firmware returns `ENOSYS`; undeclared capability returns `EACCES`; changed
generations return `ESTALE`; wrong directory type returns `ENOTDIR`.
The directory helper accepts `""`, `"."` and leading `./` for the root, or a
directory path with one trailing slash. It rejects absolute paths and traversal.
These helpers do not implement POSIX `opendir`/`readdir` or expose other apps'
names. Callback apps use the asynchronous wire operations directly.

Index loading and shared allocation traversal still run synchronously inside
the OS poll. Page and transfer limits bound returned data; they do not establish
a physical latency budget.

## Durability and cleanup

Writes, append and zero-filled gaps remain staged until CLOSE or SYNC succeeds. RENAME
atomically replaces files or empty directories of the same kind; old snapshot
readers remain valid. Failure/cancellation before the root commit preserves the
previous root. Cleanup drains operations past that point; it cannot undo a
committed result.

SYNC is additive operation 11 in the unchanged 64-byte request. Declare
capability 64 along with named files (8). A conventional main program that
requires live saves uses `minimum_api: 5` and required mask 88 (8 + 16 + 64).
Optional bit 64 allows a checked fallback on older firmware. SYNC preserves
the descriptor and position, including a seek beyond EOF, and keeps append
semantics for future writes. Readers opened earlier retain their old snapshot;
new readers see the committed data. Other mutations remain blocked while the
writer stays open. SYNC is a single-file commit, not a multi-file transaction.

The OS commits the current root, then reopens from it for the next edits.
Success means both commit and reopen completed. If either fails, the writer
handle is invalidated and the request returns an error. The commit may already
have become durable before a reopen failure: reopen and inspect the file before
retrying an ambiguous save. Cancellation cannot undo a completed commit.

Home, faults and unloading abort edits since the last commit and invalidate handles.
Cleanup keeps storage ownership until it drains, excluding installer operations
and catalog refresh from live app scratch. Initial conversion uses previously
committed private bytes, never staged app edits. Writes reject saved/app schema
mismatches unless the app explicitly enters the [API 8 migration mode](DATA.md).
That controller requires all descriptors to be closed and preserves the previous
compatible package/data pair until explicit acceptance. The explicit
[host recovery commands](DATA-RECOVERY.md) can roll back this retained pair.

Legacy callbacks preserve private-data save-on-Close behavior. The public
foreground profile discards staged private bytes on Home, faults or nonzero program
exit. Completed file commits remain durable. Newlib `exit` cleans up streams
before `_exit`, including on nonzero exit, so its closes may commit files.
`_exit` alone cannot retrospectively abort those commits.

## Explicit writer cancellation

The local API 12 candidate adds operation 15 (`LEFONY_FILE_ABORT`) and declared
capability 8192 (`FileAbort`). Existing operation numbers, 64-byte request layout,
ABI 1 and storage formats are unchanged. A conventional main app requiring this
operation declares minimum API 12 and mask 8216 (8 + 16 + 8192). Additional
capabilities such as quota queries are negotiated independently.

`lefony_file_abort(descriptor)` returns 0 after discarding this writer's edits
since the last successful close/sync. It invalidates the descriptor and preserves
committed contents, the root generation and other open readers. A new file that
was never committed remains absent. A successful earlier `fsync` cannot be undone.
Aborting a failed writer releases it for a new attempt. Cleanup yields while the
OS drains staged work; the function does not establish a physical latency bound.

Older firmware returns -1 with `ENOSYS`; undeclared capability returns `EACCES`.
A reader, stale or invalid handle returns `EBADF` without closing a valid reader
or a newer writer. Other errors must be checked: do not fall back to close when
the intention is to discard. Callback applications submit ABORT/POLL through the
ordinary request lifecycle and may cancel only after any earlier request's
completion has been consumed.

For C++, [file_writer.h](include/lefony/file_writer.h) provides
`Lefony::FileWriter`. `begin(path)` opens a staged replacement of the destination;
`write(bytes, count)` handles short writes; only successful `commit()` publishes.
`cancel()` and destruction request abort, and write errors trigger cancellation.
`error()` retains the first write/cancel failure. Beginning while active returns
false with `EBUSY`. Before opening, the adapter probes abort authorization with
invalid handle 0; unsupported or undeclared abort cannot silently create a
writer that may publish on cleanup. The helper uses no stdio buffer or allocation.

Replacing the destination directly credits its previous length toward the
logical quota. A separately named temporary file consumes additional logical
usage; rename cannot prevent that earlier allocation failure. Shared physical
space and transaction headroom still constrain replacements. Notebook 0.6 and
Link Gallery 0.2 use direct staged replacements and retain the previous document
or image until commit. Link Gallery validates its complete streamed image before
committing it. These app integrations have local full-quota ARM evidence; see
the SDK ledger for exact candidates and remaining resource/physical qualification.

Do not describe a failed commit as proof that the previous data is intact:
an I/O error may occur after the atomic commit point. Reopen and inspect the
destination before retrying an uncertain save. Home/fault cleanup remains
OS-owned and cannot undo an acknowledged commit.

The raw C helper also accepts `fileno(stream)`. After a successful abort,
`fclose(stream)` releases the libc buffer but returns an error because its
descriptor is invalid; it cannot publish those buffered bytes. Do not use that
stream again or double-close its descriptor. Abort does not require flushing:
both already-flushed staging and still-buffered bytes can be discarded. Prefer
descriptor writes or `FileWriter` when partial data must never publish during
ordinary stream cleanup. An abort failure requires handling before assuming
anything has been discarded.

## C adapter and evidence

[the SDK newlib file adapter](lib/newlib/files.c) supplies real descriptor/error
adapters, including `_rename_r` to replace the pinned library's link/unlink
fallback. Standard input/output/error are not file handles; console support is
separate. Unsupported output fails instead of reporting a successful no-op.

The tested stream profile includes binary read/write/update, short transfers,
buffering, seek/tell, backpatches, EOF/errors, stat and checked close/rename.
`fflush` sends libc buffers to staging; it does not promise durability. Check
`fclose`, or use `fflush(stream)` followed by `fsync(fileno(stream))` and check
both results before reporting a successful save. Define `_POSIX_C_SOURCE`
as `200809L` before system headers to expose `fileno` in strict C11 builds;
include `<stdio.h>` and `<unistd.h>`. This exposes declarations, not a claim of
general POSIX support. `fsync` returns -1/`ENOSYS` when firmware lacks sync; undeclared bit 64
returns -1/`EACCES`. A stale/invalid descriptor returns -1/`EBADF` on supported
firmware. It does not flush C library buffers on the caller's behalf.

The C adapter accepts up to 128 leading `./` segments and one trailing slash
for `mkdir`. The resulting relative name still follows the unchanged OS grammar
and length limits. Other operations retain trailing-slash rejection; absolute
paths, parent traversal and internal dot components are unsupported. This does
not add a current-directory service. The ARM stream probe exercises these path
forms and confirms that an invalid file path does not truncate an existing file.

The [ARM proof](experiments/files_probe.c) now builds through the ordinary SDK
profile and processes 261,925 input bytes with an
output stream open simultaneously, backpatches its header, closes and atomically
replaces the destination. A cold ARM reopen and independent host export/oracle
verify the result. [Lifecycle cases](../vm/test-sdk-file-lifecycle.py) cover
clean/nonzero exit, Home and faults with same-OS relaunch. These are platform
fixtures, not substitutes for the required C tool and playable Doom.

The [live-sync ARM proof](../vm/test-sdk-file-sync.py) checks repeated
`fflush`/`fsync`, snapshot isolation, Home/fault/immediate exit and cold reopen,
plus capability denial and older-firmware `ENOSYS`. Its host oracle verifies
8,197 saved bytes after each forced exit. The session fixture also checks
cross-chunk edits, append, seek beyond EOF, I/O failure and 44 simulated clean
or torn interruptions around sync. See the implementation ledger for exact
firmware hashes and the distinction between these model checks and hardware.

Content work advances in 2048-byte steps; index loading and allocation traversal
remain synchronous. Transfer limits do not establish a physical latency bound.
This experimental interface does not complete SDK 1.0 qualification.

## Per-app quota policy

API 7 enforces **32 MiB (33,554,432 bytes) of mutable data per app**: the sum
of current named-file lengths and the private byte store. The policy applies to
all callers of the file engine, including older apps; declaring a capability
is necessary only to use the new query. The legacy private byte store still
has its independent 64 KiB maximum. Packages, directory/index metadata, retained
roots, open snapshot readers and staged copies do not count toward logical usage;
they still consume shared physical capacity and maintenance headroom.

The initial limit fits the pinned 28,795,076-byte Doom WAD and its current saves
while keeping one app's normal mutable-data allowance below the shared region.
This is a fixed development policy, with no app or website override. It does
not reserve flash or guarantee that a write of the reported allowance will fit:
other apps, retained data, index extents and flash overhead may cause `ENOSPC`
or `EFBIG` earlier. Use SPACE for the separate shared-capacity report.

Already committed roots above the limit are preserved. They remain readable,
allow in-place edits and replacements up to their committed logical size, and
can shrink. They cannot grow further. After each commit (including live sync),
the next transaction uses `max(32 MiB, committed usage)` as its ceiling. Once
usage drops below 32 MiB, the ordinary limit applies. This policy never deletes,
truncates or converts saved data merely on inspection or mount.

Known-length creation/replacement and private checkpoints reject excess growth
before writing. Streaming writes may return a short count up to the allowance;
the next nonempty write beyond it reports `LEFONY_FILE_QUOTA_EXCEEDED` (16),
mapped to `EDQUOT` by the current newlib adapter. A seek alone does not allocate
or consume quota. A write starting past the allowed end fails before creating
its zero-filled gap. As with other file I/O failures, the public writer becomes
failed: close/sync aborts its uncommitted replacement and reports the error.
Previously acknowledged saves remain committed. Close the failed descriptor,
free space or reduce output, then start a new attempt. Older linked runtimes
without the new errno mapping may report their generic I/O error instead.

`lefony_file_quota(&quota)` requires named files (8), foreground execution (16)
for the synchronous helper, and quota queries (256): minimum API 7, mask 280.
Add live sync (64) for mask 344. Catalog queries (128) remain independently
negotiated. Older firmware returns `ENOSYS`; missing declared capability returns
`EACCES`. Raw asynchronous callers use QUOTA/POLL with the usual copied-buffer
ownership and retry semantics. The existing SPACE and request layouts are unchanged.

The zero-initialized 48-byte schema-1 `LefonyFileQuota` contains twelve uint32s:

| Field | Meaning |
| --- | --- |
| `size`, `schema`, `generation` | 48, 1 and the committed root generation |
| `flags` | `1`: writer open; `2`: committed usage exceeds policy; `4`: writer failed |
| `limitBytes` | Configured policy limit, currently 33,554,432 |
| `committedBytes` | Named files plus private bytes in the current root |
| `projectedBytes` | Committed total with the open writer's previous length replaced by its staged length; otherwise equals committed |
| `ceilingBytes` | Maximum logical total for this transaction or the next writer |
| `remainingBytes` | `ceilingBytes - projectedBytes`; logical allowance, not guaranteed flash space |
| `reserved[3]` | Zero |

A failed writer's projected length is diagnostic staging that will be discarded;
its remaining allowance does not authorize continuing that descriptor. Truncating
an existing file initially increases projected allowance without changing committed
usage. Quota inspection is read-only even for legacy storage and schema-mismatched
apps. It exposes only the authenticated app's logical usage.


Explicit host-side [file import/export](FILE-EXCHANGE.md) is available in the
matching USB development candidate. It uses the same file transactions and quota
policy, requires the app to be closed, and is independent of app package install.
Whole-app [archive/restore](ARCHIVES.md) is available as a separate host workflow.
The [host data commands](DATA-RECOVERY.md)
provide private-byte backup/restore and retained-pair rollback. The
[private-data controller](DATA.md) supplies app-side checkpoints and migration.
