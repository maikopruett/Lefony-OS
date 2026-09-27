#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline, fixed-address raw/OOB comparison for the isolated stock HP trial.

Creates a review manifest only. Does not open USB, erase, flash, or authorize a
restore. Inputs must use the SAME Linux BCH-2 raw projection, not QEMU physical
codewords. A physical executor must independently check model, geometry, source
hashes, live bad-block inventory, staged bytes and every readback.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

from analyze_hp_prime_compatibility import private_output

ERASE = 131072
RAW_BLOCK = 64 * 2112
PARTITIONS = (("boot", 0x400000), ("kernel", 0x800000),
              ("dtb", 0x100000), ("misc", 0x100000), ("rootfs", 0x1f200000))
RAW_SIZE = 4096 * RAW_BLOCK


def validate_stock_record(record):
    """Reject a physical-codeword fixture supplied as a Linux raw capture."""
    vm_path = str(Path(__file__).resolve().parents[1] / "vm")
    if vm_path not in sys.path:
        sys.path.insert(0, vm_path)
    from hp_prime_stock_nand import reconstruct_physical_page
    from prime_gpmi_bch import Layout
    from prime_nand_image import checksum
    decoded = Layout(0x0720a020, 0x0840a020).decode(reconstruct_physical_page(record))
    if (decoded.status != (0,) * 8 or decoded.payload[4:8] != b"FCB " or
            struct.unpack_from("<I", decoded.payload)[0] != checksum(decoded.payload)):
        raise ValueError("target is not the required Linux BCH2 stock capture")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(text):
    lines = text.strip().splitlines()
    if len(lines) != 6 or lines[-1] != "INVENTORY-READONLY-OK":
        raise ValueError("missing complete physical read-only inventory")
    bad, base = set(), 0
    for part, (_, size) in enumerate(PARTITIONS):
        match = re.fullmatch(rf"mtd {part} size {size} bad((?: [0-9]+)*)", lines[part])
        if not match:
            raise ValueError("unexpected partition geometry/inventory")
        local = [int(value) for value in match[1].split()]
        if local != sorted(set(local)) or any(b >= size // ERASE for b in local):
            raise ValueError("invalid bad-block inventory")
        bad.update(base + b for b in local)
        base += size // ERASE
    return bad


def backup_blocks(directory):
    manifest = json.loads((directory / "SHA256.json").read_text())
    expected = set()
    for name, size in PARTITIONS:
        for start in range(0, size, 0x1000000):
            filename = f"{name}-{start:08x}.raw-oob"
            expected.add(filename)
            data = (directory / filename).read_bytes()
            length = min(0x1000000, size - start) // ERASE * RAW_BLOCK
            if len(data) != length or manifest.get(filename) != {
                    "bytes": length, "sha256": digest(data)}:
                raise ValueError(f"backup checksum/length mismatch: {filename}")
            for at in range(0, length, RAW_BLOCK):
                yield data[at:at + RAW_BLOCK]
    if set(manifest) != expected:
        raise ValueError("unexpected backup manifest entries")


def differences(before, after, bad):
    """All records are compared; a factory-bad block must remain identical."""
    changes, marked_after = [], []
    before_hash, after_hash = hashlib.sha256(), hashlib.sha256()
    for block, (old, new) in enumerate(zip(before, after, strict=True)):
        if len(old) != RAW_BLOCK or len(new) != RAW_BLOCK:
            raise ValueError("short raw eraseblock")
        before_hash.update(old)
        after_hash.update(new)
        # Raw projection OOB[0] is the conventional physical marker after
        # the driver's swap. Stock FCB metadata also occupies this location.
        if new[2048] != 255:
            marked_after.append(block)
        if old == new:
            continue
        if block in bad:
            raise ValueError(f"factory-bad block {block} differs; no relocation allowed")
        changes.append({"block": block, "logical_offset": block * ERASE,
                        "before_sha256": digest(old), "after_sha256": digest(new)})
    return {"before_sha256": before_hash.hexdigest(),
            "after_sha256": after_hash.hexdigest(), "changed_blocks": changes,
            "target_marker_blocks": marked_after,
            "target_extra_marker_blocks": sorted(set(marked_after) - bad)}


def plan(backup, target, target_sha256, inventory_path, output):
    if target.stat().st_size != RAW_SIZE:
        raise ValueError("expected full 512 MiB raw NAND plus OOB")
    output = private_output(output)
    if output.exists():
        raise ValueError("plan output must be new")
    bad = inventory(inventory_path.read_text())
    with target.open("rb") as stream:
        for block in range(4):
            stream.seek(block * RAW_BLOCK)
            validate_stock_record(stream.read(2112))
        stream.seek(0)
        report = differences(backup_blocks(backup),
                             iter(lambda: stream.read(RAW_BLOCK), b""), bad)
    if report["after_sha256"] != target_sha256:
        raise ValueError("target identity mismatch")
    report.update({"schema": 1, "mode": "offline-review-only",
                   "representation": "matching Linux BCH2 raw/OOB projection",
                   "factory_bad_blocks_preserved": sorted(bad),
                   "raw_bytes": RAW_SIZE, "logical_bytes": 0x20000000,
                   "restore_executed": False,
                   "requires_reviewed_rollback": True})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--target-linux-raw", type=Path, required=True)
    parser.add_argument("--target-sha256", required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = plan(args.backup, args.target_linux_raw, args.target_sha256,
                  args.inventory, args.output)
    print(f"Review only: {len(report['changed_blocks'])} changed good blocks; "
          f"target extra markers {report['target_extra_marker_blocks']}")
