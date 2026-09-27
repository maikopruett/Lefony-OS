# Lefony Prime G2 emulator

This directory extends pinned QEMU with the Prime G2 LCD/panel, keyboard,
Goodix touch, PMIC, USB and NAND models. The ordinary system QEMU is not a
replacement for these models. Upstream QEMU and local integration retain their
GPL notices; see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Public-source development path

From the repository root, install the host requirements in `README.md` plus
QEMU build dependencies. On macOS, typical Homebrew dependencies are `ninja`,
`pkgconf`, `glib`, and `pixman`; on Ubuntu, install `build-essential`, `ninja-build`,
`pkg-config`, `libglib2.0-dev`, `libpixman-1-dev`, `libsdl2-dev`, `python3-venv`
and `git`. Firmware compilation also needs an ARM bare-metal GCC toolchain
with newlib, or Docker.

```sh
make emulator
make firmware-vm
./vm/run-native-vm.sh --direct
```

The shared desktop calculator is the default on macOS and Linux. Install
`requirements-dev.txt` in `.venv`; the Qt window embeds the renderer and never
opens a browser. Use `--headless` or `LEFONY_VM_DISPLAY=none` for unattended
runs. `PRIME_G2_QEMU` can select a previously built custom QEMU. Source and
build revisions are pinned in `build-prime-g2-qemu.sh`; checkout-specific short
paths allow QEMU to build even when the repository path contains spaces.

The SDK uses this same window, including on Windows. See
[desktop setup and native wrapper builds](../docs/EMULATOR-DESKTOP.md) and
[skin layouts and asset notices](../docs/EMULATOR-SKINS.md).

Direct boot loads the native ELF. It needs no HP firmware, private NAND or
U-Boot image, and provides no persistent SD storage. It does not qualify the
physical ROM/U-Boot boot path.

## Controls and UI tests

The runner prints socket and log paths under `build/prime-g2-native-vm/`.
In another terminal:

```sh
python3 vm/prime-control.py --help
python3 vm/prime-control.py press apps
python3 vm/prime-control.py press right
python3 vm/prime-control.py press ok
```

QTest/Goodix contact injection and the native event loop can test coordinate
touch independently of the host display's mouse support:

```sh
.venv/bin/python vm/test-prime-coordinate-touch.py \
  --elf dist/lefony-os-prime-g2-vm-native.elf --functions
.venv/bin/python vm/test-prime-coordinate-touch.py \
  --elf dist/lefony-os-prime-g2-vm-native.elf --calculation-history
.venv/bin/python vm/test-prime-coordinate-touch.py \
  --elf dist/lefony-os-prime-g2-vm-native.elf --derivative
```

The Functions check covers touch controls, graph drag, pinch and cancellation;
frames appear under `build/lefony-touch-qualification/`. Physical builds exclude
the test UART. Host trackpad gestures are not a substitute for injecting two
Goodix contacts when qualifying firmware pinch behavior.

## Extended boot and storage tests

The isolated [Phase 3 HP handoff probe](../docs/HP-LEFONY-PHASE3-HANDOFF.md)
uses exact private V15751 inputs and a separately built RAM loader. It validates
image rejection and observes execution. The separate `test-prime-hp-retention.py`
check passes original-image menu boot, GPIO input, NAND save and cold retained
history using a private physical-codeword fixture. This is logical framebuffer
evidence; the physical panel and calculator handoff remain unqualified. QEMU r83
includes corrected NAND clocks, short BCH transfers, GPIO keypad interrupts and
SNVS button status. See the Phase 3 record for commands and exact limitations.

`--u-boot`, `--capsule` and `--ab` build/use U-Boot and generated SD media.
These require Docker and `qemu-img`; read-only rescue also uses `qemu-io`.
`NATIVE_STORAGE_MODE` selects `persistent`, `ephemeral`, or `readonly`.
Images, overlays, logs and sockets are local ignored build artifacts.

`test-native-comprehensive.sh` orchestrates `build`, `smoke`, `application`,
`storage`, `fault`, and `long-run` groups and records bounded stage results.
The full suite needs the extended dependencies; it is not the default host
unit-test command. Read its stage list in `native-suite.py` before running it.

The smoke group includes a firmware-free USB control-endpoint regression. Run
it separately against a candidate emulator with:

```sh
.venv/bin/python vm/test-prime-g2-usb-stall.py \
  --qemu build/qemu-prime-g2/qemu-system-arm \
  --output build/usb-protocol-stall
```

Use a new output directory for each run. The check exercises IN/OUT stalls,
unchanged DMA descriptors and buffers while stalled, explicit clearing, and
recovery on a new SETUP transaction through QEMU's USB cable socket. It records
the emulator/test hashes and covers modeled behavior only.

Stock boot and retained-DMA research scripts additionally need private captures;
see [STATUS.md](../docs/STATUS.md). They are excluded from public CI. Never add
stock ROMs, NAND images, flash readbacks, or vendor PDFs to this repository.

## Where to edit

- `qemu/`: reviewable Prime board/peripheral/BCH implementations.
- `patches/`: ordered patches against the pinned QEMU and U-Boot revisions.
- `input-proxy.py`, `prime-control.py`: host input transport.
- `prime-*-check.py`, `test-*.py`, `test-*.sh`: qualification and regression tools.
- `u-boot/`: Lefony's boot selection command integration.

Model passes establish only modeled behavior. Hardware qualification notes must
state remaining electrical, timing and physical-device uncertainties.

## Boot-menu candidate

`test-prime-bootmenu.py` runs the physical U-Boot menu with synthetic NAND,
GPIO keypad input and Goodix touch. Build with
`../scripts/build_prime_g2_bootmenu.sh` from this directory. See
[Phase 1 qualification](../docs/BOOT-MENU-PHASE1.md) for inputs, hashes and limits.


The Phase 3 synthetic restore regression runs actual ARM research U-Boot without
private HP inputs:

```sh
.venv/bin/python vm/test-prime-hp-raw-restore.py
```

It covers raw program/erase/readback, rollback, exact metadata-marker handling,
physical-defect rejection, no startup flash-BBT writes, and full-device hashes.
QEMU r84 keeps software bad-marker policy separate from physical defect
injection. A passing model test does not qualify a physical NAND restoration.

## HP filesystem confinement research

[Phase 4 qualification](../docs/HP-LEFONY-PHASE4-CONFINEMENT.md) exercises an
exact-image RAM patch with disposable physical-codeword NAND fixtures. The
combined storage matrix requires private HP inputs; it covers checkpoint/full
scan, cold retention, capacity, reclamation, format and bad-block persistence.
The research profile rejects unsupported reset/update/reload operations. It is
not enabled in the installed Lefony boot menu or a physical migration flow.

QEMU r85 adds optional `prime-g2-gpmi-bch.trace-writes` observations before NAND
failure handling, including DMA paths. It does not block writes. Its overlay now
holds the full 262,144-page chip, avoiding false failures above 128 MiB. NAND
snapshot version 6 rejects old snapshots with shorter serialized arrays;
backing-image and overlay-journal formats are unchanged.

These public regressions require no private HP firmware (run from repo root):

```sh
.venv/bin/python vm/test-prime-nand-write-trace.py
.venv/bin/python vm/test-prime-nand-overlay-capacity.py
```

The fresh HP welcome-screen touch gesture and updater frontend remain
unqualified. The storage matrix calls real HP APIs from an application context;
it is not an HP UI acceptance test. Physical qualification remains separate.


## Shared-layout migration candidate

[Phase 5 qualification](../docs/HP-LEFONY-PHASE5-MIGRATION.md) documents layout 5,
signed NAND loaders, logical HP backup/recreation, a restartable offline
transaction, and exact stock rollback. `prime_dual_migration.py` and
`restore-prime-dual-fixture.py` only modify disposable regular files beneath
ignored `build/`; they have no USB/device backend. `--resume` requires the same
retained plan and immutable source artifacts.

`test-prime-dual-boot.py --rom` exercises actual NAND ROM startup, both OSes and
saved priorities; `--archive` additionally reads restored file hashes through
original HP ARM filesystem APIs. `test-prime-dual-layout-rejection.py` exercises
metadata rejection/fallback, and `test-prime-dual-native-update.py` verifies that
legacy native update entry points cannot program NAND. The migration fault
harness uses physical codewords and torn journal/page writes in a host model;
it is distinct from the ARM boot tests and physical power-loss qualification.

QEMU r86 additionally accepts the stock FCB's metadata-covered first codeword,
while retaining the legacy synthetic format. These fixture tools require private
HP inputs. Never publish their NAND files, archives, logs or calculator content.
The public physical migration flag remains disabled; the separately authorized
Phase 6 hardware trial is tracked in the installer qualification notes.

QEMU r87 also honors the FCB's `BBMarkerPhysicalOffsetInSpareData` field at
offset `0xb0`. HP's BCH-4 boot layout restores the displaced payload byte from
metadata byte 34; the legacy Lefony BCH-2 layout uses byte 0. Earlier ROM models
ignored that distinction and falsely passed incorrectly encoded dual bootstreams.
The fixture builder and route verifier now use the FCB-selected location too.
The NAND controller's ordinary guest-driven marker behavior is unchanged.

QEMU r88 adds nominal MMDC read-FIFO reset completion for initialized DDR.
`test-prime-g2-mmdc.py` checks completion, unrelated register preservation and
rejection of incomplete DDR startup. PHY timing and electrical sleep retention
remain outside the model. `test-prime-dual-wake.py` drives ordinary Shift/On
input through native suspend and HP power handling into the NAND boot menu;
`test-prime-hp-wake-instructions.py` separately covers exact HP patch sites and
bounded SNVS failure handling with explicitly modeled registers.

`test-prime-dual-refresh.py` qualifies an already retained private update review
through journal/page interruption boundaries and produces disposable transition
fixtures. `test-prime-dual-refresh-rom.py` boots their surviving old/new ROM
routes. Neither fixture builder nor test output is a physical flash interface.
