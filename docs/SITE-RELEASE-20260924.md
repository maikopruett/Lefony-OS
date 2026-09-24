# September 24, 2026 website release

Published calculator OS development build **1.0.0+1790259014** at
[build-20260924-1790259014](https://github.com/maikopruett/Lefony-OS/releases/tag/build-20260924-1790259014).
The [website installer](https://lefony.com/#install) discovers this release through
its existing release service; no website deployment was needed.

## Artifacts and provenance

The release contains 16 assets: physical firmware, VM ELF, signed LFU1 update,
ZIP package, corresponding source, public signing key, eight pinned recovery
files, manifest and checksums. Existing release signing identity, recovery pins,
trust policy and storage layout are preserved.

| Artifact | SHA-256 |
| --- | --- |
| Physical firmware | `ebfedfbc7e8df0a6e0fc52dfc856b43a6fabccf1fd85851ce649806acc449105` |
| Signed LFU1 update | `f30afa6939504badade27996cefdd199c55387d95cad4e1b7977f004c95346f5` |
| VM ELF | `d91c762a11692e8345b8d521844f466ae55d1e45205d2e3f50c66444cd0978d8` |
| Corresponding source | `57455398acad0cd5b31fc9062f23ac5e7c773e94a29b1a93f4466f33075f64ab` |

This is an audited working-tree build based on
`91701e213d74918226b3692f570079c2c13d9000`, not a clean build of that commit.
The manifest's `sourceState` identifies this explicitly and binds the actual
source archive hash. The archive includes the public working-tree snapshot and
prepared physical firmware sources. This release record postdates that snapshot.
No Git commit or branch push accompanied publication.

## Validation

- `make firmware` and `make firmware-vm` passed with the release version above;
  the NAND capsule was built with `scripts/build_prime_g2_nand_capsule.sh`.
- `make test`: 1,922 passed, two expected private DTB/DTS fixture skips.
- Focused release-package and browser-recovery tests: 23 passed, including
  working-tree provenance checks.
- `vm/native-suite.py --suite smoke`: all four checks passed using the published
  macOS SDK's QEMU (EP0 stall, direct ELF boot, smoke and protocol).
- The installed public macOS SDK passed a fresh Notebook `tests/edit.json`
  headless replay with this release's VM ELF.
- Package checks verified the production-key signature, exact version and
  physical payload, ZIP members, asset hashes and source provenance.
- The website's `release:validate-browser` passed its signature, recovery,
  baseline, RAM layout and exit-plan checks without accessing a device.
- All 16 GitHub assets matched their expected hashes. Full public downloads of
  all eight website firmware/recovery routes, the ZIP and source archive matched.
  The live latest manifest selected this exact version, and the website's
  `check-latest-release.ts` passed discovery, lengths, hashes and LFU1 signature.
- Public-tree and changed-file whitespace checks passed.

Local evidence is retained under `build/site-release-20260924-v1/` and the
sibling website's `.local/site-release-20260924-v1/`.

## macOS SDK

The latest macOS ARM64 SDK **0.2.0-dev** is already published at
[Developer downloads](https://lefony.com/#developers). Its executable source
matches the current checkout: 365 non-documentation files matched, and the SDK
code identity matched the installed frozen CLI. Generated runtime/trust inputs
were excluded from repository-path comparison. No redundant rebuild or upload
was performed.

The full public archive hash remains
`fd885d62d2b404a32d962abafc0f01273e2ebadac826a1250cfda7612b5f4eba`.
Its three corresponding-source archives matched their local hashes and public
headers/body prefixes; previous full R2 readback evidence remains retained.
The live developer page shows this exact macOS archive and the larger browser
emulator with clickable Prime keys. See [the SDK release record](SDK-EMULATOR-RELEASE.md)
for dependency hashes and installation requirements.

These remain development releases. No calculator was flashed for this release;
physical acceptance and the remaining SDK 1.0 qualification are still open.
