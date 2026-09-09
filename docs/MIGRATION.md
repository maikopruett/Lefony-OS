# Migration from Mahalo OS

The active native OS, host installer/update tools and Prime G2 emulator now live
in **Lefony OS**. This is a curated source import into a new Git repository,
not an import of the old repository's history or generated artifacts.

## Included

- Native firmware drivers, app overlays, theme, upstream pins and patches.
- Boot capsule/recovery sources, NAND layout and U-Boot integration.
- Current installer, signing, build history, diagnostics and build scripts.
- QEMU model sources/patches, native VM runners and integration tests.
- Host tests, public test keys, selected hardware facts and current documentation.

[The manifest](migration-manifest.json) records the source revision, original
paths and hashes, destination paths, and excluded files. Renamed references
were updated across build scripts, tests, documentation and CI. The original
source is removed only after the destination is checked and its original hash
still matches; the old repository's Git history remains available for recovery.

## Left in Mahalo OS

The historical Python/Linux GUI, old Linux installer and build paths, Linux VM
support, obsolete candidate packaging scripts, vendor PDFs, stock firmware/NAND
readbacks, full device captures, private DTB/DTS and old build caches are not
part of the new public source tree. The old repository remains an archive for
those materials. Its Git history must not be pushed as Lefony's history because
it contains excluded material.

The maintainer's existing release signing key is preserved privately under the
new checkout's ignored `build/lefony-update-signing/`. Backups, old build history
and recovery assets remain in the original checkout and may be selected by
explicit local paths. They are not silently regenerated or published.

See [local migration validation](MIGRATION-VALIDATION.md) for the completed
builds and tests, including remaining physical and CI limitations.

## Names

| Previous entry | Lefony entry |
| --- | --- |
| `ports/upsilon-hpprime/` | `ports/lefony-prime-g2/` |
| `scripts/build_upsilon_prime_g2_native.sh` | `scripts/build_lefony_prime_g2.sh` |
| `scripts/build_upsilon_prime_g2_vm_native.sh` | `scripts/build_lefony_prime_g2_vm.sh` |
| `scripts/upsilon_prime_installer.py` | `scripts/lefony_installer.py` |
| `native/prime_g2/upsilon_ab_boot.env` | `native/prime_g2/lefony_ab_boot.env` |
| `docs/UPSILON-*.md` | `docs/LEFONY-*.md` |

Generated checkouts, container tags and temporary VM names also use Lefony.
`UPSILON_*` identifiers that describe the upstream project remain upstream
names. `mahalo.preferences`, `mahalo.statistics`, `mahalo.regression`, the
`mahalo.prime-g2.registers.v1` schema, and U-Boot's `upsilon.env` / manifest
fields remain compatibility contracts. Renaming them would require an explicit
data/protocol migration and could strand existing records or boot media.

## Distribution

See [LICENSE.md](../LICENSE.md): the Upsilon core and adaptations retain
CC BY-NC-SA 4.0, original standalone Lefony host tools use GPL-3.0-or-later,
and QEMU/U-Boot integrations retain their upstream license notices. This makes
the complete firmware source-available with noncommercial terms.

`make check-public` checks the tracked/non-ignored source boundary, generated
artifacts, personal paths and private-key blocks. The two emulator PEM fixtures
are allowed only by exact content hash. This check is not a complete secret or
license audit; contributors still review what they add.
