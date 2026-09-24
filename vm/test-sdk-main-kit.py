#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify a relocated SDK kit with its pinned sysroot and ordinary C preview."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-main/kit')
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--measure-resources',action='store_true')
    args=parser.parse_args();output=args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'sdk-with-newlib.tar.gz'
    command = [sys.executable, str(ROOT / 'scripts/package_native_sdk.py'),
        '--newlib', str(ROOT / 'build/sdk-newlib')]
    subprocess.run([*command, '--output', str(archive)], check=True, timeout=60)
    environment = {k:v for k,v in os.environ.items() if k != 'LEFONY_SDK_NEWLIB'}
    with tempfile.TemporaryDirectory(prefix='lefony-main-kit-') as temp:
        root = Path(temp)
        repeat = root / 'repeat.tar.gz'
        subprocess.run([*command, '--output', str(repeat)], check=True, timeout=60)
        assert digest(archive) == digest(repeat), 'kit archive is not reproducible'
        with tarfile.open(archive) as bundle:
            for item in bundle.getmembers():
                assert item.isfile() and item.size <= 16*1024*1024
                assert item.name.startswith('lefony-native-sdk/') and '..' not in Path(item.name).parts
                path = root / item.name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(bundle.extractfile(item).read())
                path.chmod(item.mode)
        kit = root / 'lefony-native-sdk'
        checksums = {}
        for line in (kit / 'SHA256SUMS').read_text().splitlines():
            sha, name = line.split('  ', 1)
            assert digest(kit / name) == sha, name
            checksums[name] = sha
        assert set(checksums) == {p.relative_to(kit).as_posix() for p in kit.rglob('*')
                                  if p.is_file() and p.name != 'SHA256SUMS'}
        assert 'sdk/runtime/newlib/COPYING.NEWLIB' in checksums
        assert 'sdk/runtime/newlib/newlib-4.6.0.20260123.tar.gz' in checksums
        cli = [sys.executable, str(kit / 'sdk/tools/cli.py')]
        project = root / 'External C é'
        subprocess.run([*cli, 'new', str(project), '--template', 'c-main'], check=True, env=environment)
        assert not (project / 'sdk.lock.json').exists(), 'scaffolding should not require the sysroot'
        subprocess.run(['cmake','-S',str(project),'-B',str(project / 'build/cmake'),
            '-DLEFONY_SDK_ROOT=' + str(kit / 'sdk'), '-DCMAKE_BUILD_TYPE=Debug'],check=True,env=environment)
        subprocess.run(['cmake','--build',str(project / 'build/cmake')],check=True,env=environment,timeout=120)
        build = json.loads((project / 'build/build.json').read_text())
        assert build['profile'] == 'debug' and build['runtime']['name'] == 'foreground-newlib-1'
        assert any(str(kit / 'sdk/runtime/newlib') in argument for argument in build['link'])
        commands = [*cli, 'test', '--qemu', str(ROOT / 'build/qemu-prime-g2/qemu-system-arm'),
            '--firmware', str(args.firmware.resolve())]
        subprocess.run(commands,cwd=project,check=True,env=environment,timeout=120)
        preview = json.loads((project / 'build/run.json').read_text())
        assert preview['status'] == 'passed' and preview['persistence'] == 'disposable-installed-preview'
        profiled=None
        if args.measure_resources:
            assert 'sdk/tools/resource_profile.py' in checksums
            subprocess.run([*commands,'--suite','startup','--measure-resources'],
                           cwd=project,check=True,env=environment,timeout=120)
            profiled=json.loads((project/'build/run.json').read_text())
            measured=profiled['resources']
            assert profiled['result']==1 and measured['loads']==measured['finished_loads']==1
            assert measured['samples']>0 and measured['stack_observed_bytes']>0
            assert measured['heap_reserved_peak_bytes']==8380416 and measured['stack_peak_bytes'] is None
        subprocess.run([*commands,'--workspace','saved'],cwd=project,check=True,env=environment,timeout=120)
        first = (project / 'build/tests/saved-visits/saved.ppm').read_bytes()
        subprocess.run([*commands,'--workspace','saved'],cwd=project,check=True,env=environment,timeout=120)
        cold = json.loads((project / 'build/run.json').read_text())
        assert cold['status'] == 'passed' and cold['persistence'] == 'installed-workspace'
        assert first != (project / 'build/tests/saved-visits/saved.ppm').read_bytes(), 'cold visit count did not advance'
        subprocess.run([*cli,'source','--format','2'],cwd=project,check=True,env=environment,timeout=30)
        port = root / 'Minigzip external é'
        subprocess.run([sys.executable, str(kit / 'scripts/prepare_sdk_minigzip.py'),
            '--project', str(port), '--archive', str(ROOT / 'build/sdk-1.0-upstream/zlib-1.3.2.tar.gz'),
            '--offline', '--', 'input.dat'], check=True, env=environment, timeout=30)
        subprocess.run([*cli, '--project', str(port), 'package'], check=True, env=environment, timeout=120)
        subprocess.run([*cli, '--project', str(port), 'source', '--format', '2'], check=True, env=environment, timeout=30)
        minigzip = json.loads((port / 'build/build.json').read_text())
        assert minigzip['runtime']['name'] == 'foreground-newlib-1'
        assert any(str(kit / 'sdk/runtime/newlib') in arg for arg in minigzip['link'])
        input_project=root/'Input stream C é'
        subprocess.run([*cli,'new',str(input_project),'--template','c-main'],check=True,env=environment)
        metadata=json.loads((input_project/'app.json').read_text())
        metadata.update(minimum_api=4,required_capabilities=48)
        (input_project/'app.json').write_text(json.dumps(metadata))
        (input_project/'src/main.c').write_text('''#include <lefony/input_stream.h>
int main(void) {
  LefonyInputStream input;
  return lefony_read_input_stream(&input)!=0 || input.flags!=LEFONY_INPUT_FOCUS_RESET ||
    input.count || input.held[0] || input.held[1] || input.contactCount;
}
''')
        for old in (input_project/'tests').glob('*.json'):old.unlink()
        (input_project/'tests/input.json').write_text(json.dumps({'schema':1,'name':'input-stream',
            'steps':[{'program_exit':0},{'relaunch':True},{'program_exit':0}]}))
        subprocess.run(commands,cwd=input_project,check=True,env=environment,timeout=120)
        input_stream=json.loads((input_project/'build/run.json').read_text())
        assert input_stream['status']=='passed'
        report = {'schema':1,'status':'passed','physical':'not_tested','host':sys.platform,
            'archive_sha256':digest(archive),'files':len(checksums),'runtime':build['runtime'],
            'preview':preview,'profiled':profiled,'cold':cold,'input_stream':input_stream,'source_sha256':digest(project / 'build/app.lfsrc'),
            'minigzip': {'image_sha256': minigzip['image_sha256'],
                         'source_sha256': digest(port / 'build/app.lfsrc')}}
        (output / 'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: deterministic kit, bundled runtime, external CMake, cold saved visits and existing minigzip recipe',flush=True)


if __name__ == '__main__': main()
