# Third-party sources and notices

- **Upsilon / NumWorks Epsilon lineage:** calculator UI, applications, Poincare
  and Ion interfaces. Pinned Upsilon commit:
  `f36520e0ed5faabbfea8a2b9f4e1309edc077927` at
  <https://github.com/UpsilonNumworks/Upsilon>. Its root license is
  CC-BY-NC-SA-4.0. Component-specific notices in that tree also apply.
  Lefony modifies hardware drivers, input, display, app integration, theme,
  storage, recovery and build configuration. This repository's overlays and
  patches describe those modifications; the upstream source is fetched at build.
- **Historical HP Prime port:** Jean-Baptiste Boric's Epsilon work at
  <https://github.com/boricj/epsilon>, commit
  `d0e1e0e98b890daa8ac84a18d0e237ec5ff97868`, is a documented hardware/input
  reference. Do not infer a license for copied code from a project name;
  preserve any original notice when importing material.
- **QEMU:** <https://www.qemu.org/>, pinned by `vm/build-prime-g2-qemu.sh`.
  The Prime-specific model and applicable patches retain GPL-2.0-or-later
  notices. QEMU is a separate host program, not linked into the calculator OS.
- **U-Boot:** public upstream source and the public Prime port are pinned by
  `vm/build-u-boot.sh` and `scripts/build_prime_g2_physical_updater_uboot.sh`.
  U-Boot and its integrations retain GPL-2.0-or-later notices and applicable
  per-file licenses. It is a separate boot component.
- **Linux/Prinux hardware references:** public source URLs and revisions are
  recorded in `hardware/prime_g2/reference/sources.json`. Only curated register
  facts and protocol/geometry fixtures are included. Private device-tree
  binaries, captured firmware payloads and vendor manuals were excluded.
- **Toolchain and libraries:** compiler runtime libraries, Python components,
  app assets and other upstream dependencies keep their own notices. Before a
  binary release, collect the full notice set from the exact source/toolchain
  used; the top-level upstream license alone is insufficient.

The emulator signing key in `tests/fixtures/` is deliberately public test data.
It grants no trust in production and must never be used as a release key.

HP, HP Prime, NumWorks, Upsilon, and other third-party names/logos are their
owners' marks. Use here identifies compatibility and provenance, not endorsement.
