# Lefony OS update architecture

## Revised direction: native update mode (2026-09-09)

### Native writer and USB page candidate: 260909-030847-5f6700

The dedicated USB modal opens on USB data connection or PMIC-reported external
power. It keeps the display lit and inhibits both platform and application
auto-suspend/dimming while externally powered. It displays receiving,
checking, erasing, writing, verifying, verified, and failed states with
progress. Battery-only behavior resumes on disconnect; USB insertion wake
from deep suspend still needs physical qualification.

Native capability flag 2 selects the new installer path. After a frozen
image is uploaded and CRC verified, explicit OUT 0x53 (matching CRC) arms
installation only after successful control status completion. The RAM-running
engine checks the two raw bad-block markers of every target block and refuses
bad blocks rather than guessing a remap. It erases only needed blocks within
32..95, BCH-encodes pages within 2048..6143, checks NAND command status, then
ECC-decodes and compares every written image byte. Firmware rejects competing
vendor operations during installation, except GET 0x53 status. OUT 0x54 requests
normal reboot only after complete readback verification. New uploads alone
never invoke erase/program. Neither U-Boot nor the NAND partition layout changes.

The installer uses native USB without Linux/UUU/admin elevation for this path.
It refuses older firmware with an instruction to bootstrap once through
recovery, instead of automatically trying the known-failing recovery handoff.
Normal reboot is requested after verification; the installer does not claim
that USB disappearance alone proves the new OS booted.

82 host tests pass. Emulator `/tmp/lfusb-hukp3anq` completed the full native
install and produced the verified page screenshot. Journal comparison found
exactly 17 erases and 1,027 page programs, all inside mtd1. A fresh cold boot
using that updated journal reached Lefony runtime with the unchanged U-Boot.
A second end-to-end run (`/tmp/lefony-full-update-final-test.log`) also passed
the verified-install-only reboot command; QEMU's `-no-reboot` mode exited on
the guest reset request. These are emulator results, **not physical erase,
program, power-loss, or reboot qualification**. The physical calculator was
not changed by these tests. Single-slot updates remain vulnerable to power
loss; failed writes can require ROM recovery, and there is no A/B rollback.

**Physical whole-image readback passed on user-installed `bd09df`.**
`prime_g2_usb_diag.py --verify-nand` compared all 2,103,184 bytes across 1,027
ECC-decoded pages against the exact archived capsule. SHA-256 matched
`b293dcc6930e6d8cd31019bc2ebedc6a2e892f9a7e67a6d22ea3ee76a613a860`.
The device reported zero corrected bits, no read failures or unexpected
bad-block markers, and USB remained responsive after completion. No NAND
write, erase or reboot was performed. This qualifies clean-page BCH readback
for this installed image/layout; injected-error correction, bad-block
remapping, erase/program and power-loss behavior are not qualified by it.

Physical READID qualification on user-installed build `3db9f6` passed:
USB 0x50 returned error 0, phase 3, NAND ID `addc909554addc90`, APBH error 0
and semaphore 0. Inherited BCH layout words are `50989184` / `138414208`,
GPMI timing0 `66051`, control1 `12845580`. Repeated probes returned the same
ID and subsequent USB recovery-info requests succeeded. No NAND write was
performed. This qualifies command/address DMA and raw ID reads only—not
geometry, ECC-decoded page reads, erase/program, bad-block handling or reboot.

During full-image ECC readback testing, two early candidates timed out in
USB. A QMP register capture located the CPU in `Ion::Power::suspend`, not
in the NAND driver: the separate application suspend timer recognized only
signed update state. The fix extends its existing busy hook with recent
configured USB management activity (a two-second renewable lease). This
covers read-only verification and expires after traffic stops; it does not
permanently keep an abandoned session awake. Those intermediate candidates
were not added to installer history or installed on the calculator.

Candidate `260909-025429-bd09df`, SHA-256
`b293dcc6930e6d8cd31019bc2ebedc6a2e892f9a7e67a6d22ea3ee76a613a860`,
passes 79 host tests. Emulator `/tmp/lfusb-4_nwkuz4` compared all 2,103,184
capsule bytes through the native APBH/BCH page reader and USB interface,
then passed enumeration/address, staging/CRC, abort and reconnect checks.
Physical page readback is pending installation of this candidate. A match
in the emulator is not evidence that real NAND ECC handling is qualified.

The user requested an OS-resident updater: receive the image over native USB,
enter an exclusive update screen, program and verify NAND from RAM, then
perform a normal reboot. ROM recovery is an emergency/bootstrap path, not a
required step for each update. The older recovery-based decision below is
historical and is not the target implementation.

Physical full-image USB reception is qualified. Software entry into ROM
recovery failed on build 762b29 (dim blank LCD, no USB endpoint; rear RESET
boots existing Lefony). Native programming is not yet qualified. The existing
`nand_update.cpp` direct writer uses emulator-only GPMI registers; it must not
be enabled on physical hardware by removing its compile-time guard.

`nand_physical.cpp` begins the real APBH/GPMI driver. Its NAND commands are
READID (0x90) and READ0/READSTART (0x00/0x30), on CS0/channel0 using
cache-maintained, aligned DMA storage.
It reports inherited GPMI timing, BCH layout and DMA status through USB 0x50.
USB 0x51 requests one ECC-decoded page and returns a frozen status; 0x52
returns its data only after successful decoding. Page reads are restricted
to physical pages 2048..6143 (the existing OS slot). The accepted BCH layout
is exactly the captured `030a0880/08400880`: four 512-byte GF13 chunks with
strength 2 and ten metadata bytes. Status bytes greater than two (including
erased/uncorrectable sentinels) fail closed; no erased-page recovery heuristic
is used in this qualification path. Block-marker swapping is reversed at
payload byte 2028, bit 2. No BCH layout is changed.

`prime_g2_usb_diag.py --verify-nand /absolute/path/to/exact-installed.zImage`
compares every decoded byte and reports SHA-256 and corrected-bit totals.
It stops on ECC errors, unexpected bad-block markers on either initial page
of a block, short/stale replies or a byte mismatch. It does not remap bad
blocks automatically and must be given the actual installed build, not merely
an arbitrary latest build. No write/erase/reboot is performed.
It refuses reset/gated or busy controllers, uses bounded waits, and exposes
no erase/program API. This probe has not yet been physically qualified.

Remaining gates: physical identification and geometry; BCH-decoded reads
matching existing Linux readbacks including bad-block marker swapping; bounded
erase/program and readback tests on an explicitly approved expendable target;
exclusive update-mode UI and watchdog servicing; whole-image verification;
normal reboot validation. Until those pass, preserve the known-good U-Boot and
do not write the active OS from the experimental native driver. Single-slot
development updates are not power-loss atomic. A/B rollback needs a separately
approved and qualified layout/bootloader migration.

## Decision

Lefony uses a calculator-style host installer and recovery mode around an
Android-style A/B boot policy. The normal OS is never the component that
programs physical NAND.

The split is deliberate:

1. The running calculator enumerates as native Lefony USB.
2. It accepts a fixed-size manifest, verifies the RSA-2048 signature, receives
   the payload, and verifies its SHA-256 digest in RAM.
3. Only after authentication does it request the i.MX6ULL ROM USB recovery
   mode.
4. The desktop installer boots the known recovery Linux image in RAM. It reads
   both redundant boot-control records before any write and refuses an
   unprovisioned or changed layout.
5. Recovery backs up the inactive slot and misc partition, writes only the
   inactive slot, compares a NAND readback, and commits the stale metadata copy
   before mirroring the new generation to the other copy.
6. U-Boot verifies the selected slot's SHA-256 and zImage header. It records a
   candidate attempt before booting it.
7. Lefony marks a healthy candidate boot in SNVS. U-Boot consumes that token on
   the next reset and makes the candidate active. A candidate that exceeds the
   boot limit is rolled back automatically.

This gives a power-loss-safe commit point: until a valid newer metadata record
exists, U-Boot cannot select the newly written image. At least one redundant
record remains valid while the other is erased and programmed.

## Vendor patterns used

- TI-Nspire updates are initiated by a desktop/web host over USB and transfer
  an OS image to the calculator. This is the right user-facing model for a
  calculator with no always-on update service.
- Casio graphing calculators expose a dedicated OS Update USB mode. This
  supports a separate recovery/update personality rather than teaching the
  normal application runtime to be a NAND flasher.
- HP Prime's Connectivity Kit can place a calculator in recovery mode and
  perform firmware update/reset operations. Lefony keeps the same recovery
  boundary while using an open, auditable transport.
- Android A/B updates write an unused slot, let the bootloader try it, require
  userspace to mark it successful, and fall back to the old slot after failed
  attempts. Lefony adopts exactly those state transitions for its two 8 MiB
  boot capsules.

Primary references:

- Android A/B system updates: <https://source.android.com/docs/core/ota/ab>
- Android bootloader update guidance: <https://source.android.com/docs/core/architecture/bootloader/updating>
- HP Connectivity Kit user guide: <https://h10032.www1.hp.com/ctg/Manual/c05332952.pdf>
- TI-Nspire OS transfer support: <https://education.ti.com/en/customer-support/knowledge-base/ti-nspire-family/product-usage/40358>
- Casio OS Update mode: <https://support.casio.com/global/en/calc/manual/fx-CG100_1AUGRAPH_en/BONDSYeiiehand.html>

## Physical NAND contract

The implementation requires the captured 512 MiB, 2 KiB-page, 128 KiB-erase,
64-byte-OOB geometry. Slot A remains at 4--12 MiB. The first two eraseblocks of
the 13--14 MiB misc partition hold boot metadata. Slot B is 496--504 MiB, a
future rescue image is reserved at 504--511.75 MiB, and the final two
eraseblocks remain reserved for Linux's on-flash NAND bad-block table. Existing
UBI erase-counter headers in the slot/rescue tail must be backed up and
explicitly retired during one-time A/B provisioning; no live UBI volume header
may be present there.

The production U-Boot build uses the standard MXS NAND driver. The recovery
installer uses the already-proven Linux GPMI/BCH MTD driver. Lefony itself has
no physical NAND erase/program API.

## Qualification gate

The code and artifacts are ready for device qualification, but provisioning is
not enabled by changing the layout manifest alone. A physical device must pass
all of these checks first:

- complete native USB enumeration and signed payload reception;
- read-only confirmation of NAND geometry, bad-block map, both current boot
  streams, misc, and the final 16 MiB;
- recovery read/write/readback on a non-boot test eraseblock;
- cold-boot success from both A and B;
- reset/power-loss injection before slot write, during slot write, between
  metadata copies, and during candidate boot;
- three failed candidate boots returning to the known-good slot;
- successful candidate boot becoming active only after Lefony's health mark.

Until that matrix passes, `physical_ab_migration_allowed` stays false and the
installer refuses an unprovisioned device rather than inventing a layout.
