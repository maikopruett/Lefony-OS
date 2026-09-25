# Desktop emulator screenshots

Captured from the actual shared Qt desktop window on macOS on 2026-09-25:

- `emulator-home.png`: Lefony OS home screen in the Prime G2 QEMU model.
- `emulator-calculation.png`: `7 + 8 = 15`, entered with the clickable keypad.
- `emulator-sdk.png`: the Counter SDK example after an Add one touchscreen click.

The underlying VM ELF SHA-256 was
`8926e6bcad665887b0b99f959f94e4c5c85a8b13a83457008fff12048bf2144d`.
These are emulator screenshots with synthetic app data, not physical-device
captures or proof of physical input qualification. The images are unedited
window captures. HP Prime skin artwork retains its
[third-party asset terms](../../sdk/assets/prime/README.md).

## Device-only desktop window

`emulator-device-home.png` and `emulator-device-calculation.png` show the full
HP Prime artwork in the updated shared Qt window, without the former page
header, toolbar or footer. Captured on macOS on 2026-09-25 from actual QEMU
firmware; `7 + 8 = 15` was entered with the clickable device keys. Layout and
scale were checked through the native View menu. These are unedited window
captures; the macOS title bar and capture indicator are system UI.

`emulator-device-sdk.png` shows the same window running the SDK Counter example,
after a normal touchscreen click incremented it to 1.
