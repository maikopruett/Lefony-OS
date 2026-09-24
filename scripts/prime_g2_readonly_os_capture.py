#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture and independently reread the installed Lefony OS capsule over USB.

Only the existing OS-slot page-read requests and updater status are permitted.
This is a corrected-data capsule capture, not a raw NAND/OOB or user-data backup.
Failed attempts retain a .partial directory and report, without publishing the
requested output directory. Only active slot A is accessible through this API.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import time

import prime_g2_usb_diag as usb

FIRST_PAGE = 2048
END_PAGE = 6144
PAGE_BYTES = 2048


class ReadOnlyTransport:
    def __init__(self, device):
        self.device = device
        self.page_triggers = 0

    def read(self, request, value=0, index=0, length=64):
        valid = ((request == 0x48 and value == index == 0 and length == 64)
                 or (request == 0x51 and value == index == 0 and length == 24)
                 or (request == 0x52 and index == 0 and length == 512
                     and value in (0, 512, 1024, 1536)))
        if not valid:
            raise ValueError('Request is outside the read-only capsule protocol')
        return self.device.read(request, value=value, index=index, length=length)

    def write(self, request, data=b'', value=0, index=0):
        page = value | (index << 16)
        if (request != 0x51 or data or not 0 <= value <= 0xffff
                or index != 0 or not FIRST_PAGE <= page < END_PAGE):
            raise ValueError('Only an OS-slot NAND read trigger is permitted')
        self.page_triggers += 1
        self.device.write(request, data, value=value, index=index)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def capture(device, output, *, timeout=600, clock=time.monotonic,
            progress=lambda phase, done, total: None):
    if not 1 <= timeout <= 3600:
        raise ValueError('Use a capture timeout from 1 to 3600 seconds')
    destination = Path(output).resolve()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Use a new OS capture output directory')
    output = destination.with_name(destination.name + '.partial')
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    transport = ReadOnlyTransport(device)
    started = clock()
    report = {'schema': 1, 'status': 'running', 'passes': [],
              'scope': 'BCH-corrected installed OS capsule only; excludes OOB and app/user data',
              'nand_writes': False, 'reboots': False}

    def save():
        report['page_read_triggers'] = transport.page_triggers
        report['seconds'] = round(clock() - started, 6)
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def read_page(page):
        if clock() - started >= timeout:
            raise TimeoutError('Read-only OS capture exceeded its total deadline')
        data, state = usb.read_nand_page(transport, page)
        if state['marker'] != 0xff:
            raise usb.USBError('OS capture encountered a bad-block marker; use the recovery backup path')
        return data, state

    save()
    try:
        before = usb.update_status(transport)
        report['update_before'] = before
        if before['state'] != 'idle' or before['error'] or before['pending_slot'] is not None:
            raise usb.USBError('OS capture requires an idle updater without a pending boot')
        if before['active_slot'] != 0:
            raise usb.USBError('This read-only interface covers slot A; use recovery backup for active slot B')
        header, _ = read_page(FIRST_PAGE)
        magic, start, size = struct.unpack_from('<3I', header, 0x24)
        if (magic != 0x016f2818 or start != 0 or size <= 4096 or size % 4
                or size > (END_PAGE - FIRST_PAGE) * PAGE_BYTES):
            raise usb.USBError('Installed OS capsule header is outside the supported slot bounds')
        report['capsule_bytes'] = size
        count = (size + PAGE_BYTES - 1) // PAGE_BYTES
        for phase in (1, 2):
            if usb.update_status(transport) != before:
                raise usb.USBError('Updater state changed during OS capture')
            path = output / f'pass-{phase}.partial'
            item = {'pass': phase, 'file': path.name, 'pages': [], 'bytes': 0}
            report['passes'].append(item)
            with path.open('xb') as stream:
                path.chmod(0o600)
                for offset in range(count):
                    data, state = read_page(FIRST_PAGE + offset)
                    if offset == 0 and data != header:
                        raise usb.USBError('Installed OS header changed during capture')
                    part = data[:min(PAGE_BYTES, size - item['bytes'])]
                    stream.write(part)
                    item['bytes'] += len(part)
                    item['pages'].append({'page': state['page'], 'corrected_bits': state['corrected']})
                    progress(phase, item['bytes'], size)
                    if offset % 64 == 0:
                        save()
                stream.flush()
                os.fsync(stream.fileno())
            item['sha256'] = digest(path)
            if usb.update_status(transport) != before:
                raise usb.USBError('Updater state changed during OS capture')
            save()
        first, second = report['passes']
        if first['sha256'] != second['sha256']:
            raise usb.USBError('Independent OS capsule reads differ; retain both partial captures')
        for item, name in zip(report['passes'], ('os.zImage', 'verification.zImage')):
            (output / item['file']).rename(output / name)
            item['file'] = name
        report.update(status='passed',sha256=first['sha256'], independent_reads_identical=True,
                      update_after=before)
        save()
        if destination.exists() or destination.is_symlink():
            raise ValueError('OS capture output appeared during the reads')
        output.rename(destination)
        return report
    except BaseException as error:
        report.update(status='failed', error=str(error) or type(error).__name__)
        if output.exists():
            save()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=600)
    args = parser.parse_args()
    previous = [None]
    def progress(phase, done, total):
        step = (phase, done * 10 // total)
        if step != previous[0]:
            print(f'Pass {phase}: {done}/{total} bytes', flush=True)
            previous[0] = step
    with usb.LibUSB() as device:
        result = capture(device, args.output, timeout=args.timeout, progress=progress)
    print(json.dumps({'status':result['status'], 'bytes':result['capsule_bytes'],
                      'sha256':result['sha256'], 'seconds':result['seconds']}))
