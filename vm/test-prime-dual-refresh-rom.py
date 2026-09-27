#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual ARM ROM checks for boot-stream refresh transition fixtures."""
import argparse
import importlib
import json
from pathlib import Path
from prime_dual_migration import private_output, file_hash, require

m=importlib.import_module('test-prime-dual-boot')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixtures','uboot','ddr-image','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.rom=True;a.output=private_output(a.output)
    require(not a.output.exists(),'new output required');a.output.mkdir(parents=True)
    evidence=[]
    for name,fixture,erased in (
        ('old-primary-expanded-count','expanded-fcb.raw',()),
        ('old-secondary-expanded-count','expanded-fcb.raw',range(240,248)),
        ('new-secondary-during-primary-replacement','new-secondary.raw',range(240,248))):
        a.fixture=a.fixtures/fixture;before=file_hash(a.fixture).hex()
        overlay=a.output/(name+'.overlay')
        if erased:m.erased_blocks(overlay,erased)
        vm=m.VM(a,name,overlay)
        try:vm.wait('entering calculator runtime',75)
        finally:vm.close()
        require(file_hash(a.fixture).hex()==before,'transition input changed')
        evidence.append({'case':name,'fixture_sha256':before,'result':'PASS'})
        print('PASS '+name,flush=True)
    (a.output/'qualification.json').write_text(json.dumps({'result':'PASS',
        'cases':evidence,'qemu_sha256':file_hash(m.r.QEMU).hex(),
        'physical_qualification':False},indent=2)+'\n')


if __name__=='__main__':main()
