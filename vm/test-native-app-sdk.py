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
    }
    results = []
    out = ROOT/"build/sdk-qualification"
    out.mkdir(parents=True, exist_ok=True)
    for name, (body, expected) in cases.items():
        with tempfile.TemporaryDirectory(prefix="lf-app-test-", dir="/tmp") as folder:
            project = Path(folder)
            (project/"src").mkdir()
            (project/"app.json").write_text(json.dumps({"abi":0,"id":name,"name":name,"version":"0.1.0","license":"CC-BY-NC-SA-4.0"}))
            (project/"src/main.cpp").write_text('#include <lefony/app.h>\nextern "C" void lefony_event(Lefony::Event,uint32_t,uint32_t) {'+body+'}\n')
            result = exercise(package(project),args.qemu.resolve(),args.elf.resolve(),capture=out/f"{name}.ppm")
            assert result["result"] == expected, (name,result,expected)
            results.append(result)
            print(name, result["result"], "OS responsive", flush=True)
    (out/"results.json").write_text(json.dumps(results,indent=2)+"\n")


if __name__ == "__main__":
    main()
