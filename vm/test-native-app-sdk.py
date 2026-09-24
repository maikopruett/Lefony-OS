#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile actual app binaries and verify isolation in the Prime guest runtime."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk/tools"))
from cli import package
from lfapp import CAPABILITIES
from runner import exercise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, default=ROOT/"dist/lefony-os-prime-g2-vm-native.elf")
    parser.add_argument("--qemu", type=Path, default=ROOT/"build/qemu-prime-g2/qemu-system-arm")
    args = parser.parse_args()
    cases = {
        "return": ("(void)Lefony::millis();", 1),
        "kernel-read": ("(void)*reinterpret_cast<volatile unsigned *>(0x82000000);", -14),
        "device-write": ("*reinterpret_cast<volatile unsigned *>(0x020c4000)=0;", -14),
        "code-write": ("*reinterpret_cast<volatile unsigned *>(0x10000000)=0;", -14),
        "guard": ("*reinterpret_cast<volatile unsigned *>(0x102ef000)=0;", -14),
        "execute-data": ("reinterpret_cast<void(*)()>(0x10201000)();", -13),
        "undefined": ('asm volatile(".word 0xe7f000f0");', -11),
        "hang": ('while(true) asm volatile("nop");', -2),
        "mask-irq": ('asm volatile("cpsid i"); while(true) asm volatile("nop");', -2),
        "disable-vfp": ('asm volatile("mov r0,#0; vmsr fpexc,r0" ::: "r0");', -11),
        "bad-pointer": ('if(Lefony::service(1,reinterpret_cast<void *>(0x82000000))!=-4) while(true) {}', 1),
        "draw": ('Lefony::fill({0,0,320,240,Lefony::Green});', 1),
        "discovery": (f'Lefony::Capabilities c;if(Lefony::discover(c)!=0 || c.abi!=1 || c.features!={CAPABILITIES} || c.privateDataBytes!=65536 || c.maxBatchRects!=64) asm volatile("udf #0");', 1),
        "discovery-readonly": ('if(Lefony::service(6,reinterpret_cast<void *>(0x10000000))!=-4) asm volatile("udf #0");', 1),
        "discovery-short": ('Lefony::Capabilities c;c.size=44;if(Lefony::discover(c)!=-4) asm volatile("udf #0");', 1),
        "discovery-reserved": ('Lefony::Capabilities c;c.reserved=1;if(Lefony::discover(c)!=-4) asm volatile("udf #0");', 1),
        "batch": ('Lefony::Rect r[2]={{0,0,160,240,Lefony::Green},{160,0,160,240,Lefony::White}};if(Lefony::batch(r,2)!=0) asm volatile("udf #0");', 1),
        "batch-area": ('Lefony::Rect r[2]={{0,0,320,240,0},{0,0,1,1,0}};if(Lefony::batch(r,2)!=-4) asm volatile("udf #0");', 1),
        "batch-overflow": ('Lefony::Rect r={0,0,0x7fffffff,2,0};if(Lefony::batch(&r,1)!=-4) asm volatile("udf #0");', 1),
        "batch-pointer": ('if(Lefony::batch(reinterpret_cast<Lefony::Rect *>(0x82000000),1)!=-4) asm volatile("udf #0");', 1),
        "batch-count": ('Lefony::Rect r={0,0,1,1,0};if(Lefony::batch(&r,65)!=-4 || Lefony::batch(&r,0)!=-4) asm volatile("udf #0");', 1),
        "heap-exhaustion": ('Lefony::Arena<32> arena;if(!arena.allocate(32) || arena.allocate(1) || arena.peak()!=32) asm volatile("udf #0");arena.reset();if(!arena.allocate(16,16)) asm volatile("udf #0");', 1),
        "numeric": ('Lefony::Numeric::Statistics stats;for(unsigned i=1;i<=5;i++) stats.add(i);double mean=0,var=0;if(stats.mean(mean)!=Lefony::Numeric::Status::Ok || mean!=3 || stats.variance(var,false)!=Lefony::Numeric::Status::Ok || var!=2) asm volatile("udf #0");', 1),
        "root-cancel": ('auto root=Lefony::Numeric::bisect([](double x){return x*x-2;},0,2,1e-8,100,[](){return true;});if(root.status!=Lefony::Numeric::Status::Cancelled) asm volatile("udf #0");', 1),
        "memory": ('char a[8]={1,2,3,4,5,6,7,8};memmove(a+1,a,7);if(a[7]!=7 || a[1]!=1) asm volatile("udf #0");memset(a,0,8);char b[8];memcpy(b,a,8);if(memcmp(a,b,8)) asm volatile("udf #0");', 1),
        "expression": ('using namespace Lefony::Expression;Context context;context.set("x",7);auto parsed=context.parse("sqrt(x*x)+2^-2",14);auto result=context.evaluate(parsed.expression);if(parsed.status!=Status::Ok || result.status!=Status::Ok || result.value!=7.25) asm volatile("udf #0");', 1),
        "expression-cancel": ('using namespace Lefony::Expression;Context context;auto parsed=context.parse("1+2+3",5);if(context.evaluate(parsed.expression,[](){return true;}).status!=Status::Cancelled) asm volatile("udf #0");', 1),
        "expression-domain": ('using namespace Lefony::Expression;Context context;auto parsed=context.parse("sqrt(-1)",8);if(context.evaluate(parsed.expression).status!=Status::Domain) asm volatile("udf #0");', 1),
        "expression-math": ('using namespace Lefony::Expression;Context context;context.angle(Lefony::Math::Angle::Degrees);const char *text="sin(30)+log10(100)+2^0.5";auto parsed=context.parse(text,24);auto result=context.evaluate(parsed.expression);if(parsed.status!=Status::Ok || result.status!=Status::Ok || Lefony::Numeric::abs(result.value-(2.5+Lefony::Math::sqrt(2)))>1e-12) asm volatile("udf #0");', 1),
        "input-snapshot": ('Lefony::InputSnapshot input;if(Lefony::readInput(input)!=0 || !input.sequence || input.event || input.contactCount || input.textBytes) asm volatile("udf #0");', 1),
        "input-readonly": ('if(Lefony::service(8,reinterpret_cast<void *>(0x10000000))!=-4) asm volatile("udf #0");', 1),
        "input-short": ('Lefony::InputSnapshot input;input.size=124;if(Lefony::readInput(input)!=-4) asm volatile("udf #0");', 1),
        "input-reserved": ('Lefony::InputSnapshot input;input.reserved=1;if(Lefony::readInput(input)!=-4) asm volatile("udf #0");', 1),
        "navigation": ('if(Lefony::navigationDepth(8)!=0 || Lefony::navigationDepth(9)!=-4 || Lefony::navigationDepth(0)!=0) asm volatile("udf #0");', 1),
        "navigation-pointer": ('if(Lefony::service(9,reinterpret_cast<void *>(0x82000000))!=-4) asm volatile("udf #0");', 1),
        "navigation-reserved": ('Lefony::NavigationRequest request{16,1,1,0};if(Lefony::service(9,&request)!=-4) asm volatile("udf #0");', 1),
        "stack-overflow": ('volatile char large[70000];for(unsigned i=0;i<sizeof(large);i++) large[i]=static_cast<char>(i);', -14),
        "batch-flood": ('Lefony::Rect r={0,0,320,240,0};while(true) Lefony::batch(&r,1);', -2),
    }
    results = []
    out = ROOT/"build/sdk-qualification"
    out.mkdir(parents=True, exist_ok=True)
    for name, (body, expected) in cases.items():
        with tempfile.TemporaryDirectory(prefix="lf-app-test-", dir="/tmp") as folder:
            project = Path(folder)
            (project/"src").mkdir()
            (project/"app.json").write_text(json.dumps({"abi":0,"id":name,"name":name,"version":"0.1.0","license":"CC-BY-NC-SA-4.0"}))
            (project/"src/main.cpp").write_text('#include <lefony/app.h>\n#include <lefony/extensions.h>\n#include <lefony/runtime.h>\n#include <lefony/numeric.h>\n#include <lefony/memory.h>\n#include <lefony/expression.h>\n#include <lefony/input.h>\nextern "C" void lefony_event(Lefony::Event,uint32_t,uint32_t) {'+body+'}\n')
            result = exercise(package(project),args.qemu.resolve(),args.elf.resolve(),capture=out/f"{name}.ppm")
            assert result["result"] == expected, (name,result,expected)
            if name in ('batch-area','batch-overflow','batch-pointer','batch-count'):
                from PIL import Image
                with Image.open(out/f"{name}.ppm") as frame:
                    assert frame.convert('RGB').getpixel((10,10))==(255,255,255),'rejected batch drew partial content'
            results.append(result)
            print(name, result["result"], "OS responsive", flush=True)
    (out/"results.json").write_text(json.dumps(results,indent=2)+"\n")


if __name__ == "__main__":
    main()
