# Boot-menu Phase 1 qualification

Date: 2026-09-25 (local). Target: HP Prime G2, i.MX6ULL. This is a development
bootloader candidate, not HP dual-boot support or a public installer release.

Phase 1 status: implemented, installed in NAND with readback verification, and
accepted by the user on the connected calculator. This acceptance covers the
boot-menu milestone, not a public release or HP OS support.

## Candidate and scope

The source is [`native/prime_g2/bootmenu`](../native/prime_g2/bootmenu/README.md),
applied by the checked preparation script to the existing pinned
`zephray/uboot` revision `83c84d5e5b7a72855f4455c499b23ee6ead4f74d` plus the
one-shot SDP patch. The upstream revision and normal Lefony image locations
are unchanged. Build: `2018.03-lefony-menu1`.

Candidate NAND image: 442,368 bytes, SHA-256
`d96066b5eb99e3abbb0a23d86d11ccdf3c8800503a1d25f6f445c474b8fcc11a`.
RAM binary SHA-256:
`2be2adfbe7ce1261757eb075e675f9652691272278253dde4568e6da35f444a6`.
Build outputs and private device evidence remain under ignored `build/`.

The visible flow uses warm white and green, no standalone wordmark and no
numeric countdown. The progress bar represents a three-second timeout.
Physical Enter opens the menu; other keys and touch cannot interrupt startup.
The menu itself waits indefinitely. Up/Left move backward and Down/Right move
forward through choices, stopping at the ends without wrapping; Enter selects. HP is visibly unavailable and cannot be
booted or selected as physical priority. Recovery and real Lefony handoff are
implemented. Phase 2 and later HP integration remain separate work.

## Automated evidence

- `make test`: 2,027 passed; two optional private-fixture tests skipped.
  `make check-public` and `git diff --check` pass.
- Clean candidate build: `./scripts/build_prime_g2_bootmenu.sh`.
- Physical and VM native firmware: `make firmware` and `make firmware-vm`.
- Portable menu/preferences compiled with AddressSanitizer and UndefinedBehaviorSanitizer:
  held/released Enter, deadline precedence, clock rollover, debounce, unavailable
  OS, recovery confirmation, touch capture/cancellation, both synthetic priority
  values, invalid records, overflow, and interruption at all 64 record bytes.
- Checked preparation tested for repeat application and rejected upstream drift.
- Actual ARM U-Boot: `vm/test-prime-bootmenu.py`, using disposable synthetic NAND
  overlays and the real Lefony capsule. Automatic and keypad/touch-selected
  Lefony startup, disabled HP, saved generation after a new machine start,
  invalid preferences/images, rejected unprovisioned writes and recovery USB
  enumeration pass. One-shot recovery returns to actual Lefony boot after
  RESET and after the real 180-second timeout. Captured LCDIF frames were inspected.
- `vm/test-native-uboot-recovery.py` passes the actual native CRC/action gates,
  one-shot token consumption, RAM U-Boot handoff and SDP enumeration without
  changing NAND. The panel-enabled run initializes recovery UI successfully.
- Native emulator smoke covers direct ELF, USB protocol and normal UI startup.

The emulator patch set is r79 on the existing pinned QEMU revision. It adds
GPIO sampling of the same keypad switches already modeled by KPP, external
idle I2C pull-ups for U-Boot's bus-recovery probes, and a reset-edge correction:
a repeated low GPIO notification must not release the panel reset. The test
sets the ARM architectural timer to the Prime's 8 MHz rate. These model changes
do not establish electrical timing on physical hardware.

The tested newly built Lefony capsule has SHA-256
`67e0c5fd566a8bc157cdeecbdbc8c13ccdbe0ceb3fff8c1c03424835d53bcf09`;
its physical native payload hash is
`df56f2e9003b8fce90978ab8fb5ff4bd2838afcaacf313214ecd3a373e48c941`.
The physical trial preserves the calculator's existing OS rather than updating
it as a side effect of bootloader work.

## Physical qualification

The authorized RAM trial is complete: the user confirmed the physical screen,
Up/Down navigation and Enter-selected Lefony startup. A second unattended RAM
trial returned to native USB and collected healthy USB/display initialization
and rendered framebuffer diagnostics. This does not measure the three-second
prompt precisely: the recorded host elapsed time includes USB diagnostic reads.

Two independently acquired complete 553,648,128-byte raw/OOB NAND backups match;
their local files were hashed again before proceeding. Corrected reads showed
the entire 1 MiB `misc` partition erased and its factory markers intact. The two
profile-1 generation-1 preference pages were programmed with ECC enabled and
bad-block skipping disabled, without erasing any block. Exact readback of the
whole partition matched the expected image. The known installed bootloader and
RAM recovery bundle were retained independently.

The initial bootloader installation completed with live model/geometry checks,
preflight and readback. Both 216-page streams at 1 MiB and 2.5 MiB exactly match
the initial image (`b562ae714843d7d4aafbed6cb1e4aa36b25a15d4e78b48c0b81e767bc758b019`),
not the current candidate listed above. All four FCB copies pass raw BCH-40, checksum and geometry
verification; the three usable DBBT copies agree. Factory-bad metadata block 7
and all markers are preserved. Only its pre-established kernel erase refusal
was accepted. Two corrected OS reads matched before installation, and the
post-installation OS readback is unchanged (SHA-256
`f89621879f75057713a4f732905fc1b583ba886cb8a15ea575692e184eb6b150`).
The candidate's 488-byte DDR DCD is byte-identical to the qualified loader.
The installed NAND boot returned to native USB with both the one-shot and RAM
recovery capability flags set. Physical feedback found that Enter did not interrupt the progress bar. This
initial installation is therefore not the accepted Phase 1 result. The fix
restores each keypad column's low output latch before scanning: GPIO DR reads
input pad levels, so the backlight read/modify/write could otherwise latch a
column high. The emulator now models undriven columns sampling pulled-up rows
to reproduce this interaction. The original binary now reproduces the missed
Enter under that model, while the corrected binary passes held and newly pressed
Enter tests. The user confirmed corrected Enter entry and a subsequent Enter
boot in RAM. A further physical report identified missed Down presses. The
current candidate adds Left/Right, uses the native driver's bounded GPIO
settling loop after column release and drive, and passes the four-arrow GPIO
regression. Further user feedback requested natural repeated Up/Down navigation;
the current candidate stops at the first/last item and exercises repeated presses
in both directions. After permanent installation and the requested Enter/four-arrow
check, the user confirmed: “everything works perfectly.” This accepts the
installed Phase 1 boot-menu interaction; HP integration remains a later phase.

Several recovery attempts stopped before any write because USB did not return.
After restoring the connection and launching recovery through the current RAM
candidate, the normal Linux/kobs installation path completed. No alternate raw
writer or weakened preflight was used. A fresh raw boot backup was saved; live
model/geometry/marker checks and both prior boot streams matched the known
initial installation before writing.

The **current candidate is now installed in NAND**. Both 216-page streams at
1 MiB and 2.5 MiB have exact SHA-256
`d96066b5eb99e3abbb0a23d86d11ccdf3c8800503a1d25f6f445c474b8fcc11a`.
Independent host verification confirms all four raw BCH-40 FCBs with zero
corrections, their checksum/layout, and all three usable DBBT copies. Factory
bad-block markers are unchanged. The OS readback remains byte-identical, and
the complete misc partition matches its pre-update readback, including both
valid generation-1 Lefony-priority records. The 488-byte DDR DCD again matches
the qualified loader. Automatic boot from the installed NAND returned to native
USB with both recovery capabilities set (flags 14). LCDIF reached RUN with
`CTRL1=0x01070300`; this boot recorded no LCDIF fault events.

One installed startup logged an LCDIF FIFO-underflow status at native runtime
1,684 ms; the automatic RAM trial did not. A later read of that same boot retained the status. This observation remains
separate from emulator passes. The latest corrected NAND startup recorded no
FIFO-underflow flag or LCDIF fault event. The subsequent user acceptance reported
normal operation; no extended reset/endurance campaign is claimed.

No emulator result qualifies physical power-loss recovery, NAND endurance,
battery-disconnected startup, key feel or touch accuracy. Destructive physical
power cuts are outside this development validation; interrupted preference
saves are exercised on synthetic storage. No HP handoff, HP filesystem boundary
or partition migration has been tested by this phase.
