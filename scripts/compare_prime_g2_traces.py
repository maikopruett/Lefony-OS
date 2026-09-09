#!/usr/bin/env python3
"""Compare a decoded physical capture with the emulator hardware contract."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def normalize_physical(doc: dict) -> dict:
    result = dict(doc)
    result["records"] = {record["name"]: record for record in doc["records"]}
    return result


def lookup(doc: dict, path: str):
    value = doc
    for part in path.split("."):
        value = value[part]
    return value


def compare(physical: dict, emulator: dict, contract: dict) -> list[dict]:
    physical = normalize_physical(physical)
    mismatches = []
    for check in contract["comparisons"]:
        actual = lookup(physical, check["physical"])
        expected = check.get("emulator_constant")
        if expected is None:
            expected = lookup(emulator, check["emulator"])
        tolerance = check.get("absolute_tolerance", 0)
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            equal = abs(actual - expected) <= tolerance
        else:
            equal = actual == expected
        if not equal:
            mismatches.append({"physical_path": check["physical"], "actual": actual,
                               "expected": expected, "tolerance": tolerance})
    return mismatches


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("physical", type=Path)
    p.add_argument("emulator", type=Path)
    p.add_argument("contract", type=Path)
    args = p.parse_args()
    mismatches = compare(json.loads(args.physical.read_text()),
                         json.loads(args.emulator.read_text()),
                         json.loads(args.contract.read_text()))
    print(json.dumps({"status": "match" if not mismatches else "mismatch",
                      "mismatches": mismatches}, indent=2))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
