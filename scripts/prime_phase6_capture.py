#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture a stable full device image, reusing only freshly hash-matched bytes.

Reference images are an optimization, never substitutes for readback. Every
unknown block is read in full. Two complete fingerprints must agree; no NAND
mutation or reset is issued. Outputs are private and atomically finalized.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from prime_dual_boot_contract import require
from prime_dual_installer import atomic_json
from prime_dual_physical import model,ERASED,RAW_BLOCK
from prime_hp_raw_restore import GEOMETRY
from prime_phase6_transport import Phase6SDP


def capture(device,output,references,*,event=print):
    output=model.private_output(Path(output));require(not output.exists(),'capture destination exists')
    refs=[Path(p).resolve() for p in references]
    require(all(p.is_file() and p.stat().st_size==4096*RAW_BLOCK for p in refs),'complete reference images required')
    output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    device.verify_protocol()
    geometry,bad=device.inventory();require(geometry==GEOMETRY,'unsupported capture geometry')
    temporary=output.with_suffix('.partial');digests=[];raw_reads=0
    handles=[p.open('rb') for p in refs]
    try:
        with temporary.open('wb') as target:
            os.chmod(temporary,0o600)
            for first in range(0,4096,32):
                batch=device.hash_blocks(first,32);require(len(batch)==32,'incomplete capture fingerprint')
                digests.extend(batch)
                for i,wanted in enumerate(batch):
                    candidates=[h.read(RAW_BLOCK) for h in handles]
                    raw=ERASED if wanted==model.sha(ERASED).hex() else next(
                        (b for b in candidates if model.sha(b).hex()==wanted),None)
                    if raw is None:raw=device.read_block(first+i);raw_reads+=1
                    require(len(raw)==RAW_BLOCK and model.sha(raw).hex()==wanted,'unstable raw capture')
                    target.write(raw)
                event({'state':'capturing','blocks':first+32,'raw_reads':raw_reads})
            target.flush();os.fsync(target.fileno())
        for first in range(0,4096,32):
            require(device.hash_blocks(first,32)==digests[first:first+32],'device changed between complete capture reads')
            event({'state':'verifying-capture','blocks':first+32})
        require(device.inventory()==(geometry,bad),'capture inventory changed')
        os.replace(temporary,output)
        fd=os.open(output.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        report={'schema':1,'state':'capture-verified','sha256':model.file_hash(output).hex(),
                'bytes':output.stat().st_size,'bad_markers':sorted(bad),'raw_reads':raw_reads,
                'complete_matching_fingerprints':2}
        atomic_json(output.with_suffix('.json'),report);event(report)
        return report
    finally:
        for h in handles:h.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',action='append',type=Path,default=[]);a=p.parse_args()
    d=Phase6SDP()
    try:capture(d,a.output,a.reference,event=lambda v:print(json.dumps(v),flush=True))
    finally:d.close()
