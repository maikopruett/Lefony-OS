# SPDX-License-Identifier: GPL-3.0-or-later
"""Source-only submission format. Build commands and binary files are forbidden."""
import json
from pathlib import Path
import re
from lfapp import manifest, require

MAX_SOURCE = 1024 * 1024
FORMAT = "lefony-source-0"

def validate(value):
    require(isinstance(value, dict) and set(value) == {"format", "manifest", "files"}, "invalid source bundle")
    require(value["format"] == FORMAT, "unsupported source format")
    manifest(value["manifest"])
    files = value["files"]
    require(isinstance(files, dict) and 1 <= len(files) <= 64, "expected 1–64 source files")
    total = 0
    for name, content in files.items():
        require(isinstance(name, str) and len(name) <= 120 and re.fullmatch(r"src/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:cpp|h)", name), "invalid source path")
        require(isinstance(content, str) and "\0" not in content, "source must be text")
        size = len(content.encode("utf-8"))
        require(size <= 65536, "source file too large")
        total += size
    require(total <= 524288 and any(name.endswith(".cpp") for name in files), "invalid total source size")
    return value


def encode(value):
    validate(value)
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    require(len(data) <= MAX_SOURCE, "source bundle too large")
    return data


def decode(data):
    require(len(data) <= MAX_SOURCE, "source bundle too large")
    return validate(json.loads(data))


def collect(project):
    files = {}
    for path in sorted((project / "src").rglob("*")):
        require(not path.is_symlink(), "source symlinks are forbidden")
        if path.is_file():
            require(path.stat().st_size <= 65536, "source file too large")
            files[path.relative_to(project).as_posix()] = path.read_text(encoding="utf-8")
    return encode({"format": FORMAT, "manifest": json.loads((project / "app.json").read_text()), "files": files})


def extract(data, target):
    value = decode(data)
    target = Path(target)
    target.mkdir(parents=True, exist_ok=False)
    (target / "app.json").write_text(json.dumps(value["manifest"]), encoding="utf-8")
    for name, content in value["files"].items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return value
