# Replicated app ownership records

Status: FILE5 integration candidate. Both firmware targets compile; host
interruption and signed archive tests and six ARM SDK recovery cases pass.
Exact validation for this candidate is recorded separately in the
[implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md). Existing downloads and
physical storage are not qualified by those host tests.

## Storage contract

The canonical `apps/<id>.app` record selects the current and optional previous
package/data pair and retains the highest accepted package version. Losing it
loses ownership and downgrade history; surviving signed packages alone cannot
reconstruct that history safely.

FILE5 keeps two identical copies of that complete record: a 352-byte file payload
and littlefs custom attribute `0x52` on the same file. The payload exceeds the
production 256-byte inline limit, placing it in a separate data block. The
attribute resides in directory metadata. This provides recovery from loss of
one copy while the filesystem and the file's directory metadata remain readable.

All integers below are unsigned little-endian values.

| Offset | Bytes | Field |
| --- | --- | --- |
| 0 | 8 | `LFAFILE5` |
| 8 | 4 | Storage envelope version 5 |
| 12 | 4 | Complete envelope size 352 |
| 16 | 64 | App ID, NUL terminated and zero padded; existing 48-character limit |
| 80 | 240 | Complete logical FILE3/FILE4 root, including its existing digest |
| 320 | 32 | SHA-256 of bytes 0–319 |

The logical root format, signed package format, archive format, app ABI/API,
file indexes, private-data contracts and 64 MiB storage geometry retain their
meanings. FILE5 is an intentional new canonical storage representation.

The writer attaches the attribute with `lfs_file_opencfg`, writes the payload,
closes, verifies both identical copies, and atomically renames the pending file
over the canonical path. The pinned littlefs API commits configured attributes
atomically with file contents at sync/close; this avoids independently updated
mirrors. See the [pinned upstream API](https://github.com/littlefs-project/littlefs/blob/6cb4e86540eca0d9ba62500a298385c9d863c8be/lfs.h).
The firmware implementation is
`ports/lefony-prime-g2/ion/src/prime_g2/app_root_record.cpp` in the OS repository.

## Read and repair behavior

- Two valid identical copies return the complete root.
- One valid copy can recover from a missing/corrupt other copy or a payload
  media read failure. Reads never rewrite storage automatically.
- Two valid but different copies fail. The reader never selects the higher
  serial or discards a conflicting version history.
- A self-consistent unsupported format or valid record for another app fails,
  even when the other copy is valid for this app.
- Both copies lost, unreadable directory metadata and unmountable volumes remain
  outside this recovery path. Already-lost FILE3/FILE4 sole roots cannot acquire
  protection retroactively. The occupied namespace is never treated as empty.

Digests establish record integrity, not publisher authority. Package hashes,
signatures, execution/inspection key policy, current signer ownership and the
full version high-water mark still govern install, export and restore.

Every successful document/file/archive root commit writes FILE5. Healthy old
roots migrate on the next such commit; there is no bulk startup rewrite. Normal
FILE2 package/private storage remains readable and converts through the existing
document/file workflow. Older firmware cannot read FILE5 roots, so keep matching
firmware after migration and export verified portable archives before a firmware
downgrade. An archive preserves logical data without depending on FILE5.

`archive info` reports root protection with matching firmware. To repair a
degraded root explicitly, close the app, export a verified complete archive,
then restore that archive with `--replace`. The existing restore transaction
rebuilds both root copies and preserves the archive's signed packages/data and
the calculator's version history. The [SDK guide](../sdk/ARCHIVES.md#root-protection-and-repair)
documents commands and failure handling. This uses the existing signed restore
workflow; it does not grant new key or ownership authority.

## Negotiated diagnostics

Host hello bit 32768 advertises root inspection. Request flag 8 is valid only
for archive Inspect and may be combined with RepairCode flag 4. It retains the
192-byte schema-1 Info or 256-byte schema-2 RepairInfo layout. Only a request
with flag 8 receives the following additional Info flags:

| Flag | Meaning |
| --- | --- |
| 64 | FILE5 replicated root |
| 128 | Valid payload copy |
| 256 | Valid metadata-attribute copy |

A replicated root needs at least one valid copy. A successful legacy inspection
returns none of these flags. Old requests retain their original flag set.
The SDK reports `root_protection` as `both`, `payload-only`, `metadata-only` or
`single`; absent apps and older firmware return `null`. These flags describe
record redundancy, not authentication or a complete media-health scan.

## Cost and validation

Each protected root adds one 128 KiB data block, plus directory metadata. A
pending replacement needs another block until commit. Admission includes that
block before starting document/file/archive writes and retains the existing
24-block maintenance reserve and per-app logical quota. Physical allocation
queries include the new cost; package download size does not describe it.

The production-geometry fixture measures 1, 8, 32 and 64 roots, including actual
programmed bytes and erase/program calls. Metadata splits make the total cost
larger than just the payload blocks. Host fixtures also retain genuine legacy
roots, exercise full/torn commit interruptions, preserve outputs on failed reads,
and test signed archive recovery, conflicting copies, revoked keys, different
signers and downgrade-history enforcement. Reports live under
`build/sdk-root-recovery/`; run the tests listed in the ledger for current evidence.
Emulator evidence does not prove NAND endurance or physical power-loss behavior.
