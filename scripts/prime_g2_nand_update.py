#!/usr/bin/env python3
"""Fault-testable HP Prime G2 A/B NAND capsule manager.

The default layout is emulator-only. Physical writes are refused unless the
caller supplies a captured bad-block map and explicitly selects the current
single kernel partition; the stock rootfs is never silently repartitioned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import NamedTuple


REPO = Path(__file__).resolve().parents[1]
LAYOUT_PATH = REPO / "native" / "prime_g2" / "nand_layout.json"
ERASED = b"\xff"


class UpdateError(RuntimeError):
    pass


class Region(NamedTuple):
    name: str
    offset: int
    size: int


def load_layout(path: Path = LAYOUT_PATH) -> tuple[dict, dict[str, Region]]:
    document = json.loads(path.read_text())
    regions = {item["name"]: Region(**item)
               for item in document["emulator_ab_layout"]}
    return document, regions


def initial_state() -> dict:
    return {
        "schema": 1, "generation": 0, "active": "a", "pending": None,
        "attempts": 0, "boot_limit": 3,
        "slots": {"a": None, "b": None}, "last_result": "factory",
    }


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".new")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def validate_capsule(payload: bytes) -> None:
    if len(payload) < 0x30:
        raise UpdateError("capsule is shorter than its zImage header")
    if int.from_bytes(payload[0x24:0x28], "little") != 0x016F2818:
        raise UpdateError("capsule has no ARM zImage magic")
    if int.from_bytes(payload[0x2C:0x30], "little") != len(payload):
        raise UpdateError("capsule length does not match its zImage header")


class Manager:
    def __init__(self, image: Path, state_path: Path,
                 bad_blocks: set[int] | None = None):
        self.document, self.regions = load_layout()
        self.geometry = self.document["geometry"]
        self.image = image
        self.state_path = state_path
        self.bad_blocks = bad_blocks or set()

    def create(self) -> None:
        self.image.parent.mkdir(parents=True, exist_ok=True)
        with self.image.open("wb") as output:
            output.truncate(self.geometry["total_bytes"])
        atomic_json(self.state_path, initial_state())

    def seed_factory(self, capsule: Path) -> dict:
        payload = capsule.read_bytes()
        validate_capsule(payload)
        state = self.state()
        if state["generation"] or state["slots"]["a"] is not None:
            raise UpdateError("factory slot has already been initialized")
        digest = self._write_slot(self.regions["slot_a"], payload)
        state["slots"]["a"] = {
            "sha256": digest, "bytes": len(payload),
            "good_blocks": len(self._good_blocks(self.regions["slot_a"])),
        }
        state["last_result"] = "factory-seeded"
        atomic_json(self.state_path, state)
        return state

    def state(self) -> dict:
        if not self.state_path.exists():
            raise UpdateError("update state does not exist; run create first")
        return json.loads(self.state_path.read_text())

    def _good_blocks(self, region: Region) -> list[int]:
        erase = self.geometry["erase_block_bytes"]
        if region.offset % erase or region.size % erase:
            raise UpdateError(f"{region.name} is not erase-block aligned")
        first = region.offset // erase
        return [block for block in range(first, first + region.size // erase)
                if block not in self.bad_blocks]

    def _write_slot(self, region: Region, payload: bytes,
                    fail_after: str | None = None) -> str:
        erase = self.geometry["erase_block_bytes"]
        blocks = self._good_blocks(region)
        if len(payload) > len(blocks) * erase:
            raise UpdateError("capsule does not fit after bad-block removal")
        with self.image.open("r+b") as nand:
            for block in blocks:
                nand.seek(block * erase)
                nand.write(ERASED * erase)
            nand.flush()
            os.fsync(nand.fileno())
            if fail_after == "erase":
                raise UpdateError("simulated power loss after erase")
            cursor = 0
            for block in blocks:
                if cursor == len(payload):
                    break
                chunk = payload[cursor:cursor + erase]
                nand.seek(block * erase)
                nand.write(chunk)
                cursor += len(chunk)
            nand.flush()
            os.fsync(nand.fileno())
            if fail_after == "write":
                raise UpdateError("simulated power loss after write")
            digest = hashlib.sha256()
            remaining = len(payload)
            for block in blocks:
                if not remaining:
                    break
                count = min(remaining, erase)
                nand.seek(block * erase)
                digest.update(nand.read(count))
                remaining -= count
        expected = hashlib.sha256(payload).hexdigest()
        if digest.hexdigest() != expected:
            raise UpdateError("NAND readback digest mismatch")
        if fail_after == "verify":
            raise UpdateError("simulated power loss after verify")
        return expected

    def install(self, capsule: Path, fail_after: str | None = None) -> dict:
        payload = capsule.read_bytes()
        validate_capsule(payload)
        state = self.state()
        if not self._slot_valid(state, state["active"]):
            raise UpdateError("active slot is not a verified factory image")
        target = "b" if state["active"] == "a" else "a"
        digest = self._write_slot(self.regions[f"slot_{target}"], payload,
                                  fail_after)
        next_state = json.loads(json.dumps(state))
        next_state["generation"] += 1
        next_state["slots"][target] = {
            "sha256": digest, "bytes": len(payload),
            "good_blocks": len(self._good_blocks(self.regions[f"slot_{target}"])),
        }
        next_state["pending"] = target
        next_state["attempts"] = 0
        next_state["last_result"] = "staged"
        if fail_after == "state":
            raise UpdateError("simulated power loss before metadata commit")
        atomic_json(self.state_path, next_state)
        return next_state

    def _slot_valid(self, state: dict, slot: str) -> bool:
        metadata = state["slots"].get(slot)
        if not metadata or not isinstance(metadata.get("bytes"), int) or \
                not isinstance(metadata.get("sha256"), str):
            return False
        region = self.regions[f"slot_{slot}"]
        length = metadata["bytes"]
        if length < 0x30 or length > region.size:
            return False
        digest = hashlib.sha256()
        header = bytearray()
        remaining = length
        erase = self.geometry["erase_block_bytes"]
        with self.image.open("rb") as nand_file:
            for block in self._good_blocks(region):
                if not remaining:
                    break
                amount = min(remaining, erase)
                nand_file.seek(block * erase)
                chunk = nand_file.read(amount)
                if len(chunk) != amount:
                    return False
                if len(header) < 0x30:
                    header.extend(chunk[:0x30 - len(header)])
                digest.update(chunk)
                remaining -= amount
        if remaining or digest.hexdigest() != metadata["sha256"]:
            return False
        if len(header) < 0x30 or \
                int.from_bytes(header[0x24:0x28], "little") != 0x016F2818 or \
                int.from_bytes(header[0x2C:0x30], "little") != length:
            return False
        return True

    def select_boot(self) -> str:
        state = self.state()
        if state["pending"] is not None and \
                not self._slot_valid(state, state["pending"]):
            failed = state["pending"]
            state["pending"] = None
            state["attempts"] = 0
            state["last_result"] = f"rollback-corrupt-{failed}"
            atomic_json(self.state_path, state)
        if state["pending"] is None:
            if self._slot_valid(state, state["active"]):
                return state["active"]
            alternate = "b" if state["active"] == "a" else "a"
            if self._slot_valid(state, alternate):
                state["active"] = alternate
                state["last_result"] = f"recovered-{alternate}"
                atomic_json(self.state_path, state)
                return alternate
            state["last_result"] = "rescue-both-invalid"
            atomic_json(self.state_path, state)
            return "rescue"
        state["attempts"] += 1
        if state["attempts"] > state["boot_limit"]:
            failed = state["pending"]
            state["pending"] = None
            state["attempts"] = 0
            state["last_result"] = f"rollback-from-{failed}"
            atomic_json(self.state_path, state)
            return state["active"]
        atomic_json(self.state_path, state)
        return state["pending"]

    def mark_good(self) -> dict:
        state = self.state()
        if state["pending"] is None:
            raise UpdateError("there is no pending slot")
        if not self._slot_valid(state, state["pending"]):
            raise UpdateError("pending slot failed readback validation")
        state["active"] = state["pending"]
        state["pending"] = None
        state["attempts"] = 0
        state["last_result"] = "boot-confirmed"
        atomic_json(self.state_path, state)
        return state

    def export_uboot_environment(self, destination: Path) -> None:
        state = self.state()
        base = (REPO / "native" / "prime_g2" / "lefony_ab_boot.env").read_text()
        generated = [
            f"upsilon_active={state['active']}",
            f"upsilon_pending={state['pending'] or ''}",
            f"upsilon_attempts={state['attempts']}",
        ]
        for slot in ("a", "b"):
            metadata = state["slots"][slot]
            generated.extend((
                f"upsilon_{slot}_bytes={metadata['bytes'] if metadata else 0}",
                f"upsilon_{slot}_sha256={metadata['sha256'] if metadata else ''}",
            ))
        # Generated values follow the defaults so U-Boot's text-env parser
        # uses the current transaction metadata.
        destination.write_text(base.rstrip() + "\n" + "\n".join(generated) + "\n")


def load_bad_blocks(path: Path | None) -> set[int]:
    if path is None:
        return set()
    value = json.loads(path.read_text())
    if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
        raise UpdateError("bad-block map must be a JSON integer list")
    return set(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--bad-blocks", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--factory", type=Path)
    install = sub.add_parser("install")
    install.add_argument("capsule", type=Path)
    install.add_argument("--fail-after", choices=("erase", "write", "verify", "state"))
    sub.add_parser("select-boot")
    sub.add_parser("mark-good")
    sub.add_parser("status")
    export = sub.add_parser("export-env")
    export.add_argument("destination", type=Path)
    args = parser.parse_args()
    manager = Manager(args.image, args.state, load_bad_blocks(args.bad_blocks))
    try:
        if args.command == "create":
            manager.create()
            result = manager.seed_factory(args.factory) if args.factory else manager.state()
        elif args.command == "install": result = manager.install(args.capsule, args.fail_after)
        elif args.command == "select-boot": result = {"slot": manager.select_boot()}
        elif args.command == "mark-good": result = manager.mark_good()
        elif args.command == "export-env":
            manager.export_uboot_environment(args.destination)
            result = {"environment": str(args.destination)}
        else: result = manager.state()
    except UpdateError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
