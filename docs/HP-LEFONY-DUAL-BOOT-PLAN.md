# HP Prime G2: HP OS and Lefony dual-boot implementation plan

Date: 2026-09-25; qualification updated 2026-09-26. Status: Phases 1–5 complete
within their recorded scope. Phase 3 includes physical HP menu boot, saved-history
retention and verified Lefony rollback with user-confirmed boot/menu operation.
Phase 4 qualifies an experimental RAM confinement profile in the emulator,
with unsupported factory-reset/update/reload paths explicitly rejected.
Phase 5 qualifies the shared layout, NAND ROM boot, logical HP migration,
interruption recovery and exact stock rollback in the emulator. See the
[Phase 5 record](HP-LEFONY-PHASE5-MIGRATION.md).

This plan itself authorizes no device operation. The separately authorized
Phase 3 trial booted unmodified HP V15751 through the corrected research6 RAM
menu on unchanged stock geometry, then restored Lefony and verified all 4,096
raw NAND blocks. The HP boundary patch has since passed emulator storage tests;
no boundary-patched HP image or shared layout has been tested on hardware.
The permanent Lefony menu still disables HP; installed dual-boot support awaits
physical migration and installer qualification.

## Recommended approach

First build the complete Lefony boot-manager interface on the existing Prime
G2 U-Boot port: startup screen, Enter-key entry, countdown, OS selection and
saved priority. Validate automatic and menu-selected Lefony boot plus recovery
before beginning HP integration. Then prove HP startup and filesystem
confinement before changing NAND layout or building the website flow.
Initially preserve the original HP executable and apply a version-specific
filesystem-boundary patch to its RAM copy on every HP boot. Use a recovery
installer for backups, filesystem migration, provisioning and verification.

The intended product offers two explicit installation choices:

- **Keep HP OS and install Lefony:** migrate HP data to a smaller filesystem,
  install Lefony in a separate region, and show a short startup screen before
  automatically booting the user's priority OS unless they open the boot menu.
- **Replace HP OS with Lefony:** install the Lefony-only layout after explaining
  that HP OS and its data will be removed. Reuse the boot-manager implementation,
  with a single installed OS and an accessible recovery path.

The website can recommend the first choice when it detects a supported HP
installation. Detection must never initiate a patch, erase or migration.

### User boot flow

In dual-boot mode, every normal cold startup or reboot shows a startup screen
with the saved priority OS and a progress bar representing the three-second
boot delay. There is no standalone wordmark or numeric countdown. Keep the
warm white background and green accents. For example:

> Starting Lefony OS
> [Progress bar]
> Press Enter for boot options.

Pressing the physical **Enter** key during the countdown cancels automatic boot
and opens a menu with **Lefony OS** and **HP OS**. Holding Enter as the calculator
starts also opens the menu. Once opened, the menu waits for the user to select
an OS. If the user does nothing during the startup countdown, the boot manager
starts the saved priority OS. Only the physical Enter key opens the boot menu;
other keys and touch input do not interrupt the countdown.

The installer asks which OS should have priority. The boot menu provides an
explicit **Set as priority OS** action to change that saved choice later.
Selecting an OS for one boot leaves the priority unchanged. Store the priority
in versioned, redundant boot-manager metadata outside both OS filesystems;
ordinary boots only read it. An interrupted preference save must retain a
valid previous choice or show the menu if neither copy is valid.

Start the countdown only after the prompt is visible and keypad scanning is
ready. An Enter press recognized on the final scan before automatic boot takes
precedence over timeout. Consume the opening press and wait for its release
before accepting menu actions so a held key cannot accidentally select an OS.
Three seconds is the initial proposed duration to qualify on physical hardware.

To use the other OS, the user reboots, opens the boot menu with Enter, and selects
it. Only one OS runs at a time. If the priority preference is missing or invalid,
show the menu. If its image fails validation, stop automatic boot and offer only
verified compatible choices or recovery; never launch an unpatched HP image.

On the dual-boot build, manual **Shift + On (Off)** saves through the current
OS's normal path and turns the screen off. The next **On** shows the normal
startup progress bar and **Press Enter for boot options** prompt, without
requiring rear RESET. Enter opens the OS menu; otherwise the saved priority OS
boots after the delay. A one-use retained request returns through the NAND
bootloader; it does not change saved priority. Rear RESET uses the same flow.
Lefony's automatic idle suspend remains distinct from this manual Off action.
Explicit recovery requests and invalid-image/layout failures retain their
dedicated recovery paths. Lefony-only installations boot Lefony directly.

In this plan, an HP or Lefony "handoff" means the boot manager starting the
selected OS during boot. Persistence checks concern saved data surviving
reboots and subsequent boots of either OS.

### Does this replace U-Boot?

For an existing Lefony device, the finished boot-manager image would replace
the installed U-Boot images through a qualified, explicit bootloader update.
It remains U-Boot with Prime-specific boot policy, display/input and loaders;
it is not a new bootloader written from scratch. A stock HP device is a different
migration: install our boot path while preserving the HP components it needs.
The processor's immutable Boot ROM remains unchanged.

Use one codebase with separately validated installation profiles, not a
different bootloader for every combination. Do not require rewriting U-Boot
for ordinary OS updates. Keep boot-manager updates independently versioned.

Start from the currently pinned Prime port and preserve its recovery behavior.
An upgrade to a newer upstream U-Boot is a separate workstream after the HP
handoff works. Combining a board-port upgrade, storage migration and dual boot
would make failures much harder to diagnose. This is a prototype baseline,
not a decision to retain an old upstream indefinitely; assess maintenance and
security requirements before public release.

## Evidence and open questions

### HP filesystem boundaries identified in V15751

The locally analyzed `HPPrime_OS.img` identifies build V15751. Its container
SHA-256 is `80ba573472b3731bdbb0165bf13390579863ca1d3f5c003dfb21c17dd4871461`.
The extracted main OS payload SHA-256 is
`25d3d2d27e45fc3ce7dc8c4a111b31f8aefc14c4b21e8d8ee4b32251e31c1b82`.
The extracted updater payload SHA-256 is
`9bfe04ec74eed51b606001caa3e5c0f701acd70eeb7d622f5a25616efdc0436e`.
These identify research inputs, not qualified release artifacts.

On 512 MiB NAND with 128 KiB erase blocks:

| Stock region | Inclusive blocks | Byte range, end exclusive |
| --- | --- | --- |
| HP system area | 0–383 | 0–48 MiB |
| Reserved area | 384–391 | 48–49 MiB |
| HP YAFFS filesystem | 392–4095 | 49–512 MiB |

The observed initialization computes start as `ceil(48 MiB / block_bytes) + 8`
and end as `total_blocks - 1`. Static tracing identified the following writes:

| Component | Start-field store | End-field store |
| --- | --- | --- |
| Main OS | `0x802B1ACA` | `0x802B1AD0` |
| Separate updater | `0x80007CF0` | `0x80007CFE` |

These are loaded-code addresses for this exact build, not NAND addresses or
portable patch offsets. The main OS initializes YAFFS parameter fields at
device offsets `0x14` and `0x18`, then copies them to internal bounds at
`0xF4` and `0xF8`. The identified YAFFS format loop uses those internal bounds.
The end-setting instruction sequence is a verified candidate patch point.
[Phase 2](HP-LEFONY-PHASE2-COMPATIBILITY.md) independently reproduced these
stores, internal copies and format-loop bounds using the original instructions.
This is not yet an implemented or approved RAM patch.

This does not establish that all HP writes obey YAFFS. The separate updater,
raw NAND diagnostics, resets, bad-block-table maintenance and alternate boot
paths require their own analysis. Software bounds are not hardware isolation.

### Existing project constraints

- Current U-Boot is the Prime port at revision
  `83c84d5e5b7a72855f4455c499b23ee6ead4f74d`, with one-shot SDP recovery.
- Current Lefony firmware at 4–12 MiB and DTB at 12–13 MiB occupy addresses
  inside HP's system region. They cannot be installed there unchanged while
  claiming to preserve HP. Existing boot-stream offsets also require an
  explicit collision audit against HP's actual boot structures and images.
- Lefony app storage occupies 432–496 MiB, inside stock HP's YAFFS range.
  Its startup provisioning policy does not establish HP coexistence. It accepts
  erased/UBI layouts and rejects unknown contents; do not weaken that rejection
  to accept HP YAFFS as disposable storage.
- Existing A/B support means Lefony version rollback, not HP/Lefony selection.
  Physical A/B migration remains disabled in the checked layout contract.
- Some legacy documents call captured storage UBI. That description must not
  be reused as the stock V15751 YAFFS format or as proof of compatible ECC.
- Stock HP emulator work has unresolved authentic startup/handoff state.
  Booting a research image with exploratory shims is not acceptance evidence
  for the real dual-boot path.
- Website code is maintained in a sibling repository. Its current transport,
  provisioning worker and tests need inspection during implementation; this
  plan does not claim a website code audit.

## Architecture and responsibilities

| Component | Responsibility |
| --- | --- |
| Website / desktop installer | Identify device state, show choices and space, save backups, request recovery, display the migration plan and progress, reconnect and verify |
| RAM recovery environment | Probe actual geometry, read/write NAND using the correct ECC, migrate data, stage images, verify readback, maintain a recoverable transaction |
| U-Boot boot manager | At startup/reboot, validate layout, show the countdown and Enter shortcut, boot the saved priority OS on timeout or the user's menu selection, validate the image and apply an approved HP RAM patch when booting HP, provide recovery |
| Lefony firmware | Use only its declared regions, report layout/capabilities, preserve HP regions during startup and updates |
| HP compatibility profile | Bind supported input hashes to narrowly scoped patch rules, handoff requirements and supported maintenance paths |

Keep full backup and migration logic in recovery. Adding it to the boot menu
would increase the amount of code that must work before either OS can start.

### HP patch strategy

Preserve an exact original HP image in protected storage or an explicitly
defined image slot. At each HP launch, validate it, load it into RAM, validate
the expected instructions, apply the approved change to the RAM copy, perform
required cache maintenance, and enter the researched HP startup path.

Do not simply prepopulate the YAFFS structure: HP initialization overwrites it.
Do not assume jumping to the image's entry point reproduces HP's full boot
chain, memory state, interrupt state, peripherals or updater transitions.

Each compatibility profile must bind the complete image hash, image/component
type, geometry, patch locations and expected bytes, allowed replacement policy,
layout version and handoff version. Authenticate the profile with the project's
existing release trust chain. Reject unknown images, partial matches and
unexpected bytes; never use an unrestricted search-and-replace patch.

If HP reloads an updater from NAND, an OS-only RAM patch does not cover that
updater. Trace and mediate every such transition, including direct maintenance
boot keys and reset paths. Verify original packages using the appropriate
existing authenticity checks before any RAM transformation. A patched RAM
image is not an HP-signed update package, and the official updater must not be
assumed to accept a modified container. Do not disable signature validation.

After migration, never fall back to unpatched HP: it would see the entire NAND
again. A profile mismatch must lead to a qualified compatible OS or recovery.

### Storage design

Keep HP's filesystem start at block 392 if the boot-chain investigation permits;
reduce its end rather than relocating every HP logical block. Put Lefony's
payloads, storage, metadata and rescue capacity in the excluded upper region.
Choose one fixed split for the first supported release. Defer resizing sliders.

For capacity evaluation only, a split at 256 MiB would leave HP blocks
392–2047 (207 MiB raw filesystem space) and an upper 256 MiB region for Lefony.
This is not a selected or installable layout. Actual usable space is smaller
after bad blocks, filesystem overhead, image slots, rescue and update reserves.

Before freezing offsets, produce a complete block map covering boot control,
all boot-image copies, HP code/updater assets, both filesystems, Lefony slots,
metadata, bad-block tables and rescue. Audit whether preserving or relocating
HP system components is compatible with every HP loader. Reserve enough good
blocks for the actual image sizes and a failed block during an update.

Use a versioned layout contract shared by bootloader, firmware, recovery and
host tools. Validate ranges and non-overlap on-device as well as on the host.
Do not silently reinterpret `nand_layout.json`, `app_layout.json` or existing
boot-manifest fields. Retain distinct legacy, dual-boot and Lefony-only profiles.
Map ECC/OOB handling per region; do not apply one historical geometry setting
to HP YAFFS, Lefony storage and ROM boot structures indiscriminately.

Dual-boot Lefony must refuse storage initialization without a committed,
recognized dual-boot layout. Legacy firmware/updaters that assume the old
offsets must be rejected on this layout, including otherwise valid signed
downgrades. A signature alone does not establish layout compatibility.

## Website installation experience

1. User chooses **Connect calculator** and grants the browser device access.
   Detect G2 and classify running HP, running Lefony, boot-manager recovery,
   ROM recovery, or unknown. USB identifiers are a hint; use supported queries
   and recovery probes to establish version, capabilities and actual layout.
2. For supported HP, offer **Keep HP OS + install Lefony** and **Replace HP OS**.
   Show the resulting usable capacity and data implications before proceeding.
   Unknown HP builds keep dual boot unavailable with a clear compatibility
   explanation. Do not silently select destructive replacement instead.
3. Save and verify a recovery backup outside the calculator. Show its location
   and restore instructions. Browser memory or an unfinished download does not
   count as a retained backup. Support a desktop route where browser storage,
   USB APIs or reconnection permissions are insufficient.
4. Enter the qualified RAM recovery route. Stock HP maintenance mode is not
   proof that an unsigned recovery payload can run. Initially allow a guided
   physical ROM-recovery entry; offer automatic entry only after it is proven.
5. Recovery completes preflight. Present a concrete summary of supported HP
   build, data restoration, partition sizes, backup verification and the selected
   installation mode. For dual boot, ask which OS should boot automatically
   after the countdown and include that priority in the summary. The user
   starts that reviewed operation explicitly.
6. Run migration with durable progress and readback verification. A disconnect
   or missing acknowledgement means inspect transaction state, not blindly
   repeat an erase/write or declare success.
7. Reconnect, verify the committed layout and boot-manager version, and verify
   the installed OS. For dual-boot acceptance, verify automatic boot of the
   priority OS, then guide a reboot, Enter entry and selection of the other OS.

Existing Lefony installations get an explicit migration path; they cannot be
assumed to retain recoverable HP firmware or data. Restoring HP there requires
the user's retained backup or suitable official inputs and its own validation.
ROM-recovery mode alone does not mean NAND is blank. Existing dual-boot devices
receive layout-compatible updates, not a repeated first-install migration.

Replacing HP does not require erasing every physical NAND block. Preserve
factory bad-block information and required recovery structures. Treat it as a
separate, qualified storage profile with the same backup/readback discipline.

## Migration transaction and recovery

Do not implement the sequence as “patch HP, then start installing Lefony.”
All supported boot paths and a verified recovery route must be ready before
shrinking HP or giving its former blocks to Lefony.

| Stage | Required result before advancing | Interruption behavior |
| --- | --- | --- |
| Inspect | Model, geometry, firmware hashes, data size and layout identified | No persistent changes |
| Back up | Matching complete reads; correct raw/OOB and boot-control captures; independently restorable user data | Original layout remains available |
| Prepare | Capacity, bad blocks, signed artifacts, patch profiles and recovery assets verified | No filesystem shrink |
| Establish recovery | A boot-control transition that reaches recovery or a compatible patched loader on every supported reset path | Re-enter recovery; do not start unpatched HP after shrink begins |
| Migrate | HP data recreated/restored inside the smaller filesystem; Lefony regions provisioned and images verified | Resume using durable journal and host backup |
| Commit | Redundant layout records and all boot paths point to verified compatible components | Torn records select a known valid state or recovery |
| Qualify | Both OS boots, data persistence and recovery independently checked | Report partial completion accurately |

The exact boot-control commit order is a Phase 5 design deliverable. “Write the
bootloader last” is not universally safe here: old HP could boot after a power
cut and overwrite newly assigned Lefony blocks. Conversely, overwriting the
only viable boot stream first is also unsafe. Prove the transition using the
actual ROM search order, redundant streams, FCB/DBBT behavior and NAND program
constraints; do not infer atomicity from having two copies.

Initially migrate through a verified logical backup and recreation of HP's
filesystem, not in-place shrinking. Copying old raw pages into a smaller range
does not remap YAFFS objects or checkpoints. Establish that backup/restore
covers settings, programs, apps, resources and other required user content.
Retain a full physical recovery backup independently of the logical backup.
If restoration cannot preserve an item, report it before the user commits.

Once HP data has moved, rollback may require recovery and host backup. Do not
promise that the old stock installation stays directly bootable throughout.
Reserve explicit transaction metadata and record completion only after readback.
Do not store the sole recovery record in the filesystem being recreated.

## Implementation phases and exit criteria

### Phase 1 — Build the complete startup screen and boot menu

**Complete for the development milestone.** The corrected bootloader is installed
in NAND, both copies and boot metadata verified, and the user accepted the physical
menu after testing. See [qualification and limits](BOOT-MENU-PHASE1.md).

Implementation and qualification: [boot-menu candidate](BOOT-MENU-PHASE1.md).

This is the first implementation priority. Complete the boot-menu system and
validate it with Lefony before starting HP loader integration. Use the existing
Lefony image locations and recovery path for this milestone.

- Implement the finished on-device startup screen with the priority OS,
  three-second progress bar and **Press Enter for boot options** prompt. Start
  timing only once the display is visible and keypad scanning is ready.
- Only the physical Enter key opens the menu. Accept a press during the
  countdown or a key held at startup, cancel the timeout, and require release
  before accepting a subsequent action. Other keys and touch must not interrupt
  the countdown. Recognized Enter input takes precedence at the timeout boundary.
- Build the complete OS selection screen, all four arrow keys for navigation, Enter-to-confirm
  behavior, selected/disabled states and two large touch buttons using real
  Goodix input once the menu is open. Keep keyboard operation available if touch
  fails. The opened menu waits for a selection without another countdown.
- Include **Lefony OS** and **HP OS** entries. Boot the real Lefony image through
  both automatic and menu-selected paths. Clearly disable HP OS with an
  **Unavailable until HP integration is complete** explanation until its loader
  and compatibility checks are ready; it cannot be booted or set as priority.
- Implement **Set as priority OS**, persistence in versioned redundant metadata,
  one-time selections that leave priority unchanged, and invalid-preference or
  invalid-image handling. Test both priority values and interrupted saves with
  explicitly synthetic loader/storage fixtures; these do not establish HP boot.
  Prove cold-restart persistence on disposable emulator boot media. Physical
  metadata placement must be audited before any device write and incorporated
  into the final layout in Phase 5; do not borrow unknown NAND blocks.
- Validate recovery requests before the normal startup flow. Preserve the
  one-shot SDP endpoint, its timeout and the documented recovery shortcut.
- Preserve display/DMA/cache ownership and reset input state before starting
  Lefony. Reboot returns to the startup screen. Phase 7 adds manual Off/On entry
  through the same startup screen; automatic idle suspend retains normal resume behavior.
- Exercise the full dual-boot interface in a development configuration with
  Lefony as the available OS. Retain direct Lefony boot for the final Lefony-only
  installation profile. No HP filesystem shrink or dual-layout provisioning is
  required for this phase.

U-Boot's standard `bootmenu` is an ANSI-terminal menu, not a ready-made Prime
touch interface. The first milestone includes the actual board display, keypad
and touch integration, rather than stopping at a terminal-menu prototype.

Exit: the complete visible countdown, Enter-key menu, navigation, priority
settings and recovery behavior work in the boot manager. The actual Lefony
image boots automatically and through menu selection. Normal input tests cover
held/released Enter, ignored other keys/touch during countdown, timeout-boundary
input, menu touch/keypad selection, disabled HP, invalid preferences/images and
interrupted preference saves. Inspect captured frames and record emulator
results separately from explicitly authorized physical validation. HP startup
is the next integration workstream, not a prerequisite for this milestone.

### Phase 2 — Reproduce the evidence and define compatibility

**Research complete, with unresolved writers and handoff gates documented.**
See the [compatibility report](HP-LEFONY-PHASE2-COMPATIBILITY.md) for exact
inputs, reproducible tools, supported research paths and unsupported physical
paths. Both boundary calculations and metadata bypasses were reproduced.
Unmodified direct startup still stalls in NAND/interrupt handling; exhaustive
indirect-writer coverage and physical placement remain explicit later gates.

- Reproduce V15751 boundary tracing from the exact private input hashes.
- Trace main boot, cold/reset boot, maintenance entry, factory reset, diagnostic
  erase, HP update and bad-block metadata writes. Enumerate every writer.
- Establish HP's boot image placement, relocation assumptions and handoff state.
- Produce a private-fixture compatibility report and a public results summary.

Exit: verified patch locations plus a list of supported paths and unresolved
writers. No install UI or new physical layout is enabled.

### Phase 3 — Prove the HP handoff through RAM-loaded U-Boot

Complete: [RAM loader and qualification record](HP-LEFONY-PHASE3-HANDOFF.md).
Exact-image verification, HP menu boot, calculation, save and cold retention
pass in the model. The research6 DDR correction also passes physical HP boot
and saved-history retention. The approved stock trial and Lefony rollback each
passed full-device verification; rollback restored 672 changed blocks and matched
all 4,096 raw block hashes. Native USB, installed one-shot recovery and the user's
final Lefony boot/menu check pass. Apps/data bytes match the original backup.
The exit criteria are met for this recorded G2/V15751 trial; shared-layout dual
boot remains outside this milestone.

- Add the smallest HP loader experiment on the pinned board port.
- Start with an unmodified HP image and unchanged filesystem geometry.
- Resolve authentic handoff state; use existing research shims only to diagnose,
  never as a substitute for a working production handoff.
- Integrate the HP loader with the completed boot-menu system in an isolated
  HP test setup using unchanged HP geometry. Enable its entry only when the
  required image checks and handoff work; this does not establish coexistence
  with the current Lefony NAND layout.
- Confirm Lefony boot and one-shot SDP recovery still work.

Exit: repeatable HP startup through the intended loader with retained data,
first in the model where possible, then on an explicitly authorized test G2.
Prefer a backed-up dedicated calculator: HP itself can write during normal boot
even if U-Boot was loaded only into RAM. The user has only the current Lefony
calculator; testing it requires explicit approval of temporary stock restoration
and a verified Lefony rollback/recovery path. Do not run HP on its overlapping
current layout. If this fails, pause partition work.

### Phase 4 — Prove filesystem confinement

**Complete for the tested experimental profile.** See the
[implementation and qualification record](HP-LEFONY-PHASE4-CONFINEMENT.md).
The exact-hash V15751 RAM profile passes full-scan/checkpoint, allocation,
cold retention, deletion, capacity, reclamation, format and persistent bad-block
retirement tests with independent NAND traces. The native metadata exception
is limited to owned blocks/pages and verified callers. Both HP components have
instruction-level guard coverage. Factory-reset shortcuts, official updates
and maintenance reload are explicitly rejected; ordinary restart is retained.
The fresh welcome-screen touch gesture and updater frontend are not qualified.
No physical installation or final shared-layout qualification is claimed.

- Implement an exact-hash RAM patch profile for one HP build.
- Use disposable copy-on-write NAND fixtures with a recreated smaller YAFFS
  filesystem and protected data beyond its boundary.
- Trace every NAND program/erase, including DMA paths. Attribute filesystem,
  system-image and bad-block-table writes to their declared allowed regions.
- Exercise full scan without a checkpoint, checkpoint restore/save, allocation,
  deletion, near-full storage, garbage collection, format and reset paths.
- Address the updater's separate configuration and every alternate entry path.

Exit: both functional checks and NAND traces prove the intended boundaries for
the tested paths; unsupported alternate routes are positively rejected by the
profile. Emulator observers detect violations without blocking them, so they
cannot mask HP behavior or create a false impression of hardware isolation.

### Phase 5 — Freeze the layout and implement recovery migration

Implementation and qualification: [shared-layout migration](HP-LEFONY-PHASE5-MIGRATION.md).
The stock-source offline executor and actual NAND ROM/menu loaders are implemented.
**Complete for the recorded stock-source emulator milestone.** Both OS loaders,
80 restored HP file hashes, both priorities, legacy-writer/metadata rejection,
116,236 modeled interruption cases and exact full-stock rollback pass. The host
suite passes 2,112 tests with two private-reference skips. Physical migration
remains disabled; Phase 6 adds the installer workflow and its qualification.

- Finalize the block map and versioned contracts after measuring required space.
- Adapt Lefony image loading, app storage and update writers to the new layout.
- Implement backups, logical restore, migration journal and interrupted-install
  recovery. Integrate boot-manager installation as part of that state machine.
- Prove layout rejection for legacy installers, older firmware and bad metadata.
- Connect the completed menu and priority settings to the committed dual-boot
  layout. Verify both priority choices, both real OS loaders, reboot selection
  in both directions and cold persistence of the saved priority.
- Qualify HP update mediation or positively block unsupported update entry
  paths. A warning alone is insufficient if those paths can overwrite Lefony.

Exit: emulator fault injection at every persistent transition yields a verified
bootable state or documented recovery. Restore to stock HP is demonstrated on
disposable fixtures. Physical migration remains gated on device qualification.

### Phase 6 — Integrate the website and desktop installer

Status: **complete for the tested existing-Lefony source with a same-board HP
V15751 backup**; see [implementation and qualification](HP-LEFONY-PHASE6-INSTALLER.md).
The retained install, exact original-system restore, repaired NAND startup and
separate OS confirmations passed. Public installation remains disabled pending
Phase 7; this does not qualify other source profiles or every Prime G2.

- Inspect the website repository and extend its existing transport/provisioning
  worker using shared capability and layout contracts.
- Implement the state-specific flow above, including explicit mode selection,
  retained backups, reconnect/resume and clear completion verification.
- Exercise browser permission cancellation, insufficient disk space, stale
  releases, wrong model, unsupported HP build and USB disconnection.
- Keep an initially limited compatibility list; never infer support from a
  version string or a matching instruction fragment alone.

Exit: automated browser/host tests plus an authorized complete physical install
and restore. Existing Lefony-only installation must also pass regression checks.

### Phase 7 — Qualify and release

Release scope update: the user accepted the installed behavior and requested
publication as a browser-only development release. Remaining battery and real
power-loss matrix items are documented limitations, not claimed completed.
See [release scope and browser workflow](DUAL-BOOT-BROWSER-RELEASE.md). The
original broader qualification targets below remain useful follow-up work.

Status: **in progress**; see the [candidate, physical matrix and automated
qualification record](HP-LEFONY-PHASE7-QUALIFICATION.md). The repaired installed
snapshot passes the expanded ROM and interruption checks. Public release remains
gated on the remaining physical matrix and update/recovery qualification.
The user has accepted the installed manual Off / On startup progress bar and
Enter shortcut. This completes that requested behavior on the tested calculator;
the broader Phase 7 release criteria below remain open.

Use dedicated backed-up hardware to test cold power-on, rear reset, watchdog,
battery/USB changes, sleep/wake, both OS persistence, recovery, bad blocks,
interrupted OS/bootloader updates, install interruption and stock restoration.
Verify both reboot sequences: HP OS → startup screen → Enter → Lefony OS and
Lefony OS → startup screen → Enter → HP OS. Also verify unattended countdown
boot for each priority OS and that a one-time selection leaves priority intact.
Verify manual Shift+On → On → startup screen → Enter → menu from both OSes,
including HP's full-power-off and warm-suspend paths, unattended priority boot,
and that the request is consumed once. Qualify the
new bootloader and Lefony together through a retained, layout-compatible update.
Check saved data after returning to each OS through a reboot. Lefony calculation
history is intentionally volatile; use persistent apps/app data for its checks.
Record candidate hashes, exact board/build, commands, write traces and results.
Do not generalize one board's bad-block map or emulator result to every G2.

Publish source changes and compatibility metadata only; keep vendor firmware,
NAND captures, user backups and signing keys private. Supply HP images from
user-owned/official inputs rather than bundling them in Lefony releases.
The public dual-boot option remains unavailable until the supported HP build,
all reachable write paths and the migration/restore procedure are qualified.

## Updates and first-release scope

Lefony updates target only their declared slots and retain existing signature,
model, version and readback requirements. Do not enable the old physical A/B
migration by implication; any A/B scheme in the dual layout needs its own tests.

HP updates must pass a compatibility check before any destructive operation.
Do not install a new HP build until its image, updater and reset paths have a
qualified profile. Trace whether stock Connectivity Kit or HP can bypass the
boot manager; mediate or block those routes before claiming update-safe dual
boot. A later unknown HP image must fail into recovery, not run unrestricted.

The first release should support G2, one exact HP build, one fixed split,
a three-second startup screen with Enter entry and a saved priority OS,
explicit recovery entry if necessary, and backup/recreate/restore migration.
Defer arbitrary repartitioning, broad HP version support, seamless HP updates
and any promise of a zero-loss in-place shrink.

## Work locations and validation

| Area | Existing starting points |
| --- | --- |
| Boot-manager build | [build script](../scripts/build_prime_g2_oneshot_uboot.sh), [one-shot patch](../native/prime_g2/u-boot-lefony-oneshot-sdp.patch) |
| Layout contracts | [NAND layout](../native/prime_g2/nand_layout.json), [app layout](../native/prime_g2/app_layout.json) |
| Firmware | [Prime G2 drivers](../ports/lefony-prime-g2/ion/src/prime_g2/), especially app storage, NAND and USB/update code |
| Host installation | [installer](../scripts/lefony_installer.py), [recovery helper](../scripts/prime_g2_uboot_recovery.py) |
| HP fixtures | [stock preparation](../scripts/prepare_hp_prime_stock_fixture.py), [stock research](HP-STOCK-EMULATOR-RESEARCH.md) |
| Emulator | [peripheral model](../vm/qemu/prime_g2_peripherals.c), stock HP runners and NAND instrumentation under `vm/` |

Make durable U-Boot changes in checked-in patches or preparation scripts;
`build/lefony-uboot-oneshot-src` is regenerated. Do not edit it as the sole
implementation. New layout/profile files need explicit schema versions.

For implementation work, run the relevant host tests, `make check-public`,
both `make firmware` and `make firmware-vm`, the affected compiled U-Boot tests,
and `./vm/test-native-comprehensive.sh smoke`. Add behavioral confinement and
interruption tests rather than merely checking that a constant changed. HP
fixture tests remain optional/private and outside default public CI. Browser
checks run separately in the website repository.

The full graphical boot menu is the first implementation priority. Authentic
HP handoff, alternate writers and recoverable migration remain the largest
uncertainties for dual boot. Estimate the complete dual-boot release after
Phases 3 and 4; completing the menu does not resolve those storage and HP risks.

**First implementation milestone:** the complete three-second startup screen with a progress bar,
Enter-key boot menu, OS selection and priority settings, with verified automatic
and menu-selected Lefony boot and preserved recovery. HP remains visibly
unavailable until its integration is ready. Follow this with HP evidence
reproduction, authentic HP startup and instrumented filesystem-confinement
experiments before physical repartitioning or production website integration.

## References

- [Current project status](STATUS.md),
  [qualified one-shot recovery](UBOOT-ONESHOT-RECOVERY.md),
  [current app filesystem](NATIVE-APP-STORAGE.md).
- [Bernard Parisse's G2 research](https://www-fourier.univ-grenoble-alpes.fr/~parisse/hpg2/readme.txt):
  independently describes the 48 MiB system area, eight reserved blocks and
  filesystem starting at block 392. It describes dual boot as future work;
  this is not evidence of a finished G2 HP/Lefony bootloader.
- [YAFFS Direct Interface](https://yaffs.net/documents/yaffs-direct-interface/):
  device configuration and embedded integration.
- [U-Boot bootmenu documentation](https://docs.u-boot.org/en/latest/usage/cmd/bootmenu.html):
  terminal-menu behavior. Current upstream documentation does not establish
  feature availability or working Prime drivers in the pinned 2018 port.

External references were consulted during the September 25 research. The
version-specific addresses above are local static-analysis findings, not claims
made by those references.
