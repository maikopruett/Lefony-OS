#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Profile a populated, signed Notebook ARM preview without changing its behavior."""
import argparse
import cProfile
import functools
from pathlib import Path
import pstats
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sdk', type=Path, default=ROOT / 'sdk')
    parser.add_argument('--qemu', type=Path, default=ROOT / 'build/qemu-prime-g2/qemu-system-arm')
    args = parser.parse_args()
    sdk = args.sdk.resolve()
    sys.path.insert(0, str(sdk / 'tools'))
    import archive_device
    import device
    import emulator_usb
    import preview
    from build import digest, identity, write_json
    out = args.output.resolve()
    out.mkdir(parents=True)  # Keep earlier measurements intact.
    project = out / 'External Notebook é'
    shutil.copytree(sdk / 'examples/notebook', project,
                    ignore=shutil.ignore_patterns('build', '.lefony', 'sdk.lock.json'))
    fixtures = out / 'fixtures'
    (fixtures / 'nested/empty').mkdir(parents=True)
    (fixtures / 'notebook.txt').write_bytes(b'LFNOTE1\n' + b''.join(f'{i}+100\n'.encode() for i in range(12)))
    (fixtures / 'nested/data.bin').write_bytes(bytes(range(256)) * 513)
    write_json(project / 'tests/scroll.json', {'schema': 1, 'name': 'scroll', 'steps': [
        {'wait_ms': 1000}, {'touch': [[1, 80, 75]]}, {'touch': [[1, 80, 58]]}, {'touch': []}]})
    metrics = {}
    phases = []
    originals = []

    def instrument(owner, name, *, phase=False, group=None):
        original = getattr(owner, name)
        originals.append((owner, name, original))
        label = owner.__module__ + '.' + owner.__name__ + '.' + name
        @functools.wraps(original)
        def wrapped(*a, **kw):
            if phase: phases.append(label)
            key = (phases[-1] if phases else 'other') + '/' + label
            if group: key += '/' + group(a, kw)
            started = time.monotonic()
            try:
                return original(*a, **kw)
            finally:
                elapsed = time.monotonic() - started
                entry = metrics.setdefault(key, {'calls': 0, 'seconds': 0, 'maximum_seconds': 0})
                entry['calls'] += 1
                entry['seconds'] += elapsed
                entry['maximum_seconds'] = max(entry['maximum_seconds'], elapsed)
                if phase:
                    phases.pop()
                    print(label, round(elapsed, 3), 'seconds', flush=True)
        setattr(owner, name, wrapped)

    for owner, names in ((device.Client, ('install',)), (archive_device.Client, ('restore', 'export')),
                         (emulator_usb.PrimeUSBHost, ('connect_and_enumerate',))):
        for name in names: instrument(owner, name, phase=True)
    instrument(archive_device.Client, '_wait')
    instrument(emulator_usb.PrimeUSBHost, 'command', group=lambda a, kw: a[1].split()[0])
    report = {'schema': 1, 'status': 'running', 'sdk_sha256': identity(sdk),
              'firmware_sha256': digest(args.firmware), 'qemu_sha256': digest(args.qemu),
              'physical': 'not_tested', 'attachment_bytes': 131328, 'test_sha256': digest(Path(__file__))}
    write_json(out / 'report.json', report)
    profile = cProfile.Profile()
    profile.enable()
    try:
        result = preview.once(project, args.qemu.resolve(), args.firmware.resolve(),
                              scenario=Path('tests/scroll.json'), fixture_dir=fixtures)
        assert result['status'] == 'ready', result.get('error')
        assert next(n for n in result['layout']['nodes'] if n['id'] == 100)['bounds'] == (12, 43, 296, 36)
        assert report['sdk_sha256'] == identity(sdk), 'SDK changed during measurement'
        report.update(status='passed', preview=result)
    except BaseException as exc:
        report.update(status='failed', error=str(exc))
        raise
    finally:
        profile.disable()
        for owner, name, original in reversed(originals): setattr(owner, name, original)
        profile.dump_stats(str(out / 'profile.bin'))
        with (out / 'profile.txt').open('w') as stream:
            pstats.Stats(profile, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(60)
        report['metrics'] = metrics
        write_json(out / 'report.json', report)
    print('PASS:', result['timings'], flush=True)


if __name__ == '__main__':
    main()
