#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R0 real-ARM newlib allocation/formatting/error proof; no file-support claim."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import write_json
from runner import exercise


def main():
    from sdk_newlib_probe import compile_probe
    output = ROOT / 'build/sdk-libc-qualification'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lefony-libc-') as directory:
        app, build = compile_probe(Path(directory),'sdk/experiments/newlib_probe.c')
        result = exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',
                          ROOT/'dist/lefony-os-prime-g2-vm-native.elf',capture=output/'probe.ppm')
        assert result['result']==1 and result['os_responsive'],result
        from PIL import Image
        with Image.open(output/'probe.ppm') as frame:
            assert frame.convert('RGB').getpixel((20,20))==(33,166,66)
        write_json(output/'report.json',{'schema':1,'status':'passed','validation':'developer-local',
                   'profile':'R0 newlib allocation/formatting/parse/math; OS files explicitly unsupported',
                   **build,'runtime':result,'physical':'not_tested'})
    print('PASS: ARM newlib allocation, exhaustion, realloc preservation, formatting, parsing, sort/search, math and explicit unsupported-file errors')


if __name__=='__main__':
    main()
