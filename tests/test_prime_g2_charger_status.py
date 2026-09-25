import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / "ports" / "lefony-prime-g2"


class PrimeG2ChargerStatusTests(unittest.TestCase):
    def test_charger_fallback_cannot_overwrite_valid_adc_icon(self):
        source = (PORT / "ion/src/prime_g2/services.cpp").read_text()
        refresh = source.split("void refreshBattery()", 1)[1].split("(void)id", 1)[0]
        fallback = refresh.split("} else if (!sBatteryCalibrated) {", 1)[1]
        self.assertIn("sBatteryLevel = Ion::Battery::Charge::LOW", fallback)
        self.assertIn("sBatteryLevel = Ion::Battery::Charge::SOMEWHERE_INBETWEEN", fallback)
        self.assertNotIn("SOMEWHERE_INBETWEEN", refresh.split("} else if (!sBatteryCalibrated) {", 1)[0])

    def test_pf1550_status_dimensions_are_independent(self):
        source = (PORT / "ion/src/prime_g2/services.cpp").read_text()
        self.assertIn("sExternalPowerPresent = (vbus & PFVbusValid) != 0 &&", source)
        self.assertIn("sBatteryPresent = sBatterySenseState != PFBatteryNotDetected", source)
        self.assertIn("sBatteryFull = chargerRead && batteryRead && sBatteryPresent &&", source)
        self.assertIn("sBatteryCharging = sBatteryTelemetryFresh && sExternalPowerPresent &&", source)
        for state in ("PFChargeTimerFault", "PFChargeThermistorSuspend",
                      "PFChargeBatteryOvervoltage", "PFChargeThermalShutdown",
                      "PFChargeLinearOnly"):
            self.assertIn(f"sChargerState == {state}", source)

    def test_failed_refresh_revokes_stale_charging_claim(self):
        source = (PORT / "ion/src/prime_g2/services.cpp").read_text()
        emulator = (PORT / "ion/src/prime_g2/emulator.cpp").read_text()
        services_test = (ROOT / "vm/test-native-services.sh").read_text()
        self.assertIn("void revokeChargingTelemetry()", source)
        self.assertIn("revokeChargingTelemetry();\n  if (!sChargerConfigured)", source)
        self.assertIn("sBatteryTelemetryFresh = vbusRead && chargerRead && batteryRead", source)
        self.assertIn("sBatteryCharging = sBatteryTelemetryFresh &&", source)
        self.assertIn("BATTERY PF1550 READ FAIL", emulator)
        self.assertIn("BATTERY PF1550 READ FAIL", services_test)
        self.assertIn('test "$(raw BATTERY EXTERNAL)" = "VALUE 0"', services_test)

    def test_native_code_enables_pf1550_battery_charging(self):
        source = (PORT / "ion/src/prime_g2/services.cpp").read_text()
        self.assertIn("PFChargerOperation = 0x89", source)
        self.assertIn("PFChargerBatteryOn = 0x02", source)
        self.assertIn("configurePF1550Charger();", source)
        self.assertIn("PFChargerOperation, &mode, 1", source)
        self.assertIn("(verified & PFChargerModeMask) == PFChargerBatteryOn", source)

    def test_battery_percentage_uses_shipping_hp_adc_algorithm(self):
        adc = (PORT / "ion/src/prime_g2/battery_adc.cpp").read_text()
        services = (PORT / "ion/src/prime_g2/services.cpp").read_text()
        for token in ("ADC1 + 0x0C", "ADCChannelBattery = 1", "0xC3F3",
                      "0x5A3Cu", "raw >= 0xD0 ? 0x2E : 0x16"):
            self.assertIn(token, adc)
        for threshold in ("3501", "3664", "3700", "3863", "3551"):
            self.assertIn(threshold, services)
        self.assertIn("sBatterySamples[10]", services)
        self.assertIn("(total - low - high) / 8", services)
        self.assertIn("BatteryPercentHoldMilliseconds = 30000", services)

    def test_physical_adc_conversion_never_blocks_the_event_loop(self):
        adc = (PORT / "ion/src/prime_g2/battery_adc.cpp").read_text()
        services = (PORT / "ion/src/prime_g2/services.cpp").read_text()
        self.assertIn("sConversionPending", adc)
        self.assertIn("if (!sConversionPending)", adc)
        self.assertIn("(reg32(ADC_HS) & ADCConversionComplete) == 0", adc)
        self.assertNotIn("waitUntilSet", adc)
        self.assertIn("for (unsigned i = 0; i < 20; i++)", services)

    def test_emulator_starts_with_charger_off_and_models_adc1(self):
        model = (ROOT / "vm/qemu/prime_g2_peripherals.c").read_text()
        build = (ROOT / "vm/build-prime-g2-qemu.sh").read_text()
        qtest = (ROOT / "vm/test-prime-g2-peripherals.py").read_text()
        self.assertIn("s->regs[0x89]=0x01", model)
        self.assertIn("charger_enabled = (s->regs[0x89] & 3) == 2", model)
        self.assertIn("external_power ? 0x20 : 0x0c", model)
        self.assertIn("TYPE_PRIME_G2_ADC", model)
        self.assertIn("prime_adc_raw_for_mv", model)
        self.assertIn("qemu-prime-g2-adc.patch", build)
        self.assertIn("PATCHSET_REV=r75", build)
        self.assertIn("writel 0x02198000 0x00000001", qtest)

    def test_title_bar_uses_pmic_vbus_without_changing_usb_data_detection(self):
        patch = (PORT / "patches/prime-g2-power-status.patch").read_text()
        usb = (PORT / "ion/src/prime_g2/usb.cpp").read_text()
        self.assertIn("prime_g2_external_power_present", patch)
        self.assertIn("setIsPlugged(externalPowerPresent())", patch)
        self.assertIn("bool isPlugged() { return PrimeG2::USBDiagnostics::plugged(); }", usb)

    def test_missing_battery_and_fault_have_distinct_ui_states(self):
        source = (PORT / "apps/battery_view.cpp").read_text()
        header = (PORT / "apps/battery_view.h").read_text()
        for token in ("m_batteryPresent", "m_chargerFault"):
            self.assertIn(token, source)
            self.assertIn(token, header)
        self.assertIn("m_chargerFault && m_isPlugged", source)
        self.assertIn("!m_batteryPresent", source)

    def test_emulator_protocol_exercises_every_documented_state(self):
        emulator = (PORT / "ion/src/prime_g2/emulator.cpp").read_text()
        test = (ROOT / "vm/test-native-services.sh").read_text()
        for command in ("BATTERY EXTERNAL", "BATTERY PRESENT", "BATTERY FULL",
                        "BATTERY FAULT", "BATTERY CHARGER STATE",
                        "BATTERY SENSE STATE"):
            self.assertIn(command, emulator)
            self.assertIn(command, test)
        self.assertIn("for charger_state in 0 1 2 3", test)
        self.assertIn("for charger_state in 6 7 9 10 12", test)
        self.assertIn('test "$charging_crc" != "$no_battery_crc"', test)
        self.assertIn('test "$full_crc" != "$charging_crc"', test)
        self.assertIn('test "$fault_crc" != "$full_crc"', test)

    def test_build_applies_power_status_patch(self):
        build = (ROOT / "scripts/build_lefony_prime_g2.sh").read_text()
        self.assertIn('patches/prime-g2-power-status.patch', build)


if __name__ == "__main__":
    unittest.main()
