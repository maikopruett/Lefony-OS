# Phase 6 installer integration — complete for the tested profile

**Phase 6 is complete for the tested existing-Lefony source with a same-board
HP V15751 backup. Public physical dual-boot installation remains disabled.**
The retained website/companion install, exact original-system restore and
legacy regression passed. The repaired NAND startup is now user-accepted, and
native USB independently reports dual-boot layout 5, release 1. The companion
records separate OS confirmations and links the repair without overwriting the
original install review or readback history.

The chronology below includes the earlier failed candidates and their evidence;
those failures were resolved by the USB boot-policy and NAND encoding corrections.
Phase 7 covers broader physical and public release qualification.

## Implemented workflow

- [Explicit legacy source profile](../scripts/prime_dual_legacy.py): accepts
  only the previously qualified Phase 1 boot streams and geometry, requires
  erased staging space and a separately verified same-board HP backup, and
  preserves all Lefony app blocks. It does not infer HP data from a Lefony OS
  installation. The narrow block-6 stock retirement record is distinguished
  from factory defects by its complete retained SHA-256.
- [Stable device capture](../scripts/prime_phase6_capture.py): compares two
  complete device fingerprints; reference bytes are reused only after a fresh
  device hash matches. Unknown blocks are read in full. Private output is
  atomically finalized only after both passes and the inventory agree.
- [Retained physical restore](../scripts/prime_phase6_restore.py): separately
  binds the current snapshot and target backup, restores ROM controls last,
  checks all blocks before journal retirement, and can resume an interrupted
  final cleanup without repeating completed writes.
- [Companion bridge](../scripts/prime_dual_service.py): local prepared bundles,
  explicit install/restore and priority selection, retained review, expiring
  single-use approval, durable status, exclusive execution, and explicit resume.
  The sibling website now exposes this through authenticated `/dual/*` routes.
  Browser requests contain bounded choices and opaque identifiers, never paths
  or firmware URLs. A closed browser cannot cancel an active NAND operation.
  Native boot confirmation also checks the reviewed signed release identity;
  HP startup and saved data require the user's separate confirmation.
- [RAM entry](../scripts/prime_phase6_recovery_entry.py) uses native Lefony's
  bounded handoff or the previously demonstrated hardware ROM route. It never
  forces physical straps or treats software recovery as immutable ROM.
- The RAM loader reports its remaining 90-minute recovery budget. Every erase
  refuses to begin with five minutes or less remaining. Initialization recovery
  without a valid journal is allowed only if every non-journal block still
  matches the source and no valid foreign transaction owns either journal.

The first source-to-dual transaction changed 264 blocks. Both boot streams,
all four FCB copies, recreated HP storage, signed images and final descriptors
passed per-block readback. Its final full-device SHA-256 is
`a951e0499cde74aed6aae08e1d82c1d5e520e4c28c8ffaa14d70daa5b1273d1c`,
identical to the offline result. This proves the intended bytes were written;
the subsequent black-screen result left that candidate unqualified until the
corrections recorded below. Evidence is under ignored `build/dual-boot-phase6/completion/`.

The legacy-source model boots both OSes in ARM QEMU and restores both the
original Lefony and stock HP images byte-for-byte. The new transport also
passes actual ARM adapter tests with a lost program acknowledgement, resume
without reprogramming, and exact restore. These results do not explain or
override that earlier physical boot failure.

The first direct ROM/RAM comparison verified the complete installed IMX in RAM.
ROM acknowledged the one-shot SNVS token write but readback remained zero;
the token-dependent launch stopped. A separately verified direct jump without
the token was then sent; the user confirmed it also stayed black. The dedicated
RAM-only recovery preparation now enters SDP without depending on this token;
the installed boot-manager policy is unchanged. That new recovery binary
passes the ARM transport/restore test and physical ROM entry, USB protocol and
visible recovery-screen checks. Full controller-decoded Lefony, DTB and HP
checksums match the intended images. A separate RAM diagnostic loader verifies
the signed layout and draws the menu; directly invoking its normal dual command
boots Lefony, confirmed by the user. No NAND writes were issued during these
diagnostics.

The startup reproduction powers USBPHY1 before U-Boot entry. The old image
prints `Boot from USB for mfgtools`, discards the board's boot policy, and fails
with `Bad Linux ARM zImage magic!`, leaving an invisible serial prompt. The
Prime-specific dual preparation now excludes both inherited manufacturing
overrides and uses bootdelay -2, so pending UART input cannot bypass the
Enter-only graphical menu. The corrected binary is
`f92ff494a691941d92c617179d292a1551dbd20b7fa4322a061fb9b7efaf7df8`
(IMX `98b04a90a31358ea1f5e61c3277a02f29994fdcfa168e96ac0c22463e38d8e44`).
The USB-powered ARM test boots both OSes, verifies the HP archive, retains both
priorities and rejects missing layouts/images. The dedicated diagnostic and
RAM handoff helpers are never NAND installation artifacts.

The retained companion restore has now completed on the physical calculator:
all 264 changed blocks were restored and the complete 4,096-block result matches
the original Lefony backup SHA-256
`e97885629d5c8801f58d51a4cd4de3f8ca3bc824d82fcbbd5431c317dccc6200`.
The restore transaction is
`0741025ce11e6c1cb2fc38e031eb40580dfcf931c3420f98909471c7e98cebd1`;
the user confirmed normal startup and working apps, and the companion verified
native Lefony identity before marking this restore session complete. The paired website displays the retained operation
and blocks the legacy installer while it remains unfinished. This bench test
is USB-powered with the battery disconnected; cable removal cuts calculator
power and is not a harmless USB reconnect.

The corrected candidate has now been installed through the paired website and
configured companion. Both fresh source fingerprints match the original backup.
Transaction `a1900725441ff6cc8190723afbad3dd6d0c14df569d64252f107dba0346619fd`
changed 264 blocks and passed the final 4,096-block comparison. Its NAND SHA-256
is `768cc74f0aa4d1d47bf4aabcc5f5207e382b9dd56e518dc588a15048aaf226c3`,
identical to the corrected offline migration. The browser was reloaded during
the active operation; exactly one installation request was sent and the
operation continued to verified completion. A reset was sent, but native USB
was not detected in the first 45 seconds. Screen and both-OS checks are pending;
the companion correctly remains at “Written and verified — check startup.”

Current regression checks: 2,195 OS host tests pass with two optional private
skips; 34 focused checks pass after final preparation/harness adjustments.
The corrected ARM NAND-ROM/USB-powered boot and HP archive checks, eight layout
rejection cases, and four RAM transport transactions pass. Website build/lint,
673 unit tests (one optional skip), and 11 targeted browser tests pass. The HTTP
test initially could not bind the live companion's port; its three cases passed
after the physical operation finished and the idle companion was stopped.
The public-tree check, exact website contract parity and whitespace checks pass.

## Implemented

- [Public contract](../native/prime_g2/installer_contract.json), exported by
  [this script](../scripts/export_prime_installer_contract.py), binds layout 5,
  its SHA-256, exact supported HP image bytes/hash, geometry and qualification.
  The matching website copy lives in `src/installer/dual-contract.json`.
- [Read-only firmware identity](../ports/lefony-prime-g2/ion/src/prime_g2/installer_info.h)
  over EP0. Both dual and legacy builds advertise capability bit 16 in the
  existing `0xc0/0x4e`, value 0 report. Value 4 returns the 64-byte report below.
  Dual firmware no longer advertises the legacy development NAND writer.
- The website recognizes shared layouts and suppresses its legacy updater.
  Malformed advertised identities fail closed. Recovery connections require an
  explicit Keep HP / Replace HP choice before preparing a new installation.
  Keep HP explains the qualification limit and never falls through to replacement.
  Existing recovery jobs remain inspectable after reload without a new choice
  or replaying a write. The desktop companion has the same explicit choice and
  rejects missing/unsupported modes before creating an approval.
- The OS desktop development installer and the website's Python adapter reject
  a shared layout before calling the legacy writer. Vendored installer sources
  in the website were not changed.
- [Retained desktop session](../scripts/prime_dual_installer.py): private review,
  five-minute single-use approval, free-space check, exclusive session lock,
  revalidation before execution, and restart using only the same transaction.
  Both initial priority records are encoded with the reviewed choice; that
  choice changes the transaction identity. Backup bytes, signed images, archive,
  reconstruction and bad-block inventory pass the existing Phase 5 checks.
  Verification is reported separately from boot confirmation.

The new native report describes the running firmware and its validated layout
handoff. It is **not** a substitute for inspecting NAND, retaining a full backup,
checking signatures, or establishing device identity after a disconnect. Old
firmware without bit 16 is `legacy-unreported`, not proof of a stock layout.

## Native report

All integers are little-endian 32-bit words. Unknown versions, geometry, flags,
layout hashes and contradictory handoff/release fields are rejected.

| Offset | Meaning |
| --- | --- |
| 0 | Magic `LFI6` (`0x3649464c`) |
| 4 | Protocol 1 |
| 8 | Prime G2 model `0x32475048` |
| 12 | Layout 0 for legacy firmware; 5 for the dual candidate |
| 16 | Bit 0: dual build; bit 1: validated boot-manager handoff |
| 20 | Handoff release, or zero without a valid handoff |
| 24 | 4,096 erase blocks |
| 28 | 131,072 data bytes per erase block |
| 32 | 32-byte layout SHA-256; all zero for legacy firmware |

A dual build without a valid handoff reports `recovery-required`. It still
refuses all legacy writers. Unsupported query values stall and a subsequent
valid query succeeds.

## Desktop emulator workflow

The CLI accepts local paths, never browser-supplied paths. Prepare a private
bundle JSON with exactly `backup`, `backup_sha256`, `candidate`, `uboot`,
`archive`, `recreated`, and `public_key`, using the qualified Phase 5 inputs.
The free-space floor is 2,499,805,184 additional bytes (four full raw NAND images
plus 272 MiB of workspace); it does not claim browser disk quota availability.
Source files are retained and revalidated, not copied into a release artifact.

```sh
.venv/bin/python scripts/prime_dual_installer.py review \
  --bundle build/private-bundle.json --session build/private-session \
  --mode keep-hp --priority hp
.venv/bin/python scripts/prime_dual_installer.py run \
  --session build/private-session --approval TOKEN_FROM_REVIEW --emulator
.venv/bin/python scripts/prime_dual_installer.py resume \
  --session build/private-session --emulator
```

The token is emitted only to the local caller. Its hash is stored in the review.
Do not publish the review, token, backup or bundle paths. A changed input or
priority requires a new review; an ambiguous execution retains its consumed
approval and reconnect state. A media-contract or readback failure instead
requires recovery and refuses an ordinary resume. `--emulator` is mandatory and cannot select a
hardware backend. The public test key remains confined to emulator fixtures.

Check the website contract before building the site:

```sh
.venv/bin/python scripts/export_prime_installer_contract.py \
  --check '../Lefony OS Website/src/installer/dual-contract.json'
```

## Private physical recovery work

[The Phase 6 RAM loader](../scripts/build_prime_phase6_recovery.sh) adds a
bounded digest of the fixed upload buffer. NAND hashing uses a different
buffer, so erase/readback checks cannot destroy staged bytes. Host transfers,
controller operations and recovery residency remain bounded; an ambiguous
acknowledgement stops without retrying the write. This is a RAM-loaded research
transport, not a replacement installed bootloader or an immutable ROM feature.

[PhysicalMedia](../scripts/prime_dual_physical.py) checks the loader protocol,
NAND geometry, factory inventory and every raw block against the external
backup before issuing a transaction-specific permit. The shared engine requires
that exact permit. Each block upload is verified before erase, each erase and
program is read back, and durable journal events precede mutation. Recovery
barriers hash every ROM route before each data change; cached decoding never
replaces those physical comparisons. A torn journal copy can fall back to its
valid peer, while transport errors and valid foreign journals stop execution.
Restore transactions use a separate initial snapshot and recovery backup.

[The retained hardware trial runner](../scripts/prime_phase6_install_trial.py)
revalidates signed inputs and the explicit source profile before opening USB.
It supports an authorized private stock-to-dual or pinned legacy-Lefony trial
and resumption of that same transaction. Final snapshots include fresh physical
hash checks for every planned and preserved block. NAND verification is
separate from boot confirmation. Unprofiled legacy sources are rejected; it
cannot be used as an implicit conversion or public installer. Initialization
with no surviving valid journal requires a full pristine-source check.

The executed [bounded journal trial](../scripts/prime_phase6_journal_trial.py)
verified the complete retained Lefony backup, encoded/wrote/read both journal
copies at blocks 258 and 259, restored both to their original erased bytes, then
verified the complete original fingerprint again. No OS, filesystem, ROM route
or installed bootloader block changed. Native USB returned after reset.
The backup fingerprint is
`e97885629d5c8801f58d51a4cd4de3f8ca3bc824d82fcbbd5431c317dccc6200`.
This tests the physical write/readback transport and journal encoding, not a
complete migration or power-loss recovery.

Commands used for the isolated loader and ARM transport checks:

```sh
./scripts/build_prime_phase6_recovery.sh
.venv/bin/python vm/test-prime-hp-raw-restore.py \
  --uboot build/lefony-phase6-recovery/u-boot-dtb.bin --phase6
PRIME_DUAL_SOURCE_DIR="$PWD/build/lefony-uboot-dual6-src" \
  PRIME_DUAL_OUTPUT_DIR="$PWD/build/lefony-uboot-dual6" \
  ./scripts/build_prime_dual_boot.sh
```

The last command used the existing private release identity; no signing key was
generated. It preserves the separate Phase 5 emulator-key artifacts. Private
images and physical evidence remain under ignored `build/dual-boot-phase6/physical/`.

| Artifact | SHA-256 |
| --- | --- |
| RAM recovery used for full physical conversion | `1d1d60d101e5eede6136ae146aac77287d223364600781d6d565334a139e7b76` |
| Dedicated RAM recovery without token dependence; ARM-tested | `e61e057a88b35a764ef7c4ed685d72eb82d8cc1ddbaf806371f828d2ca97e26f` |
| New signed-candidate U-Boot binary | `b0a69457d45228a2844e5c5c2d1a712381317dd7b29be9cebf8424211cefa52e` |
| New signed-candidate NAND IMX | `e1a18f22ae47af4d72b255303f5559a545df13ef9e6a13acdfc0447274e50358` |
| Physical-target dual NAND capsule | `00ea46c250f4ba50111c556778882777792ca6d3727b4fd07aea46d99fe7747a` |

The new candidate's 564-block migration passes the offline transaction model.
Actual ARM QEMU ROM tests boot both OSes, verify the complete HP archive through
HP APIs, retain both priority choices and one-time overrides, and reject missing
layout/OS images. Captured screens were inspected. Its rollback matches all
4,096 original stock blocks. These tests are emulator evidence; the subsequent
installed candidate's physical boot failed as recorded above.

The optional `--boot-candidate <private-nand> --boot-imx <matching-imx>` arguments
to `vm/test-prime-hp-raw-restore.py --phase6` also exercise the new physical
adapter through actual ARM NAND commands on a synthetic source. This passed
the complete-device preflight, both recovery streams and ROM-route barriers,
an injected lost acknowledgement after programming an image block, resume
without a second program, and an exact full-image restore. QTest supplies RAM
transfers for this emulator test; the separate physical journal trial exercises
the real USB transport. Neither models physical interrupted programming.

Final follow-up validation: `make test` passed 2,168 tests with two optional
private-reference skips. The focused physical-media, handoff and installer
checks passed 55 tests. `make check-public`, exact website contract parity,
documentation links and whitespace checks passed. No website deployment,
public qualification flag, signing identity or installed boot policy changed.

## Qualification and remaining work

Private evidence is retained under ignored `build/dual-boot-phase6/`; website
logs are under its ignored `.local/phase6/`. Firmware candidates use distinct
`dual6`/`phase6-legacy` artifact names, preserving the existing candidates.

The new host tests cover approval reuse/expiry (including expiry during
revalidation), insufficient space, concurrent sessions, changed inputs,
interrupted execution/resume, and protocol corruption. C++ tests exercise both
firmware configurations, valid handoffs and damaged handoffs. The ARM VM test
[reads the actual USB endpoint](../vm/test-prime-installer-info.py) for both
legacy and dual builds, including malformed request recovery.

A complete retained offline migration with HP priority passed all planned and
preserved-block checks. [The session ROM test](../vm/test-prime-installer-session.py)
then cold-booted HP, entered the menu for a one-time Lefony boot, and cold-booted
HP again without changing priority. Resuming the verified session produced zero
persistent NAND-model operations; restoring it matched all 4,096 original stock
blocks byte for byte. This uses the qualified Phase 5 signed
payloads; it does not imply the new Phase 6 firmware was installed or signed
for physical release.

Candidate native binary hashes (physical candidate subsequently installed):

| Build target | SHA-256 |
| --- | --- |
| Physical dual candidate | `5fd457b25dbae5596438ebec403543696650b6d7e1e6e4a782bc6386d7e7a28c` |
| ARM VM dual candidate | `fd098e1b47934394eebe6ca7636826773a16cee6f4c5e2b0847970f990042fdf` |
| ARM VM legacy regression | `e1e8a4ba4f1169414d8a0b26d3843d43901470a84b988b5bb4627df4b4dbc1f4` |

Validation commands include the two target builds using `LEFONY_DUAL_BOOT=1`,
`vm/test-prime-installer-info.py --elf <candidate.elf> --dual` (omit `--dual`
for the legacy regression), and `vm/test-prime-installer-session.py --session
<retained-session> --uboot <matching-u-boot-dtb.bin> --output <private-output>`.
The OS full host suite passed 2,141 tests with two private-reference skips; the
final session/contract checks passed 33 tests. The public-tree check and exact
website contract parity passed. The website passed `npm ci`, build, lint,
671 unit tests (one skip), six adapter
tests and the 83-test full browser suite. Desktop/mobile screenshots were
inspected. Initial concurrent test runs hit worker timeouts; serial tests passed.
A later installer UI refinement was checked again with the targeted browser
suite. No deployed website or public release changed.

The corrected loader's subsequent physical RAM preview passed full image
readback before each ROM jump. The user confirmed that selecting HP OS boots
HP and selecting Lefony OS boots Lefony. The running Lefony USB endpoint
independently reported `dual-boot`, layout 5, release 1 and the expected layout
digest. These checks validate the corrected menu handoffs and installed OS
payloads; they do not establish startup from the NAND bootloader. The separate
rear-RESET check faded to white; a subsequent fresh power-on stayed black.
Private evidence is retained in
`completion/fixed-review-hp-user-check.json` and
`completion/fixed-review-lefony-user-check.json` beneath the Phase 6 evidence
directory.

### Physical ROM marker correction

The failed boot's four FCBs, retained DBBT area and both complete boot streams
still matched the installed snapshot. The FCB's marker metadata offset at
`0xb0` is 34, matching HP's existing filesystem encoding. The fixture builder
and ROM model incorrectly restored that byte from metadata offset zero.
Inspection of the retained physical ROM confirms that it loads this FCB field
and uses the selected auxiliary byte to restore the payload bit range. Applied
to the old stream, this rule changes 433 bytes across 225 of its 228 pages.
This defect is independent of the generic USB manufacturing-command override.

The [layout codec](../vm/prime_gpmi_bch.py),
[ROM fixture builder](../vm/prepare-prime-dual-rom-fixture.py) and
[route verifier](../vm/prime_dual_migration.py) now honor the metadata index.
QEMU r87 reproduces the prior failure and boots repaired streams through both
OSes, retained HP file checks, priorities and missing-image rejection. Tests
include an independent bit-splice expectation, an old-encoding corruption
case and out-of-range metadata rejection. Earlier r86 ROM passes do not
qualify the bootstream byte placement.

The [private repair runner](../scripts/prime_phase6_boot_repair.py) accepts only
this exact defect in boot streams matching a completed install review. It
revalidates signed installed images, the full current snapshot, original
backup and factory inventory before using the existing guarded physical media
and journal engine. Its `repair-boot` transaction can only replace boot-stream
blocks, secondary copy first. Both filesystems, OS payloads, preferences and
FCBs stay unchanged; only the eight affected boot blocks and owned transaction
journals are writable. A fresh capture preserves changes made during the RAM
boot checks. The physical repair completed: eight boot blocks and the owned
journals were updated, followed by verification of all 4,096 blocks. Final
NAND SHA-256 is
`ac39009e87f34f6f3a54675fec5fa7d8d240769aa8abbec015aebd143aed07b2`.
The bootloader binary and IMX hashes are unchanged; this repairs their NAND
encoding. A normal reset was sent without a RAM loader upload. That first reset
returned to ROM SDP, with watchdog reset status and NAND/DMA clock gates still
disabled. After the requested recovery-pad release and rear RESET, the user
reported “perfect now everything works.” Native USB independently reports
`dual-boot`, layout 5, release 1, with layout digest
`56ec2952e4bad8d3995dcb3b6cb1468976b4f0756fc5abb599841e2172655234`.
This accepts startup from the repaired installed NAND. No further NAND write
or host RAM boot upload was needed for this check.
Evidence is private under `completion/nand-startup-analysis/`.

Validation for this correction: 52 focused codec/migration/media checks, 58
repair/transaction/transport checks and the explicit lost-acknowledgement repair
test passed. The full suite initially reported 2,203 passes and two skips, plus
two failures: a newly added test's old fixture had been collected before its
marker-preserving correction, and a revision assertion still expected r86.
Both failing tests pass in the final targeted rerun, for 2,205 passing tests
and two optional private-reference skips across the runs. QEMU r87 builds;
corrected dual ROM/archive/menu checks, the original Lefony ROM regression and
actual ARM guarded physical-adapter/restore checks pass. The public-source
boundary and whitespace checks pass. No firmware binary rebuild was needed:
the correction changes physical bootstream encoding and the qualification model.

### Phase 6 acceptance

The retained companion session is complete, with separate HP and Lefony
confirmations. Its original transaction/review/readback history is preserved;
a linked boot-repair record identifies the reviewed repair, full readback and
user acceptance. HP selection was explicitly user-confirmed with the same
loader launched from RAM before the encoding repair. The latest user report
accepts installed NAND startup, and the Lefony confirmation independently checks
the running native identity and signed release. An additional post-repair HP
calculation, cold-power cycle or data-edit journey is not claimed.

Private records include `completion/nand-startup-analysis/repaired-nand-user-check.json`
and `completion/nand-startup-analysis/companion-completion.json`. The active
local companion configuration now uses the corrected ROM fixture and current
source pins; the old installation bundle remains in its historical record.

The Phase 6 physical restore exit passed for this existing-Lefony source
profile: exact original NAND restoration, native USB confirmation and the
user's app/startup check. With the physical installation accepted, the automated
installer/browser checks and original-Lefony regression satisfy this profile's
Phase 6 exit. Full stock-HP restoration, broader source profiles, both-OS reboot
and persistence journeys, power transitions and interruption qualification
remain the separate Phase 7 matrix. This result does not qualify every G2 source
or enable the public dual-boot button.
