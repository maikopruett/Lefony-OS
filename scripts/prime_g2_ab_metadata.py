#!/usr/bin/env python3
"""Create and inspect Lefony HP Prime G2 redundant A/B boot metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


MAGIC = 0x314D4241
SCHEMA = 1
COMMITTED = 0x434F4D4D
NO_SLOT = 0xFFFFFFFF
PAGE_BYTES = 2048
SLOT_BYTES = 8 * 1024 * 1024
SLOT = struct.Struct("<I4I32s")
RECORD = struct.Struct("<8I52s52s2I")
ZIMAGE_MAGIC = 0x016F2818


class MetadataError(RuntimeError):
    pass


@dataclass(frozen=True)
class Slot:
    bytes: int
    version: tuple[int, int, int, int]
    sha256: bytes

    @classmethod
    def empty(cls) -> "Slot":
        return cls(0, (0, 0, 0, 0), bytes(32))

    @classmethod
    def from_image(cls, image: bytes,
                   version: tuple[int, int, int, int]) -> "Slot":
        validate_image(image)
        return cls(len(image), version, hashlib.sha256(image).digest())

    def pack(self) -> bytes:
        return SLOT.pack(self.bytes, *self.version, self.sha256)

    @classmethod
    def unpack(cls, value: bytes) -> "Slot":
        fields = SLOT.unpack(value)
        return cls(fields[0], tuple(fields[1:5]), fields[5])


@dataclass(frozen=True)
class Metadata:
    generation: int
    active: int
    pending: int
    attempts: int
    boot_limit: int
    slots: tuple[Slot, Slot]

    def pack(self, *, page: bool = False) -> bytes:
        if self.active not in (0, 1):
            raise MetadataError("active slot must be A or B")
        if self.pending not in (0, 1, NO_SLOT):
            raise MetadataError("pending slot must be A, B, or none")
        if not 1 <= self.boot_limit <= 10:
            raise MetadataError("boot limit must be between 1 and 10")
        if any(slot.bytes < 0 or slot.bytes > SLOT_BYTES or
               len(slot.sha256) != 32 for slot in self.slots):
            raise MetadataError("slot record is invalid")
        raw = bytearray(RECORD.pack(
            MAGIC, SCHEMA, RECORD.size, self.generation, self.active,
            self.pending, self.attempts, self.boot_limit,
            self.slots[0].pack(), self.slots[1].pack(), COMMITTED, 0,
        ))
        raw[-4:] = struct.pack("<I", zlib.crc32(raw) & 0xFFFFFFFF)
        return bytes(raw).ljust(PAGE_BYTES, b"\xff") if page else bytes(raw)

    @classmethod
    def unpack(cls, raw: bytes) -> "Metadata":
        if len(raw) < RECORD.size:
            raise MetadataError("metadata record is truncated")
        fields = RECORD.unpack(raw[:RECORD.size])
        magic, schema, size, generation, active, pending, attempts, limit = fields[:8]
        committed, expected_crc = fields[10:12]
        check = bytearray(raw[:RECORD.size])
        check[-4:] = bytes(4)
        if magic != MAGIC or schema != SCHEMA or size != RECORD.size or \
           committed != COMMITTED:
            raise MetadataError("metadata header is invalid")
        if zlib.crc32(check) & 0xFFFFFFFF != expected_crc:
            raise MetadataError("metadata CRC32 is invalid")
        value = cls(generation, active, pending, attempts, limit,
                    (Slot.unpack(fields[8]), Slot.unpack(fields[9])))
        value.pack()
        return value

    def with_update(self, target: int, image: bytes,
                    version: tuple[int, int, int, int]) -> "Metadata":
        if target != 1 - self.active:
            raise MetadataError("an update must target the inactive slot")
        if version <= self.slots[self.active].version:
            raise MetadataError("update version must be newer than active slot")
        slots = list(self.slots)
        slots[target] = Slot.from_image(image, version)
        return Metadata(self.generation + 1, self.active, target, 0,
                        self.boot_limit, tuple(slots))

    def as_dict(self) -> dict[str, object]:
        return {
            "generation": self.generation,
            "active_slot": self.active,
            "pending_slot": None if self.pending == NO_SLOT else self.pending,
            "attempts": self.attempts,
            "boot_limit": self.boot_limit,
            "slots": [
                {"bytes": slot.bytes, "version": slot.version,
                 "sha256": slot.sha256.hex()} for slot in self.slots
            ],
        }


def validate_image(image: bytes) -> None:
    if len(image) < 0x30 or len(image) > SLOT_BYTES:
        raise MetadataError("slot image length is invalid")
    if int.from_bytes(image[0x24:0x28], "little") != ZIMAGE_MAGIC:
        raise MetadataError("slot image is not an ARM zImage")
    if int.from_bytes(image[0x2C:0x30], "little") != len(image):
        raise MetadataError("slot image size field does not match")


def newest(first: bytes, second: bytes) -> tuple[Metadata, int]:
    valid: list[tuple[Metadata, int]] = []
    for index, raw in enumerate((first, second)):
        try:
            valid.append((Metadata.unpack(raw), index))
        except MetadataError:
            pass
    if not valid:
        raise MetadataError("neither redundant metadata copy is valid")
    return max(valid, key=lambda item: item[0].generation)


def seed(image: bytes, version: tuple[int, int, int, int],
         boot_limit: int = 3) -> Metadata:
    return Metadata(1, 0, NO_SLOT, 0, boot_limit,
                    (Slot.from_image(image, version), Slot.empty()))


def parse_version(value: str) -> tuple[int, int, int, int]:
    pieces = value.replace("+", ".").split(".")
    if len(pieces) not in (3, 4) or any(not piece.isdigit() for piece in pieces):
        raise argparse.ArgumentTypeError("version must be MAJOR.MINOR.PATCH[+BUILD]")
    parts = tuple(int(piece) for piece in pieces)
    if len(parts) == 3:
        parts += (0,)
    if any(part > 0xFFFFFFFF for part in parts):
        raise argparse.ArgumentTypeError("version component exceeds 32 bits")
    return parts  # type: ignore[return-value]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("primary", type=Path)
    inspect.add_argument("redundant", type=Path)
    create = sub.add_parser("seed")
    create.add_argument("image", type=Path)
    create.add_argument("output", type=Path)
    create.add_argument("--version", required=True, type=parse_version)
    update = sub.add_parser("update")
    update.add_argument("primary", type=Path)
    update.add_argument("redundant", type=Path)
    update.add_argument("image", type=Path)
    update.add_argument("output", type=Path)
    update.add_argument("--version", required=True, type=parse_version)
    args = parser.parse_args()
    if args.command == "inspect":
        metadata, source = newest(args.primary.read_bytes(), args.redundant.read_bytes())
    elif args.command == "seed":
        metadata = seed(args.image.read_bytes(), args.version)
        source = None
        args.output.write_bytes(metadata.pack(page=True))
    else:
        current, source = newest(args.primary.read_bytes(), args.redundant.read_bytes())
        metadata = current.with_update(1 - current.active, args.image.read_bytes(),
                                       args.version)
        args.output.write_bytes(metadata.pack(page=True))
    print(json.dumps({"source_copy": source, **metadata.as_dict()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
