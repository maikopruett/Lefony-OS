#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read the Phase 6 identity over modeled EP0 from an actual ARM build.

Direct boot has no authenticated boot-manager handoff, so a dual build must
report recovery-required. This is a VM transport check, not physical proof.
"""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prime_dual_installer import inspect_native
from prime_usb_host import PrimeUSBHost, USBError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path, required=True)
    parser.add_argument('--dual', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='lfinfo-', dir='/tmp') as temporary:
        directory = Path(temporary)
        env = os.environ | {'NATIVE_ELF': str(args.elf.resolve()), 'NATIVE_VM_BUILD_DIR': temporary,
                            'NATIVE_VM_SOCKET_DIR': temporary, 'NATIVE_STORAGE_MODE': 'ephemeral'}
        with (directory / 'runner.log').open('w') as log:
            process = subprocess.Popen([str(ROOT / 'vm/run-native-vm.sh'), '--headless', '--direct'],
                env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 60
            uart = directory / 'uart.log'
            while time.monotonic() < deadline:
                if uart.exists() and 'entering calculator runtime' in uart.read_text(errors='replace'): break
                if process.poll() is not None: raise AssertionError((directory / 'runner.log').read_text())
                time.sleep(0.1)
            else: raise AssertionError('VM did not enter runtime')
            with PrimeUSBHost(directory / 'usb-host.sock') as host:
                host.connect_and_enumerate()
                class Device:
                    def read(self, request, *, value=0, length):
                        return host.control_in(0xc0, request, value, length=length)
                found = inspect_native(Device())
                assert found['state'] == ('recovery-required' if args.dual else 'lefony-legacy'), found
                assert found['legacy_writes_allowed'] is not args.dual
                try: host.control_in(0xc0, 0x4e, 5, length=64)
                except USBError: pass
                else: raise AssertionError('unknown layout query did not stall')
                # A stalled malformed request must not prevent a fresh query.
                assert inspect_native(Device()) == found
                print('PASS modeled ARM EP0 layout identity, malformed request and recovery:', found)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)


if __name__ == '__main__': main()
