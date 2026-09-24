# SDK architecture experiments — 2026-09-11

These are measured candidates for milestone M1, not completed SDK 1.0
architecture decisions. Firmware still uses the existing profile-2 package/data
replacement and ABI 1 byte store. No experimental storage writer is linked into
firmware; no volume has been migrated by this work.

## Data-only transactions

[The experiment](../sdk/experiments/document_store.h) runs on the repository's
actual littlefs v2.11.3 code with the existing 2048-byte page, 128 KiB block,
510 filesystem-block geometry, cache configuration and 256-byte inline limit.
Its synthetic test filesystem contains a versioned 208-byte root plus immutable
package and data blobs. The root references both generations, their lengths and
SHA-256 digests. A tentative upgrade also references the previous complete pair.

A checkpoint writes a new data blob, reads back and verifies it, writes and
verifies a pending root, then atomically renames the root. It does not write the
unchanged package blob. Upgrade acceptance clears the retained pair explicitly;
rollback switches the complete pair atomically. A second tentative upgrade is
rejected until the first is resolved. Checkpoints during migration keep the
previous pair. Generation overflow fails; it never wraps into a reused identity.
Collection removes only unreferenced blobs and has a bounded deletion count.

Reproduce with:

```sh
.venv/bin/python -m pytest tests/test_sdk_architecture.py -q
```

The sanitizer-backed harness reports to `build/sdk-architecture/document-store.json`.
It passed **860 interruption cases**, cutting before or partway through every
modeled program/erase in checkpoint, upgrade, acceptance and rollback. Recovery
accepted only the exact old or new complete root/pair. Other cases cover 100
successive checkpoints, empty data, bad arguments, quota bounds, unknown/corrupt
root rejection without writes, retained migration state and full-volume failure.

| Measured case | Result |
| --- | --- |
| Installed package | 700,000 bytes |
| Checkpoint payload | 65 bytes |
| Package bytes written by checkpoint | 0 |
| NAND bytes programmed by checkpoint | 10,240 bytes |
| Store object (macOS ARM64 host build) | 4,112 bytes |
| Root record | 208 bytes |

The difference between 65 logical bytes and 10,240 programmed bytes includes
littlefs metadata and the atomic root change. It is a single specified modeled
workload, not an endurance or worst-case amplification claim. This synchronous
host experiment also rereads package hashes; a firmware adapter needs an
incremental state machine and bounded hashing/I/O before exposing a commit call.

Remaining decisions: the production per-app root/package schema, profile-2
migration and old-reader rejection, named-record packing, interrupted import,
headroom reservation, icon pairing, bad-block/ECC qualification, read-only
recovery, and constrained first-launch migration/acceptance UX. The prototype
does not authorize downgrade, automatically roll back an installed release or
change USB/boot trust policies. Physical power cuts and flash-write measurement
are still required.

## Bounded app-side expressions

[The scalar prototype](../sdk/include/lefony/expression.h) uses fixed storage,
context-scoped generation-checked handles, a bounded parser, iterative
evaluation and cancellation at every node. All work runs under the app's existing
user-mode deadline. It supports arithmetic, variables, real powers, square root,
angle-aware trig/log functions and constants; the exact subset/errors are in
[the API](../sdk/API.md). The app-linked OpenBSD/fdlibm subset is taken byte-for-byte
from the pinned tree, with original notices and a hash manifest. It passes
760 high-precision host/ARM reference cases; matrix helpers additionally pass
120 constructed systems and failure/cancellation checks.

Host ASan/UBSan checks cover operator precedence/associativity, known numeric
answers, independent variables, failed parses/stale/foreign handles, all limits,
domain/unsupported errors, cancellation, and 10,000 deterministic arbitrary-text
cases. A context is 4,528 bytes on the test host, plus at most 1,024 bytes of
evaluation scratch. Reports are under `build/sdk-architecture/expressions.json`.
Real ARM cases additionally exercise expression evaluation, cancellation and
domain failures through the native app runtime.

This resolves a safe small app-side starting point. It does **not** resolve the
full math architecture. The pinned Poincare implementation's `TreePool::SharedStaticPool`
and expression circuit-breaker callback are global state, and its existing
container registers a callback that reads the OS keyboard. A shared adapter needs
explicit pool/context ownership, engine reentrancy and bounded/cancellable work
qualification. No synchronous unrestricted privileged evaluate call was added.
Shared Poincare and app-linked engine alternatives still need executable
footprint/reentrancy/cancellation measurements before M1 can close.

## License and responsibility boundaries

| Component | Provenance and terms | Integration decision |
| --- | --- | --- |
| SDK app-side helpers and expression prototype | Original Lefony code, CC-BY-NC-SA-4.0 file notices | Same protected native app; no promise of permissive app licensing |
| Storage experiment and firmware digest adapter | Lefony, CC-BY-NC-SA-4.0 | Test-only until a versioned runtime/storage migration exists |
| littlefs | Pinned v2.11.3, BSD-3-Clause and retained upstream notices | Existing configuration plus [failed-read cache invalidation](../ports/lefony-prime-g2/ion/src/prime_g2/littlefs/LEFONY-CHANGES.md) |
| Escher and Poincare | Pinned Upsilon `f36520e0ed5faabbfea8a2b9f4e1309edc077927`, existing component notices and CC-BY-NC-SA-4.0 core | No internal C++ types/pointers exposed as SDK wire ABI |
| App-linked OpenBSD/fdlibm subset | Exact pinned Upsilon files; retained Sun Microsystems and other per-file permission notices | Namespaced private C compatibility adapter; app-only execution and full corresponding source |
| Host tooling/tests | GPL-3.0-or-later except copied firmware harness notices | Separate host programs; retain corresponding sources/notices |
| GCC/compiler support | Pinned GCC 16.2.0, exact toolchain component terms | Full binary-release notice/source inventory still required |

SDK/API, runtime, storage, distribution and website are separate maintenance
responsibilities. Assignment to named maintainers and approval of physical
performance budgets remain release requirements; this document does not invent
owners or claim those approvals. The original app-side UI prototype now has a
tested Forms/Tables reference, copied input, Back navigation and text editing;
Graph Explorer measures a small app-side plotting/gesture/rendering alternative.
Escher extraction/comparison and the complete input/lifecycle contract remain
open. See [the milestone ledger](NATIVE-APP-MATURITY-EVIDENCE.md).
