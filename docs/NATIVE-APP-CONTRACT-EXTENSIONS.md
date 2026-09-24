# SDK contract extension work

Status: package/source negotiation implemented and locally tested, 2026-09-11.
Schema-0/source-0 remain defaults. Explicit schema-1 manifests and `source --format 1`
are opt-in local writers; compatible SDK, firmware and website readers are not
yet deployed. Storage remains profile 2, with versioned FILE3/FILE4 transactions
and an experimental [API 2 named-file interface](../sdk/FILES.md). The current
candidate adds [API 3 foreground execution and copied pixels](../sdk/FOREGROUND.md)
through explicitly declared capability 16 on both firmware targets, followed by
the [API 4 input stream](../sdk/INPUT.md) at capability 32. Existing ABI 1 layouts
and the 128-byte service-8 input snapshot retain their meanings.

## Deployment dependency

The tested app-side UI/math/graphics libraries need no privileged engine objects
or larger memory reservations. Durable checkpoints and future system services
do need explicit compatibility negotiation. Implement and test compatible
readers in the SDK, firmware and website before enabling a new writer in a
downloaded SDK. Old five-field manifests, signed ABI 1 binaries and source-0
submissions must keep their existing meanings. Unknown required capabilities
must fail before installation and again in the loader. Optional capabilities
must have documented fallbacks.

No production signing identity, executable ABI 1 event/service number, memory
window, flash region or existing anti-downgrade rule changes implicitly.
Deployment still waits for the user-requested full roadmap acceptance; a local
parser test is not permission to publish an incompatible format early.

## Package/manifest schema 1

Use an explicit container schema dispatch, retaining the original LFAPP0 magic
and existing 64-byte header layout. Header schema 0 accepts exactly the original
five fields. Schema 1 accepts ABI 1 and exactly five additional fields: `schema: 1`,
`required_capabilities`, `optional_capabilities`, `minimum_api` and `data_schema`.
The four latter fields are uint32 integers, with `minimum_api >= 1`. Header and manifest versions
must match. Existing signed LFAPP1 envelopes continue to authenticate the exact
inner bytes with unchanged trust roots and size bounds.

OS API revision is a contract revision, not an invented firmware release number.
The installed SDK release manifest must separately identify compatible actual
firmware builds. All integer fields need exact width/range checks, and required
and optional masks must not overlap. Unknown optional bits may be preserved and
ignored; unknown required bits cannot authorize execution. Shared fixtures must
cover old/new readers, canonical bytes, duplicate/extra fields, booleans supplied
as integers, boundaries, mismatch and unsupported requirements.

Hello status bit 16 advertises read-only USB IN `0x6e`, with argument zero and
length exactly 48. Its twelve little-endian uint32 words are magic `0x4341464c`,
size 48, version 1, reserved 0, ABI 1, OS API revision (currently 12), feature mask
(currently 16383, including named files at bit 8, foreground runtime at bit 16,
the input stream at bit 32, live file sync at bit 64 and directory/usage queries
at bit 128, per-app quota queries at bit 256, private-data control at bit 512,
typography at bit 1024, system services at bit 2048 and the
[app channel](../sdk/CHANNEL.md) at bit 4096 and
[writer abort](../sdk/FILES.md#explicit-writer-cancellation) at bit 8192), supported package-schema bitmask (currently 3), storage profile
(currently 2), maximum signed package bytes 2101664, private-data bytes 65536,
reserved 0. OUT is rejected. No flash reads, writes or mount are performed.
The existing 64-byte hello layout and protocol version remain unchanged. Keep protocol, package, storage and API revision values
independent. A missing response on old firmware means unsupported/unknown, never
permission to assume a new feature. Capability queries perform no device writes.

## Source format 1 and resource work

Source format 0 retains its exact src/*.cpp/*.h restriction. `lefony-source-1` carries
resources, public replay tests, SDK lock data and notices without executing hooks.
Top-level fields remain exactly `format`, `manifest`, `files`. Each file is an
object with exactly `encoding` (`utf8` or asset-only `base64`), `content`, and
lowercase 64-digit `sha256` of decoded bytes. Base64 must be canonical.
Both formats allow 1–64 files, at most 65536 decoded bytes each, 524288 decoded
bytes total and 1048576 bytes of normalized source JSON. At least one C++ file
is required. Format 1 also allows `tests/**/*.json`, `assets/**/*` with extensions
`png`, `jpg`, `jpeg`, `bmp`, `rgb565`, `bin`, `txt`, `json`; `notices/**/*.txt`/`md`;
`assets.json`, `sdk.lock.json`, `LICENSE.md`, `THIRD_PARTY_NOTICES.md`. Component
names use ASCII letters, digits, underscore and hyphen. Device-reserved Windows
names and case collisions at any path component are rejected. Hashes establish
integrity, not licensing, quality, or authenticity. Lock/tests are retained inert
inputs; no claim that a supplied test ran is inferred from its presence. Preserve the existing total
upload budget unless a coordinated size-budget change is explicitly recorded.
Paths must reject traversal, absolute/platform-special names, symlinks and case
collisions on supported hosts. Binary encodings must be canonical and bounded
before decoding. The website validates structure/ownership/integrity and signs
accepted bytes; it never runs resource conversion, builds or author tests.

The local resource converter now produces reproducible app-local read-only
LFRSRC1 bundles for PNG-to-RGB565 and raw blobs. See `sdk/API.md` for the exact
format, limits, cancellation, ownership and conversion rules. Generated data needs version, offsets, sizes, encoding and
integrity validation, within the existing executable/data reservations. The
source bundle must retain the declared original assets and conversion contract,
not merely omit inputs and ship an unexplained generated header.

## Data-only storage migration review

The existing Volume writes `apps/ID.app` as LFAFILE2, one header followed by the
signed package and staged private data. Its mount uses LFAVFS2 anchors and an
identity/migration marker. Old readers reject an unknown per-app header and do
not automatically format a mounted volume. These behaviors must be exercised
with preserved readers before choosing the new migration path.

The experiment's immutable package/data blobs and atomic current/previous root
are the starting point. Production needs a versioned per-app root, bounded
incremental I/O/hashing, catalog accounting, icon binding, cleanup and recovery.
Migration may copy a legacy package once; subsequent checkpoints must write
zero unchanged package bytes. No new raw partition geometry is necessary.

An explicit asynchronous checkpoint needs an immutable snapshot of staged data,
status/generation/error reporting and a defined close/fault path. Current
`refresh()` reuses package/data scratch buffers and cannot run unchanged while
an app has a checkpoint in flight. Writes made after the snapshot must stay
dirty and must not be falsely reported durable. Preview mode must report lack
of installed storage. An unsupported service must never produce a “Saved” UI.

Upgrades need retained complete old/new package/data pairs, a constrained
first-launch migration/acceptance operation, and an explicit recovery policy.
Preserve the highest accepted release watermark when selecting a retained pair;
do not turn recovery into arbitrary package downgrades. Unrecognized data and
failed migration/import stay recoverable and read-only. ABI 1 byte-store apps
need a specified compatibility policy before enabling this writer.

The public named-file service now includes live sync, enumeration, usage and
[per-app quota enforcement](../sdk/FILES.md#per-app-quota-policy) on the versioned
commit transaction. Per-app host exchange remains unfinished. These services
are not aliases for a staged buffer whose only durability mechanism is Close. Power cuts, full media, bad blocks, unknown
formats, failed readback and interrupted migration remain mandatory tests.

## Local acceptance evidence

The 77-case shared manifest corpus is `sdk/contracts/manifest-v1.json`; the
website keeps identical bytes at `tests/fixtures/sdk/manifest-v1.json`. Host
checks include the actual firmware parser under ASan/UBSan, truncations and
non-ASCII corruption, exact old SDK reader rejection, source exchange and
pre-upload failures. `vm/test-sdk-contracts.py` exercises the actual old/new
loaders, a negotiated signed install/readback, and an intentionally noncompliant
host rejected by firmware while preserving the previous app across cold boot.
The website tests the same corpus, source hashes and browser preflight with
mock devices. These are local checks, not physical qualification or deployment.
