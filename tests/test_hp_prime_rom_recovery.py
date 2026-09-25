import importlib.util
from pathlib import Path
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_hp_prime_bootmode",
    ROOT / "scripts/analyze_hp_prime_bootmode.py",
)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(audit)


def test_bootmode_audit_finds_addresses_without_emitting_firmware_material():
    payload = b"prefix" + struct.pack("<I", audit.TARGETS["src_gpr9"]) + b"suffix"
    assert audit.occurrences(payload, audit.TARGETS["src_gpr9"]) == [6]
    source = (ROOT / "scripts/analyze_hp_prime_bootmode.py").read_text()
    assert "sha256" not in source.lower()
    assert "read_bytes" in source
    assert '"maximum_mode": 3' in source


def test_qemu_models_persistent_boot_override_and_rom_sdp_usb():
    peripheral = (ROOT / "vm/qemu/prime_g2_peripherals.c").read_text()
    patch = (ROOT / "vm/patches/qemu-prime-g2-rom-recovery.patch").read_text()
    builder = (ROOT / "vm/build-prime-g2-qemu.sh").read_text()
    for token in (
        "prime_usb_rom_device_descriptor",
        "0xa2, 0x15, 0x80, 0x00",
        'mode=%s vid=%04x pid=%04x',
        '"rom-downloader"',
    ):
        assert token in peripheral
    for token in (
        "IMX6_SRC_GPR10_BMODE",
        "IMX6ULL_ROM_USB_CFG",
        "watchdog_reset_pending",
        '"watchdog-reset"',
        '"rom-downloader"',
    ):
        assert token in patch
    assert "qemu-prime-g2-rom-recovery.patch" in builder
    assert "PATCHSET_REV=" in builder
    assert "$QEMU_VERSION-$PATCHSET_REV" in builder


def test_built_qemu_enters_rom_sdp_without_nand_writes():
    qemu = ROOT / "build/qemu-prime-g2/qemu-system-arm"
    if not qemu.exists():
        return
    result = subprocess.run(
        [sys.executable, str(ROOT / "vm/test-prime-g2-rom-recovery.py")],
        cwd=ROOT,
        check=True,
        timeout=20,
        capture_output=True,
        text=True,
    )
    assert "15a2:0080" in result.stdout
    assert "NAND is untouched" in result.stdout
