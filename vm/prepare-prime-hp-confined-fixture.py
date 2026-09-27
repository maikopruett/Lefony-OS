#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable physical-codeword fixture with erased HP FS and upper canaries.

Never a device flashing input. Keeps original system area and factory markers.
"""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from analyze_hp_prime_compatibility import private_output
from prime_hp_confinement import FIRST_BLOCK,LAST_BLOCK
RAW_BLOCK=64*2112
STOCK_SHA='829c782248d50993ece6289c1fda8238bd9edcb804fb7361f1bf9dc9816415cb'


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stock',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 out=private_output(a.output);out.mkdir(parents=True,exist_ok=False)
 assert a.stock.stat().st_size==4096*RAW_BLOCK
 with a.stock.open('rb') as source:
  assert hashlib.file_digest(source,'sha256').hexdigest()==STOCK_SHA
 original=hashlib.sha256();result=hashlib.sha256();upper=hashlib.sha256();bad=[]
 with a.stock.open('rb') as src,(out/'confined-physical.raw').open('xb') as dest:
  for block in range(4096):
   before=src.read(RAW_BLOCK);original.update(before)
   if block<FIRST_BLOCK:after=before
   else:
    after=bytearray(b'\xff'*RAW_BLOCK)
    if block>LAST_BLOCK:
     # A recognizable physical canary per page, away from marker bytes.
     for page in range(64):
      digest=hashlib.sha256(f'phase4-protected:{block}:{page}'.encode()).digest()
      at=page*2112+128;after[at:at+32]=digest
    for page in (0,1):
     at=page*2112+2048;after[at]=before[at]
    if any(before[page*2112+2048]!=255 for page in (0,1)):bad.append(block)
   dest.write(after);result.update(after)
   if block>LAST_BLOCK:upper.update(after)
 assert original.hexdigest()==STOCK_SHA
 (out/'fixture.json').write_text(json.dumps({'source_sha256':STOCK_SHA,'fixture_sha256':result.hexdigest(),'upper_sha256':upper.hexdigest(),'erased_filesystem_blocks':[FIRST_BLOCK,LAST_BLOCK],'preserved_bad_markers':bad,'device_flash_input':False},indent=2)+'\n')
 print('Created isolated erased filesystem + protected upper canaries')
if __name__=='__main__':main()
