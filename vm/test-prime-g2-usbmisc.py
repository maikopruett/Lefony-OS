#!/usr/bin/env python3
"""USBNC initialization contract from Lefony and the i.MX Linux driver.

Includes BVALID cable-event wakeup and checkpoint restoration. Analog
thresholds, DP/DM wakeup and physical reset defaults are not qualified.
"""
import importlib
from pathlib import Path
import subprocess
import tempfile

recovery = importlib.import_module('test-prime-g2-rom-recovery')
irq = importlib.import_module('test-prime-g2-bch-irq')
migration = importlib.import_module('test-prime-g2-nand-migration')


def main():
    with tempfile.TemporaryDirectory(prefix='pg2usbmisc-') as folder:
        directory = Path(folder)
        resources = []
        def launch(name, incoming=False):
            sock, qm, us = (directory / (name + suffix) for suffix in ('.qt', '.qm', '.usb'))
            command = [str(recovery.QEMU), '-machine', 'hp-prime-g2', '-S',
                '-display', 'none', '-serial', 'none', '-monitor', 'none',
                '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null',
                '-qmp', f'unix:{qm},server=on,wait=off',
                '-chardev', f'socket,id=host,path={us},server=on,wait=off',
                '-global', 'prime-g2-usbotg-device.chardev=host']
            if incoming:
                command += ['-incoming', 'defer']
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            item = [process, None, None, None]
            resources.append(item)
            q, qmp = irq.IRQTest(sock), recovery.QMP(qm)
            item[1:3] = [q, qmp]
            usb = recovery.PrimeUSBHost(us)
            item[3] = usb
            children = qmp.execute('qom-list', {'path': '/machine/unattached'})['return']
            child, = [c['name'] for c in children if c['type'] == 'child<prime-g2-usbotg-device>']
            q.command(f'irq_intercept_out /machine/unattached/{child} sysbus-irq')
            return q, qmp, usb
        try:
            q, qmp, usb = launch('src')
            control, phy = 0x02184800, 0x02184818
            # Mirror usb_diagnostics.cpp's read-modify-write sequence exactly.
            q.writel(control, q.readl(control) | (1 << 1))
            nonburst = q.readl(control)
            q.writel(control, nonburst & ~((1 << 29) | (1 << 17) | (1 << 16) | (1 << 10)))
            final_control = q.readl(control)
            q.writel(phy, q.readl(phy) | (2 << 8))
            final_phy = q.readl(phy)
            assert (nonburst & 2 and final_control & 2 and
                    final_phy & (3 << 8) == 2 << 8), {
                'error': 'USBNC initialization configuration was lost',
                'nonburst_readback': hex(nonburst), 'final_control': hex(final_control),
                'phy_readback': hex(final_phy), 'expected_nonburst_bit': '0x2',
                'expected_vbus_source_bits': '0x200'}
            # Independent port configuration must not overwrite port zero.
            q.writel(control + 4, q.readl(control + 4) | (1 << 7))
            assert q.readl(control) == final_control
            assert q.readl(phy) == final_phy
            print('PASS USBNC native initialization readback and port isolation', flush=True)
            wie, vbus, wir = 1 << 10, 1 << 17, 1 << 31
            def wake(expected):
                assert bool(q.readl(control) & wir) == expected
                assert q.levels.get(0, False) == expected
            q.writel(control, 2 | vbus)  # WIE disabled
            assert usb.command('CONNECT') == 'OK'
            wake(False)
            q.writel(control, 2 | vbus | wie)
            assert usb.command('CONNECT') == 'OK'  # no new edge
            wake(False)
            assert usb.command('DISCONNECT') == 'OK'
            wake(True)
            q.writel(control, q.readl(control) | wir)  # WIR is not W1C
            wake(True)
            q.writel(0x02184144, 0xffffffff)  # normal USBSTS acknowledgement
            wake(True)
            q.writel(0x02184140, 2)  # ChipIdea reset does not reset USBNC
            wake(True)
            assert q.readl(phy) == final_phy
            q.writel(control, 2)
            wake(False)
            q.writel(control, 2 | wie)  # VBUS source disabled
            assert usb.command('CONNECT') == 'OK'
            wake(False)
            q.writel(control, 2 | vbus | wie)
            assert usb.command('DISCONNECT') == 'OK'
            wake(True)
            q.writel(control + 4, 0)
            wake(True)
            print('PASS BVALID edge, source/IRQ enables, sticky request, WIE acknowledgement and reset separation', flush=True)
            dst_q, dst_qmp, dst_usb = launch('dst', incoming=True)
            uri = 'unix:' + str(directory / 'migration.sock')
            dst_qmp.execute('migrate-incoming', {'uri': uri})
            qmp.execute('migrate', {'uri': uri})
            from types import SimpleNamespace
            migration.wait_migration(SimpleNamespace(qmp=qmp))
            migration.wait_migration(SimpleNamespace(qmp=dst_qmp))
            q, qmp, usb = dst_q, dst_qmp, dst_usb
            wake(True)
            assert q.readl(phy) == final_phy
            q.writel(control, 2)
            wake(False)
            q.writel(control, 2 | vbus | wie)
            assert usb.command('CONNECT') == 'OK'
            wake(True)
            qmp.execute('system_reset')
            q.readl(control)
            wake(False)
            print('PASS USBNC pending wake migration, destination cable event and system reset', flush=True)
            q.writel(0x02184144, 0xffffffff)
            q.writel(0x02184148, 4)  # enable normal port-change IRQ
            assert usb.command('DISCONNECT') == 'OK'
            assert q.readl(0x02184144) & 4  # drain asynchronous qtest IRQ events
            assert q.levels.get(0, False)
            assert not q.readl(control) & wir
            q.writel(control, 0)  # acknowledging USBNC cannot clear USBSTS
            assert q.levels.get(0, False)
            q.writel(0x02184144, 4)
            assert not q.levels.get(0, False)
            print('PASS normal USB IRQ remains independent from USBNC acknowledgement', flush=True)
        finally:
            for process, q, qmp, usb in reversed(resources):
                for connection in (usb, qmp, q):
                    if connection:
                        connection.close()
                process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=5)


if __name__ == '__main__':
    main()
