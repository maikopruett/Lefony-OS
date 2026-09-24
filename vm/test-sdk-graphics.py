#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Public raster/plot/gesture cases and actual screen output on protected ARM."""
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
#include <lefony/ui_controls.h>
#include <lefony/graphics_screen.h>
#include "sdk_graphics_cases.h"
#include "sdk_plot_cases.h"
#include "sdk_gesture_cases.h"
void check(bool good) { if(!good) asm volatile("udf #0"); }
extern "C" void lefony_event(Lefony::Event event,uint32_t,uint32_t) {
  if(event!=Lefony::Event::Start) return;
  check(GraphicsTests::test() && PlotTests::test() && GestureTests::test());
  using namespace Lefony::Graphics;
  Lefony::fill({0,0,320,240,Lefony::White});Screen output;
  auto sink=[&](int x,int y,int width,uint16_t color) { return output.span(x,y,width,color); };
  check(line({0,0,320,240},{-200,10},{1000,10},0xf800,sink)==Status::Ok);
  check(output.flush() && output.calls()==1 && output.pixels()==320);
  check(line({0,0,320,240},{20,-100},{20,500},Lefony::Green,sink)==Status::Ok);
  check(circle({0,0,320,240},60,40,10,0x001f,sink)==Status::Ok);
  const uint8_t pixels[]={0x00,0xf8,0xe0,0x07,0x1f,0x00,0x00,0x00};
  check(image({0,0,320,240},100,20,2,2,4,pixels,8,sink,true,0xf800)==Status::Ok);
  check(output.flush());
  Screen invalid;check(!invalid.span(320,0,1,0) && invalid.error()==-1 && !invalid.flush() && invalid.calls()==0);
  Lefony::UI::Canvas canvas;
  canvas.glyph(INT32_MAX,INT32_MAX,'x',0,0);canvas.glyph(INT32_MIN,INT32_MIN,'x',0,0);
  check(canvas.error()==0);
}
'''


def main():
    evidence = ROOT / 'build/sdk-graphics'
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sdk-graphics-') as directory:
        project=Path(directory);(project/'src').mkdir();(project/'tests').mkdir()
        (project/'src/main.cpp').write_text(SOURCE)
        for name in ('sdk_graphics_cases.h','sdk_plot_cases.h','sdk_gesture_cases.h'):
            (project/'src'/name).write_bytes((ROOT/'tests/native'/name).read_bytes())
        (project/'app.json').write_text(json.dumps({'abi':1,'id':'graphics-qualification','name':'Graphics Qualification',
                                                   'version':'0.1.0','license':'CC-BY-NC-SA-4.0'}))
        steps=[{'capture':'raster'}]
        for x,y,color in ((0,10,[255,0,0]),(319,10,[255,0,0]),(20,0,[33,166,66]),(20,239,[33,166,66]),
                          (70,40,[0,0,255]),(60,30,[0,0,255]),(60,40,[255,255,255]),
                          (100,20,[255,255,255]),(101,20,[0,255,0]),(100,21,[0,0,255]),(101,21,[0,0,0])):
            steps.append({'pixel':['raster',x,y,color]})
        steps.append({'key':'back'})
        (project/'tests/raster.json').write_text(json.dumps({'schema':1,'name':'raster','steps':steps}))
        with opened(project,'raster') as (workspace,_):
            result=test_project(project,package(project),ROOT/'build/qemu-prime-g2/qemu-system-arm',
                                ROOT/'dist/lefony-os-prime-g2-vm-native.elf','all',workspace)
        (evidence/'report.json').write_bytes((project/'build/run.json').read_bytes())
        assert result==0
        (evidence/'raster.ppm').write_bytes((project/'build/tests/raster/raster.ppm').read_bytes())
        print('PASS: ARM raster clipping/buffers, adaptive sampling, gestures, coalesced batches and 11 screen-pixel assertions')


if __name__=='__main__':
    main()
