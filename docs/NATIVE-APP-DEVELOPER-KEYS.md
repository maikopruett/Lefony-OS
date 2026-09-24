# Private developer app keys

Status: **live local implementation candidate, 2026-09-13**. The registry,
OS consent controller, USB/SDK commands and catalog/loader integration are
implemented. Explicit per-app signer recovery adds replacement of a lost private
key without changing firmware trust roots. Both firmware targets compile.
See [the developer workflow](../sdk/KEYS.md) and the
[implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md) for exact validation.
This is not a qualified SDK release or physical acceptance.

## Trust and recovery boundary

Developer app keys are separate from compiled store app keys and firmware update
keys. The registry contains only public RSA-2048/e65537 moduli, their canonical
SPKI SHA-256 identities, short display labels and active/revoked states. Private
keys remain on the developer's host. The identity calculation agrees with
[the existing signing tool](../sdk/tools/signing.py); the signature format and
RSA verification are unchanged.

An active registry key authenticates packages for normal installation and
execution through AppManagement and the native loader. A revoked key remains usable
only for cryptographic inspection of retained packages and saved-data export.
It cannot authorize installation, execution, update acceptance or launching a
rollback. Inspection still verifies the complete LFAPP1 envelope and signature.
It never means trusting a package's claimed app ID without authentication.

`NativeAppSignature::unwrap` selects compiled roots (plus the explicit fixture
on emulator builds). `AppManagement::unwrap` checks those roots, then the loaded
registry with the caller's explicit Execute or Inspect purpose. Catalog and
saved-data export authenticate retained revoked-key packages; install and launch
require active authority. A damaged package is quarantined from the catalog and
cannot prevent unrelated authenticated apps from appearing or grant a new signer
its installed namespace. Discovery reports the unavailable-app count.

Re-enrollment of the same public key reactivates its existing record. It is a
new proposal requiring the same OS approval as initial enrollment.
Relabeling also advances the serial. Revocation retains the public key and label;
there is no automatic eviction of revoked identities. This preserves the ability
to authenticate old packages even after a private key has been lost.

## Bounded registry format

The internal file is `developer-keys` at the root of the existing app littlefs
volume. It does not consume an app ID, change the app catalog format or change
the reserved NAND geometry. The transaction file is `.developer-keys.pending`.
App file APIs must never expose either root path.

All integer fields are unsigned little-endian. The file is exactly 2,752 bytes:

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0 | 8 | `LFDKEY1` followed by NUL |
| 8 | 4 | Format version 1 (legacy) or 2 (current writes) |
| 12 | 4 | Total bytes, 2752 |
| 16 | 4 | Nonzero mutation serial |
| 20 | 4 | Retained key count, 0–8 in version 2; 1–8 in version 1 |
| 24 | 8 | Zero reserved bytes |
| 32 | 32 | SHA-256 of bytes 0–31 followed by bytes 64–2751 |
| 64 | 2688 | Eight 336-byte records |

Each record has state at offset 0 (`1` active, `2` revoked), twelve reserved zero
bytes, a 32-byte fingerprint at offset 16, the 256-byte modulus at offset 48, and
a 32-byte label at offset 304. Labels contain 1–31 printable ASCII bytes, no
leading/trailing spaces, and a NUL followed by zero padding. Unused records are
entirely zero. Duplicate identities, mismatched fingerprints, unsupported states,
noncanonical labels/reserved fields, incorrect lengths and digests are rejected.

Eight identities bound RAM and filesystem work; this is not an app-count limit.
The table occupies 2,600 bytes. The host fixture measures the Store object at
8,064 bytes, including the table, file buffers and caches; the Cortex-A7 compiler
measures it at 8,028 bytes. Complete controller memory, stack peaks and latency
budgets still need qualification before the format becomes stable.

No file means an empty registry at serial zero. Stored zero serial is invalid;
stored zero count requires version 2. An unreadable, corrupt or unknown registry disables developer trust;
normal enrollment cannot reset it. A mutation checks the caller's observed
serial after rereading the canonical file. Stale proposals fail before writes.
Serials never wrap. Exact repeated enrollment/revocation is a no-op; full tables
reject new identities while permitting revocation and reactivation of retained
keys. Removal/recovery additionally account for retained app packages below.

The key-maintenance candidate adds **registry format 2**. Its byte layout, magic
and digest are unchanged; offset 8 is 2 and count may be zero with a nonzero
serial. Every mutation writes version 2. Readers retain strict version-1 support,
including rejection of version-1 stored-empty files. This is an intentional
internal format transition: older firmware fails closed on version 2. It changes
no app ABI, signed package format, reserved volume layout or firmware trust root.
The format-1 stored-empty restriction above describes compatibility decoding.

Removal requires a revoked key and an exhaustive check of occupied namespaces,
including quarantined entries. Both current and retained distinct package
identities must authenticate. An unreadable entry conservatively refuses removal.
The controller repeats this check after rendered OS approval, then performs the
same serial-checked verified pending-file transaction. No referenced public key
is evicted automatically; removing the last unused key retains a nonzero serial.

Damaged-registry repair explicitly reconstructs trust with one supplied public
key, not inferred states from damaged records. The SDK first exports the raw file
with size/hash verification and atomic host publication. Repair binds its exact
SHA-256 and the new public-key identity to a fresh nonce and rendered approval.
The Store rereads the entire damaged file and compares that hash after approval,
then uses the existing verified pending-file/atomic rename/readback sequence.
Installed namespaces and app version high-water marks are unchanged. Other
identities need separate re-enrollment; the original raw public records remain
in the host backup. The repaired table begins at serial 1 because the old serial
is unauthenticated. A healthy/missing registry cannot use this reset path.

Backup/repair is bounded to fully readable files of 0–65,536 bytes. Failed reads,
larger files, changed hashes, protected firmware/store/fixture identities and
unapproved requests never start replacement. Power cuts select either the exact
old damaged file or the new canonical table. A damaged survivor exposes no
developer authority and can be retried only after inspecting it and obtaining
new approval. The protocol cannot prove remote backup custody; the SDK repair
command requires verified host publication before requesting device approval.

The digest detects damaged/noncanonical records; it is not protection against an
attacker with arbitrary raw NAND write access. Authorization belongs to the OS
controller, and the registry is never imported as an ordinary application file.

### Partial backup of unreadable payloads

The separate `Snapshot` engine handles a readable file identity/size with
partially unreadable payload, up to 65,536 bytes. It captures at most one
512-byte source chunk per step using fixed buffers under 4 KiB. Only explicit
`LFS_ERR_IO` or `LFS_ERR_CORRUPT` reads mark a region unknown. Short positive
reads, unsupported sizes and unreadable metadata fail the capture. A fully
readable file is refused by this path even if its registry contents are corrupt.

The exported `LFKREAD1` container uses unsigned little-endian integers:

| Bytes | Meaning |
| --- | --- |
| 0–7 | Exact ASCII `LFKREAD1` |
| 8–31 | Six uint32 values: schema 1, original size, chunk size 512, rounded-up chunk count, zero, zero |
| Each 16-byte record | Source offset, chunk length, state (0 readable / 1 unknown), zero |
| Following a readable record | Exact chunk bytes; unknown records have no payload |

Records cover the original file exactly in order, including a short final chunk.
At least one must be unknown. No trailing bytes are allowed. The maximum encoded
bound is 67,616 bytes; SHA-256 covers the entire container. Export rereads the
known-readable fragments and the host verifies framing, counts and the whole
hash before atomic publication. Omitted bytes are never represented as zeros or
treated as an imported key table.

An explicit repair binds the snapshot hash, replacement public key and fresh
nonce. The controller captures again before consent and after freshly rendered
OS approval. A changed observation or a fully readable registry fails before
replacement. After successful revalidation the Store consumes the snapshot proof
and uses its existing atomic transaction to install one active key at serial 1.
App namespaces, retained packages, user data and version high-water marks remain
unchanged. The protocol cannot establish host backup custody; the SDK requires
verified local publication before requesting approval. Missing private keys,
unreadable ownership roots and unmountable volumes are not reconstructed here.

## Transaction and failure behavior

The Store requires exclusive ownership of its mounted littlefs instance for the
whole operation. OS approval must happen before `beginEnroll`, `beginRevoke`,
`beginRemove`, `beginRepair` or `beginRepairSnapshot`. The latter additionally
requires a matching fresh partial snapshot from after approval.
Pure `Table` proposals can prepare the display without changing persistent trust.
The Store has fixed buffers and makes progress in 512-byte chunks:

1. Read and validate the canonical registry; check the observed serial.
2. Create/truncate the fixed pending file and write the canonical candidate.
3. Close the writer, reopen the pending file and verify every byte.
4. Atomically rename the verified pending file onto the canonical path.
5. Read back the canonical file before reporting success or exposing new trust.

Cancellation before rename leaves the previous canonical registry selected. It
may leave a pending file, which load ignores and a later approved retry can
replace. Cancellation cannot claim rollback once rename starts. A rename or
readback error clears cached developer authority; a subsequent read determines
which registry was committed. The operation may have succeeded despite a missing
acknowledgement, so callers must report an unknown outcome and query it rather
than retrying with an invented serial.

The implementation uses this repository's pinned littlefs code and its normal
file close/rename operations. The upstream
[littlefs specification](https://github.com/littlefs-project/littlefs/blob/master/SPEC.md)
explains its metadata commits; the fault tests exercise the actual local code.
No format, filesystem reset, app deletion or firmware-key operation occurs here.

## OS consent and additive USB protocol

The controller shares AppManagement's existing exclusive mounted-volume owner.
Initialization loads the registry read-only. Invalid storage fails closed without
formatting it or disabling compiled-store trust. Active file readers, app
execution, other data transfers and firmware updates exclude key mutations.

Host hello flag 256 advertises enrollment/revocation; flag 512 additionally
advertises per-app signer recovery. These are host extensions, not app APIs.
The app API, ABI 1, package formats, storage geometry and firmware roots are unchanged.
The fixed structures are in
[app_developer_key_wire.h](../ports/lefony-prime-g2/ion/src/prime_g2/app_developer_key_wire.h):

| USB command | Direction | Payload |
| --- | --- | --- |
| `0x80` | IN | 160-byte operation/status record |
| `0x81` | OUT | 384-byte enrollment, revocation or recovery request |
| `0x82` | OUT | 32-byte cancellation bound to sequence and nonce |
| `0x83` | IN | Indexed 352-byte retained public-key record |
| `0x84` | IN | 192-byte prepared per-app recovery identity |
| `0x85` | IN | 64-byte damaged-registry size and complete SHA-256 |
| `0x86` | IN | Up to 512 raw damaged-registry bytes at the requested offset |
| `0x87` | IN | 96-byte completed partial-snapshot information |
| `0x88` | IN | Up to 512 serialized partial-snapshot bytes at the requested offset |

Host hello flag 2048 additionally advertises key maintenance. Request operation 4
removes an unused revoked key; its modulus, label and reserved bytes are zero.
Operation 5 repairs a corrupt registry using the enrolled-key request shape,
serial zero, and the exported damaged-file SHA-256 in the 32 reserved bytes.
The OS displays that hash and the full replacement fingerprint before approval.
Its screen explains that other keys require re-enrollment. Status reserved bytes
mirror this binding. Errors 13/14 mean an installed/unreadable namespace prevents
removal or the selected key must first be revoked. Existing operations retain
their meanings. Damaged-file reads require idle exclusive storage access.

Host hello flag 16384 advertises unreadable-registry backup/repair. Operation 6
requests a read-only capture: serial, fingerprint, modulus, label and reserved
bytes must be zero; the nonce is nonzero. It completes without presenting consent.
Operation 7 uses operation 5's shape but binds the partial-container SHA-256.
Error 15 means the registry is fully readable and cannot use partial repair.
Unsupported sizes and unreadable metadata retain distinct invalid/I/O errors.

The 96-byte snapshot information contains eight uint32 values: magic `0x554b464c`,
size 96, schema 1, operation sequence, original bytes, encoded bytes, readable
bytes and unknown-chunk count. Bytes 32–47 contain the nonce, bytes 48–79 the
container hash, and bytes 80–95 are zero. Reads require a completed operation 6
and idle exclusive volume access. A new request or restart invalidates its
binding. Operation 7 repeats capture after approval before starting any writes.

Each request binds an unpredictable 16-byte host nonce, registry serial and full
public-key fingerprint. An exact replay observes its old operation; altered
bytes under the same nonce are rejected. Consent expires after two minutes or
clock rollback. USB acknowledgement only queues preparation, never approval.
The deferred OS event may present consent only from Home, outside exam mode and
installed app execution. Approval requires the rendered OS screen, a subsequent
all-keys-up scan and then physical OK alone. Back/Home/power/disconnect cancel
pending consent. App callbacks and USB cannot synthesize the approving event.

Recovery operation 3 uses the 32 reserved request/status bytes for the exact
signed-package SHA-256; repair operations 5/7 use their respective backup hashes,
and the remaining operations require zero bytes there. Its separate
identity includes the app ID/version, old signer, saved-data generation and
package hash, bound to the operation sequence and registry serial. The OS displays
both complete signer fingerprints and the package hash. After approval it
reauthenticates the staged and installed packages and rechecks the complete
prepared identity before using the ordinary retained package/data upgrade.

The old signer must be a retained revoked developer key, the new signer an
enrolled active developer key. The replacement must use the same app ID and a
strictly higher version, including the retained version high-water mark. Store
apps, unknown/damaged namespaces and unresolved pending upgrades are rejected.
Legacy storage is converted after consent before the retained upgrade; a
cancelled conversion preserves the old package and data. The old key remains
revoked. A terminal key result refreshes the catalog even when approval,
cancellation or a USB disconnect completed outside the regular polling step.

## Remaining implementation and qualification

- The explicit maintenance candidate is implemented; its exact source, ARM and
  interruption evidence belongs in the SDK ledger. Normal enrollment never
  silently resets the table or evicts an old key. The separate partial-snapshot
  candidate handles unreadable payload with readable metadata; unmountable media
  and unreadable canonical app ownership remain outside that recovery path.
- Complete full/damaged-media and interruption coverage of the integrated
  recovery journey, beyond the underlying transaction engine fixtures.
- Qualify complete native host bundles, source/signing workflows, real USB/input,
  resource budgets and physical power-loss behavior.

## Validation

Run the focused suite with the project environment:

```sh
.venv/bin/python -m pytest -q tests/test_app_developer_keys.py tests/test_native_app_signing.py tests/test_native_app_storage.py tests/test_app_documents.py tests/test_sdk_document_root.py
```

The new test compiles production registry/storage/littlefs sources under
ASan/UBSan. It compares fingerprints and wire bytes with Python/OpenSSL, exercises
real signed packages, tests execution rejection after revocation and signature
rejection during inspection, and injects NAND interruptions and read failures.
It also checks cancellation, full storage, stale proposals, corrupt roots,
ignored pending files and preservation of an unrelated installed app/data pair.
Both full and torn program/erase interruptions remount the volume and require
the exact old or new registry before an observed-serial retry.

Exact build/test reports belong in the
[SDK implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md). These host tests do not prove physical power-loss recovery or flash endurance.
Separate ARM journeys exercise the live OS consent and recovery integration.
