"""Keep the user-confirmed NAND pair; move old histories outside installer scope.

This one-time maintenance operation never accesses the calculator. It verifies
the exact retained images before moving either history and refuses repeat runs.
"""
from dataclasses import replace
from pathlib import Path
import hashlib
import shutil

import lefony_build_history as os_history
import lefony_uboot_history as ub_history


def main():
    root = Path(__file__).resolve().parents[1] / "build"
    retired = root / "retired-installer-history-20260909"
    if retired.exists():
        raise SystemExit("Retirement already exists; refusing to overwrite it")
    plans = []
    for module, name, digest, status, notes in (
        (os_history, "lefony-os-history",
         "38cc819c903da851a6dc6a2690eb5162d7f00e039e24a9b0a5c3713c922783b3",
         "known-good",
         "WORKING NAND BASELINE: user confirmed Lefony booting from NAND on HP Prime G2, "
         "2026-09-09 UTC, paired with original Prinux U-Boot 2bbea80c11b6. Branded "
         "nonblocking-ADC build. Upload SHA-256 and NAND readback verified. "
         "USB-powered reset boot verified; battery/cold-power-cycle testing pending."),
        (ub_history, "lefony-uboot-history",
         "2bbea80c11b6cd7ec4e27f216637cc7d32356cc2a0c23255909308a9efdaef3c",
         "lefony-nand-boot-verified",
         "WORKING WITH LEFONY AND LINUX: user confirmed Lefony 38cc819c903d booting "
         "from NAND, 2026-09-09 UTC. Prinux Linux previously verified over USB console "
         "with NAND rootfs. Original 2019 U-Boot, unchanged manufacturing environment; "
         "both NAND bootstream copies verified. USB-powered reset boot verified, "
         "not a battery/cold-power-cycle qualification."),
    ):
        history_dir = root / name
        matches = [e for e in module.load_history(history_dir) if e.sha256 == digest]
        if len(matches) != 1:
            raise SystemExit(f"Expected exactly one working image in {name}")
        entry = matches[0]
        artifact = (history_dir / entry.artifact).resolve()
        if not artifact.is_relative_to(history_dir.resolve()):
            raise SystemExit("Artifact escapes history directory")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != digest:
            raise SystemExit("Working artifact hash mismatch")
        plans.append((module, history_dir, replace(entry, status=status, notes=notes)))
    retired.mkdir()
    for module, history_dir, entry in plans:
        destination = retired / history_dir.name
        shutil.move(str(history_dir), str(destination))
        retained = history_dir / entry.artifact
        retained.parent.mkdir(parents=True)
        shutil.copy2(destination / entry.artifact, retained)
        module._write_history(history_dir, [entry])
        assert len(module.load_history(history_dir)) == 1
        print(f"Kept {entry.sha256}: {history_dir}")
    print(f"Previous histories recoverable at {retired}")


if __name__ == "__main__":
    main()
