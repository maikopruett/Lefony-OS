#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted container entry point. Source is data, never a shell command/hook."""
import base64
import contextlib
import hashlib
import json
from pathlib import Path
import sys
import tempfile

SDK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SDK / 'tools'))
from cli import package
from lfapp import unpack
from runner import exercise
from source import MAX_SOURCE, extract


def validate(data, qemu, firmware):
    with tempfile.TemporaryDirectory(prefix='lf-validation-', dir='/tmp') as folder:
        project = Path(folder) / 'project'
        source = extract(data, project)
        first = package(project).read_bytes()
        second = package(project).read_bytes()
        if first != second:
            raise ValueError('Reproducible build check failed')
        metadata, _ = unpack(first)
        if metadata != source['manifest']:
            raise ValueError('Manifest changed during build')
        packed = project / 'build/validated.lfapp'
        packed.write_bytes(first)
        events = [(0,0,0), (1,5,0), (1,16,0), (1,6,0), (2,16,0),
                  (3,20 | (150<<16),256), (3,20 | (150<<16),258),
                  (3,0,3), (4,0,0)]
        report = exercise(packed, qemu, firmware, events=events)
        if report['result'] != 1 or len(report['callbacks']) != len(events):
            raise ValueError('Emulator callback check failed: '+json.dumps(report['callbacks']))
        return {'source_hash': hashlib.sha256(data).hexdigest(), 'passed': True,
                'package': base64.b64encode(first).decode(),
                'report': json.dumps({'abi': metadata['abi'], 'target': 'prime_g2_vm', 'physical_install': False,
                  'reproducible': True, 'package_validated': True, 'compiler': '16.2.0',
                  'firmware_sha256': hashlib.sha256(firmware.read_bytes()).hexdigest(),
                  'package_sha256': hashlib.sha256(first).hexdigest(), 'callbacks': report['callbacks'],
                  'os_responsive': report['os_responsive']}, separators=(',',':'))}


def main():
    data = sys.stdin.buffer.read(MAX_SOURCE+1)
    # Build diagnostics go to stderr; stdout carries exactly one bounded result.
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = validate(data, Path('/opt/runtime/qemu-system-arm'), Path('/opt/runtime/firmware.elf'))
    except Exception as error:
        result = {'source_hash': hashlib.sha256(data).hexdigest(), 'passed': False,
                  'report': str(error)[:8000]}
    print(json.dumps(result, separators=(',',':')))


if __name__ == '__main__':
    main()
