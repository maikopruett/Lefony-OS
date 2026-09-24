# Lefony Prime G2 installer

Start with `python3 scripts/lefony_installer.py --help`. A fresh checkout has
no private recovery assets or previously qualified build history. Use the
history/recovery path options in `--help` to select existing local assets, or
build new candidates and qualify them before installation. See
[STATUS.md](STATUS.md) and [MIGRATION.md](MIGRATION.md).

Build candidates without contacting hardware:

```sh
make firmware
./scripts/build_prime_g2_nand_capsule.sh
# For an explicit versioned update container, inspect required arguments:
python3 scripts/prime_g2_update_capsule.py --help
```

## Development readback performance

Install and Verify now read MTD in 2048-byte NAND pages instead of one byte
per read. Full pages go directly into the RAM readback file; a partial last
page is read once and trimmed in RAM using portable BusyBox dd options.
For a 2,103,184-byte build this reduces requested NAND read iterations from
2,103,184 to 1,027. This is not a measured wall-clock speedup.

Exact file-length checking, device-side byte comparison, host SHA-256,
U-Boot verification and backups remain enabled. Short reads are rejected.
Restart the installer after updating the script; an in-progress operation
keeps its already generated script. No calculator firmware update is needed
for this optimization. Physical timing needs measurement on the next install.

`scripts/lefony_installer.py` is the native HP Prime G2 connection
monitor, recovery installer, and running-system A/B updater. It uses a curses
interface and refreshes USB state continuously without opening or toggling a
Linux serial console.

When `LEFONY OS RUNNING` is detected, `U` sends a signed `.lfu` container over
native USB. Lefony verifies the HP Prime G2 model and version, RSA-2048
signature, payload size, and SHA-256 before erasing anything. The emulator can
write directly. A physical build resets into ROM recovery only after
authentication; the installer then boots recovery Linux, writes the inactive
slot through the proven GPMI/BCH driver, verifies readback, and atomically
commits redundant pending-slot metadata. The active slot stays bootable until
the pending image starts successfully.

## Safety boundary

Legacy recovery operations can operate only on `/dev/mtd1`, the existing 8 MiB
kernel/Lefony slot. A physical running-device update is additionally allowed to
target the inactive provisioned slot and the first two misc eraseblocks. Those
targets are constants, not host input. The TUI has no command for erasing the
complete NAND device and cannot update:

- `/dev/mtd0`, which contains the ROM boot structures and U-Boot;
- `/dev/mtd2`, which contains the device tree;
- the device-tree partition; or
- any rootfs eraseblock outside the reserved 496--512 MiB A/B tail.

The one exception is the read-only `K` audit: it reads the two kobs-managed
U-Boot copies from `/dev/mtd0` at `0x100000` and `0x280000`. It never erases or
writes `/dev/mtd0`. Both returned images must match the selected U-Boot-history
artifact byte-for-byte and by host SHA-256, including the NAND IVT offset and
the complete `bootcmd`/`bootcmd_mfg` environment.

Every mutating legacy recovery operation reads `/dev/mtd1` into a timestamped
host backup first. Install also verifies both U-Boot copies against the selected
qualified history baseline before it is allowed to erase `/dev/mtd1`. It then
writes the selected native capsule with NAND page padding, reads back exactly
the capsule length, compares it on the calculator, and verifies its SHA-256
again on the host. Only after those checks succeed, the installer clears and
reads back the retained i.MX6ULL ROM boot override, then performs a normal reset
into the installed image. Erase reads back all 8 MiB and requires every byte to
be `0xFF` before it reports success.

The default backup directory is
`build/prime-g2-native-nand/backups/`. An interrupted operation may still have
produced a useful `pre-...-mtd1.mtd` backup there, so retain those files.

### Capture the running OS without entering recovery

For firmware exposing the existing slot-A page-read interface, capture the
installed capsule with two independent reads:

```sh
.venv/bin/python scripts/prime_g2_readonly_os_capture.py \
  --output build/prime-g2-os-capture --timeout 600
```

Use a new output directory. The tool requires an idle updater, active slot A
and no pending boot. It reads only the capsule's validated declared length,
rejects bad-block markers and changed updater state, and compares both SHA-256
hashes. Its USB allowlist permits updater status and bounded slot-A page reads;
it does not program NAND or reboot the calculator.

Success creates `os.zImage`, `verification.zImage` and `report.json`. Until both
reads pass, files stay in a sibling `.partial` directory; failed attempts retain
that directory and their report. Keep these calculator-specific captures private
under ignored `build/` or in a separate private backup location.

This captures BCH-corrected OS bytes only. It excludes NAND spare/OOB bytes,
bootloader copies and app/user data, and cannot replace the full recovery backup
or qualify a firmware candidate. Active slot B requires the recovery backup path.

## Build history

Every successful native, recovery-capsule, and signed-update build is archived
under `build/lefony-os-history/`. The append-only `index.json` records the UTC
build time, SHA-256, byte size, source and upstream revisions, dirty-tree state,
qualification status, notes, and the path to an immutable copy of the artifact.
Press `H` in the installer to view the catalog, then select an installable
capsule with the arrow keys and Enter. The known-good physical baseline is
retained even when a later build replaces the normal output file. Native
intermediate binaries remain visible for diagnosis but are labeled archive-only.

Set notes while compiling with `LEFONY_BUILD_NOTES`, for example:

```sh
LEFONY_BUILD_NOTES="Recovery app added; awaiting physical test" \
  ./scripts/build_lefony_prime_g2.sh
```

After testing hardware, update an entry without changing its artifact:

```sh
./scripts/lefony_build_history.py annotate BUILD_ID \
  --status known-good --notes "Physical display, keyboard, reset, and USB recovery verified."
```

## Requirements

- macOS or Linux with Python 3 and curses;
- NXP UUU (`brew install uuu` on macOS);
- the known-good recovery assets under `~/prinux/boot/`; and
- a capsule produced by `scripts/build_prime_g2_nand_capsule.sh`.

Running-device update additionally requires OpenSSL and an RSA-2048 signing
key. A physical build creates a private local release key under ignored
`build/lefony-update-signing/`, or accepts `LEFONY_UPDATE_PUBLIC_KEY`; only the
public modulus is compiled into Lefony. Build and verify a signed container
without changing the bootable zImage:

```sh
./scripts/build_prime_g2_signed_update.sh 1.0.1+0
```

The key under `tests/fixtures/` is only the emulator test key. Back up the local
release private key separately; losing it prevents signing later updates.
Physical builds refuse an A/B write unless valid provisioned metadata already
exists. See [`LEFONY-UPDATE-ARCHITECTURE.md`](LEFONY-UPDATE-ARCHITECTURE.md) and
[`PRIME-G2-AB-MIGRATION.md`](PRIME-G2-AB-MIGRATION.md) for the qualification
and one-time migration gates.

### U-Boot history and verification

Bootloader builds have an independent append-only catalog under
`build/lefony-uboot-history/`. Each entry stores an immutable padded image,
SHA-256, byte size, embedded U-Boot version, upstream and Lefony source
revisions, IVT offset, both boot commands, notes, and physical qualification
status. `scripts/build_prime_g2_physical_updater_uboot.sh` archives every
successful output automatically.

Press `G` to inspect the U-Boot catalog and choose the comparison baseline.
The installer defaults to the newest `cold-boot-known-good` entry rather than
an unverified newer build. With the calculator in recovery, press `K` to read
and verify both installed U-Boot copies. Readbacks are retained in the normal
backup directory even when a mismatch is found.

An unqualified entry may be selected for the read-only audit, including when
the catalog contains no qualified baseline. Install rejects that selection
before preparing a write operation. A matching readback or an emulator pass
alone does not qualify a bootloader for physical Lefony installation.

The validator parses the packed default environment exactly as U-Boot imports
it and stops at its first double-NUL. It does not accept `bootcmd` text merely
because `strings` can find it later in the binary. This check blocks the
historical `cbf3…`, `da8…`, and `e537…` images whose shortened
`bootcmd_mfg` was incorrectly NUL-padded and hid the normal boot command. New
builds may be marked `emulator-cold-boot-qualified`, but only a subsequent
physical reset test should promote one to `cold-boot-known-good`.

After a real cold-boot test, qualify the exact immutable artifact:

```sh
./scripts/lefony_uboot_history.py annotate BUILD_ID \
  --status cold-boot-known-good \
  --notes "Both NAND copies verified; physical cold reset booted Lefony."
```

On macOS, UUU needs administrator access to detach the ROM USB driver. The TUI
opens the normal macOS authorization dialog only after an operation is
confirmed. Cancelling that dialog leaves NAND untouched.

While an operation runs, the TUI shows its current named phase, whole-operation
phase percentage, any byte-transfer percentage reported by UUU, and elapsed
time. UUU's byte counter restarts for each command, so it is deliberately not
presented as the percentage of the entire installation. A successful install
ends with the explicit `INSTALL COMPLETED AND VERIFIED` result only after both
the device comparison and host SHA-256 readback check pass. Initial USB and
recovery stage waits time out after 30 seconds instead of appearing active
forever; no NAND command has run while the display says it is still waiting for
the expected recovery protocol.

## Start the installer

```sh
./scripts/build_lefony_prime_g2.sh
./scripts/build_prime_g2_nand_capsule.sh
./scripts/build_prime_g2_signed_update.sh 1.0.1+0
./scripts/lefony_installer.py
```

The default image is
`build/lefony-os-native-nand/lefony-os-native.lfu`. Recovery operations automatically
extract the unchanged zImage from an `.lfu` container:

```sh
./scripts/lefony_installer.py \
  --image /safe/path/upsilon-native.zImage \
  --backup-dir /safe/path/prime-backups \
  --prinux /safe/path/prinux
```

Paths are copied into a private whitespace-free staging directory before UUU
runs. The selected capsule must be between 1 MiB and 8 MiB, contain the ARM
zImage magic, and have an exact capsule-size field.

## Live device states

| Display | Meaning | NAND operations |
|---|---|---|
| `ROM RECOVERY` | i.MX6ULL SDP, USB `15A2:0080` | Enabled |
| `RECOVERY LINUX` | UUU fastboot recovery is already running | Enabled |
| `LINUX RUNNING` | Gadget Serial from the Linux system | Blocked |
| `LEFONY OS RUNNING` | Native diagnostic USB `CAFE:5052` | Signed inactive-slot update enabled |
| `HP PRIME OS RUNNING` | Stock G2 USB `03F0:2441` | Research status only; blocked |
| `HP PRIME UPDATE MODE` | Stock G2 updater USB `03F0:2541` | Research status only; blocked |
| `WAITING FOR DEVICE` | No supported USB endpoint | Blocked |

Recovery detection is evaluated before serial-port detection, preventing a
stale macOS `/dev/cu.usbmodem*` node from hiding an SDP calculator. Follow
[`SDP.md`](https://github.com/nxp-imx/mfgtools/wiki) to enter ROM recovery safely.

The two stock-HP states intentionally expose no install command. Research has
confirmed that the running stock OS accepts its normal USB mode-3 request to
enter HP update mode without opening the calculator. The private emulator also
proves that HP's device-side package validation rejects a one-bit mutation with
otherwise valid transport CRCs before any NAND program. The TUI therefore
directs first installations to ROM recovery and enables cable-only updates only
after Lefony is running; stock mode remains research-only unless a separate
authorized execution mechanism is discovered.

## Controls

| Key | Operation |
|---|---|
| `U` | Authenticate, write, read back, and mark the inactive A/B slot pending |
| `I` | Back up, erase, install, read back, and verify Upsilon |
| `V` | Back up and compare installed NAND with the selected image |
| `K` | Read and verify both installed U-Boot copies against the selected bootloader history entry |
| `B` | Back up `/dev/mtd1` without modifying it |
| `E` | Back up, erase, and verify `/dev/mtd1` as erased |
| `X` | Clear the retained recovery override and boot Lefony without touching NAND |
| `H` | View archived Lefony OS builds, hashes, qualification, and notes |
| `G` | View U-Boot history and select the read-only verification baseline |
| `L` | View the filtered UUU operation log |
| `R` | Refresh device and image state immediately |
| `Q` | Quit; disabled while an operation is active |

Update requires typing `UPDATE`. Install requires typing `INSTALL`. Erase
requires typing `ERASE MTD1`.
Backup and verify are read-only but still require a detected recovery endpoint.

For automation and support reports, the monitor has a noninteractive mode:

```sh
./scripts/lefony_installer.py --once --json
```

It reports the detected mode, recovery eligibility, capsule validity and
digest, and the hard-coded NAND target without performing an operation.
# Automatic OS selection and failed-build retirement

Without `--image`, the installer follows the newest hash-verified, installable
OS artifact in the configured history, including unverified candidates. Failed,
superseded, corrupt, missing and raw native-only artifacts are not selected.
The selection refreshes while idle, but remains fixed during an operation.
Explicit `--image` or a manual History selection pins a deliberate rollback.
U-Boot selection continues to prefer its qualified baseline independently.

Marking an OS build failed removes its entry and artifact from active history.
The artifact and failure notes are retired recoverably in the sibling
`build/lefony-os-history-retired` directory, outside the installer's history.
Legacy failed entries are migrated on startup/refresh. A USB transport failure
does not automatically condemn a build. Administrator/password handling is
unchanged.
