# Working on Lefony OS

## Orientation

Read `README.md` and `docs/STATUS.md` first. This is the native HP Prime G2
firmware, installer and emulator repository. It is not the historical Mahalo
Linux GUI. Paths and commands below are relative to this repository root.

- Firmware drivers: `ports/lefony-prime-g2/ion/src/prime_g2/`.
- Emulator-only target: `ports/lefony-prime-g2/ion/src/prime_g2_vm/` and
  `PRIME_G2_EMULATOR` guards. Never expose test UART controls on physical builds.
- App overlays: `ports/lefony-prime-g2/apps/`; shared upstream changes are in
  `patches/` or checked/idempotent `scripts/prepare_prime_*.py` transformations.
- Firmware build: `scripts/build_lefony_prime_g2.sh`; upstream pins: `ports/lefony-prime-g2/UPSTREAM`.
- Installer: `scripts/lefony_installer.py`; USB/update and history modules are
  siblings in `scripts/`.
- QEMU model: `vm/qemu/prime_g2_peripherals.c`, related sources and `vm/patches/`.
- Tests: `tests/` for host tests; `vm/test-*.sh` and `vm/test-*.py` for integration.

## Make durable, scoped changes

Inspect `git status` before editing and preserve existing work. Follow the
user's requested scope. If working with other agents, agree on file ownership
and do not revert their changes. Use `rg` for targeted searches.

Do not make a feature live only in `build/lefony-prime-g2/`: the build resets
that generated checkout. Change the checked-in port, patch, or preparation
script, then rebuild. Preparation scripts should reject unexpected upstream
context and work on repeated runs. Do not manually edit generated i18n, theme,
object, firmware or capsule files as a substitute for their source.

Keep upstream identifiers where they describe Upsilon itself. Public Lefony
entry points and filenames use Lefony naming. Persistent `mahalo.*` record
names and existing boot-manifest fields are compatibility contracts: changing
them needs an explicit versioned migration, not a search-and-replace.

Do not silently change pinned upstream revisions, storage layouts, protocol
IDs, signature policies, boot defaults, or release trust roots while fixing an
unrelated issue. Document intentional changes and update their actual callers.

## Validation

Use the project's virtual environment (`.venv/bin/python`) after installing
`requirements-dev.txt`.

```sh
make test                       # Host suite, no connected hardware
make check-public               # Repository boundary, keys and artifact check
make firmware                   # Physical target compilation
make firmware-vm                # Emulator target compilation
make emulator                   # Build custom QEMU
./vm/test-native-comprehensive.sh smoke
```

Scale checks to the change. A documentation-only edit needs link/command and
public-tree checks. Driver or shared UI changes normally need both target
builds and the relevant emulator check. Installer changes need host tests for
preflight, backups, cancellation, readback, and action boundaries. Do not invent
successful checks when a compiler, Docker, fixture, or device is unavailable.
Report exact failing checks and distinguish existing failures from regressions.

For touch work, use `vm/test-prime-coordinate-touch.py --functions` or
`--calculation-history` with the VM ELF (no private firmware needed). The input
must traverse Goodix and normal event dispatch; direct controller calls do not
qualify the physical input path. Inspect captured frames when changing layout.

A passing emulator validates the model and guest behavior. It does not prove
physical electrical behavior, flash endurance, power-loss recovery, battery
calibration, or touch feel. Record the candidate hash, board/build target,
commands, evidence and remaining physical validation in qualification notes.

## Hardware and recovery

Ordinary coding, builds and host tests do not require a calculator. Do not
flash, erase, provision, repartition, or restore a connected device unless the
user has authorized that operation. Existing explicit authorization remains
valid; do not repeatedly ask for it. Code changes must not bypass the
installer's backups, geometry checks, model checks, signature verification,
readback verification, or documented unprovisioned-layout rejection.

Physical release signing keys are local secrets under ignored `build/` (or an
explicit external path). The public test private key is only for emulator
fixtures and must never become a production trust root. A migration to a new
checkout must preserve a maintainer's existing keys privately; do not generate
new release identity accidentally.

Keep register waits, USB transfers and polling bounded. Preserve driver
ownership of clocks, DMA/cache maintenance, framebuffer presentation, touch
capture cancellation and key debouncing. Check hardware reference facts before
changing addresses, bitfields or timings; identify modeled assumptions clearly.

## Public repository and contributions

Never stage or publish firmware/NAND/ROM dumps, readbacks, vendor PDFs,
calculator-specific captures, recovery archives, generated build trees, local
paths with usernames, or release keys. `make check-public` allows only the
explicitly documented emulator key fixture. Optional private-fixture tests
must state their inputs and remain outside default CI.

Preserve file-level license notices. The core is CC-BY-NC-SA-4.0; original
standalone host tools are GPL-3.0-or-later; QEMU/U-Boot changes retain upstream
GPL notices. See `LICENSE.md`, particularly the exception for code fragments
embedded in preparation scripts. Do not relabel the entire OS as permissively
licensed or fully open source.

Update documentation when commands, supported behavior or qualification status
change. Keep the README useful to a new contributor; detailed hardware history
belongs in reference notes. Do not commit, push, publish releases, or open
external communications unless requested. End with what changed, validation,
and material limitations, using links to relevant files.
