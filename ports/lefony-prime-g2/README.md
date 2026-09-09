# Lefony native Prime G2 port

This directory overlays the exact Upsilon revision in [UPSTREAM](UPSTREAM).
Build from the repository root with `make firmware` (physical) or
`make firmware-vm` (emulator). Both produce artifacts in `dist/` without
contacting a calculator.

- `ion/src/prime_g2/`: board startup, drivers, storage, input and native services.
- `ion/src/prime_g2_vm/`: emulator target entry points and configuration.
- `apps/`: Lefony app overlays and persistent preferences/datasets.
- `build/`: checked-in platform/toolchain definitions; this directory is source.
- `patches/`: durable upstream changes, applied by the firmware builder.
- `themes/`: Lefony appearance.
- `LEFONY_VERSION`: project version used during preparation.

The builder recreates `build/lefony-prime-g2/` from the upstream pin, applies
patches, copies these overlays and runs `scripts/prepare_prime_*.py`. Edit those
inputs, not the generated checkout. Physical and emulator builds share one
prepared checkout and must run sequentially.

Upstream Upsilon identifiers and notices are retained. Core changes follow
CC BY-NC-SA 4.0; see [the license map](../../LICENSE.md). The Linux simulator
port from the old Mahalo repository is not part of this native project.

Read [AGENTS.md](../../AGENTS.md), [status](../../docs/STATUS.md), and
[development](../../docs/LEFONY-NATIVE-DEVELOPMENT.md) before driver changes.
