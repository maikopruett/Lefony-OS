#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ordinary C/C++ ARM programs qualify formatting and explicit angle contexts."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from cli import package
from replay import Controls
from runner import exercise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-notebook-system/math')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm';sdk_identity=identity(ROOT/'sdk');cases=[]
    with tempfile.TemporaryDirectory(prefix='Notebook math ARM é ') as temp:
        for name,language in [('sdk_number_format','c'),('sdk_notebook_math','cpp')]:
            project=Path(temp)/name;(project/'src').mkdir(parents=True)
            source=ROOT/f'tests/native/{name}.{language}';shutil.copyfile(source,project/f'src/main.{language}')
            write_json(project/'app.json',{'schema':1,'abi':1,'id':'notebook-math','name':'Notebook math','version':'1.0.0',
                'license':'CC-BY-NC-SA-4.0','minimum_api':3,'required_capabilities':16,'optional_capabilities':0,'data_schema':0})
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':[f'src/main.{language}']})
            for profile in ('debug','release'):
                folder=output/(name+'-'+profile);folder.mkdir(exist_ok=True);records=[]
                artifact=package(project,profile)
                for item in ('app-debug.elf','build.json',artifact.name):shutil.copyfile(project/'build'/item,folder/item)
                def controls(channel):
                    normal=Controls(channel,folder)
                    try:normal.run({'steps':[{'program_exit':0}]},records)
                    finally:normal.close()
                result=exercise(artifact,qemu,args.firmware,controls=controls)
                assert result['result']==1 and result['os_responsive'],result
                cases.append({'name':name,'profile':profile,'source_sha256':digest(source),'runtime':result,'steps':records,
                    'build':json.loads((folder/'build.json').read_text())})
                print('PASS:',name,profile,flush=True)
    assert sdk_identity==identity(ROOT/'sdk'),'SDK changed during qualification'
    write_json(output/'report.json',{'schema':1,'status':'passed','sdk_sha256':sdk_identity,'cases':cases,
        'firmware_sha256':digest(args.firmware),'qemu_sha256':digest(qemu),'physical':'not_tested',
        'format_cases':20,'angle_expression_cases':10})


if __name__=='__main__':main()
