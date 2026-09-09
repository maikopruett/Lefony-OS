from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lefony_installer as installer


def test_sdp_exit_uses_staged_clear_reset_uboot_without_nand_access():
    script = installer.make_exit_recovery_script("recovery-sdp")
    assert "u-boot-clearreset.imx" in script
    assert script.index("SDP: boot") < script.index("SDP: jump")
    assert "FBK:" not in script
    assert "/dev/mtd" not in script
    assert "nand" not in script.lower()


def test_fastboot_exit_clears_and_verifies_override_before_reset():
    script = installer.make_exit_recovery_script("recovery-fastboot")
    recovery_reset = script.index("/proc/sysrq-trigger")
    clear_reset = script.index("SDP: boot")
    assert recovery_reset < clear_reset
    assert "/dev/mtd" not in script
    assert "nand" not in script.lower()


def test_clear_reset_uboot_patches_only_manufacturing_environment(tmp_path=None):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "u-boot.imx"
        destination = root / "clear.imx"
        original = (
            b"prefix" + installer.CLEAR_RESET_ENV_KEY
            + b"run old manufacturing command with plenty of room;" + b"\0suffix"
        )
        source.write_bytes(original)
        installer.build_clear_reset_uboot(source, destination)
        patched = destination.read_bytes()
        assert len(patched) == len(original)
        assert installer.CLEAR_RESET_ENV in patched
        start = original.index(installer.CLEAR_RESET_ENV_KEY)
        end = original.index(b"\0", start)
        assert patched[:start] == original[:start]
        assert patched[end:] == original[end:]
        assert b"\0\0" not in patched[start:end + 1]
        assert patched[len(installer.CLEAR_RESET_ENV) + start:end].strip() == b""


def test_terminal_jump_timeout_is_recognized_only_after_successful_jump():
    completed = (
        "Start Cmd:SDP: jump -f u-boot-clearreset.imx -ivt\n"
        "100%\nOkay (0.1s)\nError: Timeout: Wait for next USB Device\n"
    )
    assert installer.terminal_clear_reset_jump_completed(completed)
    assert not installer.terminal_clear_reset_jump_completed(
        "Start Cmd:SDP: jump -f u-boot-clearreset.imx -ivt\nFail\n"
    )


def test_install_host_verification_precedes_recovery_exit():
    app = object.__new__(installer.LefonyOSPrimeInstaller)
    events = []
    with tempfile.TemporaryDirectory() as directory:
        operation = installer.PreparedOperation(
            "install", Path(directory), Path(directory) / "install.uu", "stamp"
        )
        app.prepare_operation = mock.Mock(return_value=operation)
        app._run_uuu = mock.Mock(return_value=0)
        app._host_verify = mock.Mock(side_effect=lambda unused: events.append("verified"))
        app._recovery_mode_after_operation = mock.Mock(
            side_effect=lambda: events.append("detected") or "recovery-sdp"
        )
        app._exit_recovery = mock.Mock(side_effect=lambda unused: events.append("exited"))
        app._save_artifacts = mock.Mock()
        assert app.run_operation("install") == 0
    assert events == ["verified", "detected", "exited"]


def test_uuu_accepts_exit_recovery_scripts():
    uuu = shutil.which("uuu")
    if not uuu:
        return
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "u-boot-clearreset.imx").write_bytes(b"placeholder")
        for mode in ("recovery-sdp", "recovery-fastboot"):
            script = root / f"{mode}.uu"
            script.write_text(installer.make_exit_recovery_script(mode))
            result = subprocess.run(
                [uuu, "-dry", str(script)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
