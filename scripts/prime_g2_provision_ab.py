#!/usr/bin/env python3
"""Generate the one-time, recovery-only Lefony A/B provisioning script.

This tool does not run UUU.  It validates the three inputs and emits a fixed-
target script that writes the ROM boot streams, slot A, and two metadata copies.
Every programmed object is read back and compared before reboot.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import prime_g2_ab_metadata as ab_metadata


UBOOT_IVT_OFFSET = 0x400
UBOOT_IVT = bytes.fromhex("d1002040")
FIRMWARE_A_OFFSET = 0x100000
FIRMWARE_B_OFFSET = 0x280000
METADATA_BYTES = 2048
METADATA_REDUNDANT_OFFSET = 128 * 1024


def recovery_boot_lines() -> list[str]:
    return [
        "SDP: boot -f recovery-u-boot.imx -nojump",
        "SDP: write -f recovery-zImage -addr 0x80800000",
        "SDP: write -f recovery.dtb -addr 0x83000000",
        "SDP: write -f recovery-initramfs.u-boot -addr 0x86800000",
        "SDP: jump -f recovery-u-boot.imx -ivt",
        "",
    ]


def validate_inputs(uboot: bytes, image: bytes, metadata_page: bytes) -> None:
    if len(uboot) > FIRMWARE_B_OFFSET - FIRMWARE_A_OFFSET:
        raise ValueError("U-Boot does not fit in either redundant boot stream")
    if uboot[UBOOT_IVT_OFFSET:UBOOT_IVT_OFFSET + 4] != UBOOT_IVT:
        raise ValueError("U-Boot lacks the NAND-ROM IVT at offset 0x400")
    ab_metadata.validate_image(image)
    if len(metadata_page) != METADATA_BYTES:
        raise ValueError("seed metadata must be exactly one NAND page")
    metadata = ab_metadata.Metadata.unpack(metadata_page)
    expected = ab_metadata.Slot.from_image(image, metadata.slots[0].version)
    if metadata.generation != 1 or metadata.active != 0 or \
       metadata.pending != ab_metadata.NO_SLOT or metadata.attempts != 0 or \
       metadata.slots[0] != expected or metadata.slots[1] != ab_metadata.Slot.empty():
        raise ValueError("metadata is not a clean slot-A seed for this image")


def make_script(uboot_bytes: int, image_bytes: int) -> str:
    lines = ["uuu_version 1.2.135", "", *recovery_boot_lines()]
    lines.extend([
        "FBK: ucmd mkdir -p /tmp/lefony-os-provision",
        "FBK: ucmd sh -c \"mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true\"",
        "FBK: ucmd test -r /sys/kernel/debug/gpmi-nand/raw_mode",
        "FBK: ucp lefony-u-boot.imx T:/tmp/lefony-os-provision/lefony-u-boot.imx",
        "FBK: ucp lefony-slot-a.zImage T:/tmp/lefony-os-provision/lefony-slot-a.zImage",
        "FBK: ucp seed-metadata.bin T:/tmp/lefony-os-provision/seed-metadata.bin",
        f"FBK: ucmd test $(wc -c < /tmp/lefony-os-provision/lefony-u-boot.imx) -eq {uboot_bytes}",
        f"FBK: ucmd test $(wc -c < /tmp/lefony-os-provision/lefony-slot-a.zImage) -eq {image_bytes}",
        f"FBK: ucmd test $(wc -c < /tmp/lefony-os-provision/seed-metadata.bin) -eq {METADATA_BYTES}",
        # mtd0 contains one known bad block.  The default erase policy skips it;
        # kobs publishes that fact through the ROM DBBT copies.
        "FBK: ucmd flash_erase /dev/mtd0 0 32",
        "FBK: ucmd sh -c \"export TMPDIR=/tmp TEMP=/tmp TMP=/tmp; kobs-ng init -v -w --chip_0_device_path=/dev/mtd0 --secondary_boot_stream_off_in_MB=2 /tmp/lefony-os-provision/lefony-u-boot.imx > /tmp/lefony-os-provision/kobs.log 2>&1\"",
        "FBK: ucmd grep -q 'mtd_commit_bcb(FCB): status 0' /tmp/lefony-os-provision/kobs.log",
        "FBK: ucp T:/tmp/lefony-os-provision/kobs.log kobs.log",
        f"FBK: ucmd nanddump -q -s {FIRMWARE_A_OFFSET} -l {uboot_bytes} -f /tmp/lefony-os-provision/boot-a.readback /dev/mtd0",
        "FBK: ucmd cmp /tmp/lefony-os-provision/lefony-u-boot.imx /tmp/lefony-os-provision/boot-a.readback",
        f"FBK: ucmd nanddump -q -s {FIRMWARE_B_OFFSET} -l {uboot_bytes} -f /tmp/lefony-os-provision/boot-b.readback /dev/mtd0",
        "FBK: ucmd cmp /tmp/lefony-os-provision/lefony-u-boot.imx /tmp/lefony-os-provision/boot-b.readback",
        "FBK: ucp T:/tmp/lefony-os-provision/boot-a.readback boot-a.readback",
        "FBK: ucp T:/tmp/lefony-os-provision/boot-b.readback boot-b.readback",
        "FBK: ucmd flash_erase -N /dev/mtd1 0 64",
        "FBK: ucmd nandwrite -p -N /dev/mtd1 /tmp/lefony-os-provision/lefony-slot-a.zImage",
        f"FBK: ucmd nanddump -q -l {image_bytes} -f /tmp/lefony-os-provision/slot-a.readback /dev/mtd1",
        "FBK: ucmd cmp /tmp/lefony-os-provision/lefony-slot-a.zImage /tmp/lefony-os-provision/slot-a.readback",
        "FBK: ucp T:/tmp/lefony-os-provision/slot-a.readback slot-a.readback",
        "FBK: ucmd flash_erase -N /dev/mtd3 0 1",
        "FBK: ucmd nandwrite -p -N -s 0 /dev/mtd3 /tmp/lefony-os-provision/seed-metadata.bin",
        f"FBK: ucmd nanddump -q -s 0 -l {METADATA_BYTES} -f /tmp/lefony-os-provision/metadata-a.readback /dev/mtd3",
        "FBK: ucmd cmp /tmp/lefony-os-provision/seed-metadata.bin /tmp/lefony-os-provision/metadata-a.readback",
        "FBK: ucmd flash_erase -N /dev/mtd3 131072 1",
        f"FBK: ucmd nandwrite -p -N -s {METADATA_REDUNDANT_OFFSET} /dev/mtd3 /tmp/lefony-os-provision/seed-metadata.bin",
        f"FBK: ucmd nanddump -q -s {METADATA_REDUNDANT_OFFSET} -l {METADATA_BYTES} -f /tmp/lefony-os-provision/metadata-b.readback /dev/mtd3",
        "FBK: ucmd cmp /tmp/lefony-os-provision/seed-metadata.bin /tmp/lefony-os-provision/metadata-b.readback",
        "FBK: ucp T:/tmp/lefony-os-provision/metadata-a.readback metadata-a.readback",
        "FBK: ucp T:/tmp/lefony-os-provision/metadata-b.readback metadata-b.readback",
        "FBK: ucmd sync",
        "FBK: ucmd echo ===LEFONY-OS-A-B-PROVISION-COMPLETE===",
        # This mfgtool fastboot gadget does not implement Android's `reboot`
        # command. End the verified transaction successfully; the host can
        # then request one physical RESET without misreporting the flash.
        "FBK: done",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("uboot", type=Path)
    parser.add_argument("image", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    uboot = args.uboot.read_bytes()
    image = args.image.read_bytes()
    metadata = args.metadata.read_bytes()
    validate_inputs(uboot, image, metadata)
    args.output.write_text(make_script(len(uboot), len(image)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
