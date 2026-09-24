/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <lefony/text.h>
#include <lefony/foreground.h>
#include <string.h>
#define check(good) do {if(!(good)) lefony_program_exit(__LINE__);} while(0)
static void rejected(LefonyTextRequest r,int expected) {
  LefonyTextRequest before=r;check(lefony_typography(&r)==expected);check(!memcmp(&r,&before,sizeof(r)));
}
static LefonyTextRequest draw(const char *text,unsigned bytes,unsigned font,int y) {
  LefonyTextRequest r=lefony_text_request(LEFONY_TEXT_DRAW,font,text,bytes);
  r.x=12;r.y=y;r.clipWidth=320;r.clipHeight=240;r.foreground=0x1947;r.background=0xffff;return r;
}
int main(int argc,char **argv) {
  check(argc==2);
  LefonyTextRequest r=lefony_text_request(LEFONY_TEXT_MEASURE,0,"abc",3);
  if(!strcmp(argv[1],"denied") || !strcmp(argv[1],"unsupported")) {
    rejected(r,!strcmp(argv[1],"denied")?-4:-3);return 0;
  }
  check(lefony_fill((lefony_rect_t){0,0,320,240,0xffff})==0);
  for(unsigned font=0;font<4;font++) {
    r=lefony_text_request(LEFONY_TEXT_MEASURE,font,"abc",3);check(lefony_typography(&r)==0);
    check(r.width==3*r.glyphWidth && r.height==r.glyphHeight);
    check(r.glyphWidth==((font&1)?10u:7u) && r.glyphHeight==((font&1)?18u:14u));
    r=draw("Cafe\xcc\x81 \xcf\x80 = 3.14",16,font,16+font*28);check(lefony_typography(&r)==0 && !r.flags);
  }
  r=lefony_text_request(LEFONY_TEXT_MEASURE,0,"e\xcc\x81",3);check(lefony_typography(&r)==0 && r.width==7);
  r=lefony_text_request(LEFONY_TEXT_MEASURE,1,NULL,0);check(lefony_typography(&r)==0 && !r.width && r.height==18);
  char longest[256];memset(longest,'A',sizeof(longest));r=lefony_text_request(LEFONY_TEXT_MEASURE,1,longest,sizeof(longest));
  check(lefony_typography(&r)==0 && r.width==2560);
  r=draw("CLIPPING IN ALL DIRECTIONS",25,1,148);r.x=-4;r.clipX=20;r.clipY=152;r.clipWidth=80;r.clipHeight=8;
  check(lefony_typography(&r)==0 && r.flags==LEFONY_TEXT_CLIPPED);
  if(!strcmp(argv[1],"baseline")) return 0;
  const char *bad[]={"\xc0\x80","\xed\xa0\x80","\xf4\x90\x80\x80","\xe2\x82","\x80","a\n","a\t","\xcc\x81"};
  for(unsigned i=0;i<sizeof(bad)/sizeof(*bad);i++) rejected(draw(bad[i],strlen(bad[i]),0,180),-4);
  rejected(draw("a\0b",3,0,180),-4);
  rejected(draw("\xf0\x9f\x98\x80",4,0,180),-5);
  r=draw("abc",3,0,180);r.text=0;rejected(r,-4);
  r.text=0x82000000u;rejected(r,-4);r.text=0xffffffffu;rejected(r,-4);
  r=draw("abc",257,0,180);rejected(r,-4);
  r=draw("abc",3,0,180);r.clipWidth=321;rejected(r,-4);r.clipWidth=320;r.clipX=-1;rejected(r,-4);
  r=draw("abc",3,0,180);r.x=4097;rejected(r,-4);r.x=-4097;rejected(r,-4);
  r=draw("abc",3,4,180);rejected(r,-4);r.font=0;r.width=1;rejected(r,-4);
  r=draw("abc",3,0,180);r.foreground=65536;rejected(r,-4);
  r=lefony_text_request(LEFONY_TEXT_MEASURE,0,"abc",3);r.x=1;rejected(r,-4);
  check(lefony_typography(NULL)==-4);
  check(lefony_service(LEFONY_TEXT_SERVICE,(void *)0x82000000u)==-4);
  static const LefonyTextRequest readonly={80,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
  check(lefony_service(LEFONY_TEXT_SERVICE,&readonly)==-4);
  return 0;
}
