/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Phase 5 candidate. Missing/torn/unrecognized layout always means recovery. */
#include <common.h>
#include <command.h>
#include <malloc.h>
#include <nand.h>
#include <linux/errno.h>
#include <linux/libfdt.h>
#include <u-boot/sha256.h>
#include <u-boot/rsa-mod-exp.h>
#include <watchdog.h>
#include <asm/io.h>
#include "hardware.h"
#include "preferences.h"
#include "dual_layout.h"

#define PAGE 2048u
#define BLOCK 0x20000u
#define HP_STAGE 0x84000000UL
#define LF_STAGE 0x80800000UL
#define DTB_STAGE 0x83000000UL
#define HANDOFF 0x87ffd000UL
static struct mtd_info *flash;
static u8 descriptor[512] __aligned(64);
static const unsigned first[] = {LF_DUAL_HP_IMAGE_FIRST, LF_DUAL_LEFONY_IMAGE_FIRST,
    LF_DUAL_LEFONY_DTB_FIRST, LF_DUAL_RESCUE_FIRST};
static const unsigned blocks[] = {LF_DUAL_HP_IMAGE_BLOCKS, LF_DUAL_LEFONY_IMAGE_BLOCKS,
    LF_DUAL_LEFONY_DTB_BLOCKS, LF_DUAL_RESCUE_BLOCKS};
static const unsigned maximum[] = {8192864, 8388608, 1048576, 8388608};
int hp_boot_staged_os(int confined);
static u32 word(const u8 *b) { return (u32)b[0] | (u32)b[1]<<8 | (u32)b[2]<<16 | (u32)b[3]<<24; }
static int read_exact(ulong off, u8 *data, size_t count)
{
    size_t got = 0;
    int ret = mtd_read(flash, off, count, &got, data);
    return ((ret && ret != -EUCLEAN) || got != count) ? -1 : 0;
}
static int uniform(const u8 *data, size_t n, u8 value)
{
    while (n--) if (*data++ != value) return 0;
    return 1;
}
static int signature_valid(const u8 *data)
{
    struct key_prop key = { .rr=lf_dual_rr, .modulus=lf_dual_modulus,
        .n0inv=LF_DUAL_N0INV, .num_bits=2048 };
    static const u8 der[] = {0x30,0x31,0x30,0x0d,0x06,0x09,0x60,0x86,0x48,
        0x01,0x65,0x03,0x04,0x02,0x01,0x05,0x00,0x04,0x20};
    u8 digest[32], decoded[256] __aligned(8);
    unsigned i;
    if (memcmp(data,"LFD5",4) || word(data+4)!=1 || word(data+8)!=LF_DUAL_LAYOUT ||
        word(data+12)!=0x32475048 || !word(data+16) || word(data+20)!=4 ||
        word(data+24)!=1 || word(data+28) ||
        memcmp(data+32,lf_dual_layout_sha,32) || memcmp(data+64,lf_dual_profile_sha,32) ||
        !uniform(data+240,16,0)) return 0;
    for (i=0;i<4;i++) if (!word(data+96+36*i) || word(data+96+36*i)>maximum[i]) return 0;
    sha256_csum_wd(data,256,digest,CHUNKSZ_SHA256);
    if (rsa_mod_exp_sw(data+256,256,&key,decoded)) return 0;
    return decoded[0]==0 && decoded[1]==1 && uniform(decoded+2,202,0xff) &&
        decoded[204]==0 && !memcmp(decoded+205,der,sizeof(der)) && !memcmp(decoded+224,digest,32);
}
static int layout_valid(const u8 *page)
{
    unsigned end;
    if (memcmp(page,"LFC5",4) || word(page+4)!=1 || word(page+8)!=LF_DUAL_LAYOUT ||
        !word(page+12) || word(page+16)>1 || uniform(page+20,32,0) ||
        !uniform(page+52,12,0) || word(page+2044)!=crc32(0,page,2044)) return 0;
    end=word(page+16) ? 576 : 64;
    return uniform(page+end,2044-end,0xff);
}
static int load_layout(void)
{
    u8 p[2][PAGE] __aligned(64);
    int valid[2], selected;
    unsigned i;
    flash=get_nand_dev_by_index(0);
    if (!flash || flash->size!=0x20000000ULL || flash->erasesize!=BLOCK ||
        flash->writesize!=PAGE || flash->oobsize!=64) return -1;
    for (i=0;i<2;i++) valid[i]=!nand_block_isbad(flash,(256+i)*BLOCK) &&
        !read_exact((256+i)*BLOCK,p[i],PAGE) && layout_valid(p[i]);
    if (!valid[0] && !valid[1]) return -1;
    if (valid[0] && valid[1] && (memcmp(p[0]+20,p[1]+20,32) ||
        (word(p[0]+12)==word(p[1]+12) && memcmp(p[0],p[1],PAGE)))) return -1;
    selected= !valid[0] || (valid[1] && word(p[1]+12)>word(p[0]+12));
    if (word(p[selected]+16)!=1 || !signature_valid(p[selected]+64)) return -1;
    memcpy(descriptor,p[selected]+64,512);
    return 0;
}
static int load_image(unsigned index, ulong address)
{
    size_t length, actual=0;
    u8 digest[32];
    unsigned bytes=word(descriptor+96+36*index);
    length=ALIGN(bytes,PAGE);
    if (nand_read_skip_bad(flash,first[index]*BLOCK,&length,&actual,blocks[index]*BLOCK,(u8 *)address)) return -1;
    sha256_csum_wd((u8 *)address,bytes,digest,CHUNKSZ_SHA256);
    return memcmp(digest,descriptor+100+36*index,32) ? -1 : 0;
}
static int pref_read(void *ctx,unsigned slot,u8 *out)
{
    u8 page[PAGE] __aligned(64);
    ulong off=(LF_DUAL_PREFERENCE_PRIMARY_FIRST+slot)*BLOCK;
    (void)ctx;
    if (slot>1 || nand_block_isbad(flash,off) || read_exact(off,page,PAGE)) return -1;
    memcpy(out,page,LF_PREF_BYTES);return 0;
}
static int pref_replace(void *ctx,unsigned slot,const u8 *record)
{
    u8 *data; ulong off=(LF_DUAL_PREFERENCE_PRIMARY_FIRST+slot)*BLOCK;
    size_t written=0; int ret=-1;
    (void)ctx;
    if (slot>1 || load_layout() || nand_block_isbad(flash,off)) return -1;
    data=memalign(64,BLOCK);if (!data) return -1;
    if (read_exact(off,data,BLOCK) ||
        (memcmp(data,"LFBP",4) && !uniform(data,LF_PREF_BYTES,0xff)) ||
        !uniform(data+LF_PREF_BYTES,BLOCK-LF_PREF_BYTES,0xff)) goto done;
    memset(data,0xff,PAGE);memcpy(data,record,LF_PREF_BYTES);
    if (nand_erase(flash,off,BLOCK) || mtd_write(flash,off,PAGE,&written,data) || written!=PAGE) goto done;
    ret=0;
done: free(data);return ret;
}
static const struct lf_pref_io preferences={NULL,pref_read,pref_replace};
static int save_priority(void *ctx,unsigned os)
{
    (void)ctx;
    return load_layout() ? -1 : lf_pref_save(&preferences,os);
}
static int boot_lefony(void)
{
    u32 *image=(u32 *)LF_STAGE;
    u8 *handoff=(u8 *)HANDOFF;
    unsigned bytes=word(descriptor+132);
    if (load_image(1,LF_STAGE) || load_image(2,DTB_STAGE) || image[0]!=0xea00000e ||
        image[9]!=0x016f2818 || image[10] || image[11]!=bytes ||
        bytes<0x1100 || image[12]!=0x354c464c || image[13]!=5 || image[14]!=1 || image[15] || image[0x1000/4]!=0xea000006 || image[0x1020/4]!=0xf10c00c0 ||
        fdt_check_header((void *)DTB_STAGE) || fdt_totalsize((void *)DTB_STAGE)>word(descriptor+168)) return -1;
    /* Separate handoff contract; never reinterpret the existing LFB1 A/B record. */
    memset(handoff,0,64);memcpy(handoff,"LFH5",4);
    memcpy(handoff+4,lf_dual_layout_sha,32);memcpy(handoff+36,descriptor+16,4);
    ((u32 *)handoff)[15]=crc32(0,handoff,60);
    flush_dcache_range(HANDOFF,HANDOFF+64);
    /* LFMW v1: consumed by native startup, only this loader supports the
     * wake-to-menu mailbox. Keep the existing LFUB recovery contract intact. */
    writel(0x574d464c,(void *)0x8000100c);
    writel(~0x574d464cU,(void *)0x80001010);
    flush_dcache_range(0x80001000,0x80001040);
    flush_dcache_range(LF_STAGE,LF_STAGE+ALIGN(bytes,64));
    lf_hw_shutdown();run_command("bootz 80800000 - 83000000",0);
    return -1;
}
static int recovery(void)
{
    puts("Dual boot: recovery required; no unrestricted HP fallback\n");
    run_command("sdp 0",0);
    return CMD_RET_FAILURE;
}
static int do_lfdualboot(cmd_tbl_t *cmdtp,int flag,int argc,char *const argv[])
{
    struct lf_menu menu;struct lf_preference pref;
    int valid,drawn=-1;unsigned selected=99;u32 last=0;
    enum lf_notice notice=LF_NONE;
    (void)cmdtp;(void)flag;(void)argc;(void)argv;
    if (load_layout() || lf_hw_init()) return recovery();
    /* LFM1 is one-use and does not change NAND preferences. Preserve recovery,
     * watchdog and boot-confirmation tokens owned by the existing protocols. */
    if (readl((void *)0x020cc068)==0x314d464c) {
        unsigned retry=100;
        writel(0,(void *)0x020cc068);
        while (readl((void *)0x020cc068) && retry--) udelay(100);
    }
    valid=!lf_pref_load(&preferences,&pref);
    lf_menu_init(&menu,get_timer(0),valid?pref.priority:LF_LEFONY,valid,3,save_priority,NULL);
    /* Off/On returns through the same countdown as an ordinary startup.
     * The retained request is consumed above; only Enter opens the menu. */
    if (lf_hw_present(&menu,menu.start)) return recovery();
    menu.start=get_timer(0);
    puts(valid?"Dual boot: countdown ready\n":"Dual boot: menu ready\n");
    for (;;) {
        u32 now=get_timer(0);WATCHDOG_RESET();
        lf_menu_step(&menu,now,lf_hw_keys());lf_hw_touch(&menu,now);
        if (drawn!=menu.screen || selected!=menu.selected || notice!=menu.notice ||
            (menu.screen==LF_COUNTDOWN && now-last>=50)) {
            if (lf_hw_present(&menu,now)) return recovery();
            if (drawn!=menu.screen || selected!=menu.selected)
                printf("Dual boot: screen=%u selected=%u\n",menu.screen,menu.selected);
            drawn=menu.screen;selected=menu.selected;notice=menu.notice;last=now;
        }
        if (menu.screen==LF_BOOT) {
            printf("Dual boot: loading OS %u\n",menu.boot_os);
            if (!load_layout()) {
                if (menu.boot_os==LF_LEFONY) boot_lefony();
                else if (menu.boot_os==LF_HP && !load_image(0,HP_STAGE)) hp_boot_staged_os(1);
            }
            if (lf_hw_init()) return recovery();
            lf_menu_boot_failed(&menu);drawn=-1;
        } else if (menu.screen==LF_RECOVERY) return recovery();
        udelay(5000);
    }
}
U_BOOT_CMD(lfdualboot,1,0,do_lfdualboot,"validated dual-layout boot manager","");

#ifdef LEFONY_DUAL_RAM_DIAGNOSTIC
/* Only the separate RAM diagnostic builder defines this macro. No NAND writes,
 * OS handoff or caller-selected address: inspect each pre-boot stage in SDP. */
static void diagnostic_report(unsigned stage, int status)
{
    u32 *report=(u32 *)0x83e03000;
    memset(report,0,64);
    report[0]=0x4744464c; /* LFDG */
    report[1]=1;report[2]=stage;report[3]=status;
    flush_dcache_range(0x83e03000,0x83e03040);
}
static int do_lfdualprobe(cmd_tbl_t *cmdtp,int flag,int argc,char *const argv[])
{
    struct lf_menu menu;int result,show;
    (void)cmdtp;(void)flag;
    if (argc!=2 || (strcmp(argv[1],"layout") && strcmp(argv[1],"menu"))) return CMD_RET_FAILURE;
    show=!strcmp(argv[1],"menu");
    diagnostic_report(1,0);result=load_layout();diagnostic_report(2,result);
    if (result || !show) return 0; /* Status is in the fixed report. */
    diagnostic_report(3,0);result=lf_hw_init();diagnostic_report(4,result);
    if (result) return 0;
    lf_menu_init(&menu,get_timer(0),LF_LEFONY,1,3,NULL,NULL);
    result=lf_hw_present(&menu,menu.start);diagnostic_report(5,result);
    return 0;
}
U_BOOT_CMD(lfdualprobe,2,0,do_lfdualprobe,"RAM-only dual startup diagnostic","layout|menu");
#endif
