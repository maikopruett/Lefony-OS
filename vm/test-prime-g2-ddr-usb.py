#!/usr/bin/env python3
"""ROM SDP DMA writes must honor DDR availability; initialize through USB DCD."""
import importlib
from pathlib import Path
import struct
import tempfile

recovery = importlib.import_module('test-prime-g2-rom-recovery')
mmdc = importlib.import_module('test-prime-g2-mmdc')


def main():
    with tempfile.TemporaryDirectory(prefix='pg2ddrusb-') as directory:
        vm = recovery.RecoveryVM(Path(directory) / 'vm')
        try:
            recovery.arm_rom_usb_boot(vm.qtest)
            vm.qtest.writew(recovery.WDOG1_WCR, 4)
            vm.wait_for_mode('rom-sdp')
            vm.usb.connect_and_enumerate()
            address = 0x80800000
            recovery.sdp_command(vm.usb, 0x0404, address, 4)
            vm.usb.setup_packet(0x21, 9, 0x202, length=5)
            response = vm.usb.command('OUT 0211223344')
            assert response != 'OK' and response.startswith('ERR'), response
            assert vm.usb.command('RESET') == 'OK'
            pairs = [(mmdc.BASE + 0x1c, 0x8000), (mmdc.BASE, 0x83180000)]
            pairs += [(mmdc.BASE + 0x1c, value) for value in mmdc.COMMANDS]
            pairs += [(mmdc.BASE + 0x1c, 0)]
            body = b''.join(struct.pack('>II', *pair) for pair in pairs)
            command = b'\xcc' + struct.pack('>H', len(body) + 4) + b'\x04' + body
            dcd = b'\xd2' + struct.pack('>H', len(command) + 4) + b'\x40' + command
            recovery.sdp_command(vm.usb, 0x0a0a, 0x00910000, len(dcd))
            vm.usb.control_out(0x21, 9, 0x202, payload=b'\x02' + dcd)
            recovery.sdp_security(vm.usb)
            assert vm.usb.endpoint_in(1, 65) == bytes.fromhex('04128a8a12')
            assert vm.qtest.readl(address) == 0, 'rejected DMA write reached RAM'
            recovery.sdp_download(vm.usb, address, b'\x78\x56\x34\x12')
            assert vm.qtest.readl(address) == 0x12345678
            assert vm.qtest.readl(address + 0x10000000) == 0x12345678
            print('PASS ROM SDP DMA rejects unavailable DDR; USB DCD enables subsequent download and alias readback')
            vm.qtest.writel(mmdc.BASE + 0x404, 0x00200001)
            recovery.sdp_command(vm.usb, 0x0404, address, 4)
            vm.usb.setup_packet(0x21, 9, 0x202, length=5)
            response = vm.usb.command('OUT 0211223344')
            assert response.startswith('ERR'), response
            assert vm.usb.command('RESET') == 'OK'
            vm.qtest.writel(mmdc.BASE + 0x404, 1)
            assert vm.qtest.readl(address) == 0x12345678, 'self-refresh DMA changed retained memory'
            print('PASS ROM SDP DMA blocked during software self-refresh; wake preserves data')
        finally:
            vm.close()


if __name__ == '__main__':
    main()
