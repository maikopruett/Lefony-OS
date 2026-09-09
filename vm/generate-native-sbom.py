#!/usr/bin/env python3
"""Generate the reproducible SPDX component inventory for native artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "build" / "lefony-prime-g2-native.spdx.json"


def assignment(path: Path, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}=(.+)$", path.read_text(), re.M)
    if not match:
        raise RuntimeError(f"{name} not found in {path}")
    value = match.group(1).strip()
    default = re.fullmatch(r'\$\{[^:}]+:-"([^"]+)"\}', value)
    return default.group(1) if default else value.strip('"')


def checksum(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    return [{"algorithm": "SHA256", "checksumValue": hashlib.sha256(path.read_bytes()).hexdigest()}]


upstream = REPO / "ports" / "lefony-prime-g2" / "UPSTREAM"
uboot_script = REPO / "vm" / "build-u-boot.sh"
upsilon_commit = assignment(upstream, "UPSILON_COMMIT")
uboot_commit = assignment(uboot_script, "UBOOT_REVISION")

packages = [
    {
        "name": "Upsilon",
        "SPDXID": "SPDXRef-Upsilon",
        "versionInfo": upsilon_commit,
        "downloadLocation": assignment(upstream, "UPSILON_REPOSITORY") + "@" + upsilon_commit,
        "licenseConcluded": "CC-BY-NC-SA-4.0",
        "licenseDeclared": "CC-BY-NC-SA-4.0",
        "copyrightText": "NOASSERTION",
        "filesAnalyzed": False,
        "checksums": checksum(REPO / "dist" / "lefony-os-prime-g2-vm-native.elf"),
    },
    {
        "name": "U-Boot",
        "SPDXID": "SPDXRef-UBoot",
        "versionInfo": uboot_commit,
        "downloadLocation": assignment(uboot_script, "UBOOT_REPOSITORY") + "@" + uboot_commit,
        "licenseConcluded": "GPL-2.0-or-later",
        "licenseDeclared": "GPL-2.0-or-later",
        "copyrightText": "NOASSERTION",
        "filesAnalyzed": False,
        "checksums": checksum(REPO / "build/prime-g2-native-vm/u-boot/u-boot.elf"),
    },
    {
        "name": "Lefony Prime G2 port overlay",
        "SPDXID": "SPDXRef-LefonyOverlay",
        "versionInfo": "working-tree",
        "downloadLocation": "NOASSERTION",
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "copyrightText": "NOASSERTION",
        "filesAnalyzed": False,
    },
]

document = {
    "spdxVersion": "SPDX-2.3",
    "dataLicense": "CC0-1.0",
    "SPDXID": "SPDXRef-DOCUMENT",
    "name": "Lefony-Prime-G2-native",
    "documentNamespace": "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(packages, sort_keys=True))),
    "creationInfo": {"creators": ["Tool: vm/generate-native-sbom.py"], "created": "2026-08-30T00:00:00Z"},
    "packages": packages,
    "relationships": [
        {"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": p["SPDXID"]}
        for p in packages
    ],
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(document, indent=2) + "\n")
print(OUTPUT)
