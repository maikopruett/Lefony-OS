# Phase 7: dual-boot qualification and release

Phase 7 is in progress. The tested calculator has the repaired dual bootloader
installed in NAND. Physical acceptance, emulator evidence and public release
readiness are tracked separately. Public dual-boot installation remains disabled.
No release, commit, website deployment or compatibility expansion is implied.

## Candidate and scope

The original source is the qualified Phase 1 Lefony installation, converted using
a retained same-board HP backup and the exact V15751 confinement profile. This
is one HP Prime G2, not a qualification of every G2 or arbitrary HP firmware.
The battery is disconnected; current physical observations use USB power.
Lefony calculation history is intentionally volatile, as confirmed by the user.
Lefony persistence checks concern saved apps and app data, not calculation history.

| Artifact | SHA-256 |
| --- | --- |
| Verified installed NAND snapshot, before Phase 7 user activity | `ac39009e87f34f6f3a54675fec5fa7d8d240769aa8abbec015aebd143aed07b2` |
| Installed U-Boot binary | `f92ff494a691941d92c617179d292a1551dbd20b7fa4322a061fb9b7efaf7df8` |
| Paired NAND IMX | `98b04a90a31358ea1f5e61c3277a02f29994fdcfa168e96ac0c22463e38d8e44` |
| Installed Lefony native binary | `5fd457b25dbae5596438ebec403543696650b6d7e1e6e4a782bc6386d7e7a28c` |
| HP V15751 image | `25d3d2d27e45fc3ce7dc8c4a111b31f8aefc14c4b21e8d8ee4b32251e31c1b82` |
| QEMU r87 used for these checks | `1dbb04dea25e7b722f8305af98986cc6bde295c29cd754dfd02f4fb2be334829` |

The Phase 6 baseline used layout 5, release 1 and layout digest
`56ec2952e4bad8d3995dcb3b6cb1468976b4f0756fc5abb599841e2172655234`
above. The installed wake-to-menu update below advances to release 2 without
changing layout or trust identity. Qualification status must not be edited inside
the signed layout merely to update this progress document.

## Physical matrix

| Check | Evidence / status |
| --- | --- |
| Installed NAND startup | Phase 6 user acceptance after recovery-pad release and rear RESET; native identity independently matched |
| Lefony → RESET → Enter → HP | Phase 7 user confirmed clear HP display and calculation `12+3=15` |
| HP Shift+On, then On, original installed candidate | User confirmed HP resume and retained calculation; superseded by the new wake-to-menu requirement below |
| HP → RESET → Enter → Lefony | Phase 7 user confirmed Lefony boots; missing volatile history explicitly accepted |
| Manual Off / On with corrected startup progress bar and Enter prompt | User reported “Everything works perfectly” after the NAND countdown correction; accepted for this calculator, without extending the separate power/recovery matrix |
| Both unattended priorities and one-time override | Unattended HP priority passed; one-time override and restored Lefony priority requested separately |
| Persistent Lefony apps/data after both OS boots | App opening requested; a separate saved app-data check remains |
| USB-only cold power-on | Remaining; disconnect only while idle, after saving HP data |
| Battery-powered and USB/battery transitions | Remaining; battery currently disconnected |
| Installed recovery entry/timeout and watchdog return | Remaining on this exact candidate |
| Physical interrupted install/update and bad-block handling | Not established by host fault injection; dedicated controlled trials remain |
| Exact original-Lefony restore | Phase 6 passed all 4,096 block comparisons plus user/native acceptance |
| Exact stock-HP restore from final shared layout | Older stock and modeled restore evidence exist; final-candidate physical round trip remains |

The current source snapshots and backups are retained privately. A future stock
restore trial must start from a fresh capture so Phase 7 user data is preserved.
No physical erase/program failure is induced merely to simulate a bad block.
Recovery-pad availability does not count as a tested recovery result.

## Automated checks on the installed snapshot

The actual ARM NAND-ROM suite now uses the fully verified repaired readback,
not the earlier staging fixture. Both OS loaders, saved HP and Lefony priorities,
one-time override, unchanged priority after override, and missing layout/image
rejection pass. Eight additional actual ARM checks pass: invalid signature,
layout, profile and CRC; conflicting transactions; newer recovery record;
single surviving layout copy; and old preference-format rejection.
The installed physical-target Lefony ELF also rejects legacy manifest, install
and development update entry points without NAND programs.

The [cross-OS retention test](../vm/test-prime-dual-retention.py) boots HP through
NAND ROM, enters `37+5` through ordinary GPIO keypad input, saves with Shift+On,
cold-boots Lefony once through the menu, and cold-boots unattended HP. The saved
history pixels match and display `42`; HP priority is unchanged. It uses one
copy-on-write NAND overlay and checks the input snapshot remains unchanged.
HP-save attempts and committed writes are traced separately from boot-menu
preference writes: all 37 attempted and committed HP save programs stayed in
filesystem blocks 397–398. Logical framebuffer comparison is not physical panel proof.

The [installed-profile fault runner](../vm/test-prime-dual-installed-faults.py)
revalidates the private signed bundle, derives the exact existing-Lefony install
and rollback plans, and optionally revalidates the retained boot-repair review.
It invokes the existing physical-codeword model for every persistent boundary.
All writes are in disposable host memory; it has no hardware connection.

| Transaction | Changed blocks | Erase/program/half-page/journal cuts | Initialization cuts |
| --- | ---: | ---: | ---: |
| Corrected existing-Lefony install | 264 | 49,893 | 10 |
| Final installed snapshot → original Lefony | 266 | 7,656 | 10 |
| Retained bootstream repair | 8 | 1,464 | 10 |

Restore cleanup adds four cuts. Replacing the old journal before restore and
repair adds four cuts each: **59,055 interruption points total**. Each trial
resumes the interrupted checked step and compares all touched blocks against
the uninterrupted baseline. This does not model electrical interrupted erase,
NAND wear, or prove that an incomplete transaction can boot an OS without its
retained host recovery plan. ARM boot and physical recovery are separate checks.

Eight focused public host tests pass, including repair qualification with a
valid foreign journal in the immutable source. The new retention harness first
selected the wrong menu row, then needed QEMU `-no-shutdown` to inspect NAND after
HP powered down; these failed harness runs are retained but excluded from passes.
Neither required a firmware change or calculator write.

Private commands, logs, screenshots and JSON results are under ignored
`build/dual-boot-phase7/`. No vendor assets, dumps, user captures or signing keys
belong in the public tree.

## Manual Off / On menu entry (original wake candidate)

The first wake candidate implemented manual Shift+On → screen off → next On
opening the OS selection menu directly in both OSes. The user confirmed both
paths work, then requested the normal progress bar and Enter shortcut instead.
The startup-page correction is recorded separately below. Saved priority is
unchanged. The original hashes above are the Phase 6 baseline; the evidence in
this section applies to the first wake candidate.

The native implementation uses a separate LFMW loader capability and the
one-use SNVS LPGPR token LFM1. It saves and suspends before waiting for On;
the next key release requests a NAND reset. USB idle permits manual Off while
active transfers remain protected. Shared charger IRQs do not qualify as On.
Legacy Lefony builds and Lefony automatic idle suspend retain their existing behavior.

The exact V15751 RAM patch profile `hp-v15751-wake-menu-v1` is separate from
the NAND confinement profile. It checks every expected instruction/cave before
any write, preserves HP's save path, sets the request before full power-off,
and resets after warm wake. Vendor images on disk and in NAND remain unchanged.
SNVS lock, pending boot-confirmation, PGD and bounded write failures fall back
to HP's existing behavior. Instruction tests cover those cases; hardware power
and USB/battery transitions still require physical acceptance.

[The private refresh transaction](../scripts/prime_dual_refresh.py) accepts only
a complete retained prior transaction and an authenticated committed source.
It preserves HP, apps and preferences; signs release 2 with the existing release
identity and updates Lefony/rescue plus boot streams. Enlarged ROM page counts
require an erased old tail and are written before secondary, then primary boot
replacement. Layout descriptors commit last. All 4,096 source blocks are checked
before authorization, and every changed block and the final device are verified.
This is a private research path, not a new public installer capability.

Current modeled update evidence: 48 changed blocks, 8,148 persistent-operation
cuts, 10 initialization cuts and four journal-retirement cuts, all passing.
Actual ARM ROM tests pass with the old primary and secondary images under the
enlarged page counts, and with the new secondary while primary is unavailable.
The final candidate passes both OS loads, priority/one-time selection and
missing-image/layout rejection. On QEMU r88, Lefony manual wake, HP warm suspend
and HP full power-off all reach the menu; HP history pixels remain unchanged
after selecting HP again. The request is consumed once, and an unrelated reset
returns to the priority countdown. Short (300 ms) and one-second Off presses
exercise HP's distinct paths. Cold On after HP's full power-off is represented
by QMP reset/continue; its physical PMIC behavior is not established by this test.
Physical installation is now complete as recorded below.

The first integrated HP warm-wake trial stopped in HP's original OCRAM routine,
polling MMDC MPDGCTRL0 bit 31 at PC `0x009045d2`, before the new wake hook.
QEMU r88 models nominal read-FIFO reset completion for initialized DDR, matching
[U-Boot's i.MX6 FIFO reset sequence](https://github.com/u-boot/u-boot/blob/v2018.03/arch/arm/mach-imx/mx6/ddr.c).
Other calibration bits remain shadows. This adds no physical firmware workaround
and makes no claim about PHY latency or electrical retention.

Both physical and emulator Lefony targets compile. The bootloader builds from
the same pinned Lefony U-Boot source. The focused update/recovery suite passes
127 tests, boot/menu/HP/native checks pass 57, model source checks pass 23, all
14 MMDC scenarios pass, and SNVS input plus generated HP instruction-table
checks pass. The public source-boundary check passes. Failed harness/model runs
are retained privately and excluded from passing evidence.

| Wake-to-menu artifact | SHA-256 |
| --- | --- |
| U-Boot binary | `9967106eca534fdd42333d5cafed005381ddef4330d3b6cd53d25d6d73df3bca` |
| Paired NAND IMX | `dc94a72ab5c53a85159f627f1832f48c19566d193c072db4e6ab046124ca5a93` |
| Lefony physical native binary | `ea237a52a433ed000eb637eee183cdeb9cf903ae159ead0f41a70a51b0dac437` |
| Lefony emulator native binary | `66d9569d8501a8e72ddef19dab9d8caa62eea5395d4a7b0a06504bdcdb8c7218` |
| Lefony/rescue capsule | `ef6a0b26fd309b664ad77e048e1d7caab66d32774fb8cdb757654654be21f515` |
| QEMU r88 | `2597c568c6d7ba409ff6694df710c73ea1e516cee4865e970d5ad1788e087ff7` |

### Physical NAND installation, September 27, 2026

The user explicitly requested installation while Lefony was running. The pinned
dedicated RAM recovery entered successfully over native USB. A fresh full NAND
capture passed two complete device fingerprints and retained 27 changed blocks
from recent user activity. The prepared 48-block plan matches the tested plan's
before-images and payloads; only the two layout record identities differ because
they bind the fresh capture. Existing priority was Lefony and remains unchanged.

The guarded refresh completed with per-block readback and a final comparison of
all 4,096 blocks. Both ROM bootloader copies, Lefony/rescue images and signed
release-2 descriptors are installed permanently in NAND. HP, apps, preferences,
factory bad-block markers and other non-target bytes match the fresh capture.
The transaction also owns its two dedicated journal blocks.

- Transaction: `c4667c02bf25895439671b713fb2b2bff1cd1c559bffef9f2e3102e761d1f7d0`.
- Verified NAND SHA-256: `5e37deb48d5c8294e4341c9166bfca1b0c88e32d17cc4c7ffb6dd382853453cd`.
- One ordinary reset was sent after verification. Native USB returned and
  independently reported committed layout 5, release 2, the unchanged layout
  digest, and legacy writes disabled.
- The user confirmed physical Shift+On → On menu entry from both OSes, then
  requested the startup-page correction below. Battery reconnection has not
  been confirmed.

The retained review, complete before/after snapshots, operation log and separate
native boot result remain private under `build/dual-boot-phase7/wake-menu/physical/`.
No disposable model fixture was flashed. Public installation remains disabled.

### Off / On startup-page correction, September 27, 2026

After confirming that manual Off / On reaches the menu from both OSes, the user
requested the ordinary startup page instead. The bootloader now consumes LFM1
without synthesizing Enter: a valid saved preference starts the existing
three-second progress bar and Enter prompt, then boots the priority OS unless
Enter opens the menu. Invalid preferences still open the menu. The OS wake
hooks, styling, duration and stored priority are unchanged.

The physical HP Prime G2 bootloader was rebuilt with the same pinned U-Boot via
`scripts/build_prime_dual_boot.sh`, using separate source/output directories
for this candidate. The BIN/IMX pair retains the same 230-page ROM stream length.

| Installed countdown artifact | SHA-256 |
| --- | --- |
| U-Boot binary | `b2eb3246db39b2214df4c8e222b9778c3a2c541f3f2416980c3c4b2c8d5f9ec3` |
| Paired NAND IMX | `89fc97004c5dc8c1605ae6cc103e8ae358e67a11770d4d6b28060cf651d7882d` |

The user explicitly authorized NAND installation without another backup or test
run. The guarded private installation reused the retained verified snapshot,
validated geometry, bad markers, signed source images and live protected blocks,
then replaced secondary blocks 248–251 before primary blocks 240–243. Each write
passed full block readback. A final 4,096-block fingerprint matched the live
pre-install fingerprint with only those eight boot blocks replaced. Current HP
data, apps and preferences were preserved, including changes since the retained
snapshot. OS images, layout descriptors and release 2 remain unchanged.

Operation: `7c0855b31719f030834c835dd20f496b64355cffe99e3b90883d3783e1ac6700`.
The host operation record, before/after fingerprints and installation result are
retained privately under `build/dual-boot-phase7/wake-menu/countdown/`. This is
a separate boot-copy operation; the preceding refresh review alone no longer
describes the current boot bytes. Existing on-device journals were preserved.
After verification, one ordinary NAND reset returned Lefony's native USB
interface with committed layout 5, release 2 and legacy writes disabled. The
separate `boot-result.json` records that observation.

No fresh NAND backup or automated tests were run for this correction. The wake
harness now expects the countdown followed by physical-model Enter input, but
has not been rerun. Earlier passes above refer to the direct-menu candidate.
After the NAND installation, the user reported “Everything works perfectly.”
This records acceptance of the corrected Off / On startup behavior on this
calculator. It does not establish the remaining battery, interruption, recovery
or stock-restoration checks, and does not change public release readiness.

## Reproduce the private checks

Use the repository virtualenv and ARM tools. The paths below are placeholders
for operator-owned files; each output directory must be new.

```sh
.venv/bin/python vm/test-prime-dual-boot.py \
  --fixture build/private/installed.raw --uboot build/private/u-boot-dtb.bin \
  --ddr-image build/private/u-boot-dtb.imx --rom --usb-powered-before-entry \
  --output build/private/phase7-rom
.venv/bin/python vm/test-prime-dual-retention.py \
  --fixture build/private/installed.raw --uboot build/private/u-boot-dtb.bin \
  --ddr-image build/private/u-boot-dtb.imx --output build/private/phase7-retention
.venv/bin/python vm/test-prime-dual-installed-faults.py \
  --bundle build/private/reviewed-bundle.json --installed build/private/installed.raw \
  --repair-review build/private/repair/review.json --output build/private/phase7-faults
.venv/bin/python -m pytest -q tests/test_prime_dual_fault_harness.py \
  tests/test_prime_phase6_boot_repair.py
```

Omit `--repair-review` if no encoding repair was performed. This option accepts
only the retained exact-defect repair; it is not a generic bootloader updater.
The fault runner also supports the existing stock-source bundle format, but this
run qualifies the recorded existing-Lefony source only.

For the new candidate, run `vm/test-prime-dual-wake.py` with the same `--fixture`,
`--uboot`, `--ddr-image` and a new `--output` directory. Repeat with
`--hp-first --long-off-press` for HP's full-off case. The default case exercises
Lefony with its idle USB screen visible. `--dismiss-usb` exercises its app screen.
`vm/test-prime-dual-refresh.py --review build/private/refresh --output
build/private/refresh-tests` revalidates a prepared retained review before fault
qualification. Use its fixtures with `vm/test-prime-dual-refresh-rom.py`; none
of these commands writes to a calculator.

## Release gates

Before enabling a public installation, finish the physical matrix, freeze the
supported source/build and recovery procedure, qualify or reject every reachable
HP update/reset path, and verify signed package contents and platform installer
journeys. Unsupported HP factory resets, maintenance reload and official updates
remain refused by the exact profile. Do not claim transparent HP updates.
The legacy Lefony update writers also remain blocked on layout 5; a supported
public shared-layout update workflow still needs integration and physical
qualification beyond the private retained refresh implemented here.

The existing contract's `physical_migration_allowed: false` stays in effect.
Distribution must contain source, compatible Lefony artifacts and metadata;
HP images must come from user-owned or official inputs. Publication remains a
separate action after the candidate and qualification evidence are ready.

## Browser development release preparation, September 27, 2026

The user accepted the installed behavior and explicitly requested publication,
website-installer verification and commit/push, choosing an entirely browser-only
installer. This narrows the first public release to a development release with
the remaining battery/real-power-loss items disclosed. It does not mark those
unperformed items passed. The earlier release gates describe broader stable
qualification; the [development scope](DUAL-BOOT-BROWSER-RELEASE.md) governs this
publication. The layout digest and research migration flag remain unchanged.

The browser performs direct WebUSB RAM recovery entry and bounded WebHID SDP,
full local NAND backup, HP logical migration, signed shared-layout updates and
mirrored-journal resume. It retains the signed release in the recovery folder,
so a newer website cannot replace an interrupted operation's inputs. The source
folder and HP firmware never leave the user's computer. The fixed public NAND
codec includes its source and license.

Generation 3 signs the same accepted Lefony capsule, DTB and rescue image; the
countdown bootloader also remains unchanged. Only the descriptor generation
advances from 2 to 3. The package is separate from automatic legacy firmware
releases and never contains HP firmware, full NAND or signing keys.

Validation completed before physical browser writes:

- Synthetic BCH-2/BCH-4 vectors and bit correction match the existing codec.
- All 100 logical HP objects, 80 file hashes, five reconstructed NAND blocks and
  four ROM control pages match the existing implementation on the retained
  private stock fixture.
- All 564 browser migration target blocks match the Python planner exactly.
- Actual ARM ROM boot of the browser-created fixture passes both OSes, saved
  priority, one-time override and missing-layout/image refusal (seven cases).
- The real ten-target refresh plan passes 96 erase/partial-program/lost-ACK
  interruptions through the browser executor. Synthetic journal tests also
  cover every interruption boundary and changed-device rejection.
- Signed-download corruption, local-folder cancellation, asset retention,
  forbidden transport bounds and poisoned-connection/no-retry checks pass.
- Desktop/mobile layout was inspected. The unrelated fullscreen test initially
  raced its transition during the full run, then passed its isolated rerun.
- The host suite's old wake-condition assertion was updated to include the
  physical power-button request; its regression rerun passes. New packaging
  tests verify the exact public allowlist and refuse mismatched paired images.
- Website unit checks initially hit a five-second timeout in an existing
  subprocess worker test under load. Both tail-size cases pass on focused rerun.
- Production website build, lint, Worker dry-run and public-source boundary pass.

Local evidence remains under ignored `build/dual-boot-release/` in the OS tree
and `.local/dual-boot-release/` in the website tree. No private fixture is included
in the public source archive or the default tests.

### Physical browser transaction

The production browser build ran in desktop Chrome against the connected Prime
G2, using real WebUSB/WebHID and the ordinary permission/folder dialogs. No
companion, UUU, host NAND writer or mocked device was used for this installation.
The browser entered RAM recovery from running Lefony, saved and reopened the
full raw backup, and matched live hashes before and after capture. An independent
Python decode of that browser backup also matched both accepted boot routes,
both Lefony image copies and the DTB.

The reviewed generation-3 update changed only layout blocks 256 and 257, plus
its mirrored journals at 258/259. Every target passed erase/program readback.
All 4,096 final block hashes passed, preserving boot bytes, HP storage, Lefony
apps and saved priority. The browser recorded verified completion and issued an
ordinary NAND restart. This is a physical shared-layout update test; a fresh
stock-to-dual browser migration is supported by the separate planner/ROM checks,
not claimed as a second physical installation on this calculator.

Transaction: `9fa068075cd91cace4ea4101af2e51ab109d3975068ff254d31292e1ff7ea5a0`.
Signed generation-3 descriptor SHA-256: `4ea64f8545cd112185cf5d17a1fc4e7083b3935d61545d9512bb70103d400b6a`.
The local recovery folder retains the signed release, original raw NAND, full
fingerprint, targets and operation result.

The accepted countdown candidate also passes fresh actual-ARM wake regressions:
Lefony app-screen Off/On, HP warm suspend/On, HP full-off with modeled cold
power-on, saved HP history and one-use wake requests. Model cold power-on uses
QMP reset/cont while retaining SNVS and does not qualify electrical battery or
PMIC behavior.
