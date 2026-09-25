# Emulator skins

The SDK browser and native QEMU launcher display the bundled HP Prime Medium
skin by default. Both run the actual VM ELF, with matrix input through
QTest/KPP and touch through Goodix. Physical firmware is unchanged. Native
macOS windows use WKWebView to render the same interface.

Five original skins and fifteen normal/hover/pressed PNGs are stored in
[`sdk/assets/prime/`](../sdk/assets/prime/README.md). These are proprietary
Moravia/HP assets, not covered by Lefony’s licenses. The retained EULA prohibits
distribution; no separate redistribution grant was identified. See the asset
notice and provenance manifest for the exact source and hashes.

From the repository root, with `requirements-dev.txt` installed in `.venv`:

```sh
# Default: macOS desktop window or Linux browser, with keyboard.
make run

# Native QEMU, with the same interface in the browser.
./vm/run-native-vm.sh --direct --browser

# SDK app preview; uses the same assets and browser controls.
.venv/bin/python sdk/tools/cli.py --project /path/to/app run
```

No asset download, environment variable or opt-in is required. The loader uses
the bundled assets in source checkouts and frozen SDK installations. Missing or
invalid assets produce an error instead of silently dropping the keyboard.
`LEFONY_EMULATOR_ASSETS` can override the asset directory for custom skins; it
must contain `skins/` definitions and their referenced `images/` PNGs.

`--headless` retains unattended operation. The desktop wrapper currently
supports macOS; use the browser panel on other supported hosts. The Swift window
is compiled into ignored `build/emulator-window/` on first use. Explicit
`LEFONY_VM_DISPLAY=cocoa` or `sdl` remains a diagnostic raw-display override.

The layout selector exposes every supplied skin. Whole-calculator scaling
keeps the key regions, framebuffer and touch coordinates aligned. At 1×, the
Medium skin has a 320 × 240 CSS-pixel display; the Large landscape skin uses
640 × 480. These are screen coordinates, not calibrated physical inches.

All 51 keys are displayed with hover/pressed artwork. The separate On/Off key
uses the VM control channel rather than a fictitious matrix coordinate. Waking
the emulator uses its existing `POWER RESUME` command: this does not qualify
physical SNVS wake behavior. If the calculator sleeps, click **On** to wake it.
Switching skins or scale, losing focus and closing the page release held inputs.

Interactive browser/desktop sessions model external power to keep the preview
awake. Press **Esc** if the guest initially shows its USB-connected status
screen. Headless and plain Cocoa/SDL runs retain their battery defaults. The
current VM can leave its display blank after battery-mode suspend/resume; this
host preview does not fix or qualify that firmware/model behavior.

Stop the ordinary QEMU preview with **Stop emulator**, closing the desktop
window, or Ctrl-C. Closing a browser tab releases input; use Stop or Ctrl-C to
end that QEMU session. Direct boot has no persistent SD storage. The SDK keeps
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
input qualification. Capture actual browser/window output
when checking visual alignment, and use the existing normal-input touch suite
for guest regression checks.
