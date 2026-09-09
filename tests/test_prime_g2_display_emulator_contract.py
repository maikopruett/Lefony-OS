import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
QEMU_PATCH = REPO / "vm/patches/qemu-prime-g2-panel.patch"
QEMU_FIDELITY_PATCH = REPO / "vm/patches/qemu-prime-g2-electrical-fidelity.patch"
QEMU_ILI9322_PATCH = REPO / "vm/patches/qemu-prime-g2-ili9322-datasheet.patch"
RUNNER = REPO / "vm/run-native-vm.sh"
BACKLIGHT = REPO / "ports/lefony-prime-g2/ion/src/prime_g2/backlight.cpp"
TIMING = REPO / "ports/lefony-prime-g2/ion/src/prime_g2/timing.cpp"


class PrimeG2DisplayEmulatorContractTest(unittest.TestCase):
    def test_qemu_models_serial_rgb_and_panel_gates(self) -> None:
        patch = QEMU_PATCH.read_text()
        for contract in (
            "CTRL_WORD_LENGTH_8",
            "PRIME_SERIAL_CYCLES",
            "prime_panel_registers_ready",
            "prime_panel_backlight_ready",
            "PRIME_PANEL_RESET_INCOMPLETE",
            "PRIME_PANEL_NOT_CONFIGURED",
            "PRIME_PANEL_BAD_LCDIF_MODE",
            "CTRL_SFTRST",
            "CTRL_CLKGATE",
            '"prime-g2-pwm7"',
            '"prime-g2-panel"',
        ):
            self.assertIn(contract, patch)

    def test_qemu_enforces_prime_electrical_and_timing_contracts(self) -> None:
        patch = QEMU_FIDELITY_PATCH.read_text()
        for contract in (
            "prime_panel_iomux_ready",
            "prime_panel_pixel_clock_hz",
            "prime_panel_timing_ready",
            "prime_panel_polarity_ready",
            "PRIME_RESET_PHASE_NS",
            "PRIME_PANEL_RECOVERY_NS",
            "PRIME_MIN_SPI_HALF_NS",
            "PRIME_MIN_SPI_HOLD_NS",
            "PRIME_CTRL1_UNDERFLOW_IRQ",
            "PRIME_CTRL1_RECOVER",
            "LCDIF FIFO underflow recovered",
            '"prime-g2-fault-iomux"',
            '"prime-g2-fault-signal"',
            '"prime-g2-fault-timing"',
            '"prime-g2-fault-polarity"',
            '"prime-g2-fault-power"',
            '"prime-g2-fault-fifo"',
        ):
            self.assertIn(contract, patch)
        # Working Linux leaves VDCTRL0 DOTCLK_ACT_FALLING (bit 25) clear.
        self.assertIn("(1u << 27) | (1u << 26) | (1u << 25)", patch)
        required_line = next(
            line for line in patch.splitlines()
            if "uint32_t required =" in line
        )
        self.assertNotIn("1u << 25", required_line)

    def test_qemu_models_the_ili9322_datasheet_contract(self) -> None:
        patch = QEMU_ILI9322_PATCH.read_text()
        for contract in (
            "prime_ili9322_reset_registers",
            "prime_ili9322_write_mask",
            "ILI9322_POWER_CONTROL",
            "ILI9322_DISPLAY_CONTROL",
            "PRIME_PANEL_STARTUP_WHITE",
            "prime_panel_white_until_ns",
            "PRIME_MIN_SPI_SETUP_NS",
            "PRIME_MIN_SPI_CS_NS",
            "VMSTATE_UINT8_ARRAY_V(prime_panel_regs",
            "ILI9322 is in standby or display-off state",
            "if (!(s->prime_panel_regs[ILI9322_POLARITY] & (1u << 6)))",
            "s->prime_panel_regs[0x0a] = 0x49",
        ):
            self.assertIn(contract, patch)

    def test_delay_timer_divides_owned_24_mhz_perclk_to_3_mhz(self) -> None:
        source = TIMING.read_text()
        self.assertIn("CR_CLKSRC = 2u << 6", source)
        self.assertIn("Prescaler = 7", source)
        self.assertIn("TICKS_PER_MICROSECOND = 3", source)
        self.assertIn("updateBits(CCM + 0x1C, (1u << 6) | 0x3Fu, 1u << 6)", source)

    def test_vm_enables_prime_panel_and_supports_capsule_handoff(self) -> None:
        runner = RUNNER.read_text()
        self.assertIn("imx6ul-lcdif.prime-g2-panel=on", runner)
        self.assertIn("--capsule", runner)
        self.assertIn("lefony-os-vm.zImage", runner)
        self.assertIn("build_prime_g2_nand_capsule.sh", runner)
        for fault in ("iomux", "signal", "timing", "polarity", "power", "fifo"):
            self.assertIn(fault, runner)

    def test_comprehensive_suite_runs_display_fidelity_regression(self) -> None:
        suite = (REPO / "vm/native-suite.py").read_text()
        self.assertIn("test-native-display-fidelity.sh", suite)
        self.assertIn("NATIVE_DISPLAY_FIDELITY_DIR", suite)

    def test_guest_never_bypasses_backlight_hardware(self) -> None:
        source = BACKLIGHT.read_text()
        self.assertNotIn("PRIME_G2_EMULATOR", source)
        self.assertIn("PrimeG2::reg32(PWMCR)", source)
        self.assertIn("PrimeG2::gpioWrite(PrimeG2::GPIO2, 21, true)", source)


if __name__ == "__main__":
    unittest.main()
