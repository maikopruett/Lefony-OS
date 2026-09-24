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

Cocoa is the macOS default display and SDL is the Linux default. Use
`--headless` or `LEFONY_VM_DISPLAY=none` for unattended runs. `PRIME_G2_QEMU`
can select a previously built custom QEMU. Source and build revisions are
pinned in `build-prime-g2-qemu.sh`; checkout-specific short paths allow QEMU to
build even when the repository path contains spaces.

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
```

The Functions check covers touch controls, graph drag, pinch and cancellation;
frames appear under `build/lefony-touch-qualification/`. Physical builds exclude
the test UART. Host trackpad gestures are not a substitute for injecting two
Goodix contacts when qualifying firmware pinch behavior.

## Extended boot and storage tests

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
