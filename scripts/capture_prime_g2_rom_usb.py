#!/usr/bin/env python3
"""Read Prime ROM descriptors and fixed status/clock registers; never reset or flash."""

import argparse
import ctypes
import json
import struct
import subprocess
import sys
from pathlib import Path

from prime_g2_usb_diag import LibUSB, USBError


REGISTER_PROFILES = {
    "dma-status": {"CCM_CCGR0": 0x020c4068, "APBH_CTRL0": 0x01804000,
                   "APBH_CTRL1": 0x01804010, "APBH_CTRL2": 0x01804020,
                   "APBH_CHANNEL_CTRL": 0x01804030, "APBH_CH0_CURCMDAR": 0x01804100,
                   "APBH_CH0_NXTCMDAR": 0x01804110, "APBH_CH0_CMD": 0x01804120,
                   "APBH_CH0_BAR": 0x01804130, "APBH_CH0_SEMA": 0x01804140,
                   "APBH_CH0_DEBUG1": 0x01804150, "APBH_CH0_DEBUG2": 0x01804160},
    "src": {"SRC_SCR": 0x020d8000, "SRC_SBMR1": 0x020d8004, "SRC_SRSR": 0x020d8008,
            "SRC_SBMR2": 0x020d801c, "SRC_GPR9": 0x020d8040, "SRC_GPR10": 0x020d8044},
    "clocks": {"CCM_CCDR": 0x020c4004, "CCM_CCSR": 0x020c400c, "CCM_CACRR": 0x020c4010,
               "CCM_CBCDR": 0x020c4014, "CCM_CBCMR": 0x020c4018,
               "CCM_CSCMR1": 0x020c401c, "CCM_CSCDR1": 0x020c4024,
               "CCM_CCGR0": 0x020c4068, "CCM_CCGR4": 0x020c4078,
               "CCM_CCGR6": 0x020c4080, "ANATOP_PLL_ARM": 0x020c8000,
               "ANATOP_PLL_USB1": 0x020c8010, "ANATOP_PLL_SYS": 0x020c8030,
               "ANATOP_PFD_528": 0x020c8100},
    "nand-status": {"CCM_CCGR4": 0x020c4078, "CCM_CCGR6": 0x020c4080,
                    "BCH_CTRL": 0x01808000, "BCH_STATUS0": 0x01808010,
                    "BCH_MODE": 0x01808020, "BCH_FLASH0LAYOUT0": 0x01808080,
                    "BCH_FLASH0LAYOUT1": 0x01808090, "BCH_VERSION": 0x01808160,
                    "BCH_DEBUG1": 0x01808170, "GPMI_CTRL0": 0x01806000,
                    "GPMI_CTRL1": 0x01806060, "GPMI_TIMING0": 0x01806070,
                    "GPMI_TIMING1": 0x01806080, "GPMI_TIMING2": 0x01806090,
                    "GPMI_STAT": 0x018060b0},
}


def nand_clocks_enabled(values: dict) -> bool:
    return ((int(values['CCM_CCGR4']['value'], 16) & 0xff003000) == 0xff003000
            and (int(values['CCM_CCGR6']['value'], 16) & 0x3c0) == 0x3c0)


def dma_clock_enabled(values: dict) -> bool:
    return int(values['CCM_CCGR0']['value'], 16) & 0x30 == 0x30


def dma_chain_window(cursor: int, semaphore: int) -> range:
    if semaphore & 0x00ff0000 or cursor & 3 or not 0x00900300 <= cursor <= 0x0091ff00:
        raise USBError("DMA chain capture refused: active channel or pointer outside bounded OCRAM")
    return range(cursor - 768, cursor + 256, 4)


def capture_registers(profile: str) -> dict:
    """Issue only SDP READ_REGISTER for a fixed, documented register profile.

    The HID command uses an OUT transfer, but it requests a register read:
    this function contains no WRITE_REGISTER, WRITE_FILE, DCD, or JUMP command.
    macOS uses its native HID driver without administrator access or detach.
    Other platforms retain the libusb transport.
    """
    registers = REGISTER_PROFILES['dma-status' if profile in ('dma-chain', 'dma-buffers') else profile]
    if sys.platform == "darwin":
        root = Path(__file__).resolve().parents[1]
        source = root / "scripts/capture_prime_g2_rom_hid.c"
        executable = root / "build/capture-prime-rom-hid"
        if not executable.is_file() or source.stat().st_mtime_ns > executable.stat().st_mtime_ns:
            executable.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["clang", "-Wall", "-Wextra", "-Werror",
                            "-framework", "IOKit", "-framework", "CoreFoundation",
                            str(source), "-o", str(executable)], check=True)
        command = [str(executable)] + (["--" + profile] if profile != "src" else [])
        result = subprocess.run(command, check=True, capture_output=True,
                                text=True, timeout=20)
        key = {"clocks": "clock_registers", "src": "src_registers",
               "nand-status": "nand_registers", "dma-status": "dma_registers",
               "dma-chain": "dma_registers", "dma-buffers": "dma_registers"}[profile]
        captured = json.loads(result.stdout)[key]
        if profile in ('dma-chain', 'dma-buffers'):
            window = dma_chain_window(int(captured['APBH_CH0_CURCMDAR']['value'], 16),
                                      int(captured['APBH_CH0_SEMA']['value'], 16))
            expected = dict(REGISTER_PROFILES['dma-status'])
            expected.update({f'OCRAM_{address:08x}': address for address in window})
            if profile == 'dma-buffers':
                from analyze_prime_g2_rom_dma import analyze
                candidates = analyze({'dma_registers': captured}, include_buffers=False)['candidates']
                if len(candidates) != 1:
                    raise USBError('DMA buffers require one validated retained NAND read chain')
                for prefix, key, length in (('PAYLOAD', 'payload_address', 2048),
                                             ('AUX', 'auxiliary_address', 64)):
                    start = int(candidates[0][key], 16)
                    if start & 3 or not 0x00900000 <= start <= 0x00920000 - length:
                        raise USBError('DMA buffer outside aligned OCRAM')
                    expected.update({f'{prefix}_{a:08x}': a for a in range(start, start + length, 4)})
            if {name: int(item['address'], 16) for name, item in captured.items()} != expected:
                raise USBError('Native DMA chain capture returned an unexpected address set')
        return captured
    if profile in ('dma-chain', 'dma-buffers'):
        raise USBError('Bounded DMA chain capture currently requires the native macOS HID helper')
    with LibUSB(0x15a2, 0x0080) as usb:
        lib = usb.lib
        lib.libusb_claim_interface.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.libusb_claim_interface.restype = ctypes.c_int
        lib.libusb_release_interface.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.libusb_interrupt_transfer.argtypes = [
            ctypes.c_void_p, ctypes.c_ubyte, ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_uint]
        lib.libusb_interrupt_transfer.restype = ctypes.c_int
        result = lib.libusb_claim_interface(usb.handle, 0)
        if result < 0:
            raise USBError(f"Cannot claim ROM HID interface: libusb {result}; "
                           "macOS may require running this read-only capture with sudo")
        try:
            def report() -> bytes:
                buffer = (ctypes.c_ubyte * 65)()
                actual = ctypes.c_int()
                result = lib.libusb_interrupt_transfer(
                    usb.handle, 0x81, buffer, 65, ctypes.byref(actual), 1500)
                if result < 0:
                    raise USBError(f"ROM interrupt read failed: libusb {result}")
                return bytes(buffer[:actual.value])

            result = {}
            for name, address in registers.items():
                if profile == "dma-status" and name == "APBH_CTRL0" and not dma_clock_enabled(result):
                    raise USBError("DMA status capture refused: APBHDMA clock gate is not enabled")
                if profile == "nand-status" and name == "BCH_CTRL" and not nand_clocks_enabled(result):
                    raise USBError("NAND status capture refused: clock gates are not all enabled")
                command = b"\x01" + struct.pack(">HIBIIB", 0x0101, address, 32, 4, 0, 0)
                buffer = (ctypes.c_ubyte * len(command)).from_buffer_copy(command)
                count = lib.libusb_control_transfer(
                    usb.handle, 0x21, 9, 0x201, 0, buffer, len(command), 1500)
                if count != len(command):
                    raise USBError(f"SDP READ_REGISTER submission failed: {count}")
                security = report()
                if security[:5] != bytes.fromhex("0356787856"):
                    raise USBError(f"ROM is not reporting HAB open: {security.hex()}")
                data = report()
                if len(data) < 5 or data[0] != 4:
                    raise USBError(f"Unexpected SDP register reply: {data.hex()}")
                result[name] = {"address": f"0x{address:08x}",
                                "value": f"0x{int.from_bytes(data[1:5], 'little'):08x}"}
            return result
        finally:
            lib.libusb_release_interface(usb.handle, 0)


def capture_src() -> dict:
    return capture_registers("src")


def capture() -> dict:
    with LibUSB(0x15a2, 0x0080) as usb:
        def descriptor(kind: int, value: int, language: int = 0) -> str:
            buffer = (ctypes.c_ubyte * 255)()
            result = usb.lib.libusb_control_transfer(
                usb.handle, kind, 6, value, language, buffer, 255, 1500)
            if result < 0:
                raise USBError(f"GET_DESCRIPTOR {value:#06x}: libusb {result}")
            return bytes(buffer[:result]).hex()

        return {
            "device": descriptor(0x80, 0x100),
            "configuration": descriptor(0x80, 0x200),
            "hid_report": descriptor(0x81, 0x2200),
            "strings": {str(index): descriptor(0x80, 0x300 | index,
                                              0x409 if index else 0)
                        for index in (0, 1, 2, 4, 5)},
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", type=Path,
                        help="Compare captured bytes with an existing JSON fixture")
    parser.add_argument("--src", action="store_true",
                        help="Also read six SRC control/status/boot-mode registers (native HID on macOS; no sudo)")
    parser.add_argument("--clocks", action="store_true",
                        help="Read fixed CCM/ANATOP controls; no clock writes or gated NAND MMIO reads")
    parser.add_argument("--nand-status", action="store_true",
                        help="Read fixed NAND control/status registers only if CCM clock gates are enabled")
    parser.add_argument("--dma-status", action="store_true",
                        help="Read fixed APBH channel-0 status only if its CCM clock gate is enabled")
    parser.add_argument("--dma-chain", action="store_true",
                        help="Also read 1024 bytes of OCRAM around an idle channel-0 descriptor (macOS)")
    parser.add_argument("--dma-buffers", action="store_true",
                        help="Also read the retained chain's bounded OCRAM payload/auxiliary buffers (macOS)")
    parser.add_argument("--output", type=Path,
                        help="Save a new JSON capture; refuses to overwrite an existing file")
    args = parser.parse_args()
    if args.output and args.check:
        parser.error('--output and --check are mutually exclusive')
    if args.output and args.output.exists():
        parser.error('--output already exists; choose a new capture path')
    actual = capture()
    if args.src:
        actual["src_registers"] = capture_src()
    if args.clocks:
        actual["clock_registers"] = capture_registers("clocks")
    if args.nand_status:
        actual["nand_registers"] = capture_registers("nand-status")
    if args.dma_status or args.dma_chain or args.dma_buffers:
        actual["dma_registers"] = capture_registers('dma-buffers' if args.dma_buffers else
                                                    'dma-chain' if args.dma_chain else 'dma-status')
    if args.check:
        expected = json.loads(args.check.read_text())
        differing = [key for key, value in actual.items() if expected.get(key) != value]
        if differing:
            raise SystemExit(f"Physical ROM capture differs: {', '.join(differing)}")
        print("PASS: physical ROM descriptors and requested registers match the fixture")
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as target:
            json.dump(actual, target, indent=2)
            target.write('\n')
        print(f'Saved read-only capture: {args.output}')
    else:
        print(json.dumps(actual, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
