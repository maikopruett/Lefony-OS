# Device-only desktop emulator — 2026-09-25

The OS launcher and SDK now display only the complete HP Prime device artwork,
live LCD and clickable keys. The page heading, toolbar, connection footer and
help expander have been removed. Native menus provide File → Stop Emulator,
View → Layout / Scale / Fit to Screen, and Help → Keyboard Shortcuts and Saving
/ Connection Status. macOS uses the system menu bar; Linux and Windows use the
desktop's application menu placement.

The whole device fits both window dimensions without clipping the keypad.
Native menu changes release held input. Stop and close retain the existing
SDK workspace-save and QEMU shutdown lifecycle. The OS and SDK use the same
renderer and native host; no browser launch or firmware behavior changed.

## Distribution and evidence

The website's macOS ARM64 and Linux x86-64 downloads and standalone source kit
include the new renderer, native menu host and bundled keyboard assets. The
installer uses `20260925-device1` prefixes, retains existing installations and
can update command links from the preceding `desktop1` release. Corresponding
sources and checksums accompany both bundles. Firmware, QEMU, compiler and
release trust identities are retained from the prior desktop SDK release.

- 190 focused renderer, desktop lifecycle, packaging and source-binding tests
  passed; the 11 skin/source-kit checks passed again after fixing the packaged
  screenshot reference. All 196 website SDK contract, catalogue and installer
  checks passed. Public-tree and whitespace checks passed.
- Source and frozen macOS window startup checks passed. Real QEMU sessions
  exercised native layout/scale menus, clickable calculator keys, SDK touch
  and keyboard input, native Stop and the close shortcut.
- Fresh frozen macOS and Linux SDKs passed doctor and starter-app checks.
  The macOS Notebook replay passed unchanged. Linux Notebook passed with 2 s
  settling intervals added between normal inputs; the original fast replay
  repeatedly missed the second Enter under nested CPU emulation, while the
  previous SDK passed the comparison run. The guest firmware, QEMU binary and
  input-module bytes are unchanged. This timing limitation remains open; the
  shipped replay was not modified. Linux window startup and clean shutdown
  passed under x86-64 CPU emulation with Xvfb; this is not native Linux/WSL
  desktop qualification.
  Sandbox disabling was limited to that isolated root test container.
- Every archived checksum member was verified; packaged renderer, host and
  keyboard bytes matched the selected source. All uploaded artifacts passed
  complete SHA-256 readback before updating the website catalogue.
- Public catalogue, installer and complete download bytes were verified after
  deployment. The website Worker and all other static assets were preserved.

The [README](../README.md#run-the-emulator) and [SDK guide](../sdk/README.md)
show unedited full-device desktop captures. See [desktop setup](EMULATOR-DESKTOP.md)
for dependencies and platform behavior. Native Windows SDK distribution and
native Linux/WSL interactive acceptance remain unqualified. No calculator was
flashed or changed.

## Published artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| lefony-sdk-darwin-arm64.tar.gz | 341640974 | `1a0935b3c5011f08df5d1fa4dfadcb71df0c72cc36fb0b5c6b7dda80127717aa` |
| lefony-sdk-source-lefony-qemu.tar.gz | 55771937 | `73748c0a9a21d7fcf6df7d1b7e6837a6753451cd1af9f4446251dda8c8ef76e8` |
| lefony-sdk-source-runtime.tar.gz | 396280310 | `e0136c43e35a79e0c0a2c72093e11cef07e02ddaed423b81d549b3869dbd3f2c` |
| lefony-sdk-source-toolchain.tar.gz | 180144434 | `3370c1f74f3f485af03ed1b66513ecdf1ca99c4f6a6e03bad1c3d744e49dd8bd` |
| lefony-native-sdk-source.tar.gz | 14884971 | `a9f5339290aee286d5c95da50a19f3803e5ca850a4928738369ac4fe7363ceed` |
| lefony-sdk-source-desktop-window.tar.gz | 1037997881 | `b59aba3a7e00d1ae4197c660fdecbb6419b7bbb5708305c579d84f1ae312be5d` |
| lefony-sdk-linux-x86_64.tar.gz | 439883713 | `8c26e709a3bb6621df407fbd1b379c0113193c6bfd324d940b985744807f8eb2` |
| lefony-sdk-linux-source-lefony-qemu.tar.gz | 55771897 | `38601082d72e9173cc7b24cc6479aa189dd8fa8b9b9310f3857ad660637e605b` |
| lefony-sdk-linux-source-runtime.tar.gz | 1039281284 | `b9e005f495a0929546ca8600addc8f3c4df5674e70301564d8a804844b314fc0` |

Website deployment: `ff6c5aa6-cadc-4f39-858d-b8f0a92e8c5b`.
