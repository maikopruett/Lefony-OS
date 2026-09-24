# Production large-file storage

Status: internal production-volume implementation, 2026-09-12. This uses the
existing shared littlefs/NAND backend and 64 MiB region. Host tests stream the
pinned Freedoom WAD, verify cold reads against an independent SHA-256 oracle,
and verify partial edits. The [API 2 file session](../sdk/FILES.md) now exposes
authenticated asynchronous handles and real newlib stdio in the VM execution
profile. Physical conventional execution, quotas and import/export still need
implementation/qualification. The representation below is shared by both targets.

## Representation

`LFAFILE4` retains the 240-byte root layout, SHA-256 seal, version watermark and
current/previous pairs from [document transactions](NATIVE-APP-DOCUMENT-TRANSACTIONS.md).
The root version is 4. Each pair's formerly reserved word at offset 20 is its
data kind: 0 is the existing byte store; 1 is an immutable file index. FILE3
continues to require zero there. FILE4 can retain a raw FILE3 pair while its
current pair uses an index, preserving recovery during conversion.

Indexes use `objects/ID/dXXXXXXXX` and are bound by the root hash. The wire layout
is little-endian, with these explicit bounds:

| Record | Layout |
| --- | --- |
| Header, 32 bytes | Eight magic bytes `LFAIDX1\0`; uint32 version 1, entry count, extent count and three reserved zero words |
| Entry, 128 bytes, at most 128 | NUL-padded 96-byte path; uint32 kind, byte length, first extent, extent count; 16 reserved zero bytes |
| Extent, 48 bytes, at most 512 | uint32 generation, part, object type, byte length; SHA-256 |

An index is at most **40,992 bytes**. Entry zero preserves the ABI 1 private byte
store, up to 64 KiB. It initially references the existing raw data object; later
saves can reference a chunk. These bytes do not contain the index or named files.
The other 127 entries hold files/directories. Paths are case sensitive, at most
95 bytes overall and 48 per component, using ASCII letters, digits, spaces,
dot, underscore and hyphen. Absolute paths, empty/dot/dot-dot components,
missing/non-directory parents and duplicate names are rejected. Contents are
arbitrary bytes.

Entry kinds are 1 for files, 2 for directories and 3 for the reserved private
byte store. Extent object types are 0 for an existing raw data object and 1 for
a chunk. Raw data-object references are allowed only in entry zero.

Chunks use `objects/ID/cXXXXXXXX.YYYYYYYY`: generation and nonzero part number
in lowercase hexadecimal. Each holds at most **130,944 bytes**, chosen to fit
one erase block with conservative overhead. Only the final extent is shorter.
Committed chunks are immutable. The internal 64 MiB file-length ceiling is not
a promise of 64 MiB usable space: packages, other files, metadata and retained
generations share the fixed region.

Older FILE2 and retained FILE3 readers reject FILE4 without formatting or changing
synthetic NAND. Unknown versions, kinds, noncanonical padding, extents and paths
fail closed. Storage profile, USB wire version, partition, ABI and trust roots
are unchanged.

## Transactions and readers

`AppFileStore::Store`, owned by `AppStorage::Volume`, supports streaming
creation/replacement, seek/read, same-length range edits, directories, deletion
and rename. Replacements can change length; range edits stay within the existing
length. Rename requires an absent destination. Nonempty directory deletion and
moving a directory into itself are rejected.

Before writing, the engine validates committed pairs and extents, then collects
unreferenced objects. Admission runs **after collection**, so abandoned chunks
cannot prevent an otherwise feasible retry. It counts actual allocation plus
new chunks, an index and metadata headroom. Per-app quotas and guaranteed
rollback capacity remain unfinished.

Allocated/free-space accounting includes the physical file objects. The existing
catalog's logical-used-byte total still counts packages and the legacy byte
store; named-file usage, public metadata/enumeration and per-app space reporting
need integration with the public file API.

Input calls accept at most 2048 bytes, potentially fewer at a chunk boundary.
Polling copies unchanged boundary bytes for range edits, seals/readback-verifies
changed chunks, and commits a verified index through the atomic root rename.
Untouched chunks keep their references. Old and new references survive through
commit; later collection reclaims obsolete objects. Interruption exposes the
complete old or new namespace, never a mixture.

The original single-stream reader remains as an internal compatibility helper;
it blocks mutations and verifies each newly entered chunk synchronously. The
volume now also owns **four independent snapshot readers** alongside its writer.
Each reader copies a file's validated extent references, owns a separate littlefs
file/cache and position, and keeps those chunks alive during collection. Existing
readers see their original contents after replacement, rename or unlink. New
opens see the committed namespace. Uninstall rejects an app with live readers;
closing the last reader allows later collection to reclaim obsolete chunks.

Snapshot tokens are checked against their owner namespace and are not reused
during a volume lifetime. Close/remount invalidates them, including when closing
during verification or after a read failure. The future app facade must derive
that namespace from the authenticated running app and close its handles on all
exit paths. These internal methods do not expose a guest syscall.

`readSnapshot` returns at most 2048 bytes, a short chunk-boundary transfer, EOF,
an error, or a pending result. Pending verification keeps no caller pointer and
advances at most 2048 content bytes per `stepSnapshot`. A caller retries after
verification completes; no unverified bytes reach its output. Seek is available
when ready, including beyond EOF. Root/index acquisition at open is still
synchronous, and littlefs metadata traversal can require multiple backend reads.
This content-work bound is not a physical privileged-latency guarantee.

### Growing output and random access

`beginStream` now starts a writer without a declared output length. Truncate
creates or replaces a file; update requires an existing file; append creates
when needed and places each write at the current end even after a seek. The
writer supports bounded reads of its own staged contents, seek/tell, header
backpatches and growth. Seeking alone does not extend the file; a later write
materializes zero-filled gaps. Transfers can be short at a chunk boundary.
The existing bounded index/region limits still apply.

The writer retains one 130,944-byte chunk buffer, shared with the commit-index
wire buffer because publication ends the stream. Loading, zeroing, writing and
readback verification advance in at most 2048-byte content steps. Pending calls
consume no caller data and retain no caller pointer. Changing cached chunks
flushes dirty data first. Dirty chunks use this transaction's new generation and
the chunk's ordinal part number. Repeated backpatches may rewrite those staged
objects; committed objects remain immutable. The new index becomes authoritative
only through the existing root transaction. Cancellation/failure before that
point leaves the previous committed contents intact.

Capacity admission checks actual allocated blocks before each flush and before
publication, reserving an index and metadata headroom. Growing user output also
preserves the volume's 24 maintenance-reserve blocks, which remain available to
package updates and recovery. Storage may fill after a
write was accepted into RAM; the later flush/commit then reports failure instead
of publishing a partial file. Internal failures expose littlefs error codes,
including no space and file-size limits. Admission/index work still includes
synchronous metadata traversal, so the content-step bound does not establish
a physical latency budget or complete quota policy.

The host acceptance case now reads an input while producing variable-length
output and backpatching its header, then checks the cold output against an
independent Python SHA-256 oracle. Another case rewrites a staged chunk 520
times without exhausting part numbers. The pinned WAD also uses `beginStream`
without passing its length. These exercise the production engine on synthetic
NAND; app-owned public descriptors, asynchronous open/completion, scheduler and
lifecycle integration, stdio/errno mapping and latency qualification remain
unfinished. This is not yet a conventional minigzip or Doom guest-I/O proof.

Cancellation before root commitment preserves the old root. Root commitment
and uninstall-after-unlink remain past the cancellation boundary. Named files
survive ABI 1 private-data saves and package upgrades. A future public migration
interface must authenticate the loaded app's target schema before granting writes.

## Local evidence and commands

The host fixture compiles the real volume, file/transaction engines and littlefs
under ASan/UBSan against synthetic NAND. **630 interruption cases** cover creation,
cross-chunk edits, rename, file deletion and uninstall. Additional cases cover full media,
corrupt chunks, an unavailable free block, cancellation/retry, EOF/seeks,
directories, private-data coexistence, file restoration after package rollback,
and retry after abandoning 36 MiB of a
48 MiB stream. Codec tests cover truncation, bounds, noncanonical fields, paths
and explicit FILE4 negotiation.

The Freedoom Phase 1 0.13.0 WAD is **28,795,076 bytes**, SHA-256
`7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d`.
It was streamed through 2048-byte input buffers and cold-read to that exact hash.
A 37-byte edit wrote 130,944 chunk bytes and programmed **159,744 NAND bytes**
including metadata. The entire edited file matched an independent Python hash:
`ae61ff409f1ef40e4aac2d6b830b9e866762c9612456e6f78ddb1adb2821c5b6`.
Unchanged package bytes were not rewritten. Before independent snapshot readers,
the host `Volume` occupied 262,416 bytes including indexes/caches; the stream
buffer was not its complete memory footprint. That physical-target symbol
occupied 262,088 bytes; the corresponding VM reported
19,818,464 bytes reserved for the kernel heap and the unchanged 8,380,416-byte
experimental app heap. All five allocation/guard/pixel cases pass on that VM.
These measurements do not qualify physical timing or endurance.

The snapshot-only candidate's host `Volume` occupied **378,464 bytes**, including
four **29,000-byte** readers. Its ASan/UBSan fixture copies and transforms a
261,925-byte input while writing another file, cold-reopens and checks every
output byte against an independent pattern, and checks reader isolation,
stale tokens, exhaustion, seeks/EOF, corruption and cancellation during
verification. Old unread chunks remain available across replacement, rename,
unlink and later commits; collection reclaims them after close. Cross-chunk
interruption cases now keep a snapshot open during the patch. Full-media failure
also preserves a live reader. See the [current ledger](NATIVE-APP-SDK-1.0-PROGRESS.md)
for final target identities and validation limits.

The growing-writer candidate's host `Volume` occupies **468,456 bytes**. Its
130,944-byte writer cache replaces the 40,992-byte index wire allocation and adds
small control fields, for a net **89,992-byte** increase. The host fixture adds
**718 interruption cases** for growing output/backpatches and extending an
existing file, alongside the earlier 630 FILE4 cases. Full-media growth aborts
without publishing the output, preserves committed files and permits a smaller
retry after collecting abandoned chunks. A maximum-size package upgrade and
compatible rollback are admitted after full-media staging fails, with the
maintenance reserve still available. See the ledger for current firmware
memory measurements; physical durability remains unqualified.

```sh
.venv/bin/python -m pytest -q tests/test_app_file_index.py tests/test_app_files.py tests/test_sdk_document_root.py
.venv/bin/python tests/test_app_files.py --wad build/sdk-1.0-upstream/freedoom1.wad
make firmware-vm
.venv/bin/python vm/test-sdk-documents.py --files
make firmware
```

The WAD command uses the verified cache from [the Doom fetch recipe](../sdk/ports/doom/README.md).
Default host CI uses synthetic bytes and needs no game data. The optional command
`.venv/bin/python tests/test_sdk_document_root.py --previous-file3 build/sdk-large-files/old-file3`
checks the exact prior generated reader sources, preserved after verifying their
earlier sealed hashes. That local fixture is not a default-CI requirement.

The ARM script seeds FILE4 and an asset using the host-compiled production engine,
then exercises signed ARM byte-store saves/upgrades while checking the asset's
complete hash. It does not expose a guest named-file syscall. Reports are under
`build/sdk-large-files/`. Public APIs, stdio, import/export, hardware durability
and the complete Doom workload remain SDK 1.0 requirements.
