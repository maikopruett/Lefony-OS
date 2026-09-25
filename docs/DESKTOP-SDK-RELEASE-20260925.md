# Desktop SDK download release — 2026-09-25

The SDK downloads and installer at [lefony.com](https://lefony.com/#developers) now
provide the shared desktop QEMU emulator with the bundled HP Prime keyboard.
`lefony-sdk run` and `launch` open the desktop window by default. The shared
renderer stays inside Qt WebEngine; no browser installation or browser launch
is used. Headless tests remain available.

## Distribution

- macOS 26+, Apple Silicon: complete frozen SDK, QEMU and Qt window bundle.
- Linux x86-64, glibc 2.39+: complete frozen SDK, QEMU and Qt window bundle;
  Ubuntu desktop dependencies are listed on the website and in
  [desktop setup](EMULATOR-DESKTOP.md).
- Windows instructions use the Linux SDK in Ubuntu 24.04 under WSL 2 with WSLg.
  A native Windows SDK download and native WSL qualification remain pending.
- ARM64 Linux has no current prebuilt SDK. The installer now rejects that
  platform explicitly instead of silently building the older September 11
  browser-based snapshot. Current source remains downloadable for manual work.

The installer uses new `20260925-desktop1` prefixes, pins both binary hashes,
and recognizes the previously published September 24 description-release
prefixes when updating its command symlink. It retains earlier installations.
The website retains prior content-addressed artifacts for rollback.

## Corresponding sources

Each platform has compiler, runtime dependency and Lefony/QEMU source archives.
A shared fourth archive supplies Qt 6.11.2 (including Qt WebEngine/Chromium),
PySide 6.11.2, wrapper/build sources and notices. Linux's compiler sources are
unchanged from the preceding release. The standalone SDK source kit includes
the shared renderer, desktop launcher and all keyboard assets.

`scripts/emulator_window_sources.py` maps frozen native window inputs to exact
wheel RECORD hashes, Homebrew formula versions or Debian source versions.
The SDK packager verifies those inputs and the pinned upstream Qt source
archives before recording `corresponding_sources_verified: true`.
The macOS inventory covers 330 native inputs; Linux covers 462. Matching source
availability is verified; rebuilding the upstream Qt wheels byte-for-byte is
not qualified (`source_rebuild_qualified: false`).

This refresh retains the preceding source-matched VM firmware and QEMU model;
it changes the launcher and packaged assets rather than the physical firmware.
The VM ELF SHA-256 is
`d5afc42f0bb32b118509c39c8cd2054d0e256af0466b968a88c3569f3bf1d8b2`.
The exact public source snapshot and prepared firmware/QEMU inputs are supplied
in each platform's corresponding source archive.

## Validation

- 105 focused desktop, SDK packaging and source-binding tests passed.
- `make check-public` passed.
- All 5267 macOS and 8644 Linux archive checksum members passed;
  keyboard assets and launcher files were compared with the release source.
- macOS frozen SDK: real desktop QEMU session, touchscreen counter increment,
  keyboard increment, clean shutdown and Notebook edit replay passed.
- Linux frozen SDK: doctor, starter app and Notebook edit replay passed.
  The embedded window rendered frames; touchscreen input incremented the
  counter from 0 to 1, its Prime Enter key incremented it to 2, and Stop
  returned an OS-responsive result. These checks ran under x86-64 CPU emulation
  with Xvfb. Chromium sandbox disabling was confined to that root test container;
  the distributed launcher retains the normal sandbox behavior.
- Website: 656 tests passed, one skipped; lint, build, companion tests and
  focused SDK installation/download browser journeys passed. Desktop and mobile
  screenshots were inspected. One initial parallel run hit a recovery-test
  timeout under load; the complete rerun with two workers passed.
- Uploaded artifacts passed complete SHA-256 readback before catalogue changes.
  Public downloads, catalogue, installer and website assets passed verification
  after deployment. A fresh installation through the public macOS installer
  passed doctor and starter-app tests in an isolated prefix. The deployed
  Worker implementation was preserved byte-for-byte.

These results do not qualify native Linux/WSL desktop behavior, a native Windows
SDK, physical hardware, or independent rebuilds of all upstream binary wheels.
No calculator was flashed or modified for this release.

## Published artifact identities

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| lefony-sdk-darwin-arm64.tar.gz | 341644754 | `181aee86153bc6cda200ba23416f519a88d58f1ed191c72f32cc0a0cff3e3136` |
| lefony-sdk-source-lefony-qemu.tar.gz | 55214730 | `5b90d7ac180aa03dbc70a549c6a0ed637fe934da67c0b99436d242034bd3115b` |
| lefony-sdk-source-runtime.tar.gz | 396280310 | `c92d67993d3c27b601237fbf39a4eedb760cafadf8a9ac4fc927096c9ee34a3b` |
| lefony-sdk-source-toolchain.tar.gz | 180144434 | `cc4b8f0d3b348da19d875739133b6014fef94e068d8ade080e9db0f72cb24f30` |
| lefony-native-sdk-source.tar.gz | 14941556 | `b68cb72bbe7fb70f090ff3a59ced38e6e39ab37287e5f63d4fa9dab3db118c42` |
| lefony-sdk-source-desktop-window.tar.gz | 1037996038 | `d3fd3babf0ecf454ad5e762f70576b4cb9a960f0db8d5b272cbde247cbf99caa` |
| lefony-sdk-linux-x86_64.tar.gz | 439886055 | `3a4bca27b861d46dc65570f8b4a7171d40a6839ab222b246fd39d6bd46dd61d5` |
| lefony-sdk-linux-source-lefony-qemu.tar.gz | 55214681 | `c11c5b91495d505d61d47edaf204d167cefa65ca8df7703063ccdd97e14f8626` |
| lefony-sdk-linux-source-runtime.tar.gz | 1038723701 | `00ad6a3cbfd2c329106f6a224c560a7eceaeb2852522e4b945670edc9259be47` |

Website deployment version: `16e0b92e-caac-4a73-a62b-0b2e5af55f33`.
