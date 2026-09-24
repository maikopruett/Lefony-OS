# Private app installation and signing-key recovery

This local candidate adds developer public-key management and explicit private
installation. It requires matching firmware and an already provisioned app
volume. It does not enroll firmware update keys or change storage geometry.
The local macOS bundle passes 36 frozen CLI steps across six ARM sessions,
including local key generation/signing, canceled and approved enrollment,
Notebook installation, revocation, signer replacement, damaged-registry repair,
partial backups/fresh-scan repair under unreadable payload faults, and cold
saved-data reopening. Network, Homebrew and checkout access are denied
to the executable. This models USB and uses temporary test identities; clean
supported hosts, unreadable ownership/filesystem metadata and physical operation
remain separately unqualified. Exact candidates are in the implementation ledger.

## Enroll and install

Create a separate RSA-2048/e65537 app identity with the SDK. These local commands
also work in the desktop executable using its bundled OpenSSL, without a separate
Python installation. Keep the private key outside the project and retain a private backup:

```sh
lefony-sdk keys generate --private-key /private/app-private.pem --public-key /private/app-public.pem
lefony-sdk keys enroll --public-key /private/app-public.pem --label "My development key"
lefony-sdk keys list
```

Return the calculator to Home. Compare the complete public-key fingerprint on
the host and calculator, release all keys, then press OK on the calculator.
Back, Home, USB disconnect or the two-minute consent deadline cancels an
unapproved request. The private key never travels over USB. The firmware update
key, compiled store roots and public emulator fixture cannot be enrolled as
developer keys.

Build/package an ABI 1 project normally, then sign and explicitly install it:

```sh
lefony-sdk sign ./build/my-app-1.0.0.lfapp --private-key /private/app-private.pem --output ./build/my-app-1.0.0-signed.lfapp
lefony-sdk install ./build/my-app-1.0.0-signed.lfapp --public-key /private/app-public.pem
```

Generation never replaces an existing key destination. Signing verifies the
package before creating a new output file and refuses an existing output. Neither
command connects to USB or the store. An interrupted generation can leave reserved
files; inspect them and choose new paths for a new attempt rather than overwriting
an identity. On Unix the private file is created with mode 0600; on Windows use a
private directory with appropriate account permissions.

The host verifies the signature before opening USB, checks runtime compatibility and
verifies the installed package by complete readback. Ordinary updates retain
their signing identity, obey version monotonicity and preserve saved data.
Store publication remains a separate workflow with its own signing authority.

## Revoke or replace a lost key

Use the full fingerprint returned by `keys list`:

```sh
lefony-sdk keys revoke FULL_64_DIGIT_FINGERPRINT
lefony-sdk keys status
```

Revocation needs calculator approval. It blocks installation and execution of
packages signed by that key, while retaining the public key to authenticate the
catalog and saved-data exports. Other store and developer apps retain their
existing trust. Re-enrolling the same public key explicitly reactivates it; this
does not recreate a lost private key.

To replace a lost private key for one installed app:

1. Create and enroll a new independent app key, then revoke the lost key.
2. Build a higher-version package with the same app ID and compatible data
   migration behavior, and sign it with the new key.
3. Run the explicit recovery installation:

```sh
lefony-sdk install ./build/my-app-1.1.0-signed.lfapp --public-key /private/new-app-public.pem --recover-signer
```

The calculator displays the app ID/version, old and new fingerprints and exact
signed-package SHA-256. Compare them with the SDK output before pressing OK.
Approval binds those bytes, the observed key-registry serial and the current
saved-data generation. The OS checks them again before starting the upgrade.

Recovery requires an authenticated installed package under the retained revoked
key and an already enrolled active replacement key. It cannot claim a store app,
unknown/damaged namespace, different app ID, same/lower version or an app with an
unresolved pending upgrade. It grants no authority over another app. The old key
stays revoked after recovery; ordinary later updates use the replacement key.

The existing document transaction retains the previous compatible package/data
pair until upgrade acceptance. A legacy byte-store app is first converted while
preserving its exact package and data, then upgraded. Cancellation or failure
between those commits may leave that representation converted, with the old
signer and user bytes unchanged. Restoring execution under a revoked old signer
still requires its explicit re-enrollment; recovery does not bypass revocation.

## Cancellation and unknown outcomes

`keys status` reports operation, fingerprint, nonce, sequence, registry serial,
state and error; recovery also reports the package hash. To cancel the exact
current request from the host:

```sh
lefony-sdk keys cancel SEQUENCE --nonce FULL_32_DIGIT_NONCE
```

Cancellation is effective only before the transaction commits. A disconnect or
lost reply after commit may leave the operation completed despite a host error.
The SDK never automatically retries the write or reports cancellation as a
rollback. Inspect `keys status`, `keys list`, the app catalog and saved-data
exports before deciding on a new operation. Nonces prevent a repeated request
from reopening its old approval screen; they are not persistent receipts after
a calculator restart.

## Remove an unused retained key

Eight retained identities bound registry storage. Revocation does not automatically
evict a key. To free a slot, explicitly revoke an unused identity and remove it:

```sh
lefony-sdk keys revoke FULL_64_DIGIT_FINGERPRINT
lefony-sdk keys remove FULL_64_DIGIT_FINGERPRINT
```

Both changes require calculator approval. Removal refuses active keys, keys used
by an installed package, and keys needed by a retained upgrade/recovery pair.
Unreadable or unauthenticated installed packages conservatively block removal;
repair/export their data first. The firmware checks again after approval. Removing
the last key preserves the registry's mutation serial; it does not reset it to a
fresh installation. Full tables still allow reactivation of retained identities.

## Rebuild a damaged registry

A corrupt registry disables developer trust while leaving compiled store trust
and installed bytes intact. Normal enrollment never resets it. The explicit
repair workflow first exports and verifies the exact damaged file on the host:

```sh
lefony-sdk keys backup-damaged ./damaged-registry.keys
lefony-sdk keys repair --public-key /private/app-public.pem --label "Recovered key" --backup ./repair-original.keys
```

The repair command requires a **new backup destination**. It makes its own verified
backup before requesting approval. Keep that file: it contains the original
public-key records, including any records that could not be decoded. On the
calculator, compare both the supplied key fingerprint and damaged-file SHA-256
with the SDK output, then approve with OK. Back/disconnect cancels unapproved
repair and leaves the saved backup available. A changed damaged file invalidates
the proposal. A failed backup never starts repair.

Repair reconstructs the registry with the supplied public key active at serial 1.
Other keys require explicit re-enrollment; their former active/revoked states
cannot be trusted after corruption. It does not change installed packages, data,
namespace ownership or version high-water marks. Supply an original app key to
restore authentication of its existing packages. A new unrelated key cannot
claim their namespaces; lost-private-key replacement still uses the separate
per-app recovery workflow above after authenticating the original public key.
The existing private key is never recovered or transferred by this operation.

Only fully readable damaged registry files up to 64 KiB can be backed up and
repaired this way. I/O failures and larger files are refused without rewriting
storage. Unknown commit outcomes still require inspection rather than a retry.
Whole-app archives preserve app ownership and data but do not import key trust.

Removal, damaged export and repair require host hello flag 2048. This candidate
reads registry format 1 and writes format 2, which represents an empty registry
without losing its serial. Older firmware cannot read format 2 and disables
developer trust; keep matching firmware/SDK versions. This does not change app
ABI/package formats or NAND geometry. Physical power-loss qualification and
complete native host bundles remain open.

## Rebuild a registry with unreadable regions

The separate partial-backup candidate handles unreadable registry payload bytes
when the volume and file metadata are still readable. Use these explicit commands:

```sh
lefony-sdk keys backup-unreadable ./partial-registry.keys
lefony-sdk keys repair-unreadable --public-key /private/app-public.pem --label "Recovered key" --backup ./repair-partial.keys
```

`backup-unreadable` is read-only on the calculator. Its `LFKREAD1` file contains
the readable fragments and marks missing regions; it cannot recover those missing
bytes. The result reports original size, preserved bytes, missing-region count and
the SHA-256 of the complete partial backup. It refuses fully readable registries,
unreadable metadata and files larger than 64 KiB. Use the preceding workflow for
a fully readable corrupt registry.

`repair-unreadable` creates its own verified partial backup at a **new path**
before requesting approval. Compare the replacement public-key fingerprint and
**partial backup SHA-256** on the host and calculator. The screen states that
the backup omits unreadable bytes. Release all keys, then press OK to approve.
The firmware scans again before displaying consent and again after approval;
changed readable fragments, changed missing regions or a now-readable registry
refuse replacement. A failed export or host backup publication never requests
repair. Cancellation leaves the verified backup available.

Approved repair atomically replaces the registry with only the supplied public
key, active at serial 1. Partial fragments never import former key trust or
revocation states. Installed packages, saved data, signer ownership and version
high-water marks are preserved. Restore an app's original public key to
authenticate its packages; an unrelated key cannot take ownership of them.
Lost private keys, unreadable app ownership records and unmountable storage need
separate recovery. Unknown commit outcomes require inspection before a new request.

These commands require host hello flag 16384 and matching source SDK/firmware.
They leave the app API, registry format 2 and storage geometry unchanged. They
are a local implementation candidate; consult the ledger for the exact host,
firmware and ARM evidence. Existing downloads do not acquire the new commands.

The [implementation ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md) records exact
host/ARM validation. Emulator input follows normal keypad dispatch and the
OS-owned consent screen; an app callback or USB command cannot approve a key.

## Emulator qualification

The explicit `keys --emulator-usb PATH OPERATION` and
`install PACKAGE --public-key KEY --emulator-usb PATH` forms use an already
enumerated, exclusively handed-off QEMU model socket. They preserve each
command's ordinary request restrictions and consent/signature checks. They never
discover a physical device or fall back to physical USB. The runner must lend its
connection until the command exits; this option is for controlled emulator tests,
not a substitute for ordinary workspace preview. It does not reset/enumerate USB
or permit firmware operations. Key generation remains local and rejects this option.
