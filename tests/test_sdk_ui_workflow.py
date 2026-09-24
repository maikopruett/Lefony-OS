# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from preview import decode_layout,fixtures,render,source_state


@pytest.mark.parametrize('debug',[False,True])
def test_text_validation_editing_and_scroll_model(tmp_path,debug):
    compiler=shutil.which('clang++') or shutil.which('g++');assert compiler
    binary=tmp_path/'ui'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-include','initializer_list',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all',f'-DLEFONY_SDK_DEBUG={int(debug)}',
        '-I',str(ROOT/'sdk/include'),'-I',str(ROOT/'ports/lefony-prime-g2/ion/src/prime_g2'),
        str(ROOT/'tests/native/sdk_text.cpp'),'-o',str(binary)],check=True,timeout=30)
    subprocess.run([binary],check=True,timeout=30)
    symbols=subprocess.check_output(['nm',str(binary)],text=True)
    assert ('lefony_ui_debug' in symbols)==debug


def test_layout_frame_is_bounded_and_flags_clipped_source(tmp_path):
    data=bytearray(11288);struct.pack_into('<6I',data,0,0x4955464c,1,len(data),2,1,0)
    struct.pack_into('<2I8i2I32s96s',data,24,7,2,310,10,30,20,310,10,10,20,3,42,b'Save',b'src/main.cpp')
    value=decode_layout(data);assert value['nodes'][0]['clipped'] and value['nodes'][0]['line']==42
    for index,bad in ((0,0),(3,1),(4,65)):
        copy=bytearray(data);struct.pack_into('<I',copy,index*4,bad)
        with pytest.raises(ValueError):decode_layout(copy)
    with pytest.raises(ValueError):decode_layout(data[:-1])
    current=data+bytearray(4);struct.pack_into('<2I',current,4,2,len(current))
    assert decode_layout(current)['input_ready'] is False
    struct.pack_into('<I',current,11288,1)
    assert decode_layout(current)['input_ready'] is True
    assert decode_layout(current)['nodes']==value['nodes']
    struct.pack_into('<I',current,11288,2)
    with pytest.raises(ValueError,match='readiness'):decode_layout(current)
    render(tmp_path,{'status':'failed','error':'<script>bad source</script>','layout':value})
    page=(tmp_path/'index.html').read_text();assert 'STALE' in page and '&lt;script&gt;' in page and '<script>' not in page


@pytest.mark.parametrize('phase',['initial-layout','layout'])
@pytest.mark.parametrize('output',[b'Hardware watchpoint 1\n', 'Hardware watchpoint 1\n', None])
def test_layout_timeout_retains_debugger_diagnostics(tmp_path,monkeypatch,phase,output):
    from types import SimpleNamespace
    import preview
    session=tmp_path/'session';session.mkdir()
    result=tmp_path/'preview';result.mkdir()
    # A failed inspection must not replace the last successful visible frame.
    (result/'frame.png').write_bytes(b'previous frame')
    normal=SimpleNamespace(channel=SimpleNamespace(session_directory=session),execute=lambda *args:None)
    monkeypatch.setattr(preview.shutil,'which',lambda name:'/gdb')
    def timeout(*args,**kwargs):
        raise subprocess.TimeoutExpired(args[0],kwargs['timeout'],output=output,stderr=b'last guest position\xff\n')
    monkeypatch.setattr(preview.subprocess,'run',timeout)
    with pytest.raises(ValueError,match='completed frame within 30 seconds') as error:
        preview.inspect_layout(normal,tmp_path/'app.elf',result,name=phase)
    log=result/(phase+'-gdb.log')
    assert log.name in str(error.value)
    assert 'last guest position\ufffd' in log.read_text()
    if output:assert 'Hardware watchpoint 1' in log.read_text()
    assert (result/'frame.png').read_bytes()==b'previous frame'
    assert not (result/(phase+'.json')).exists()


def test_preview_fixture_bounds_symlinks_and_source_fingerprint(tmp_path):
    project=tmp_path/'project';(project/'src').mkdir(parents=True);(project/'src/main.cpp').write_text('one')
    before=source_state(project);(project/'build').mkdir();(project/'build/run.json').write_text('{}')
    assert source_state(project)==before
    (project/'src/main.cpp').write_text('two');assert source_state(project)!=before
    directory=tmp_path/'fixtures';directory.mkdir();(directory/'notebook.txt').write_text('LFNOTE1\n2+3\n')
    assert fixtures(directory)==[('notebook.txt',directory/'notebook.txt')]
    (directory/'alias').symlink_to(directory/'notebook.txt')
    with pytest.raises(ValueError):fixtures(directory)


def test_document_format_migration_and_failed_parse_preserves_value(tmp_path):
    source=tmp_path/'document.cpp';source.write_text(r'''
#include "document.h"
#include <cassert>
int main() {
  Document value;assert(value.decode("LFNOTE1\n2+3\nx^2\n",16));
  assert(value.count==2 && value.migrated);char encoded[1200];unsigned size=value.encode(encoded);
  Document current;assert(current.decode(encoded,size));assert(!current.migrated && current.count==2);
  const char *bad[]={"LFNOTE3\n","LFNOTE2\nL\nunterminated","LFNOTE2\nZ\n","LFNOTE2\nL\n\n"};
  for(auto text:bad) {assert(!current.decode(text,strlen(text)));assert(current.count==2);}
  assert(!current.decode("LFNOTE2\nL\na\0b\n",14));assert(current.count==2);
}
''')
    binary=tmp_path/'document';compiler=shutil.which('clang++') or shutil.which('g++');assert compiler
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
        '-I',str(ROOT/'sdk/include'),'-I',str(ROOT/'sdk/examples/notebook/src'),str(source),'-o',str(binary)],check=True,timeout=30)
    subprocess.run([binary],check=True,timeout=30)


def test_list_pixel_scroll_tap_cancel_limits_and_resize(tmp_path):
    compiler=shutil.which('clang++') or shutil.which('g++');assert compiler
    binary=tmp_path/'list-scroll'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
        '-fno-sanitize-recover=all','-I',str(ROOT/'sdk/include'),str(ROOT/'tests/native/sdk_list_scroll.cpp'),
        '-o',str(binary)],check=True,timeout=30)
    result=subprocess.run([binary],check=True,capture_output=True,text=True,timeout=30)
    report=json.loads(result.stdout);assert report['adversarial_steps']==100000
    output=ROOT/'build/sdk-list-scroll';output.mkdir(exist_ok=True,parents=True)
    (output/'model-report.json').write_text(json.dumps(report,indent=2)+'\n')


def test_menu_dialog_capture_focus_bounds_and_scrollbar_arithmetic(tmp_path):
    compiler=shutil.which('clang++') or shutil.which('g++');assert compiler
    binary=tmp_path/'ui-patterns'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
        '-fno-sanitize-recover=all','-I',str(ROOT/'sdk/include'),str(ROOT/'tests/native/sdk_ui_patterns.cpp'),
        '-o',str(binary)],check=True,timeout=30)
    result=subprocess.run([binary],check=True,capture_output=True,text=True,timeout=30)
    report=json.loads(result.stdout);assert report['scale_vectors']==20000
    output=ROOT/'build/sdk-ui-components';output.mkdir(exist_ok=True,parents=True)
    (output/'model-report.json').write_text(json.dumps(report,indent=2)+'\n')


def test_field_touch_utf8_selection_viewport_cancel_and_limits(tmp_path):
    compiler=shutil.which('clang++') or shutil.which('g++');assert compiler
    binary=tmp_path/'text-field'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-include','initializer_list',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I',str(ROOT/'sdk/include'),
        str(ROOT/'tests/native/sdk_text_field.cpp'),'-o',str(binary)],check=True,timeout=30)
    result=subprocess.run([binary],check=True,capture_output=True,text=True,timeout=30)
    report=json.loads(result.stdout);assert report['adversarial_steps']==20000


def test_paragraph_word_wrap_breaks_utf8_and_bounds(tmp_path):
    compiler=shutil.which('clang++') or shutil.which('g++');assert compiler
    binary=tmp_path/'paragraph'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I',str(ROOT/'sdk/include'),
        str(ROOT/'tests/native/sdk_paragraph.cpp'),'-o',str(binary)],check=True,timeout=30)
    result=subprocess.run([binary],check=True,capture_output=True,text=True,timeout=30)
    assert json.loads(result.stdout)['word_vectors']==5000
