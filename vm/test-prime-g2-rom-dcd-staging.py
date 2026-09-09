#!/usr/bin/env python3
"""DCD staging before late ECC failure, using disposable re-encoded fixtures."""
import importlib
from pathlib import Path
import struct
import subprocess
import tempfile

physical = importlib.import_module('test-prime-g2-physical-rom-boot')
recovery = importlib.import_module('test-prime-g2-rom-recovery')
mmdc = importlib.import_module('test-prime-g2-mmdc')
boot = physical.boot


def run(folder, case):
    fcb, _ = physical.decode_fcb(physical.read_record(0))
    layout = physical.fcb_layout(fcb)
    records = {}
    for start in (512, 1280):
        if case in ('split-late', 'split-error', 'split-boot-data', 'partial-final-page'):
            decoded = [layout.decode(physical.read_record(start + i)) for i in range(2)]
            assert not any(page.failed for page in decoded)
            payload = bytearray(b''.join(page.payload for page in decoded))
            self_address = struct.unpack_from('<I', payload, 0x414)[0]
            base = self_address - 0x400
            if case == 'partial-final-page':
                offset = struct.unpack_from('<I', payload, 0x410)[0] - base
                struct.pack_into('<I', payload, offset + 4, 0x4f23)
            elif case == 'split-boot-data':
                offset = struct.unpack_from('<I', payload, 0x410)[0] - base
                payload[0x7fc:0x808] = bytes(payload[offset:offset + 12])
                struct.pack_into('<I', payload, 0x410, base + 0x7fc)
            else:
                dcd = struct.unpack_from('<I', payload, 0x40c)[0] - base
                length = int.from_bytes(payload[dcd + 1:dcd + 3], 'big')
                command = bytes(payload[dcd:dcd + length])
                assert len(command) == length and 16 < length < 0x800
                payload[0x7f0:0x7f0 + length] = command
                struct.pack_into('<I', payload, 0x40c, base + 0x7f0)
            for i, page in enumerate(decoded):
                records[start + i] = layout.encode(bytes(payload[i*2048:(i+1)*2048]), page.metadata)
        broken_page = start + (0 if case == 'early' else 1 if case == 'split-error' else 10)
        record = physical.read_record(broken_page)
        for byte in range(12, 16):
            record[byte] ^= 0xff
        assert layout.decode(record).failed
        records[broken_page] = record
    overlay = physical.overlay(folder / (case + '.overlay'), records)
    monitor = folder / (case + '.qmp')
    qtest_path = folder / (case + '.qtest')
    command = boot.command(overlay, qmp_path=monitor) + [
        '-qtest', f'unix:{qtest_path},server=on,wait=off', '-qtest-log', '/dev/null']
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    qmp = q = None
    try:
        qmp = recovery.QMP(monitor)
        qmp.execute('stop')
        initialized = qmp.execute('qom-get', {
            'path': '/machine/soc/mmdc', 'property': 'initialized'})['return']
        q = recovery.QTest(qtest_path)
        if not initialized:
            mmdc.initialize(q)  # Open the gate before inspecting backing bytes.
        def memory(address, length):
            response = q.command(f'read 0x{address:x} 0x{length:x}').split()[1]
            return bytes.fromhex(response.removeprefix('0x'))
        actual = memory(0x877ff000, 11 * 2048)
        if case in ('early', 'split-error'):
            assert actual == bytes(len(actual)), 'unprepared image changed backing DDR'
        else:
            def logical_page(number):
                decoded = layout.decode(records.get(number) or physical.read_record(number))
                return layout.swap_marker(decoded.payload, decoded.metadata)[0]
            expected = b''.join(logical_page(page) for page in range(1280, 1290))
            if case == 'partial-final-page':
                expected = expected[:0x4f23] + bytes(10*2048 - 0x4f23)
            differences = [(i, a, b) for i, (a, b) in enumerate(zip(actual, expected)) if a != b]
            assert not differences, ('received prefix absent or corrupted after late ECC', differences[:16])
            assert actual[10*2048:] == bytes(2048), 'failed page reached DDR'
            assert memory(0x977ff000, 10*2048) == expected, 'DDR alias lost streamed prefix'
    finally:
        if q:
            q.close()
        if qmp:
            qmp.close()
        result = boot.stop(process)
    assert b'no valid i.MX6ULL NAND FCB/DBBT/IVT boot chain' in result, result[-2000:]
    assert b'U-Boot 2018.03' not in result
    if case in ('early', 'split-error'):
        assert b'DCD stage ready' not in result
        assert not initialized, 'pre-DCD error initialized DDR'
    else:
        assert initialized, 'post-DCD error did not leave initialized command state'
        count = 1 if case in ('late', 'partial-final-page') else 2
        for start in (512, 1280):
            stage = f'DCD stage ready after {count} firmware pages from {start}'.encode()
            failure = f'uncorrectable BCH in NAND firmware page {start + 10}'.encode()
            assert stage in result and failure in result, result[-3000:]
            assert result.index(stage) < result.index(failure), 'late error preceded DCD'
    print('PASS ROM DCD staging', case)


def main():
    original_command, original_nand = boot.command, boot.NAND
    boot.NAND = physical.PHYSICAL
    boot.command = lambda *args, **kwargs: original_command(*args, **kwargs) + [
        '-global', 'prime-g2-gpmi-bch.physical-pages=on']
    try:
        with tempfile.TemporaryDirectory(prefix='pg2dcdstage-') as directory:
            for case in ('early', 'late', 'split-late', 'split-error',
                         'split-boot-data', 'partial-final-page'):
                run(Path(directory), case)
    finally:
        boot.command, boot.NAND = original_command, original_nand


if __name__ == '__main__':
    main()
