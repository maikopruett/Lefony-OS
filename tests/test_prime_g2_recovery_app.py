from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recovery_is_not_a_launcher_app():
    platform = (
        ROOT / "ports/lefony-prime-g2/build/platform.prime_g2.mak"
    ).read_text()
    apps = next(line for line in platform.splitlines() if line.startswith("EPSILON_APPS ="))
    assert "recovery" not in apps.split()
    assert "regression settings" in apps


def test_recovery_app_requests_one_shot_rom_usb_boot():
    app = (
        ROOT / "ports/lefony-prime-g2/apps/recovery/app.cpp"
    ).read_text()
    watchdog = (
        ROOT / "ports/lefony-prime-g2/ion/src/prime_g2/watchdog.cpp"
    ).read_text()
    assert "rebootToROMRecovery()" in app
    assert "reg32(SRCGPR9) = ROMUSBBoot" in watchdog
    assert "reg32(SRCGPR10) = BootModeEnable" in watchdog
    assert 'asm volatile("cpsid if"' in watchdog
    recovery = watchdog.split("[[noreturn]] void rebootToROMRecovery()", 1)[1].split("bool enabled()", 1)[0]
    assert "internalReset = Enable | (1u << 4)" in recovery
    assert recovery.count("reg16(WCR) = internalReset") == 3
    assert 'asm volatile("wfi")' not in recovery
    assert "reg32(PrimeG2::SRC) &= ~1u" in recovery
    assert "reg32(PrimeG2::CCM + 0x74) |= 3u << 16" in recovery
    assert "recordResetReason(" not in recovery
    assert "reg16(WMCR) = 0" in recovery
    assert "Ion::Timing::msleep(1000)" in recovery
    first = recovery.index("reg16(WCR) = internalReset")
    ping = recovery.index("reg16(WSR) = 0x5555", first)
    ping_end = recovery.index("reg16(WSR) = 0xAAAA", ping)
    second = recovery.index("reg16(WCR) = internalReset", first + 1)
    assert first < ping < ping_end < second
    assert recovery.index("msleep(1000)") < recovery.index("cpsid if") < first


def test_all_app_suite_uses_settings_without_recovery_slot():
    suite = (ROOT / "vm/native-app-test.py").read_text()
    assert '("Settings", 11)' in suite
    assert "Recovery is launcher slot 11" not in suite
