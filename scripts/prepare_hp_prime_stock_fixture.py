#!/usr/bin/env python3
"""Prepare a private HP Prime G2 firmware fixture for emulator research.

The source archive and extracted proprietary images belong under ``build/``
and must never be committed.  This tool deliberately does not download HP
firmware; the operator supplies an image or ZIP they are entitled to use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path


CONTAINER_NAME = "HPPrime_OS.img"
IVT_OFFSET = 0x400
IVT_HEADER = 0x412000D1
RAM_BASE = 0x80000000
RAM_LIMIT = 0x90000000

# The current HP image spends a substantial amount of emulator time in this
# calibrated busy-wait.  Replacing only this exact function with ``bx lr`` is
# an optional research acceleration, not a signature bypass or a distributable
# firmware modification.  The original image is always retained separately.
DELAY_SIGNATURE = bytes.fromhex("4ff4de71491efdd1401ef9d17047")
THUMB_RETURN = bytes.fromhex("7047")
EXPLORATORY_LOOP_SIGNATURE = bytes.fromhex("012000213a4660f02ced84438d43cfe7")
THUMB_BRANCH_TO_EXIT = bytes.fromhex("ffe7")
# Direct-loading HP's maintenance application bypasses the preceding boot
# stage that normally starts the RTOS timebase.  The USB-role task's initial
# one-second settle sleep therefore never expires in QEMU.  This exact,
# private-only research shim changes only that first sleep argument to zero so
# the native USB initialization path can be observed while the missing
# handoff is implemented properly.
BOOTLOADER_SETTLE_SIGNATURE = bytes.fromhex(
    "10b54ff47a7002f0defa0920"
)
# Replace the one-shot settle delay, after the RTOS allocator is live, with
# HP's native NAND initializer. This both supplies the direct-load NAND
# handoff and avoids relying on the absent inherited RTOS timebase.
THUMB_CALL_NAND_INITIALIZER = bytes.fromhex("fbf7f1fb")
BOOTLOADER_ROLE_DEBOUNCE_SIGNATURE = bytes.fromhex(
    "38b5f1f76bfc05003235dff874040468"
)
THUMB_TRUE_RETURN = bytes.fromhex("01207047")
# Once endpoint 2 has been armed, the updater's receive worker polls its event
# queue and delays for 100 ticks when it is empty. A maintenance image loaded
# directly has no inherited RTOS tick source, so a report arriving after that
# first poll wakes the event object but not the sleeping task. Replacing only
# that exact idle delay argument with zero turns vTaskDelay into a scheduler
# yield; all receive, CRC, package, signature, and NAND code remains authentic.
BOOTLOADER_WORKER_IDLE_SIGNATURE = bytes.fromhex(
    "fff7bcfccbe6642009f03dfcfde6"
)
THUMB_ZERO = bytes.fromhex("0020")
# Direct-loaded OS clears the I2C completion byte with ``movs r0,#0`` (Z=1)
# immediately before calling the interrupt-driven transfer helper. That helper
# reuses the incoming flags as a null check, so Z=1 takes the assert path:
# log, then ``bkpt`` forever, with IRQs masked. I2C1 already has IIF pending.
# Replacing only this exact ``bne`` with an unconditional branch keeps the
# authentic transfer/ISR code and lets the pending I2C interrupt complete.
I2C_NULLCHECK_SIGNATURE = bytes.fromhex("0646154609d140f25a32")
THUMB_BRANCH_SAME_OFFSET = bytes.fromhex("09e0")
# Interrupt-driven I2C waits on a completion byte the ISR never sets while
# the CPU is in abort with IRQs masked. Replace the exact ``beq`` spin with
# a Thumb nop so the helper returns; the transfer itself already programmed
# I2C1.
I2C_WAIT_SPIN_SIGNATURE = bytes.fromhex("207b0028fcd0")
THUMB_NOP = bytes.fromhex("00bf")


class FixtureError(ValueError):
    pass


@dataclass(frozen=True)
class Block:
    index: int
    offset: int
    size: int
    declared_data_size: int
    name: str
    data: bytes


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_container(source: Path) -> tuple[bytes, str]:
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            matches = [name for name in archive.namelist() if Path(name).name == CONTAINER_NAME]
            if len(matches) != 1:
                raise FixtureError(f"archive must contain exactly one {CONTAINER_NAME}")
            return archive.read(matches[0]), matches[0]
    return source.read_bytes(), source.name


def parse_blocks(container: bytes) -> list[Block]:
    if len(container) < 24:
        raise FixtureError("firmware container is too short")
    declared_size = struct.unpack_from("<I", container)[0]
    if declared_size != len(container):
        raise FixtureError(
            f"container size mismatch: header={declared_size}, file={len(container)}"
        )

    blocks: list[Block] = []
    offset = 4
    while offset < len(container):
        if len(container) - offset < 16:
            raise FixtureError(f"truncated block header at 0x{offset:x}")
        block_size, data_size, name_size = struct.unpack_from("<III", container, offset)
        if block_size < 16 or block_size > len(container) - offset:
            raise FixtureError(f"invalid block size at 0x{offset:x}: {block_size}")
        if name_size < 4 or 16 + name_size > block_size:
            raise FixtureError(f"invalid block name size at 0x{offset:x}: {name_size}")
        name_bytes = container[offset + 12 : offset + 12 + name_size]
        name = name_bytes.rstrip(b"\0").decode("utf-8", "replace")
        reserved_offset = offset + 12 + name_size
        reserved = container[reserved_offset : reserved_offset + 4]
        if reserved != b"\0\0\0\0":
            raise FixtureError(f"nonzero reserved field at 0x{reserved_offset:x}")
        data_offset = reserved_offset + 4
        data = container[data_offset : offset + block_size]
        blocks.append(Block(len(blocks), offset, block_size, data_size, name, data))
        offset += block_size
    if offset != len(container):
        raise FixtureError("block table does not consume the complete container")
    if len(blocks) < 3:
        raise FixtureError("firmware container has no OS/bootloader/signature set")
    return blocks


def parse_ivt(image: bytes, label: str) -> dict[str, int]:
    if len(image) < IVT_OFFSET + 32:
        raise FixtureError(f"{label} is too short for an i.MX IVT")
    header, entry, reserved1, dcd, boot_data, self_addr, csf, reserved2 = struct.unpack_from(
        "<8I", image, IVT_OFFSET
    )
    if header != IVT_HEADER:
        raise FixtureError(f"{label} has unexpected IVT header 0x{header:08x}")
    if not RAM_BASE <= entry < RAM_LIMIT:
        raise FixtureError(f"{label} entry 0x{entry:08x} is outside expected DDR")
    if self_addr != RAM_BASE + IVT_OFFSET:
        raise FixtureError(
            f"{label} IVT self address is 0x{self_addr:08x}, expected 0x{RAM_BASE + IVT_OFFSET:08x}"
        )
    return {
        "header": header,
        "entry": entry,
        "reserved1": reserved1,
        "dcd": dcd,
        "boot_data": boot_data,
        "self": self_addr,
        "csf": csf,
        "reserved2": reserved2,
    }


def fast_boot_copy(image: bytes) -> tuple[bytes, int]:
    offset = image.find(DELAY_SIGNATURE)
    if offset < 0 or image.find(DELAY_SIGNATURE, offset + 1) >= 0:
        raise FixtureError("calibrated delay signature is absent or ambiguous")
    patched = bytearray(image)
    patched[offset : offset + len(THUMB_RETURN)] = THUMB_RETURN
    return bytes(patched), offset


def skip_i2c_nullcheck_assert(image: bytes) -> tuple[bytes, int | None]:
    """Keep interrupt-driven I2C off the direct-load assert/bkpt path."""
    offset = image.find(I2C_NULLCHECK_SIGNATURE)
    if offset < 0:
        return image, None
    if image.find(I2C_NULLCHECK_SIGNATURE, offset + 1) >= 0:
        raise FixtureError("I2C null-check signature is ambiguous")
    patched = bytearray(image)
    branch_offset = offset + 4
    patched[branch_offset : branch_offset + 2] = THUMB_BRANCH_SAME_OFFSET
    start = 0
    wait_offsets: list[int] = []
    while True:
        wait = patched.find(I2C_WAIT_SPIN_SIGNATURE, start)
        if wait < 0:
            break
        spin = wait + 4
        patched[spin : spin + 2] = THUMB_NOP
        wait_offsets.append(spin)
        start = wait + 2
    return bytes(patched), branch_offset if wait_offsets else branch_offset


def exploratory_copy(image: bytes) -> tuple[bytes, int]:
    """Bypass one reproducible QEMU-only startup loop for fault isolation."""
    offset = image.find(EXPLORATORY_LOOP_SIGNATURE)
    if offset < 0 or image.find(EXPLORATORY_LOOP_SIGNATURE, offset + 1) >= 0:
        raise FixtureError("exploratory startup-loop signature is absent or ambiguous")
    patched = bytearray(image)
    branch_offset = offset + len(EXPLORATORY_LOOP_SIGNATURE) - 2
    patched[branch_offset : branch_offset + 2] = THUMB_BRANCH_TO_EXIT
    return bytes(patched), branch_offset


def exploratory_bootloader_copy(image: bytes) -> tuple[bytes, list[int]]:
    """Supply narrow handoffs absent when the updater is direct-loaded."""
    offset = image.find(BOOTLOADER_SETTLE_SIGNATURE)
    if offset < 0 or image.find(BOOTLOADER_SETTLE_SIGNATURE, offset + 1) >= 0:
        raise FixtureError("bootloader USB settle signature is absent or ambiguous")
    patched = bytearray(image)
    nand_handoff_offset = offset + 6
    patched[
        nand_handoff_offset : nand_handoff_offset + len(THUMB_CALL_NAND_INITIALIZER)
    ] = THUMB_CALL_NAND_INITIALIZER
    debounce_offset = image.find(BOOTLOADER_ROLE_DEBOUNCE_SIGNATURE)
    if debounce_offset < 0 or image.find(
        BOOTLOADER_ROLE_DEBOUNCE_SIGNATURE, debounce_offset + 1
    ) >= 0:
        raise FixtureError("bootloader USB role debounce signature is absent or ambiguous")
    patched[debounce_offset : debounce_offset + 4] = THUMB_TRUE_RETURN
    worker_offset = image.find(BOOTLOADER_WORKER_IDLE_SIGNATURE)
    if worker_offset < 0 or image.find(
        BOOTLOADER_WORKER_IDLE_SIGNATURE, worker_offset + 1
    ) >= 0:
        raise FixtureError("bootloader update-worker idle signature is absent or ambiguous")
    worker_argument_offset = worker_offset + 6
    patched[
        worker_argument_offset : worker_argument_offset + len(THUMB_ZERO)
    ] = THUMB_ZERO
    return bytes(patched), [
        nand_handoff_offset,
        debounce_offset,
        worker_argument_offset,
    ]


def prepare(source: Path, output_dir: Path, enable_fast_boot: bool,
            enable_exploratory_shims: bool = False) -> dict[str, object]:
    container, member_name = read_container(source)
    blocks = parse_blocks(container)
    if blocks[0].name or blocks[1].name:
        raise FixtureError("first two firmware blocks are not the unnamed OS and bootloader")
    if blocks[2].name != "files.sig":
        raise FixtureError("third firmware block is not files.sig")

    output_dir.mkdir(parents=True, exist_ok=True)
    images = (("os", "HPPrime.img", blocks[0].data), ("bootloader", "bootloader.img", blocks[1].data))
    image_manifest: dict[str, object] = {}
    for key, filename, data in images:
        destination = output_dir / filename
        destination.write_bytes(data)
        image_manifest[key] = {
            "path": filename,
            "bytes": len(data),
            "sha256": sha256(data),
            "ivt": parse_ivt(data, key),
        }

    if enable_fast_boot:
        patched, patch_offset = fast_boot_copy(blocks[0].data)
        patched, i2c_offset = skip_i2c_nullcheck_assert(patched)
        fast_name = "HPPrime.fast.img"
        (output_dir / fast_name).write_bytes(patched)
        image_manifest["os_fast"] = {
            "path": fast_name,
            "bytes": len(patched),
            "sha256": sha256(patched),
            "ivt": parse_ivt(patched, "os_fast"),
            "research_patch": {
                "offset": patch_offset,
                "original_sha256": sha256(blocks[0].data),
                "purpose": "replace exact calibrated delay routine with Thumb bx lr",
            },
        }
        if i2c_offset is not None:
            image_manifest["os_fast"]["i2c_irq_patch"] = {
                "offset": i2c_offset,
                "purpose": (
                    "skip the flags-wrong I2C null assert so the pending "
                    "I2C1 interrupt can complete"
                ),
            }

    if enable_exploratory_shims:
        accelerated, delay_offset = fast_boot_copy(blocks[0].data)
        patched, loop_offset = exploratory_copy(accelerated)
        patched, i2c_offset = skip_i2c_nullcheck_assert(patched)
        research_name = "HPPrime.research.img"
        (output_dir / research_name).write_bytes(patched)
        research_patches = [
            {"offset": delay_offset, "purpose": "accelerate exact calibrated delay routine"},
            {
                "offset": loop_offset,
                "purpose": "fault-isolation bypass for reproducible QEMU-only startup loop",
            },
        ]
        if i2c_offset is not None:
            research_patches.append({
                "offset": i2c_offset,
                "purpose": (
                    "skip the flags-wrong I2C null assert so the pending "
                    "I2C1 interrupt can complete"
                ),
            })
        image_manifest["os_research"] = {
            "path": research_name,
            "bytes": len(patched),
            "sha256": sha256(patched),
            "ivt": parse_ivt(patched, "os_research"),
            "research_patches": research_patches,
        }
        bootloader_patched, bootloader_offsets = exploratory_bootloader_copy(
            blocks[1].data
        )
        bootloader_research_name = "bootloader.research.img"
        (output_dir / bootloader_research_name).write_bytes(bootloader_patched)
        image_manifest["bootloader_research"] = {
            "path": bootloader_research_name,
            "bytes": len(bootloader_patched),
            "sha256": sha256(bootloader_patched),
            "ivt": parse_ivt(bootloader_patched, "bootloader_research"),
            "research_patches": [
                {
                    "offset": bootloader_offsets[0],
                    "purpose": (
                        "replace the USB-role task's one-shot settle delay with "
                        "HP's native NAND initializer after the allocator is live"
                    ),
                },
                {
                    "offset": bootloader_offsets[1],
                    "purpose": (
                        "make the USB role debounce succeed while the same "
                        "pre-application RTOS timebase handoff is not emulated"
                    ),
                },
                {
                    "offset": bootloader_offsets[2],
                    "purpose": (
                        "yield instead of sleeping in the update receiver's idle "
                        "poll while the inherited RTOS tick is not emulated"
                    ),
                },
            ],
        }

    manifest: dict[str, object] = {
        "format": "hp-prime-g2-private-emulator-fixture-v1",
        "redistribution": "prohibited; generated under ignored build directory",
        "source": {
            "input_name": source.name,
            "container_member": member_name,
            "bytes": len(container),
            "sha256": sha256(container),
        },
        "images": image_manifest,
        "signature_block": {
            "name": blocks[2].name,
            "bytes": len(blocks[2].data),
            "sha256": sha256(blocks[2].data),
        },
        "resources": [
            {"name": block.name, "bytes": len(block.data), "sha256": sha256(block.data)}
            for block in blocks[3:]
        ],
    }
    manifest_path = output_dir / "fixture.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware", type=Path, help="HPPrime_OS.img or its official ZIP archive")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/hp-prime-stock"), help="ignored private output directory"
    )
    parser.add_argument(
        "--fast-boot", action="store_true", help="also create a locally patched timing-accelerated OS image"
    )
    parser.add_argument(
        "--exploratory-shims", action="store_true",
        help="also create a clearly labeled private image with the current fault-isolation shim",
    )
    args = parser.parse_args()
    try:
        manifest = prepare(args.firmware, args.output_dir, args.fast_boot,
                           args.exploratory_shims)
    except (FixtureError, OSError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
