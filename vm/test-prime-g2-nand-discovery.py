#!/usr/bin/env python3
"""Exercise NAND discovery and decoded-capture DMA adaptation in real QEMU."""
import importlib
from pathlib import Path
import struct
import subprocess
import tempfile

from prime_gpmi_bch import Layout

recovery = importlib.import_module('test-prime-g2-rom-recovery')


def crc16(data):
    crc = 0x4f4e
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x8005 if crc & 0x8000 else 0)) & 0xffff
    return crc


def qualify(onfi=True, physical=False):
    with tempfile.TemporaryDirectory(prefix='prime-nand-discovery-') as folder:
        sock = Path(folder) / 'qtest.sock'
        overlay = Path(folder) / 'physical.overlay'
        process = subprocess.Popen([
            str(recovery.QEMU), '-machine', 'hp-prime-g2', '-S',
            '-display', 'none', '-serial', 'none', '-monitor', 'none',
            '-global', f'prime-g2-gpmi-bch.onfi={"on" if onfi else "off"}',
            '-global', f'prime-g2-gpmi-bch.physical-pages={"on" if physical else "off"}',
            *(['-global', f'prime-g2-gpmi-bch.stock-overlay={overlay}'] if physical else []),
            '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = None
        try:
            q = recovery.QTest(sock)

            def write(address, data):
                q.command(f'write 0x{address:x} {len(data)} 0x{data.hex()}')

            def read(address, size):
                return bytes.fromhex(q.command(f'read 0x{address:x} {size}').split()[1][2:])

            def dma(pio, direction=0, data=b'', length=0):
                buffer, descriptor = 0x80002000, 0x80001000
                if data:
                    write(buffer, data)
                    length = len(data)
                words = [0, (length << 16) | (len(pio) << 12) | 0x48 | direction,
                         buffer, *pio]
                write(descriptor, struct.pack('<' + 'I' * len(words), *words))
                q.writel(0x01804110, descriptor)
                q.writel(0x01804140, 1)
                return read(buffer, length) if direction == 1 else b''

            def command(value, address=0):
                # Actual CLE then ALE cycles, not diagnostic address shortcuts.
                dma([1 << 17], 2, bytes([value]))
                dma([2 << 17], 2, bytes([address]))

            command(0x90, 0x20)
            signature = dma([1 << 24], 1, length=4)
            assert signature == (b'ONFI' if onfi else b'\xff' * 4), signature
            command(0x90)
            assert dma([1 << 24], 1, length=5) == bytes.fromhex('2cdc909556')
            command(0xec)
            copies = dma([1 << 24], 1, length=768)
            if not onfi:
                assert copies == b'\xff' * 768
                print('PASS disabled ONFI legacy fallback')
                return
            first = copies[:256]
            assert copies == first * 3
            assert crc16(first[:254]) == int.from_bytes(first[254:], 'little')
            assert struct.unpack_from('<I', first, 80)[0] == 2048
            assert first[112] == 1  # requirement rounded to BCH strength 2 by MXS
            assert dma([1 << 24], 1, length=4) == b'\xff' * 4

            payload = bytes(index % 251 for index in range(2048))
            metadata = b'\xffPRIME-ECC'
            cases = [(t, 512, 4, 512, 13) for t in (0, 2, 6, 8)]
            if physical:
                cases.append((8, 0, 3, 1024, 14))
            for page, (strength, first_size, count, chunk_size, field) in enumerate(cases, 16):
                gf = int(field == 14) << 10
                l0 = ((count - 1) << 24) | (10 << 16) | ((strength // 2) << 11) | gf | (first_size // 4)
                l1 = (2112 << 16) | ((strength // 2) << 11) | gf | (chunk_size // 4)
                layout = Layout(l0, l1)
                q.writel(0x01808080, l0)
                q.writel(0x01808090, l1)
                dma_payload, dma_metadata = layout.swap_marker(payload, metadata)
                write(0x80003000, dma_payload)
                write(0x80004000, dma_metadata)
                q.writel(0x01806100, 0x80)
                q.writel(0x01806104, page)
                dma([0, 0, 0x1000, 2112, 0x80003000, 0x80004000])
                q.writel(0x01806100, 0x10)
                q.writel(0x01806100, 0)
                q.writel(0x01806104, page)
                # Explicit backing formats must never be silently conflated.
                raw = bytes(q.readl(0x01806108) for _ in range(2112))
                if physical:
                    assert raw == layout.encode(dma_payload, dma_metadata), strength
                else:
                    assert raw[:2048] == payload, strength
                    assert raw[2048:2058] == metadata, strength
                q.writel(0x01806104, page)
                write(0x80003000, bytes(2048))
                write(0x80004000, bytes(64))
                dma([1 << 24, 0, 0x1000, 2112, 0x80003000, 0x80004000])
                assert read(0x80003000, 2048) == dma_payload
                aux = read(0x80004000, 12 + count)
                assert aux[:10] == dma_metadata
                assert aux[12:] == bytes(count)
                if physical and strength:
                    # Store damaged physical codewords directly, with no fault
                    # injection hint supplied to the emulated BCH decoder.
                    for extra, mask in enumerate((1, 3, 255), 1):
                        damaged = bytearray(raw)
                        damaged[0] ^= mask
                        damaged[layout.chunks[1].end_bit // 8 - 1] ^= 1
                        expected = layout.decode(bytes(damaged))
                        fault_page = page + extra * 64
                        q.writel(0x01806100, 0x80)
                        q.writel(0x01806104, fault_page)
                        dma([0, 0, 0], 2, data=damaged)
                        q.writel(0x01806100, 0x10)
                        q.writel(0x01806100, 0)
                        q.writel(0x01806104, fault_page)
                        dma([1 << 24, 0, 0x1000, 2112, 0x80003000, 0x80004000])
                        assert read(0x80003000, 2048) == expected.payload, (strength, mask)
                        assert read(0x80004000, 12 + count) == layout.auxiliary(expected)
                        assert q.readl(0x01806148) == int(expected.failed)
                        fields = ((expected.status[0] << 8) | (4 if expected.failed else 0)
                                  | (8 if any(0 < s < 0xfe for s in expected.status) else 0))
                        assert q.readl(0x01808010) & 0xff0c == fields, (strength, mask)
                        assert q.readl(0x0180612c) == max(
                            status for status in expected.status if status < 0xfe)
            if physical:
                # Real stored erased pages; no decoder fault hints. Keep this
                # separate from the round-trip cases used by overlay replay.
                erased_layout = Layout(0x030a0880, 0x08400880)
                q.writel(0x01808080, 0x030a0880)
                q.writel(0x01808090, 0x08400880)
                patterns = [(), (0,), (80, 81), (80, 81, 82),
                            (erased_layout.chunks[1].end_bit - 1,),
                            (0, erased_layout.chunks[1].start_bit,
                             erased_layout.chunks[2].end_bit - 1)]
                images = []
                for positions in patterns:
                    damaged = bytearray(b'\xff' * 2112)
                    for bit in positions:
                        damaged[bit // 8] ^= 1 << (bit % 8)
                    images.append(bytes(damaged))
                images.append(erased_layout.encode(b'\xff' * 2048, b'\xff' * 10))
                # A programmed first codeword next to erased chunks.
                mixed = bytearray(images[-1])
                boundary = erased_layout.chunks[0].end_bit
                mixed_word = int.from_bytes(mixed, 'little') | (((1 << (2112 * 8 - boundary)) - 1) << boundary)
                images.append(mixed_word.to_bytes(2112, 'little'))
                for image_index, stored_image in enumerate(images):
                    stored_page = 512 + image_index
                    q.writel(0x01806100, 0x80)
                    q.writel(0x01806104, stored_page)
                    dma([0, 0, 0], 2, data=stored_image)
                    q.writel(0x01806100, 0x10)
                    for threshold in (0, 1, 2, 3, 2, 0):
                        q.writel(0x01808020, threshold)
                        q.writel(0x01806100, 0)
                        q.writel(0x01806104, stored_page)
                        dma([1 << 24, 0, 0x1000, 2112, 0x80003000, 0x80004000])
                        expected = erased_layout.decode(stored_image, threshold)
                        context = (image_index, threshold)
                        assert read(0x80003000, 2048) == expected.payload, context
                        assert read(0x80004000, 16) == erased_layout.auxiliary(expected), context
                        assert q.readl(0x01808170) == expected.erased_zero_count, context
                        assert q.readl(0x01806148) == int(expected.failed), context
                        fields = ((expected.status[0] << 8) | (4 if expected.failed else 0)
                                  | (8 if any(0 < s < 0xfe for s in expected.status) else 0))
                        assert q.readl(0x01808010) & 0xff0c == fields, context
                q.writel(0x01808020, 0)
                # Explicit error-field vectors, independent of the reference
                # status-to-register calculation above. No fault hints.
                data_buffer, meta_buffer = erased_layout.swap_marker(payload, metadata)
                base = erased_layout.encode(data_buffer, meta_buffer)
                assert base[2048] == 0xff  # preserve the physical bad-block marker
                vectors = [([], 0), ([(0, 1)], 0x108),
                           ([(1, 1)], 0x008), ([(1, 32)], 0x004),
                           ([(0, 1), (1, 32)], 0x10c),
                           ([(0, 32), (1, 1)], 0xfe0c), ([], 0)]
                for case_index, (errors, fields) in enumerate(vectors):
                    damaged = bytearray(base)
                    for chunk_index, bits in errors:
                        start = erased_layout.chunks[chunk_index].start_bit
                        for bit in range(start, start + bits):
                            damaged[bit // 8] ^= 1 << (bit % 8)
                    stored_page = 640 + case_index
                    q.writel(0x01806100, 0x80)
                    q.writel(0x01806104, stored_page)
                    dma([0, 0, 0], 2, data=damaged)
                    q.writel(0x01806100, 0x10)
                    assert not q.readl(0x0180610c) & 1, ('program failed', case_index)
                    q.writel(0x01806100, 0)
                    q.writel(0x01806104, stored_page)
                    q.writel(0x01808008, 1)
                    dma([1 << 24, 0, 0x1000, 2112, 0x80003000, 0x80004000])
                    observed = q.readl(0x01808010) & 0xff0c
                    assert observed == fields, (case_index, hex(observed), hex(fields))
                    q.writel(0x01808008, 1)
                    assert q.readl(0x01808010) & 0xff0c == fields
                    q.writel(0x01808010, 0xffffffff)
                    assert q.readl(0x01808010) & 0xff0c == fields
                print('PASS first/later chunk STATUS0 errors, simultaneous '
                      'corrected/uncorrectable flags, acknowledgement retention and refresh')
                print('PASS erased threshold boundaries, metadata/data/parity, '
                      'mixed/programmed FF pages and per-read DEBUG1 refresh')
            print('PASS ONFI CRC/copies and DMA read/write at strengths 0/2/6/8; '
                  + ('physical codewords corrected without error hints' if physical else 'decoded capture adaptation'))
        finally:
            if q:
                q.close()
            process.terminate()
            try:
                _, errors = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                _, errors = process.communicate(timeout=5)
            if process.returncode not in (0, -15):
                raise RuntimeError(errors.decode(errors='replace'))
        if physical:
            stored = overlay.read_bytes()
            assert stored[:8] == b'PG2RAW1\n'
            records = {}
            for offset in range(8, len(stored), 2120):
                kind, stored_page = struct.unpack_from('<B3xI', stored, offset)
                assert kind == 1
                records[stored_page] = stored[offset + 8:offset + 2120]
            assert records[page] == raw
            # Reject a physical overlay when opened as a decoded capture.
            rejected = subprocess.run([
                str(recovery.QEMU), '-machine', 'hp-prime-g2', '-display', 'none',
                '-serial', 'none', '-monitor', 'none',
                '-global', f'prime-g2-gpmi-bch.stock-overlay={overlay}'],
                capture_output=True, timeout=5)
            assert rejected.returncode != 0 and b'overlay' in rejected.stderr
            restarted = subprocess.Popen([
                str(recovery.QEMU), '-machine', 'hp-prime-g2', '-S', '-display', 'none',
                '-serial', 'none', '-monitor', 'none',
                '-global', 'prime-g2-gpmi-bch.physical-pages=on',
                '-global', f'prime-g2-gpmi-bch.stock-overlay={overlay}',
                '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            q = None
            try:
                q = recovery.QTest(sock)
                q.writel(0x01806100, 0)
                q.writel(0x01806104, page)
                assert bytes(q.readl(0x01806108) for _ in range(2112)) == raw
            finally:
                if q:
                    q.close()
                restarted.terminate()
                try:
                    restarted.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    restarted.kill()
                    restarted.communicate(timeout=5)
            print('PASS physical codeword persistence/restart and cross-format rejection')


if __name__ == '__main__':
    qualify()
    qualify(False)
    qualify(physical=True)
