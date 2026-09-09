<p align="center"><img src="assets/lefony-logo.png" alt="Lefony" width="180"></p>

# Lefony OS

**A community-developed calculator OS for the HP Prime G2.**

Lefony brings Upsilon's calculator applications and Poincare math engine to the
Prime G2's native hardware, with a green-and-white interface, the Prime keyboard
layout, touch controls, and a host installer and emulator for development.

This repository contains the **native firmware port, installer/update tools,
Prime G2 QEMU models, tests, and development documentation**. The earlier Mahalo
Linux desktop and its obsolete deployment scripts are outside this project.

> **Development status:** native firmware boots on physical Prime G2 hardware.
> Changes are checked in an emulator, and physical acceptance is recorded
> separately. This is community firmware, not an HP-supported update. Prime G1
> is not a supported target.

## What works

- Calculator history with touch scrolling and expression/answer recall.
- Functions with touchable controls, one-finger graph panning and two-finger
  pinch zoom. Tap the bottom banner for plot options.
- Prime keypad layout, Shift/Alpha shortcuts and math templates.
- Native LCD rendering, brightness, refresh-rate trials with rollback, and
  battery/clock integration.
- Calculator, Functions, RPN, Python, statistics, probability, equation solver,
  periodic table, sequences, regression, and settings applications from Upsilon.
- A USB installer with build history, backups, verification, recovery handling,
  and signed-update support.
- A custom QEMU model for the Prime's display, input, PMIC, USB and NAND, plus
  automated application and hardware-model checks.

See [current status](docs/STATUS.md) for limitations and the distinction between
hardware-tested behavior and modeled behavior.

## Start contributing

You can work on the host tools and unit tests without owning a calculator,
without vendor firmware, and without connecting a USB device.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
make test
make check-public
```

Use **Python 3.11 or newer**, Git, and a C/C++ compiler. Development is focused on
macOS and Linux. The installer uses a terminal UI; native Windows support is
not currently established.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and
[AGENTS.md](AGENTS.md) for guidance for coding agents. Useful starting areas
include touch interactions, installer usability, model accuracy, tests, and
clearer hardware documentation.

## Build the firmware

Successful main-branch builds are packaged automatically in
[GitHub Releases](https://github.com/maikopruett/Lefony-OS/releases), with signed
updates, emulator firmware, corresponding source and checksums. These are
development builds; see [release packaging](docs/RELEASES.md) for qualification
limits and the website's automatic latest-package discovery.

Install `arm-none-eabi-gcc`/`g++`, or use a running Docker engine for the
container build path. The scripts fetch the exact upstream revision recorded
in [UPSTREAM](ports/lefony-prime-g2/UPSTREAM).

```sh
make firmware       # Physical Prime G2 target; compile only
make firmware-vm    # Emulator target with test interfaces
```

Outputs are in `dist/`. The physical image is
`lefony-os-prime-g2-native.bin`; the emulator ELF is
`lefony-os-prime-g2-vm-native.elf`. The prepared Upsilon checkout under
`build/lefony-prime-g2/` is disposable: builds recreate it. Make durable changes
in the port, patches, or preparation scripts.

**Building does not install or flash anything.** For bootable recovery capsules
and signed updates, see [the installer guide](docs/LEFONY-INSTALLER.md).

## Run the emulator

The native UI needs this repository's Prime-specific QEMU models. An unmodified
system QEMU cannot substitute for them.

```sh
make emulator       # Build pinned QEMU with the Prime G2 models
make firmware-vm
make run            # Native ELF fast path; no HP firmware required
```

QEMU build dependencies include Ninja, pkg-config, a C/C++ compiler, Python,
GLib and pixman development packages. Linux desktop display also needs SDL2;
macOS uses Cocoa. See [vm/README.md](vm/README.md) for headless operation,
keyboard/touch controls, test suites, and U-Boot boot-media modes.

The emulator's private-stock-fixture research tests are optional and clearly
separated from the firmware/unit-test workflow. HP ROMs, firmware archives,
NAND dumps, and vendor PDFs are not distributed here.

## Installer

```sh
python3 scripts/lefony_installer.py --help
python3 scripts/lefony_installer.py --once --json  # Detect/report only
python3 scripts/lefony_installer.py              # Interactive installer
```

Hardware operations additionally need `libusb`, NXP's `uuu` tool, and the
recovery assets described in the [installer guide](docs/LEFONY-INSTALLER.md).
Prepare backups and a verified recovery path before installing development
firmware. A/B updates require a provisioned, qualified layout; normal updates
do not repartition an unprovisioned calculator.

## Repository map

| Directory | Contents |
| --- | --- |
| `ports/lefony-prime-g2/` | Native Ion drivers, app overlays, theme, upstream patches and build definitions |
| `native/prime_g2/` | Boot capsule, recovery stub, NAND layout and physical U-Boot integration |
| `scripts/` | Firmware builds, preparation, installer, signing, history and diagnostics |
| `vm/` | QEMU board models, emulator runners, boot media and integration tests |
| `tests/` | Host tests and explicitly public emulator signing fixtures |
| `hardware/prime_g2/` | Register contracts, measured facts, and hardware qualification notes |
| `docs/` | Architecture, contributor guides, installer and technical references |

Generated files and local signing keys live in ignored directories. See
[the migration notes](docs/MIGRATION.md) for the move from Mahalo OS and names
retained for storage/protocol compatibility.

## Licensing and credits

The complete OS is **source-available with a noncommercial restriction** because
its pinned Upsilon core is under **CC BY-NC-SA 4.0**. Contributions to the core
retain that license. It would be inaccurate to call the complete firmware
OSI-approved open source.

Lefony's original standalone installer and host tools are **GPL-3.0-or-later**.
QEMU and U-Boot integrations retain their **GPL-2.0-or-later** notices. Embedded
upstream code and third-party components retain their own terms; see
[LICENSE.md](LICENSE.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Lefony builds on [Upsilon](https://github.com/UpsilonNumworks/Upsilon), the
NumWorks/Epsilon lineage, [QEMU](https://www.qemu.org/), U-Boot, and the public
HP Prime hardware work cited in the repository. HP, NumWorks, Upsilon and other
third-party names and marks belong to their respective owners. This project
is not affiliated with or endorsed by HP or NumWorks.
