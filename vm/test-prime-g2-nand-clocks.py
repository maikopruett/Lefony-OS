#!/usr/bin/env python3
"""Observe live CCM NAND clock outputs after guest register writes."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

recovery = importlib.import_module('test-prime-g2-rom-recovery')
boot = importlib.import_module('test-prime-g2-nand-rom-boot')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prime_g2_nand_clocks import decode


def main():
    capture = json.loads((ROOT / 'hardware/prime_g2/reference/rom-clock-nand-status-20260907.json').read_text())
    names = ('ANATOP_PLL_SYS', 'ANATOP_PFD_528', 'CCM_CSCMR1', 'CCM_CSCDR1', 'CCM_CCGR4', 'CCM_CCGR6')
    with tempfile.TemporaryDirectory(prefix='pg2clock-') as folder:
        directory = Path(folder)
        sock, monitor = directory / 'qtest', directory / 'qmp'
        process = subprocess.Popen([
            str(recovery.QEMU), '-machine', 'hp-prime-g2', '-accel', 'qtest',
            '-display', 'none', '-serial', 'none', '-monitor', 'none',
            '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null',
            '-qmp', f'unix:{monitor},server=on,wait=off'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = qmp = None
        try:
            q, qmp = recovery.QTest(sock), recovery.QMP(monitor)

            def write(name, value):
                address = int(capture['clock_registers'][name]['address'], 16)
                q.writel(address, value)
                masks = {'CCM_CSCMR1': 3 << 18, 'CCM_CSCDR1': (7 << 19) | (7 << 22),
                         'CCM_CCGR4': (3 << 26) | (3 << 28), 'CCM_CCGR6': (3 << 6) | (3 << 8),
                         'ANATOP_PLL_SYS': 0x1f001, 'ANATOP_PFD_528': 0x00bf00bf}
                assert q.readl(address) & masks[name] == value & masks[name], (name, hex(q.readl(address)), hex(value))

            def check():
                actual = {'clock_registers': {name: {'value': hex(q.readl(int(capture['clock_registers'][name]['address'], 16)))} for name in names}}
                roots = decode(actual)['roots']
                for name, root in roots.items():
                    rate = root['configured_hz']
                    hz = rate['numerator'] // rate['denominator'] if rate else 0
                    if not root['ccgr4_gate_encoding'] & 1 or not root['ccgr6_gate_encoding'] & 1:
                        hz = 0
                    expected = (1000000000 << 32) // hz if hz else 0
                    period = qmp.execute('qom-get', {'path': f'/machine/soc/ccm/{name}',
                                                  'property': 'qtest-clock-period'})['return']
                    assert period == expected, (name, period, expected, actual)

            for name in names:
                write(name, int(capture['clock_registers'][name]['value'], 16))
            check()
            for select in (0, 1 << 18, 1 << 19, (1 << 18) | (1 << 19)):
                write('CCM_CSCMR1', select)
                for divisor in range(8):
                    write('CCM_CSCDR1', (divisor << 19) | ((7 - divisor) << 22))
                    check()
            for register, offset in (('CCM_CCGR4', 28), ('CCM_CCGR4', 26),
                                      ('CCM_CCGR6', 8), ('CCM_CCGR6', 6)):
                original = int(capture['clock_registers'][register]['value'], 16)
                for gate in range(4):
                    write(register, (original & ~(3 << offset)) | gate << offset)
                    check()
                write(register, original)
            for pll in (0x80002000, 0x80002001, 0x80003001, 0x80000001,
                        0x80012001, 0x80016001):
                write('ANATOP_PLL_SYS', pll)
                check()
            write('ANATOP_PLL_SYS', 0x80002001)
            for pfd in (0x5058505b, 0x50d850db, 0, 0x5023500c):
                write('ANATOP_PFD_528', pfd)
                check()
            # Exercise the actual analog SET/CLR aliases, not only direct writes.
            address = int(capture['clock_registers']['ANATOP_PFD_528']['address'], 16)
            for offset in (4, 8, 12):
                q.writel(address + offset, (1 << 23) | (1 << 7))
                check()
            qmp.execute('system_reset')
            q.readl(0x020c401c)
            check()
            print('PASS live CCM NAND clocks: captured rates, independent mux/dividers, gates, '
                  'PLL/PFD states, analog aliases and reset', flush=True)
        finally:
            if qmp:
                qmp.close()
            if q:
                q.close()
            boot.stop(process)


if __name__ == '__main__':
    main()
