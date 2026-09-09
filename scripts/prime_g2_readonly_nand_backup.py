#!/usr/bin/env python3
"""Generate a read-only UUU script for a complete HP Prime G2 NAND capture.

The capture includes OOB bytes and dumps factory-bad blocks instead of skipping
them.  Rootfs is transferred in bounded chunks so recovery RAM never needs to
hold the complete 498 MiB partition.
"""

from __future__ import annotations

import argparse
from pathlib import Path


CHUNK_BYTES = 16 * 1024 * 1024
PARTITIONS = (
    ("boot", "/dev/mtd0", 4 * 1024 * 1024),
    ("kernel", "/dev/mtd1", 8 * 1024 * 1024),
    ("dtb", "/dev/mtd2", 1 * 1024 * 1024),
    ("misc", "/dev/mtd3", 1 * 1024 * 1024),
    ("rootfs", "/dev/mtd4", 498 * 1024 * 1024),
)


def recovery_boot_lines() -> list[str]:
    return [
        "SDP: boot -f u-boot-dtb.imx -nojump",
        "SDP: write -f recovery-zImage -addr 0x80800000",
        "SDP: write -f recovery.dtb -addr 0x83000000",
        "SDP: write -f recovery-initramfs.u-boot -addr 0x86800000",
        "SDP: jump -f u-boot-dtb.imx -ivt",
        "",
    ]


def make_script(bootstrap: bool) -> str:
    lines = ["uuu_version 1.2.135", ""]
    if bootstrap:
        lines.extend(recovery_boot_lines())
    lines.append("FBK: ucmd mkdir -p /tmp/lefony-os-prime-backup")
    for name, device, size in PARTITIONS:
        for offset in range(0, size, CHUNK_BYTES):
            length = min(CHUNK_BYTES, size - offset)
            suffix = f"-{offset // CHUNK_BYTES:03d}" if size > CHUNK_BYTES else ""
            destination = f"nand-{name}{suffix}.raw-oob"
            lines.extend([
                "FBK: ucmd nanddump -q --oob --bb=dumpbad "
                f"-s {offset} -l {length} "
                f"-f /tmp/lefony-os-prime-backup/chunk.raw-oob {device}",
                "FBK: ucp T:/tmp/lefony-os-prime-backup/chunk.raw-oob "
                f"{destination}",
            ])
    lines.extend([
        "FBK: ucmd echo ===LEFONY-OS-RAW-OOB-BACKUP-COMPLETE===",
        "FBK: done",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="UUU script to create")
    parser.add_argument(
        "--bootstrap", action="store_true",
        help="begin by booting recovery Linux from an SDP-mode calculator",
    )
    args = parser.parse_args()
    args.output.write_text(make_script(args.bootstrap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
