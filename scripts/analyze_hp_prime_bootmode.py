#!/usr/bin/env python3
"""Sanitized static audit of an operator-supplied HP Prime G2 fixture.

The report contains code offsets and semantic counts only. It never emits
firmware bytes, signatures, or digests, so proprietary fixtures remain under
``build/`` and outside the repository.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import struct


RAM_BASE = 0x80000000
TARGETS = {
    "src_gpr9": 0x020D8040,
    "src_gpr10": 0x020D8044,
    "src_base": 0x020D8000,
    "wdog1": 0x020BC000,
    "wdog2": 0x020C0000,
    "wdog3": 0x021E4000,
}


def occurrences(data: bytes, value: int) -> list[int]:
    needle = struct.pack("<I", value)
    result: list[int] = []
    offset = 0
    while True:
        offset = data.find(needle, offset)
        if offset < 0:
            return result
        result.append(offset)
        offset += 1


def is_immediate(operand: object, arm_op_imm: int, value: int) -> bool:
    return operand.type == arm_op_imm and operand.imm == value


def synthesized_mmio(md: object, data: bytes, arm_op_reg: int,
                     arm_op_imm: int) -> dict[str, list[int]]:
    """Find nearby MOVW/MOVT pairs that construct a target address."""
    low_halves: dict[int, tuple[int, int]] = {}
    result: dict[str, list[int]] = defaultdict(list)
    reverse = {value: name for name, value in TARGETS.items()}
    for instruction in md.disasm(data, RAM_BASE):
        if instruction.id == 0:
            continue
        operands = instruction.operands
        if (instruction.mnemonic == "movw" and len(operands) >= 2 and
                operands[0].type == arm_op_reg and
                operands[1].type == arm_op_imm):
            low_halves[operands[0].reg] = (
                instruction.address, operands[1].imm & 0xFFFF)
        elif (instruction.mnemonic == "movt" and len(operands) >= 2 and
              operands[0].type == arm_op_reg and
              operands[1].type == arm_op_imm):
            low = low_halves.get(operands[0].reg)
            if low is None or instruction.address - low[0] > 24:
                continue
            value = ((operands[1].imm & 0xFFFF) << 16) | low[1]
            name = reverse.get(value)
            if name is not None:
                result[name].append(low[0] - RAM_BASE)
    return result


def find_reset_dispatch(md: object, data: bytes, arm_op_reg: int,
                        arm_op_imm: int) -> dict[str, object] | None:
    """Locate the normal USB 0xE8 handler and decode its four-entry TBB."""
    # A 16-bit Thumb CMP Rn,#0xe8 is encoded with 0xe8 as its first byte and
    # 00101xxx as its second. Prefiltering those aligned sites avoids a second
    # multi-million-instruction pass over a full OS image.
    for offset in range(0, len(data) - 24, 2):
        if data[offset] != 0xE8 or data[offset + 1] & 0xF8 != 0x28:
            continue
        decoded = list(md.disasm(
            data[offset:offset + 24], RAM_BASE + offset))
        if not decoded:
            continue
        instruction = decoded[0]
        if (instruction.mnemonic != "cmp" or
                not any(is_immediate(op, arm_op_imm, 0xE8)
                        for op in instruction.operands)):
            continue
        nearby = decoded
        if len(nearby) < 6 or nearby[1].mnemonic != "bne":
            continue
        # Authentic handler: cmp command,#0xe8; bne; ldrb length; add packet;
        # ldrb mode; bl dispatcher. Requiring this shape rejects data decoded
        # accidentally as Thumb instructions.
        if [item.mnemonic for item in nearby[2:6]] != ["ldrb", "add", "ldrb", "bl"]:
            continue
        # Capstone exposes 32-bit branch destinations as signed values on
        # some hosts; normalize them back into the target address space.
        dispatcher = nearby[5].operands[0].imm & 0xFFFFFFFF
        dispatcher_offset = dispatcher - RAM_BASE
        body = list(md.disasm(
            data[dispatcher_offset:dispatcher_offset + 64], dispatcher))
        if len(body) < 4 or body[1].mnemonic != "cmp" or body[2].mnemonic != "bhi":
            continue
        if not any(is_immediate(op, arm_op_imm, 3) for op in body[1].operands):
            continue
        tbb = next((item for item in body[:6] if item.mnemonic == "tbb"), None)
        if tbb is None:
            continue
        table_address = tbb.address + 4
        table_offset = table_address - RAM_BASE
        case_offsets = [
            table_offset + 2 * entry for entry in data[table_offset:table_offset + 4]
        ]
        calls: list[int | None] = []
        for case_offset in case_offsets:
            case = list(md.disasm(
                data[case_offset:case_offset + 20], RAM_BASE + case_offset))
            call = next((item for item in case if item.mnemonic == "bl"), None)
            calls.append(
                (call.operands[0].imm & 0xFFFFFFFF) - RAM_BASE
                if call else None)
        command_register = instruction.operands[0].reg
        command_ids: list[int] = []
        window_start = max(0, offset - 160)
        for item in md.disasm(
                data[window_start:offset + 1024], RAM_BASE + window_start):
            operands = item.operands
            if (item.mnemonic == "cmp" and len(operands) >= 2 and
                    operands[0].type == arm_op_reg and
                    operands[0].reg == command_register and
                    operands[1].type == arm_op_imm and
                    0xE0 <= operands[1].imm <= 0xFF):
                command = operands[1].imm
                if command not in command_ids:
                    command_ids.append(command)
        return {
            "command": 0xE8,
            "nearby_command_ids": command_ids,
            "handler_offset": offset,
            "dispatcher_offset": dispatcher_offset,
            "maximum_mode": 3,
            "mode_call_offsets": calls,
        }
    return None


def analyze_image(path: Path, include_dispatch: bool) -> dict[str, object]:
    data = path.read_bytes()
    report: dict[str, object] = {
        "bytes": len(data),
        "aligned_literal_offsets": {
            name: [offset for offset in occurrences(data, address)
                   if offset % 4 == 0]
            for name, address in TARGETS.items()
        },
    }
    if not include_dispatch:
        return report

    try:
        from capstone import CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
        from capstone import CS_MODE_THUMB, Cs
        from capstone.arm import ARM_OP_IMM, ARM_OP_REG
    except ImportError as error:
        raise SystemExit(
            "full audit requires Python capstone (python3 -m pip install capstone)"
        ) from error

    synthesized: dict[str, list[int]] = defaultdict(list)
    thumb = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    thumb.detail = True
    thumb.skipdata = True
    arm = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    arm.detail = True
    arm.skipdata = True
    for decoder in (thumb, arm):
        for name, offsets in synthesized_mmio(
                decoder, data, ARM_OP_REG, ARM_OP_IMM).items():
            synthesized[name].extend(offsets)
    report["movw_movt_offsets"] = dict(synthesized)
    report["normal_usb_reset"] = find_reset_dispatch(
        thumb, data, ARM_OP_REG, ARM_OP_IMM)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir", type=Path, default=Path("build/hp-prime-stock"))
    parser.add_argument(
        "--literal-only", action="store_true",
        help="skip Capstone dispatch and MOVW/MOVT analysis")
    args = parser.parse_args()

    manifest_path = args.fixture_dir / "fixture.json"
    if not manifest_path.is_file():
        raise SystemExit(f"private fixture manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    images: dict[str, object] = {}
    for name in ("os", "bootloader"):
        record = manifest.get("images", {}).get(name)
        if record is None:
            continue
        path = args.fixture_dir / record["path"]
        images[name] = analyze_image(path, not args.literal_only)
    print(json.dumps({
        "format": "lefony-hp-prime-bootmode-audit-v1",
        "images": images,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
