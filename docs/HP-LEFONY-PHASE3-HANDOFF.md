# Phase 3: original HP image handoff

Status: **Phase 3 complete for the recorded Prime G2 / HP V15751 trial**.
The corrected research6 RAM menu boots the unmodified HP image on hardware and
retains the saved `12+3=15` history after a fresh ROM/menu launch. Model menu,
calculation, save/cold-retention and Lefony/recovery regressions also pass.
The temporary stock trial ended with verified Lefony restoration: all 672
changed-block readbacks and all 4,096 final raw NAND hashes matched the original
backup. Native USB and installed one-shot recovery returned successfully. The
user confirmed that Lefony is running again and the boot menu works perfectly.

The complete raw comparison covers saved apps/data bytes; it is not an
application-by-application functional test. The ordinary installed menu still
disables HP. No experimental HP bootloader was installed in NAND. This milestone
qualifies the isolated stock-layout handoff, not shared-layout dual boot,
filesystem confinement, power-loss recovery or flash endurance. Phase 4 is next
and has not started.

Only the user's current calculator was available. Its overlapping layout
required the explicitly approved temporary stock restoration and verified
Lefony rollback. RAM-loading a loader alone cannot protect Lefony from HP's
writes. The investigation sections below preserve chronological checkpoints;
the completion status above and final acceptance record supersede their earlier
pending states.

## Loader and menu

`scripts/build_prime_hp_handoff.sh` uses a separate checkout/build directory
with pinned Prime U-Boot revision `83c84d5e5b7a72855f4455c499b23ee6ead4f74d`.
It applies the accepted one-shot SDP and menu sources, followed by the checked,
idempotent experimental preparation. It produces no padded NAND installer
artifact and deliberately stops at the command prompt.

`hpram os|updater <hex-length>` accepts only the exact V15751 component sizes,
SHA-256 hashes and original IVT/ARM entry recorded in
[Phase 2](HP-LEFONY-PHASE2-COMPATIBILITY.md). It initializes the panel, stops
U-Boot scanout with a bounded wait, releases keypad columns, performs standard
ARM cache/MMU/interrupt cleanup and enters `0x80002000` in ARM state. The pinned
port's ordinary `go` forces Thumb and is unsuitable. The command has no NAND
reader, writer or partition migration. Exact-hash research restrictions do not
replace release signing or constrain HP's own writes after entry.

`lfhpboot` reuses the existing menu rendering and GPIO/Goodix input. It checks
the staged main OS at `0x84000000`, enables only HP in this isolated stock trial,
and disables persistent preference writes. It copies the verified image to
`0x80000000` immediately before handoff. This copy must follow board startup:
startup writes the existing `LFUB` capability marker at `0x80001000`. The probe
verifies the entire copied image against the original before execution. No HP
instructions, NAND geometry, partition bounds or filesystem code are patched.
The ordinary `lfboot` command and one-shot recovery remain available separately.

## Reproduce the model qualification

All firmware, NAND, overlays and captures are private, ignored build artifacts.
The full raw/OOB capture must have the documented Linux BCH-2 projection; the
converter rejects incompatible length/FCB geometry and retains captured parity.
It does not generate a physical flashing image or repair/re-encode the source.

```sh
./vm/build-prime-g2-qemu.sh
./scripts/build_prime_hp_handoff.sh
.venv/bin/python vm/convert-prime-stock-nand.py \
  --capture-linux-bch2 /private/path/stock-nand.raw \
  --output build/dual-boot-phase3/stock-physical.raw
.venv/bin/python vm/test-prime-hp-retention.py \
  --image build/dual-boot-phase2/fixture/HPPrime.img \
  --stock-physical build/dual-boot-phase3/stock-physical.raw \
  --uboot build/lefony-uboot-hp-handoff/u-boot-dtb.bin \
  --ddr-image build/lefony-uboot-hp-handoff/u-boot-dtb.imx \
  --output build/dual-boot-phase3/retention-test
```

Use new output paths. The retention check runs two separate QEMU processes,
selects HP through the menu with Enter, enters the calculation through GPIO,
saves with Shift+On, and cold-boots a copy of the resulting NAND overlay. It
requires NAND writes, changed history after input, identical history pixels
before shutdown and after restart, and an unchanged backing-file hash. Each
run also checks unknown-component, wrong-length and corrupted-image rejection
in the actual ARM loader. `vm/probe-prime-hp-handoff.py` remains an observation
tool: its successful transfer message alone does not establish boot success.

The retained older stock capture supplies real HP filesystem contents and
unchanged stock geometry; the RAM OS is the exact V15751 image. This demonstrates
loading and saving those contents, not general compatibility across HP versions.

## Model corrections and limits

- **r80 NAND clocks:** remove an incorrect CCGR6 dependency; NAND root gates
  belong to CCGR4. Live clock and DMA gating tests cover both cases.
- **r81 short BCH transfers:** accept the guest's eight 128-byte BCH-40 FCB
  codewords with 32 metadata bytes (`0720a020 / 0840a020`). DMA writes the actual
  1024-byte payload. Synthetic physical codewords cover clean, corrected,
  uncorrectable and erased reads, completion/interrupt status and a following
  payload canary. The legacy decoded-capture path retains its stricter layout.
- **r82 keypad IRQ:** switch closures and driven-column changes pass through
  the normal GPIO input/interrupt logic, even without CPU polling. This wakes
  HP's GPIO-based keypad driver; no HP wait loop or CPU interrupt is patched.
- **r83 SNVS power key:** model the latched LPSR SPO event, its W1C acknowledgement
  and DP_EN interrupt gate separately from the read-only HPSR BTN pin level.
  This follows the register contract used by the upstream
  [Linux SNVS power-key driver](https://github.com/torvalds/linux/blob/master/drivers/input/keyboard/snvs_pwrkey.c).
  HP's normal shutdown now saves history; holding a key no longer creates an
  unacknowledgeable interrupt.

The model preinitializes DDR, so these runs do not test HP DCD or physical reset
state. HP programs a 320×240 XRGB8888 framebuffer and different LCDIF/pad/timing
settings from Lefony's serial-byte setup. The existing strict panel model rejects
that configuration. `lcdif-logical.png` reads the actual LCDIF framebuffer;
`screen.png` remains the separate modeled panel result. **Logical pixels are
not evidence of correct physical panel routing, timing or visibility.** No
panel checks were disabled to obtain the retained-history result. The RAM
handoff's panel initialization/quiesce behavior needs physical qualification.

## Validation record

2026-09-26 UTC (September 25 local), Prime G2 / i.MX6ULL:

- Experimental RAM loader SHA-256:
  `4f2d6be63b580afad95e5086f249c5e5c37df182811fc3740b623c95581dcdd0`.
- QEMU 11.1.1 / Prime r83 SHA-256:
  `b34537590c1fa606c545524aae8ed4235404afda31f5d58e199811377dc801f1`.
- Stock physical fixture SHA-256:
  `829c782248d50993ece6289c1fda8238bd9edcb804fb7361f1bf9dc9816415cb`.
  Checked converter reproduces the independently reconstructed fixture exactly.
- HP main-image SHA-256:
  `25d3d2d27e45fc3ce7dc8c4a111b31f8aefc14c4b21e8d8ee4b32251e31c1b82`.
- Private retention evidence: `build/dual-boot-phase3/r83-retention-test/`.
  History-region SHA-256 after input and cold restoration:
  `327fed2e094fcfd3743db08edf8e01d6c093eec4a8550534d9c3a2b8cad99db3`.
- U-Boot build and QEMU fresh/repeated builds passed. Existing U-Boot compiler
  attribute warnings remain. 51 targeted host tests and three subtests passed.
- Short-page BCH, BCH IRQ, GPIO keypad IRQ, SNVS button and peripheral regressions
  passed. The old peripheral test incorrectly treated BTN as W1C; it now releases
  the physical key, with separate tests checking read-only BTN and SPO W1C.
- The accepted Phase 1 image passes the complete menu/recovery regression on
  r83: automatic boot, Enter, four arrows, held keys, preferences, Goodix touch,
  invalid-input/save rejection, USB recovery and one-shot RESET to Lefony.
- The experimental image separately passes those Lefony/recovery cases with
  `--command-prompt`, explicitly issuing `lfboot` after its intentional prompt.
- Public-tree and whitespace checks passed; no proprietary data or private key
  is added to the public source tree.

The accepted installed Phase 1 RAM-image hash remains
`2be2adfbe7ce1261757eb075e675f9652691272278253dde4568e6da35f444a6`.
The physical device has been read through RAM recovery for fresh backup and
used for a RAM-only recovery-kernel launch (see the pending result below).
Physical backup, restoration approval and handoff results must be recorded
separately before changing this document's completion status.

## Historical checkpoint: prepared trial before approval

The only calculator was placed into its existing one-shot SDP and RAM Linux
recovery. Model/geometry checks passed. Two independent full raw/OOB reads
produced 36 files per read, **553,648,128 bytes each** (512 MiB NAND plus OOB).
All files were rehashed from disk and both manifests match. Private evidence:
`build/dual-boot-phase3/current-device-backup/verification.json`; manifest SHA-256:
`b4cf9f63b878812568f618b5ff389a7033413301fd3f2a1d868b754ba3c338e2`.
The running recovery kernel reports the same BCH-2/GF13/10-byte metadata capture
geometry as the original stock backup. Backup agreement is not proof of a
successful future restoration.

Proposed execution, requiring explicit approval because it temporarily replaces
this calculator's current OS and data:

1. Establish the ROM recovery route and stage the exact recovery/loader assets
   before any persistent change. The existing HP diagnostic FCB-erase route
   requires user interaction once HP is restored; hardware ROM entry is the
   fallback if HP diagnostics cannot run. Do not assume Lefony USB remains
   available after replacing its NAND contents.
2. Restore the private original stock raw/OOB capture with unchanged stock
   geometry. The prepared U-Boot raw writer reconstructs physical codewords from
   the exact original Linux capture and verifies their individual identities.
   It does not accept a QEMU fixture as a flashing input. A Linux raw writer
   would instead require the original Linux representation. Preserve factory
   bad blocks, reject unexpected geometry/markers, and verify erased blocks,
   programmed blocks and the entire device before executing HP.
3. Load the separately built experimental U-Boot into RAM through recovery,
   stage the exact V15751 main image, and enter `lfhpboot`. Verify the physical
   display, Enter/arrows, calculation, save, and repeat handoff with retained
   history. No experimental bootloader is installed permanently.
4. Return through ROM/RAM recovery, restore the newly verified current Lefony
   backup, independently verify readbacks and both boot copies, then confirm
   Lefony boot, menu, recovery and retained apps/data. Stop on any new bad block
   or write/readback discrepancy; never silently relocate raw backup records.

At this checkpoint the writer was model-tested only, and neither stock
restoration nor HP execution had occurred on the connected calculator. The
later physical results below supersede this historical state.

## Recovery preparation and unresolved handoff

The read-only ARM helper `native/prime_g2/hp_handoff/mtd_inventory.c` ran on the
physical manufacturing kernel. Its MTD geometry and eight factory-bad blocks
match both fresh backups and the old stock capture. The offline review tool
`scripts/prime_hp_restore_plan.py` verifies the backup manifest, compares every
raw/OOB eraseblock at its original address, and rejects any changed factory-bad
block. It has no USB or flash operations. The actual comparison identifies 668
changed good blocks. Stock metadata produces additional conventional bad-marker
bytes in blocks 0, 1, 2, 3 and 6; those require a reviewed return procedure,
not a blanket bad-block override. Five host cases cover bad-block preservation,
extra metadata markers, truncated streams, physical-inventory rejection and
rejection of a physical-codeword fixture passed as a Linux raw capture. The
planner validates all four original stock FCB records before comparison.

Keeping the current first 4 MiB while restoring the other stock regions was
tested in the model and **did not boot HP**: black logical framebuffer, no ECC
writes, and a stable IRQ-masked execution path. Do not flash that hybrid plan.
The observation probe's `--ram-loader` option wraps the complete unchanged
U-Boot/DTB binary in ELF to prevent QEMU's automatic NAND ROM path from replacing
the intended RAM entry. An ELF without the appended DTB is not equivalent.

The existing manufacturing Linux can write NAND, but has `CONFIG_KEXEC` disabled.
`scripts/build_prime_hp_ram_recovery.sh` prepares an isolated RAM-only candidate
from its exact NXP source revision
`5d6cbeafb80c52af322a45985aa7b41f9b9ec66c`, with the captured configuration plus
kexec and its selected dependencies. It leaves release recovery assets unchanged.
The small `kexec_uboot.c`/`.S` helper embeds a host-hash-verified complete U-Boot
binary and uses Linux's normal kexec relocation/shutdown API. It contains no NAND
access. The handoff sets the existing one-shot SDP mailbox, then enters the RAM
loader. This is a candidate, not a qualified recovery route.

The kernel build passed after adding the required `lzop` build dependency.
Candidate SHA-256:
`78266974d29759d45992838858a147c4eef2f0fbbdf348b87f4b54900adec049`.
On hardware the SDP download/jump completed, but the expected manufacturing USB
endpoint **did not reappear**. After rear RESET and confirmed Lefony boot, SDP
read the retained kernel log: the new kernel reached userspace and the USB
manufacturing service. The old qualified recovery image then showed the same
USB symptom, resolved by unplugging/reconnecting USB without RESET. A second
new-kernel run became accessible and passed the physical MTD inventory check.
Its `kexec_load` succeeded and `/sys/kernel/kexec_loaded` reported `1`.
The subsequent execution request did not expose the expected U-Boot SDP endpoint
within 45 seconds; the actual handoff remains unproven. No NAND operation occurred.
After rear RESET, the retained kernel log was retrieved through SDP. It ends
with `Starting new kernel`, `Disabling non-boot CPUs ...`, and `Bye!`. This
confirms Linux reached its final jump, but does not establish U-Boot startup.
A normal recovery-to-Lefony command also failed to restore USB enumeration;
physical RESET/USB reconnection and a direct native RAM-launch control are being
checked separately. No NAND erase or write was sent.

The tested helper SHA-256 is
`875ad1b6adc2d7eb46719cc71c3f9235364d65245bfe7fb3351a96deaa04e1d0`.
The existing kernel rejected the helper's load request with `ENOSYS`, as expected
from its configuration. That rejection is not successful kexec qualification.

This failed Linux-kexec route is superseded for trial entry by the direct
native RAM launch below. Hardware ROM return after HP still requires physical
qualification. Obtain the previously requested explicit approval for temporary
stock replacement before sending any NAND erase or write. Phase 3 remains
incomplete.


## Direct RAM recovery and guarded restore follow-up

The native RAM bootstrap now launches the complete experimental U-Boot/DTB
successfully on the physical Prime G2. Use `prime_g2_uboot_recovery.py ram-test`
with its canonical wrapper. Return with an explicit U-Boot `reset`, rather than
calling `lfboot` while the SDP gadget is active. The native diagnostic endpoint
confirms the installed one-shot bootloader capability after reset. Native Lefony
is not a HID interface: use its libusb diagnostic protocol to detect its return.
A HID-only scan caused one false report of missing native USB.

The isolated loader now disables **flash BBT creation** and keeps the bad-block
table in RAM. Otherwise ordinary NAND initialization reserves the last four
blocks and can create persistent BBT metadata in the stock HP region. This
change is confined to the experimental build; the installed loader is unchanged.
It also fixes SDP's legacy-script result status, stops at the prompt after the
recovery window, and adds read-only `hpnandinfo` and `hpnandhash` commands. The
latest research5 build has a bounded 90-minute window to accommodate complete
preflight, raw transfers, erase verification and full final verification. It
never automatically boots an OS when that window ends.

A research3 physical scan compared **all 4,096 raw physical block hashes** with
independent inverse projections of the verified Linux backups. Every block
matched, including all eight factory-bad blocks; no supplemental capture was
needed. The first eight device-computed hashes were independently checked using
complete USB raw reads. The full fingerprint scan took 199.5 seconds. Evidence:
`build/dual-boot-phase3/restore-tools/fresh-state/verification.json`.
The scan's loader SHA-256 is
`2835f185d56d908db5048cbfde55aa06db1f5597cdefe2e2521f1434b67062e3`.
No NAND erase, write or mark-bad command was sent.

`scripts/prime_hp_raw_restore.py` supplies isolated restore primitives, not an
ordinary firmware installer or signed-update path. It requires explicit trial
approval, exact geometry and factory inventory, complete before-images, verified
RAM staging, a durable journal and exact raw readback. Erase is independently
verified: the pinned U-Boot erase utility can return success after an underlying
MTD failure. Readback uses a separate RAM buffer so it cannot overwrite the
staged program data. An ambiguous USB response stops the operation without
retrying a command. Empty HID reads wait for the same response within a finite
bound; malformed or out-of-order responses remain errors. Repeated physical
reads exposed intermittent report loss with a whole-block SDP request. The
[macOS hidapi implementation](https://github.com/libusb/hidapi/blob/master/mac/hid.c)
drops old reports when its short input queue fills. Reads now request at most
1,024 bytes at a time (16 data reports plus one security report), keeping each
complete response below that limit even when the host is descheduled. A host
test simulates that queue and requires exact full-block reconstruction.

The full-image wrapper captures each changed before-image, checks every target
before the first erase, writes the boot region last, and compares all 4,096 final
hashes. It makes no power-loss guarantee. Rollback scans the entire device and
restores every difference from the verified Lefony image, including new HP
writes outside the original 668-block plan. Only exact known stock metadata in
blocks 0, 1, 2, 3 and 6 may receive the narrowly scoped scrub exception. Any
changed factory-bad data, additional bad block or changed metadata identity
stops the operation; there is no raw-block relocation.

QEMU r84 separates marker-based ROM/host exclusion from injected physical
program/erase failures. An OOB marker is not hardware write protection; see the
upstream [U-Boot NAND markbad/scrub documentation](https://github.com/ARM-software/u-boot/blob/master/doc/README.nand).
The synthetic `vm/test-prime-hp-raw-restore.py` runs actual ARM U-Boot commands,
verifies normal programming and rollback, explicitly clears a metadata-only
marker, and proves an injected defect still rejects raw program/erase. Startup
must leave the NAND overlay byte-identical, proving there is no automatic flash
BBT write. Full-device orchestration is tested with all 4,096 hashes before and
after a transaction. These model results do not qualify physical erase/write,
endurance, power loss or recovery-pad access.

Private preparation is in `build/dual-boot-phase3/restore-tools/stock-trial.py`;
its default preparation opens no USB device. It rehashes both complete backups,
checks all four stock FCBs and the exact original stock source hash, derives the
668-block comparison, and binds loader/recovery assets in `trial-review.json`.
The original Linux capture, not the emulator output, supplies target bytes.
Before-images and the action journal are flushed to disk before mutation.
The ROM return script is syntax-checked with UUU's dry-run mode; this is not a
physical ROM-entry test. The expected i.MX6ULL ROM identity is **15a2:0080**
(SE Blank 6ULL), distinct from the research U-Boot's **cafe:5053**. **1fc9:0135
is UUU's i.MX RT106x entry, not this calculator's 6ULL ROM identity.** Hardware
pads may still be necessary after the HP trial; they cannot be operated remotely.

Latest research5 RAM loader SHA-256:
`a844f4f545827be35b905f5a65d6133d5b66b58d82e69c30288b39e1637f47e9`.
QEMU r84 SHA-256:
`061ec101deff13782fdfc3fd3692333affae0a75eba5576d130e304db07e4696`.
The synthetic restore/full-verification and original HP retained-history tests
pass on r84 with the research5 image. The history hash is unchanged from the
earlier r83 qualification. Evidence is under
`restore-tools/raw-restore-research5-model-full.log` and
`r84-research5-retention/`. The public host tests additionally cover stale before-images,
failed erase, corrupted upload/readback, ambiguous writes, exact metadata
exceptions, and unrelated corruption detected by the complete final scan.

Physical stock replacement, HP menu/display/key/save testing and the final
verified Lefony rollback remain pending. None of these model or read-only
results completes Phase 3 or enables HP in the installed menu.


### Latest physical read-only check and trial boundary

Research4 completed 100 consecutive raw block reads using the bounded requests
in 85.8 seconds, with every hash matching the backup, then reset into the normal
native USB protocol. Research5 (hash above) separately passed direct RAM startup,
the eight-block hash check, independent reads of blocks 0, 7 and 4095, and reset
back to native Lefony. Private evidence: `restore-tools/research4-readonly.json`
and `restore-tools/research5-readonly.json`. Its synthetic full-image restore
check also passed (`restore-tools/raw-restore-research5-model-full.log`).

The 90-minute research window accounts for the measured USB speed and repeated
verification; it affects only this RAM session, not the installed three-second
boot screen. Allow roughly 2–3 hours for stock restoration, physical interaction
and Lefony rollback. Actual NAND programming speed has not yet been measured.
The private executor stops starting new erases with five minutes left and never
automatically retries or boots after a failure. A stopped partial restore may
require hardware ROM recovery; verified backups are not a power-loss guarantee.

37 targeted host tests passed, alongside fresh/repeated QEMU builds, the
peripheral regression and the ARM restore tests. Public-tree and whitespace
checks passed. **No physical erase or program command has been issued.** The
calculator is back in Lefony with the installed bootloader unchanged. Approval
for the exact temporary stock trial and verified rollback is the remaining
execution boundary; physical HP and rollback acceptance still gate completion.


### Approved physical trial in progress

The user explicitly approved the temporary stock restoration and verified
Lefony rollback on 2026-09-26 UTC. The first execution passed its complete
live before-image check but stopped before capturing a changed block or sending
any erase: the private original capture directory disappeared after input
validation. The original Linux raw/OOB capture was recovered by reversing the
retained lossless physical projection. Its complete SHA-256 exactly matches the
recorded original `eb3794a616400ef4c81627ba9864ecb50eb883764673ef4c334051452d4616ac`;
256 retained Linux records also passed an independent round-trip check. This
recovers the exact original input; it does not substitute physical-codeword
bytes for a Linux capture. The trial was restarted after returning to normal
Lefony and checking the same immutable review identities. Progress and any
physical results remain separate from completed qualification.


The restarted attempt passed full-device identity checks, saved and independently
rehashed all 668 before-images, and completed the second device preflight. It
has now begun the approved physical erase/program sequence: the first 15 data
blocks passed erased-byte checks and exact raw readback. The trial is **in
progress**, not qualified or complete; NAND is no longer the original Lefony
image. Do not reset or boot a partially restored device. The private journal is
the source of current per-block status.


The approved physical stock restoration **passed**. All 668 changed eraseblocks
passed staged-byte, erased-byte and programmed raw readback checks, and the
final complete scan matched the target hashes for **all 4,096 blocks**, including
the eight preserved factory-bad blocks. Execution took 66.6 minutes. Evidence:
`restore-tools/stock-1790409855582406000/qualification.json` and its durable action
journal. NAND now contains the verified original stock image. This qualifies
this recorded restore, not power-loss recovery or the still-pending Lefony
rollback. The original V15751 image is being staged for the physical HP menu
trial; HP startup is not inferred from a successful restoration.

### Physical RAM handoff failure and stock boot control

The entire 8,192,864-byte V15751 RAM upload was read back and matched its exact
SHA-256 before launching the research5 menu. The user confirmed that the menu
appeared, but selecting HP OS caused the display to slowly fade to white.
The old research USB interface remained enumerated initially; a bounded,
read-only SDP probe failed with a short command transfer. Enumeration therefore
did not establish a working recovery service or successful HP execution.

After rear RESET, the user confirmed that stock HP booted and everything worked,
and reported build **15515** in About. The Mac enumerated the normal HP Prime
USB device (`03f0:2441`).
This establishes a working stock boot/display control after the verified NAND
restoration. It does not qualify the V15751 RAM handoff: the installed stock
15515 image and its original startup path are separate from the V15751 experiment. The
failure may concern display state or earlier startup; its root cause is not
yet established. The calculator currently runs stock HP, and the already
approved verified Lefony rollback remains outstanding. Phase 3 is incomplete.

The observation tool now supports `--sdp-launch`: it preloads the command in
model RAM, enumerates the research gadget, requests its HID descriptor, sends
the SDP jump command, and selects HP with the modeled Enter key. Research5
still reaches HP and calculates `12+3=15` through this path. Private evidence:
`research5-sdp-hid64-jump/observation.json` and `after-keys.png`. This is an
observation, not a new qualification: the serial log includes an EP0 IN failure
warning during enumeration, the upload is a RAM fixture, and the strict physical
panel result remains separate from the logical framebuffer. Earlier probe
attempts timed out while initializing the modeled HID transport. No physical
bootloader or NAND changes were made during this follow-up.

The stock first OS page decodes with zero BCH errors. Its 724-byte DCD matches
V15751 exactly, narrowing the version comparison without proving equivalent
runtime initialization. The physical root cause is still unresolved. The
follow-up host checks passed 27 tests; public-tree and whitespace checks passed.

### Physical ROM entry and clean-start comparison

The user subsequently entered genuine ROM SDP: the Mac reported `SE Blank 6ULL`
(`15a2:0080`). UUU stopped before transfer with a macOS kernel-driver detach
error. Native HID transport successfully read ROM registers, applied the pinned
research image's DCD, uploaded that same image, and verified all 457,728 RAM
bytes against its hash. A second DCD command after SKIP_DCD acknowledged but
did not retain the one-shot token, so execution stopped before jumping.

A separate continuation reverified the entire RAM image, then used the standard
SDP WRITE_REGISTER command, following
[NXP's implementation](https://github.com/nxp-imx/mfgtools/blob/master/libuuu/sdp.cpp),
to set the reviewed one-shot token. Token readback and the ROM jump succeeded;
research U-Boot enumerated as `cafe:5053`. This establishes physical ROM-to-RAM
recovery, without a NAND command. The private rollback runner now uses this
native HID sequence with the same pinned image and token, retaining all its
existing backup, geometry, journal and complete-device verification checks.

The exact V15751 image was uploaded and fully read back again before requesting
the HP menu. This new trial starts from ROM instead of the earlier running
Lefony firmware. The user reported the same fading white screen after selecting
HP. A bounded read-only SDP probe again failed with a short command transfer.
Thus inherited state from a running Lefony session is not the sole cause;
the U-Boot-to-HP handoff and HP-version difference remain under investigation. Evidence:
`restore-tools/rom-hid-token-jump.json` and
`restore-tools/stock-1790409855582406000/hp-clean-rom-launch.json`.
No bootloader was installed or NAND rewritten during this comparison.

### Direct ROM-to-HP control succeeds

After returning to ROM SDP, the exact V15751 image was loaded directly using
its own unmodified DCD and IVT. All 8,192,864 RAM bytes matched the source hash
before the jump. Normal HP USB (`03f0:2441`) appeared, and the user confirmed a
clear display, `12+3=15`, and build **15751** in About. This qualifies the direct
ROM-to-HP control, not our menu handoff or retained-data milestone. Evidence:
`restore-tools/rom-hid-direct-hp.jsonl`.

The HP and research U-Boot DCDs differ in nine final register values, including
MMDC MDCTL (`85180000` vs `83180000`) and MDASP (`5f` vs `47`). HP's observed
LCDIF framebuffer is at `907cf840`. The U-Boot MDASP value ends CS0 at
`8fffffff`, below that address; HP's value extends it to `bfffffff`. The absolute
32 MiB partition units follow [NXP's MMDC explanation](https://community.nxp.com/t5/i-MX-Processors/Questions-about-value-in-reg-MMDC1-MDASP/m-p/314662).
This is a concrete memory-map mismatch and a leading cause to test, not yet a
qualified fix. The current QEMU model always provides the DDR alias independently
of MDASP, so its passing logical-framebuffer checks did not cover this boundary.
A same-loader experiment with HP's original DCD is prepared next; the pinned
rollback loader and installed NAND remain unchanged.

### DDR correction confirmed by the physical menu control

ROM applied the original HP DCD before loading the unchanged research5 image.
MDCTL and MDASP were read back both before and after U-Boot startup, confirming
`85180000` and `0000005f`. The complete HP upload was independently read back
again. The user then selected HP in the menu and confirmed a clear display and
`12+3=15`. With both executable images unchanged, changing the preceding DDR
setup resolved the physical handoff failure. The user subsequently confirmed
that Shift+On turned HP off for the saved-history check. Evidence:
`restore-tools/hp-ddr-research-launch.jsonl` and
`restore-tools/stock-1790409855582406000/hp-ddr-menu-launch.json`.

Research6 makes the nine DDR configuration differences durable in the isolated
U-Boot preparation, retaining the original startup write order. It also refuses
HP startup before stopping the menu display unless the expected MDCTL/MDASP
values are present. It never changes live DDR while executing from DDR. Normal
Lefony boot-menu preparation is unchanged. Separate build source/output paths
preserve the exact research5 rollback assets and immutable trial review.

Candidate hashes:

- RAM U-Boot/DTB: `cb1be2cc34bc08b3533be98d6818ad48db2a15715ddb09ed0cd8c8971f0f2005`.
- ROM IMX: `638a301a2a257d1d958bc53ced8cbf45ca1e6926a83846efb2090309f34d020d`.

The retention probe accepts `--uboot` and `--ddr-image` to replay the paired
IMX's DCD through model MMIO before staging RAM images. It explicitly checks
that a valid HP image is rejected with the old CS0 boundary. DCD replay does
not model PHY timing or qualify electrical memory behavior. The initial run
failed because generic-loader staging preceded DDR initialization; staging
after DCD corrects that test ordering. Physical acceptance and rollback were
subsequently completed as recorded below.

Research6 subsequently passed the complete model save/cold-retention journey
with its paired DCD and incompatible-map rejection, plus the ordinary Lefony
menu/recovery regression (automatic startup, Enter, four arrows, touch, saved
priority, invalid-input rejection and recovery RESET). Evidence:
`research6-retention-staged/qualification.json` and
`restore-tools/research6-lefony-regression.log`. The physical research6 IMX
then passed complete ROM upload/readback and entered RAM SDP; the exact HP
image also passed complete RAM readback before opening the test menu. The user
confirmed that this corrected candidate boots HP and that the earlier saved
`12+3=15` remains in Home history. The save occurred through the research5/HP-DCD
control and was retained through a fresh research6 ROM/menu launch. No
experimental loader was installed in NAND. The already-authorized Lefony
restoration followed this successful HP test, as recorded below.

### Verified physical Lefony rollback

The user returned the calculator to genuine ROM SDP after the successful HP
retention check. The pinned research5 recovery image passed complete RAM
readback before entry. Both complete Lefony backups and all reviewed source
identities were revalidated. The live comparison found **672 changed blocks**,
including HP-written blocks 842–845 beyond the original 668-block stock trial.
All changed blocks had durable before-images and a complete pre-write recheck.
Each erase and program passed raw readback; the boot region was written last.

The final independent scan matched **all 4,096 physical raw block hashes** to
the original Lefony backup, preserving all eight factory-bad blocks. The restore
finished successfully in 65.93 minutes. Evidence:
`restore-tools/lefony-1790416469505809000/qualification.json` and `journal.jsonl`;
journal SHA-256:
`d23338cb0170935852d74c989d14cb57ba16aa03daec2ad6427c40a3f94a48bd`.
This covers both boot copies and the entire captured apps/data layout. It does
not qualify power-loss recovery or general flashing endurance. A single normal
reset was sent only after that complete verification, followed by the native
USB, recovery and user boot/menu checks below.

Native Lefony USB returned after the verified rollback and normal reset, with
capability flags 14 and bootloader version 1. The restored one-shot recovery
request then entered installed SDP; its entry bytes match the accepted Phase 1
image and its one-shot token was consumed. An initial host check wrongly expected
the native capability cookie during early SDP. Source inspection confirms that
this cookie is deliberately cleared until SDP exits; that check stopped before
sending a reset. A corrected read-only check used the bootloader entry and
consumed token instead, then sent a single normal reset. This was a host-check
assumption error, not a bootloader change or a NAND retry.

The corrected recovery check completed: native USB returned again with flags 14.
The device is now restored Lefony, with no USB writer active. The user then
confirmed: “lefony is back up and running now. boot menu also works perfectly”.
This closes Phase 3. Apps/data preservation is established by the complete raw
backup match; no separate application-by-application exercise is claimed.
The latest documentation/public-tree and whitespace checks passed.
