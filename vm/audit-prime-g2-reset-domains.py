#!/usr/bin/env python3
"""Report modeled watchdog reset domains; not a physical retention oracle."""
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import time

mmdc = importlib.import_module('test-prime-g2-mmdc')
SRC = 0x020d8000
WDOG = 0x020bc000
CCDR = 0x020c4004


def clock_handshake_access():
    with tempfile.TemporaryDirectory(prefix='pg2ccdraudit-') as directory:
        vm = mmdc.state.VM(Path(directory), 'clock', None)
        try:
            result = {'reset_value': hex(vm.q.readl(CCDR)), 'writes': []}
            for value in (0, 1 << 16, 1 << 17, 3 << 16):
                vm.q.writel(CCDR, value)
                result['writes'].append({'written': hex(value), 'readback': hex(vm.q.readl(CCDR))})
            vm.qmp.execute('system_reset')
            result['after_system_reset'] = hex(vm.q.readl(CCDR))
            return result
        finally:
            vm.close()


def observe(warm_enabled):
    with tempfile.TemporaryDirectory(prefix='pg2resetdomain-') as directory:
        vm = mmdc.state.VM(Path(directory), 'watchdog', None)
        try:
            q = vm.q
            mmdc.initialize(q)
            q.writel(0x80010000, 0x12345678)
            q.writel(0x00920000, 0xabcdef01)
            scr = (q.readl(SRC) & ~1) | int(warm_enabled)
            q.writel(SRC, scr)
            assert q.readl(SRC) == scr
            q.writel(SRC + 8, 0xffffffff)  # Clear earlier reset causes.
            q.writew(WDOG, 4)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and not q.readl(SRC + 8) & 16:
                time.sleep(0.01)
            assert q.readl(SRC + 8) & 16, 'watchdog reset not observed'
            result = {
                'scr_before': hex(scr),
                'scr_after': hex(q.readl(SRC)),
                'reset_status': hex(q.readl(SRC + 8)),
                'mmdc_initialized': mmdc.ready(vm),
                'mdctl': hex(q.readl(mmdc.BASE)),
                'mapsr': hex(q.readl(mmdc.BASE + 0x404)),
                'ocram_marker': hex(q.readl(0x00920000)),
            }
            # Open the gate before inspecting retained bytes: a closed-read
            # zero would not establish that RAM had actually been erased.
            mmdc.initialize(q)
            result['ddr_after_reinitialize'] = hex(q.readl(0x80010000))
            return result
        finally:
            vm.close()


def main():
    disabled, enabled = observe(False), observe(True)
    compare = ('mmdc_initialized', 'mdctl', 'mapsr', 'ocram_marker',
               'ddr_after_reinitialize')
    same = all(disabled[key] == enabled[key] for key in compare)
    print(json.dumps({
        'qemu_sha256': hashlib.sha256(mmdc.state.recovery.QEMU.read_bytes()).hexdigest(),
        'physical_access': False,
        'full_hardware_parity': False,
        'ccdr_access': clock_handshake_access(),
        'warm_reset_disabled': disabled,
        'warm_reset_enabled': enabled,
        'same_modeled_ddr_outcome': same,
        'interpretation': 'Identical outcomes expose an unqualified warm-reset distinction; they do not prove physical retention or loss.',
    }, indent=2))


if __name__ == '__main__':
    main()
