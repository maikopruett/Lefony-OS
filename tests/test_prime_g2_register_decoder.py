import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("decoder", ROOT / "scripts/decode_prime_g2_registers.py")
decoder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(decoder)


def test_golden_capture_decodes_physical_display():
    doc = decoder.capture_directory(ROOT / "hardware/prime_g2/captures/20260831T154107Z")
    assert doc["derived"]["physical_width"] == 320
    assert doc["derived"]["physical_height"] == 240
    assert 59.0 < doc["derived"]["refresh_hz"] < 61.0
    assert doc["derived"]["pixel_clock_source"] == "observed fbset mode"
    assert 49.0 < doc["derived"]["backlight_duty_percent"] < 51.0
    regs = {r["name"]: r for r in doc["records"]}
    assert regs["LCDIF_VDCTRL0"]["decoded"]["dotclk_active_falling"] is False
    assert regs["LCDIF_CTRL2"]["decoded"]["outstanding_requests"] == 5


def test_failed_bounded_probe_is_not_misparsed():
    assert decoder.load_capture(ROOT / "hardware/prime_g2/captures/20260831T154107Z/registers-kpp.txt") == []


def test_kpp_decoder():
    assert decoder.decode("KPP_KPCR", 0xFFFE) == {
        "row_enable_mask": 0xFE, "column_open_drain_mask": 0xFF
    }
