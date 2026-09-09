#!/usr/bin/env python3
"""Execute a secure ARM guest through PWM IRQ entry, GIC EOI and return.

This is a nominal TCG integration check, not a silicon timing differential.
Only a temporary RAM payload is loaded; the calculator and NAND are untouched.
"""
import importlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time

recovery = importlib.import_module('test-prime-g2-rom-recovery')
ROOT = Path(__file__).resolve().parents[1]


def payload(folder, source=None):
    obj = folder / 'irq.o'
    subprocess.run([os.environ.get('CLANG', 'clang'), '--target=armv7-none-eabi',
                    '-c', str(source or ROOT / 'vm/guest/prime-g2-pwm-irq.S'),
                    '-o', str(obj)], check=True)
    data = obj.read_bytes()
    assert data[:7] == b'\x7fELF\x01\x01\x01', 'expected little-endian ELF32'
    offset = struct.unpack_from('<I', data, 32)[0]
    size, count, names_index = struct.unpack_from('<HHH', data, 46)
    sections = [struct.unpack_from('<10I', data, offset + i * size)
                for i in range(count)]
    names = sections[names_index]
    strings = data[names[4]:names[4] + names[5]]
    text = None
    for section in sections:
        assert not (section[1] in (4, 9) and section[5]), 'unresolved relocations'
        name = strings[section[0]:].split(b'\0', 1)[0]
        if name == b'.text':
            text = data[section[4]:section[4] + section[5]]
    assert text, 'missing code'
    result = folder / 'irq.bin'
    result.write_bytes(text)
    return result


def main():
    with tempfile.TemporaryDirectory(prefix='pg2pwmcpu-') as temporary:
        folder = Path(temporary)
        code = payload(folder)
        qt, qm = folder / 'qt', folder / 'qm'
        command = [str(recovery.QEMU), '-machine', 'hp-prime-g2',
                   '-global', 'prime-g2-mmdc.preinitialized=on',
                   '-accel', 'tcg', '-S', '-display', 'none', '-serial', 'none',
                   '-monitor', 'none', '-qtest-log', '/dev/null',
                   '-qtest', f'unix:{qt},server=on,wait=off',
                   '-qmp', f'unix:{qm},server=on,wait=off',
                   '-device', f'loader,file={code},addr=0x80010000,force-raw=on',
                   '-device', 'loader,addr=0x80010000,cpu-num=0']
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = qmp = None
        try:
            q = recovery.QTest(qt)
            qmp = recovery.QMP(qm)
            qmp.execute('cont')
            deadline = time.monotonic() + 10
            result = None
            while time.monotonic() < deadline:
                result = [q.readl(0x80020000 + 4 * i) for i in range(4)]
                if result[3] == 1 or result[0] == 0xffffffff:
                    break
                time.sleep(0.01)
            assert result == [1, 148, 1, 1], result
            print('PASS secure TCG guest: PWM SPI116 / ID148, IRQ vector, GIC EOI, exception return')
        finally:
            if q:
                q.close()
            if qmp:
                qmp.close()
            process.terminate()
            try:
                _, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                _, stderr = process.communicate(timeout=5)
            if process.returncode not in (0, -15):
                raise RuntimeError(stderr.decode(errors='replace'))


if __name__ == '__main__':
    main()
