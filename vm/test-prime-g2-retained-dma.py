#!/usr/bin/env python3
"""Replay the physically captured ROM DMA chain with explicit test codewords."""
import importlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from prime_nand_image import decode_fcb, fcb_layout

physical = importlib.import_module('test-prime-g2-physical-rom-boot')
recovery = importlib.import_module('test-prime-g2-rom-recovery')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_prime_g2_rom_dma import analyze
from prime_g2_raw_read_plan import build_plan


def main():
    capture_path = os.environ.get('LEFONY_PRIVATE_ROM_DMA_CAPTURE')
    if not capture_path:
        raise SystemExit('This physical replay requires LEFONY_PRIVATE_ROM_DMA_CAPTURE; '
                         'the public analyzer fixture contains synthetic payload words.')
    capture = json.loads(Path(capture_path).read_text())
    candidate, = analyze(capture)['candidates']
    raw_plan = build_plan(capture)
    row = candidate['row_3byte']
    fcb, _ = decode_fcb(physical.read_record(0))
    layout = fcb_layout(fcb)
    clean = bytes(physical.read_record(row))
    damaged = bytearray(clean)
    chunk = layout.chunks[2]
    parity_start = chunk.start_bit + chunk.message_bytes * 8
    for bit in range(parity_start, parity_start + 16):
        damaged[bit // 8] ^= 1 << (bit % 8)
    expected = layout.decode(bytes(damaged))
    assert expected.status == (0, 0, 0xfe, 0)
    assert expected.payload == layout.decode(clean).payload
    captured_payload = b''.join(struct.pack('<I', int(item['value'], 16))
                               for name, item in capture['dma_registers'].items()
                               if name.startswith('PAYLOAD_'))
    with tempfile.TemporaryDirectory(prefix='pg2replay-') as folder:
        directory = Path(folder)
        for label, record, statuses, status0 in (
                ('clean-reference', clean, (0, 0, 0, 0), 0),
                ('synthetic-parity-errors', bytes(damaged), (0, 0, 0xfe, 0), 4)):
            overlay = physical.overlay(directory / (label + '.overlay'), {row: record})
            sock = directory / (label + '.sock')
            process = subprocess.Popen([
                str(recovery.QEMU), '-machine', 'hp-prime-g2', '-S', '-display', 'none',
                '-serial', 'none', '-monitor', 'none',
                '-global', 'prime-g2-gpmi-bch.physical-pages=on',
                '-global', f'prime-g2-gpmi-bch.stock-nand={physical.PHYSICAL}',
                '-global', f'prime-g2-gpmi-bch.stock-overlay={overlay}',
                '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            q = None
            try:
                q = recovery.QTest(sock)
                for name, item in capture['dma_registers'].items():
                    if name.startswith('OCRAM_'):
                        q.writel(int(item['address'], 16), int(item['value'], 16))
                for name in ('BCH_FLASH0LAYOUT0', 'BCH_FLASH0LAYOUT1', 'BCH_MODE'):
                    item = capture['nand_registers'][name]
                    q.writel(int(item['address'], 16), int(item['value'], 16))
                payload = int(candidate['payload_address'], 16)
                auxiliary = int(candidate['auxiliary_address'], 16)
                q.command(f'memset 0x{payload:x} 2048 0xa5')
                q.command(f'memset 0x{auxiliary:x} 64 0xa5')
                q.writel(0x01808008, 1)
                q.writel(0x01804110, int(candidate['start_descriptor'], 16))
                q.writel(0x01804140, 1)
                def read(address, length):
                    return bytes.fromhex(q.command(f'read 0x{address:x} {length}').split()[1][2:])
                data, aux = read(payload, 2048), read(auxiliary, 64)
                assert tuple(aux[12:16]) == statuses, (label, aux.hex())
                logical, _ = layout.swap_marker(data, aux[:10])
                assert logical == captured_payload, label
                assert q.readl(0x01808010) & 0xff0c == status0, label
                assert q.readl(0x01804100) == int(capture['dma_registers']['APBH_CH0_CURCMDAR']['value'], 16)
                assert q.readl(0x01804110) == 0
                assert q.readl(0x01804130) == 0
                assert q.readl(0x01804140) == 0
                assert q.readl(0x01804120) == 0x48, 'captured terminal command is not exposed'
                q.writel(0x01804120, 0xffffffff)
                assert q.readl(0x01804120) == 0x48, 'CMD must be read-only'
                # Preserve the complete raw destination, including the 64 bytes
                # beyond the ordinary decoded payload. No NAND writes occur.
                q.command(f'memset 0x{payload + 2048:x} 64 0x5a')
                saved_ram = read(payload, 2112)
                saved_aux = read(auxiliary, 64)
                saved_status = q.readl(0x01808010)
                saved_overlay = overlay.read_bytes()
                for edit in raw_plan['descriptor_edits']:
                    assert q.readl(edit['address']) == edit['before']
                    q.writel(edit['address'], edit['after'])
                try:
                    q.writel(0x01804110, raw_plan['start_descriptor'])
                    q.writel(0x01804140, 1)
                    assert read(payload, 2112) == record, 'raw parity/data bytes differ'
                    assert read(auxiliary, 64) == saved_aux, 'raw read touched auxiliary RAM'
                    assert q.readl(0x01808010) == saved_status, 'raw read ran BCH'
                    assert q.readl(0x01804100) == raw_plan['terminal_descriptor']
                    assert q.readl(0x01804140) == 0
                    assert overlay.read_bytes() == saved_overlay, 'read modified NAND overlay'
                finally:
                    for edit in raw_plan['descriptor_edits']:
                        q.writel(edit['address'], edit['before'])
                    q.command(f'write 0x{payload:x} 2112 0x{saved_ram.hex()}')
                assert read(payload, 2112) == saved_ram, 'incomplete RAM restoration'
                for edit in raw_plan['descriptor_edits']:
                    assert q.readl(edit['address']) == edit['before']
                # Restoration must also work functionally: rerun the original
                # BCH-enabled chain and recover the same result and status.
                q.writel(0x01808008, 1)
                q.writel(0x01804110, raw_plan['start_descriptor'])
                q.writel(0x01804140, 1)
                assert read(payload, 2048) == data
                assert read(auxiliary, 64) == aux
                assert q.readl(0x01808010) == saved_status
                assert read(payload + 2048, 64) == saved_ram[2048:]
                assert overlay.read_bytes() == saved_overlay
                print(f'PASS raw 2112-byte read and RAM/descriptor restoration: {label}', flush=True)
                q.writel(0x01804110, 0)  # no descriptor fetched for this field check
                q.writel(0x01804140, 1)
                assert q.readl(0x01804140) == 0x10000
                q.writel(0x01804140, 2)
                assert q.readl(0x01804140) == 0x30000
                q.writel(0x01804140, 0x10000)  # PHORE is not directly writable
                assert q.readl(0x01804140) == 0x30000
                print(f'PASS exact retained ROM chain: {label}', flush=True)
            finally:
                if q:
                    q.close()
                physical.boot.stop(process)
    print('Synthetic parity case explains a possible mechanism, not the unknown physical parity bytes.')


if __name__ == '__main__':
    main()
