# Whole-app backup and restore candidate

The working-tree `archive` commands transfer one app's signed package, private
bytes, named files and directories together. Pending upgrades include the prior
compatible package/data pair. This local candidate requires matching firmware
with archive hello flag 1024; existing downloads do not include it. Physical
storage, USB and complete desktop-bundle qualification remain open.

Close the app on the calculator before using these commands. The desktop SDK
includes libusb; source users install it as for [file exchange](FILE-EXCHANGE.md).
The explicit synthetic transport is described in
[emulator qualification](FILE-EXCHANGE.md#emulator-qualification). Use the public signing keys
that authenticate the packages in the archive, including any retained version:

```sh
lefony-sdk archive info notebook
lefony-sdk archive export notebook notebook.lfarchive --public-key developer-public.pem
lefony-sdk archive restore notebook.lfarchive --public-key developer-public.pem
lefony-sdk archive restore notebook.lfarchive --replace --public-key developer-public.pem
lefony-sdk archive status
lefony-sdk archive cancel 7 --nonce 00112233445566778899aabbccddeeff00
```

`--replace` explicitly permits replacing an existing local export file or an
installed app during restore. Repeat `--public-key` for multiple signers. The
bundled SDK also trusts its supplied store public keys. Supplying a host public
key does not enroll it on the calculator; use the [developer-key workflow](KEYS.md)
first. Status returns the current sequence and nonce for a scoped cancellation.

## What is preserved

Archives contain exact signed code, data schemas, the version high-water mark,
private bytes and named contents. Empty files/directories and pending recovery
pairs are preserved. They contain no private keys, enrollment grants, raw NAND
addresses or device identity. Separately attached store icons are outside this
format. They can be obtained from the store after restoring the matching code.

Export verifies every stored byte and publishes the destination only after host
size, hash and package-signature verification. A failed export removes its partial
file and preserves an existing destination. Restore validates a regular file
before opening USB, retains that same descriptor for upload, then independently
checks the received bytes and signatures on the calculator.

For an existing app, restored code must either match the installed signed
package exactly or have a version strictly above its retained high-water mark.
Restoring old data to the exact currently installed code is permitted after a
rollback. The current signer must retain ownership of that app. Store signing
roots share the existing store update authority. A retained pair under a
different developer key must match the recovery package already authorized on
this calculator. For a fresh calculator, use the explicit approval workflow below.

The current package needs an active execution key; retained packages and exports
may use retained inspection keys. Archives cannot silently reactivate revoked
keys. Unknown canonical formats and unreadable signed code are not treated as an
empty namespace. Valid signed code can be inspected independently of damaged
private data or a damaged named-file index, allowing an intact archive to repair
those contents while preserving ownership.

## Repair unreadable installed code

Matching firmware with hello flag 8192 adds explicit code repair:

```sh
lefony-sdk archive info notebook --include-unreadable
lefony-sdk archive restore notebook.lfarchive --repair-code --public-key developer-public.pem
```

`--repair-code` authorizes replacing the selected app and its data with the
verified archive. It requires an occupied namespace with unavailable signed code;
readable apps use ordinary `restore --replace`. It cannot be combined with
`--allow-recovery-pair`. The replacement must authenticate under an active key
already trusted by the calculator and prove the **exact original package**:

- FILE3/FILE4 roots retain its full package hash and size, even if its code object
  is missing, truncated or corrupt. A different or newer package cannot repair it.
- Legacy FILE2 stores a combined package/private-data hash. An intact signed
  envelope can prove the original code even when the payload is damaged, allowing
  a selected private-data backup. If that envelope is unavailable or differs,
  repair requires the exact package and private bytes matching the combined hash.
  This fallback may require an older backup with the original private data.

The host checks that proof before upload; firmware verifies it independently
before allowing commit. Existing version high-water marks, retained-signer rules,
quotas, cancellation and atomic publication still apply. No key is enrolled or
reactivated. Inspection reports unknown signed version/schema/signer fields as
`null`; namespace metadata is not presented as authenticated package metadata.
`index_known` still describes decoded usage metadata, not verified file contents.

Canonical roots without a valid surviving copy cannot use this path: their
ownership proof is unavailable. They remain occupied and are never silently
reformatted. Canonical record read failures report storage I/O errors; readable
but malformed records report integrity errors. Neither permits repair to proceed.
The local candidate's exact host/ARM evidence is in the ledger;
physical media and current native bundles remain unqualified.

## Root protection and repair

Matching FILE5 firmware stores two complete copies of each converted app's
ownership, package/data references and version history. `archive info` negotiates
hello flag 32768 and adds `root_protection`:

- `both`: both record copies are valid and identical.
- `payload-only` or `metadata-only`: one valid copy remains; back up and repair.
- `single`: this app still uses the older single-record representation.
- `null`: the app is absent or the firmware cannot report this information.

Close the app and back up the complete surviving state, then explicitly restore
that verified backup to rebuild both copies:

```sh
lefony-sdk archive info notebook
lefony-sdk archive export notebook notebook-recovery.lfarchive --public-key developer-public.pem
lefony-sdk archive restore notebook-recovery.lfarchive --replace --public-key developer-public.pem
lefony-sdk archive info notebook
```

This restores the exported snapshot, including pending recovery pairs. Keep the
app closed between export and restore so intervening edits are not replaced by
the backup. Supply every required package public key. If code is also damaged,
use an earlier verified archive with `--repair-code` as described above. Failed
exports and unknown commit outcomes retain their existing handling. Inspect the
result before retrying; successful repair reports `both`.

The reader does not silently repair storage. New saves and explicit archive
restores write protected roots; healthy legacy roots migrate on their next root
commit. FILE5 needs matching firmware: older firmware rejects those roots.
Conflicting valid copies, loss of both copies, unreadable metadata or an
unmountable volume cannot be repaired from guessed ownership. This protection
adds a 128 KiB payload block per root plus metadata, counted in shared usage.
See the [storage contract](../docs/NATIVE-APP-ROOT-RECOVERY.md) for exact limits.

## Restore a recovery pair onto a fresh calculator

If an archive contains a pending upgrade signed by one developer key and a
retained version signed by another, enroll both public keys first. The current
signer must be active; the retained key may stay revoked. Both must be enrolled
developer keys; this option cannot transfer store signing authority. Close the app and
return the calculator to Home, then run:

```sh
lefony-sdk archive restore notebook.lfarchive --public-key current-public.pem --public-key previous-public.pem --allow-recovery-pair
```

This option requires matching firmware with hello flag 4096 and an absent app
namespace. It cannot change ownership of an existing app, even with `--replace`.
Ordinary restore still refuses a fresh pair across different signing authorities.
A pair already authorized on that calculator retains its ordinary restore path.

The calculator stages and verifies the entire archive before requesting
approval. Compare the full app ID, both versions and signer fingerprints, and
archive SHA-256 with the SDK output. Release all keys and press physical OK to
allow that exact pair, or Back to cancel. The retained package becomes the
explicit recovery option; rollback restores its original signing ownership.

Approval expires after two minutes. Back, Home, power or USB disconnect before
acknowledged commit cancels the staged restore; commit is unavailable before
rendered OS approval. The SDK still sends a separate bound commit after approval.
A lost commit response retains the normal unknown-outcome handling below. Trust
and destination generation are rechecked at approval and commit.

This does not enroll keys or reactivate a revoked key. A retained revoked signer
can authenticate the archive while remaining unavailable for execution/rollback;
explicitly reenroll it before using that retained version. The recovered app keeps
its version high-water mark and its current and previous saved-data snapshots.

## Commit and capacity

Restore stages new objects and verifies all incoming pairs before an atomic
root replacement. The existing canonical app and its objects remain available
until that commit. Unchanged chunks are reused only after verifying their actual
bytes; damaged chunks are replaced from the archive. Quota and real shared-flash
headroom are checked separately. Normal 32 MiB per-app mutable-data limits apply;
existing oversized data retains its documented no-growth allowance when its
index can be decoded. A damaged index cannot establish an oversized allowance.

Cancellation, timeout and disconnect before commit discard staged work. An
acknowledged commit drains across USB reset. After a lost commit response, the SDK
reports an unknown outcome and does not retry or roll back. Reconnect and inspect
the app before deciding whether to restore again. A verified commit receipt is
followed by inspection of the new generation, package hash, schemas and usage.
If that inspection fails, the SDK reports that commit succeeded but final
inspection failed.

Ctrl-C follows the [file-exchange cancellation contract](FILE-EXCHANGE.md).
Before commit, the CLI finishes its current USB transfer and cancels the owned
archive session. During commit it finishes the bounded receipt/inspection checks;
it does not discard a successful result or retry an uncertain write.

This is a whole-app snapshot. For a single document or private-data snapshot,
use [file exchange](FILE-EXCHANGE.md) or [data recovery](DATA-RECOVERY.md).
The [archive format and session design](../docs/NATIVE-APP-ARCHIVES.md) and
[implementation ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md) record exact
validation and remaining work.
