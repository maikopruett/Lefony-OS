#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the same high-precision fixture corpus in a protected ARM app."""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
sys.path.insert(0, str(ROOT / 'tests'))
from cli import package
from runner import exercise
from sdk_math_vectors import cpp, vectors


def main():
    with tempfile.TemporaryDirectory(prefix='sdk-math-') as folder:
        project=Path(folder);(project/'src').mkdir()
        (project/'src/linear_cases.h').write_text((ROOT/'tests/native/sdk_linear_cases.h').read_text())
        source=cpp(arm=True).replace('#include <lefony/app.h>', '#include <lefony/app.h>\n#include "linear_cases.h"')
        source=source.replace('!testMath()', '(!testMath() || !LinearTests::test())')
        (project/'src/main.cpp').write_text(source)
        (project/'app.json').write_text(json.dumps({'abi':1,'id':'math-qualification','name':'Math qualification',
                                                  'version':'0.1.0','license':'CC-BY-NC-SA-4.0'}))
        result=exercise(package(project),ROOT/'build/qemu-prime-g2/qemu-system-arm',ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
        result['numeric_cases']=len(vectors());result['oracle']='mpmath 1.3.0 / 400 decimal digits'
        result['linear_algebra']={'systems':120,'dimensions':[1,2,3,4,8,16],
                                  'cases':['solve','inverse','multiply','transpose','alias','singular','nonfinite','overflow','cancel_each_checkpoint']}
        result['build']=json.loads((project/'build/build.json').read_text())
        (ROOT/'build/sdk-math-arm.json').write_text(json.dumps(result,indent=2)+'\n')
        assert result['result']==1 and result['os_responsive'], result
        print(f"PASS: {len(vectors())} high-precision math cases, 120 matrix systems, helper/domain checks, ARM deadline and OS recovery")


if __name__=='__main__':
    main()
