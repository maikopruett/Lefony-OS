#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Maximum resource CRC/lookup in protected ARM code, no physical calculator."""
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from cli import package
from runner import exercise


def main():
    output=ROOT/'build/sdk-resource-arm';output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lefony-assets-') as folder:
        project=Path(folder);(project/'src').mkdir();(project/'assets').mkdir()
        write_json(project/'app.json',{'abi':1,'id':'resource-bounds','name':'Resource Bounds','version':'1.0.0','license':'CC-BY-NC-SA-4.0'})
        records=[]
        for i in range(6):
            name=f'assets/blob-{i}.bin'
            size=65536 if i<5 else 42528
            (project/name).write_bytes(bytes(range(256))*(size//256)+bytes(range(size%256)))
            records.append({'id':f'blob-{i}','path':name,'type':'blob'})
        from PIL import Image
        Image.new('RGB',(320,240)).save(project/'assets/image.png')
        records.append({'id':'zz-image','path':'assets/image.png','type':'rgb565'})
        write_json(project/'assets.json',{'schema':1,'resources':records})
        (project/'src/main.cpp').write_text('''#include <lefony/app.h>
#include <lefony/resources.h>
using namespace Lefony::Resources;
extern "C" void lefony_event(Lefony::Event,uint32_t,uint32_t){
 Bundle bundle;Resource r;
 if(embeddedBytes!=524288 || bundle.open(embedded,embeddedBytes)!=Status::Ok || bundle.count()!=7)asm volatile("udf #0");
 for(unsigned i=0;i<6;i++) {
  if(!bundle.at(i,r) || r.kind!=Kind::Blob || r.bytes!=(i<5?65536:42528) || r.data[0]!=0 || r.data[r.bytes-1]!=uint8_t(r.bytes-1))asm volatile("udf #0");
 }
 if(!bundle.find("zz-image",r) || r.kind!=Kind::RGB565 || r.bytes!=153600 || r.width!=320 || r.height!=240)asm volatile("udf #0");
 unsigned polls=0;
 if(bundle.open(embedded,embeddedBytes,[&](){return ++polls==10;})!=Status::Cancelled || polls!=10 || !bundle.find("blob-5",r))asm volatile("udf #0");
}
''')
        app=package(project)
        result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
        assert result['result']==1,result
        write_json(output/'report.json',{'schema':1,'status':'passed','validation':'developer-local','physical':'not_tested',
                                        'bundle_bytes':524288,'result':result,'build':json.loads((project/'build/build.json').read_text())})
        print('PASS: maximum 512 KiB resource validates/looks up inside ARM callback, cancellation preserves prior view',flush=True)

if __name__=='__main__':main()
