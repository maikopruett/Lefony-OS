# Linux SDK public development release

The current Linux and macOS bundles include the larger browser emulator and
clickable Prime keyboard. See the [current release record](SDK-EMULATOR-RELEASE.md)
for their updated hashes, matching source kit, installer versions and checks.

The sections below record the preceding Linux candidate's immutable hashes and
qualification. Its local archives were deleted after replacement verification;
checksum and test receipts remain. These historical checks are not newly claimed
for the refreshed archive.

## Installation and host requirements

Use the Linux commands on the developer page. The installer selects the complete
x86-64 bundle and requires glibc 2.39 or newer (for example Ubuntu 24.04).
It rejects older glibc, musl and an unavailable version before creating files or
downloading the SDK. It needs curl and CA certificates; the archive supplies the
compiler, Python, ARM GDB, libraries and Prime emulator. Allow about 1.1 GB for
installation. Graphical use needs a desktop; account commands need a running,
unlocked Secret Service. WSL x86-64 uses this bundle but remains unqualified.
Linux ARM64 retains a separate source-build path using the older snapshot.

The installer verifies the pinned archive checksum, runs doctor and a fresh
normal-input starter-app test, and only then marks the installation complete and
links the command. Reinstallation checks the existing complete installation.
The default Linux release directory is `0.2.0-dev-20260915-linux-x86_64`.

## Immutable public artifacts

Every artifact below passed a full local hash, R2 streaming readback and public
HTTPS download check. Public responses also matched size, hash and filename.

| Filename | Bytes | SHA-256 |
| --- | ---: | --- |
| lefony-sdk-linux-x86_64.tar.gz | 208471835 | `7cdf903b53a6748979928377b829fe5735fb6dfbd6fd627c5563ac7fd63ec01f` |
| lefony-sdk-linux-source-toolchain.tar.gz | 180138009 | `be5786ad45c710bf44bef496f730babeb4aedb342abbbd73bcc6e0c034dff581` |
| lefony-sdk-linux-source-runtime.tar.gz | 787523227 | `3a519b96677fe85b865dd431c04a5977ae5cb12da58b6357f65a5e328e43519f` |
| lefony-sdk-linux-source-lefony-qemu.tar.gz | 52222892 | `c044a003c3b283d84d5b56c0363547cfeb83afb51b308c235e84124a5b49fd4f` |

Download links use `https://lefony.com/api/store/sdk/artifacts/` followed by the
full hash. Select all three source archives labelled Linux for corresponding
sources and notices. Existing macOS artifact bytes and filenames are unchanged.

## Public journey evidence — 2026-09-16 UTC

A normal user in an Ubuntu 24.04 container downloaded the real public installer
and archive into a path with spaces and an accented character. All eight driver
steps passed: installer download, installation, linked doctor, repeat installation,
SDK Counter download, signature inspection and two independent ARM launches.
The starter report records one normal-input test passed with no failures/skips.
The unchanged store-signed SDK Counter package passed with the bundle's default
production trust key and VM firmware; no replacement signature was used.

These x86-64 programs ran under explicit emulation on an ARM host. This is not a
native Linux desktop, clean-host, interactive credential or physical USB result.
The frozen archive's earlier source/dependency, account, publication, GDB and
companion checks retain their scope in the
[SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).

Production deployment `91d6a92c-32aa-4447-acdb-e74d031acf7b` serves the eight-entry
SDK catalogue. Its compiled Worker is unchanged from the preceding production
version. Submissions remain enabled and both legacy deletion gates remain off.
Post-rollout database checks show two apps/two published releases, unchanged
162,505-byte managed usage, valid foreign keys and `quick_check=ok`.
The R2 bucket contains 41 objects totalling 2,430,725,336 bytes. A separately
reviewed SDK/archive allowance is now 4 GiB; managed app quotas are unchanged.

Website build/lint, 566 unit tests (one skipped) and all 62 browser tests pass.
Desktop/mobile views were inspected, including separate platform source groups.
The public installer SHA-256 is
`89f2698bb8a9f480d9745b1c0f09fca4927cfddbdb179c7747d2cac81c40a096`.

Local evidence is under `build/sdk-linux-web-install-v1/`; the sibling website's
private rollout evidence is `.local/sdk-linux-release-v1/`. Original SDK/source
archives remain in `build/sdk-linux-store-assembly-v1/`. The test extraction was
compared against all 5,524 archive files/links; only expected installer-user
ownership differed. The wrapper, completion marker and full starter project are
retained in a verified delta archive. Only the redundant 1,050,008 KiB test
extraction was removed, and its container was stopped. Existing recovery data,
release keys, archives and app artifacts remain retained.

## Remaining acceptance

Native Windows packaging, clean native hosts, physical calculator input/USB,
performance, power-loss recovery and flash durability remain open. The current
user trial scope is maintainer testing on macOS; independent developer feedback
has not been collected. No GitHub release, commit or push accompanies this rollout.
