# Lefony install preserving verified Prinux U-Boot

Installed after user manually entered ROM recovery, 2026-09-09 UTC.

- Lefony: latest archived physical recovery capsule, branded nonblocking-ADC build, SHA-256 `38cc819c903da851a6dc6a2690eb5162d7f00e039e24a9b0a5c3713c922783b3`, 2103152 bytes. Newer archive entry is emulator-only and was not selected.
- U-Boot preserved: original Prinux `2bbea80c11b6cd7ec4e27f216637cc7d32356cc2a0c23255909308a9efdaef3c`. Both bootstream copies matched before writing OS. No mtd0 writes performed.
- Replaced only mtd1 (kernel) with Lefony. DTB, misc, and Linux rootfs preserved; no backups taken.
- Upload SHA-256 and byte-for-byte NAND readback passed.
- Mounted preserved Linux rootfs read-only and used its devmem tool via chroot, binding recovery /dev. Cleared SRC_GPR9 and SRC_GPR10 and verified both read zero. Unmounted both mounts and synced.
- Issued one delayed sysrq reset. Recovery USB disconnected. User subsequently confirmed: "lefony os is booting from nand now". This qualifies this exact OS/U-Boot pair for physical reset-to-NAND boot. No subsequent reset or RAM download performed; battery/cold-power-cycle qualification remains pending.

At the user's request, active installer histories were reduced to this single working pair. Other history entries/artifacts were retired recoverably under `build/retired-installer-history-20260909`, outside the installer history roots. Lefony status is `known-good`; U-Boot status is `lefony-nand-boot-verified` with Linux and Lefony evidence. Installer default image selection now prefers the hash-verified known-good recovery capsule.

Scripts: `<user-home>/prinux/lefony-preserve-prinux-20260909.uu`, `<user-home>/prinux/lefony-normal-boot-20260909.uu`.
Logs: `/tmp/lefony-preserve-prinux-20260909-retry.log`, `/tmp/lefony-normal-boot-20260909.log`.
