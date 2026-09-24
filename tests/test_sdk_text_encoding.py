# SPDX-License-Identifier: GPL-3.0-or-later
"""SDK workflows with UTF-8 mode disabled and a non-UTF-8 default locale."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'sdk/tools'


def environment():
    return {**os.environ, 'LC_ALL': 'C', 'LANG': 'C', 'PYTHONUTF8': '0',
            'PYTHONCOERCECLOCALE': '0', 'PYTHONIOENCODING': 'ascii:strict',
            'PYTHONWARNDEFAULTENCODING': '1'}


def run_script(text, *arguments):
    prelude = """
import io,json,locale,sys,warnings
from pathlib import Path
sys.path.insert(0,sys.argv[1])
assert sys.flags.utf8_mode==0
assert locale.getencoding().lower().replace('-','') not in ('utf8','utf_8')
warnings.filterwarnings('error',category=EncodingWarning,module=r'(workspace|preview|build|diagnostics|assets|replay|store_projects|signing|sdk_environment)$')
root=Path(sys.argv[2])
"""
    result = subprocess.run([sys.executable, '-c', prelude + text, str(TOOLS), *map(str, arguments)],
                            env=environment(), capture_output=True, timeout=120)
    assert result.returncode == 0, result.stdout.decode('utf-8', 'replace') + result.stderr.decode('utf-8', 'replace')
    return result


@pytest.fixture
def locale_root(tmp_path):
    probe = subprocess.run([sys.executable, '-c',
        'import json,locale,sys;print(json.dumps([locale.getencoding(),sys.getfilesystemencoding()]))'],
        env=environment(), capture_output=True, check=True, timeout=10)
    locale_encoding, filesystem_encoding = json.loads(probe.stdout)
    if locale_encoding.lower().replace('-', '') == 'utf8':
        pytest.skip('This host does not provide a non-UTF-8 locale with UTF-8 mode disabled')
    # macOS/Windows retain UTF-8 filesystem paths independently of text locale.
    # A POSIX host with an ASCII filesystem codec still tests UTF-8 file contents.
    name = 'SDK Café 数学' if filesystem_encoding.lower().replace('-', '') == 'utf8' else 'sdk-text'
    root = tmp_path/name; root.mkdir()
    return root


def test_workspace_unicode_metadata_survives_export_and_restore(locale_root):
    run_script(r'''
from build import write_json
from workspace import opened,manage,restore
value='Caf\u00e9 \u6570\u5b66 \u2192 \u03c0'
with opened(root,'original') as (directory,state):
    state['description']=value
    write_json(directory/'workspace.json',state)
raw=(directory/'workspace.json').read_bytes()
assert value.encode('utf-8') in raw and b'\r\n' not in raw
assert manage(root,'info','original')['description']==value
manage(root,'export','original',root/'workspace.zip')
restore(root,'restored',root/'workspace.zip')
assert manage(root,'info','restored')['description']==value
assert (root/'.lefony/workspaces/restored/workspace.json').read_bytes()==raw
bad=root/'.lefony/workspaces/restored/workspace.json'
bad.write_bytes(b'{"schema":1,"description":"\xff"}')
overlay=(bad.parent/'nand.overlay').read_bytes()
try:manage(root,'reset','restored')
except UnicodeDecodeError:pass
else:raise AssertionError('Invalid UTF-8 metadata was accepted')
assert (bad.parent/'nand.overlay').read_bytes()==overlay
assert not (bad.parent/'.lock').exists()
''', locale_root)


def test_preview_html_keeps_unicode_labels_and_errors(locale_root):
    run_script(r'''
from preview import render
value='Caf\u00e9 \u6570\u5b66 \u2192 \u03c0'
node={'id':1,'kind':'label','name':value+' <script>', 'bounds':[0,0,20,20],
      'clip':[0,0,20,20],'state':0,'file':'src/main.cpp','line':4,'clipped':False}
render(root,{'status':'failed','error':value,'layout':{'nodes':[node]}})
raw=(root/'index.html').read_bytes()
assert value.encode('utf-8') in raw and b'\r\n' not in raw
assert b'&lt;script&gt;' in raw and b'<script>' not in raw
assert 'STALE \u2014 failed'.encode('utf-8') in raw
''', locale_root)


def test_project_index_reads_utf8_locations_without_rewriting_them(locale_root):
    metadata={'abi':1,'id':'unicode-test','name':'Unicode test','version':'1.0.0','license':'MIT'}
    (locale_root/'app.json').write_text(json.dumps(metadata), encoding='utf-8')
    run_script(r'''
from store_projects import bind_project,projects,registry_directory
origin='https://example.com';account='github:123'
bind_project(root,origin,account,'unicode-test',state_root=root/'state')
entry=next(registry_directory(root/'state',origin,account).glob('*.json'))
record=json.loads(entry.read_text(encoding='utf-8'))
entry.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8',newline='\n')
before=entry.read_bytes()
result=projects(origin,account,state_root=root/'state')
assert result[0]['path']==str(root.resolve()) and result[0]['linked']
assert entry.read_bytes()==before
''', locale_root)


@pytest.mark.parametrize('entry', ['cli.py', 'lefony-sdk', 'portable_entry.py'])
def test_all_cli_entry_points_write_redirected_utf8(locale_root, entry):
    target=locale_root/'project'
    result=subprocess.run([sys.executable,str(TOOLS/entry),'new',str(target)],
                          env=environment(),capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr.decode('utf-8','replace')
    assert str(target).encode('utf-8') in result.stdout
    assert b'\r\n' not in result.stdout
    assert (target/'app.json').is_file()


@pytest.fixture
def built_project(locale_root):
    if not all(shutil.which(name) for name in ('arm-none-eabi-g++','arm-none-eabi-objcopy','arm-none-eabi-nm','arm-none-eabi-addr2line')):
        pytest.skip('Requires the pinned ARM SDK toolchain')
    subprocess.run([sys.executable,str(TOOLS/'cli.py'),'new',str(locale_root/'app')],
                   env=environment(),check=True,capture_output=True,timeout=30)
    project=locale_root/'app'
    (project/'src/main.cpp').write_text('''#include <lefony/app.h>
extern "C" __attribute__((noinline)) unsigned café(unsigned n) { asm volatile("" : "+r"(n)); return n+1; }
extern "C" void lefony_event(Lefony::Event,uint32_t,uint32_t) {
  Lefony::fill({0,0,320,240,static_cast<uint16_t>(café(1))});
}
''',encoding='utf-8',newline='\n')
    result=subprocess.run([sys.executable,str(TOOLS/'cli.py'),'--project',str(project),'package','--profile','debug'],
                          env=environment(),capture_output=True,timeout=120)
    assert result.returncode==0,result.stdout.decode('utf-8','replace')+result.stderr.decode('utf-8','replace')
    return project


def test_real_arm_symbols_debug_script_and_source_roundtrip(built_project):
    run_script(r'''
import subprocess
from diagnostics import matching_symbols,symbolize,gdb_script
from source import collect,extract
from build import build
package=next((root/'build').glob('*.lfapp'))
debug=matching_symbols(root,package)
symbols=subprocess.check_output(['arm-none-eabi-nm',str(debug)],encoding='utf-8',timeout=10)
entry=next(line for line in symbols.splitlines() if line.endswith(' caf\u00e9'))
address=int(entry.split()[0],16)
assert 'caf\u00e9' in symbolize(root,package,address)['symbol'][0]
script=gdb_script(root,package,root/'gdb-endpoint')
raw=script.read_bytes()
assert str(root).encode('utf-8') in raw and b'\r\n' not in raw
source=collect(root,2)
restored=root.parent/'restored'
extract(source,restored)
assert (restored/'src/main.cpp').read_bytes()==(root/'src/main.cpp').read_bytes()
assert collect(restored,2)==source
assert build(restored,Path(sys.argv[1]).parent,'debug')[1].read_bytes()==(root/'build/app.elf').read_bytes()
''', built_project)


def test_failed_preview_preserves_frame_and_unicode_diagnostic(built_project):
    source=built_project/'src/main.cpp'
    with source.open('a',encoding='utf-8',newline='\n') as stream:
        stream.write('\n#error Café 数学\n')
    run_script(r'''
from preview import once
from build import write_json
output=root/'build/preview';output.mkdir(parents=True)
frame=b'retained-frame-bytes';(output/'frame.png').write_bytes(frame)
write_json(output/'status.json',{'status':'ready','label':'Caf\u00e9'})
state=once(root,root/'unused-qemu',root/'unused-firmware',inspect=False)
assert state['status']=='failed' and 'Caf\u00e9 \u6570\u5b66' in state['error']
assert (output/'frame.png').read_bytes()==frame
assert 'Caf\u00e9'.encode('utf-8') in (output/'index.html').read_bytes()
assert not (output/'.lock').exists()
''', built_project)
