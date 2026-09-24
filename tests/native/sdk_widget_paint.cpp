// SPDX-License-Identifier: GPL-3.0-or-later
#include <lefony/ui_widgets.h>
#include <lefony/foreground.h>
#include <stdlib.h>
#include <string.h>
using namespace Lefony;
using namespace Lefony::UI;
namespace {
constexpr Box clips[]={{0,0,320,240},{83,82,133,41},{0,0,100,240},{130,0,190,240},{0,108,320,132},{91,111,94,3},{0,0,0,0}};
int paint(unsigned kind,unsigned page) {
  lefony_fill({0,0,320,240,0x1234});Widgets ui({},clips[page]);Box box{60,70,200,80};
  TextBuffer<1024> text;char content[1024];memset(content,'a',1023);memcpy(content+1020,"END",3);content[1023]=0;text.set(content,1023);
  ListModel list;list.layout(box,30);list.count(10);list.select(4);
  inspectionBegin();int expectedError=0;
  switch(kind) {
    case 0:ui.label(1,box,"Cafe\xcc\x81 \xcf\x80",LEFONY_FONT_LARGE,LEFONY_UI_HERE);break;
    case 1:ui.button(1,box,"Button for clipping",Enabled|Focused|Pressed,LEFONY_UI_HERE);break;
    case 2:ui.row(1,box,"Original row","second line",Enabled|Focused|Selected,LEFONY_UI_HERE);break;
    case 3:ui.choice(1,box,"Choice label",true,Enabled|Focused|Pressed,LEFONY_UI_HERE);break;
    case 4:ui.progress(1,box,63,100,LEFONY_UI_HERE);break;
    case 5:ui.slider(1,box,50,100,Enabled|Focused|Pressed,LEFONY_UI_HERE);break;
    case 6:ui.field(1,box,text,Enabled|Focused|Invalid,LEFONY_UI_HERE);break;
    case 7:ui.scrollbar(1,box,list,LEFONY_UI_HERE);break;
    case 8:ui.dialog(1,DialogLayout{},"Original confirmation",2,"Continue",Enabled,3,"Cancel",Enabled|Focused,LEFONY_UI_HERE);break;
    case 9: {
      MenuModel<8> menu;menu.layout(box);menu.add(10,"First action");menu.add(11,"Unavailable",false);menu.add(12,"Last partially clipped action");
      ui.menu(1,menu,"No actions",LEFONY_UI_HERE);break;
    }
    case 10: {
      content[26]=0;memcpy(content+23,"END",3);text.set(content,26);
      ui.field(1,box,text,Enabled|Focused|Invalid,LEFONY_UI_HERE);break;
    }
    case 11: {
      MenuModel<8> menu;menu.layout(box);ui.menu(1,menu,"No actions",LEFONY_UI_HERE);break;
    }
    case 12: {
      box={INT32_MIN+99,INT32_MIN+100,INT32_MAX,INT32_MAX};
      list.layout({0,0,320,80},32767);list.count(UINT32_MAX);list.select(UINT32_MAX-2);
      ui.scrollbar(1,box,list,LEFONY_UI_HERE);break;
    }
    case 13:case 14:case 15:case 16: {
      auto result=ui.paragraph(1,box,"Cafe\xcc\x81 \xcf\x80: words wrap at spaces.\n\nA_very_long_word_without_spaces_and_more.",
        kind-13,LEFONY_UI_HERE,kind==15?NoState:kind==16?Enabled|Invalid:Enabled);
      if(!result.lines || !result.height || result.error) return -101;
      break;
    }
    case 17: {
      // Validate unsupported glyphs even after all visible lines are filled.
      memcpy(content+1019,"\xf0\x9f\x98\x80",4);
      auto result=ui.paragraph(1,box,content,LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      if(result.error!=-5) return -102;
      expectedError=-5;break;
    }
    case 18: {
      content[1022]=static_cast<char>(0xff);
      auto result=ui.paragraph(1,box,content,LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      if(result.error!=-4) return -103;
      expectedError=-4;break;
    }
    case 19: {
      content[0]='e';for(unsigned i=1;i<259;i+=2) {content[i]=static_cast<char>(0xcc);content[i+1]=static_cast<char>(0x81);}content[259]=0;
      auto result=ui.paragraph(1,box,content,LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      if(result.error!=-4) return -104;
      expectedError=-4;break;
    }
    case 20: {
      auto result=ui.paragraph(1,{60,70,3,30},"abc",LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      if(result.error || !result.clipped || result.lines!=3 || result.height!=46) return -105;
      break;
    }
    case 21: {
      auto result=ui.paragraph(1,box,"",LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      if(result.error || result.lines || result.height) return -106;
      break;
    }
    case 22: {
      auto result=ui.paragraph(1,box,"Invalid spacing",LEFONY_FONT_SMALL,LEFONY_UI_HERE,Enabled,33);
      if(result.error!=-4) return -107;
      expectedError=-4;break;
    }
    case 23:case 24: {
      if(kind==24) box={-1000,70,2000,80};
      auto result=ui.paragraph(1,box,content,LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      unsigned lines=kind==23?37:4;
      if(result.error || result.lines!=lines || result.height!=lines*16-2 || !result.clipped) return -109;
      break;
    }
    default:return -100;
  }
  // A visible stage marker acknowledges normal input in both build profiles.
  // It is outside the tested control and excluded from the pixel oracle.
  char stage[]="0";stage[0]+=page;
  inspectNode(900,Custom,{0,238,2,2},{0,238,2,2},Enabled,stage,LEFONY_UI_HERE);
  inspectionEnd();lefony_fill({0,238,2,2,page%2?0x07e0u:0xf800u});
  return ui.error()==expectedError?0:ui.error()?ui.error():-108;
}
}
int main(int argc,char **argv) {
  if(argc!=2) return 1;
  unsigned kind=static_cast<unsigned>(atoi(argv[1])),page=0;uint32_t sequence=0;
  if(int error=paint(kind,page)) return 2000-error;
  for(;;) {
    InputSnapshot input;
    if(readInput(input)==0 && input.sequence!=sequence) {
      sequence=input.sequence;
      if(input.event==1 && input.key==InputKey::Confirm) {
        page=(page+1)%7;if(int error=paint(kind,page)) return 2000-error;
      }
    }
    lefony_program_yield();
  }
}
