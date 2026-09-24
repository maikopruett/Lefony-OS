# Publishing from a project folder

This local candidate implements `lefony-sdk publish`: snapshot the folder,
build and test its exact release package in the ARM emulator, then upload and
publish it through the matching store backend. `publish --dry-run` stops at a
local preview without authentication, network access or physical USB. Interrupted
uploads can resume their saved bytes. `listing pull` reviews and merges store
text/media into the linked project. The matching browser form also offers listing
comparison and explicit conflict resolution. `listing push` edits presentation
without a new release; `apps withdraw APP_ID` removes all active store versions.
The matching Worker and migrations through 0010 are deployed to the live store.
Initial production namespace and owner inventory has passed; submissions are enabled.
The public Linux x86-64 bundle includes these commands; the macOS download is
an older preview. The real production publication journey used the macOS source
SDK; Linux account/publication checks used local services under emulation. See the
[SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md) for qualification status.

Publication preparation builds and tests a fresh copy of the selected inputs;
it does not reuse the original project's earlier `build/run.json`. Cancelling
that replay retains an incomplete report inside the attempt and creates no
ready submission. Start a new `publish --dry-run` or `publish` after correcting
the interruption. `--resume` requires a completed, verified submission; an
incomplete local test is distinct from an interrupted upload of prepared bytes.

## Prepare the listing

New projects include `store/listing.json`, empty `description.md` and
`release-notes.md`, and a `screenshots/` directory with instructions. Add your
`store/icon.png` and actual screenshots. Identity, name, version, ABI and license
come from `app.json` for a release. A metadata-only edit may change the store
display name while retaining the original name inside the immutable package.

```json
{
  "schema": 1,
  "publish_source": true,
  "repository_url": "https://github.com/example/my-app"
}
```

Templates start with source permission disabled. Enable it when you intend to
distribute the source. The optional repository URL is an inert HTTPS link without
credentials, query or fragment; the SDK does not fetch the repository.

| File | Rule |
| --- | --- |
| `store/description.md` | Required nonempty text, at most 2,000 UTF-16 code units |
| `store/release-notes.md` | Required file; text may be empty, at most 4,000 UTF-16 code units |
| `store/icon.png` | Square, 64–512 pixels, at most 256 KiB |
| `store/screenshots/*.png` | 1–5 files; width 160–1280 and height 120–960 pixels; at most 1 MiB each |

Text is trimmed and displayed literally, including Markdown/HTML. Unicode
surrogates and NUL are rejected. UTF-16 counting matches the website: ordinary
characters use one unit and an emoji such as 🌍 uses two. Screenshot filenames
contain ASCII letters, numbers, hyphens or underscores, followed by `.png`.
Case-sensitive filename order determines display order; names differing only
in case are rejected. The screenshots README and `.gitkeep` are ignored.

Images must be static, non-interlaced, 8-bit RGB/RGBA PNGs. The SDK checks chunk
types, checksums, dimensions, scanline filters and bounded decompression. It
strips ancillary metadata before producing upload bytes. These rules and clean
image hashes have a common SDK/website corpus; browser uploads may normalize
other supported image formats to PNG first.

## Build and test the snapshot

```sh
lefony-sdk --project ./my-app publish --dry-run
# Source checkouts can select the candidate runtime explicitly:
lefony-sdk --project ./my-app publish --dry-run \
  --qemu ./path/to/qemu-system-arm --firmware ./path/to/firmware.elf
```

The command collects source format 2 inputs (`src`, `assets`, `tests`, `notices`
and the explicitly allowed project/configuration/license files), plus the
listing. It excludes top-level `.git`, credentials, build outputs, captures,
caches and `.lefony`. Unsupported entries inside the selected source roots,
symlinks/reparse points, oversized files and invalid media fail preflight.
Keep secrets out of source and assets deliberately included in your project.

Each attempt has a fresh private `.lefony/publish/UUID/` directory. The original
project is not built or changed. An absent SDK lock is generated in the copied
project before input hashes are recorded; an existing mismatched lock fails
with guidance to select the matching SDK or explicitly update the original lock.
All source and listing bytes are copied before the release build and tests.
Normal edits to the original project subsequently belong to another attempt.

The SDK builds the copy with the release profile and tests its exact unsigned
package through normal ARM emulator input. All JSON replays below `tests/`,
including nested directories, run in sorted path order. With no author replays,
the startup proof runs and missing author interactions are explicitly skipped.
Any failed test, omitted replay, changed snapshot/package or changed SDK/QEMU/
firmware identity prevents a complete submission.

Successful attempts contain:

- `index.html`: local listing/media preview and exact file/hash summary.
- `submission.json`: canonical version-1 manifest binding app/listing identity,
  the input manifest digest and every upload file's size/SHA-256.
- `upload/`: only `source.lfsrc`, `package.lfapp`, `report.json`, normalized
  `icon.png` and ordered `screenshots/01.png` through `05.png` as supplied.
- `inputs.json`, `inputs/` and `project/`: retained local input proof and build
  tree. These are not additional upload artifacts.
- `build.log`, `test.log` and the copied project's detailed test outputs: local
  diagnostics, retained after failure as well as success.

The upload report deliberately includes only bounded test names/statuses/counts
and hashes. Raw runtime reports, absolute paths, logs and test captures remain
local. The package hash is checked again after testing; a prepared attempt's
file digests and input relationships are verified before it can be consumed by
the forthcoming upload client. Inputs and prepared artifacts are read-only to
discourage accidental edits; integrity comes from verification, not file modes.

The result is a **developer-local assertion**. It does not prove an independent
source rebuild or physical qualification. Store ingestion checks package/source
structure, every digest, current authorization, ownership and version/revision
rules before signing and publishing.

## Publish and update

```sh
lefony-sdk login
lefony-sdk --project ./my-app publish
# Later: edit source/listing files and increase app.json's version.
lefony-sdk --project ./my-app publish
lefony-sdk apps show my-app
```

An explicit `publish` creates a store release after the local build/tests and
server checks, without another website form or approval step. It prints the
accepted release, immutable version, signed and unsigned package hashes, and app
URL. It creates a local project link for the current store/account/app and keeps
the observed listing revision. It does not install onto any calculator.

For an app already owned on the store but not linked locally, inspect it with
`apps show APP_ID`, then use `project link APP_ID` from the matching project.
The first link captures the current revision; repeating the command preserves
that baseline. A later website edit or withdrawal makes the SDK baseline stale
and stops publication. Do not use unlink/relink merely to dismiss this conflict:
review and reconcile the source/listing changes with `listing pull` first.

Versions must be strictly higher numerically than every previously submitted
version. The SDK never bumps a version automatically. Repeating the exact accepted
submission returns its receipt; different bytes at the same version fail.
An older receipt retains its original publication revision, so replaying it
cannot treat subsequent website edits as reviewed or roll back a newer local
publication baseline.

## Pull and merge listing changes

```sh
lefony-sdk listing pull --dry-run
# Open the printed local preview and inspect each local/store difference.
lefony-sdk listing pull --plan PLAN_ID --take-local description --take-remote screenshots
```

Unlike `publish --dry-run`, this review authenticates and downloads owner-only
listing metadata and images. It never uploads or publishes. Plain `listing pull`
applies non-conflicting changes immediately; conflicts return exit status 1 with
the plan ID, affected fields and preview path. Use `--dry-run` when every change
should be reviewed before applying it.

The SDK compares the saved store baseline, current local files and an exact store
snapshot. A field changed on only one side is retained from that side; different
edits to the same field require an explicit choice. Repeat `--take-local` or
`--take-remote` for `name`, `description`, `release_notes`, `repository_url`,
`icon` and `screenshots`. The ordered screenshot set is one field. Taking store
screenshots replaces the local PNG set with `01.png`, `02.png`, etc.; the review
shows both sets first. Other files in `store/`, including screenshot instructions,
remain intact. A missing or incomplete remote media set does not delete local
images. Older revision-only baselines use conservative conflict handling when
existing local and remote values differ.

Applying a plan rechecks its account/app binding, the full store snapshot and
the raw local file hashes. Intervening edits require a new review. Pulling a name
can change only `app.json`'s name: version, ID, ABI, license and source files stay
as authored. Rebuild and test after changes before publishing. Pull never enables
`publish_source`; a missing listing configuration is created with permission off.
The saved baseline records the store content, even when you keep different local
edits. Replaying an old publication receipt cannot acknowledge newer store edits.

Private review files live under `.lefony/listing/PLAN_ID/`. Applying uses a journal
with original/replacement bytes and writes the store baseline last. Ordinary
write errors roll back; a process interruption blocks later publish/pull/link
operations until explicit offline recovery:

```sh
lefony-sdk listing recover PLAN_ID
```

Recovery restores exact original bytes only when each file still matches either
its saved original or replacement. If you edited it after interruption, recovery
stops and retains the journal for reconciliation. This is process-interruption
recovery, not qualification of host disks under physical power loss. Keep
`.lefony/` private and out of Git; it is excluded from source submission.

The matching website requires the revision captured when source was selected for
an update and checks it again at commit. It also stores release notes and an
optional repository URL. Use its listing review to compare the current form with
saved text/images, copy selected fields and explicitly accept the reviewed
revision. Selecting another source file alone does not dismiss a conflict.
For metadata-only edits, use `listing push` as described below.

## Resume, inspect and cancel

Each operation prints the local attempt UUID before any upload. Reuse that UUID:

```sh
lefony-sdk --project ./my-app publish --status ATTEMPT_ID
lefony-sdk --project ./my-app publish --resume ATTEMPT_ID
lefony-sdk --project ./my-app publish --cancel ATTEMPT_ID
```

`--resume` also uploads a successful dry-run attempt. It rechecks the retained
input proof and all artifacts, without rebuilding or reading later source edits
into the submission. It transfers only missing 256 KiB chunks, verifies each
completed file and finalizes the exact manifest. A dropped request gets at most
three identical attempts per operation; later manual resume queries server
progress. Authentication is checked again, and an attempt cannot move to another
account or store. Local publication operations on one project are exclusive;
their operating-system lock is released if the process exits unexpectedly.

`remote.json` stores the account/origin, submission digest, base revision and
remote attempt ID before transfer. `receipt.json` records acceptance. Neither
contains a credential. If local tracking cannot be saved after remote acceptance,
the CLI still reports the accepted release and the tracking problem. Status can
retrieve its durable receipt even after staging cleanup. Status and cancellation
also work when a local payload has been lost or new publication is disabled.

Staging expires after 24 hours. At most three unexpired attempts per account are
retained; cancelled or invalid attempts count until cleanup. Expired/conflicting
staging requires a reviewed fresh attempt; never alter retained artifacts to
reuse an old ID. Cancelling staging does not withdraw an accepted release. Its
status reflects later website withdrawal without republishing the release.

Store commands accept `--store-origin` and `--store-ca-file` for a controlled
development store. HTTPS certificate/hostname checks, no redirects or ambient
proxies, bounded bodies and socket timeouts remain enabled. Local TLS/Worker/ARM
journeys are development evidence; production GitHub/store accounts, clean hosts, complete
website parity and coordinated distribution still require qualification.

The current macOS desktop candidate passes a 37-step frozen-executable journey
against the actual local Worker/D1/R2 handlers. It signs in through SDK
authorization/session endpoints using synthetic browser-approved accounts and
native Keychain, resumes interrupted uploads, updates and merges listings,
withdraws and republishes. The exact signed store download then passes frozen
SDK inspection and normal ARM installation/launch using the public emulator
fixture key. Temporary credentials/project records are removed. The companion
source-mode journey passes 28 steps. See the
[implementation ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md) for exact artifacts;
this is not real GitHub OAuth, production publication or physical installation.

## Edit a listing without publishing a new version

```sh
lefony-sdk listing push --dry-run
lefony-sdk listing push
lefony-sdk listing push --status OPERATION_ID
lefony-sdk listing push --resume OPERATION_ID
```

These commands use the linked project’s name, description, release notes,
repository link, icon and ordered screenshots. They do not compile, upload
source or change executable bytes/version. Source-sharing permission can remain
false. A complete icon/screenshot set is still required; a missing local image
does not delete remote media. Unchanged owned images are referenced by digest.
`--dry-run` authenticates and reads the store, returning a field comparison
without submitting an edit. Unlike `publish --dry-run`, it is not offline.

The saved baseline must match the current store revision. A stale push returns
conflicts; use `listing pull --dry-run` and apply the reviewed merge first.
Before sending, the SDK writes the exact request and its identity/digest under
`.lefony/operations/OPERATION_ID/`. Keep this directory private. A failed request
prints its saved ID; status reads the durable receipt, and resume sends the same
request even if local source or listing files have since changed. An unknown
receipt is reported as unaccepted, not as proof that a timed-out request cannot
still finish. Retrying the saved ID is safe. Do not edit the saved request.

Accepted receipts retain the original commit revision and content. Reading an
old receipt cannot acknowledge later website changes or roll back a newer local
baseline. A local tracking failure is reported separately from remote acceptance.
Each metadata revision describes one release and keeps its prior revisions.
A newer executable release starts with its own submitted listing. Metadata edits
to a withdrawn release do not make it public again.

The website’s **Your apps → Edit listing** offers the same fields and conflict
review. An interrupted save keeps the exact request for retry/status while that
page remains open. Closing the page discards that browser draft; reopen the
listing to read its current stored state. CLI journals survive process exit.

## Withdraw an owned app

```sh
lefony-sdk apps withdraw my-app --dry-run
lefony-sdk apps withdraw my-app
lefony-sdk apps withdraw my-app --status OPERATION_ID
lefony-sdk apps withdraw my-app --resume OPERATION_ID
```

Withdrawal needs an authenticated owner but no local source folder. It removes
every active version and pending submission atomically, preserving history,
ratings, ownership and installed copies. Its private host journal is isolated
by store/account/app. A changed revision rejects the request; a replay of an
accepted withdrawal never removes releases published later. Withdrawal and
receipt reads remain available while new publication is paused.

To republish, review/pull the changed listing state, choose a higher unused
version in `app.json`, enable source permission and run `publish`. Withdrawal
does not refresh project baselines or uninstall calculator apps.

## Bundled installation data (source SDK candidate)

Publication schema 2 can carry up to 32 MiB of initial app files separately
from the executable. The total upload remains below 16 MiB; gzip data is at
most 12 MiB split into one or two 8 MiB parts. Existing schema 1 publications
and executable limits are unchanged. This feature requires the updated source
CLI; previously downloaded frozen SDKs do not understand `.lfbundle` files.

Add `notices/bundled-data.txt`, a JSON descriptor with `schema: 1`,
`encoding: "gzip"`, total `bytes`, SHA-256, and ordered `files` records containing
`path`, `offset`, `bytes`, and `sha256`. Put the matching public inputs in
`data/`. Only flat `.wad`, `.bin`, and `.txt` files with bounded safe names are
allowed. Include redistribution licenses in both the source notices and data.
The source download retains the descriptor; large data travels separately in
the complete app download. No source-tree files are uploaded implicitly.

`publish --dry-run` snapshots and hashes these inputs, installs them through
synthetic USB before its ARM replay, and binds the tested files to the source
and publication. The store checks bounded expansion and all file hashes. It
signs companion metadata with the existing app key, binding data to the exact
signed package. The website downloads and verifies everything before installing.
Existing matching files are verified and preserved; conflicting files cause an
error, never replacement. Updates prepare missing data before the new package
so the firmware's pending-upgrade protection remains intact. An already pending
upgrade must be resolved normally before new files can be imported.

The website's **Download app** returns a complete `.lfbundle` for releases with
data, or the original `.lfapp` for other releases. The source CLI accepts:

```sh
lefony-sdk install app.lfbundle --public-key store-public.pem
```

It validates both signatures, package binding, compressed and expanded hashes
before opening USB. File commits remain bounded, create-only and independently
verified. Interrupted installations can leave the app and some completed data
files; refresh/verify finishes missing inputs without rewriting saves. No
firmware upgrade, flash-layout change or signature bypass is involved.

## Short and detailed descriptions

Set `short_description` in `store/listing.json` to a single sentence of 1–120
UTF-16 code units (an emoji can count as two). This text appears in catalog rows.
Keep the full explanation, controls, requirements and limitations in
`store/description.md` (up to 2,000 units), shown on the app detail page.

```json
{
  "schema": 1,
  "publish_source": true,
  "short_description": "Explore and rotate 3D graphs on your Prime."
}
```

New projects include an empty short-description field that must be filled before
publishing. Existing projects that omit it retain compatibility; the store uses
a brief first-sentence fallback without altering their detailed text.
`publish --dry-run` previews both descriptions. `listing pull` and `listing push`
merge and edit them independently; use `--take-local short_description` or
`--take-remote short_description` to resolve a conflict. Pulling a listing records
its short description in `store/listing.json`.

The updated client negotiates both fields with `X-Lefony-Listing-Fields:
descriptions`. Older clients continue receiving their original listing/receipt
shape. Their listing-only edits preserve an already authored short description.
Previously prepared publication manifests and saved operation requests remain
byte-identical when resumed. Reinstall the SDK to get both editable fields.
