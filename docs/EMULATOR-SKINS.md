# Emulator skins

The SDK and native QEMU launcher display the bundled HP Prime Medium
skin by default. Both run the actual VM ELF, with matrix input through
QTest/KPP and touch through Goodix. Physical firmware is unchanged. The shared
desktop window embeds the renderer on macOS, Linux and Windows. See
[desktop setup](EMULATOR-DESKTOP.md) for native runtime dependencies.

Five original skins and fifteen normal/hover/pressed PNGs are stored in
[`sdk/assets/prime/`](../sdk/assets/prime/README.md). These are proprietary
Moravia/HP assets, not covered by Lefony’s licenses. The retained EULA prohibits
distribution; no separate redistribution grant was identified. See the asset
notice and provenance manifest for the exact source and hashes.

From the repository root, with `requirements-dev.txt` installed in `.venv`:

```sh
# Default desktop calculator, with keyboard.
make run

# SDK app preview; uses the same desktop window and controls.
.venv/bin/python sdk/tools/cli.py --project /path/to/app run
```

No asset download, environment variable or opt-in is required. The loader uses
the bundled assets in source checkouts and frozen SDK installations. Missing or
invalid assets produce an error instead of silently dropping the keyboard.
`LEFONY_EMULATOR_ASSETS` can override the asset directory for custom skins; it
must contain `skins/` definitions and their referenced `images/` PNGs.

`--headless` retains unattended operation. Browser mode and automatic browser
launching have been removed. The embedded desktop renderer uses the same
layout and inputs on all platforms. Explicit `LEFONY_VM_DISPLAY=cocoa` or `sdl`
remains a diagnostic raw-display override.

The native **View → Layout** menu exposes every supplied skin. Whole-calculator scaling
keeps the key regions, framebuffer and touch coordinates aligned. At 1×, the
Medium skin has a 320 × 240 CSS-pixel display; the Large landscape skin uses
640 × 480. These are screen coordinates, not calibrated physical inches.

All 51 keys are displayed with hover/pressed artwork. The separate On/Off key
uses the VM control channel rather than a fictitious matrix coordinate. Waking
the emulator uses its existing `POWER RESUME` command: this does not qualify
physical SNVS wake behavior. If the calculator sleeps, click **On** to wake it.
Switching skins or scale, losing focus and closing the window release held inputs.

Interactive desktop sessions model external power to keep the preview
awake. Launchers dismiss the guest USB-connected status sheet before showing the
interactive calculator. Headless and plain Cocoa/SDL runs retain their battery defaults. The
current VM can leave its display blank after battery-mode suspend/resume; this
host preview does not fix or qualify that firmware/model behavior.

Stop the QEMU preview with **File → Stop Emulator**, closing the desktop
window, or Ctrl-C. Direct boot has no persistent SD storage. The SDK keeps
its existing workspace/save lifecycle.

## Validation

Tests check bundled asset integrity and use synthetic fixtures for malformed
input. No network download is required:

```sh
.venv/bin/python -m pytest tests/test_emulator_skin.py \
  tests/test_sdk_emulator_ui.py tests/test_sdk_replay_lifecycle.py
make check-public
```

The host interface does not change firmware behavior or establish physical
input qualification. Capture actual window output
when checking visual alignment, and use the existing normal-input touch suite
for guest regression checks.
