#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated Phase 3 fixed-address restore primitives; no automatic installer.

No CLI write operation is exposed. An approved private trial runner must supply
the verified full backups, exact block bytes, factory inventory and journal.
The Linux raw capture must be reconstructed before this physical-codeword API.
Ordinary releases, signed updates and layout provisioning do not use this code.
"""
from dataclasses import dataclass
import hashlib
import struct
import time
import zlib

RAW_BLOCK = 64 * 2112
ERASE = 131072
GEOMETRY = (0x20000000, ERASE, 2048, 64)
STAGE = 0x84000000
READBACK = 0x84200000
REPORT = 0x83e00000
STATUS = 0x83f00000
SCRIPT = 0x83800000
DONE = 0x52454144


def sha(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Change:
    block: int
    before: bytes
    after: bytes
    # Only an exact known stock-metadata block may need its false bad-marker
    # interpretation cleared. The runner must compare it with the stock capture.
    stock_metadata_sha256: str | None = None


def check_inventory(actual, factory_bad, metadata_blocks):
    geometry, bad = actual
    if geometry != GEOMETRY or not factory_bad <= bad or bad - factory_bad - metadata_blocks:
        raise ValueError("geometry or factory bad-block inventory changed")


def restore_blocks(device, changes, factory_bad, journal, *, approved=False):
    """Stop on the first discrepancy; never retry or relocate an ambiguous write.

    journal must durably record the supplied event before returning. The caller
    also performs complete-device verification after this per-block transaction.
    """
    if approved is not True:
        raise ValueError("explicit approval for this private restore is required")
    changes = list(changes)
    seen, metadata = set(), set()
    for c in changes:
        if not 0 <= c.block < 4096 or c.block in seen or c.block in factory_bad:
            raise ValueError("duplicate, out-of-range or factory-bad destination")
        if len(c.before) != RAW_BLOCK or len(c.after) != RAW_BLOCK or c.before == c.after:
            raise ValueError("invalid complete physical eraseblock")
        seen.add(c.block)
        if c.stock_metadata_sha256 is not None:
            if c.block not in {0, 1, 2, 3, 6} or sha(c.before) != c.stock_metadata_sha256:
                raise ValueError("stock-metadata exception lacks exact matching bytes")
            metadata.add(c.block)
    check_inventory(device.inventory(), factory_bad, metadata)
    # Check EVERY destination before the first erase, so stale plans cannot
    # partly replace the device. Recheck each block immediately before mutation.
    for c in changes:
        if device.read_block(c.block) != c.before:
            raise ValueError(f"stale before-image at block {c.block}")
    for c in changes:
        check_inventory(device.inventory(), factory_bad, metadata)
        if device.read_block(c.block) != c.before:
            raise ValueError(f"before-image changed at block {c.block}")
        device.stage(c.after)
        if device.read_stage() != c.after:
            raise ValueError("RAM upload verification failed before erase")
        event = {"block": c.block, "before_sha256": sha(c.before), "after_sha256": sha(c.after)}
        journal({**event, "state": "erase-pending"})
        device.erase(c.block, stock_metadata=c.block in metadata)
        # Old U-Boot nand erase can report success despite an MTD failure.
        # Read into a separate buffer so this cannot overwrite staged data.
        if device.read_block(c.block) != b"\xff" * RAW_BLOCK:
            raise ValueError(f"erase verification failed at block {c.block}; stop before program")
        journal({**event, "state": "program-pending"})
        device.program(c.block)
        if device.read_block(c.block) != c.after:
            raise ValueError(f"raw readback mismatch at block {c.block}; stop, keep RAM recovery alive")
        journal({**event, "state": "verified"})
    check_inventory(device.inventory(), factory_bad, metadata)


def image_hashes(device):
    result = []
    for first in range(0, 4096, 32):
        batch = device.hash_blocks(first, 32)
        if len(batch) != 32:
            raise ValueError("incomplete full-device fingerprint")
        result.extend(batch)
    return result


def restore_image(device, target_hashes, target_block, factory_bad, journal,
                  capture_before, *, expected_before=None, stock_metadata=None,
                  approved=False):
    """Full-device orchestration for a separately approved private trial.

    target_block supplies physical bytes from independently validated inputs.
    capture_before must durably save each changed block before returning. Stock
    install requires expected_before from the fresh complete Lefony backup;
    rollback deliberately discovers ALL HP changes, including outside that plan.
    stock_metadata maps only the five known metadata blocks to exact stock hashes.
    This function never boots, resets, retries or relocates a failed transaction.
    """
    if approved is not True:
        raise ValueError("explicit approval for this private restore is required")
    if len(target_hashes) != 4096 or (expected_before is not None and len(expected_before) != 4096):
        raise ValueError("complete image fingerprints required")
    metadata = stock_metadata or {}
    if set(metadata) - {0, 1, 2, 3, 6}:
        raise ValueError("unexpected stock metadata exception")
    check_inventory(device.inventory(), factory_bad, set(metadata))
    live = image_hashes(device)
    if expected_before is not None and live != list(expected_before):
        raise ValueError("full-device before-image changed; no erase permitted")
    if any(live[b] != target_hashes[b] for b in factory_bad):
        raise ValueError("factory-bad block differs; no relocation permitted")
    for block, digest in metadata.items():
        if live[block] != digest:
            raise ValueError("stock metadata bytes changed; no exception permitted")
    changes = []
    for block in range(4096):
        if live[block] == target_hashes[block]:
            continue
        before = device.read_block(block)
        if sha(before) != live[block]:
            raise ValueError("inconsistent live before-image")
        after = target_block(block)
        if len(after) != RAW_BLOCK or sha(after) != target_hashes[block]:
            raise ValueError("target source changed; no erase permitted")
        capture_before(block, before)
        changes.append(Change(block, before, after, metadata.get(block)))
    # Replace the boot region last. This does not promise power-loss recovery.
    changes.sort(key=lambda c: (c.block < 32, c.block))
    journal({"state": "preflight-complete", "changed_blocks": [c.block for c in changes]})
    restore_blocks(device, changes, factory_bad, journal, approved=True)
    final = image_hashes(device)
    if final != list(target_hashes):
        raise ValueError("complete-device readback mismatch; keep RAM recovery alive")
    journal({"state": "complete-device-verified", "blocks": 4096})
    return final


def legacy_script(command):
    text = command.encode("ascii") + b"\n"
    payload = struct.pack(">II", len(text), 0) + text
    header = struct.pack(">7I4B32s", 0x27051956, 0, 0, len(payload), 0, 0,
                         zlib.crc32(payload), 5, 2, 6, 0, b"Phase 3 explicit RAM command")
    return header[:4] + struct.pack(">I", zlib.crc32(header)) + header[8:] + payload


class PrimeSDP:
    """Research loader v5 only: RAM BBT, corrected script status, 90-minute cap."""
    def __init__(self):
        import hid
        found = [d for d in hid.enumerate(0xcafe, 0x5053)
                 if d["usage_page"] == 0xff00 and d["usage"] == 1]
        if len(found) != 1:
            raise RuntimeError("expected exactly one Prime research SDP interface")
        self.device = hid.device()
        self.device.open_path(found[0]["path"])

    def close(self):
        self.device.close()

    def _ack(self, report, size):
        # Empty HID reads are not a response. Continue waiting for this same
        # command within a total bound; never resend an ambiguous command.
        end = time.monotonic() + 10
        while True:
            if time.monotonic() >= end:
                raise TimeoutError("bounded SDP acknowledgement wait; command not retried")
            data = bytes(self.device.read(65, 1000))
            if data:
                break
        if len(data) != size + 1 or data[0] != report:
            raise RuntimeError(f"unexpected SDP response (length={len(data)}, header={data[:5].hex()}); stop without retrying command")
        return struct.unpack_from("<I", data, 1)[0]

    def _command(self, command, address, data=b"", read_count=0):
        packet = bytearray(16)
        struct.pack_into(">HI", packet, 0, command, address)
        if read_count:
            packet[6] = 0x20
        struct.pack_into(">I", packet, 7, read_count or len(data))
        if self.device.write(b"\x01" + packet) != 17:
            raise RuntimeError("short SDP command")
        for offset in range(0, len(data), 1024):
            if self.device.write(b"\x02" + data[offset:offset + 1024].ljust(1024, b"\0")) != 1025:
                raise RuntimeError("short SDP upload")
        if self._ack(3, 4) != 0x56787856:
            raise RuntimeError("unexpected SDP security status")
        if command == 0x0404 and self._ack(4, 64) != 0x88888888:
            raise RuntimeError("SDP upload rejected")

    def read(self, address, count):
        if not 0 < count <= RAW_BLOCK:
            raise ValueError("bounded RAM read required")
        # macOS hidapi drops the oldest report when its queue reaches roughly
        # 32 entries. A whole NAND block produces 2112 reports and can silently
        # lose bytes if the host is descheduled. At most 16 data reports plus
        # one security report may be outstanding for each request here.
        # https://github.com/libusb/hidapi/blob/master/mac/hid.c
        result = bytearray()
        end = time.monotonic() + 30
        while len(result) < count:
            size = min(1024, count - len(result))
            self._command(0x0101, address + len(result), read_count=size)
            remaining = size
            while remaining:
                if time.monotonic() > end:
                    raise TimeoutError("bounded SDP RAM read")
                packet = bytes(self.device.read(65, 1000))
                if not packet:
                    continue  # this response only; never repeat the command
                if len(packet) != 65 or packet[0] != 4:
                    raise RuntimeError(f"invalid SDP RAM read report: length={len(packet)}, id={packet[0]}")
                used = min(64, remaining)
                result.extend(packet[1:1 + used])
                remaining -= used
        return bytes(result)

    def run(self, command):
        # The cleared marker is uploaded separately, before any shell parsing.
        self._command(0x0404, STATUS, bytes(4))
        body = f"if {command}; then mw.l {STATUS:x} {DONE:x}; fi"
        self._command(0x0404, SCRIPT, legacy_script(body))
        self._command(0x0b0b, SCRIPT)
        # Commands are synchronous on the device. The next request is serviced
        # after completion; USB timeouts are never taken as permission to retry.
        if self.read(STATUS, 4) != struct.pack("<I", DONE):
            raise RuntimeError("research command failed; no automatic retry")

    def inventory(self):
        self.run("hpnandinfo")
        words = struct.unpack("<136I", self.read(REPORT, 544))
        if words[:2] != (0x314e5048, 1):
            raise ValueError("unsupported NAND inventory report")
        bad = {n for n in range(4096) if words[8 + n // 32] & (1 << (n % 32))}
        if len(bad) != words[6]:
            raise ValueError("incomplete NAND bad-block bitmap")
        return tuple(words[2:6]), bad

    def read_block(self, block):
        self._block(block)
        self.run(f"nand read.raw {READBACK:x} {block * ERASE:x} 40")
        return self.read(READBACK, RAW_BLOCK)

    def hash_blocks(self, first, count):
        self._block(first)
        if type(count) is not int or not 1 <= count <= 128 or first + count > 4096:
            raise ValueError("bounded block-hash batch required")
        self.run(f"hpnandhash {first:x} {count:x}")
        if struct.unpack("<3I", self.read(0x83e01000, 12)) != (0x31484e48, first, count):
            raise ValueError("incomplete physical NAND hash batch")
        data = self.read(0x83000000, count * 32)
        return [data[i:i + 32].hex() for i in range(0, len(data), 32)]

    def stage(self, data):
        if len(data) != RAW_BLOCK:
            raise ValueError("complete physical eraseblock required")
        self._command(0x0404, STAGE, data)

    def read_stage(self):
        return self.read(STAGE, RAW_BLOCK)

    @staticmethod
    def _block(block):
        if type(block) is not int or not 0 <= block < 4096:
            raise ValueError("invalid physical NAND block")

    def erase(self, block, *, stock_metadata=False):
        self._block(block)
        if stock_metadata and block not in {0, 1, 2, 3, 6}:
            raise ValueError("invalid stock-metadata block")
        verb = "scrub -y" if stock_metadata else "erase"
        self.run(f"nand {verb} {block * ERASE:x} {ERASE:x}")

    def program(self, block):
        self._block(block)
        self.run(f"nand write.raw {STAGE:x} {block * ERASE:x} 40")
