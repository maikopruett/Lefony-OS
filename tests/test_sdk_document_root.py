# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the future root codec and actual preserved FILE2 reader fail-closed behavior."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]
PORT=ROOT/'ports/lefony-prime-g2/ion/src/prime_g2'
REVISION='91701e213d74918226b3692f570079c2c13d9000'


def compiler():
    found=shutil.which('clang++') or shutil.which('g++')
    assert found,'host C++ compiler required'
    return found


def test_document_root_codec_boundaries_and_preserved_output(tmp_path):
    source=tmp_path/'codec.cpp';binary=tmp_path/'codec'
    source.write_text('''#include "app_document_root.h"
#include <cassert>
#include <cstdio>
using namespace PrimeG2::AppDocumentRoot;
int main(int argc,char **argv){
 assert(argc==2);
 Root r;r.serial=10;r.flags=PendingUpgrade;r.highVersion[0]=2;
 r.current.package=9;r.current.data=10;r.current.packageBytes=700000;r.current.dataBytes=65536;r.current.dataSchema=2;
 r.previous.package=6;r.previous.data=8;r.previous.packageBytes=600000;r.previous.dataBytes=1024;r.previous.dataSchema=1;
 for(unsigned i=0;i<32;i++){r.current.packageHash[i]=i;r.current.dataHash[i]=32+i;r.previous.packageHash[i]=64+i;r.previous.dataHash[i]=96+i;}
 uint8_t wire[Bytes],again[Bytes];assert(encode(r,wire));Root actual;assert(decode(wire,Bytes,&actual)==Result::Ok);
 assert(encode(actual,again) && !memcmp(wire,again,Bytes));
 FILE *f=fopen(argv[1],"wb");assert(f && fwrite(wire,1,Bytes,f)==Bytes && !fclose(f));
 for(unsigned n=0;n<Bytes;n++){actual.serial=123;assert(decode(wire,n,&actual)==Result::Invalid && actual.serial==123);}
 for(unsigned i=0;i<Bytes;i++){uint8_t bad[Bytes];memcpy(bad,wire,Bytes);bad[i]^=128;actual.serial=123;
  assert(decode(bad,Bytes,&actual)!=Result::Ok && actual.serial==123);}
 const unsigned fields[][2]={{12,0},{16,2},{20,1000000},{32,11},{36,11},{40,467},{40,2101665},{44,65537},{52,1},{120,0},{140,1}};
 for(auto &field:fields){uint8_t bad[Bytes];memcpy(bad,wire,Bytes);Detail::put(bad+field[0],field[1]);
  PrimeG2::NativeAppHash::sha256(bad,Bytes-32,bad+Bytes-32);assert(decode(bad,Bytes,&actual)==Result::Invalid);}
 r.previous={};memset(again,0xa5,Bytes);assert(!encode(r,again));for(auto b:again)assert(b==0xa5);
 r.flags=0;r.serial=0xffffffffu;r.current.package=r.serial;r.current.data=r.serial;r.current.dataSchema=0xffffffffu;
 for(auto &part:r.highVersion)part=999999;
 assert(encode(r,wire) && decode(wire,Bytes,&actual)==Result::Ok);
 r.previous=r.current;r.flags=PendingUpgrade;assert(!valid(r));r.flags=0;assert(valid(r));
 r.previous.dataSchema^=1;assert(!valid(r));r.previous=r.current;r.previous.packageHash[0]^=1;assert(!valid(r));
}
''')
    subprocess.run([compiler(),'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',
                    '-I',str(PORT),str(source),'-o',str(binary)],check=True,timeout=60)
    fixture=tmp_path/'root.bin';subprocess.run([binary,fixture],check=True,timeout=30)
    data=fixture.read_bytes();assert len(data)==240 and data[:8]==b'LFAFILE3'
    assert hashlib.sha256(data[:208]).digest()==data[208:]


@pytest.mark.parametrize('format', [3, 4, 5])
def test_preserved_file_two_reader_rejects_future_root_without_formatting(tmp_path, format):
    preserved_reader(tmp_path, format)


def preserved_reader(tmp_path, format, previous=None):
    old=tmp_path/'old';old.mkdir()
    names=['app_storage.h','app_storage.cpp','legacy_app_storage.h','legacy_app_storage.cpp','native_app_digest.h']
    if previous:
        names += ['app_document_root.h', 'app_document_store.h', 'app_document_store.cpp']
    for name in names:
        path='ports/lefony-prime-g2/ion/src/prime_g2/'+name
        (old/name).write_bytes((previous/name).read_bytes() if previous else
                              subprocess.check_output(['git','show',REVISION+':'+path],cwd=ROOT))
    # Reuse only the synthetic NAND backend from the maintained storage test.
    fixture=(ROOT/'tests/native/app_storage.cpp').read_text()
    flash=fixture[fixture.index('struct PowerCut'):fixture.index('static void finish')]
    source=tmp_path/'old-reader.cpp';binary=tmp_path/'old-reader'
    source.write_text('''#include "app_storage.h"
#include "app_document_root.h"
#include <cassert>
#include <array>
#include <map>
#include <set>
#include <vector>
#include <cstring>
using namespace PrimeG2::AppStorage;
using Page=std::array<uint8_t,PageBytes>;
'''+flash+'''
int main(){
 Flash flash;std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
 auto name=[](const uint8_t *,size_t,char id[49]){strcpy(id,"example");return true;};
 {Volume v(flash.backend());assert(v.initialize(package.data(),package.size(),data.data(),data.size(),name));}
 // Mount the same filesystem independently to seed a synthetic future file.
 // No production reader, private field, or parser is patched to accept it.
 lfs_t fs{};lfs_config c{};uint8_t read[2048]{},prog[2048]{},look[64]{},cache[2048]{};
 c.context=&flash;
 c.read=[](const lfs_config *cfg,lfs_block_t b,lfs_off_t off,void *out,lfs_size_t size){
  assert(off%PageBytes==0 && size%PageBytes==0);for(unsigned i=0;i<size;i+=PageBytes) {
   if(!Flash::read(cfg->context,(FirstBlock+2+b)*PagesPerBlock+(off+i)/PageBytes,static_cast<uint8_t *>(out)+i))return int(LFS_ERR_IO); } return 0;};
 c.prog=[](const lfs_config *cfg,lfs_block_t b,lfs_off_t off,const void *in,lfs_size_t size){
  assert(off%PageBytes==0 && size%PageBytes==0);for(unsigned i=0;i<size;i+=PageBytes) {
   if(!Flash::program(cfg->context,(FirstBlock+2+b)*PagesPerBlock+(off+i)/PageBytes,static_cast<const uint8_t *>(in)+i))return int(LFS_ERR_IO); } return 0;};
 c.erase=[](const lfs_config *cfg,lfs_block_t b){return Flash::erase(cfg->context,FirstBlock+2+b)?0:int(LFS_ERR_IO);};
 c.sync=[](const lfs_config *){return 0;};c.read_size=c.prog_size=c.cache_size=PageBytes;c.block_size=BlockBytes;c.block_count=BlockCount-2;
 c.block_cycles=100;c.lookahead_size=64;c.read_buffer=read;c.prog_buffer=prog;c.lookahead_buffer=look;c.name_max=53;
 c.file_max=MaximumPackage+MaximumData+64;c.metadata_max=8192;c.inline_max=256;
 assert(!lfs_mount(&fs,&c));
 PrimeG2::AppDocumentRoot::Root root;root.serial=1;root.current.package=root.current.data=1;root.current.packageBytes=468;
 uint8_t wire[240];assert(PrimeG2::AppDocumentRoot::encode(root,wire));
 if(FUTURE_FORMAT==4) {
   wire[7]='4';PrimeG2::AppDocumentRoot::Detail::put(wire+8,4);
   PrimeG2::AppDocumentRoot::Detail::put(wire+44,160);PrimeG2::AppDocumentRoot::Detail::put(wire+52,1);
   PrimeG2::NativeAppHash::sha256(wire,208,wire+208);
 }
 lfs_file_t file{};lfs_file_config config{};config.buffer=cache;
 uint8_t protectedWire[352]{};const uint8_t *payload=wire;unsigned payloadBytes=sizeof(wire);lfs_attr attribute{};
 if(FUTURE_FORMAT==5) {
   memcpy(protectedWire,"LFAFILE5",8);PrimeG2::AppDocumentRoot::Detail::put(protectedWire+8,5);
   PrimeG2::AppDocumentRoot::Detail::put(protectedWire+12,352);memcpy(protectedWire+16,"example",7);
   memcpy(protectedWire+80,wire,240);PrimeG2::NativeAppHash::sha256(protectedWire,320,protectedWire+320);
   payload=protectedWire;payloadBytes=sizeof(protectedWire);attribute={0x52,protectedWire,sizeof(protectedWire)};
   config.attrs=&attribute;config.attr_count=1;
 }
 assert(!lfs_file_opencfg(&fs,&file,"apps/example.app",LFS_O_CREAT|LFS_O_WRONLY,&config));
 assert(lfs_file_write(&fs,&file,payload,payloadBytes)==int(payloadBytes));assert(!lfs_file_close(&fs,&file));assert(!lfs_unmount(&fs));
 auto before=flash.pages;int writes=flash.writes;
 {Volume reader(flash.backend());assert(reader.mount());Entry entry;
  assert(!reader.entry("example",&entry));
  assert(!reader.list([](void *,const char *,const Entry &){return true;},nullptr));
  assert(reader.initialize(package.data(),package.size(),data.data(),data.size(),name));
  assert(!reader.entry("example",&entry));
 }
 assert(flash.writes==writes && flash.pages==before);
}
'''.replace('FUTURE_FORMAT',str(format)))
    flags=['-DLFS_NO_MALLOC','-DLFS_NO_DEBUG','-DLFS_NO_WARN','-DLFS_NO_ERROR','-DLFS_NO_ASSERT']
    objects=[]
    for name in ('lfs','lfs_util'):
        obj=tmp_path/(name+'.o');objects.append(str(obj))
        subprocess.run([shutil.which('cc'),'-std=c99','-fsanitize=address,undefined','-fexceptions',*flags,'-I',str(PORT),
                        '-DLFS_DEFINES=littlefs_compat/defines.h','-c',str(PORT/f'littlefs/{name}.c'),'-o',str(obj)],check=True,timeout=60)
    extras=[str(old/'app_document_store.cpp')] if previous else []
    subprocess.run([compiler(),'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',*flags,'-I',str(old),'-I',str(PORT),
                    str(source),str(old/'app_storage.cpp'),str(old/'legacy_app_storage.cpp'),*extras,*objects,'-o',str(binary)],check=True,timeout=60)
    subprocess.run([binary],check=True,timeout=60)


if __name__ == '__main__':
    import argparse
    import tempfile
    parser=argparse.ArgumentParser(description='Verify the retained FILE3 source reader rejects FILE4 without NAND mutation.')
    parser.add_argument('--previous-file3',type=Path,required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='lefony-old-file3-') as temporary:
        preserved_reader(Path(temporary),4,args.previous_file3)
    print('PASS: retained FILE3 reader rejects FILE4 without formatting or NAND mutation')
