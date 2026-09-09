import pathlib
import re
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
DISPLAY = REPO / "ports/lefony-prime-g2/ion/src/prime_g2/display.cpp"
SERVICES = REPO / "ports/lefony-prime-g2/ion/src/prime_g2/services.cpp"
BACKLIGHT = REPO / "ports/lefony-prime-g2/ion/src/prime_g2/backlight.cpp"


def function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError(f"unterminated function: {signature}")


class PhysicalDisplayContractTest(unittest.TestCase):
    def test_cold_boot_reveals_only_a_completed_black_initialized_frame(self):
        display = DISPLAY.read_text()
        init = function_body(display, "void init()")
        self.assertIn("sFramebuffer[i] = 0x00000000", init)
        self.assertNotIn("sFramebuffer[i] = 0x00FFFFFF", init)
        ready = function_body(display, 'extern "C" void prime_g2_first_frame_ready()')
        self.assertLess(ready.index("Ion::Timing::msleep(20)"),
                        ready.index("PrimeG2::Backlight::reveal()"))

        board = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/board.cpp").read_text()
        board_init = function_body(board[board.index("namespace Board"):], "void init()")
        self.assertIn("PrimeG2::Backlight::prepare()", board_init)
        self.assertNotIn("Display::showBootSplash()", board_init)
        self.assertNotIn("Ion::Backlight::init()", board_init)

        backlight = BACKLIGHT.read_text()
        prepare = function_body(backlight, "void prepare()")
        reveal = function_body(backlight, "void reveal()")
        init_backlight = function_body(backlight, "void init()")
        self.assertIn("configureHardware()", prepare)
        self.assertIn("sRevealDeferred = true", prepare)
        self.assertNotIn("GPIO2, 21, true", prepare)
        self.assertIn("gpioWrite(PrimeG2::GPIO2, 21, true)", reveal)
        self.assertIn("if (!sRevealDeferred)", init_backlight)

        progress = (REPO / "ports/lefony-prime-g2/patches/physical-boot-progress.patch").read_text()
        self.assertNotIn("PrimeG2BeginApplicationDraw()", progress)
        self.assertNotIn('include "lefony_splash.h"', display)
        redraw = progress[progress.index("void Window::redraw(bool force)"):]
        self.assertLess(redraw.index("View::redraw(bounds())"),
                        redraw.index("PrimeG2FirstFrameReady()"))
        self.assertIn("#define PRIME_G2_VISIBLE_BOOT_DIAGNOSTICS 0", display)

    def test_physical_off_uses_interrupt_wake_and_resumes(self):
        source = SERVICES.read_text()
        suspend = function_body(source, "void suspend(bool checkIfOnOffKeyReleased)")
        physical = suspend.split("#else", 1)[1].split("#endif", 1)[0]
        self.assertIn("if (checkIfOnOffKeyReleased)", physical)
        self.assertIn("while (PrimeG2::Services::onKeyPressed())", physical)
        self.assertIn("armPowerWakeSources()", physical)
        self.assertIn("while (!sPowerWakeRequested)", physical)
        self.assertIn('__asm volatile("wfi"', physical)
        self.assertIn("disarmPF1550Wake()", physical)
        self.assertNotIn("while (!PrimeG2::Services::onKeyPressed())", physical)
        self.assertIn("PrimeG2::Display::resume()", physical)
        self.assertIn("Ion::Backlight::init()", physical)
        self.assertIn("PrimeG2::Touch::init()", physical)
        self.assertIn("sPowerSuspended = false", physical)
        self.assertNotIn("PrimeG2::Services::powerOff()", physical)

    def test_panel_and_backlight_have_electrical_off_sequences(self):
        display = DISPLAY.read_text()
        standby = function_body(display, "void enterPanelStandby()")
        self.assertLess(standby.index("panelRegister(0x30, 0x09)"),
                        standby.index("panelRegister(0x07, 0xEE)"))
        self.assertIn("Ion::Timing::msleep(100)", standby)
        shutdown = function_body(display, "void shutdown()")
        self.assertLess(shutdown.index("enterPanelStandby()"),
                        shutdown.index("reg32(LCDIF + 0x08)"))

        backlight = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/backlight.cpp").read_text()
        off = function_body(backlight, "void shutdown()")
        self.assertLess(off.index("reg32(PWMSAR) = 0"),
                        off.index("reg32(PWMCR) = 0"))
        self.assertIn("gpioWrite(PrimeG2::GPIO4, 19, false)", off)
        self.assertIn("gpioWrite(PrimeG2::GPIO2, 21, false)", off)

    def test_full_shutdown_prepares_pf1550_then_sets_snvs_top(self):
        source = SERVICES.read_text()
        configure = function_body(source, "bool configurePF1550ForPowerOff()")
        self.assertIn("PFPwrOnResetEnable | PFRestartEnable | PFOnKeyResetEnable", configure)
        self.assertIn("PFGotoCoreOff", configure)
        self.assertNotIn("PFGotoShip", configure)
        off = function_body(source, "[[noreturn]] void powerOff()")
        self.assertLess(off.index("configurePF1550ForPowerOff()"),
                        off.index("SNVSPowerOff"))
        self.assertIn("setBits(SNVSLPCR", off)
        self.assertNotIn("reg32(SNVSLPCR) =", off)
        standby = function_body(source, "void standby()")
        self.assertIn("PrimeG2::Services::powerOff()", standby)
        self.assertNotIn("suspend(false)", standby)

    def test_cold_boot_explicitly_enables_verified_lcd_supply(self):
        source = SERVICES.read_text()
        supply = function_body(source, "bool configureLCDSupply()")
        self.assertIn("PFLdo1Voltage3300mV", supply)
        self.assertIn("PFLdo1Enable | PFLdo1StandbyEnable", supply)
        self.assertIn("Ion::Timing::msleep(10)", supply)
        self.assertGreaterEqual(supply.count("PrimeG2::I2C::read8"), 2)
        init = function_body(source, "void init()")
        self.assertIn("configureLCDSupply()", init)
        board = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/board.cpp").read_text()
        board_init = function_body(board[board.index("namespace Board"):], "void init()")
        self.assertLess(board_init.index("Services::init()"),
                        board_init.index("Display::init()"))

    def test_prime_dpad_repeat_is_disabled_without_disabling_backspace(self):
        policy = (REPO / "ports/lefony-prime-g2/patches/prime-g2-single-step-dpad.patch").read_text()
        for event in ("Left", "Up", "Down", "Right", "ShiftLeft",
                      "ShiftUp", "ShiftDown", "ShiftRight"):
            self.assertIn(f"Events::{event}", policy)
        self.assertIn("return false", policy)
        self.assertNotIn("e == Events::Backspace) return false", policy)

    def test_physical_vblank_does_not_wait_on_unobservable_panel_signal(self):
        source = DISPLAY.read_text()
        function = source[source.index("bool waitForVBlank()") : source.index(
            "void POSTPushMulticolor", source.index("bool waitForVBlank()")
        )]
        self.assertIn("return presentFrame()", function)
        # The shared presenter has bounded polling; physical delays remain
        # independent of the runtime GPT clock.
        hardware = source[source.index("struct PresentationHardware"):source.index("bool presentFrame()")]
        self.assertIn("#if PRIME_G2_EMULATOR", hardware)
        self.assertIn("uint32_t loops = 13200", hardware)

    def test_only_physical_runtime_delays_bypass_gpt(self):
        timing = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/timing.cpp").read_text()
        delay = function_body(timing, "void usleep(uint32_t us)")
        self.assertIn("if (sRuntimeDelays)", delay)
        self.assertIn("uint32_t loops = 132", delay)
        self.assertIn("uint32_t start = ticks()", delay)
        board = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/board.cpp").read_text()
        init = function_body(board[board.index("namespace Board"):], "void init()")
        self.assertGreater(init.index("Timing::enterRuntime()"),
                           init.index("Display::init()"))

    def test_physical_bringup_does_not_arm_watchdog(self):
        watchdog = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/watchdog.cpp").read_text()
        init = function_body(watchdog, "void init()")
        poll = function_body(watchdog, "void poll(bool healthy)")
        self.assertIn("#if PRIME_G2_EMULATOR", init)
        self.assertIn("sEnabled = false", init)
        self.assertIn("sEnabled = (reg16(WCR) & Enable) != 0", init)
        physical_poll = poll.split("#if !PRIME_G2_EMULATOR", 1)[1].split("#else", 1)[0]
        self.assertNotIn("reg16(WCR) =", physical_poll)
        self.assertIn("if (sEnabled) feed()", physical_poll)

    def test_physical_keypad_uses_gpio_matrix_without_kpp_mmio(self):
        keyboard = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/keyboard.cpp").read_text()
        init = function_body(keyboard, "void init()")
        self.assertIn("#if PRIME_G2_EMULATOR", init)
        self.assertIn("mux(muxOffsets[i], padOffsets[i], 5", init)
        self.assertIn("GPIO_COLUMN_MASK", init)
        scan = function_body(keyboard, "void scanMatrix(uint8_t state[8])")
        physical = scan.split("#else", 1)[1].split("#endif", 1)[0]
        self.assertIn("PrimeG2::GPIO2 + 0x08", physical)
        self.assertIn("GPIO_COLUMN_MASK", physical)
        self.assertNotIn("reg16(KPDR)", physical)
        self.assertNotIn("Ion::Timing::usleep", physical)
        self.assertIn("settleGPIOMatrix()", physical)

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = DISPLAY.read_text()

    def test_ili9322_sequence_combines_prime_values_with_datasheet_power_order(self) -> None:
        reset = function_body(self.source, "void preparePanelReset()")
        body = function_body(self.source, "void initPanel()")

        reset_expected = [
            "gpioWrite(PrimeG2::GPIO3, 4, false)",
            "msleep(20)",
            "gpioWrite(PrimeG2::GPIO3, 4, true)",
            "msleep(10)",
            "gpioWrite(PrimeG2::GPIO3, 4, false)",
            "msleep(10)",
        ]
        cursor = 0
        for operation in reset_expected:
            cursor = reset.index(operation, cursor) + len(operation)

        expected = [
            "gpioWrite(PrimeG2::GPIO3, 4, true)",
            "msleep(120)",
            "panelRegister(0x07, 0xEE)",
            "panelRegister(0x01, 0x14)",
            "panelRegister(0x02, 0x3A)",
            "panelRegister(0x05, 0x67)",
            "panelRegister(0x06, 0x0F)",
            "panelRegister(0x0A, 0x49)",
            "panelRegister(0x0B, 0x05)",
            "panelRegister(0x07, 0xEF)",
            "msleep(200)",
            "panelRegister(0x30, 0x0D)",
            "msleep(400)",
        ]
        cursor = 0
        for operation in expected:
            cursor = body.index(operation, cursor) + len(operation)

        init = function_body(self.source, "void init()")
        self.assertLess(init.index("preparePanelReset()"),
                        init.index("initController()"))
        self.assertLess(init.index("initController()"), init.index("initPanel()"))
        self.assertNotIn("panelRegister(0x04", body)
        self.assertNotIn("PRIME_G2_EMULATOR", body)

    def test_serial_rgb_lcdif_encoding_matches_prime_linux_patch(self) -> None:
        body = function_body(self.source, "void initController()")
        compact = re.sub(r"\s+", " ", body)
        self.assertIn(
            "(1u << 14) | (1u << 8) | (1u << 10)", compact
        )
        self.assertIn("TransferWidth = Width * 3", compact)
        self.assertIn("reg32(base + 0x10) = 7u << 16", compact)
        self.assertIn("reg32(base + 0x30) = (Height << 16) | TransferWidth", compact)
        self.assertNotIn("PRIME_G2_EMULATOR", body)

    def test_lcdif_polarity_matches_live_working_linux(self) -> None:
        body = function_body(self.source, "void initController()")
        self.assertNotIn("VDCTRL0_DOTCLK_FALLING", body)
        self.assertIn("working Prinux register snapshot is 0x11300001", body)

    def test_elcdif_uses_required_stmp_reset_handshake(self) -> None:
        body = function_body(self.source, "bool resetController(uintptr_t base)")
        expected = [
            "reg32(base + 0x08) = CTRL_SFTRST",
            "waitForControllerBit(base, CTRL_SFTRST, false)",
            "reg32(base + 0x08) = CTRL_CLKGATE",
            "reg32(base + 0x04) = CTRL_SFTRST",
            "waitForControllerBit(base, CTRL_CLKGATE, true)",
            "reg32(base + 0x08) = CTRL_SFTRST",
            "waitForControllerBit(base, CTRL_SFTRST, false)",
            "reg32(base + 0x08) = CTRL_CLKGATE",
            "waitForControllerBit(base, CTRL_CLKGATE, false)",
        ]
        cursor = 0
        for operation in expected:
            cursor = body.index(operation, cursor) + len(operation)


if __name__ == "__main__":
    unittest.main()
