#!/usr/bin/env python3
"""Capture cold-boot MMIO coverage; coverage is not physical parity."""
import argparse
from collections import Counter
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import time

EVENT = re.compile(r"memory_region_ops_(read|write).*?cpu (-?\d+).*?addr (0x[\da-f]+).*?size (\d+) name '([^']+)'")


def summarize(lines):
    regions, diagnostics, accesses = {}, Counter(), Counter()
    for line in lines:
        match = EVENT.search(line)
        if match:
            operation, cpu, address, size, name = match.groups()
            item = regions.setdefault(name, {'read': 0, 'write': 0, 'cpu_indices': set(), 'addresses': set()})
            item[operation] += 1
            item['cpu_indices'].add(int(cpu))
            item['addresses'].add(int(address, 16))
            accesses[(name, address, operation, int(cpu))] += 1
        elif line.strip():
            diagnostics[line.strip()] += 1
    return {
        'regions': {name: {**item, 'cpu_indices': sorted(item['cpu_indices']),
                          'addresses': [hex(v) for v in sorted(item['addresses'])]}
                    for name, item in sorted(regions.items())},
        'non_mmio_log_lines': dict(diagnostics.most_common()),
        'top_accesses': [{'region': key[0], 'address': key[1], 'operation': key[2],
                          'cpu_index': key[3], 'count': count}
                         for key, count in accesses.most_common(40)],
        'warning': 'Addresses are QEMU memory_region_to_absolute_addr results, not region offsets. Counts include host accesses (CPU -1); '
                   'a registered region may only shadow registers. Neither counts nor a boot marker prove parity.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='new directory; existing paths are rejected')
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--include-reads', action='store_true', help='also trace polling reads; may hit the size limit before boot')
    parser.add_argument('--summarize-log', type=Path, help='analyze a saved trace without running QEMU')
    args = parser.parse_args()
    if not 0 < args.timeout <= 60:
        parser.error('timeout must be in (0, 60] seconds')
    if args.summarize_log:
        with args.summarize_log.open(errors='replace') as source:
            report = summarize(source)
        report.update({'source_log': str(args.summarize_log.resolve()),
                       'full_hardware_parity': False, 'runtime_marker_reached': None})
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(args.output / 'report.json')
        return
    physical = importlib.import_module('test-prime-g2-physical-rom-boot')
    boot = physical.boot
    boot.NAND = physical.PHYSICAL
    for path in (boot.QEMU, boot.NAND):
        if not path.is_file():
            parser.error(f'missing input: {path}')
    args.output.mkdir(parents=True, exist_ok=False)
    overlay = physical.overlay(args.output / 'nand.overlay', {})
    log = args.output / 'mmio.log'
    command = boot.command(overlay) + ['-global', 'prime-g2-gpmi-bch.physical-pages=on',
        '-trace', 'enable=memory_region_ops_' + ('*' if args.include_reads else 'write'),
        '-d', 'unimp,guest_errors', '-D', str(log)]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, reached = bytearray(), False
    selected = selectors.DefaultSelector()
    selected.register(process.stdout, selectors.EVENT_READ)
    selected.register(process.stderr, selectors.EVENT_READ)
    deadline = time.monotonic() + args.timeout
    try:
        while time.monotonic() < deadline and process.poll() is None:
            for key, _ in selected.select(.1):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if chunk:
                    output.extend(chunk)
                else:
                    selected.unregister(key.fileobj)
            if physical.MARKER in output:
                reached = True
                break
            if log.exists() and log.stat().st_size > 128 * 1024 * 1024:
                break  # bound polling-loop traces; preserve incomplete evidence
    finally:
        selected.close()
        output.extend(boot.stop(process))
    (args.output / 'console.log').write_bytes(output)
    with log.open(errors='replace') as source:
        report = summarize(source)
    report.update({'runtime_marker_reached': reached, 'command': command,
        'qemu_sha256': hashlib.sha256(boot.QEMU.read_bytes()).hexdigest(),
        'nand_fixture': str(boot.NAND), 'nand_fixture_kind': 'regenerated physical codewords, not acquired parity',
        'physical_device_accessed': False, 'full_hardware_parity': False,
        'rom_execution': 'functional C substitute; no physical mask-ROM instructions executed',
        'reads_traced': args.include_reads,
        'trace_bytes': log.stat().st_size})
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'report': str(args.output / 'report.json'), 'runtime_marker_reached': reached,
                      'regions': len(report['regions']), 'trace_bytes': report['trace_bytes']}))
    if not reached or not report['regions']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
