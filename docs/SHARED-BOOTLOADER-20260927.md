# Shared bootloader for Simple Install and Dual Boot Install

Both website install choices use the new green startup screen, three-second
progress bar and calculator Enter shortcut. Simple Install boots Lefony only;
HP remains unavailable in its menu. Dual Boot Install enables both operating
systems and saved priority. Manual Off/On returns to the startup bar in either
configuration. The numeric countdown and bootloader logo remain absent.

## Configuration and compatibility

`scripts/build_prime_shared_boot.sh` produces two profiles from the same pinned
U-Boot source and verifies that their `u-boot-nodtb.bin` cores are identical.
The embedded `/config/lefony,boot-layout` device-tree property is 1 for existing
single-OS storage or 5 for signed dual storage. The IMX packages differ because
of that property. This does not change either NAND layout or the release key.

The dual profile defaults to layout 5 and fails closed on malformed metadata;
it never falls back to single-OS offsets. The simple profile rejects LFL5
capsules and does not write preferences for an unavailable second OS.

Native development request `0x4e`, value 0, now reports flag 32 when the consumed
LFUB/LFMW bootloader handoff advertises the menu/wake contract. The website's
protocol-2 `browserRecovery.bootMenu: 1` release contract forces full bootloader,
OS and DTB installation if that flag is missing, including when the OS is
already current. Subsequent native OS updates can retain the new bootloader.
A newer-than-published OS is not silently downgraded.

The website validates the explicit simple DTB profile and imported boot command
before staging the baseline. Only explicitly enabled development protocol-2
menu releases may use `emulator-cold-boot-qualified` baseline history. That
status never satisfies the physically verified release contract. Existing
signature, geometry, bad-block, boot-control and readback checks still apply.
Adding dual boot later remains subject to the existing supported-source and
retained stock-backup requirements; this change does not broaden migration
support to arbitrary single-OS installations.

## Validation and limits

- Both profiles compiled; executable cores compared byte-for-byte.
- Physical and VM firmware targets compiled with the existing release identity.
- Actual ARM NAND-ROM simple-profile test passed: automatic Lefony startup,
  countdown interruption by Enter, four arrow keys, disabled HP and Off/On back
  to countdown. Test: `vm/test-prime-shared-simple.py`.
- Actual ARM NAND-ROM dual regressions passed: both OSes, saved priority,
  one-time selection and rejection of missing layout/HP/Lefony data.
- Browser release/profile tests and 90 browser flow tests passed using mocked
  hardware. Artifact validation uses the actual published bundle bytes.

This is a development release. The new simple profile has not been installed
on a physical calculator in this change. The emulator does not qualify DDR
PHY timing, battery behavior or physical power loss. No attached calculator
was erased or flashed during this work.

## Candidate identity

| Artifact | SHA-256 |
| --- | --- |
| Shared executable core | `ba2c1fefc7e9f5c5a4d2c592f6f88eac3828d6df7817b58524d111d31cb89d75` |
| Simple NAND baseline | `90836b53fb0afcb43f1afa1bd56ec452f8b358d0cc510eba34183ddf7990f748` |
| Dual IMX | `5e1af1b6ebfab694ef0293895a3b6d4090c5cd8ed9c5c0a83ba5d0685890156f` |
| Simple native capsule | `9a7166911a31aa71da16a568def538fd6bb596c8a6554340e81dc60c419d78ef` |

Release packages: `build-20260927-shared-boot` (Simple Install) and
`dual-boot-20260927-shared` (dual profile, generation 3 OS/descriptor retained).
