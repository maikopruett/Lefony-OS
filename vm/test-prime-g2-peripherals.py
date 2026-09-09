#!/usr/bin/env python3
"""Black-box qtest checks for the Prime G2 MMIO peripheral models."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
QEMU = Path(os.environ.get("PRIME_G2_QEMU", ROOT / "build/qemu-prime-g2/qemu-system-arm"))


def check_snvs_counter_domains_and_alarm() -> None:
    process = subprocess.Popen([
        str(QEMU), "-machine", "hp-prime-g2",
        "-global", "imx6ul-lcdif.prime-g2-panel=on",
        "-display", "none", "-monitor", "none", "-serial", "none",
        "-qtest", "stdio",
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True)

    def qtest(command: str) -> int | None:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(command + "\n")
        process.stdin.flush()
        reply = process.stdout.readline().strip()
        if not reply.startswith("OK"):
            raise AssertionError(f"qtest command failed: {command!r}: {reply!r}")
        fields = reply.split()
        return int(fields[1], 16) if len(fields) == 2 else None

    try:
        hp_high = qtest("readl 0x020cc024")
        hp_low = qtest("readl 0x020cc028")
        lp_high = qtest("readl 0x020cc050")
        assert hp_high is not None and hp_low is not None and lp_high is not None
        hp_count = (hp_high << 32) | hp_low
        if hp_high != 0 or hp_count > 5 * 32768 or lp_high == hp_high:
            raise AssertionError(
                f"SNVS HP/LP domains are not independent: "
                f"hp=0x{hp_count:x} lp_high=0x{lp_high:x}"
            )

        alarm = (hp_count + 4096) & ((1 << 47) - 1)
        qtest(f"writel 0x020cc02c 0x{alarm >> 32:08x}")
        qtest(f"writel 0x020cc030 0x{alarm & 0xffffffff:08x}")
        qtest("writel 0x020cc008 0x00000003")
        time.sleep(0.25)
        status = qtest("readl 0x020cc014")
        if status is None or not status & 1:
            raise AssertionError(f"SNVS HP alarm did not latch: hpsr={status!r}")
        qtest("writel 0x020cc014 0x00000001")
        if qtest("readl 0x020cc014") != 0:
            raise AssertionError("SNVS HP alarm status did not clear")

        # RTC_EN | PI_EN | PI_FREQ=5: HPRTCLR bit 5 toggles every 32 ticks,
        # giving the 1024 Hz periodic source used by the stock scheduler.
        qtest("writel 0x020cc008 0x00000059")
        time.sleep(0.02)
        status = qtest("readl 0x020cc014")
        if status is None or not status & 2:
            raise AssertionError(
                f"SNVS periodic interrupt did not latch: hpsr={status!r}"
            )
        # Stop the 1024 Hz source before testing acknowledgement: otherwise
        # host scheduling can allow a new event between the write and read.
        qtest("writel 0x020cc008 0x00000051")
        qtest("writel 0x020cc014 0x00000002")
        if qtest("readl 0x020cc014") != 0:
            raise AssertionError("SNVS periodic interrupt status did not clear")

        # Stock display startup performs a bounded delay by polling PWM7's
        # read-only counter. Use a slow prescaler so progress is observable.
        gates = qtest("readl 0x020c4080")
        assert gates is not None
        qtest(f"writel 0x020c4080 0x{gates | 0xc0000000:x}")
        qtest("writel 0x020f8010 0x0000004f")
        qtest("writel 0x020f8000 0x0001fff1")
        pwm_before = qtest("readl 0x020f8014")
        if pwm_before is None or pwm_before > 0x50:
            raise AssertionError(f"PWM7 counter outside programmed period: {pwm_before!r}")
        # Host scheduling can delay a read by a whole number of PWM periods.
        # Equal samples do not prove a stopped counter; require observable
        # progress within a bounded window and validate every sampled value.
        deadline = time.monotonic() + 0.1
        pwm_after = pwm_before
        while pwm_after == pwm_before and time.monotonic() < deadline:
            time.sleep(0.0013)
            pwm_after = qtest("readl 0x020f8014")
            if pwm_after is None or pwm_after > 0x50:
                raise AssertionError(f"PWM7 counter outside programmed period: {pwm_after!r}")
        if (pwm_before is None or pwm_after is None or
                pwm_before == pwm_after or pwm_after > 0x50):
            raise AssertionError(
                f"PWM7 counter did not advance/wrap: "
                f"before={pwm_before!r} after={pwm_after!r}"
            )
        qtest("writel 0x020f8000 0x0001fff0")
        stopped = qtest("readl 0x020f8014")
        time.sleep(0.003)
        if qtest("readl 0x020f8014") != stopped:
            raise AssertionError("Disabled PWM7 counter continued advancing")
    finally:
        process.terminate()
        process.communicate(timeout=5)


def check_persistent_nand_overlay() -> None:
    with tempfile.TemporaryDirectory(prefix="prime-g2-overlay-") as directory:
        overlay = Path(directory) / "nand.overlay"
        base = [
            str(QEMU), "-machine", "hp-prime-g2",
            "-global", "imx6ul-lcdif.prime-g2-panel=on",
            "-global", f"prime-g2-gpmi-bch.stock-overlay={overlay}",
            "-display", "none", "-monitor", "none", "-serial", "none",
            "-qtest", "stdio",
        ]
        def run_qtest(commands: list[str]) -> tuple[int, str, str]:
            process = subprocess.Popen(
                base, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
            try:
                stdout, stderr = process.communicate(
                    "\n".join(commands) + "\n", timeout=2,
                )
            except subprocess.TimeoutExpired:
                process.terminate()
                stdout, stderr = process.communicate(timeout=5)
            return process.returncode, stdout, stderr

        first_code, _, first_error = run_qtest([
                "writel 0x01806104 0x00000003",
                "writel 0x01806100 0x00000080",
                "writel 0x01806108 0x000000a5",
                "writel 0x01806100 0x00000010",
            ])
        if first_code not in (0, -15):
            raise RuntimeError(first_error)
        second_code, second_output, second_error = run_qtest([
                "writel 0x01806100 0x00000000",
                "writel 0x01806104 0x00000003",
                "readl 0x01806108",
                "readl 0x01806160",
            ])
        reads = [
            int(line.split()[1], 16) for line in second_output.splitlines()
            if line.startswith("OK") and len(line.split()) == 2
        ]
        if second_code not in (0, -15) or reads != [0xA5, 1]:
            raise AssertionError(
                f"persistent NAND overlay failed: reads={reads}\n"
                f"{second_output}\n{second_error}"
            )


def main() -> int:
    commands = "\n".join([
        # Prime's serialized LCD bus leaves the unused GPIO2 input pads pulled
        # high; stock startup verifies this exact board-level mask.
        "readl 0x020a0008",
        # PSR samples output pads as well as external input pins. Stock HP
        # firmware uses this for its GPIO loopback self-test during startup.
        "writel 0x0209c004 0x00000003", "writel 0x0209c000 0x00000002",
        "readl 0x0209c008",
        # KPP setup, matrix press, row sense and release.
        "writew 0x020b8000 0xfffe", "writew 0x020b8004 0xff00",
        "writew 0x020b8006 0xfeff", "writew 0x020b8008 0x8200",
        "readw 0x020b8006", "readw 0x020b8002",
        "writew 0x020b8008 0x0200", "readw 0x020b8006",
        # Three corners of a rectangle create the fourth sensed ghost key:
        # r2c0 + r2c1 + r3c1, while c0 is driven low, pulls r2 and r3 low.
        "writew 0x020b8008 0x8200", "writew 0x020b8008 0x8201",
        "writew 0x020b8008 0x8301", "readw 0x020b8006",
        "writew 0x020b8008 0x0200", "writew 0x020b8008 0x0201",
        "writew 0x020b8008 0x0301",
        # ADC1 calibration, battery-channel conversion, and read-to-clear COCO.
        # The default 3850 mV PF1550 battery model maps to HP ADC code 211.
        "writel 0x02198018 0x000000a0", "readl 0x02198018",
        "writel 0x02198000 0x00000001", "readl 0x02198008",
        "readl 0x0219800c", "readl 0x02198008",
        # SNVS high-power alarm registers and write-one-clear status. HP's
        # stock updater uses this alarm as the FreeRTOS tickless-idle wakeup.
        "writel 0x020cc02c 0x00001234", "writel 0x020cc030 0x89abcdef",
        "readl 0x020cc02c", "readl 0x020cc030",
        "writel 0x020cc0fc 0x00000001", "readl 0x020cc014",
        "writel 0x020cc014 0x00000040", "readl 0x020cc014",
        # LCDIF atomic aliases and deferred NEXT buffer switch.
        "writel 0x021c8000 0x00000001", "writel 0x021c8004 0x00000002",
        "readl 0x021c8000", "writel 0x021c8008 0x00000001",
        "readl 0x021c8000", "writel 0x021c8040 0x88000000",
        "writel 0x021c8050 0x88010000", "readl 0x021c8040",
        # Captured synthetic NAND geometry and ECC strength.
        "readl 0x01806110", "readl 0x01806114", "readl 0x01806118",
        "readl 0x0180611c", "readl 0x01806120", "readl 0x01806124",
        # APBH CURCMDAR identifies the last descriptor fetched from a chain.
        # HP's stock NAND probe rejects a valid READID result if this remains
        # zero after the terminal descriptor completes.
        "writel 0x80001000 0x00000000", "writel 0x80001004 0x00000048",
        "writel 0x80001008 0x00000000", "writel 0x01804110 0x80001000",
        "writel 0x01804140 0x00000001", "readl 0x01804100",
        # BCH write descriptors source payload/aux through PIO pointer words,
        # not the APBH data-buffer field. Program and read one byte back.
        "writel 0x80002000 0xaabbccdd", "writel 0x80003000 0x11223344",
        "writel 0x80001100 0x00000000", "writel 0x80001104 0x00006048",
        "writel 0x80001108 0x00000000", "writel 0x8000110c 0x00000000",
        "writel 0x80001110 0x00000000", "writel 0x80001114 0x00001000",
        "writel 0x80001118 0x00000000", "writel 0x8000111c 0x80002000",
        "writel 0x80001120 0x80003000", "writel 0x01806100 0x00000080",
        "writel 0x01806104 0x00000005", "writel 0x01804110 0x80001100",
        "writel 0x01804140 0x00000001", "writel 0x01806100 0x00000010",
        "writel 0x01806100 0x00000000", "writel 0x01806104 0x00000005",
        "readl 0x01806108", "readl 0x01806170",
        # Sparse NAND persistence, erased-page semantics, and bad blocks.
        "writel 0x01806104 0x00000001", "writel 0x01806100 0x00000080",
        "writel 0x0180614c 0x4433225a", "writel 0x01806100 0x00000010",
        "writel 0x01806100 0x00000000", "writel 0x01806104 0x00000002",
        "readl 0x01806108", "writel 0x01806104 0x00000001",
        "readl 0x0180614c", "writel 0x01806128 0x00000001",
        "writel 0x01806104 0x00000040", "readl 0x01806128",
        "writel 0x01806100 0x000000d0", "readl 0x0180610c",
        # BCH corrected and uncorrectable faults at data/OOB boundaries.
        "writel 0x01806130 0x00000001", "writel 0x01806134 0x00000001",
        "writel 0x01806138 0x00030000", "writel 0x01806100 0x00000000",
        "writel 0x01806104 0x00000001", "readl 0x01806108",
        "readl 0x0180612c", "readl 0x01808100",
        "writel 0x01806130 0x00000002", "writel 0x01806138 0x00010000",
        "writel 0x01806100 0x00000000", "writel 0x01806104 0x00000001",
        "readl 0x01806108", "readl 0x01806148", "readl 0x01808100",
        "writel 0x01806130 0x00000001", "writel 0x01806138 0x000f0800",
        "writel 0x01806100 0x00000000", "writel 0x01806104 0x00000001",
        "readl 0x0180612c", "readl 0x01806138",
        # Wear promotion and read-disturb become deterministic bad/ECC errors.
        "writel 0x01806130 0x00000000", "writel 0x0180613c 0x00000001",
        "writel 0x01806104 0x00000080", "writel 0x01806100 0x000000d0",
        "readl 0x0180610c", "readl 0x01806144",
        "writel 0x01806100 0x000000d0", "readl 0x0180610c",
        "readl 0x01806144", "readl 0x01806128",
        "writel 0x01806104 0x00000003", "writel 0x01806100 0x00000080",
        "writel 0x01806108 0x000000a5", "writel 0x01806100 0x00000010",
        "readl 0x0180610c", "writel 0x01806140 0x00000001",
        "writel 0x01806100 0x00000000", "writel 0x01806104 0x00000003",
        "readl 0x01806108", "readl 0x01806148",
        "writel 0x01806100 0x00000000", "writel 0x01806104 0x00000003",
        "readl 0x01806108", "readl 0x01806148",
    ]) + "\n"
    process = subprocess.Popen([
        str(QEMU), "-machine", "hp-prime-g2",
        # This DMA/peripheral fixture assumes DDR was configured already.
        # Dedicated DDR tests exercise the strict cold default instead.
        "-global", "prime-g2-mmdc.preinitialized=on",
        "-global", "imx6ul-lcdif.prime-g2-panel=on", "-display", "none",
        "-monitor", "none", "-serial", "none", "-qtest", "stdio",
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = process.communicate(commands, timeout=2)
    except subprocess.TimeoutExpired:
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
    if process.returncode not in (0, -15):
        raise RuntimeError(stderr)
    replies = [line for line in stdout.splitlines() if line.startswith("OK")]
    reads = [int(line.split()[1], 16) for line in replies if len(line.split()) == 2]
    expected = [
        0x00005554,
        0x00000002,
        0xFEFB, 0x0001, 0xFEFF, 0xFEF3,
        0x00000020, 0x00000001, 0x000000D3, 0x00000000,
        0x00001234, 0x89ABCDEF, 0x00000040, 0x00000000,
        0x00000003, 0x00000002, 0x88000000,
        2048, 64, 131072, 4096, 8, 5, 0x80001000, 0xDD, 1,
        0xFF, 0x4433225A, 1, 0xE1,
        0x5A, 2, 2, 0x5B, 1, 0x80000000, 4, 0x000F0800,
        0xE0, 1, 0xE1, 2, 1,
        0xE0, 0xA5, 0, 0xA4, 1,
    ]
    if reads != expected:
        raise AssertionError(f"qtest reads differ\nexpected={expected}\nactual={reads}\n{stdout}")
    check_snvs_counter_domains_and_alarm()
    check_persistent_nand_overlay()
    print("PASS: GPIO pad status, KPP, battery ADC, SNVS HP alarm, LCDIF and persistent/restartable NAND/BCH correction, uncorrectable, OOB, wear, read-disturb, and bad-block semantics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
