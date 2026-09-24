from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "lefony_installer.py"
SPEC = importlib.util.spec_from_file_location("lefony_installer", MODULE_PATH)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


def make_capsule(path: Path, size: int = installer.MIN_IMAGE_BYTES) -> None:
    data = bytearray(size)
    data[installer.ZIMAGE_MAGIC_OFFSET : installer.ZIMAGE_MAGIC_OFFSET + 4] = (
        installer.ZIMAGE_MAGIC
    )
    data[installer.ZIMAGE_SIZE_OFFSET : installer.ZIMAGE_SIZE_OFFSET + 4] = size.to_bytes(
        4, "little"
    )
    path.write_bytes(data)


def make_signed_capsule(path: Path, size: int = installer.MIN_IMAGE_BYTES) -> bytes:
    payload_path = path.with_suffix(".zImage")
    make_capsule(payload_path, size)
    payload = payload_path.read_bytes()
    installer.update_capsule.build(
        payload_path,
        path,
        (1, 0, 1, 0),
        MODULE_PATH.parents[1] / "tests/fixtures/prime_g2_emulator_update_private.pem",
    )
    return payload


def make_uboot(path: Path) -> None:
    data = bytearray(8192)
    data[0x400:0x404] = installer.uboot_history.IVT
    strings = b"\0".join((
        b"U-Boot 2018.03 (installer test)",
        b"bootcmd=nand read 80800000 400000 800000;bootz 80800000 - 83000000",
        b"bootcmd_mfg=run bootcmd;",
        b"",
    ))
    data[0x800:0x800 + len(strings)] = strings
    path.write_bytes(data)


class DetectionTests(unittest.TestCase):
    def test_native_writer_route_never_prepares_recovery(self):
        app = installer.LefonyOSPrimeInstaller.__new__(installer.LefonyOSPrimeInstaller)
        app.validation_errors = mock.Mock(return_value=[])
        app.prepare_operation = mock.Mock(side_effect=AssertionError("recovery was prepared"))
        app._native_development_update = mock.Mock(return_value=0)
        device = mock.MagicMock()
        device.__enter__.return_value = device
        with mock.patch.object(installer.usb_update, "LibUSB", return_value=device), \
             mock.patch.object(installer.usb_update, "development_capabilities", return_value={"flags":3}):
            self.assertEqual(app.run_operation("dev-update"), 0)
        app._native_development_update.assert_called_once_with(device)
        app.prepare_operation.assert_not_called()

    def test_development_update_requires_handoff_before_writer(self):
        for mode in ("disconnected", "recovery-sdp", "recovery-fastboot"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                app = installer.LefonyOSPrimeInstaller.__new__(installer.LefonyOSPrimeInstaller)
                app.validation_errors = mock.Mock(return_value=[])
                stage_dir = root / "stage"
                stage_dir.mkdir()
                operation = installer.PreparedOperation("install", stage_dir,
                    stage_dir / "install.uu", "test", uboot_entry=SimpleNamespace(size=389120))
                app.prepare_operation = mock.Mock(return_value=operation)
                app.log_path = root / "log"
                app.detector = mock.Mock()
                app.detector.probe.return_value = installer.DeviceStatus(mode, mode, "", None, 0)
                app._execute_recovery_operation = mock.Mock(return_value=0)
                device = mock.MagicMock()
                device.__enter__.return_value = device
                ready = {"state": 2, "received": installer.MIN_IMAGE_BYTES,
                         "length": installer.MIN_IMAGE_BYTES, "crc32": 123}
                with mock.patch.object(installer.usb_update, "LibUSB", return_value=device), \
                     mock.patch.object(installer.usb_update, "development_capabilities", return_value={"flags": 1}), \
                     mock.patch.object(installer.usb_update, "stage_capsule", return_value=ready), \
                     mock.patch.object(installer.usb_update, "request_development_recovery") as handoff, \
                     mock.patch.object(installer.time, "monotonic", side_effect=[0, 31]):
                    if mode == "disconnected":
                        with self.assertRaisesRegex(RuntimeError, "NAND untouched"):
                            app._legacy_development_update()
                        app._execute_recovery_operation.assert_not_called()
                    else:
                        self.assertEqual(app._legacy_development_update(), 0)
                        app._execute_recovery_operation.assert_called_once_with("install", operation)
                        self.assertEqual(app.active_bootstrap, mode == "recovery-sdp")
                    handoff.assert_called_once_with(device, ready)
                self.assertFalse(stage_dir.exists())

    def test_verified_write_with_missing_boot_is_warning_not_write_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            app = installer.LefonyOSPrimeInstaller.__new__(installer.LefonyOSPrimeInstaller)
            root = Path(directory)
            stage = root / "stage"
            stage.mkdir()
            operation = installer.PreparedOperation("install", stage, stage / "install.uu", "test")
            app.job = installer.BackgroundJob()
            app.log_path = root / "log"
            app._run_uuu = mock.Mock(return_value=0)
            app._host_verify = mock.Mock()
            app._save_artifacts = mock.Mock()
            app._recovery_mode_after_operation = mock.Mock(side_effect=RuntimeError("endpoint vanished"))
            self.assertEqual(app._execute_recovery_operation("install", operation), 0)
            app._host_verify.assert_called_once_with(operation)
            self.assertIn("NAND verified", app.job.warning)

    def test_ram_test_never_launches_nand_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            app = installer.LefonyOSPrimeInstaller.__new__(installer.LefonyOSPrimeInstaller)
            app.log_path = Path(directory) / "upload.log"
            app.image_path = Path(directory) / "image.zImage"
            app.validation_errors = mock.Mock(return_value=[])
            app._run_uuu = mock.Mock(side_effect=AssertionError("NAND writer invoked"))
            device = mock.MagicMock()
            with mock.patch.object(installer.usb_update, "LibUSB", return_value=device), \
                 mock.patch.object(installer.usb_update, "stage_capsule",
                                   return_value={"crc32": 0x12345678}) as stage:
                self.assertEqual(app.run_operation("stage"), 0)
            stage.assert_called_once()
            device.__enter__.return_value.write.assert_called_once_with(
                installer.usb_update.REQUEST_RECOVERY_ABORT)
            app._run_uuu.assert_not_called()
            self.assertIn("OS was not installed", app.log_path.read_text())

    def test_rom_recovery(self):
        status = installer.parse_uuu_output(
            "0:1 MX6ULL SDP: 0x15A2 0x0080", checked_at=123.0
        )
        self.assertIsNotNone(status)
        self.assertEqual(status.mode, "recovery-sdp")
        self.assertTrue(status.recovery)
        self.assertEqual(status.checked_at, 123.0)

    def test_recovery_linux(self):
        status = installer.parse_uuu_output("0:1 MX6ULL FBK: 0x066f 0x9bff")
        self.assertEqual(status.mode, "recovery-fastboot")
        self.assertTrue(status.recovery)

    def test_native_upsilon_usb(self):
        status = installer.parse_usb_inventory("Bus 001 Device CAFE:5052", [])
        self.assertEqual(status.mode, "upsilon")
        self.assertFalse(status.recovery)

    def test_official_hp_os_usb(self):
        status = installer.parse_usb_inventory("Bus 001 Device 03F0:2441 HP Prime", [])
        self.assertEqual(status.mode, "hp-stock")
        self.assertEqual(status.label, "HP PRIME OS RUNNING")
        self.assertFalse(status.recovery)

    def test_official_hp_update_usb_from_macos_inventory(self):
        inventory = '\n'.join(('"idVendor" = 1008', '"idProduct" = 9537'))
        status = installer.parse_usb_inventory(inventory, [])
        self.assertEqual(status.mode, "hp-update")
        self.assertEqual(status.label, "HP PRIME UPDATE MODE")
        self.assertFalse(status.recovery)

    def test_linux_usb_requires_live_serial_node(self):
        self.assertIsNone(installer.parse_usb_inventory("0525:a4a7 Gadget Serial", []))
        status = installer.parse_usb_inventory(
            "0525:a4a7 Gadget Serial", ["/dev/cu.usbmodem101"]
        )
        self.assertEqual(status.mode, "linux")
        self.assertEqual(status.port, "/dev/cu.usbmodem101")

    def test_recovery_wins_over_stale_linux_node(self):
        detector = installer.Detector(uuu="/test/uuu")
        completed = mock.Mock(stdout="MX6ULL SDP: 0x15A2 0x0080", stderr="")
        with (
            mock.patch.object(installer.subprocess, "run", return_value=completed),
            mock.patch.object(installer, "find_linux_ports", return_value=["/dev/cu.old"]),
        ):
            status = detector.probe()
        self.assertEqual(status.mode, "recovery-sdp")


class ImageTests(unittest.TestCase):
    def test_signed_update_capsule_exposes_embedded_recovery_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lefony.lfu"
            payload = make_signed_capsule(path)
            info = installer.ImageInfo.inspect(path)
            self.assertEqual(info.errors(), [])
            self.assertEqual(info.update_errors(), [])
            self.assertTrue(info.signed_update)
            self.assertEqual(info.update_version, (1, 0, 1, 0))
            self.assertEqual(info.recovery_payload(), payload)

    def test_valid_capsule(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upsilon.zImage"
            make_capsule(path)
            info = installer.ImageInfo.inspect(path)
            self.assertEqual(info.errors(), [])
            self.assertEqual(info.size, installer.MIN_IMAGE_BYTES)
            self.assertEqual(len(info.sha256), 64)

    def test_rejects_wrong_magic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-upsilon.zImage"
            path.write_bytes(bytes(installer.MIN_IMAGE_BYTES))
            errors = installer.ImageInfo.inspect(path).errors()
            self.assertTrue(any("magic" in error for error in errors))

    def test_rejects_declared_size_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad-size.zImage"
            make_capsule(path)
            data = bytearray(path.read_bytes())
            data[installer.ZIMAGE_SIZE_OFFSET : installer.ZIMAGE_SIZE_OFFSET + 4] = (42).to_bytes(
                4, "little"
            )
            path.write_bytes(data)
            errors = installer.ImageInfo.inspect(path).errors()
            self.assertTrue(any("size field" in error for error in errors))


class ThemeTests(unittest.TestCase):
    def test_installer_preserves_terminal_canvas_uses_terminal_default(self):
        app = object.__new__(installer.LefonyOSPrimeInstaller)
        screen = mock.Mock()
        with (
            mock.patch.object(installer.curses, "has_colors", return_value=True),
            mock.patch.object(installer.curses, "start_color") as start_color,
            mock.patch.object(installer.curses, "use_default_colors") as use_default_colors,
            mock.patch.object(installer.curses, "init_pair") as init_pair,
        ):
            app.configure_theme(screen)

        start_color.assert_called_once_with()
        use_default_colors.assert_called_once_with()
        self.assertEqual(
            init_pair.call_args_list,
            [
                mock.call(app.ERROR, installer.curses.COLOR_RED, -1),
                mock.call(app.GOOD, installer.curses.COLOR_GREEN, -1),
                mock.call(app.WARN, installer.curses.COLOR_YELLOW, -1),
            ],
        )
        screen.bkgd.assert_not_called()
        screen.attrset.assert_not_called()


class ProgressTests(unittest.TestCase):
    def test_install_progress_uses_ordered_phases(self):
        raw = "\n".join(
            (
                "New USB Device Attached at 0:1-",
                "0:1->Start Cmd:SDP: boot -f u-boot-dtb.imx -nojump",
                "100%0:1->Okay",
                "0:1->Start Cmd:FBK: ucmd flash_erase /dev/mtd1 0 0",
                "42%",
            )
        )
        progress = installer.operation_progress("install", raw, bootstrap=True)
        self.assertEqual(progress.phase, "Erasing the Lefony OS NAND slot")
        self.assertEqual(progress.current, 8)
        self.assertEqual(progress.total, 13)
        self.assertEqual(progress.percent, 62)
        self.assertEqual(progress.transfer_percent, 42)

    def test_direct_fastboot_does_not_count_sdp_phase(self):
        raw = "0:1->Start Cmd:FBK: ucmd nanddump -f /tmp/lefony-os-prime-installer/pre-operation.mtd /dev/mtd1"
        progress = installer.operation_progress("install", raw, bootstrap=False)
        self.assertEqual(progress.current, 4)
        self.assertEqual(progress.total, 12)

    def test_attached_device_wait_is_explicit(self):
        progress = installer.operation_progress(
            "install", "Wait for Known USB Device Appear...\nNew USB Device Attached at 0:1-"
        )
        self.assertEqual(progress.current, 0)
        self.assertIn("waiting for the required recovery stage", progress.phase.lower())

    def test_completion_reserves_final_host_verification(self):
        progress = installer.operation_progress(
            "install", "===UPSILON-INSTALL-COMPLETE===", bootstrap=False
        )
        self.assertEqual(progress.percent, 95)

    def test_progress_bar_is_bounded(self):
        self.assertEqual(installer.progress_bar(-1, 4), "[----]")
        self.assertEqual(installer.progress_bar(50, 4), "[##--]")
        self.assertEqual(installer.progress_bar(101, 4), "[####]")

    def test_specific_uuu_error_wins_over_applescript_wrapper(self):
        lines = [
            "Error: Timeout: Wait for next USB Device",
            "0:349: execution error: The command exited with a non-zero status. (255)",
        ]
        self.assertEqual(
            installer.uuu_failure_detail(lines),
            "Error: Timeout: Wait for next USB Device",
        )


class ScriptSafetyTests(unittest.TestCase):
    def test_page_readback_is_exact_for_aligned_and_partial_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            output = root / "readback"
            data = bytes(range(256)) * 16384
            source.write_bytes(data)
            for size in (1, 2047, 2048, 2049, 2103184):
                command = installer.page_readback_command(str(source), str(output), size)
                # Match FBK's outer shell plus its quoted sh -c argument.
                subprocess.run(["sh", "-c", 'sh -c "' + command + '"'],
                               check=True, capture_output=True)
                self.assertEqual(output.read_bytes(), data[:size])
                self.assertNotIn(f"if={source} bs=1 ", command)
            source.write_bytes(b"short")
            command = installer.page_readback_command(str(source), str(output), 2049)
            result = subprocess.run(["sh", "-c", 'sh -c "' + command + '"'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_install_and_verify_use_page_reads_and_keep_comparison(self):
        for action in ("install", "verify"):
            script = installer.make_uuu_script(action, 2103184)
            self.assertIn("readback.mtd bs=2048 count=1026", script)
            self.assertIn("bs=2048 skip=1026 count=1", script)
            self.assertIn("wc -c < /tmp/lefony-os-prime-installer/readback.mtd | grep -q", script)
            self.assertIn("^[[:space:]]*2103184[[:space:]]*$", script)
            self.assertIn("FBK: ucmd cmp", script)
            self.assertIn("FBK: ucp T:/tmp/lefony-os-prime-installer/readback.mtd", script)

    def test_install_is_backup_erase_write_readback(self):
        script = installer.make_uuu_script("install", installer.MIN_IMAGE_BYTES)
        backup = script.index("nanddump")
        erase = script.index("flash_erase /dev/mtd1")
        write = script.index("nandwrite -p /dev/mtd1")
        compare = script.index("FBK: ucmd cmp")
        self.assertLess(backup, erase)
        self.assertLess(erase, write)
        self.assertLess(write, compare)

    def test_all_operations_are_locked_to_mtd1(self):
        for action in ("backup", "verify", "install", "erase"):
            size = installer.MIN_IMAGE_BYTES if action in ("verify", "install") else 0
            script = installer.make_uuu_script(action, size)
            self.assertIn("/dev/mtd1", script)
            self.assertNotIn("/dev/mtd0", script)
            self.assertNotIn("/dev/mtd2", script)
            self.assertNotIn("/dev/mtd3", script)
            self.assertNotIn("/dev/mtd4", script)

    def test_erase_never_writes_an_image(self):
        script = installer.make_uuu_script("erase")
        self.assertIn("flash_erase /dev/mtd1", script)
        self.assertNotIn("nandwrite", script)
        self.assertIn(str(installer.NAND_SLOT_BYTES), script)

    def test_fastboot_script_does_not_wait_for_sdp(self):
        script = installer.make_uuu_script(
            "verify", installer.MIN_IMAGE_BYTES, bootstrap=False
        )
        self.assertNotIn("SDP:", script)
        self.assertIn("FBK:", script)

    def test_invalid_action_and_size_are_rejected(self):
        with self.assertRaises(ValueError):
            installer.make_uuu_script("full-nand-erase")
        with self.assertRaises(ValueError):
            installer.make_uuu_script("install", installer.NAND_SLOT_BYTES + 1)

    def test_uboot_verification_reads_both_copies_and_never_writes_nand(self):
        script = installer.make_uboot_verify_script(8192)
        self.assertIn("nanddump -q -s 1048576 -l 8192", script)
        self.assertIn("nanddump -q -s 2621440 -l 8192", script)
        self.assertIn("/dev/mtd0", script)
        self.assertNotIn("flash_erase", script)
        self.assertNotIn("nandwrite", script)

    def test_ab_update_reads_metadata_before_any_write(self):
        probe = installer.make_ab_metadata_read_script()
        self.assertIn("metadata-0.bin", probe)
        self.assertIn("metadata-1.bin", probe)
        self.assertNotIn("flash_erase", probe)
        self.assertNotIn("nandwrite", probe)
        self.assertNotIn("FBK: done", probe)

    def test_ab_update_writes_slot_before_redundant_metadata(self):
        script = installer.make_ab_install_script(
            1, installer.MIN_IMAGE_BYTES, stale_copy=1
        )
        slot_write = script.index(
            f"nandwrite -p -N -s {installer.AB_SLOT_B_OFFSET_IN_ROOTFS}"
        )
        readback = script.index("readback.mtd")
        redundant_commit = script.index("flash_erase /dev/mtd3 131072 1")
        primary_commit = script.index("flash_erase /dev/mtd3 0 1")
        self.assertLess(slot_write, readback)
        self.assertLess(readback, redundant_commit)
        self.assertLess(redundant_commit, primary_commit)
        self.assertNotIn("/dev/mtd0", script)
        self.assertIn("FBK: done", script)
        self.assertNotIn("FBK: acmd reboot", script)
        self.assertIn(
            f"flash_erase /dev/mtd4 {installer.AB_SLOT_B_OFFSET_IN_ROOTFS} 64",
            script,
        )
        self.assertNotIn(
            f"flash_erase /dev/mtd4 {installer.AB_SLOT_B_ERASE_BLOCK} 64",
            script,
        )

    def test_uuu_accepts_generated_command_lists(self):
        uuu = shutil.which("uuu")
        if not uuu:
            self.skipTest("uuu is not installed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_capsule(root / "lefony-os-native.zImage")
            for action in ("backup", "verify", "install", "erase"):
                size = installer.MIN_IMAGE_BYTES if action in ("verify", "install") else 0
                script = root / f"{action}.uu"
                script.write_text(installer.make_uuu_script(action, size, bootstrap=False))
                result = subprocess.run(
                    [uuu, "-dry", str(script)],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=f"{action}: {result.stdout}\n{result.stderr}",
                )
            generated = {
                "ab-read": installer.make_ab_metadata_read_script(bootstrap=False),
                "ab-install": installer.make_ab_install_script(
                    1, installer.MIN_IMAGE_BYTES, stale_copy=1
                ),
                "verify-uboot": installer.make_uboot_verify_script(8192, bootstrap=False),
            }
            (root / "metadata.bin").write_bytes(bytes(installer.AB_METADATA_PAGE_BYTES))
            (root / "expected-u-boot.imx").write_bytes(bytes(8192))
            for name, contents in generated.items():
                script = root / f"{name}.uu"
                script.write_text(contents)
                result = subprocess.run(
                    [uuu, "-dry", str(script)], cwd=root,
                    capture_output=True, text=True, timeout=10, check=False,
                )
                self.assertEqual(
                    result.returncode, 0,
                    msg=f"{name}: {result.stdout}\n{result.stderr}",
                )


class OperationGuardTests(unittest.TestCase):
    def make_args(self, root: Path) -> argparse.Namespace:
        return argparse.Namespace(
            prinux=root / "prinux",
            image=root / "upsilon.zImage",
            backup_dir=root / "backups",
            uuu="/test/uuu",
            interval=1.0,
            once=False,
            json=False,
            no_admin=True,
            history_dir=root / "os-history",
            uboot_history_dir=root / "uboot-history",
        )

    def record_uboot(self, root: Path, status="cold-boot-known-good"):
        artifact = root / "u-boot-pad.imx"
        make_uboot(artifact)
        return installer.uboot_history.record_build(
            artifact, history_dir=root / "uboot-history", source=MODULE_PATH.parents[1],
            status=status, notes="Installer test baseline.",
        )

    def test_unqualified_bootloader_baselines_allow_audit_but_not_install(self):
        statuses = (
            "unverified", "emulator-cold-boot-qualified", "nand-readback-verified",
            "linux-nand-boot-verified", "physical-failed-black",
            "physical-failed-white", "superseded",
        )
        for status in statuses:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                make_capsule(root / "upsilon.zImage")
                entry = self.record_uboot(root, status=status)
                with mock.patch.object(
                    installer.Detector, "probe", return_value=installer.DeviceStatus(
                        "recovery-fastboot", "RECOVERY", "fastboot", None, 1.0
                    ),
                ):
                    app = installer.LefonyOSPrimeInstaller(self.make_args(root))
                # The sole entry is selected for inspection even when it is not
                # qualified. Selection alone must never authorize installation.
                self.assertEqual(app.selected_uboot, entry)
                self.assertEqual(app.validation_errors("verify-uboot"), [])
                with mock.patch.object(installer.tempfile, "mkdtemp") as stage:
                    with self.assertRaisesRegex(RuntimeError, "not qualified"):
                        app.prepare_operation("install")
                    stage.assert_not_called()
                operation = app.prepare_operation("verify-uboot")
                try:
                    script = operation.script.read_text()
                    self.assertNotIn("nandwrite", script)
                    self.assertNotIn("flash_erase", script)
                finally:
                    installer.shutil.rmtree(operation.stage)

    def test_manual_bootloader_selection_cannot_bypass_qualification(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_capsule(root / "upsilon.zImage")
            entry = self.record_uboot(root)
            with mock.patch.object(
                installer.Detector, "probe", return_value=installer.DeviceStatus(
                    "recovery-fastboot", "RECOVERY", "fastboot", None, 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))
            for status in installer.uboot_history.QUALIFIED_STATUSES:
                app.selected_uboot = replace(entry, status=status)
                self.assertEqual(app.validation_errors("install"), [])
            app.selected_uboot = replace(entry, status="unverified")
            with mock.patch.object(installer.tempfile, "mkdtemp") as stage:
                with self.assertRaisesRegex(RuntimeError, "not qualified"):
                    app.prepare_operation("install")
                stage.assert_not_called()

    def test_uboot_verification_requires_and_stages_a_history_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_capsule(root / "upsilon.zImage")
            for relative in installer.RECOVERY_ASSETS.values():
                asset = root / "prinux" / relative
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_bytes(b"recovery")
            entry = self.record_uboot(root)
            with mock.patch.object(
                installer.Detector, "probe",
                return_value=installer.DeviceStatus(
                    "recovery-sdp", "ROM RECOVERY", "sdp", None, 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))
            self.assertEqual(app.selected_uboot, entry)
            operation = app.prepare_operation("verify-uboot")
            try:
                self.assertEqual(operation.uboot_entry, entry)
                self.assertEqual(
                    (operation.stage / "expected-u-boot.imx").read_bytes(),
                    (root / "u-boot-pad.imx").read_bytes(),
                )
                self.assertNotIn("nandwrite", operation.script.read_text())
            finally:
                installer.shutil.rmtree(operation.stage)

    def test_installer_rejects_history_artifact_with_truncated_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_capsule(root / "upsilon.zImage")
            entry = self.record_uboot(root)
            artifact = root / "uboot-history" / entry.artifact
            data = bytearray(artifact.read_bytes())
            environment = b"\0".join((
                b"bootdelay=0",
                b"bootcmd_mfg=run bootcmd;",
                b"",
                b"bootcmd=nand read 80800000 400000 800000",
                b"",
            ))
            data[0x900:0x900 + len(environment)] = environment
            artifact.write_bytes(data)
            index_path = root / "uboot-history" / installer.uboot_history.INDEX_NAME
            index = json.loads(index_path.read_text())
            index["builds"][0]["sha256"] = hashlib.sha256(data).hexdigest()
            index_path.write_text(json.dumps(index))
            with mock.patch.object(
                installer.Detector, "probe",
                return_value=installer.DeviceStatus(
                    "recovery-fastboot", "RECOVERY", "fastboot", None, 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))
            self.assertIn(
                "bootcmd was not found",
                "\n".join(app.validation_errors("verify-uboot")),
            )

    def test_host_uboot_verification_requires_two_exact_history_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_capsule(root / "upsilon.zImage")
            entry = self.record_uboot(root)
            with mock.patch.object(
                installer.Detector, "probe",
                return_value=installer.DeviceStatus(
                    "recovery-fastboot", "RECOVERY", "fastboot", None, 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))
            stage = root / "stage"
            stage.mkdir()
            expected = (root / "u-boot-pad.imx").read_bytes()
            (stage / "boot-primary.readback").write_bytes(expected)
            (stage / "boot-secondary.readback").write_bytes(expected)
            operation = installer.PreparedOperation(
                "verify-uboot", stage, stage / "verify.uu", "stamp",
                uboot_entry=entry,
            )
            app.log_path = root / "log"
            app.log_path.write_text("")
            app._host_verify_uboot(operation)
            self.assertIn(entry.sha256, app.log_path.read_text())
            damaged = bytearray(expected)
            damaged[-1] ^= 1
            (stage / "boot-secondary.readback").write_bytes(damaged)
            with self.assertRaisesRegex(RuntimeError, "secondary mismatch"):
                app._host_verify_uboot(operation)

    def test_prepare_is_blocked_outside_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_capsule(root / "upsilon.zImage")
            self.record_uboot(root)
            with mock.patch.object(
                installer.Detector,
                "probe",
                return_value=installer.DeviceStatus(
                    "linux", "LINUX", "normal boot", "/dev/cu.test", 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))
            with self.assertRaisesRegex(RuntimeError, "not in a detected recovery"):
                app.prepare_operation("install")

    def test_stock_hp_os_is_detected_but_all_writes_remain_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_signed_capsule(root / "upsilon.zImage")
            with mock.patch.object(
                installer.Detector,
                "probe",
                return_value=installer.DeviceStatus(
                    "hp-stock", "HP PRIME OS RUNNING", "official USB", None, 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))
            with self.assertRaisesRegex(RuntimeError, "not in a detected recovery"):
                app.prepare_operation("install")
            self.assertIn(
                "requires LEFONY OS RUNNING", app.validation_errors("update")[0]
            )

    def test_runtime_update_is_allowed_only_for_native_usb_and_signed_capsule(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "upsilon.zImage"
            make_signed_capsule(package)
            with mock.patch.object(
                installer.Detector,
                "probe",
                return_value=installer.DeviceStatus(
                    "upsilon", "LEFONY OS RUNNING", "native USB", None, 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))
            device = mock.MagicMock()
            device.__enter__.return_value = device
            status = {"pending_slot": 1, "generation": 2}
            with (
                mock.patch.object(installer.usb_update, "LibUSB", return_value=device),
                mock.patch.object(installer.usb_update, "install_signed_capsule", return_value=status) as update,
            ):
                self.assertEqual(app.run_operation("update"), 0)
            update.assert_called_once_with(device, package.resolve(), reboot=False)
            device.write.assert_called_once_with(
                installer.usb_update.REQUEST_UPDATE_REBOOT, timeout_ms=10000
            )

    def test_runtime_update_rejects_raw_recovery_capsule(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_capsule(root / "upsilon.zImage")
            with mock.patch.object(
                installer.Detector,
                "probe",
                return_value=installer.DeviceStatus(
                    "upsilon", "LEFONY OS RUNNING", "native USB", None, 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))
            with self.assertRaisesRegex(RuntimeError, "signed .lfu"):
                app.run_operation("update")

    def test_physical_runtime_update_hands_authenticated_package_to_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "upsilon.zImage"
            make_signed_capsule(package)
            for relative in installer.RECOVERY_ASSETS.values():
                asset = root / "prinux" / relative
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_bytes(b"recovery")
            with mock.patch.object(
                installer.Detector, "probe",
                return_value=installer.DeviceStatus(
                    "upsilon", "LEFONY OS RUNNING", "native USB", None, 1.0
                ),
            ):
                args = self.make_args(root)
                args.uuu = "/test/uuu"
                app = installer.LefonyOSPrimeInstaller(args)
            device = mock.MagicMock()
            device.__enter__.return_value = device
            status = {
                "handoff": "recovery", "active_slot": 0,
                "pending_slot": None, "generation": 7,
            }
            with (
                mock.patch.object(installer.usb_update, "LibUSB", return_value=device),
                mock.patch.object(installer.usb_update, "install_signed_capsule", return_value=status),
                mock.patch.object(app, "_physical_ab_update") as finish,
            ):
                self.assertEqual(app.run_operation("update"), 0)
            device.write.assert_called_once_with(
                installer.usb_update.REQUEST_UPDATE_RECOVERY, timeout_ms=10000
            )
            finish.assert_called_once()
            self.assertIs(finish.call_args.args[0], status)
            self.assertEqual(finish.call_args.args[1].payload, app.image.recovery_payload())

    def test_fastboot_prepare_stages_valid_script_and_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_capsule(root / "upsilon.zImage")
            self.record_uboot(root)
            with mock.patch.object(
                installer.Detector,
                "probe",
                return_value=installer.DeviceStatus(
                    "recovery-fastboot", "RECOVERY", "fastboot", None, 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))
            operation = app.prepare_operation("install")
            try:
                self.assertTrue((operation.stage / "lefony-os-native.zImage").is_file())
                self.assertNotIn("SDP:", operation.script.read_text())
            finally:
                installer.shutil.rmtree(operation.stage)

    def test_prepare_snapshots_sdp_before_ui_switches_to_working(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_capsule(root / "upsilon.zImage")
            self.record_uboot(root)
            for relative in installer.RECOVERY_ASSETS.values():
                asset = root / "prinux" / relative
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_bytes(b"recovery")
            with mock.patch.object(
                installer.Detector,
                "probe",
                return_value=installer.DeviceStatus(
                    "recovery-sdp", "ROM RECOVERY", "sdp", None, 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))

            original_validation = app.validation_errors

            def switch_ui_status(action, recovery_mode=None):
                app.status = installer.DeviceStatus(
                    "working", "NAND OPERATION ACTIVE", action, None, 2.0
                )
                return original_validation(action, recovery_mode)

            with mock.patch.object(app, "validation_errors", side_effect=switch_ui_status):
                operation = app.prepare_operation("install")
            try:
                self.assertTrue(app.active_bootstrap)
                self.assertIn("SDP: boot", operation.script.read_text())
                for staged_name in installer.RECOVERY_ASSETS:
                    self.assertTrue((operation.stage / staged_name).is_file())
            finally:
                installer.shutil.rmtree(operation.stage)

    def test_partial_backup_is_preserved_when_uuu_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_capsule(root / "upsilon.zImage")
            with mock.patch.object(
                installer.Detector,
                "probe",
                return_value=installer.DeviceStatus(
                    "recovery-fastboot", "RECOVERY", "fastboot", None, 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))

            def fail_after_backup(operation):
                (operation.stage / "pre-operation.mtd").write_bytes(b"recoverable")
                raise OSError("simulated USB disconnect")

            with mock.patch.object(app, "_run_uuu", side_effect=fail_after_backup):
                with self.assertRaisesRegex(OSError, "USB disconnect"):
                    app.run_operation("backup")
            backups = list((root / "backups").glob("pre-backup-*-mtd1.mtd"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), b"recoverable")

    def test_uuu_exit_failure_reports_log_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_capsule(root / "upsilon.zImage")
            with mock.patch.object(
                installer.Detector,
                "probe",
                return_value=installer.DeviceStatus(
                    "recovery-fastboot", "RECOVERY", "fastboot", None, 1.0
                ),
            ):
                app = installer.LefonyOSPrimeInstaller(self.make_args(root))
            app.log_path = root / "uuu.log"

            def timeout(operation):
                app.log_path.write_text("Error: Timeout: Wait for next USB Device\n")
                return 1

            with mock.patch.object(app, "_run_uuu", side_effect=timeout):
                with self.assertRaisesRegex(
                    RuntimeError, "UUU failed.*Timeout: Wait for next USB Device"
                ):
                    app.run_operation("backup")


if __name__ == "__main__":
    unittest.main()
