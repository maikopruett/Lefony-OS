# Phase 5: shared layout and recovery migration

Date: 2026-09-26. **Phase 5 complete for the recorded stock-source emulator
milestone.** This milestone concerns the offline migration executor and emulator. Physical migration remains disabled in the
layout contract. No calculator was read, flashed, erased or reset in this phase.
The installed Lefony-only bootloader is unchanged.

## Layout and firmware contracts

The separate [layout 5 contract](../native/prime_g2/dual_boot_layout.json) freezes
this candidate's map. It does not reinterpret the existing Lefony-only/A/B layout.
Canonical layout SHA-256:
`56ec2952e4bad8d3995dcb3b6cb1468976b4f0756fc5abb599841e2172655234`.

All boundaries below are 128 KiB eraseblocks on the 512 MiB Prime G2 NAND.

| Blocks (inclusive) | Owner and purpose |
| --- | --- |
| 0–3 | ROM FCB copies |
| 4–7 | HP bad-block metadata, preserved |
| 8–239 | Preserved HP system area |
| 240–247 / 248–255 | Redundant recovery/menu boot streams |
| 256 / 257 | Signed shared-layout records |
| 258 / 259 | Restart journal, outside both filesystems |
| 260 / 261 | Versioned, redundant OS priority |
| 262–391 | Reserved/preserved system space |
| 392–2047 | Recreated HP YAFFS filesystem: 207 MiB before bad blocks/overhead |
| 2048–2127 | Exact supported HP image: 10 MiB slot |
| 2128–2207 | Lefony image: 10 MiB slot |
| 2208–2215 | Device tree: 1 MiB slot |
| 2216–2295 | Signed reserved rescue payload: 10 MiB slot |
| 2296–3455 | Reserved upper space, preserved |
| 3456–3967 | Existing 64 MiB Lefony app-region addresses |
| 3968–4095 | Preserved tail, including recognized flash-BBT copies |

Boot streams retain HP's BCH4 format and DDR setup. Shared records and Lefony
images use Lefony's BCH2 format. HP YAFFS retains its BCH4 tags/header format.
Payload placement skips factory-bad blocks and reserves at least one good spare
block in each image slot. Occupied stock staging blocks, inadequate capacity,
wrong geometry, unexpected markers and incompatible inputs stop preflight.

A 512-byte RSA-2048 descriptor binds the layout digest, exact V15751 confinement
profile, release number and HP/Lefony/DTB/rescue image hashes. Redundant layout
records have generations, transaction identities and CRCs. Missing, conflicting,
unrecognized, newer recovery-only or unauthenticated records enter recovery.
There is no unrestricted HP fallback. Each HP boot verifies the original image
and applies the Phase 4 confinement profile in RAM.

The candidate's Lefony capsule carries a distinct layout/ABI tag. The firmware
requires a matching boot handoff before app-storage access. Legacy LFU1/A/B,
development and low-address OS writes are disabled in this build. The ordinary
Lefony-only build remains the default. The model candidate explicitly uses the
public emulator test key; no production signing identity was generated or changed.

The reserved rescue payload is authenticated but is not a separate executable
rescue OS yet. Recovery for this milestone is the verified U-Boot SDP service
and retained host backup/plan. Installing newer OS images is recovery-mediated;
there is no enabled in-OS dual-layout updater or website installation flow.

## Logical backup and recreation

[Logical archive code](../vm/prime_hp_logical_archive.py) decodes physical HP
codewords, validates tag ECC, reconstructs the live directory tree and resolves
file truncation/deletion/rename history. It recreates headers, file bytes and
fresh allocation sequences in the smaller filesystem. It does not relocate old
raw YAFFS pages or checkpoints. Unsupported links/special objects, ambiguous
names/trees, unknown flags and uncorrectable codewords fail before migration.

Wire-format references are the upstream YAFFS
[object header](https://github.com/Aleph-One-Ltd/yaffs2/blob/master/core/yaffs_guts.h),
[packed tags](https://github.com/Aleph-One-Ltd/yaffs2/blob/master/core/yaffs_packedtags2.c)
and [tag ECC](https://github.com/Aleph-One-Ltd/yaffs2/blob/master/core/yaffs_ecc.c).
HP's byte order and metadata marker position were checked against the retained
capture. The tag-parity implementation derives coordinate parity directly.

The retained stock fixture exports **100 live objects: 80 files and 20 directories,
250,846 file bytes**. Programs, settings and application resources in this capture
are included. Original HP ARM filesystem APIs independently read all 80 files
and matched their hashes both on the original 4,096-block geometry and after
recreation/ROM boot on the 2,048-block profile. Recreated content uses 282 pages
in five good eraseblocks, leaving 1,650 good filesystem blocks in this fixture.
This qualifies the tested contents; unsupported object types are rejected, not
silently omitted or generalized to arbitrary HP installations.

The complete physical backup remains independently retained. The exporter checks
its source hash before and after scanning. Archives bind exact header/file hashes
and object relationships. Two matching, isolated Linux flash-BBT tail blocks are
recognized explicitly and preserved; arbitrary ECC failures are never ignored
as presumed foreign metadata.

## Transaction and restart order

[The transaction core](../scripts/prime_dual_boot_transaction.py) and
[offline executor](../vm/prime_dual_migration.py) require an immutable full backup,
a matching logical archive/recreation, validated signed payloads and a retained
host plan. Only disposable regular files under ignored `build/` are writable;
there is no physical transport backend.

1. Stage/read back both menu/recovery streams in verified-erased stock space.
2. Redirect/read back all four FCB copies, lowest search priority first.
3. Verify every ROM route and both complete recovery streams. No HP filesystem
   or upper-region data write is permitted before this barrier.
4. Recreate HP files, initialize the Lefony app region for this stock-source
   migration, and write/read back both OS payloads, DTB, rescue and preferences.
5. Commit the two signed layout records last. The first valid commit can boot
   only after all payload and data readbacks have passed.

Before each erase, a pending record is persisted/read back in the alternate
journal. Completion is recorded only after full raw block readback. Resume
verifies completed blocks and the backup identity, retries a partially written
pending block, and avoids another erase when a completed write lost its reply.
A valid foreign journal is rejected. Unexpected changes, bad blocks or changed
retained inputs require recovery/replanning rather than guessed progress.

Before FCB redirection completes, the stock filesystem remains untouched.
Afterwards, a missing commit reaches U-Boot recovery instead of old unrestricted
HP. A cut during initial journal creation leaves OS/ROM data pristine: the host
can recreate the journal only after every planned target still matches its
original bytes. Losing all valid progress records after data changes requires
the retained full-backup recovery path.

Stock rollback disables both dual-layout records first, restores data, restores
stock FCBs after data verification, then removes the retired menu streams. Journal
cleanup comes only after comparison of all other stock bytes. A cut during final
cleanup leaves stock boot/data restored; the retained plan completes cleanup.
Both migration and restore accept `--resume` only with the same retained plan.
The rollback fixture matches the complete original backup, all 4,096 blocks.

This executor deliberately handles a backed-up **stock source** with erased
staging space. It rejects an occupied legacy Lefony layout. Conversion of an
already installed Lefony calculator is not inferred from this stock path; the
future installer must explicitly preserve its existing app/data backup and select
an independently qualified conversion path.

## Qualification

Private evidence is under ignored `build/dual-boot-phase5/`:

- Physical and VM native targets compile with `LEFONY_DUAL_BOOT=1`; the physical
  target binary is exercised in ROM-boot QEMU runs. No physical flash is implied.
- `migrated-menu3/`: NAND ROM cold boot of both OS loaders, Enter menu, both saved
  priorities, one-time selection without changing priority, and all 80 restored
  HP file hashes through actual HP APIs. Missing images/layout fail closed.
- `arm-rejection/`: actual ARM rejection of bad signature, wrong layout/profile,
  bad CRC, conflicting transaction and newer recovery records; single surviving
  layout copy boots; legacy preference profile enters the menu.
- `native-update-rejection/`: actual ARM manifest/install/development entry points
  reject legacy updates without NAND programs.
- `migration1/`: 564 changed blocks read back, complete unplanned-region
  comparison, and idempotent resume with zero further persistent operations.
- `file-interruption/`: persisted half-page loss in HP block 392, process restart
  through the retained plan, and identical final migrated NAND hash.
- `rollback3/`: exact full-stock restoration and idempotent completed restore.
- `archive-stock-check2/`: independent original HP API validation before migration.
- `legacy-menu/`: existing Lefony-only countdown, Enter, all arrows, Goodix,
  priority, invalid image/preferences and recovery-reset regression passes.
- `faults4/`: all 27,228 migration and 88,980 rollback persistent-operation
  cut points resume successfully in the physical-codeword host model. An
  additional 20 journal-initialization, four old-journal replacement and four
  final-cleanup cuts preserve the documented recovery state: 116,236 cuts total.
  The model verifies each resumed step and unrelated bytes. This is distinct
  from actual ARM ROM/OS tests and from physical power interruption.
- `host-suite.log`: **2,112 tests passed, two private-reference tests skipped**.
  The skips require separately supplied hardware DTB/DTS inputs. Final targeted
  migration/contract/logical tests additionally cover the strengthened FCB/DBBT
  preflight and real file-backed journal encoding. Both native builds, source
  boundary checks, Python/shell syntax and whitespace checks pass.

QEMU r86 corrects the FCB decoder for the captured stock format, whose first
protected codeword includes 32 metadata bytes. The previous synthetic FCB format
still decodes. The host reference tests cover metadata/payload correction and
uncorrectable rejection. No hardware register addresses or upstream pins changed.
The model cold-boots the new NAND U-Boot streams; original stock ROM IVT 4.1 boot
is not newly qualified by this model. Stock rollback is established by exact
backup equivalence and the earlier physical stock-boot evidence.

| Artifact | SHA-256 |
| --- | --- |
| Candidate U-Boot IMX | `6975b0b1868dfc77e741916e6790915cbfa6fe6c92d6b4d1679a6294949b4291` |
| Candidate U-Boot executable | `d1a5eda79484e11d185f3a41eefc08ac03550f36f0c060a010e03ac2118dec57` |
| Physical native binary | `7aae9434df70704b4c52cbb1cf3e1cbf549d59f60bf7dc8589db1dcdd6824810` |
| VM native binary | `d798a2b092edae03103d1c407ae192e85d6936a5fa0c87f946a42777197afe75` |
| Native NAND capsule | `23e756ee5af267db010754c75a0266439c1fd744cf3a343daf24efdb40a55ca7` |
| QEMU r86 | `1825d9b266f3e3bfdda9b27813a84ae97e76c011e3bcb9a458079e1c454d3285` |
| Original stock fixture | `829c782248d50993ece6289c1fda8238bd9edcb804fb7361f1bf9dc9816415cb` |
| Migrated fixture | `b1f85205e7a293afd8bc118906e3dcb8d8a349ead64e8754ecda4da7a23f655d` |

HP logical framebuffer and filesystem results remain separate from the strict
panel/touch model. This does not qualify physical DDR timing, USB reconnection,
NAND endurance, real power interruption, new bad-block retirement during migration,
or an arbitrary HP build. Unsupported HP update/reset/reload paths remain blocked
by the Phase 4 profile. Physical migration is a later explicit qualification gate.

## Reproduce

Run from the repository root. Private input paths are examples, not distributed
artifacts. Use new output directories unless explicitly resuming a retained plan.

```sh
LEFONY_DUAL_PUBLIC_KEY="$PWD/tests/fixtures/prime_g2_emulator_update_public.pem" \
  ./scripts/build_prime_dual_boot.sh
LEFONY_DUAL_BOOT=1 LEFONY_NATIVE_DIST_NAME=lefony-os-prime-g2-dual5-native \
  ./scripts/build_lefony_prime_g2.sh
LEFONY_DUAL_BOOT=1 LEFONY_NATIVE_PLATFORM=prime_g2_vm \
  LEFONY_NATIVE_DIST_NAME=lefony-os-prime-g2-dual5-vm-native \
  ./scripts/build_lefony_prime_g2.sh
LEFONY_DUAL_BOOT=1 ./scripts/build_prime_g2_nand_capsule.sh \
  dist/lefony-os-prime-g2-dual5-native.bin build/dual-boot-phase5/lefony-dual5.zImage
```

Build disposable payload and ROM fixtures with
`vm/prepare-prime-dual-boot-fixture.py` and
`vm/prepare-prime-dual-rom-fixture.py` (`--help` lists their explicit inputs).
Export and recreate logical data with `vm/prime_hp_logical_archive.py`; supply the
source's verified bad-block inventory. Then:

```sh
.venv/bin/python vm/prime_dual_migration.py \
  --backup build/dual-boot-phase3/stock-physical.raw \
  --backup-sha256 829c782248d50993ece6289c1fda8238bd9edcb804fb7361f1bf9dc9816415cb \
  --candidate build/dual-boot-phase5/rom-fixture/nand.raw \
  --uboot build/lefony-uboot-dual5/u-boot-dtb.imx \
  --archive build/dual-boot-phase5/stock-logical \
  --recreated build/dual-boot-phase5/recreated \
  --public-key tests/fixtures/prime_g2_emulator_update_public.pem \
  --output build/dual-boot-phase5/migration-new
```

The fault harness `vm/test-prime-dual-migration-faults.py` takes the same input
arguments plus `--migrated` and a fresh `--output`. The ARM menu test
`vm/test-prime-dual-boot.py` takes `--fixture`, `--uboot`, `--ddr-image`, `--output`,
`--rom` and optional `--archive`. The rejection and native-writer tests are
`vm/test-prime-dual-layout-rejection.py` and `vm/test-prime-dual-native-update.py`.
Rollback uses `vm/restore-prime-dual-fixture.py --help`; its `--current` input stays
immutable and a separate output clone is restored. These tools never accept a
physical calculator transport.
