# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / 'sdk'
sys.path.insert(0, str(SDK / 'tools'))
from build import build, contract, identity
from replay import validate, KEYS
from workspace import manage, opened, restore


def test_contract_matches_package_linker_and_normal_keymap():
    import lfapp
    limits = contract(SDK)['limits']
    assert (limits['code_start'], limits['data_start'], limits['data_end']) == (lfapp.CODE, lfapp.DATA, lfapp.DATA_END)
    linker = (SDK / 'cmake/app.ld').read_text()
    assert f"0x{limits['data_end']:08x}" in linker
    source = (ROOT / 'ports/lefony-prime-g2/ion/src/prime_g2/keymap.inc').read_text()
    keys = {name: [int(row), int(col)] for name, row, col in re.findall(
        r'PRIME_G2_KEY\((\w+),\s*\d+,\s*\w+,\s*(\d+),\s*(\d+)\)', source) if row != '255'}
    assert KEYS == keys


@pytest.mark.parametrize('step', [
    {'wait_ms': 60001}, {'wait_ms': True}, {'program_exit': True}, {'program_exit': 2147483648},
    {'touch': [[0, 320, 0]]}, {'touch': [[0, 1, 1], [0, 2, 2]]},
    {'key': 'invented'}, {'capture': '../secret'}, {'same': ['missing', 'missing']},
    {'keys':['left','left']}, {'keys':['invented']}, {'keys':'left'}, {'keys':[None]},
    {'run': 'arbitrary hook'}, {'pixel': []}, {'relaunch': False}, {'key': 'ok', 'wait_ms': 1},
])
def test_replay_rejects_unsupported_or_unbounded_actions(step):
    with pytest.raises(ValueError):
        validate({'schema': 1, 'name': 'sample', 'steps': [step]})


def test_replay_budget_and_checked_examples():
    with pytest.raises(ValueError, match='180 seconds'):
        validate({'schema': 1, 'name': 'sample', 'steps': [{'wait_ms': 5000}] * 37})
    for path in (SDK / 'examples').glob('*/tests/*.json'):
        validate(json.loads(path.read_text()))


def test_workspace_roundtrip_exclusive_and_bad_archive_preserves_prior_data(tmp_path):
    with opened(tmp_path, 'main') as (path, _):
        original = (path / 'nand.overlay').read_bytes()
        with pytest.raises(ValueError, match='locked'):
            with opened(tmp_path, 'main'):
                pass
    archive = tmp_path / 'workspace.zip'
    manage(tmp_path, 'export', 'main', archive)
    restore(tmp_path, 'restored', archive)
    with opened(tmp_path, 'restored') as (path, _):
        assert (path / 'nand.overlay').read_bytes() == original
    with pytest.raises(ValueError, match='existing data was preserved'):
        restore(tmp_path, 'restored', archive)
    bad = tmp_path / 'bad.zip'
    with zipfile.ZipFile(bad, 'w') as out:
        out.writestr('../nand.overlay', 'escape')
    with pytest.raises(ValueError):
        restore(tmp_path, 'bad', bad)
    assert not (tmp_path / '.lefony/workspaces/bad').exists()
    assert manage(tmp_path, 'info', 'main')['kind'] == 'synthetic-prime-g2'


def test_workspace_symlink_rejected(tmp_path):
    (tmp_path / '.lefony').symlink_to(tmp_path)
    with pytest.raises(ValueError, match='symlink'):
        manage(tmp_path, 'info', 'sample')


def test_app_side_runtime_and_numeric_contracts_under_sanitizers(tmp_path):
    compiler = shutil.which('clang++') or shutil.which('g++')
    if not compiler:
        pytest.skip('C++ host compiler unavailable')
    source = tmp_path / 'runtime.cpp'
    source.write_text('''
#include <lefony/runtime.h>
#include <lefony/numeric.h>
#include <cassert>
#include <limits>
int main() {
  Lefony::Arena<64> arena;
  assert(arena.allocate(1,1));
  void *aligned=arena.allocate(16,16);
  assert(aligned && reinterpret_cast<uintptr_t>(aligned)%16==0);
  assert(arena.used()==32 && arena.peak()==32);
  assert(!arena.allocate(SIZE_MAX));assert(!arena.allocate(0));assert(!arena.allocate(2,3));
  assert(arena.used()==32 && arena.failures()==3);
  assert(arena.allocate(32));assert(!arena.allocate(1));
  arena.reset();assert(arena.used()==0 && arena.peak()==64);
  Lefony::Vector<int,2> values;
  assert(values.push(7));assert(values.push(8));assert(!values.push(9));assert(!values.at(2));
  assert(*values.at(0)==7);assert(values.pop());values.clear();assert(!values.pop());
  Lefony::Task task{0,9,false};task.step(3,[](unsigned){return true;});assert(task.completed==3);
  task.cancel();task.step(100,[](unsigned){return true;});assert(task.completed==3);
  assert(Lefony::elapsed(3,UINT32_MAX-2)==6);
  using namespace Lefony::Numeric;
  Statistics stats;double value=123;
  assert(stats.mean(value)==Status::Empty && value==123);
  for(double x:{2.,4.,4.,4.,5.,5.,7.,9.}) assert(stats.add(x)==Status::Ok);
  assert(stats.mean(value)==Status::Ok && abs(value-5)<1e-12);
  assert(stats.variance(value,false)==Status::Ok && abs(value-4)<1e-12);
  assert(stats.add(std::numeric_limits<double>::infinity())==Status::Invalid && stats.count()==8);
  auto never=[](){return false;};
  Root root=bisect([](double x){return x*x-2;},0,2,1e-10,100,never);
  assert(root.status==Status::Ok && abs(root.value-1.4142135623730951)<1e-9);
  assert(bisect([](double x){return x*x+1;},-1,1,1e-8,10,never).status==Status::Domain);
  assert(bisect([](double x){return x<0?-1.:1.;},-1,1,1e-8,50,never).status==Status::Limit);
  assert(bisect([](double x){return x;},-1,1,1e-8,10,[](){return true;}).status==Status::Cancelled);
  assert(bisect([](double x){return x;},-1,1,1e-8,257,never).status==Status::Invalid);
}
'''.replace('#include <limits>', '#include <limits>\n#include <initializer_list>'))
    executable = tmp_path / 'runtime'
    subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-I', str(SDK / 'include'), str(source), '-o', str(executable)], check=True, timeout=30)
    subprocess.run([str(executable)], check=True, timeout=10)


def pinned_compiler():
    compiler = shutil.which('arm-none-eabi-g++')
    if not compiler or subprocess.check_output([compiler, '-dumpfullversion'], text=True).strip() != '16.2.0':
        pytest.skip('SDK integration requires pinned GCC 16.2.0')


def test_incremental_build_debug_symbols_relocation_lock_and_ctor_rejection(tmp_path):
    pinned_compiler()
    project = tmp_path / 'App with spaces é'
    shutil.copytree(SDK / 'templates/basic', project)
    build(project, SDK)
    original = (project / 'build/app.elf').read_bytes()
    build(project, SDK)
    report = json.loads((project / 'build/build.json').read_text())
    assert report['compiled'] == []
    assert report['resources']['code_bytes'] > 0 and report['resources']['stack_reserved_bytes'] == 65536
    assert (project / 'build/app.map').is_file()
    commands = json.loads((project / 'compile_commands.json').read_text())
    assert '-g3' in commands[0]['arguments']
    relocated = tmp_path / 'Relocated'
    shutil.copytree(project, relocated, ignore=shutil.ignore_patterns('build'))
    build(relocated, SDK)
    assert (relocated / 'build/app.elf').read_bytes() == original
    with (project / 'src/main.cpp').open('a') as out:
        out.write('\n// Incremental source change\n')
    build(project, SDK)
    assert json.loads((project / 'build/build.json').read_text())['compiled'] == ['src/main.cpp']
    lock = json.loads((project / 'sdk.lock.json').read_text());lock['abi'] = 99
    (project / 'sdk.lock.json').write_text(json.dumps(lock))
    with pytest.raises(ValueError, match='sdk.lock'):
        build(project, SDK)
    (project / 'sdk.lock.json').unlink()
    with (project / 'src/main.cpp').open('a') as out:
        out.write('\nstruct Constructor { Constructor(){ Lefony::fill({0,0,1,1,0}); } }; Constructor global;\n')
    with pytest.raises(subprocess.CalledProcessError):
        build(project, SDK)
    assert not (project / 'build/build.json').exists()


def test_doctor_never_guesses_device_support():
    process = subprocess.run([sys.executable, str(SDK / 'tools/cli.py'), 'doctor'], capture_output=True, text=True, timeout=15)
    result = json.loads(process.stdout)
    assert result['physical_install']['device'] == 'not_checked'
    assert result['physical_install']['sdk_supported'] is True
    assert result['publication'] == 'developer-local'


def test_emulator_fixture_never_becomes_a_physical_app_trust_root(tmp_path):
    from signing import sign
    from lfapp import pack
    from test_native_app_package import image, META
    port = ROOT / 'ports/lefony-prime-g2/ion/src/prime_g2'
    for name in ('native_app_signature.h', 'native_app_digest.h', 'app_trust_roots.h'):
        shutil.copyfile(port / name, tmp_path / name)
    public = ROOT / 'tests/fixtures/prime_g2_emulator_update_public.pem'
    private = ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem'
    subprocess.run([sys.executable, str(ROOT / 'scripts/configure_native_app_keys.py'),
                    '--emulator-fixture', str(public), str(tmp_path / 'app_emulator_trust_root.h')], check=True)
    (tmp_path / 'verify.cpp').write_text('''#include "native_app_signature.h"
#include <stdio.h>
uint8_t data[32768];
int main(){size_t n=fread(data,1,sizeof(data),stdin),length=0;const uint8_t *payload=nullptr;
return PrimeG2::NativeAppSignature::unwrap(data,n,&payload,&length)?0:1;}
''')
    package = sign(pack({**META, 'abi': 1}, image()), private)
    for emulator in (0, 1):
        output = tmp_path / f'verify-{emulator}'
        subprocess.run(['c++', '-std=c++17', '-O2', f'-DPRIME_G2_EMULATOR={emulator}',
                        str(tmp_path / 'verify.cpp'), '-o', str(output)], check=True, timeout=30)
        assert subprocess.run([output], input=package, timeout=10).returncode == (0 if emulator else 1)


@pytest.mark.parametrize('command', ['new','build','package','run','test','source','inspect','debug','symbolize','workspace','lock'])
def test_documented_commands_have_help(command):
    result = subprocess.run([sys.executable, str(SDK/'tools/cli.py'), command, '--help'],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and 'usage:' in result.stdout
