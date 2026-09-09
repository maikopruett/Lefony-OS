#!/usr/bin/env python3
"""Archive and identify boot-critical HP Prime G2 U-Boot images."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY_DIR = REPO / "build" / "lefony-uboot-history"
INDEX_NAME = "index.json"
SCHEMA_VERSION = 1
NAND_IVT_OFFSET = 0x400
IVT = bytes.fromhex("d1002040")
QUALIFIED_STATUSES = ("cold-boot-known-good", "known-good", "lefony-nand-boot-verified")
STATUS_CHOICES = (
    "unverified",
    "emulator-cold-boot-qualified",
    "nand-readback-verified",
    "linux-nand-boot-verified",
    "lefony-nand-boot-verified",
    "cold-boot-known-good",
    "physical-failed-black",
    "physical-failed-white",
    "superseded",
)


@dataclass(frozen=True)
class UBootHistoryEntry:
    build_id: str
    created_at: str
    version: str
    status: str
    notes: str
    sha256: str
    size: int
    artifact: str
    source_revision: str
    upstream_revision: str
    branch: str
    dirty: bool
    ivt_offset: int
    bootcmd: str
    bootcmd_mfg: str

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "UBootHistoryEntry":
        return cls(
            build_id=str(value.get("build_id", "")),
            created_at=str(value.get("created_at", "")),
            version=str(value.get("version", "")),
            status=str(value.get("status", "unverified")),
            notes=str(value.get("notes", "")),
            sha256=str(value.get("sha256", "")),
            size=int(value.get("size", 0)),
            artifact=str(value.get("artifact", "")),
            source_revision=str(value.get("source_revision", "")),
            upstream_revision=str(value.get("upstream_revision", "")),
            branch=str(value.get("branch", "")),
            dirty=bool(value.get("dirty", False)),
            ivt_offset=int(value.get("ivt_offset", 0)),
            bootcmd=str(value.get("bootcmd", "")),
            bootcmd_mfg=str(value.get("bootcmd_mfg", "")),
        )


@dataclass(frozen=True)
class UBootImageInfo:
    sha256: str
    size: int
    version: str
    ivt_offset: int
    bootcmd: str
    bootcmd_mfg: str


def _git(source: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source), *args], capture_output=True, text=True,
            timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _default_environment(data: bytes) -> dict[bytes, bytes]:
    """Return only variables U-Boot will import from its packed environment.

    Looking for a variable anywhere in the binary is unsafe: command strings
    after the first double-NUL are present in ``strings`` output but are not
    imported by U-Boot.  That exact mistake allowed a boot image with an
    undefined ``bootcmd`` to be archived and flashed to the Prime G2.
    """
    # Callers may pass a mutable boot stream while repairing it in memory.
    # Normalize so split fields are hashable dictionary keys.
    data = bytes(data)
    start = data.find(b"bootdelay=")
    if start < 0:
        # Small synthetic fixtures and some vendor images omit bootdelay.
        start = data.find(b"bootcmd=")
    if start < 0:
        return {}
    end = data.find(b"\0\0", start)
    if end < 0:
        return {}
    result: dict[bytes, bytes] = {}
    for item in data[start:end].split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        result[key] = value.rstrip(b" ")
    return result


def inspect_bytes(data: bytes) -> UBootImageInfo:
    ivt_offset = NAND_IVT_OFFSET if data[NAND_IVT_OFFSET:NAND_IVT_OFFSET + 4] == IVT else (
        0 if data[:4] == IVT else -1
    )
    # U-Boot contains many diagnostic strings beginning with "U-Boot".  The
    # release banner is the one followed by a numeric year/version.
    version_match = re.search(rb"U-Boot \d{4}\.\d{2}[^\0\r\n]*", data)
    version = version_match.group(0).decode("ascii", "replace") if version_match else ""
    environment = _default_environment(data)
    return UBootImageInfo(
        hashlib.sha256(data).hexdigest(), len(data), version, ivt_offset,
        (b"bootcmd=" + environment[b"bootcmd"]).decode("ascii", "replace")
        if b"bootcmd" in environment else "",
        (b"bootcmd_mfg=" + environment[b"bootcmd_mfg"]).decode("ascii", "replace")
        if b"bootcmd_mfg" in environment else "",
    )


def inspect_image(path: Path) -> UBootImageInfo:
    return inspect_bytes(path.read_bytes())


def validation_errors(info: UBootImageInfo, *, require_nand_handoff: bool = True) -> list[str]:
    errors: list[str] = []
    if info.ivt_offset != NAND_IVT_OFFSET:
        errors.append("NAND U-Boot must contain its i.MX IVT at offset 0x400")
    if not info.version:
        errors.append("U-Boot version string was not found")
    if not info.bootcmd:
        errors.append("bootcmd was not found")
    if require_nand_handoff and info.bootcmd_mfg != "bootcmd_mfg=run bootcmd;":
        errors.append("bootcmd_mfg does not hand off to the NAND boot command")
    return errors


def load_history(history_dir: Path = DEFAULT_HISTORY_DIR) -> list[UBootHistoryEntry]:
    index = history_dir / INDEX_NAME
    if not index.is_file():
        return []
    try:
        document = json.loads(index.read_text())
        if document.get("schema_version") != SCHEMA_VERSION:
            return []
        entries = [UBootHistoryEntry.from_dict(item) for item in document.get("builds", [])]
    except (OSError, ValueError, TypeError, AttributeError):
        return []
    return sorted(entries, key=lambda entry: entry.created_at, reverse=True)


def preferred_entry(entries: list[UBootHistoryEntry]) -> UBootHistoryEntry | None:
    for entry in entries:
        if entry.status in QUALIFIED_STATUSES:
            return entry
    return entries[0] if entries else None


def _write_history(history_dir: Path, entries: list[UBootHistoryEntry]) -> None:
    history_dir.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".index.", suffix=".tmp", dir=history_dir
    )
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(
                {"schema_version": SCHEMA_VERSION, "builds": [asdict(entry) for entry in entries]},
                stream, indent=2, sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, history_dir / INDEX_NAME)
    finally:
        try:
            Path(temporary_name).unlink()
        except FileNotFoundError:
            pass


def record_build(
    artifact: Path,
    *,
    history_dir: Path = DEFAULT_HISTORY_DIR,
    source: Path = REPO,
    notes: str = "",
    status: str = "unverified",
    upstream_revision: str = "",
    source_revision_override: str = "",
    created_at_override: str = "",
) -> UBootHistoryEntry:
    artifact = artifact.expanduser().resolve()
    history_dir = history_dir.expanduser().resolve()
    source = source.expanduser().resolve()
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise ValueError(f"U-Boot artifact is missing or empty: {artifact}")
    if status not in STATUS_CHOICES:
        raise ValueError(f"unsupported U-Boot qualification status: {status}")
    info = inspect_image(artifact)
    # Original Prinux uses a separate USB manufacturing path. Preserve it for
    # Linux qualification without certifying the Lefony recovery handoff.
    errors = validation_errors(
        info, require_nand_handoff=status not in (
            "linux-nand-boot-verified", "lefony-nand-boot-verified"
        )
    )
    if errors:
        raise ValueError(errors[0])
    now = datetime.now(timezone.utc)
    created_at = created_at_override or now.isoformat(timespec="seconds").replace("+00:00", "Z")
    build_id = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-uboot-{info.sha256[:12]}"
    archive_dir = history_dir / "artifacts" / build_id
    archive_dir.mkdir(parents=True, exist_ok=False)
    archived = archive_dir / artifact.name
    shutil.copy2(artifact, archived)
    source_revision = source_revision_override or _git(source, "rev-parse", "HEAD")
    resolved_notes = notes.strip() or f"Automatic U-Boot build from {source_revision[:12] or 'unknown source'}."
    entry = UBootHistoryEntry(
        build_id, created_at, info.version, status, resolved_notes,
        info.sha256, info.size, str(archived.relative_to(history_dir)),
        source_revision, upstream_revision, _git(source, "branch", "--show-current") or "detached",
        bool(_git(source, "status", "--porcelain")), info.ivt_offset,
        info.bootcmd, info.bootcmd_mfg,
    )
    entries = load_history(history_dir)
    entries.insert(0, entry)
    _write_history(history_dir, entries)
    return entry


def annotate_build(
    history_dir: Path, build_id: str, *, notes: str | None = None,
    status: str | None = None,
) -> UBootHistoryEntry:
    if status is not None and status not in STATUS_CHOICES:
        raise ValueError(f"unsupported U-Boot qualification status: {status}")
    entries = load_history(history_dir)
    for index, entry in enumerate(entries):
        if entry.build_id != build_id:
            continue
        updated = replace(
            entry, notes=entry.notes if notes is None else notes.strip(),
            status=entry.status if status is None else status,
        )
        entries[index] = updated
        _write_history(history_dir, entries)
        return updated
    raise ValueError(f"unknown U-Boot build id: {build_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    record = subparsers.add_parser("record", help="archive one NAND-installable U-Boot")
    record.add_argument("--artifact", type=Path, required=True)
    record.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    record.add_argument("--source", type=Path, default=REPO)
    record.add_argument("--notes", default="")
    record.add_argument("--status", choices=STATUS_CHOICES, default="unverified")
    record.add_argument("--upstream-revision", default="")
    record.add_argument("--source-revision", default="")
    annotate = subparsers.add_parser("annotate", help="change qualification notes or status")
    annotate.add_argument("build_id")
    annotate.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    annotate.add_argument("--notes")
    annotate.add_argument("--status", choices=STATUS_CHOICES)
    subparsers.add_parser("list", help="print history as JSON").add_argument(
        "--history-dir", type=Path, default=DEFAULT_HISTORY_DIR
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "record":
        entry = record_build(
            args.artifact, history_dir=args.history_dir, source=args.source,
            notes=args.notes, status=args.status,
            upstream_revision=args.upstream_revision,
            source_revision_override=args.source_revision,
        )
        print(json.dumps(asdict(entry), sort_keys=True))
        return 0
    if args.command == "annotate":
        if args.notes is None and args.status is None:
            raise SystemExit("annotate requires --notes or --status")
        entry = annotate_build(args.history_dir, args.build_id, notes=args.notes, status=args.status)
        print(json.dumps(asdict(entry), sort_keys=True))
        return 0
    print(json.dumps([asdict(entry) for entry in load_history(args.history_dir)], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
