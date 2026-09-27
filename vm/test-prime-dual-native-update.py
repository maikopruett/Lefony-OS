#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual ARM candidate rejects legacy update entry points without NAND writes."""
import argparse
import importlib
import json
from pathlib import Path
import subprocess
from prime_dual_migration import private_output

m=importlib.import_module('test-prime-dual-boot')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','uboot','ddr-image','native-elf','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.rom=True;a.output=private_output(a.output);a.output.mkdir(parents=True,exist_ok=False)
    table=subprocess.check_output(['arm-none-eabi-nm','-C',str(a.native_elf)],text=True)
    symbols={parts[2]:int(parts[0],16) for line in table.splitlines() if len(parts:=line.split(maxsplit=2))==3}
    addresses=[symbols[name] for name in ('PrimeG2::NANDUpdate::status()',
        'PrimeG2::NANDUpdate::acceptManifest(void const*, unsigned int)',
        'PrimeG2::NANDUpdate::install(unsigned char const*, unsigned int)',
        'PrimeG2::DevelopmentUpdate::begin(unsigned char const*, unsigned int, unsigned int)')]
    vm=m.VM(a,'native-update',a.output/'native.overlay')
    try:
        vm.wait('entering calculator runtime',75)
        script=vm.out/'deny.gdb'
        program='''import gdb
mem=gdb.selected_inferior()
def word(a):return int.from_bytes(mem.read_memory(a,4),'little')
def call(a,args):
    sig=','.join('unsigned int' for _ in args) or 'void'
    return int(gdb.parse_and_eval('((unsigned int (*)(%s))%#x)(%s)'%(sig,a,','.join(str(v) for v in args))))
status=call(ADDR[0],[])
assert word(status+60)==0, 'legacy install advertised'
programs=word(0x01806170)
assert call(ADDR[1],[0,0])==0 and word(status+12)==7, 'manifest not refused by layout guard'
assert call(ADDR[2],[0,0])==0 and word(status+12)==7, 'install not refused by layout guard'
assert call(ADDR[3],[0,0,0])==0, 'development install accepted'
assert word(0x01806170)==programs, 'rejected update wrote NAND'
print('PASS ARM legacy manifest/install/development refusal; no NAND programs')
'''.replace('ADDR',repr(addresses))
        script.write_text('set pagination off\nset confirm off\nset architecture arm\nfile '+json.dumps(str(a.native_elf.resolve()))+
            '\ntarget remote '+str(vm.p/'gdb')+'\npython\n'+program+'end\ndetach\nquit\n')
        with (vm.out/'result.log').open('w') as log:
            subprocess.run(['arm-none-eabi-gdb','-q','-nx','-batch','-x',str(script)],check=True,
                           stdout=log,stderr=subprocess.STDOUT,timeout=60)
        assert 'PASS ARM legacy' in (vm.out/'result.log').read_text()
    finally:vm.close()
    print('PASS actual native candidate refuses legacy update writers',flush=True)


if __name__=='__main__':main()
