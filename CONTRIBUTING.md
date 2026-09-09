# Contributing to Lefony OS

Contributions to the firmware, installer, emulator, tests and documentation are
welcome. A calculator is not required for host tests and many UI improvements.

## Set up

1. Fork or clone the repository and create a branch for one coherent change.
2. Use Python 3.11+, a C/C++ compiler, and Git. Run `python3 -m venv .venv`, activate
   it, then `python -m pip install -r requirements-dev.txt`.
3. Run `make test` and `make check-public`. Firmware and emulator dependencies
   are described in the README and `vm/README.md`.
4. Read `AGENTS.md`; it describes the source-of-truth layout and hardware rules
   for human and agent-assisted development.

The build downloads pinned public upstream source into `build/`. Never submit
edits that exist only in that generated checkout. Keep fixes in the native
port, patch files, or preparation scripts.

## A useful pull request

Explain the user-visible problem, the resulting behavior, and the checks you
ran. Include a small screenshot for UI changes. For hardware changes, identify
the target, build hash, emulator evidence, and physical tests separately. Keep
unrelated renames or speculative refactors out of a focused fix.

When reporting a bug, include the Lefony build ID, host OS, physical or emulator
target, reproduction steps, and relevant sanitized logs. Do not attach a full
NAND dump, HP firmware, release key or private USB/device capture.

A first contribution can improve a test, clarify an installation step, fix
keyboard/touch behavior, or replace a documented emulator assumption with a
measured hardware contract. Discuss large format, licensing, or architecture
changes before investing in an implementation.

## Licensing

Submit contributions under the applicable component's license described in
`LICENSE.md`. Retain upstream authorship and notices. Contributions must be
original or come with redistribution permission and the required attribution.
Do not copy code or assets from proprietary HP firmware.

The complete firmware inherits Upsilon's noncommercial license. The standalone
host tools are GPL-3.0-or-later, and QEMU/U-Boot integrations retain their GPL
terms. A pull request must not accidentally mix these licensing boundaries.

## Hardware operations

Tests and builds must not discover and write to a physical calculator by
surprise. Device writes are explicit installer operations, preceded by the
existing checks and backups. Emulator success alone is not permission to mark
a candidate physically verified.
