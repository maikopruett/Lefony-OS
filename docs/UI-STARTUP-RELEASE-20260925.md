# App launch and touch selection release

Published development version `1.0.0+1790315562` on 2026-09-25 UTC:
[GitHub release](https://github.com/maikopruett/Lefony-OS/releases/tag/build-20260925-1790315562).
The live Lefony website discovers this release automatically. Its latest-manifest
endpoint returned the same version, asset hashes and release tag after publication.

This combines the [installed-app launch optimization](APP-LAUNCH-PERFORMANCE.md)
and [Home touch selection change](APP-INSTALL-AND-HOME-ORDER.md#touch-selection-feedback--local-follow-up).
Authentication remains mandatory; the loader returns verified metadata to avoid
repeating validation. Touch hides selection feedback and directional-pad
navigation restores it. Existing release/app trust roots and the pinned one-shot
U-Boot recovery bundle are unchanged.

## Exact release artifacts

| Artifact / target | SHA-256 |
| --- | --- |
| Physical HP Prime G2 `prime_g2` binary | `2c911bc147ece658cab6bfb3c524fd1959dade3f7c95c728fd618bdf28c0f0bb` |
| Emulator `prime_g2_vm` ELF | `cb177401b764d75024200c27c4f93bd88fef8424479273d40f94cbe1366c3614` |
| Signed LFU1 capsule | `88deb929c7edebd1fcd6924f724ae1581e0b5e9e492b95dd65950b3a6f7781a3` |
| Corresponding-source archive | `bdf6f25f1b7ac77ff58145a6f7f4c42b668ede5cf258f2b55b8ec2b2996bea22` |

The source archive contains the audited public working tree and prepared physical
firmware sources. Base commit `a017cd036dbda18afb71e5536bed141c0b6b2ad3` identifies
the starting revision; the manifest's `sourceState` binds the actual shipped
source. No branch commit or push was made. This publication record was written
after publication and is not part of that source snapshot.

## Validation

Builds used `LEFONY_RELEASE_VERSION=1.0.0+1790315562`,
`LEFONY_APP_PUBLIC_KEYS=ports/lefony-prime-g2/app-trust-roots.json`, and the
physical target additionally used
`LEFONY_UPDATE_PUBLIC_KEY=ports/lefony-prime-g2/release-signing.pub`.
`make firmware-vm` and `make firmware` passed; the physical source was captured
after its build. The existing private release key matched the checked-in public
identity before signing.

- `make test`: 1,981 passed, two expected private DTB/DTS skips.
- `vm/test-home-app-order.py --firmware <release-elf>`: all ten checks passed;
  Goodix touch, ordinary event dispatch, cold NAND persistence and screenshot
  comparisons were exercised. Selection captures were visually inspected.
- `vm/test-sdk-contracts.py --firmware <release-elf>`: all 12 cases passed,
  including five signed-loader rejection cases. The optional historical-loader
  comparison was skipped because no pre-schema-1 ELF was supplied.
- `vm/test-prime-coordinate-touch.py --elf <release-elf> --calculation-history`:
  passed touch, keypad, scrolling and cancellation regression checks.
- `vm/native-suite.py --suite smoke`: all four selected cases passed with the
  release ELF hash recorded in its report.
- `make check-public`, source snapshot comparison, archive member/hash checks,
  LFU1 verification, ZIP checks and `git diff --check`: passed.
- Website `npm run release:validate-browser -- <manifest> <release-directory>`:
  recovery files, signature, baseline, RAM layout and exit plan passed.
- All 16 uploaded files were downloaded from the draft and their lengths and
  SHA-256 hashes checked before publication.
- Website `npm run release:check-latest`: discovered this published version,
  downloaded its capsule/public key and passed lengths, hashes and LFU1 signature.
  A separate live website manifest check matched the packaged metadata and hashes.

Evidence is retained locally under ignored `build/ui-startup-release-20260925/`.
Python's initial request to the website manifest returned HTTP 403, and direct
browser navigation to that JSON endpoint was blocked by the browser client.
The ordinary curl request returned HTTP 200 and the expected manifest; the
website's own release checker also passed independently.

No calculator was accessed or flashed. This is a build-tested development
release, not physical qualification. Surface 3D launch timing and touch feel
still need testing on hardware; the earlier Counter speed measurements are
emulator measurements. Existing physical power-loss and endurance limitations
remain open.
