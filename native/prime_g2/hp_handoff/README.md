# Experimental HP RAM handoff

Built separately by `scripts/build_prime_hp_handoff.sh` on the pinned Prime
U-Boot port. This command is absent from the ordinary Phase 1 boot-menu build.
Its separate `lfhpboot` command enables a verified HP image in an isolated
stock-layout RAM trial. It does not change `lfboot` or provide a NAND installer.

The exact V15751 main OS or updater must be loaded at `0x80000000` after U-Boot
initializes. `hpram os 7d0360` or `hpram updater 577ac` verifies the complete
image, original IVT and HP-compatible DDR map, then transfers to its ARM entry. The normal `go` command
in this board fork forces Thumb and is unsuitable for these images.

`lfhpboot` verifies the main OS staged at `0x84000000` and copies it after board
initialization. Persistent priorities and Lefony selection are disabled in this
stock-only experimental menu.

Use the emulator probe and qualification instructions in
[Phase 3](../../../docs/HP-LEFONY-PHASE3-HANDOFF.md). Model menu boot and cold saved-history checks pass.
Physical menu startup and display work when preceded by HP's DDR initialization;
physical saved-history retention and verified Lefony rollback complete that
Phase 3 milestone. Consult the record for its exact scope and limits.
HP itself may write NAND; do not run this experiment on the current
Lefony layout. No proprietary bytes or modified HP images belong here.

The separate `scripts/build_prime_hp_ram_recovery.sh` builds an experimental
manufacturing kernel with kexec from the original pinned NXP source/configuration.
Pass the private original `config.gz`, complete RAM U-Boot/DTB binary and its
expected SHA-256. It only builds local artifacts; it performs no USB operation.
The embedded `kexec-uboot --load` helper stages that loader in RAM using Linux's
normal syscall. `--execute` stages it again and leaves Linux for one-shot U-Boot
SDP. Neither helper accesses NAND. Physical qualification and the stock restore
procedure remain separate; consult the Phase 3 record before using these tools.

`mtd_inventory.c` is a freestanding read-only Linux MTD geometry/bad-block probe.
`scripts/prime_hp_restore_plan.py` verifies private backup hashes and produces an
offline block comparison; it does not execute a restore. In particular, stock
FCB metadata is not permission to ignore factory-bad blocks during rollback.


Research5 keeps its NAND bad-block table only in RAM, offers a bounded 90-minute
SDP session, and fixes legacy-script result reporting. `hp_nand_info.c` exposes
read-only geometry/bad-block inventory and bounded physical block hashing.
Direct native-to-RAM startup works; Linux kexec remains unqualified. See the
Phase 3 record for exact physical test hashes and limits.

`scripts/prime_hp_raw_restore.py` provides guarded raw transactions and complete
image verification for a separately approved private trial. It requires exact
source identities, durable before-image capture/journaling, erase verification,
raw readback and complete-device hashes. Its physical-byte API must never be fed
Linux raw-projection bytes. Consult the Phase 3 record for the completed stock
restore and verified Lefony rollback; neither guarantees power-loss recovery.

Research6 applies the physically checked HP DDR settings in the experimental
ROM DCD. A native-to-RAM launch inherits native DDR settings and is therefore
rejected for HP; use ROM/DCD startup for this experiment. It never reconfigures
live DDR. Set `PRIME_HP_HANDOFF_SOURCE_DIR` and `PRIME_HP_HANDOFF_OUTPUT_DIR` to
absolute paths when a separate build is needed to preserve pinned recovery
artifacts. The original stock restoration passed full physical verification;
Lefony rollback also passed complete physical verification and native USB/recovery
return. The user confirmed restored Lefony boot and menu operation; the full
raw match verifies preservation of apps/data bytes. Phase 3 is complete for this
recorded trial; HP remains disabled in the permanent menu.
