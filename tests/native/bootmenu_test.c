/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "menu.h"
#include "preferences.h"
static unsigned saves,chosen;static int fail_save;
static int save(void *ctx,unsigned os) {(void)ctx;saves++;chosen=os;return fail_save;}
static void key(struct lf_menu *m,uint32_t t,unsigned k) {lf_menu_step(m,t,k);lf_menu_step(m,t+30,k);lf_menu_step(m,t+40,0);lf_menu_step(m,t+70,0);}
static void open(struct lf_menu *m) {lf_menu_init(m,0,0,1,1,save,NULL);lf_menu_step(m,10,LF_ENTER);lf_menu_step(m,100,0);lf_menu_step(m,130,0);}
static unsigned char media[2][LF_PREF_BYTES];static int fail_at=-1,reads_fail;
static int rd(void *ctx,unsigned slot,uint8_t *b) {(void)ctx;if(reads_fail)return -1;memcpy(b,media[slot],LF_PREF_BYTES);return 0;}
static int wr(void *ctx,unsigned slot,const uint8_t *b) {(void)ctx;memset(media[slot],255,LF_PREF_BYTES);if(fail_at<0)memcpy(media[slot],b,LF_PREF_BYTES);else memcpy(media[slot],b,fail_at);return fail_at<0?0:-1;}
int main(int argc,char **argv) {
    struct lf_menu m;struct lf_preference p;struct lf_pref_io io={NULL,rd,wr};unsigned i;
    uint32_t pixels[320*240];FILE *f;
    lf_menu_init(&m,100,0,1,1,save,NULL);
    lf_menu_step(&m,3099,LF_UP);assert(m.screen==LF_COUNTDOWN);
    lf_menu_touch(&m,3099,1,0,70,80);assert(m.screen==LF_COUNTDOWN);
    lf_menu_step(&m,3100,0);assert(m.screen==LF_BOOT && m.boot_os==0 && saves==0);
    lf_menu_init(&m,0,0,1,1,save,NULL);lf_menu_step(&m,3000,LF_ENTER);assert(m.screen==LF_MENU);
    for(i=0;i<100;i++)lf_menu_step(&m,3100+i*100,LF_ENTER);
    assert(m.screen==LF_MENU);lf_menu_step(&m,20000,0);lf_menu_step(&m,20030,0);
    key(&m,20100,LF_ENTER);assert(m.screen==LF_BOOT);
    /* Every physical arrow navigates every menu without activating it. */
    for(i=LF_MENU;i<=LF_RECOVERY_CONFIRM;i++) {
        unsigned count=i==LF_MENU?4:2;
        open(&m);m.screen=i;
        key(&m,200,LF_DOWN);assert(m.screen==i && m.selected==1);
        key(&m,300,LF_UP);assert(m.screen==i && m.selected==0);
        key(&m,400,LF_LEFT);assert(m.screen==i && m.selected==0);
        key(&m,500,LF_RIGHT);assert(m.screen==i && m.selected==1);
        key(&m,600,LF_LEFT|LF_RIGHT);assert(m.screen==i && m.selected==1);
        key(&m,700,LF_LEFT);assert(m.selected==0);
        lf_menu_step(&m,800,LF_DOWN);lf_menu_step(&m,830,LF_DOWN);
        lf_menu_step(&m,3000,LF_DOWN);assert(m.selected==1 && m.screen==i);
        lf_menu_step(&m,3100,0);lf_menu_step(&m,3130,0);
        for(unsigned j=0;j<5;j++) key(&m,3200+j*100,LF_DOWN);
        assert(m.screen==i && m.selected==count-1);
        for(unsigned j=0;j<5;j++) key(&m,4000+j*100,LF_UP);
        assert(m.screen==i && m.selected==0);
    }
    lf_menu_init(&m,0,0,1,1,save,NULL);
    key(&m,100,LF_UP);key(&m,200,LF_DOWN);key(&m,300,LF_LEFT);key(&m,400,LF_RIGHT);
    assert(m.screen==LF_COUNTDOWN);lf_menu_step(&m,3000,0);assert(m.screen==LF_BOOT);
    open(&m);key(&m,200,LF_DOWN);key(&m,300,LF_ENTER);assert(m.screen==LF_MENU && m.notice==LF_UNAVAILABLE);
    key(&m,400,LF_DOWN);key(&m,500,LF_ENTER);assert(m.screen==LF_PRIORITY);
    key(&m,600,LF_ENTER);assert(m.screen==LF_MENU && m.notice==LF_SAVED && saves==1 && chosen==0);
    open(&m);key(&m,200,LF_DOWN);key(&m,300,LF_DOWN);key(&m,400,LF_DOWN);
    key(&m,500,LF_ENTER);assert(m.screen==LF_RECOVERY_CONFIRM && m.selected==0);
    key(&m,600,LF_ENTER);assert(m.screen==LF_MENU);
    open(&m);key(&m,200,LF_DOWN);key(&m,300,LF_DOWN);key(&m,400,LF_DOWN);
    key(&m,500,LF_ENTER);key(&m,600,LF_DOWN);key(&m,700,LF_ENTER);assert(m.screen==LF_RECOVERY);
    open(&m);lf_menu_touch(&m,200,0,0,0,0);lf_menu_touch(&m,220,1,3,50,80);lf_menu_touch(&m,240,0,0,0,0);assert(m.screen==LF_BOOT);
    open(&m);lf_menu_touch(&m,200,0,0,0,0);lf_menu_touch(&m,220,1,3,50,80);lf_menu_touch(&m,230,1,3,50,150);lf_menu_touch(&m,240,0,0,0,0);assert(m.screen==LF_MENU);
    open(&m);lf_menu_touch(&m,200,0,0,0,0);lf_menu_touch(&m,220,1,3,50,80);lf_menu_touch(&m,230,-1,0,0,0);lf_menu_touch(&m,240,0,0,0,0);assert(m.screen==LF_MENU);
    lf_menu_init(&m,0,1,1,3,save,NULL);lf_menu_step(&m,3000,0);assert(m.screen==LF_BOOT && m.boot_os==1);
    lf_menu_init(&m,0,1,1,1,save,NULL);assert(m.screen==LF_MENU && m.notice==LF_BAD_PREF);
    lf_menu_init(&m,UINT32_MAX-1000,0,1,1,save,NULL);lf_menu_step(&m,1998,0);assert(m.screen==LF_COUNTDOWN);lf_menu_step(&m,1999,0);assert(m.screen==LF_BOOT);
    lf_menu_boot_failed(&m);assert(m.screen==LF_MENU && !m.available && m.notice==LF_BAD_IMAGE);
    memset(media,255,sizeof(media));assert(lf_pref_load(&io,&p));assert(lf_pref_save(&io,0));
    lf_pref_encode(media[0],1,0);assert(!lf_pref_load(&io,&p)&&p.priority==0);
    for(i=0;i<LF_PREF_BYTES;i++) {
        lf_pref_encode(media[0],1,0);memset(media[1],255,LF_PREF_BYTES);fail_at=i;
        assert(lf_pref_save(&io,1));assert(!lf_pref_load(&io,&p)&&p.priority==0);
    }
    fail_at=-1;assert(!lf_pref_save(&io,1));assert(!lf_pref_load(&io,&p)&&p.priority==1&&p.generation==2);
    media[p.slot][60]^=1;assert(!lf_pref_load(&io,&p)&&p.priority==0);
    lf_pref_encode(media[0],UINT32_MAX,0);assert(lf_pref_save(&io,1));
    lf_pref_encode(media[0],8,0);lf_pref_encode(media[1],8,1);assert(lf_pref_load(&io,&p));assert(lf_pref_save(&io,0));
    reads_fail=1;assert(lf_pref_load(&io,&p));assert(lf_pref_save(&io,0));reads_fail=0;
    if(argc==2) {
        const char *names[]={"countdown","menu","priority","recovery"};char path[1024];unsigned n;
        for(n=0;n<4;n++) {
            lf_menu_init(&m,0,0,1,1,save,NULL);m.screen=n==0?LF_COUNTDOWN:n==1?LF_MENU:n==2?LF_PRIORITY:LF_RECOVERY_CONFIRM;
            lf_menu_draw(&m,700,pixels);snprintf(path,sizeof(path),"%s/%s.ppm",argv[1],names[n]);f=fopen(path,"wb");assert(f);fprintf(f,"P6\n320 240\n255\n");
            for(i=0;i<320*240;i++) {fputc(pixels[i]>>16,f);fputc(pixels[i]>>8,f);fputc(pixels[i],f);}fclose(f);
        }
    }
    puts("PASS: countdown, physical-key policy, touch capture, priority and 64 torn writes");return 0;
}
