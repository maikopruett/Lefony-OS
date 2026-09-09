from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "lefony_uboot_history", ROOT / "scripts/lefony_uboot_history.py"
)
history = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = history
SPEC.loader.exec_module(history)

PATCH_SPEC = importlib.util.spec_from_file_location(
    "patch_uboot_env", ROOT / "scripts/patch_uboot_env.py"
)
patcher = importlib.util.module_from_spec(PATCH_SPEC)
assert PATCH_SPEC.loader
PATCH_SPEC.loader.exec_module(patcher)


def make_uboot(path: Path, *, bootcmd: bytes = b"bootcmd=nand read 80800000 400000 800000") -> None:
    data = bytearray(8192)
    data[0x400:0x404] = history.IVT
    strings = b"\0".join((
        b"U-Boot 2018.03 (test build)",
        bootcmd,
        b"bootcmd_mfg=run bootcmd;",
        b"",
    ))
    data[0x800:0x800 + len(strings)] = strings
    path.write_bytes(data)


def test_history_records_boot_contract_and_prefers_cold_boot_qualified_build():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        artifact = root / "u-boot-pad.imx"
        make_uboot(artifact)
        known = history.record_build(
            artifact, history_dir=root / "history", source=ROOT,
            status="cold-boot-known-good", notes="Physical NAND reset passed.",
        )
        make_uboot(artifact, bootcmd=b"bootcmd=if lefony_ab boot; then bootz 80800000; fi")
        candidate = history.record_build(
            artifact, history_dir=root / "history", source=ROOT,
            status="unverified", notes="New A/B candidate.",
        )
        entries = history.load_history(root / "history")
        assert entries == [candidate, known]
        assert history.preferred_entry(entries) == known
        assert known.ivt_offset == 0x400
        assert known.bootcmd_mfg == "bootcmd_mfg=run bootcmd;"
        assert "nand read" in known.bootcmd
        assert json.loads((root / "history" / history.INDEX_NAME).read_text())["schema_version"] == 1


def test_history_rejects_non_nand_and_bad_manufacturing_images():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        artifact = root / "u-boot.imx"
        make_uboot(artifact)
        data = bytearray(artifact.read_bytes())
        data[0:4] = history.IVT
        data[0x400:0x404] = b"\0" * 4
        artifact.write_bytes(data)
        try:
            history.record_build(artifact, history_dir=root / "history")
        except ValueError as error:
            assert "0x400" in str(error)
        else:
            raise AssertionError("un-padded U-Boot was accepted")


def test_linux_qualification_preserves_vendor_mfg_without_certifying_lefony():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        artifact = root / "original.imx"
        make_uboot(artifact)
        artifact.write_bytes(artifact.read_bytes().replace(
            b"bootcmd_mfg=run bootcmd;", b"bootcmd_mfg=run mfgtool_args;"
        ))
        entry = history.record_build(
            artifact, history_dir=root / "history",
            status="linux-nand-boot-verified", notes="Linux booted from NAND.",
        )
        assert history.load_history(root / "history")[0] == entry
        assert entry.status not in history.QUALIFIED_STATUSES
        qualified = history.annotate_build(
            root / "history", entry.build_id, status="lefony-nand-boot-verified",
            notes="User confirmed this exact pair booting Lefony from NAND.",
        )
        assert qualified.status in history.QUALIFIED_STATUSES
        assert history.preferred_entry([entry, qualified]) == qualified
        info = history.inspect_image(root / "history" / entry.artifact)
        assert history.validation_errors(info)
        assert history.validation_errors(info, require_nand_handoff=False) == []
        broken = bytearray(artifact.read_bytes())
        broken[0x400:0x404] = b"\0" * 4
        assert history.validation_errors(
            history.inspect_bytes(broken), require_nand_handoff=False
        )


def test_historical_patched_uboot_is_rejected_and_exact_capture_can_be_patched_safely():
    artifact = ROOT / "build/lefony-os-history/artifacts/20260903T045252Z-ram-verified-nonblocking-adc-38cc819c/u-boot-zephray-nandboot-pad.imx"
    if not artifact.is_file():
        return
    info = history.inspect_image(artifact)
    assert "bootcmd was not found" in history.validation_errors(info)
    assert info.sha256 == "cbf3cf8fa0b88a4ab333e6547b049d882eeec09685ec0bbe015775cb04a93650"

    raw = ROOT / "build/prime-g2-a606-emulator/exact-capture/exact-a606-nand.raw"
    if not raw.is_file():
        return
    stream = bytearray()
    with raw.open("rb") as source:
        for page in range(512, 512 + 190):
            source.seek(page * (2048 + 64))
            stream.extend(source.read(2048 + 64)[:2048])
    assert history.inspect_bytes(stream).bootcmd.startswith("bootcmd=nand read")
    patcher.patch(stream, patcher.MODES["nandboot"])
    repaired = history.inspect_bytes(stream)
    assert history.validation_errors(repaired) == []
    assert repaired.bootcmd_mfg == "bootcmd_mfg=run bootcmd;"
