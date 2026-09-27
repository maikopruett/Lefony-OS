# Prime G2 boot menu (Phase 1 candidate)

This is a separate development U-Boot build based on the same pinned Prime
revision as the installed Lefony one-shot loader. It does not implement HP OS
handoff, instant switching, partition migration or an installer release.

The warm white/green startup screen shows the priority OS, a three-second
progress bar and an Enter prompt. There is no standalone wordmark or numeric
timer. Only the physical Enter key interrupts startup. The opened menu has no
timeout; Up/Left move backward and Down/Right move forward through the choices.
Navigation stops at the first and last choice; it never wraps around. Each
released and pressed arrow moves one choice without activating it.
Enter or Goodix touch selects an action. HP stays disabled.
Selecting an OS boots once; the separate priority screen saves the default.
Recovery asks for confirmation and preserves the existing three-minute SDP
window and rear RESET behavior. Ordinary OS suspend/wake does not run this menu.

## Build and test

From the repository root, after installing `requirements-dev.txt` in `.venv`:

```sh
./scripts/build_prime_g2_bootmenu.sh
.venv/bin/python -m pytest -q tests/test_prime_bootmenu.py
./vm/build-prime-g2-qemu.sh
.venv/bin/python vm/test-prime-bootmenu.py
```

The ARM integration test needs `dist/lefony-os-prime-g2.zImage`. An explicit
`--capsule` can select a newly built capsule. It builds disposable NAND overlays
from that Lefony capsule, the U-Boot DTB and synthetic preferences; no HP image
or private NAND dump is used. The test programs the emulated CPU counter to the
Prime's 8 MHz rate because upstream QEMU's default differs. Its keys traverse
the GPIO matrix, and touch traverses the Goodix registers and I2C driver.

The build outputs `build/lefony-uboot-bootmenu/`, including
`lefony-bootmenu-nand.imx` and `SHA256SUMS`. Building does not install anything.
The existing one-shot build is retained independently. The preparation script
checks its pinned context and can be applied repeatedly. Fonts come from the
bundled OFL input; generated atlases stay in the build directory.

## Candidate storage contract

Profile/schema version 1 uses two 128 KiB erase blocks at absolute NAND offsets
`0x00dc0000` and `0x00de0000`, inside the end of the existing `misc` partition.
This is an explicitly provisioned development profile, not permission to borrow
those blocks on any calculator. Audit both logical data and factory markers,
verify complete backups and the exact 512 MiB / 2048+64-byte / 128 KiB geometry
before provisioning in recovery. Do not repartition or touch HP filesystems.
Phase 5 must incorporate or explicitly migrate this contract.

The first page contains a 64-byte little-endian record: `LFBP`, schema 1,
layout/profile 1, nonzero generation, OS number (0 Lefony, 1 HP), forty zero
reserved bytes and IEEE CRC32 over bytes 0–59. All remaining bytes in the block
are erased. Two initial generation-1 Lefony records are provisioned explicitly.
Startup never formats or writes blank/unknown media. Missing, conflicting or
unavailable priorities open the menu; persistence remains unavailable until
recovery provisions a valid record. HP cannot be saved by the physical backend.

Saving replaces the other block and verifies the record; the old valid copy is
retained until the next save. The higher valid generation wins. Equal-generation
conflicts and generation overflow fail closed. A damaged record can fall back
to its valid peer; a target block with an unrecognized prefix or non-erased tail
requires recovery repair rather than being erased automatically. Bad blocks
are rejected, never skipped into neighboring storage.

## Handoff and recovery

The Lefony image stays at 4 MiB (8 MiB slot) and DTB at 12 MiB (1 MiB slot).
Bounded zImage, native-payload and DTB checks precede `bootz`. These are structural
checks; the existing installer's signature policy remains the trust boundary.
No new secure-boot claim is made. The display backend owns two cache-cleaned
buffers, waits for LCDIF to latch a frame and quiesces the panel/DMA before
handoff, including recovery Linux started from SDP.

Use the existing `scripts/prime_g2_uboot_recovery.py wrap` and `ram-test` path
for a non-installing physical trial. It requires the existing native CRC action
gates and preserves the known installed bootloader. A direct `lfboot` script
started inside the early RAM SDP window runs before normal capability-cookie
publication; use RAM staging or rear RESET to recover from that trial rather
than assuming the native one-shot capability flag will be set. A NAND installation must
use the documented recovery checks, kobs redundant streams/FCB/DBBT validation
and independent readback, never a raw write of this file to `/dev/mtd0`.

Qualification and remaining physical checks are recorded in
[`docs/BOOT-MENU-PHASE1.md`](../../../docs/BOOT-MENU-PHASE1.md).
