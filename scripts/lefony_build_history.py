#!/usr/bin/env python3
"""Archive Lefony OS build artifacts and maintain their local history index."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY_DIR = REPO / "build" / "lefony-os-history"
INDEX_NAME = "index.json"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BuildHistoryEntry:
    build_id: str
    created_at: str
    kind: str
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

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "BuildHistoryEntry":
        return cls(
            build_id=str(value.get("build_id", "")),
            created_at=str(value.get("created_at", "")),
            kind=str(value.get("kind", "unknown")),
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
        )


def _git(source: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_failed(entry: BuildHistoryEntry) -> bool:
    return entry.status == "failed" or entry.status.startswith("physical-failed-")


def load_history(history_dir: Path = DEFAULT_HISTORY_DIR, *, include_failed: bool = False) -> list[BuildHistoryEntry]:
    index = history_dir / INDEX_NAME
    if not index.is_file():
        return []
    try:
        document = json.loads(index.read_text())
        if document.get("schema_version") != SCHEMA_VERSION:
            return []
        entries = [BuildHistoryEntry.from_dict(item) for item in document.get("builds", [])]
    except (OSError, ValueError, TypeError, AttributeError):
        return []
    return sorted((entry for entry in entries if include_failed or not is_failed(entry)),
                  key=lambda entry: (entry.created_at, entry.build_id), reverse=True)


def _write_history(history_dir: Path, entries: list[BuildHistoryEntry]) -> None:
    history_dir.mkdir(parents=True, exist_ok=True)
    # Retire failed artifacts outside the active history; preserve evidence
    # recoverably without leaving a failed image selectable in the installer.
    for entry in entries:
        if not is_failed(entry):
            continue
        relative = Path(entry.artifact)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid failed artifact path")
        source = history_dir / relative
        if not source.resolve().is_relative_to(history_dir.resolve()):
            raise ValueError("Failed artifact escapes history")
        destination = history_dir.parent / (history_dir.name + "-retired") / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            if destination.exists():
                raise ValueError("Refusing to overwrite retired artifact")
            shutil.move(str(source), str(destination))
        destination.with_suffix(destination.suffix + ".history.json").write_text(
            json.dumps(asdict(entry), indent=2) + "\n")
    entries = [entry for entry in entries if not is_failed(entry)]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "builds": [asdict(entry) for entry in entries],
    }
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".index.", suffix=".tmp", dir=history_dir
    )
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, history_dir / INDEX_NAME)
    finally:
        try:
            Path(temporary_name).unlink()
        except FileNotFoundError:
            pass


def prune_failed_builds(history_dir: Path = DEFAULT_HISTORY_DIR) -> int:
    entries = load_history(history_dir, include_failed=True)
    count = sum(is_failed(entry) for entry in entries)
    if count:
        _write_history(history_dir, entries)
    return count


def record_build(
    artifact: Path,
    kind: str,
    *,
    history_dir: Path = DEFAULT_HISTORY_DIR,
    source: Path = REPO,
    version: str = "",
    notes: str = "",
    status: str = "unverified",
    upstream_revision: str = "",
    source_revision_override: str = "",
) -> BuildHistoryEntry:
    artifact = artifact.expanduser().resolve()
    source = source.expanduser().resolve()
    history_dir = history_dir.expanduser().resolve()
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise ValueError(f"build artifact is missing or empty: {artifact}")
    digest = sha256_file(artifact)
    now = datetime.now(timezone.utc)
    created_at = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    source_revision = source_revision_override or _git(source, "rev-parse", "HEAD")
    branch = _git(source, "branch", "--show-current") or "detached"
    dirty = bool(_git(source, "status", "--porcelain"))
    resolved_notes = notes.strip() or os.environ.get("LEFONY_BUILD_NOTES", "").strip()
    if not resolved_notes:
        revision_label = source_revision[:12] if source_revision else "unknown source"
        resolved_notes = f"Automatic {kind} build from {revision_label}."
    safe_kind = "".join(character if character.isalnum() or character in "-_" else "-" for character in kind)
    build_id = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{safe_kind}-{digest[:12]}"
    archive_dir = history_dir / "artifacts" / build_id
    archive_dir.mkdir(parents=True, exist_ok=False)
    archived = archive_dir / artifact.name
    shutil.copy2(artifact, archived)
    entry = BuildHistoryEntry(
        build_id=build_id,
        created_at=created_at,
        kind=kind,
        version=version,
        status=status,
        notes=resolved_notes,
        sha256=digest,
        size=artifact.stat().st_size,
        artifact=str(archived.relative_to(history_dir)),
        source_revision=source_revision,
        upstream_revision=upstream_revision,
        branch=branch,
        dirty=dirty,
    )
    entries = load_history(history_dir)
    entries.insert(0, entry)
    _write_history(history_dir, entries)
    return entry


def annotate_build(
    history_dir: Path,
    build_id: str,
    *,
    notes: str | None = None,
    status: str | None = None,
) -> BuildHistoryEntry:
    entries = load_history(history_dir)
    for index, entry in enumerate(entries):
        if entry.build_id != build_id:
            continue
        updated = replace(
            entry,
            notes=entry.notes if notes is None else notes.strip(),
            status=entry.status if status is None else status,
        )
        entries[index] = updated
        _write_history(history_dir, entries)
        return updated
    raise ValueError(f"unknown build id: {build_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    record = subparsers.add_parser("record", help="archive one successful build")
    record.add_argument("--artifact", type=Path, required=True)
    record.add_argument("--kind", required=True)
    record.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    record.add_argument("--source", type=Path, default=REPO)
    record.add_argument("--version", default="")
    record.add_argument("--notes", default="")
    record.add_argument(
        "--status", choices=("unverified", "known-good", "failed", "superseded"),
        default="unverified",
    )
    record.add_argument("--upstream-revision", default="")
    record.add_argument("--source-revision", default="")
    annotate = subparsers.add_parser("annotate", help="change build notes or status")
    annotate.add_argument("build_id")
    annotate.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    annotate.add_argument("--notes")
    annotate.add_argument(
        "--status", choices=("unverified", "known-good", "failed", "superseded")
    )
    subparsers.add_parser("list", help="print history as JSON").add_argument(
        "--history-dir", type=Path, default=DEFAULT_HISTORY_DIR
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "record":
        entry = record_build(
            args.artifact,
            args.kind,
            history_dir=args.history_dir,
            source=args.source,
            version=args.version,
            notes=args.notes,
            status=args.status,
            upstream_revision=args.upstream_revision,
            source_revision_override=args.source_revision,
        )
        print(json.dumps(asdict(entry), sort_keys=True))
        return 0
    if args.command == "annotate":
        if args.notes is None and args.status is None:
            raise SystemExit("annotate requires --notes or --status")
        entry = annotate_build(
            args.history_dir, args.build_id, notes=args.notes, status=args.status
        )
        print(json.dumps(asdict(entry), sort_keys=True))
        return 0
    print(json.dumps([asdict(entry) for entry in load_history(args.history_dir)], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
