import importlib.util
import struct
import unittest
import tempfile
from unittest.mock import Mock, patch
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "prime_g2_usb_diag.py"
SPEC = importlib.util.spec_from_file_location("prime_g2_usb_diag", SCRIPT)
diag = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(diag)


class PrimeG2UsbDiagnosticsTests(unittest.TestCase):
    def test_elapsed_clock_is_read_only_and_64_bit(self):
        device = Mock()
        device.read.return_value = struct.pack("<4I", 0x3143544c, 1, 123, 2)
        self.assertEqual(diag.elapsed_millis(device), (2 << 32) + 123)
        device.read.assert_called_once_with(0x55, value=2, length=16)
        device.write.assert_not_called()
        for response in (b"", bytes(16), struct.pack("<4I", 0x3143544c, 2, 0, 0)):
            device.read.return_value = response
            with self.assertRaises(diag.USBError):
                diag.elapsed_millis(device)

    def test_battery_display_status_is_read_only_and_validated(self):
        device = Mock()
        device.read.return_value = struct.pack("<4I", 0x3154424c, 1, 3, 100)
        self.assertEqual(diag.battery_display_status(device), {"level": 3, "percent": 100})
        device.read.assert_called_once_with(0x55, value=1, length=16)
        device.write.assert_not_called()
        for response in (b"", bytes(16), struct.pack("<4I", 0x3154424c, 1, 4, 101)):
            device.read.return_value = response
            with self.assertRaises(diag.USBError):
                diag.battery_display_status(device)

    def test_battery_diagnostics_are_read_only_and_versioned(self):
        device = Mock()
        words = [0x3154424c, 1] + list(range(2, 24))
        words[15:18] = [211, 3853, 1]
        device.read.return_value = struct.pack("<24I", *words)
        result = diag.battery_diagnostics(device)
        self.assertEqual((result["raw"], result["millivolts"], result["valid"]),
                         (211, 3853, 1))
        device.read.assert_called_once_with(0x55, length=96)
        device.write.assert_not_called()
        for response in (b"", bytes(96), struct.pack("<24I", 0x3154424c, 2, *range(22))):
            device.read.return_value = response
            with self.assertRaises(diag.USBError):
                diag.battery_diagnostics(device)

    def test_native_installer_waits_for_verified_completion(self):
        ready = {"state": 2, "length": 4096, "received": 4096, "crc32": 0xabcd1234}
        device = Mock()
        states = [{"state": n, "done": 4096 if n == 8 else 0, "total": 4096,
                   "error": 0, "changed": int(n > 5), "crc": ready["crc32"]}
                  for n in (4, 5, 6, 7, 8)]
        with patch.object(diag, "development_capabilities", return_value={"flags": 3}), \
             patch.object(diag, "stage_capsule", return_value=ready), \
             patch.object(diag, "native_install_status", side_effect=states), \
             patch.object(diag.time, "sleep"):
            self.assertEqual(diag.install_native_capsule(device, Path("unused"))["state"], 8)
        device.write.assert_called_once_with(0x53, value=0x1234, index=0xabcd)

    def test_native_installer_does_not_reboot_or_retry_write_failure(self):
        device = Mock()
        ready = {"state": 2, "length": 4096, "received": 4096, "crc32": 1}
        with patch.object(diag, "development_capabilities", return_value={"flags": 3}), \
             patch.object(diag, "stage_capsule", return_value=ready), \
             patch.object(diag, "native_install_status", return_value={"state": 9, "changed": 1}):
            with self.assertRaisesRegex(diag.USBError, "keep power"):
                diag.install_native_capsule(device, Path("unused"))
        self.assertEqual(device.write.call_count, 1)
        self.assertEqual(device.write.call_args.args, (0x53,))

    def test_readback_inhibits_app_suspend_only_while_usb_is_active(self):
        root = REPO / "ports/lefony-prime-g2/ion/src/prime_g2"
        source = (root / "usb_diagnostics.cpp").read_text()
        active = source.split("bool managementActive()", 1)[1].split("\n}", 1)[0]
        self.assertIn("StatusConfigured", active)
        self.assertIn("sLastManagementTime < 2000", active)
        self.assertIn("USBDiagnostics::managementActive()", (root / "nand_update.cpp").read_text())

    def test_ecc_image_compare_and_fail_closed_cases(self):
        payload = bytearray((i * 17) & 255 for i in range(3000))
        struct.pack_into("<I", payload, 0x24, 0x016f2818)
        struct.pack_into("<I", payload, 0x2c, len(payload))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.zImage"
            path.write_bytes(payload)
            def read(device, page):
                offset = (page - 2048) * 2048
                return bytes(payload[offset:offset + 2048]).ljust(2048, b"\xff"), {
                    "marker": 255, "corrected": 1}
            with patch.object(diag, "read_nand_page", side_effect=read):
                result = diag.verify_nand_image(Mock(), path)
                self.assertEqual(result["verified_bytes"], 3000)
                self.assertEqual(result["corrected_bits"], 2)
                self.assertEqual(result["sha256"], diag.hashlib.sha256(payload).hexdigest())
            with patch.object(diag, "read_nand_page", return_value=(bytes(2048), {"marker": 255})):
                with self.assertRaisesRegex(diag.USBError, "differs"):
                    diag.verify_nand_image(Mock(), path)
            with patch.object(diag, "read_nand_page", return_value=(bytes(2048), {"marker": 0})):
                with self.assertRaisesRegex(diag.USBError, "bad block"):
                    diag.verify_nand_image(Mock(), path)

    def test_page_error_never_returns_stale_data(self):
        device = Mock()
        device.read.return_value = struct.pack("<6I", 0x3152504c, 2048, 9, 0, 255, 0)
        with self.assertRaisesRegex(diag.USBError, "rejected"):
            diag.read_nand_page(device, 2048)
        self.assertEqual(device.read.call_count, 1)
        device.write.reset_mock()
        with self.assertRaises(diag.USBError):
            diag.read_nand_page(device, 0)
        device.write.assert_not_called()

    def test_read_only_nand_probe_contract(self):
        device = Mock()
        words = [0x31504e4c, 1, 0, 3, 0x9590dcec, 0] + [0] * 12
        device.read.return_value = struct.pack("<18I", *words)
        result = diag.probe_nand(device)
        self.assertEqual(result["nand_id_hex"], "ecdc909500000000")
        self.assertFalse(result["probe_wrote_nand"])
        device.write.assert_called_once_with(0x50, value=0x4e50)
        device.read.return_value = b"short"
        with self.assertRaises(diag.USBError):
            diag.probe_nand(device)

    def test_physical_nand_probe_cannot_program_or_erase(self):
        source = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/nand_physical.cpp").read_text()
        self.assertIn("sCommand[0] = 0x90", source)
        import re
        probe = source.split("bool probe()", 1)[1].split("const Report &report", 1)[0]
        self.assertEqual(set(re.findall(r"sCommand\[0\] = (0x[0-9a-f]+)", probe)), {"0x90"})
        self.assertIn("attempt < 2000", source)
        self.assertIn("cleanDataCacheRange(&sDescriptor", source)
        self.assertIn("invalidateDataCacheRange(sData", source)
        self.assertNotIn("GPMI + 0x100", source)
        header = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/nand_physical.h").read_text()
        self.assertIn("block < 32 || block >= 96", source)
        self.assertIn("page < 2048 || page >= 6144", source)

    def test_development_handoff_contract(self):
        device = Mock()
        device.read.return_value = struct.pack("<4I", 0x3156444c, 1, 1, 8 << 20)
        self.assertEqual(diag.development_capabilities(device)["version"], 1)
        diag.request_development_recovery(device,
            {"state": 2, "received": 4096, "length": 4096, "crc32": 0x1234abcd})
        device.write.assert_called_once_with(0x4E, value=0xabcd, index=0x1234, timeout_ms=10000)
        device.write.reset_mock()
        with self.assertRaises(diag.USBError):
            diag.request_development_recovery(device,
                {"state": 1, "received": 512, "length": 4096, "crc32": 0})
        device.write.assert_not_called()
        device.read.side_effect = diag.USBError("stall")
        with self.assertRaisesRegex(diag.USBError, "bootstrap"):
            diag.development_capabilities(device)

    def test_development_handoff_is_crc_and_status_ack_gated(self):
        source = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/usb_diagnostics.cpp").read_text()
        request = source.split("case 0x4E: // explicit development", 1)[1].split("case 0x4C:", 1)[0]
        self.assertIn("sRecoveryState != RecoveryState::Ready", request)
        self.assertIn("setupValue32(setup) != sRecoveryCRC", request)
        self.assertNotIn("rebootToROMRecovery()", request)
        for function in ("handleSetup", "handleBusReset"):
            body = source.split(f"void {function}() {{", 1)[1].split("\n}", 1)[0]
            self.assertIn("sRecoveryAfterStatus = false", body)

    def test_ram_upload_progress_and_failure_cleanup(self):
        payload = bytearray(1100)
        struct.pack_into("<I", payload, 0x24, 0x016F2818)
        struct.pack_into("<I", payload, 0x2C, len(payload))
        checksum = diag.ion_crc32(payload)
        class Device:
            def __init__(self, fail=False, bad_crc=False):
                self.writes = []
                self.fail, self.bad_crc = fail, bad_crc
            def read(self, *args, **kwargs):
                ready = any(w[0] == diag.REQUEST_RECOVERY_FINISH for w in self.writes)
                return struct.pack("<8I", 0x4D475243, 1, 2 if ready else 0,
                                   8 << 20, len(payload), len(payload) if ready else 0,
                                   checksum ^ int(self.bad_crc), 512)
            def write(self, request, data=b"", value=0, index=0):
                self.writes.append((request, data, value, index))
                if self.fail and request == diag.REQUEST_RECOVERY_CHUNK:
                    raise diag.USBError("transfer interrupted")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.zImage"
            path.write_bytes(payload)
            device = Device()
            progress = []
            diag.stage_capsule(device, path, lambda n, total: progress.append(n))
            self.assertEqual(progress, [0, 512, 1024, 1100])
            chunks = [w for w in device.writes if w[0] == diag.REQUEST_RECOVERY_CHUNK]
            self.assertEqual([w[2] for w in chunks], [0, 512, 1024])
            self.assertEqual(b"".join(w[1] for w in chunks), payload)
            self.assertNotIn(diag.REQUEST_UPDATE_COMMIT, [w[0] for w in device.writes])
            for broken in (Device(fail=True), Device(bad_crc=True)):
                with self.assertRaises(diag.USBError):
                    diag.stage_capsule(broken, path)
                self.assertEqual(broken.writes[-1][0], diag.REQUEST_RECOVERY_ABORT)
            path.write_bytes(b"not a capsule")
            untouched = Device()
            with self.assertRaises(diag.USBError):
                diag.stage_capsule(untouched, path)
            self.assertEqual(untouched.writes, [])

    def test_upload_polling_remains_bounded(self):
        source = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/usb_diagnostics.cpp").read_text()
        poll = source.split("void poll() {", 1)[1].split("uint32_t statusFlags", 1)[0]
        self.assertIn("uploadPoll < 200", poll)
        self.assertIn("sRecoveryState != RecoveryState::Receiving", poll)
        self.assertIn("sStatus & StatusError", poll)

    def test_info_contract(self):
        values = [diag.INFO_MAGIC, 1, 0x17, 2, 7, 28, 256, 128] + [0] * 8
        info = diag.decode_info(struct.pack("<16I", *values))
        self.assertEqual(info["event_size"], 28)
        self.assertEqual(info["snapshot_size"], 256)

    def test_event_contract(self):
        data = struct.pack("<7I", diag.EVENT_MAGIC, 3, 900, 0x0223, 1, 2, 3)
        event = diag.decode_event(data)
        self.assertEqual(event["name"], "LCDIF_STARTED")
        self.assertEqual(event["timestamp_ms"], 900)

    def test_recovery_status_contract(self):
        class Device:
            def read(self, request, value=0, index=0, length=64):
                self.request = request
                return struct.pack("<8I", 0x4D475243, 1, 2, 8 << 20,
                                   4096, 4096, 0x1234, 512)
        device = Device()
        status = diag.recovery_info(device)
        self.assertEqual(device.request, diag.REQUEST_RECOVERY_INFO)
        self.assertEqual(status["state"], 2)
        self.assertEqual(status["max_chunk"], 512)

    def test_uploader_crc_matches_ion_firmware(self):
        self.assertEqual(diag.ion_crc32(bytes((0x6C,))), 0xD7A1E247)
        self.assertEqual(diag.ion_crc32(bytes((0x6C, 0x6C, 0x65, 0x48))),
                         0x93591FFD)

    def test_analyzer_separates_framebuffer_from_transport(self):
        words = [0] * 64
        words[0] = diag.SNAPSHOT_MAGIC
        words[10] = 1
        words[13] = (240 << 16) | 960
        words[14] = 0x8F000040
        words[28] = 1 << 4
        words[29] = 1 << 4
        words[54:59] = [0x123456] * 5
        words[60] = (1 << 30) | (1 << 31)
        snapshot = diag.decode_snapshot(struct.pack("<64I", *words))
        report = {
            "info": {"status": 7},
            "events": [{"name": "LCDIF_STARTED"}],
            "snapshot": snapshot,
        }
        result = " ".join(diag.analyze(report))
        self.assertIn("downstream", result)
        self.assertNotIn("UI rendering did not", result)

    def test_analyzer_reports_cpu_exception(self):
        words = [0] * 64
        words[0] = diag.SNAPSHOT_MAGIC
        report = {
            "info": {"status": 7},
            "events": [{
                "name": "FATAL_EXCEPTION", "value0": 4,
                "value1": 0x82001234, "value2": 0x600001D7,
            }],
            "snapshot": diag.decode_snapshot(struct.pack("<64I", *words)),
        }
        result = " ".join(diag.analyze(report))
        self.assertIn("CPU exception captured", result)
        self.assertIn("82001234", result)

    def test_analyzer_identifies_charger_off_with_battery_and_vbus(self):
        words = [0] * 64
        words[0] = diag.SNAPSHOT_MAGIC
        words[61] = (1 << 16) | (1 << 18) | (1 << 21) | (1 << 22) | (1 << 24)
        words[60] = (1 << 30) | (1 << 31)
        report = {
            "info": {"status": 7},
            "events": [{"name": "LCDIF_STARTED"}],
            "snapshot": diag.decode_snapshot(struct.pack("<64I", *words)),
        }
        result = " ".join(diag.analyze(report))
        self.assertIn("CHG_OPER is mode 1", result)
        self.assertIn("charging is disabled", result)

    def test_firmware_usb_waits_are_bounded(self):
        source = (REPO / "ports" / "lefony-prime-g2" / "ion" / "src" /
                  "prime_g2" / "usb_diagnostics.cpp").read_text()
        self.assertNotIn("while (reg32(ENDPTPRIME) != 0)", source)
        self.assertIn("waitFor(ENDPTPRIME", source)
        self.assertIn("waitFor(ENDPTFLUSH", source)

    def test_enable_preserves_active_controller_and_first_error(self):
        source = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/usb_diagnostics.cpp").read_text()
        init = source.split("bool init() {", 1)[1].split("void poll()", 1)[0]
        self.assertLess(init.index("if (sStatus & StatusController)"),
                        init.index("NANDUpdate::init()"))
        self.assertIn("if (!sFirstErrorStep) sFirstErrorStep = step", source)
        shutdown = source.split("void shutdown()", 1)[1]
        self.assertIn("~(StatusConfigured | StatusController)", shutdown)

    def test_enumeration_trace_survives_bus_reset(self):
        source = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/usb_diagnostics.cpp").read_text()
        reset = source.split("void handleBusReset()", 1)[1].split("void handleComplete", 1)[0]
        self.assertIn("sEnumeration.resets++", reset)
        self.assertNotIn("sEnumeration.phase =", reset)
        self.assertNotIn("sEnumeration.request =", reset)
        self.assertIn("setup.requestType == 0xC0 && setup.request == 0x4D", source)

    def test_queue_publication_and_bounded_setup_tripwire(self):
        source = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/usb_diagnostics.cpp").read_text()
        init = source.split("void initializeQueueHeads()", 1)[1].split("bool resetController()", 1)[0]
        self.assertIn("cleanDataCacheRange(&sControllerMemory", init)
        setup = source.split("void handleSetup()", 1)[1].split("void handleBusReset()", 1)[0]
        self.assertIn("attempt < 16", setup)
        self.assertIn("SetupTripwire = 1u << 13", setup)
        self.assertLess(setup.index("reg32(USBCMD) |= SetupTripwire"), setup.index("destination[i] = source[i]"))
        self.assertIn("reg32(USBCMD) &= ~SetupTripwire", setup)
        self.assertIn("fail(14, USBCMD)", setup)

    def test_set_address_defers_register_write_until_status_completion(self):
        source = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/usb_diagnostics.cpp").read_text()
        request = source.split("case 5: // SET_ADDRESS", 1)[1].split("case 6:", 1)[0]
        self.assertIn("sPendingAddress = setup.value", request)
        self.assertNotIn("reg32(DEVICEADDR)", request)
        complete = source.split("void handleComplete", 1)[1].split("bool init()", 1)[0]
        self.assertIn("static_cast<uint32_t>(sPendingAddress) << 25", complete)
        self.assertIn("sPendingAddress >= 0", complete)
        for function in ("handleSetup", "handleBusReset", "shutdown"):
            body = source.split(f"void {function}() {{", 1)[1]
            self.assertIn("sPendingAddress = -1", body.split("\n}", 1)[0])

    def test_address_fast_path_is_bounded_and_ack_gated(self):
        source = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/usb_diagnostics.cpp").read_text()
        fast = source.split("void finishAddressStatusPromptly()", 1)[1].split("constexpr uint8_t DeviceDescriptor", 1)[0]
        self.assertIn("attempt < 2000", fast)
        self.assertIn("InterruptReset", fast)
        self.assertIn("reg32(ENDPTSETUPSTAT) & 1u", fast)
        self.assertLess(fast.index("reg32(ENDPTCOMPLETE) & (1u << 16)"), fast.index("handleComplete(1u << 16)"))
        self.assertNotIn("reg32(DEVICEADDR)", fast)
        request = source.split("case 5: // SET_ADDRESS", 1)[1].split("case 6:", 1)[0]
        self.assertLess(request.index("statusIn()"), request.index("finishAddressStatusPromptly()"))

    def test_snapshot_includes_raw_battery_evidence(self):
        firmware = (REPO / "ports" / "lefony-prime-g2" / "ion" / "src" /
                    "prime_g2" / "diagnostics.cpp").read_text()
        for name in ("battery_adc_raw", "battery_mv", "battery_status",
                     "adc1_cfg", "adc1_gc"):
            self.assertIn(name, diag.SNAPSHOT_NAMES)
        self.assertIn("Services::batteryRawADC()", firmware)
        self.assertIn("Services::chargerOperation()", firmware)
        self.assertIn("Services::vbusSense()", firmware)
        self.assertIn("Services::batteryTelemetryFresh()", firmware)

    def test_analyzer_reports_incomplete_pmic_refresh(self):
        words = [0] * 64
        words[0] = diag.SNAPSHOT_MAGIC
        words[60] = 1 << 30
        report = {
            "info": {"status": 7},
            "events": [{"name": "LCDIF_STARTED"}],
            "snapshot": diag.decode_snapshot(struct.pack("<64I", *words)),
        }
        result = " ".join(diag.analyze(report))
        self.assertIn("telemetry is incomplete", result)

    def test_imx6ull_phy_and_controller_contract(self):
        source = (REPO / "ports" / "lefony-prime-g2" / "ion" / "src" /
                  "prime_g2" / "usb_diagnostics.cpp").read_text()
        self.assertIn("(1u << 20)", source)  # IMX6UL_CLK_USBPHY1
        self.assertIn("ANATOP + 0x120, 1u", source)  # vdd3p0 enable
        self.assertIn("2u | (1u << 3) | (1u << 4)", source)
        self.assertIn("reg32(OTGSC) = 0x007F0000u", source)
        self.assertNotIn("otg | (1u << 3) | 1u", source)
        self.assertNotIn("(1u << 24);\n      statusIn()", source)

    def test_recovery_staging_is_sequential_and_capsule_gated(self):
        source = (REPO / "ports" / "lefony-prime-g2" / "ion" / "src" /
                  "prime_g2" / "usb_diagnostics.cpp").read_text()
        self.assertIn("offset != sRecoveryReceived", source)
        self.assertIn("magic == 0x016F2818", source)
        self.assertIn("Ion::crc32Byte", source)

    def test_vm_runs_the_native_driver_against_device_mode_hardware(self):
        firmware = (REPO / "ports" / "lefony-prime-g2" / "ion" / "src" /
                    "prime_g2" / "usb_diagnostics.cpp").read_text()
        model = (REPO / "vm" / "qemu" / "prime_g2_peripherals.c").read_text()
        runner = (REPO / "vm" / "run-native-vm.sh").read_text()
        self.assertNotIn("bool init() { return false; }", firmware)
        self.assertIn("TYPE_PRIME_G2_USBOTG", model)
        self.assertIn("USB_ENDPTLISTADDR", model)
        self.assertIn("prime-g2-usbotg-device.chardev=primeusb", runner)


if __name__ == "__main__":
    unittest.main()
