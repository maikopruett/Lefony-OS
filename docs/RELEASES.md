# Automatic development packages

Every successful `main` push runs host tests, compiles the physical and emulator
targets, builds a boot capsule, signs LFU1 with the existing Lefony release key,
and publishes a GitHub prerelease. Pull requests can build but cannot publish
or access the signing secret. Manual workflow runs on `main` also publish.

The workflow is `.github/workflows/native-emulator.yml`. Configure the Actions
secret `LEFONY_UPDATE_PRIVATE_KEY` with the existing RSA private key matching
`ports/lefony-prime-g2/release-signing.pub`. Never generate a replacement identity
in CI. Signing fails if the key is missing or does not match. Secrets are used
only in the packaging job, after build and test jobs succeed.

Update versions use the existing protocol baseline `1.0.0` plus the build's UTC
Unix timestamp (unsigned 32-bit). That version is compiled into the physical
updater's fallback identity and signed into LFU1. Local builds retain their
historical baseline. Settings also retains the separately maintained product
version in `LEFONY_VERSION`. Concurrent main builds cancel older runs.

Each release has a unique `build-RUN_ID-ATTEMPT` tag. Assets are uploaded to a
draft before publication, so consumers never discover a partial release.
Do not replace assets or move a published tag: publish a new build instead.

- `lefony-os-prime-g2.zip`: native firmware, signed update, emulator ELF, public
  verification key, build metadata and license notices.
- `lefony-os-source.tar.gz`: this repository at the source commit and the full
  prepared upstream tree used for the physical build, including submodule source
  and upstream license notices. Generated outputs and Git metadata are excluded.
- Individual firmware, LFU1, emulator and public key downloads.
- `lefony-release.json` and `SHA256SUMS`: exact lengths and SHA-256 hashes.

The release body embeds the same manifest inside a `lefony-release-v1` HTML
comment. The website reads public GitHub REST release metadata (which supports
browser CORS), filters out drafts, and chooses the newest matching published
release. It then pins downloads to that tag. No GitHub account, access token,
website rebuild or hand-edited download URL is needed. Prereleases intentionally
do not become GitHub's stable `/releases/latest` target.

These are **development packages**, not physically qualified installer bundles.
Automated compilation and host tests do not establish hardware acceptance.
No private/vendor recovery assets, device backups or production private key are
included. The website offers the package download while keeping physical install
disabled until the complete recovery bundle and hardware qualification exist.
The website's `docs/RELEASES.md` documents that future `ready` manifest contract.

## Preparing a browser recovery release

`scripts/prepare_browser_recovery_release.py` audits local recovery inputs and
assembles a separate distribution from an existing signed development release.
It does not rebuild or re-sign the firmware, access a calculator, or publish.
The automatic development workflow remains unchanged.

First prepare a private `candidate.json` beside an `artifacts/` directory. Use
`schema: 1`, `status: "recovery-candidate"`, the signed firmware's `version`, and
an `assets` object. Each descriptor contains `path: "artifacts/FILENAME"`, exact
`bytes`, and `sha256`. Include these eight asset names:

- `capsule`, `publicKey`
- `recoveryUboot`, `recoveryKernel`, `recoveryDtb`, `recoveryInitramfs`
- `baselineUboot`, `baselineHistory`

The baseline history must contain one qualified entry with `artifact:
"baseline.imx"`. Its hash, size, version, IVT offset and boot environment must
match the actual baseline bytes. Preserving an original Prinux manufacturing
command is supported; it does not imply that any stock HP bootloader can boot
Lefony. Both installed baseline copies must still match before writing.

Audit without distributing or changing anything:

```sh
.venv/bin/python scripts/prepare_browser_recovery_release.py \
  --bundle build/recovery-candidate/candidate.json
```

The audit verifies the capsule against the checked-in release public key, all
eight hashes and sizes, the baseline history, RAM image headers and address
overlap, and space for the browser's recovery-exit command. Its output remains
`recovery-candidate`. A structural pass is not physical acceptance.

Before assembly, add `recoverySource` and `recoveryNotices` descriptors and files
to the candidate. They must contain the corresponding source, build inputs,
changes and applicable notices for the distributed recovery components.
Maintainers must establish their provenance and redistribution suitability;
the script checks byte integrity, not license compliance. Do not substitute a
private recovery archive or calculator dump for corresponding source.

Place the existing GitHub release's `lefony-release.json` and its six referenced
assets together in a private directory, with flat filenames. Then assemble:

```sh
.venv/bin/python scripts/prepare_browser_recovery_release.py \
  --bundle build/recovery-candidate/candidate.json \
  --package build/downloaded-release/lefony-release.json \
  --output build/recovery-release-candidate
```

This copies only the explicitly described artifacts, creates `SHA256SUMS`, and
embeds the resulting manifest in `release-notes.md`. It refuses an existing
output directory or a firmware/key mismatch. Without acceptance, the output
keeps `status: "package"` and cannot enable browser recovery installation.

For a qualified release, additionally pass `--acceptance PATH` pointing to the
actual hardware test record. That JSON must contain:

- `schema: 1`, `model: "HPG2"`, `qualification: "physical-verified"`.
- `version`, `payloadSha256`, and `assets` matching the audit output exactly.
- `browserRecovery: {"protocol": 1, "target": "single-slot-mtd1"}`.
- `evidence`: a description or reference to the retained real hardware evidence.
- `checks`: true values for `romBootstrap`, `deviceIdentity`,
  `baselineComparison`, `nandWrite`, `nandReadback`, `normalBoot`,
  `tabLossContinuation`, and `browserRecoveryExit`.

Record these results only after testing the browser path on the exact bundle.
An earlier UUU installation or another firmware hash does not qualify it.
The tool checks the record's completeness and byte identities; it cannot
independently establish that a human's hardware observations occurred.

An accepted output has `status: "ready"` and the explicit `browserRecovery`
contract already understood by the website. Upload every output to a new draft
GitHub release, use `release-notes.md` as its body, then publish only when that
publication is authorized. Do not replace the current release's assets.
Private test logs and acceptance records are not copied into the output.
