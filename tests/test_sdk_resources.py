# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zlib
import pytest
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from assets import prepare, HEADER, ENTRY
from build import build, write_json, lock_value
from source import collect, extract


def project(path):
    (path/'assets').mkdir(parents=True)
    pixels=Image.new('RGBA',(4,2))
    pixels.putdata([(255,0,0,255),(0,255,0,255),(0,0,255,255),(0,0,0,0),
                    (255,255,255,255),(0,0,0,255),(128,128,128,255),(248,252,248,255)])
    pixels.save(path/'assets/test.png')
    (path/'assets/note.txt').write_bytes(b'resource note\n')
    spec={'schema':1,'resources':[{'id':'image','type':'rgb565','path':'assets/test.png','transparent':0xf81f},
                                {'id':'note','type':'blob','path':'assets/note.txt'}]}
    write_json(path/'assets.json',spec)
    return spec


def test_resource_bytes_are_deterministic_canonical_rgb565_and_source_roundtrip(tmp_path):
    spec=project(tmp_path);data,report=prepare(tmp_path)
    assert data==prepare(tmp_path)[0]
    assert HEADER.unpack_from(data)==(b'LFRSRC1\0',1,2,len(data),32,160,zlib.crc32(data[32:]))
    assert ENTRY.unpack_from(data,32)[1:]==(2,160,16,4,2,8,1,0xf81f,0,0)
    assert data[160:176]==struct.pack('<8H',0xf800,0x7e0,0x1f,0xf81f,0xffff,0,0x8410,0xffff)
    spec['resources'].reverse();write_json(tmp_path/'assets.json',spec)
    assert prepare(tmp_path)[0]==data # declaration order is irrelevant
    (tmp_path/'src').mkdir();(tmp_path/'src/main.cpp').write_text('// source\n')
    write_json(tmp_path/'app.json',{'abi':1,'id':'asset-test','name':'Asset','version':'1.0.0','license':'CC-BY-NC-SA-4.0'})
    with pytest.raises(ValueError,match='format 1'):collect(tmp_path)
    copy=tmp_path/'copy';extract(collect(tmp_path,1),copy)
    assert prepare(copy)[0]==data
    assert report['bytes']==len(data) and len(report['entries'])==2


def test_actual_resource_parser_and_clipped_pixels_under_sanitizers(tmp_path):
    project(tmp_path);data,_=prepare(tmp_path)
    # Golden converter bytes enter the public C++ reader unchanged.
    source=tmp_path/'test.cpp'
    source.write_text('''#include <lefony/resources.h>
#include <lefony/graphics.h>
#include <cassert>
#include <cstring>
#include <vector>
using namespace Lefony;
const uint8_t bytes[]={'''+','.join(map(str,data))+'''};
int main(){
 Resources::Bundle bundle;Resources::Resource resource;
 assert(!bundle.count() && !bundle.find("image",resource));
 assert(bundle.open(bytes,sizeof(bytes))==Resources::Status::Ok && bundle.count()==2);
 assert(bundle.find("image",resource) && resource.kind==Resources::Kind::RGB565);
 assert(resource.width==4 && resource.height==2 && resource.bytes==16 && resource.transparent && resource.key==0xf81f);
 uint16_t pixels[8];for(auto &p:pixels)p=0xaaaa;
 auto status=Graphics::image({0,0,4,2},0,0,resource.width,resource.height,resource.stride,resource.data,resource.bytes,
  [&](int x,int y,int w,uint16_t color){for(int i=0;i<w;i++)pixels[y*4+x+i]=color;return true;},resource.transparent,resource.key);
 assert(status==Graphics::Status::Ok);
 const uint16_t expected[]={0xf800,0x7e0,0x1f,0xaaaa,0xffff,0,0x8410,0xffff};assert(!memcmp(pixels,expected,sizeof(pixels)));
 assert(bundle.find("note",resource) && resource.bytes==14 && !memcmp(resource.data,"resource note\\n",14));
 assert(!bundle.find(nullptr,resource) && !bundle.find("missing",resource) && !bundle.find("this-name-is-more-than-23-characters",resource));
 assert(!bundle.at(2,resource) && !bundle.name(2));
 for(unsigned n=0;n<sizeof(bytes);n++)assert(bundle.open(bytes,n)==Resources::Status::Invalid);
 for(unsigned i=0;i<sizeof(bytes);i++){std::vector<uint8_t> bad(bytes,bytes+sizeof(bytes));bad[i]^=128;assert(bundle.open(bad.data(),bad.size())==Resources::Status::Invalid);}
 const unsigned fields[][2]={{8,2},{12,0},{12,33},{16,0},{20,31},{24,159},
  {32+24,3},{32+28,0},{32+32,0},{32+36,321},{32+40,241},{32+44,6},{32+48,2},{32+52,65536},{32+56,1},
  {96+24,3},{96+28,175},{96+32,65537},{96+36,1},{96+48,1}};
 for(auto &field:fields){
  std::vector<uint8_t> bad(bytes,bytes+sizeof(bytes));
  for(unsigned j=0;j<4;j++)bad[field[0]+j]=uint8_t(field[1]>>(8*j));
  uint32_t crc=0xffffffffu;
  for(unsigned i=32;i<bad.size();i++){crc^=bad[i];for(unsigned b=0;b<8;b++)crc=(crc>>1)^((crc&1)?0xedb88320u:0);}
  crc^=0xffffffffu;for(unsigned j=0;j<4;j++)bad[28+j]=uint8_t(crc>>(8*j));
  assert(bundle.open(bad.data(),bad.size())==Resources::Status::Invalid);
 }
 assert(bundle.count()==2 && bundle.find("note",resource));
 assert(bundle.open(bytes,sizeof(bytes),[](){return true;})==Resources::Status::Cancelled);
}
''')
    compiler=shutil.which('clang++') or shutil.which('g++');assert compiler
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',
                    '-I',str(ROOT/'sdk/include'),str(source),'-o',str(tmp_path/'test')],check=True)
    subprocess.run([tmp_path/'test'],check=True,timeout=30)


@pytest.mark.parametrize('kind',['id','duplicate','count','schema','unknown','traversal','source-symlink','config-symlink','input-size','partial-alpha','opaque-key','unkeyed-alpha','oversize-image','unknown-type','unsupported-extension'])
def test_resource_conversion_rejects_bad_inputs(tmp_path,kind):
    spec=project(tmp_path);records=spec['resources']
    if kind=='id':records[0]['id']='../image'
    elif kind=='duplicate':records[1]['id']='image'
    elif kind=='count':spec['resources']=[]
    elif kind=='schema':spec['schema']=True
    elif kind=='unknown':spec['extra']=1
    elif kind=='traversal':records[0]['path']='assets/../test.png'
    elif kind=='source-symlink':(tmp_path/'assets/test.png').unlink();(tmp_path/'assets/test.png').symlink_to(tmp_path/'assets/note.txt')
    elif kind=='config-symlink':pass
    elif kind=='input-size':(tmp_path/'assets/note.txt').write_bytes(bytes(65537))
    elif kind=='partial-alpha':Image.new('RGBA',(1,1),(255,0,0,128)).save(tmp_path/'assets/test.png')
    elif kind=='opaque-key':Image.new('RGBA',(1,1),(255,0,255,255)).save(tmp_path/'assets/test.png')
    elif kind=='unkeyed-alpha':del records[0]['transparent']
    elif kind=='oversize-image':Image.new('RGB',(321,1)).save(tmp_path/'assets/test.png')
    elif kind=='unknown-type':records[0]['type']='script'
    else:records[0]['path']='assets/test.jpg'
    write_json(tmp_path/'assets.json',spec)
    if kind=='config-symlink':(tmp_path/'assets.json').unlink();(tmp_path/'assets.json').symlink_to(tmp_path/'missing')
    with pytest.raises(ValueError):prepare(tmp_path)


def test_resource_changes_rebuild_only_generated_object_and_stay_readonly(tmp_path):
    project(tmp_path);(tmp_path/'src').mkdir()
    write_json(tmp_path/'app.json',{'abi':1,'id':'asset-test','name':'Asset','version':'1.0.0','license':'CC-BY-NC-SA-4.0'})
    (tmp_path/'src/main.cpp').write_text('''#include <lefony/app.h>
#include <lefony/resources.h>
Lefony::Resources::Bundle bundle;
extern "C" void lefony_event(Lefony::Event event,uint32_t,uint32_t){
 if(event==Lefony::Event::Start && bundle.open(Lefony::Resources::embedded,Lefony::Resources::embeddedBytes)!=Lefony::Resources::Status::Ok)asm volatile("udf #0");
}
''')
    _,first=build(tmp_path,ROOT/'sdk');original=first.read_bytes()
    report=json.loads((tmp_path/'build/build.json').read_text())
    assert report['resources']['embedded_resource_bytes']==len(prepare(tmp_path)[0])
    build(tmp_path,ROOT/'sdk');assert json.loads((tmp_path/'build/build.json').read_text())['compiled']==[]
    (tmp_path/'assets/note.txt').write_text('changed\n')
    _,second=build(tmp_path,ROOT/'sdk')
    assert second.read_bytes()!=original
    assert json.loads((tmp_path/'build/build.json').read_text())['compiled']==['build/generated/lefony-resources.cpp']
    from lfapp import elf_segments
    _,segments=elf_segments(second.read_bytes());data=prepare(tmp_path)[0]
    assert any(data in content and permissions==5 for _,content,_,permissions in segments)
    assert not any(data in content for _,content,_,permissions in segments if permissions==6)
