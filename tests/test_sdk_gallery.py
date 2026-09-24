# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import shutil
import struct
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]


def test_cache_reader_rejects_corrupt_dimensions_checksum_and_partial_files(tmp_path):
    pixels=bytes((i*19+3)&255 for i in range(288*128*2));checksum=2166136261
    for value in pixels:checksum=((checksum^value)*16777619)&0xffffffff
    valid=b'LFGAL1\r\n'+struct.pack('<6I',288,128,len(pixels),checksum,0,0)+pixels
    values={'valid':valid,'truncated':valid[:-1],'extra':valid+b'x'}
    for offset in (0,8,12,16,20,24,28,40):
        bad=bytearray(valid);bad[offset]^=1;values['bad-'+str(offset)]=bytes(bad)
    for name,data in values.items():(tmp_path/name).write_bytes(data)
    source=tmp_path/'cache.cpp';source.write_text('''#include <stdlib.h>
static bool rejectAllocation=false;
static void *allocate(size_t size) {return rejectAllocation?nullptr:malloc(size);}
#define malloc allocate
#include "cache.h"
#undef malloc
#include <cassert>
#include <vector>
int main(int argc,char **argv) {
 for(int i=1;i<argc;i++) {
   auto p=GalleryCache::read(argv[i]);assert(bool(p)==(i==1));
   if(p) {auto bytes=reinterpret_cast<unsigned char *>(p);assert(bytes[0]==3 && bytes[73727]==240);free(p);}
   FILE *file=fopen(argv[i],"rb");if(!file) continue;
   std::vector<unsigned char> input;int c;while((c=fgetc(file))!=EOF) input.push_back(c);assert(!ferror(file));fclose(file);
   for(unsigned chunk:{1,7,31,32,33,440,2048,73760}) {
     GalleryCache::Candidate candidate;bool accepted=true;
     for(unsigned at=0;at<input.size();) {
       unsigned bytes=input.size()-at;if(bytes>chunk) bytes=chunk;
       if(!candidate.append(input.data()+at,bytes)) {accepted=false;break;}at+=bytes;
     }
     assert((accepted && candidate.complete())==(i==1));
     auto pixels=candidate.take();assert(bool(pixels)==(i==1));
     if(pixels) {assert(!memcmp(pixels,input.data()+32,GalleryCache::Pixels*2));free(pixels);}
     assert(!candidate.complete());candidate.reset();
     if(i==1) {
       rejectAllocation=true;assert(!candidate.append(input.data(),32));assert(!candidate.complete());rejectAllocation=false;
       candidate.reset();assert(candidate.append(input.data(),input.size()) && candidate.complete());
       unsigned char extra=0;assert(!candidate.append(&extra,1) && !candidate.complete());
       candidate.reset();assert(!candidate.append(nullptr,1));
     }
   }
 }
}
''')
    compiler=shutil.which('clang++') or shutil.which('g++');assert compiler
    executable=tmp_path/'cache'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',
        '-I',str(ROOT/'sdk/examples/link-gallery/src'),str(source),'-o',str(executable)],check=True,timeout=30)
    subprocess.run([str(executable),*[str(tmp_path/name) for name in values],str(tmp_path/'absent')],check=True,timeout=30)
    assert all((tmp_path/name).read_bytes()==data for name,data in values.items())
