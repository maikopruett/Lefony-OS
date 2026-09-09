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
