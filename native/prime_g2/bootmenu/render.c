/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "menu.h"
#include "font.h"
#define BG 0xFAFBF8u
#define INK 0x183D30u
#define GREEN 0x27764Du
#define MUTED 0x64766Cu
#define PALE 0xE8F0E8u
#define LINE 0xDCE5DDu
#define DISABLED 0x8B968Fu
static uint32_t *fb;
static void rect(int x,int y,int w,int h,uint32_t c) {
    int xx,yy; for(yy=y; yy<y+h && yy<240; yy++) for(xx=x;xx<x+w && xx<320;xx++)
        if(xx>=0 && yy>=0) fb[yy*320+xx]=c;
}
static void roundrect(int x,int y,int w,int h,uint32_t c) {
    rect(x+3,y,w-6,h,c); rect(x+1,y+1,w-2,h-2,c);rect(x,y+3,w,h-6,c);
}
static uint32_t blend(uint32_t a,uint32_t b,unsigned v) {
    unsigned r=(((a>>16)&255)*v+((b>>16)&255)*(15-v)+7)/15;
    unsigned g=(((a>>8)&255)*v+((b>>8)&255)*(15-v)+7)/15;
    unsigned bl=((a&255)*v+(b&255)*(15-v)+7)/15;return r<<16|g<<8|bl;
}
static int text_width(const char *s,int size) {
    const struct lf_glyph *g=size==28?lf_glyph_28:size==16?lf_glyph_16:lf_glyph_12;int w=0;
    while(*s) { unsigned c=(unsigned char)*s++; if(c>=32 && c<127) w+=g[c-32].advance; }return w;
}
static void text(int x,int y,const char *s,int size,uint32_t color) {
    const struct lf_glyph *g=size==28?lf_glyph_28:size==16?lf_glyph_16:lf_glyph_12;
    const unsigned char *f=size==28?lf_font_28:size==16?lf_font_16:lf_font_12;
    while(*s) {
        unsigned c=(unsigned char)*s++,i,j;if(c<32 || c>=127)continue;c-=32;
        for(j=0;j<(unsigned)size+6;j++)for(i=0;i<g[c].width;i++) {
            unsigned n=j*g[c].width+i,v=f[g[c].offset+n/2];v=(n&1)?v&15:v>>4;
            if(v && x+(int)i>=0 && x+(int)i<320 && y+(int)j>=0 && y+(int)j<240) {
                uint32_t *p=fb+(y+j)*320+x+i;*p=blend(color,*p,v);
            }
        }
        x+=g[c].advance;
    }
}
static void center(int y,const char *s,int size,uint32_t color) {text((320-text_width(s,size))/2,y,s,size,color);}
static void title(const char *s) {text(20,21,s,16,GREEN);rect(20,49,280,1,LINE);}
static void button(int x,int y,int w,const char *s,int selected) {
    roundrect(x,y,w,28,selected?GREEN:PALE);
    text(x+(w-text_width(s,12))/2,y+5,s,12,selected?0xFFFFFF:INK);
}
static const char *notice(enum lf_notice n) {
    switch(n) {
    case LF_UNAVAILABLE:return "The selected OS is unavailable.";
    case LF_SAVED:return "Priority saved.";
    case LF_SAVE_FAILED:return "Could not save. Previous priority retained.";
    case LF_BAD_IMAGE:return "Image unavailable. Choose recovery.";
    case LF_BAD_PREF:return "Priority unavailable. Choose an OS.";
    default:return "Arrows to choose  |  Enter to select";
    }
}
void lf_menu_draw(const struct lf_menu *m,uint32_t now,uint32_t *pixels) {
    unsigned i; fb=pixels;rect(0,0,320,240,BG);
    if(m->screen==LF_COUNTDOWN || m->screen==LF_BOOT) {
        unsigned elapsed=now-m->start,left=elapsed<3000?3000-elapsed:0;
        unsigned os=m->screen==LF_BOOT?m->boot_os:m->priority;
        center(94,os==LF_HP?"Starting HP OS":"Starting Lefony OS",16,INK);
        if(m->screen==LF_COUNTDOWN) {
            roundrect(80,137,160,3,LINE);rect(80,137,(int)(160*left/3000),3,GREEN);
            center(168,"Press Enter for boot options",12,MUTED);
        } else center(137,"Please wait",12,MUTED);
        return;
    }
    if(m->screen==LF_RECOVERY_CONFIRM || m->screen==LF_RECOVERY) {
        title("RECOVERY");
        center(82,"Connect to your computer",16,INK);
        center(111,"Rear RESET returns to normal startup.",12,MUTED);
        center(128,"Recovery times out after three minutes.",12,MUTED);
        if(m->screen==LF_RECOVERY_CONFIRM) {
            button(20,158,136,"Cancel",m->selected==0);
            button(164,158,136,"Enter recovery",m->selected==1);
        }else center(170,"Waiting for connection",16,GREEN);
        return;
    }
    title(m->screen==LF_PRIORITY?"SET PRIORITY OS":"BOOT OPTIONS");
    for(i=0;i<2;i++) {
        int y=64+58*i,enabled=(m->available&(1u<<i))!=0,selected=m->selected==i;
        uint32_t bg=selected&&enabled?GREEN:enabled?PALE:0xF0F2EE;
        roundrect(20,y,280,50,bg);
        if(selected&&!enabled) {rect(20,y+5,2,40,DISABLED);}
        text(34,y+5,i?"HP OS":"Lefony OS",16,!enabled?DISABLED:selected?0xFFFFFF:INK);
        text(34,y+28,!enabled?(i?"Unavailable until HP integration is complete":"Image unavailable"):
             m->screen==LF_PRIORITY?"Use for automatic startup":m->priority==i?"Priority OS":"Boot once",12,
             !enabled?DISABLED:selected?0xDCECDF:MUTED);
        if(enabled)text(280,y+13,">",16,selected?0xFFFFFF:GREEN);
    }
    if(m->screen==LF_MENU) {
        button(20,184,136,"Set priority OS",m->selected==2);
        button(164,184,136,"Recovery",m->selected==3);
    } else center(188,"Enter to save  |  Esc to return",12,MUTED);
    center(220,notice(m->notice),12,MUTED);
}
