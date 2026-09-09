# Development status

Lefony targets the **HP Prime G2** (i.MX6ULL). It is a native, bare-metal Upsilon
port, not a Linux desktop. Prime G1 and stock NumWorks hardware are not targets
of these build scripts.

## Firmware and applications

Physical native boot, display and keyboard have bring-up evidence in the
hardware notes. Calculator touch history and Functions touch use the normal
Goodix report/event path. Functions supports tapping tabs and controls,
one-finger graph panning, and two-finger pinch zoom. The graph's on-screen OK
button is removed; its bottom banner and physical OK key still open options.
Gestures cancel across modal/tab transitions and recover after contact loss.

The emulator target includes UART/QTest controls that are compiled out of the
physical target. Automated UI checks establish behavior in the model; graph
feel, contact tracking and responsiveness on the physical touchscreen still
need hands-on acceptance for each release candidate.

Drivers include display presentation, brightness, keypad, touch, timers, PMIC,
USB and storage integration. Some hardware models remain provisional. Detailed
notes under `hardware/prime_g2/` record observations and failures at particular
revisions; historical success does not qualify every later build. Do not infer
physical power-loss safety or battery calibration from an emulator pass.

Physical application persistence remains RAM-only; VM persistence uses atomic
SD-backed slots. Saving an expression in the UI is not yet a promise that it
will survive a physical power cycle.

## Installer and recovery

The installer supports detection, build selection/history, backup and readback,
RAM/recovery workflows and signed updates. A/B installation requires a
provisioned and qualified layout. A normal update rejects an unprovisioned
layout instead of creating one. Recovery assets and private backups are
maintainer/device-specific and are not shipped in this repository.

Building the physical target creates a local signing identity if none was
supplied. Keep it under ignored `build/lefony-update-signing/`, or set
`LEFONY_UPDATE_KEY_DIR` / `LEFONY_UPDATE_PUBLIC_KEY`. Existing installed devices
must retain their matching trust root. Emulator fixture keys are deliberately
public and must never sign a physical release.

## Public and private tests

`make test` runs host tests without a calculator, firmware dump or network
access. `make firmware`, `make firmware-vm`, and the direct emulator/touch
workflow use only publicly fetched upstream sources and this repository.

Two optional device-tree tests require privately supplied files:

```sh
LEFONY_PRIVATE_HARDWARE_DIR=/path/to/private/reference make test
```

The directory must contain `imx6ull-14x14-prime.dtb` and its matching `.dts`.
Without the environment variable, these tests report explicit skips. Do not
copy the files into the public repository.

Stock boot, retained-DMA replay and exact NAND research under `vm/` require
private local captures and sometimes a qualified U-Boot/capsule. Consult each
script's inputs, including `PRIME_G2_EXACT_NAND` and
`PRIME_G2_CURRENT_CAPSULE`. Retained-DMA replay also requires
`LEFONY_PRIVATE_ROM_DMA_CAPTURE` pointing to an original private JSON capture. They are not part of default public CI.
The public `rom-dma-buffers-20260907.json` is an analyzer fixture whose payload
words are synthetic zeroes; it is not evidence of captured firmware content.

Full boot-media/storage/fault suites additionally use Docker, U-Boot and
`qemu-img`/`qemu-io`. See [the emulator guide](../vm/README.md).
