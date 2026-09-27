#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual NAND-ROM wake-to-countdown paths using ordinary modeled power/key input.

HP's full power-down stops QEMU. Reset/cont represents the next cold power-on
while retaining SNVS; the physical ON/PMIC transition is a separate acceptance.
"""
import argparse
import importlib
import json
from pathlib import Path
import time
from PIL import Image
from prime_dual_migration import private_output, file_hash

m = importlib.import_module('test-prime-dual-boot')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','uboot','ddr-image','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--dismiss-usb',action='store_true',help='also test Off from the calculator app')
    parser.add_argument('--hp-first',action='store_true',help='start HP directly from cold NAND ROM')
    parser.add_argument('--long-off-press',action='store_true',help='hold Off for one second instead of 300 ms')
    args=parser.parse_args();args.rom=True;args.allow_reboot=True;args.keep_on_shutdown=True
    args.output=private_output(args.output);args.output.mkdir(parents=True,exist_ok=False)
    hashes={name:file_hash(path).hex() for name,path in
            [('nand',args.fixture),('uboot',args.uboot),('imx',args.ddr_image),('qemu',m.r.QEMU)]}
    vm=m.VM(args,'wake',args.output/'wake.overlay',held=args.hp_first)
    def on(hold=.3):
        vm.q.writel(0x020cc0fc,1);time.sleep(hold);vm.q.writel(0x020cc0fc,0);time.sleep(.2)
    def off():
        vm.q.writew(0x020b8008,0x8306);time.sleep(.2)
        on(1 if args.long_off_press else .3);vm.q.writew(0x020b8008,0x0306)
    def mark():return len(vm.log.read_text())
    def open_wake_menu(after,name):
        vm.wait('countdown ready',75,after=after)
        vm.capture(name+'-countdown')
        vm.key(7,0)
        vm.wait('screen=1',after=after);time.sleep(4)
        vm.capture(name+'-menu')
        assert 'loading OS' not in vm.log.read_text()[after:],'Enter did not stop countdown'
        assert vm.q.readl(0x020cc068)==0,'wake request not consumed'
    def history(name):
        vm.capture_hp_logical()
        frame=Image.open(vm.out/'hp-logical.png').convert('RGB')
        frame.save(vm.out/(name+'.png'))
        return frame.crop((0,20,320,220)).tobytes()
    try:
        if args.hp_first:
            vm.wait('screen=1');vm.release()
        else:
            vm.wait('entering calculator runtime',75);time.sleep(6)
            if args.dismiss_usb:vm.key(4,6);time.sleep(.5)
            native_off=mark();off();time.sleep(3)
            assert not vm.q.readl(0x021c8000)&1,'Lefony did not stop scanout for Off'
            assert 'countdown ready' not in vm.log.read_text()[native_off:],'Off reset before the next On'
            on();open_wake_menu(native_off,'native-wake')
            print('PASS native Shift+On stays off; next On resets through NAND into countdown; Enter opens menu',flush=True)
        hp_start=mark();vm.key(4,5);vm.key(7,0)
        vm.wait('HP RAM: wake-menu-v1 applied',after=hp_start)
        vm.wait('HP RAM: verified V15751 os',after=hp_start);time.sleep(10)
        for row,col in ((6,6),(6,2),(1,5),(6,4),(7,0)):
            vm.key(row,col)
        time.sleep(1)
        expected_history=history('hp-before-off')
        hp_off=mark();off();time.sleep(8)
        if vm.q.readl(0x020cc068)==0x314d464c:
            hp_wake='cold power-on represented by QMP reset/cont'
            # QEMU records SNVS TOP, but has no physical PMIC On edge.
            vm.mp.execute('system_reset');vm.mp.execute('cont')
        else:
            hp_wake='ordinary On input after HP warm suspend'
            assert not vm.q.readl(0x020f8000)&1,'HP did not turn off its backlight'
            assert 'countdown ready' not in vm.log.read_text()[hp_off:],'HP reset before On'
            on()
        open_wake_menu(hp_off,'hp-cold-wake')
        print('PASS HP save -> '+hp_wake+' -> NAND-ROM countdown -> Enter -> menu',flush=True)
        back=mark();vm.key(4,5);vm.key(7,0)
        vm.wait('HP RAM: verified V15751 os',after=back);time.sleep(10)
        assert history('hp-after-wake')==expected_history,'HP history lost during wake reboot'
        print('PASS saved HP history remains after wake menu and HP selection',flush=True)
        # A subsequent unrelated reset must return to normal priority countdown.
        reset=mark();vm.mp.execute('system_reset');vm.mp.execute('cont')
        vm.wait('countdown ready',after=reset)
        vm.wait('entering calculator runtime',75,after=reset)
        assert vm.q.readl(0x020cc068)==0,'wake request repeated'
        print('PASS wake request is one-use; ordinary reset retains Lefony priority',flush=True)
    except Exception:
        # Retain CPU state for failed hardware-model transitions; do not infer
        # a guest/physical failure merely from a timeout.
        state=vm.mp.execute('human-monitor-command',{'command-line':'info registers'})
        (vm.out/'failure-registers.txt').write_text(str(state))
        raise
    finally:vm.close()
    for name,path in [('nand',args.fixture),('uboot',args.uboot),('imx',args.ddr_image),('qemu',m.r.QEMU)]:
        assert file_hash(path).hex()==hashes[name],'input changed during test'
    (args.output/'qualification.json').write_text(json.dumps({'result':'PASS','hashes':hashes,
        'scope':('HP-first cold boot' if args.hp_first else 'native power input/reset')+
                ', HP save/power-off and ROM countdown/Enter menu; saved history; one-use request',
        'hp_wake':hp_wake,'physical_qualification':False,
        'limits':['HP PMIC cold On modeled by QMP reset/cont',
        'Physical power transitions still require acceptance']},indent=2)+'\n')


if __name__=='__main__':main()
