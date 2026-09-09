# HP Prime G2 A/B migration and first-install gates

Lefony's signed A/B update path is implemented in the emulator, physical
firmware, recovery installer, and U-Boot. A physical calculator is deliberately
not provisioned for it until the one-time NAND migration is qualified. This
document separates two operations that have different trust and recovery
requirements:

1. **First installation:** replace HP's software and establish Lefony's boot
   structures, trust root, metadata, and initial slot.
2. **Normal update:** while Lefony is running, authenticate an LFU capsule,
   hand it to a RAM-resident recovery environment, write only the inactive
   slot, verify it, mark it pending, and reboot with automatic rollback.

The second operation is fully exercised in the emulator and implemented for a
calculator that already has valid A/B metadata. The first remains gated by
physical NAND qualification and by the stock updater's authorization policy.
An unprovisioned physical calculator is rejected before any NAND write.

## Captured layout versus emulator layout

All offsets are erase-block aligned. One erase block is 128 KiB.

| Region | Captured physical layout | Emulator A/B layout | Policy |
|---|---:|---:|---|
| ROM boot / U-Boot | 0--4 MiB | 0--4 MiB | Preserve and back up raw+OOB |
| Lefony slot A | 4--12 MiB | 4--12 MiB | Existing kernel slot |
| Device tree | 12--13 MiB | 12--13 MiB | Preserve |
| Misc / A/B metadata area | 13--14 MiB | two redundant 128 KiB records | Reprovision only from recovery/RAM updater |
| Linux UBI rootfs | 14 MiB--end of NAND | 14--496 MiB | Must be measured and migrated/shrunk first |
| Lefony slot B | currently inside UBI | 496--504 MiB | Not physically safe yet |
| Rescue image | currently inside UBI | 504--511.75 MiB | Preserve until a rescue format is qualified |
| Linux NAND BBT | final two eraseblocks | 511.75--512 MiB | Always preserve |

The existence of apparently unused files inside Linux does not prove that the
tail physical eraseblocks are free. UBI wear leveling can place live logical
eraseblocks anywhere in the partition.

## Required physical evidence

The signing and recovery-writing components now exist. Physical A/B
provisioning remains disabled until their behavior and the destructive layout
migration have been qualified on real hardware:

- a complete raw+OOB NAND backup with bad blocks retained and a second read
  whose geometry and content are independently verified;
- ROM FCB/DBBT and boot-copy mapping, including the BCH geometry used for every
  boot page;
- a read-only UBI inventory containing PEB-to-LEB mappings, bad/reserved PEBs,
  erase counters, volume sizes, and the highest live PEB;
- a tested rootfs migration that creates the final 16 MiB tail reservation
  without assuming that filesystem free space equals free NAND eraseblocks;
- the generated release LFU public key embedded in Lefony, with the private key
  kept off the calculator and repository, followed by an explicit production
  key-custody decision;
- the implemented recovery-Linux GPMI/BCH writer validated against the physical
  bad-block map and slot boundaries;
- power-cut tests at every erase, page program, readback, and metadata commit
  boundary, followed by successful ROM recovery from the untouched backup.

The provisioning operation must run from RAM or recovery, never from a rootfs
whose backing UBI volume is being moved. It must create slot B and rescue space,
seed a verified slot A, write one metadata copy at a time, and leave the old
boot path recoverable until the new U-Boot policy has booted successfully. The
ordinary update action does not perform this migration implicitly.

## No-tweezers first installation

The authentic HP OS and maintenance image now run in the private emulator
fixture. The normal HP USB protocol's mode-3 request enters HP update mode, so
the mechanical pin-short sequence is not inherently required merely to reach
that mode.

That does **not** authorize Lefony. The official Connectivity Kit verifies
HP's RSA/SHA-256 `files.sig` before upload, and device-side enforcement is now
proven: a one-bit package mutation with valid per-report CRCs is rejected before
any NAND program. A no-tweezers installer is shippable only if one of these is
demonstrated in the emulator and then reproduced safely on hardware:

- HP update mode accepts a Lefony-controlled, authenticated RAM bootstrap;
- an intended stock maintenance API can execute that bootstrap; or
- a responsibly handled vulnerability provides bounded RAM execution.

The tested updater accepts only the authentic signed package. HP's private key
cannot be replaced by an engineering workaround. ROM recovery therefore
remains the first-install path unless a separate authorized execution path is
found, while every later Lefony release uses the cable-only A/B updater.

## Evidence already passing

`vm/test-native-ab-update.sh` currently proves the controlled update sequence:

- factory slot A seed and verification;
- full signed LFU transfer over native USB;
- inactive slot B erase, bad-block-aware program, SHA-256 readback, and
  redundant pending metadata commit;
- reboot into pending slot B and runtime confirmation;
- a second signed update followed by three unconfirmed boots; and
- automatic rollback to the last confirmed slot.

The deterministic manager tests additionally cover interrupted erase/program,
metadata power loss, corruption, corrected/uncorrectable ECC, read disturbance,
wear promotion, and bad-block capacity loss. The physical build also includes
the U-Boot slot-selection policy, recovery installer, release-key injection,
and signed LFU packaging. Physical enablement must preserve those invariants;
it is not allowed to weaken them to fit the captured layout. The complete
qualification matrix is in [LEFONY-UPDATE-ARCHITECTURE.md](LEFONY-UPDATE-ARCHITECTURE.md).

The exact-capture cold-boot test additionally replays the physical FCB,
redundant U-Boot streams, redundant A/B metadata, slot-A payload and DTB. It
reproduces the 2026-09 black screen as a truncated U-Boot environment, and the
repaired A/B image verifies the captured slot SHA-256 and reaches a visible
Lefony frame. This qualifies the logical A/B handoff in emulation; it does not
remove the physical NAND-layout migration gate above.
