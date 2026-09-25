# Prime G2 one-shot U-Boot recovery (development)

The candidate extends the existing single-slot Prime U-Boot, pinned at
`zephray/uboot` revision `83c84d5e5b7a72855f4455c499b23ee6ead4f74d`.
It preserves NAND offsets, normal boot commands, DDR configuration, and release
trust roots. It is built by `scripts/build_prime_g2_oneshot_uboot.sh` from
`native/prime_g2/u-boot-lefony-oneshot-sdp.patch`. Nothing automatically flashes.

Lefony writes the versioned `LFS1` token (`0x3153464c`) to SNVS LPGPR
(`0x020cc068`) and performs an ordinary watchdog software reset. ROM loads the
NAND bootloader normally. U-Boot clears the token, verifies the clear, and runs
its own `sdp 0` downloader. Another RESET therefore selects normal NAND boot.
SRC ROM override registers and NAND environment are not used for this request.
A pending `LFOK` signed-update confirmation prevents a request; existing `WDGR`
reset-reason handling remains separate.

This is **U-Boot SDP**, USB `cafe:5053`, not the chip ROM's `15a2:0080` endpoint.
Use UUU's `SPL` protocol profile (explicit CFG mapping), not its ROM DCD flow.
U-Boot accepts RAM payloads and legacy U-Boot scripts. Initial enumeration and the subsequent downloader loop share a single
180-second window. On timeout,
U-Boot resumes normal NAND boot. An inherited watchdog is serviced, never armed.
The Prime USB port is forced to peripheral mode without changing keyboard pads
or sourcing VBUS through the EVK board's power-pin setup.

A RAM cookie at `0x80001000` reports version 1 to native firmware. U-Boot publishes
it only after returning from SDP, immediately before normal boot. Native firmware
consumes and clears it, preventing a RAM test from advertising installed support
after RESET returns through the old NAND bootloader.

## Development commands

```
./scripts/build_prime_g2_oneshot_uboot.sh
.venv/bin/python scripts/prime_g2_uboot_recovery.py wrap \
  build/lefony-uboot-oneshot/u-boot-dtb.bin \
  build/lefony-uboot-oneshot/ram-test.zImage
.venv/bin/python scripts/prime_g2_uboot_recovery.py status
# Explicit connected-device actions; require prior hardware authorization:
.venv/bin/python scripts/prime_g2_uboot_recovery.py ram-test \
  build/lefony-uboot-oneshot/ram-test.zImage
.venv/bin/python scripts/prime_g2_uboot_recovery.py once
```

The RAM wrapper is deliberately non-executable and rejected by native OS install
request `0x53`. It is only accepted by CRC-gated development request `0x5d`, which
validates the fixed `0x87800000` destination, ARM entry, header and size, shuts down
display/USB DMA, cleans caches, disables MMU/caches, and enters U-Boot. It never
writes NAND. Request `0x5c` performs the one-shot reboot and additionally requires
the capability cookie from the current boot. Requests are acted on only after
USB status completion and are abandoned on failed/replaced transactions.
A failed RAM-bootstrap mailbox write leaves the OS and USB available.

SNVS writes need bounded cross-domain readback. A latched power-glitch condition
can also continuously zeroize LPGPR. The development request uses the same
`LPPGDR = 0x41736166` initialization as Linux `drivers/rtc/rtc-snvs.c`, then clears
only the PGD status bit. It does not change RTC time, lock bits, fuses, or disable
GPR zeroization. See NXP RM 48.7.14 and the Linux driver for the hardware contract.

## Qualification

The compiled physical and VM native targets have both reached the compiled
U-Boot downloader and enumerated its distinct USB descriptor in QEMU. Tests reject
missing staging, malformed wrappers, wrong CRCs, OS installation of the RAM
wrapper, requests through older U-Boot, and pending boot-confirmation conflicts.
A separate compiled U-Boot reset test verifies that exactly one SDP entry is
followed by the normal NAND read path after RESET. Blank model NAND does not
prove a successful physical OS boot.

```
.venv/bin/python vm/test-native-uboot-recovery.py \
  --elf dist/lefony-os-prime-g2-native.elf \
  --uboot build/lefony-uboot-oneshot/u-boot-dtb.bin
.venv/bin/python vm/test-uboot-oneshot-reset.py \
  --uboot build/lefony-uboot-oneshot/u-boot-dtb.bin
```

QEMU r75 adds the retained LPGPR/lock model and USB CAPLENGTH needed by the
existing U-Boot USB driver. The model does not establish electrical behavior or
power-glitch behavior. Physical RAM handoff now succeeds after confirming and clearing
`SNVS_LPSR = 0x40000008` through the Linux-compatible initialization. U-Boot SDP
was enumerated and used to load the pinned recovery kernel, DTB and initramfs;
Linux confirmed the board, partition layout, BCH-2 and one existing bad boot
block. macOS UUU requires administrator access to claim the HID interface.
Physical NAND installation and independent readback verification now pass. Both
boot streams match the candidate exactly, all four FCB copies have zero BCH-40
corrections, and their geometry matches the original apart from the new image
length. Three usable DBBT copies and the original bad-block marker are verified.
Two complete 553648128-byte corrected-data-plus-OOB backups match across all
36 chunks; a separate raw boot-area capture preserves the original FCB encoding.

The installed bootloader boots native Lefony with capability version 1 (flags
15). Native request `0x5c` reaches `cafe:5053`; a legacy script containing `reset`
sent over that endpoint returns to native Lefony with LPGPR zero. This is a
physical software-reset test; it does not claim the rear button was pressed.
The automatic timeout test also passes: SDP appears in 1.02 seconds, then native
USB returns in 204.92 seconds without a host reset or payload. LPGPR remains
zero and installed capability version 1 is retained. A third native request
loaded the full recovery kernel, DTB and initramfs through the installed U-Boot.
Linux read back the unchanged OS capsule (SHA-256
`d907b5b8ec39ca86a322e50b4aeace5587b6e7c8fe0856422740bf72e1af125f`),
then rebooted successfully to native Lefony. That immediate Linux reboot
disconnected USB before UUU received its final acknowledgement, so UUU reported
`LIBUSB_ERROR_IO`; successful native enumeration, capability version 1 and zero
mailbox were verified independently afterward. The calculator was left in
native Lefony.

The initial post-write log parser also stopped on interleaved stdout/stderr for
the known bad-block refusal. A read-only verification pass handled that exact
diagnostic correctly and checked all readbacks; the bootloader was not rewritten
to retry a logging check. Two early
physical RAM-bootstrap attempts stopped at mailbox readback; the first returned
through ordinary reboot, the second kept native USB alive. Those failed attempts
did not change NAND. Private evidence and candidates remain under ignored `build/`.

The physical candidate is `2018.03-lefony-sdp1`, built for `mx6ull_prime`:

| Artifact | SHA-256 |
| --- | --- |
| NAND image, 413696 bytes, IVT at 0x400 | `8b2490cd5e1ec64bea3231ccf153c83203ba52942de32c3463ec341b91b8617a` |
| RAM U-Boot with DTB | `dbcf9cc7221472c9769792c182693086d0234d73fe0a0204ac4a4c413aae6e7c` |
| Physical native binary with SNVS initialization | `76393bb99db41da54142e8d45696e8d635486972fbdef834f94fe6dbbd304c75` |

The original and candidate DDR DCD are byte-identical. The NAND image uses the
existing redundant stream offsets (1 MiB and 2.5 MiB); the unpadded `.imx` and
RAM wrapper are not NAND images. Installation qualification requires two matching
complete backups, model/geometry checks, preservation of factory bad blocks,
byte comparison of both streams, all usable FCB/DBBT copies, and normal boot.
The physical board has bad block 7, so its fourth DBBT search position is skipped;
three good DBBT copies must agree. All four FCB copies are usable. FCB verification
checks BCH-40 parity, checksum, BCH-2 payload geometry and the bad-block marker
at payload byte 2028, bit 2. Ordinary corrected NAND reads alone cannot validate
the FCB encoding.

NXP's legacy [`kobs-ng`](https://github.com/nxp-imx/imx-kobs/blob/master/src/mtd.c)
excludes the first two boot-control search areas from its
boot-stream bad-block list. Thus this board's original DBBT has zero list pages,
despite Linux correctly reporting bad block 7. The qualification procedure checks
these separately. It also requires the obsolete `gpmi/ignorebad` override to be
absent. The kernel rejects the erase of block 7; only that exact known refusal
can be accepted, followed by verification of every usable copy and unchanged
physical bad-block markers. An arbitrary nonzero tool result is not success.

`make test` passed 1985 tests with two optional private-fixture skips. Both
firmware target builds, the four-test native smoke group, and `make check-public`
passed. The physical and VM compiled targets both passed
`vm/test-native-uboot-recovery.py`; `vm/test-uboot-oneshot-reset.py` passed with
the same compiled U-Boot. These checks do not qualify interrupted bootloader
writes or physical power-loss recovery.

## September 25 release integration

Firmware `1.0.0+1790305558` exposes Settings → About → Enter recovery mode.
The confirmation explains rear RESET or waiting three minutes; Cancel is the
default. Confirmation writes the one-use request and resets automatically.
An older bootloader produces an update instruction instead. A failed mailbox
write returns a visible error without resetting.

Failed ROM-entry stubs, timeout-reset experiments, override probes, the temporary
ROM reader and unused recovery launcher app are removed. The website no longer
uses the failed ROM action or clears SRC override registers on exit. Hardware
ROM recovery remains available independently.

The release pin now selects the new bootloader for subsequent CI packages, and
CI explicitly publishes protocol 2. The website can update an older OS first,
then launch a release-verified RAM U-Boot wrapper to migrate an older bootloader.
Installed support uses request `0x5c`; migration uses `0x5d`. The exact compiled
source for both physical firmware and U-Boot accompanies the release.

The revised U-Boot shares one 180-second deadline between enumeration and SDP
requests. Its exact NAND SHA-256 is
`80c1c3732ed339025f22cdb9c3a08bbdf8b9571c64f8acc65846452f2c5c6f4c`;
RAM `.imx` SHA-256 is
`fbe7d8acf09408e5bb59bd015f11dcb1847fc84b1ecaea3cad13afd06faea25f`.
The physical OS capsule SHA-256 is
`9157f4bd600be52d4423d24959ef883029065e4d30845b81c2504031508827ca`.
The full website worker was run on the calculator through a local qualification
transport: OS/DTB, both boot streams, four BCH-40 FCBs, three usable DBBTs and
unchanged factory markers all passed, followed by native boot with capability 1.
Chrome WebHID separately loaded the recovery Linux through the installed U-Boot.
The final shared-timeout candidate returned to native USB in 213.14 seconds,
including normal startup; no host reset or payload was sent during that test.

Both firmware targets compile. The OS host suite passes 1981 tests (two optional
private-fixture skips); the four smoke tests and public-boundary check pass.
Compiled native/U-Boot handoff and reset tests pass. The normal key-matrix Settings
test covers the visible confirmation, Cancel, and automatic reset on Confirm;
the screen was inspected. It does not claim a physical finger pressed Settings
or the rear RESET button. Physical interruption, cold-power and electrical
qualification remain separate.


The complete Chrome website flow subsequently passed on both the existing
installation and fully erased usable NAND. The blank-NAND test erased all five
MTD partitions after revalidating two matching full backups, preserved factory
bad-block markers, installed OS/DTB/U-Boot through the website, and automatically
returned to native firmware `1.0.0+1790305558`. The browser displayed its verified
current-version screen. The obsolete desktop native-to-ROM update fallback is
also removed; recovery exit no longer writes SRC override registers.
