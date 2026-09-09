#!/usr/bin/env python3
"""Build a private, ignored raw+OOB NAND fixture from eight HP backup chunks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

CHUNK_DATA_BYTES = 64 * 1024 * 1024
PAGE_DATA_BYTES = 2048
PAGE_OOB_BYTES = 64
PAGES_PER_CHUNK = CHUNK_DATA_BYTES // PAGE_DATA_BYTES
CHUNK_RAW_BYTES = PAGES_PER_CHUNK * (PAGE_DATA_BYTES + PAGE_OOB_BYTES)
CHUNK_COUNT = 8
TOTAL_RAW_BYTES = CHUNK_COUNT * CHUNK_RAW_BYTES
NAME_PATTERN = re.compile(r"^(\d+)-(\d+)mb\.bin$", re.IGNORECASE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ordered_chunks(source_dir: Path) -> list[Path]:
    found: dict[int, Path] = {}
    for path in source_dir.iterdir():
        match = NAME_PATTERN.match(path.name)
        if not match:
            continue
        start, end = map(int, match.groups())
        if end - start != 64 or start % 64 or start < 0 or end > 512:
            raise ValueError(f"invalid NAND chunk range: {path.name}")
        found[start // 64] = path
    if sorted(found) != list(range(CHUNK_COUNT)):
        raise ValueError("expected exactly the ranges 0-64mb through 448-512mb")
    chunks = [found[index] for index in range(CHUNK_COUNT)]
    for path in chunks:
        if path.stat().st_size != CHUNK_RAW_BYTES:
            raise ValueError(
                f"{path.name}: expected {CHUNK_RAW_BYTES} raw+OOB bytes, "
                f"got {path.stat().st_size}"
            )
    return chunks


def prepare(source_dir: Path, output_dir: Path) -> dict[str, object]:
    chunks = ordered_chunks(source_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "stock-nand.raw"
    raw_digest = hashlib.sha256()
    chunk_records = []
    with raw_path.open("wb") as destination:
        for index, path in enumerate(chunks):
            chunk_digest = hashlib.sha256()
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    destination.write(block)
                    raw_digest.update(block)
                    chunk_digest.update(block)
            chunk_records.append(
                {
                    "index": index,
                    "source_name": path.name,
                    "size": path.stat().st_size,
                    "sha256": chunk_digest.hexdigest(),
                }
            )
    if raw_path.stat().st_size != TOTAL_RAW_BYTES:
        raise RuntimeError("joined NAND fixture size changed during preparation")
    manifest = {
        "format": "hp-prime-g2-raw-nand-v1",
        "private_fixture": True,
        "geometry": {
            "data_bytes": PAGE_DATA_BYTES,
            "oob_bytes": PAGE_OOB_BYTES,
            "pages_per_block": 64,
            "blocks": 4096,
        },
        "image": {
            "path": raw_path.name,
            "size": raw_path.stat().st_size,
            "sha256": raw_digest.hexdigest(),
        },
        "chunks": chunk_records,
    }
    manifest_path = output_dir / "nand-fixture.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="directory containing the eight private backup chunks")
    parser.add_argument("--output", type=Path, default=Path("build/hp-prime-stock"))
    args = parser.parse_args()
    try:
        manifest = prepare(args.source_dir.expanduser(), args.output)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(manifest["image"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
