#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate copied input snapshots through normal KPP/Goodix dispatch."""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from cli import package
from replay import test_project
from workspace import opened

SOURCE = r'''
#include <lefony/input.h>
#include <lefony/expression_input.h>
void check(bool good) { if(!good) asm volatile("udf #0"); }
void mark(int x,int y) { Lefony::fill({x,y,20,20,Lefony::Green}); }
extern "C" void lefony_event(Lefony::Event event,uint32_t first,uint32_t) {
  Lefony::InputSnapshot input;check(Lefony::readInput(input)==0);
  check(input.size==128 && input.version==1 && input.sequence && input.event==static_cast<uint32_t>(event));
  for(auto reserved:input.reservedOutput) check(!reserved);
  if(event==Lefony::Event::Start) Lefony::fill({0,0,320,240,Lefony::White});
  if(event==Lefony::Event::Key) {
    if(input.key==static_cast<Lefony::InputKey>(18)) {
      check(first==18 && input.physicalKey==55 && !input.modifiers && input.textBytes==1 && input.text[0]=='2');mark(0,0);
    }
    if(input.key==Lefony::InputKey::Plus) {
      check(first==0 && input.physicalKey==13 && input.textBytes==1 && input.text[0]=='+');mark(25,0);
    }
    if(input.key==Lefony::InputKey::Sqrt) {
      check(first==0 && input.physicalKey==25 && (input.modifiers&Lefony::InputShift));mark(50,0);
    }
    if(input.key==Lefony::InputKey::Sin || input.key==Lefony::InputKey::Asin || input.key==Lefony::InputKey::Log) {
      Lefony::UI::TextBuffer<16> buffer;check(Lefony::Expression::edit(buffer,input));
      if(input.key==Lefony::InputKey::Sin) { check(buffer.size()==4 && buffer.text()[0]=='s');mark(75,0); }
      if(input.key==Lefony::InputKey::Asin) { check(buffer.size()==5 && buffer.text()[0]=='a' && (input.modifiers&Lefony::InputShift));mark(100,0); }
      if(input.key==Lefony::InputKey::Log) { check(buffer.size()==6 && buffer.text()[3]=='1' && buffer.text()[4]=='0');mark(125,0); }
    }
    check(Lefony::validInputText(input.text,input.textBytes));
  }
  if(event==Lefony::Event::Touch) {
    check(input.textBytes==0 && input.key==Lefony::InputKey::Unknown);
    if(input.touchPhase==0 && input.contactCount==1 && input.contacts[0].id==7) {
      check(input.contacts[0].x==90 && input.contacts[0].y==110);mark(0,40);
    }
    if(input.contactCount==2) {
      check(input.contacts[0].id==2 && input.contacts[1].id==7);
      if(input.flags&Lefony::ContactsChanged) {
        check(input.contacts[0].x==200 && input.contacts[1].x==90);mark(25,40);
      } else {
        check(input.contacts[0].x==180 && input.contacts[0].y==130 && input.contacts[1].x==100);mark(25,65);
      }
    }
    if(input.touchPhase==1 && input.contactCount==1 && (input.flags&Lefony::ContactsChanged)) {
      check(input.contacts[0].id==2 && input.contacts[1].id==0 && input.contacts[1].x==0);mark(50,40);
    }
    if(input.touchPhase==3) { check(input.contactCount==0);mark(75,40); }
    if(input.touchPhase==2) { check(input.contactCount==0 && input.contacts[0].id==3);mark(100,40); }
  }
}
'''


def main():
    evidence = ROOT / 'build/sdk-input'
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sdk-input-') as folder:
        project = Path(folder)
        (project / 'src').mkdir(); (project / 'tests').mkdir()
        (project / 'src/main.cpp').write_text(SOURCE)
        (project / 'app.json').write_text(json.dumps({'abi': 1, 'id': 'input-contract', 'name': 'Input Contract',
                                                    'version': '0.1.0', 'license': 'CC-BY-NC-SA-4.0'}))
        steps = [{'key': 'two'}, {'key': 'plus'}, {'key': 'shift'}, {'key': 'square'},
                 {'key': 'sin'}, {'key': 'shift'}, {'key': 'sin'}, {'key': 'log'},
                 {'touch': [[7,90,110]]}, {'touch': [[7,90,110],[2,200,120]]},
                 {'touch': [[2,180,130],[7,100,110]]}, {'touch': [[2,180,130]]},
                 {'touch': [[9,10,90]]}, {'touch': []}, {'touch': [[3,110,120]]},
                 {'touch': []}, {'capture': 'input'}]
        for x,y in ((10,10),(35,10),(60,10),(85,10),(110,10),(135,10),(10,50),(35,50),(35,75),(60,50),(85,50),(110,50)):
            steps.append({'pixel': ['input',x,y,[33,166,66]]})
        steps.append({'key': 'back'})
        (project / 'tests/input.json').write_text(json.dumps({'schema': 1, 'name': 'input', 'steps': steps}))
        with opened(project, 'input') as (directory, _):
            result = test_project(project, package(project), ROOT / 'build/qemu-prime-g2/qemu-system-arm',
                                  ROOT / 'dist/lefony-os-prime-g2-vm-native.elf', 'all', directory)
        (evidence / 'report.json').write_bytes((project / 'build/run.json').read_bytes())
        assert result == 0
        (evidence / 'input.ppm').write_bytes((project / 'build/tests/input/input.ppm').read_bytes())
        print('PASS: key/text/modifier/physical positions; two stable touch IDs, reordering, contact changes, cancellation and release')


if __name__ == '__main__':
    main()
