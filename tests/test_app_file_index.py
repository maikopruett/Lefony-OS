# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded file-index wire format, path validation and explicit FILE4 rejection."""
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / 'ports/lefony-prime-g2/ion/src/prime_g2'


def test_file_index_codec_and_file_four_root(tmp_path):
    source = tmp_path / 'index.cpp'
    source.write_text('''#include "app_file_index.h"
#include "app_document_root.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>
using namespace PrimeG2::AppFileIndex;
int main(int argc,char **argv) {
  assert(argc==2);Index index;index.clear();index.entries=3;index.extents=2;
  index.entry[1].kind=Directory;strcpy(index.entry[1].name,"level");
  auto &file=index.entry[2];file.kind=File;strcpy(file.name,"level/data.bin");file.bytes=ChunkBytes+5;file.count=2;
  for(unsigned i=0;i<2;i++) {auto &e=index.extent[i];e.generation=9;e.type=ChunkObject;e.part=i+1;e.bytes=i?5:ChunkBytes;}
  uint8_t wire[512],copy[512];assert(encode(index,9,wire,sizeof(wire)));Index decoded;
  assert(decode(wire,sizeof(wire),9,&decoded));assert(encode(decoded,9,copy,sizeof(copy)) && !memcmp(copy,wire,512));
  FILE *out=fopen(argv[1],"wb");assert(out && fwrite(wire,1,512,out)==512 && !fclose(out));
  for(unsigned bytes=0;bytes<512;bytes++) assert(!decode(wire,bytes,9,&decoded));
  const unsigned fields[][2]={{8,2},{12,129},{16,513},{20,1},{128,File},{256,PrivateBytes},{388,0},
    {392,1},{416,0},{420,0},{424,DataObject},{428,ChunkBytes+1},{464,10},{468,1},{144,1}};
  for(auto &field:fields) {memcpy(copy,wire,512);put(copy+field[0],field[1]);assert(!decode(copy,512,9,&decoded));}
  memcpy(copy,wire,512);memset(copy+32+256,'a',96);assert(!decode(copy,512,9,&decoded));
  for(const char *name:{"/absolute","../escape","x/../escape","x//y","x/","x/./y",".","..","x\\\\y"}) assert(!path(name));
  assert(path("Mixed Names/data_1.bin"));assert(!parent(index,"missing/data.bin"));
  PrimeG2::AppDocumentRoot::Root root;root.format=4;root.serial=9;root.current.package=root.current.data=9;
  root.current.packageBytes=468;root.current.dataBytes=512;root.current.dataKind=PrimeG2::AppDocumentRoot::FileIndex;
  uint8_t encoded[240];assert(PrimeG2::AppDocumentRoot::encode(root,encoded));
  assert(!memcmp(encoded,"LFAFILE4",8));PrimeG2::AppDocumentRoot::Root actual;
  assert(PrimeG2::AppDocumentRoot::decode(encoded,240,&actual)==PrimeG2::AppDocumentRoot::Result::Ok);
  assert(actual.format==4 && actual.current.dataKind==1);root.format=3;assert(!PrimeG2::AppDocumentRoot::encode(root,encoded));
}
''')
    binary = tmp_path / 'index'
    subprocess.run([shutil.which('c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', '-I', str(PORT), str(source), '-o', str(binary)], check=True, timeout=60)
    wire = tmp_path / 'index.bin'
    subprocess.run([str(binary), str(wire)], check=True, timeout=30)
    value = wire.read_bytes()
    assert len(value) == 512 and value[:8] == b'LFAIDX1\0'
    assert struct.unpack_from('<6I', value, 8) == (1, 3, 2, 0, 0, 0)
    assert value[288:303] == b'level/data.bin\0'
    assert struct.unpack_from('<4I', value, 416) == (9, 1, 1, 130944)
    assert struct.unpack_from('<4I', value, 464) == (9, 2, 1, 5)
