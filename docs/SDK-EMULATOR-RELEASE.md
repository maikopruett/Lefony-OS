# Browser emulator SDK development release

Updated 2026-09-16 UTC. The macOS ARM64 and Linux x86-64 SDK **0.2.0-dev**
bundles and matching sources are available at [Developer downloads](https://lefony.com/#developers).
Normal interactive `run` opens a browser panel with all 50 Prime matrix keys
underneath a 640×480 touchscreen. The screen menu offers 1.5×, 2× and 3× scaling.
Save through the application, then use **Stop emulator** to drain workspace storage.
Closing the browser tab releases keys but leaves the terminal session running.

## Downloads and installation

The installer verifies the platform archive, runs doctor and a fresh starter
replay, and then links the command. Current prefixes are
`0.2.0-dev-20260916-macos-arm64` and `0.2.0-dev-20260916-linux-x86_64`.
Linux requires x86-64 and glibc 2.39+. The separately labelled September 11 ARM64
source-build fallback remains older and unqualified; it does not include this panel.
Native Windows source inputs were refreshed locally, but no complete Windows
executable is available. WSL browser opening remains unqualified.

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| lefony-sdk-darwin-arm64.tar.gz | 156634251 | `fd885d62d2b404a32d962abafc0f01273e2ebadac826a1250cfda7612b5f4eba` |
| lefony-sdk-source-toolchain.tar.gz | 180139527 | `2c1c4b25e65a6d31426f59cf022e4f6cd8f7cde0dee492f301672dcc7d5e1b8c` |
| lefony-sdk-source-runtime.tar.gz | 396258029 | `7613626b38488142961192ab3437f1f066a45babcd93cfe01c02387abc9e46d2` |
| lefony-sdk-source-lefony-qemu.tar.gz | 51699491 | `8cfc1e17aadfccd780d8781dbcfd9828b2dc97ed006b12d322f12ef4bc632525` |
| lefony-sdk-linux-x86_64.tar.gz | 208542511 | `fa3df390a2253efbd3c0019b83ac9a0b266275c2ef27766a64a1f65bbd5740b6` |
| lefony-sdk-linux-source-toolchain.tar.gz | 180138009 | `be5786ad45c710bf44bef496f730babeb4aedb342abbbd73bcc6e0c034dff581` |
| lefony-sdk-linux-source-runtime.tar.gz | 787567038 | `3b006c79860c5fc8da6f022b5eb9e03420dbf97f17c90cdc30f3d6a0a4f76703` |
| lefony-sdk-linux-source-lefony-qemu.tar.gz | 52267618 | `30cacfff41bcc651478e01cd08d60fd83815ea7b857f44459f038df72c6cbb9a` |
| lefony-sdk-legacy-arm64-source.tar.gz | 50982147 | `0632769771b528bc93b8ed055f519c3676e6f7fe3b8ff1089d32b5d58a79fe84` |

The standalone SDK source kit is `8d0e8c024fa01452aab5fd95539cecdf548b9f7690a93b2a0815360a5a6e3e7e`. Download the three
corresponding source groups for the complete platform dependencies and notices.
The source snapshot predates this final release note; SDK modules match the
frozen executables. Firmware and release trust are unchanged.

## Validation and limits

Both archives passed complete member/hash/mode/link verification and frozen CLI
checks. macOS browser testing exercised all 50 keys, physical keyboard input,
Goodix touches at all zoom levels, normal Stop and cold restoration of an actual
saved Notebook expression. Linux testing exercised the exact bundled HTTP panel,
KPP/Goodix input, headless replay, normal Stop and saved/cold Notebook under
x86-64 emulation on the ARM build host.

Every current archive passed full R2 SHA-256 readback. Public macOS/Linux
binaries and the standalone SDK source kit also passed full HTTPS download hashes.
All catalogue routes match size/hash/filename headers; each current route body
prefix matches the local archive. The larger corresponding-source public streams
were stopped after their complete R2 verification. Public installer bytes match
the sealed build.
Website build, lint, Worker dry-run, 36 focused tests (one skipped), and two
SDK desktop/mobile browser journeys passed. The initial 5-second installer-test
limit was exceeded under concurrent build/upload load; the same tests passed
with a 30-second command-line test limit, without changing their assertions.
The OS public-tree check passed.

Production version: `1654419c-3fba-4b3d-8a2a-9f53e2347336`. The compiled Worker stays byte-identical
to the preceding production version. Only static assets and SDK catalogue/source
variables change; database schema, app records, quotas and trust stay unchanged.
Public installer SHA-256: `912f603665ba2097fa3ac5bcf9ab28a60c57664bc835d6a906d508b471bc70d6`.

Current local release evidence is in `build/sdk-emulator-bundles-v1/`; website
readback, public download, installer and sealed deployment evidence is in the
sibling website's `.local/sdk-panel-release-v1/`. Old local SDK distributions
were deleted at the user's request after replacement verification. Checksum and
test receipts remain; developer projects/workspaces, release keys, recovery data
and current component inputs were preserved. Remote historical objects remain.

The real public macOS installer passed its fresh starter replay, full installed
archive audit and repeat-install check. The new CLI reads the existing SDK
session from native Keychain, and the original Notebook workspace reopens with
identical content. Its local restart shortcut now uses the installed command.

Cleanup removed 125 superseded SDK archives and 18 old extracted bundles,
plus one redundant current extraction and installer archive cache. Observed
free space increased by 15.7 GiB to 17.6 GiB. This is net free
space during the task; APFS cloning and concurrent system activity affect it.

These are development artifacts. macOS Developer ID/notarization, clean-host
acceptance, native Linux/Windows, independent trials and physical calculator
USB/input/performance/power-loss/flash durability remain unverified. The user's
current trial scope is maintainer macOS feedback. SDK 1.0 remains incomplete.
