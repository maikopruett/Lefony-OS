# Migration validation — 2026-09-09

Validated locally on macOS/Apple silicon, Python 3.14, from the new Lefony OS
checkout (including its path containing spaces). No connected calculator was
flashed or changed during this migration.

| Check | Result |
| --- | --- |
| `make test` | 323 passed; 2 optional private DTB/DTS checks skipped |
| `make check-public` | Passed for the curated tracked/non-ignored source |
| `make firmware` | Physical target compiled |
| `make firmware-vm` | Emulator target compiled |
| `scripts/build_prime_g2_nand_capsule.sh` | Capsule built using the local ARM toolchain |
| `make emulator` | Pinned custom QEMU built and signed on macOS |
| `vm/test-native-direct.sh` | Direct native boot and framebuffer capture passed |
| Coordinate touch `--functions` | Controls, tabs, drag, anchored pinch, transitions and cancellation passed |
| Coordinate touch `--calculation-history` | Recall, edit, exact/approximate selection, scroll and cancellation passed |
| Graph frame inspection | On-screen OK button absent; plot and bottom banner visible |
| Installer `--help`, Python compilation and SPDX inventory generation | Passed |
| Local Markdown links, selected-source hashes and signing-key identity | Passed |

Physical ELF compilation reports the existing RWX load-segment linker warning.
The build is not physical acceptance. Linux CI configuration was prepared but
not run on GitHub here. Full Docker/U-Boot/media/fault suites and tests needing
private stock firmware were not run as part of this migration.

The import also updates stale source-contract assertions for the current GPT
prescaler, frame presenter, dynamic NAND marker layout and QEMU patch revision.
The default host suite no longer requires private device-tree files.

Build artifacts, runtime screenshots and detailed logs remain local under
ignored `build/` / `dist/`. Original file identities are recorded in
[migration-manifest.json](migration-manifest.json). The source revision in that
manifest belongs to the Mahalo archive; new build-history entries also record
the new repository's current revision and dirty working-tree status.
