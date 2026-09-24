# Whole-app archive implementation

Status: live integration candidate in the working tree. The host validator,
export/restore engines, exclusive USB session and [SDK commands](../sdk/ARCHIVES.md)
are implemented. Host, production-filesystem and eight signed ARM/USB journeys
pass; exact evidence is recorded in the implementation ledger. This does not
qualify existing downloads or physical backup/restore.

The later [FILE5 root-recovery candidate](NATIVE-APP-ROOT-RECOVERY.md) allows
these same authenticated export/restore engines to use a surviving canonical
root copy. It adds negotiated diagnostics, preserves complete ownership and
version history, and leaves the portable archive format unchanged. It cannot
reconstruct ownership when neither copy survives.

## Portable contents

An archive contains one app ID, its version high-water mark, and a current
signed package with its private bytes and named files/directories. A pending
upgrade also contains the previous compatible package/data pair. A completed
upgrade has one pair. Stored icons attached separately by the store are not
included in this format.

The binary representation uses little-endian integers and these fixed records:

| Record | Size | Contents |
| --- | --- | --- |
| Archive header | 128 bytes | `LFARCH1`, schema/size/total bytes, one or two pairs, pending flag, version high-water mark, app ID and zero reserved fields |
| Pair header | 128 bytes | Package/private lengths, data schema, named-entry count, package version and SHA-256 hashes of package/private bytes |
| Named entry | 112 bytes | Zero-padded relative path, file/directory kind, content length and zero reserved fields |

Each pair header is followed by the signed LFAPP1 package, private bytes, then
its named entries. Each file entry is followed by its contents and a 32-byte
SHA-256 trailer. Directories have neither contents nor a trailer. Putting the
file digest after its contents permits a single streaming export pass. Empty
files still have the SHA-256 digest of empty contents.

Paths follow the existing FILE4 path grammar. Each pair allows 127 named
entries plus the private byte store, up to 512 independently chunked extents,
at most 64 KiB of private bytes and at most 64 MiB total mutable bytes. Actual
restore remains subject to the app quota and available flash/headroom. Package
size retains the existing signed-package bound. Package identity and numeric
version must agree with the archive; the retained version must be older than
the current version. Only a pending current pair may carry data awaiting its
package's schema migration.

Archives contain no filesystem generations, object addresses, device identity,
developer trust enrollment or private keys. Content hashes establish integrity,
not authority to execute code or ownership of user data. The selected package
keys must independently authenticate the signed packages.

## Restore engine

The internal [restore engine](../ports/lefony-prime-g2/ion/src/prime_g2/app_archive_restore.h)
accepts bounded input and performs filesystem writes/verification in chunks.
Package scratch belongs to the exclusive OS operation owner. The engine itself
uses fixed-capacity storage, including one file chunk and four bounded indexes;
it does not buffer a whole named file or whole archive.

The owner must authenticate the existing namespace independently of potentially
damaged user data, enforce signer/version/schema policy, supply the current
quota and actual allocation admission, and prevent concurrent volume operations.
It must bind the canonical namespace/generation and trust state before starting
and again when committing. These are mandatory internal callbacks, never
host-provided policy. The live AppManagement session owns these checks and
excludes simultaneous app/file/key mutations.

Incoming packages, indexes and new file chunks use generations beyond the
installed root. Verified unchanged chunks can be reused from either installed
pair or the already staged current pair. A hash match in an old index is not
sufficient: the engine reads and hashes the actual chunk before reusing it.
Damaged candidates are skipped and the incoming bytes are written instead.
References cannot be duplicated within one index.

Only after all declared bytes, hashes, paths, index bounds and signed packages
pass can the operation become ready to commit. The document store then verifies
both incoming pairs and their referenced chunks before publishing through its
existing atomic root rename. This path neither verifies damaged old data as a
prerequisite nor collects any replaced object before commit. The high-water mark
is preserved. A legacy FILE2 canonical file remains intact until the same rename.

Cancellation or failure before commit removes staged objects in bounded steps.
Entering the commit boundary stops cancellation. An I/O failure during rename
is reported as an unknown commit outcome, and its possibly referenced objects
are retained for readback/recovery. Old objects left after successful replacement
can be reclaimed by ordinary verified document transactions.

The [host parser](../sdk/tools/archive_format.py) validates an open regular file,
uses bounded reads, checks all contents and returns exact spans plus the whole
archive hash. It reports whether signatures were verified; structural inspection
alone does not authenticate packages. The SDK transfer holds the same file
descriptor, and firmware independently checks the received digest and its own
trusted signing keys.

## Host session

Hello flag 1024 negotiates this host-only extension. App API 11, ABI 1, package
formats and storage geometry retain their meanings. Commands are scoped to one
canonical app ID, root generation, sequence and random 16-byte host nonce:

| Request | Direction | Meaning |
| --- | --- | --- |
| `0x90` | IN | 112-byte status, including operation, state, offset, generation, whole hash and nonce |
| `0x91` | OUT | 144-byte inspect/export/restore request |
| `0x92` | IN / OUT | At most 512 export bytes, or a 24-byte binding followed by at most 488 upload bytes |
| `0x93` | OUT | 24-byte sequence/next-offset/nonce acknowledgement of export bytes |
| `0x94` | OUT | Commit the fully verified restore, bound to sequence and nonce |
| `0x95` | OUT | Cancel that sequence and nonce before acknowledged commit |
| `0x96` | IN | 216-byte verified recovery-pair approval identity, keyed by sequence; requires hello flag 4096 |

The 192-byte inspection result authenticates package metadata independently of
mutable data. `index_known` means usage metadata was decoded; it is not a claim
that every saved byte has been verified. Export performs that content check.
The canonical stat also prevents ordinary installation from taking over a
damaged namespace omitted from the executable catalog. Unrelated valid apps
remain available when an entry's index or saved data is damaged.

OUT operations only advance after the USB status acknowledgement. Repeated
reads do not consume output. Unacknowledged writes, mismatched nonces/offsets and
stale generations cannot advance a session. Waiting export/upload/commit-ready
sessions expire after 30 seconds without progress. Active bounded filesystem
work is polled independently of that idle deadline. Acknowledged commit cannot
be cancelled by reset; uncertain publication retains possibly referenced objects.

## Fresh recovery-pair consent

Hello flag 4096 adds restore request flag 2 (`AllowRecoveryPair`), status state 8
(`AwaitUser`), status flag 4 (`RecoveryPair`), error 16 (`Denied`) and the
read-only `0x96` approval record. Existing
wire structure sizes and values remain unchanged. Older firmware rejects the
new request flag; the SDK discovers support before issuing any archive request.

The flag is allowed only on restore and only when the destination namespace is
absent. Both packages must authenticate under the calculator's existing keys;
the current key must permit execution. The new grant requires both signers to
be developer keys, excluding compiled store roots and the emulator fixture.
Different retained authority can stage
only with this flag, then enters `AwaitUser` after full archive verification.
Existing namespaces continue to require their current signer and exact previously
authorized retained package; the new flag cannot bypass either ownership check.

The 216-byte little-endian record consists of four uint32 fields (size 216,
schema 1, sequence, zero reserved), current and previous version triples, the
zero-padded 64-byte app ID, current signer, retained signer and archive hash
(32 bytes each), and the 16-byte nonce. The SDK checks every field against the
validated open archive and session before displaying the host prompt. Status
flag 4 persists through approval and commit so early physical approval cannot
skip the host identity check; committed recovery-pair restores report flags 5.

The OS opens its approval view only from Home, outside exam mode and with no
open app. It shows all identities and explains that rollback restores the old
signer. A rendered screen, an all-up physical keyboard scan and then physical
OK are required. No USB request approves the pair. Consent has a two-minute
expiry; approval rechecks canonical source/trust and only makes the session
commit-ready. The normal separately acknowledged commit retains its own checks
and 30-second idle expiry. Dismissal or reset before acknowledged commit removes
staged work. Acknowledged commit continues to completion across reset.

The key registry is unchanged. A revoked retained key remains inspection-only
until explicitly reenrolled, including before rollback to its package. No private
key or trust enrollment is imported from the archive.

## Remaining integration and qualification

The explicit unreadable-code repair path is implemented as described below.
Evolving [preview data retention](../sdk/UI.md) now uses
verified archives in fresh synthetic installations. Broaden large
archive/resource coverage and finish clean-host bundles. Physical media,
power-loss behavior and native USB timing remain separate gates.

Production-filesystem tests live in
[the native fixture](../tests/native/app_archive_restore.cpp), driven by
[the host test](../tests/test_app_archive_restore.py). Format and authenticity
cases are in [the parser tests](../tests/test_sdk_archive.py). Live session cases
are in [the session fixture](../tests/test_app_archive_session.py), host transport
and CLI cases in [the device tests](../tests/test_sdk_archive_device.py), and the
signed ARM workflow in [the USB journey](../vm/test-sdk-archives.py). Exact completed
checks and their limitations belong in the
[implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).

The [canonical-media journey](../vm/test-sdk-archive-media.py) uses a normally
installed signed app and SDK commands over the modeled USB path. A transient
uncorrectable read of its FILE2 canonical header makes ordinary/repair
inspection, export preflight and repair-restore preflight report storage I/O
failure. They preserve both synthetic flash and any previous host destination.
Clearing the fault restores inspection and byte-identical export; the sequence
also passes after a cold restart. Host filesystem tests separately cover loss
of both metadata copies holding an inline FILE3 root. This checks diagnosis and
safe refusal, not recovery when ownership proof is permanently lost.

## Unreadable-code repair

Hello flag 8192 adds request flag 4 (`RepairCode`) for inspection/restore and
status flag 8 (`CodeRepair`) for restore. A restore must also set `Replace` and
must not set `AllowRecoveryPair`; its destination must exist and its installed
code must be unavailable. Old clients retain the ordinary 192-byte inspection
and refusal behavior. The SDK discovers support before sending repair requests.

Explicit repair inspection returns 256 bytes with size 256/schema 2: the same
192-byte information fields, followed by the FILE2 combined digest and signed
prefix digest (32 bytes each). Flags 8/16/32 mean code unavailable, legacy proof,
and readable prefix respectively. Unknown signed version/schema/signer fields
are zero on the wire and `null` in SDK output. The legacy full package hash and
high-water/schema fields are also unknown. Unused proof fields are zero. Healthy
or absent explicit inspections use this same envelope without repair flags.

FILE3/FILE4 repair requires the exact current package size/hash retained by the
validated canonical root. FILE2 repair first compares the replacement's 352-byte
LFAPP1 signed envelope with the readable installed prefix. The replacement is
fully authenticated, including its payload digest, before that comparison grants
identity. A damaged/missing prefix instead requires both original lengths and
SHA-256(package || private bytes) from the surviving FILE2 header. The restore
engine computes that combined digest as bytes arrive and invokes the policy hook
after private-data verification, before accepting the pair or offering commit.
Truncated legacy files are admitted only through the explicit repair path with
that validated header and mandatory final policy hook.

Signature/trust, package support, retained cross-signer identity, version
high-water, quota and canonical-generation checks remain enforced. All writes
are staged and verified before the existing atomic root publication. Status flag
8 persists through ready/commit; the SDK requires it and checks committed flags
9, the archive digest and the final authenticated metadata. Canonical/trust changes
still abort before publication. Unknown or damaged canonical headers/roots fail
closed; raw unreadable-media salvage remains outside this contract.

The [ARM repair journey](../vm/test-sdk-code-repair.py) exercises signed USB
recovery and cold reopening; the session fixture additionally injects full/torn
write interruptions. Consult the ledger for actual runs and candidate hashes.
