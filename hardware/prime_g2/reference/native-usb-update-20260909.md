# First physical native USB installation

Build `260909-032005-5ac2e0`, installed on 2026-09-09 UTC.

- Image: `build/lefony-settings-candidate/lefony-settings.zImage`
- Size: 2,103,224 bytes
- SHA-256: `1ec38416ea0196247bd56849c243bdd8302ef03dee9abc0ccbc81cb28370c0e5`
- Previous firmware advertised development capabilities version 1, flags 3,
  capacity 8 MiB, with its native install engine idle.
- Installer `dev-update` transferred over native CAFE:5052 USB, programmed the
  OS slot, and reported complete byte-for-byte NAND readback verification.
- No recovery Linux, UUU, or U-Boot modification was involved.
- A normal reboot was requested after verification. The native USB endpoint
  was not available afterward; physical boot/display confirmation is pending.
  Successful readback must not be interpreted as successful automatic reboot.

This build removes the USB page's blue banner, uses theme green `#466645`,
preserves the black installer-ready text, and avoids unconditional 300 ms
full-page redraws. The emulator screenshot was checked and 83 relevant unit
tests passed. Physical flicker improvement still needs user confirmation.
