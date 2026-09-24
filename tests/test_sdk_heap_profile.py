# SPDX-License-Identifier: GPL-3.0-or-later
"""Diagnostic build identity, ELF ownership and honest allocator observations."""
import hashlib,json,os,runpy,struct,subprocess,sys,tarfile
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import build
from lfapp import pack,unpack
import heap_profile as heap
import project as projects

SOURCE='#include <stdlib.h>\nvolatile unsigned char *p;\nint main(void){p=malloc(64);if(!p)return 1;p[0]=1;free((void *)p);return 0;}\n'

@pytest.fixture(scope='module')
def candidate(tmp_path_factory):
    p=tmp_path_factory.mktemp('heap-profile');(p/'src').mkdir()
    (p/'src/main.c').write_text(SOURCE)
    metadata={'abi':1,'id':'heap-build','name':'Heap build','version':'1.0.0','license':'CC-BY-NC-SA-4.0',
        'schema':1,'minimum_api':3,'required_capabilities':16,'optional_capabilities':0,'data_schema':0}
    config={'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c']}
    (p/'app.json').write_text(json.dumps(metadata));(p/'project.json').write_text(json.dumps(config))
    original=build(p,ROOT/'sdk')[1].read_bytes()
    assert heap.address(pack(metadata,original)) is None
    config['defines']={'LEFONY_PROFILE_HEAP':1};(p/'project.json').write_text(json.dumps(config))
    diagnostic=build(p,ROOT/'sdk')[1].read_bytes()
    assert diagnostic!=original and heap.address(pack(metadata,diagnostic)) is not None
    del config['defines'];(p/'project.json').write_text(json.dumps(config))
    assert build(p,ROOT/'sdk')[1].read_bytes()==original
    return metadata,diagnostic

def test_diagnostics_are_explicit_and_reversible(candidate):
    metadata,image=candidate
    location=heap.address(pack(metadata,image))
    assert 0x10201000<=location<0x102ef000

def test_relocated_source_kit_builds_identical_instrumented_image(candidate,tmp_path):
    metadata,image=candidate
    archive=tmp_path/'sdk.tar.gz'
    runpy.run_path(str(ROOT/'scripts/package_native_sdk.py'))['package'](archive,newlib=ROOT/'build/sdk-newlib')
    with tarfile.open(archive) as bundle:bundle.extractall(tmp_path,filter='data')
    kit=tmp_path/'lefony-native-sdk'
    for line in (kit/'SHA256SUMS').read_text().splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256((kit/name).read_bytes()).hexdigest()==expected,name
    project=tmp_path/'External profiled C é';(project/'src').mkdir(parents=True)
    (project/'src/main.c').write_text(SOURCE)
    (project/'app.json').write_text(json.dumps(metadata))
    (project/'project.json').write_text(json.dumps({'schema':2,'runtime':'foreground-newlib-1',
        'sources':['src/main.c'],'defines':{'LEFONY_PROFILE_HEAP':1}}))
    environment={k:v for k,v in os.environ.items() if k not in ('LEFONY_SDK_NEWLIB','PYTHONPATH')}
    subprocess.run([sys.executable,str(kit/'sdk/tools/cli.py'),'--project',str(project),'package'],
        cwd=tmp_path,env=environment,check=True,timeout=120,capture_output=True,text=True)
    report=json.loads((project/'build/build.json').read_text())
    assert any(str(kit/'sdk/runtime/newlib') in value for value in report['link'])
    assert (project/'build/app.elf').read_bytes()==image
    assert heap.address(pack(metadata,image)) is not None

@pytest.mark.parametrize('value',[-1,2,'1',True])
def test_invalid_diagnostic_flags_are_rejected(value):
    with pytest.raises(ValueError):
        projects.validate({'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c'],
                           'defines':{'LEFONY_PROFILE_HEAP':value}})

def test_callback_profile_cannot_request_newlib_hooks():
    with pytest.raises(ValueError,match='foreground-newlib'):
        projects.validate({'schema':1,'sources':['src/main.c'],'defines':{'LEFONY_PROFILE_HEAP':1}})

@pytest.mark.parametrize('damage',['address','flags','size','magic','schema','sequence','duplicate','section-table'])
def test_untrusted_diagnostic_metadata_is_rejected(candidate,damage):
    metadata,source=candidate;image=bytearray(source)
    start=struct.unpack_from('<I',image,32)[0];count,names_index=struct.unpack_from('<HH',image,48)
    sections=[struct.unpack_from('<10I',image,start+40*i) for i in range(count)]
    table=sections[names_index];names=image[table[4]:table[4]+table[5]]
    index=next(i for i,s in enumerate(sections) if names[s[0]:].split(b'\0',1)[0]==b'.lefony.heap_profile')
    section=sections[index];at=start+40*index
    if damage=='address':struct.pack_into('<I',image,at+12,0x102f0000)
    elif damage=='flags':struct.pack_into('<I',image,at+8,5)
    elif damage=='size':struct.pack_into('<I',image,at+20,39)
    elif damage=='magic':struct.pack_into('<I',image,section[4],0)
    elif damage=='schema':struct.pack_into('<I',image,section[4]+4,2)
    elif damage=='sequence':struct.pack_into('<I',image,section[4]+12,2)
    elif damage=='duplicate':image[start+40:start+80]=image[at:at+40]
    elif damage=='section-table':struct.pack_into('<I',image,32,len(image))
    with pytest.raises(ValueError,match='Heap profile ELF'):heap.address(pack(metadata,bytes(image)))

TARGET=hashlib.sha256(b'heap snapshot identity').hexdigest()
LOCATION=0x10202000
class Channel:
    def __init__(self,reply):self.reply=reply
    def command(self,_):return self.reply
def response(**changes):
    values=dict.fromkeys(heap.FIELDS,0)
    values.update(version=1,bytes=heap.SNAPSHOT.size,flags=3,samples=10,
        allocated_peak_bytes=4096,arena_bytes=4096,arena_peak_bytes=8192,
        allocator_observations=5,loads=2,address=LOCATION,lfapp_sha256=bytes.fromhex(TARGET))
    values.update(changes)
    return 'DATA '+heap.SNAPSHOT.pack(*(values[n] for n in heap.FIELDS)).hex()
def test_free_returns_live_usage_but_retains_peak():
    r=heap.snapshot(Channel(response()),TARGET,LOCATION,2)
    assert r['allocated_bytes']==0 and r['allocated_peak_bytes']==4096
    assert r['arena_bytes']==4096 and r['status']=='observed'
    assert 'padding and metadata' in r['includes']
def test_interrupted_record_is_not_claimed_complete():
    r=heap.snapshot(Channel(response(flags=19)),TARGET,LOCATION,2)
    assert r['status']=='partial'
def test_no_allocator_calls_are_not_reported_as_measured_zero():
    r=heap.snapshot(Channel(response(flags=1,allocated_peak_bytes=0,arena_bytes=0,
        arena_peak_bytes=0,allocator_observations=0)),TARGET,LOCATION,2)
    assert r['status']=='not_observed'
@pytest.mark.parametrize('fields',[{'version':2},{'bytes':0},{'reserved':1},{'flags':0},{'flags':7},
    {'flags':35},{'samples':0},{'loads':1},{'address':LOCATION+4},{'lfapp_sha256':bytes(32)},
    {'allocated_bytes':8193},{'allocated_peak_bytes':8193},{'arena_peak_bytes':8380417},
    {'flags':1}])
def test_invalid_or_misattributed_snapshots_are_rejected(fields):
    with pytest.raises(RuntimeError):heap.snapshot(Channel(response(**fields)),TARGET,LOCATION,2)
def test_older_firmware_cannot_silently_skip_heap_observation():
    with pytest.raises(RuntimeError,match='matching VM'):heap.arm(Channel('ERR unknown command'),LOCATION)
