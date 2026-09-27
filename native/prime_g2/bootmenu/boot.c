/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <common.h>
#include <command.h>
#include <malloc.h>
#include <nand.h>
#include <linux/errno.h>
#include <watchdog.h>
#include <linux/libfdt.h>
#include "hardware.h"
#include "preferences.h"
#define PREF0 0x00dc0000u
#define PREF1 0x00de0000u
#define BLOCK 0x20000u
#define PAGE 2048u
/* Profile 1 is explicitly provisioned in the last two misc blocks. No startup
 * format, raw/OOB writes, bad-block skipping or implicit allocation is allowed. */
static struct mtd_info *flash;
static int geometry(void) {
    flash=get_nand_dev_by_index(0);
    return flash && flash->size==0x20000000ull && flash->erasesize==BLOCK && flash->writesize==PAGE && flash->oobsize==64;
}
static int exact_read(ulong offset,void *data,size_t len) {
    size_t got=0;int r=mtd_read(flash,offset,len,&got,data);
    return (r && r!=-EUCLEAN) || got!=len ? -1 : 0;
}
static int pref_read(void *ctx,unsigned slot,uint8_t *out) {
    u8 page[PAGE] __aligned(64);ulong off=slot?PREF1:PREF0;
    (void)ctx;
    if(slot>1 || !geometry() || nand_block_isbad(flash,off) || exact_read(off,page,PAGE))return -1;
    memcpy(out,page,LF_PREF_BYTES);return 0;
}
static int pref_replace(void *ctx,unsigned slot,const uint8_t *record) {
    u8 *block;unsigned i;ulong off=slot?PREF1:PREF0;size_t wrote=0;int result=-1;
    (void)ctx;
    if(slot>1 || !geometry() || nand_block_isbad(flash,off))return -1;
    block=memalign(64,BLOCK);if(!block)return -1;
    if(exact_read(off,block,BLOCK))goto done;
    /* Permit only an erased block or one of our provisioned records. */
    for(i=0;i<LF_PREF_BYTES;i++)if(block[i]!=0xff)break;
    if(i!=LF_PREF_BYTES && memcmp(block,"LFBP\1\0\0\0\1\0\0\0",12))goto done;
    for(i=LF_PREF_BYTES;i<BLOCK;i++)if(block[i]!=0xff)goto done;
    memset(block,0xff,PAGE);memcpy(block,record,LF_PREF_BYTES);
    if(nand_erase(flash,off,BLOCK) || mtd_write(flash,off,PAGE,&wrote,block) || wrote!=PAGE)goto done;
    result=0;
done:free(block);return result;
}
static const struct lf_pref_io preference_io={NULL,pref_read,pref_replace};
static int save_priority(void *ctx,unsigned os) {
    struct lf_preference p;(void)ctx;
    /* Provisioning is an explicit recovery operation, not a menu side effect. */
    if(os!=LF_LEFONY || lf_pref_load(&preference_io,&p))return -1;
    return lf_pref_save(&preference_io,os);
}
static int load_lefony(void) {
    u32 *image=(u32 *)0x80800000;void *dtb=(void *)0x83000000;
    size_t length=PAGE,actual=0;u32 bytes;
    if(!geometry())return -1;
    if(nand_read_skip_bad(flash,0x400000,&length,&actual,0x800000,(u8 *)image))return -1;
    /* Keep the existing zImage handoff and installer signature trust policy.
     * These are additional bounded type/size checks, not a secure-boot claim. */
    bytes=image[11];
    if(image[0]!=0xea00000e || image[9]!=0x016f2818 || image[10] || bytes<0x1100 || bytes>0x800000 || (bytes&3))return -1;
    length=ALIGN(bytes,PAGE);
    if(nand_read_skip_bad(flash,0x400000,&length,&actual,0x800000,(u8 *)image))return -1;
    if(image[0x1000/4]!=0xea000006 || image[0x1020/4]!=0xf10c00c0)return -1;
    length=0x100000;
    if(nand_read_skip_bad(flash,0xc00000,&length,&actual,0x100000,dtb) || fdt_check_header(dtb) || fdt_totalsize(dtb)>0x100000)return -1;
    flush_dcache_range((ulong)image,(ulong)image+ALIGN(bytes,64));
    return 0;
}
/* bootz from SDP also hands display ownership away, not just menu boots. */
void board_quiesce_devices(void) { lf_hw_shutdown(); }
void lefony_recovery_screen(void) {
    struct lf_menu m;
    if(lf_hw_init())return;
    lf_menu_init(&m,get_timer(0),0,1,1,NULL,NULL);m.screen=LF_RECOVERY;
    lf_hw_present(&m,get_timer(0));
}

static int do_lfboot(cmd_tbl_t *cmdtp,int flag,int argc,char * const argv[]) {
    struct lf_menu menu;struct lf_preference pref;int valid;u32 now,last=0;int drawn=-1;unsigned previous=99;enum lf_notice notice=LF_NONE;
    (void)cmdtp;(void)flag;(void)argc;(void)argv;
    if(lf_hw_init()) {puts("Lefony menu hardware unavailable; entering recovery\n");run_command("sdp 0",0);return CMD_RET_FAILURE;}
    valid=!lf_pref_load(&preference_io,&pref);
    if(valid)printf("Boot preference: generation=%u priority=%u slot=%u\n",pref.generation,pref.priority,pref.slot);
    lf_menu_init(&menu,get_timer(0),valid?pref.priority:LF_LEFONY,valid,1,save_priority,NULL);
    if(lf_hw_present(&menu,menu.start)) {lf_hw_shutdown();run_command("sdp 0",0);return CMD_RET_FAILURE;}
    menu.start=get_timer(0);
    puts(valid?"Lefony boot menu: countdown ready\n":"Lefony boot menu: preference unavailable; menu ready\n");
    for(;;) {
        WATCHDOG_RESET();now=get_timer(0);
        lf_menu_step(&menu,now,lf_hw_keys());lf_hw_touch(&menu,now);
        if(drawn!=menu.screen || previous!=menu.selected || notice!=menu.notice ||
           (menu.screen==LF_COUNTDOWN && (u32)(now-last)>=50)) {
            if(lf_hw_present(&menu,now)) {puts("Lefony menu: presentation failed\n");lf_hw_shutdown();run_command("sdp 0",0);return CMD_RET_FAILURE;}
            if(drawn!=menu.screen || previous!=menu.selected)printf("Lefony boot menu: screen=%u selected=%u\n",menu.screen,menu.selected);
            drawn=menu.screen;previous=menu.selected;notice=menu.notice;last=now;
        }
        if(menu.screen==LF_BOOT) {
            printf("Lefony boot menu: loading OS %u\n",menu.boot_os);
            if(menu.boot_os==LF_LEFONY && !load_lefony()) {
                lf_hw_shutdown();run_command("bootz 80800000 - 83000000",0);
                if(lf_hw_init())return CMD_RET_FAILURE;
            }
            lf_menu_boot_failed(&menu);drawn=-1;
        }else if(menu.screen==LF_RECOVERY) {
            puts("Lefony boot menu: recovery requested\n");run_command("sdp 0",0);
            valid=!lf_pref_load(&preference_io,&pref);
            lf_menu_init(&menu,get_timer(0),valid?pref.priority:0,valid,1,save_priority,NULL);
            drawn=-1;
        }
        udelay(5000);
    }
}
U_BOOT_CMD(lfboot,1,0,do_lfboot,"Lefony graphical boot manager","");
