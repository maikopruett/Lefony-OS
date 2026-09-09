# Native Lefony on HP Prime G2

This target runs Upsilon directly on the Prime G2's i.MX6ULL Cortex-A7. Linux,
glibc, framebuffer devices, evdev, and the Mahalo launcher are not involved.
U-Boot remains the recovery-safe first-stage bootloader and initializes DDR.

The prioritized implementation and release checklist is maintained in
[`LEFONY-NATIVE-PORT-CHECKLIST.md`](LEFONY-NATIVE-PORT-CHECKLIST.md).

## Current implementation

For supported behavior and remaining physical qualification, use
[STATUS.md](STATUS.md). The port includes native startup, display presentation,
keyboard/touch, timing, power and USB integration. Physical application storage
is still RAM-only; the VM has atomic persistent storage. Native installation
and update tooling is described in [the installer guide](LEFONY-INSTALLER.md).

```sh
make firmware
make firmware-vm
```

The build emits `dist/lefony-os-prime-g2-native.elf` for U-Boot `bootelf`,
`dist/lefony-os-prime-g2-native-debug.elf` with debug information, and
`dist/lefony-os-prime-g2-native.bin`. Emulator output names include `-vm-native`.
Run the builds sequentially; they share a prepared checkout.

The remaining handoff notes describe early bring-up, not an instruction to
flash a connected calculator. Use the qualified installer workflow for an
explicitly authorized installation.

## Safe U-Boot handoff

Load the ELF file into unused DDR, not its linked execution address. The ELF is
linked at `0x82000000`; its framebuffer is at `0x8f000000`. A suitable staging
address is `0x88000000` as long as the image remains below the framebuffer.

At a U-Boot prompt, after transferring the file to the staging address:

```text
bootelf -p 0x88000000
```

Do not use `nand write`, change `bootcmd`, or overwrite the existing kernel
while this target is in bring-up. Power-cycling returns to the existing system.

## Handoff assumptions

- U-Boot has initialized the 256 MiB DDR and UART1.
- U-Boot's ELF loader flushes the loaded image before jumping.
- The payload normalizes itself to MMU-off, cache-off operation.
- The Prime remains at its U-Boot-established CPU and bus clock rates.
- The PF1550 boot regulators remain enabled.

The LCD pixel clock uses the already-running 528 MHz PLL2 bus clock divided to
17.6 MHz, close to the device-tree's 18 MHz target without retuning a shared
PLL. LCDIF uses the Prime kernel's 32-bpp-to-8-bit serial RGB mode, so each
320-pixel active line is transmitted as 960 byte clocks.
