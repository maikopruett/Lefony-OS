/* SPDX-License-Identifier: GPL-2.0-or-later
 * Prime board facts: hardware/prime_g2/reference/keypad-matrix.csv, captured
 * LCDIF/CCM/PWM registers, ILI9322-MODEL.md; Linux Goodix reset/report protocol.
 * This driver owns its display buffers until LCDIF has stopped at handoff.
 */
#include <common.h>
#include <malloc.h>
#include <i2c.h>
#include <watchdog.h>
#include <asm/io.h>
#include <asm/arch/clock.h>
#include "hardware.h"
#define LCD 0x021c8000u
#define CCM 0x020c4000u
#define MUX 0x020e0000u
#define GPIO1 0x0209c000u
#define GPIO2 0x020a0000u
#define GPIO3 0x020a4000u
#define GPIO4 0x020a8000u
#define PWM 0x020f8000u
#define BYTES (320*240*4)
static u32 *buffers[2];
static unsigned front;
static int display_ready, touch_ready;
static int touch_contacts;
static struct udevice *touch;
static void bits(u32 a,u32 mask,u32 v) {clrsetbits_le32((void *)a,mask,v);}
static void mux(unsigned m,unsigned p,unsigned mode,unsigned ctrl) {writel(mode,MUX+m);writel(ctrl,MUX+p);}
static void output(u32 gpio,unsigned pin,int value) {bits(gpio,1u<<pin,value?1u<<pin:0);bits(gpio+4,1u<<pin,1u<<pin);}
static void level(u32 gpio,unsigned pin,int value) {bits(gpio,1u<<pin,value?1u<<pin:0);}
static int wait_bit(u32 addr,u32 mask,int set,unsigned us) {
    while(us--) {if(!!(readl(addr)&mask)==!!set)return 0;udelay(1);}return -1;
}
static void panel(unsigned reg,unsigned value) {
    unsigned word=(reg<<8)|value,i;
    level(GPIO4,22,0);
    for(i=0;i<16;i++) {level(GPIO4,21,0);level(GPIO4,23,!!(word&0x8000));udelay(5);level(GPIO4,21,1);udelay(5);word<<=1;}
    level(GPIO4,22,1);udelay(5);
}
static int pmic_panel_power(void) {
    struct udevice *dev;u8 v,r;unsigned i;
    if(i2c_get_chip_for_busnum(0,0x08,1,&dev))return -1;
    for(i=0;i<3;i++) {
        if(dm_i2c_read(dev,0x4c,&v,1))continue;
        v=(v&~0x1f)|0x1f;
        if(dm_i2c_write(dev,0x4c,&v,1)||dm_i2c_read(dev,0x4c,&r,1)||r!=v)continue;
        if(dm_i2c_read(dev,0x4d,&v,1))continue;
        v=(v&~0x0f)|1;
        if(!dm_i2c_write(dev,0x4d,&v,1)&&!dm_i2c_read(dev,0x4d,&r,1)&&r==v)return 0;
    }return -1;
}
static void keys_init(void) {
    unsigned row,col;
    /* GPIO2 even pads are pulled-up rows 1..7; odd pads are open-drain
     * columns simulated by output-low/input direction switching. */
    for(row=1;row<8;row++)mux(0x00c4+row*8,0x0350+row*8,5,0x1b010);
    for(col=0;col<8;col++)mux(0x00c8+col*8,0x0354+col*8,5,0x110b0);
    bits(GPIO2+4,0xfffe,0);bits(GPIO2,0xaaaa,0);
}
static void keys_settle(void) {
    /* Match the physical native driver's bounded GPIO settling loop. Allow
     * pulled-up rows to recover after releasing a column as well as settling
     * the driven column, so one switch cannot leak into the next sample. */
    volatile unsigned i;
    for(i=0;i<8192;i++)__asm__ volatile("nop");
}
unsigned lf_hw_keys(void) {
    unsigned col,result=0;u32 rows;
    bits(GPIO2+4,0xaaaa,0);
    for(col=0;col<8;col++) {
        keys_settle();
        /* GPIO DR reads input pad levels for input-direction pins. A
         * backlight read/modify/write can therefore latch a floating column
         * high. Restore the low output latch before driving each column. */
        bits(GPIO2,0xaaaa,0);
        bits(GPIO2+4,0xaaaa,1u<<(col*2+1));keys_settle();
        rows=~readl(GPIO2+8);
        if(col==0 && (rows&(1u<<14)))result|=LF_ENTER;
        if(col==4 && (rows&(1u<<10)))result|=LF_UP;
        if(col==5 && (rows&(1u<<8)))result|=LF_DOWN;
        if(col==6 && (rows&(1u<<8)))result|=LF_BACK;
        if(col==7 && (rows&(1u<<2)))result|=LF_LEFT;
        if(col==1 && (rows&(1u<<14)))result|=LF_RIGHT;
        bits(GPIO2+4,0xaaaa,0);
    }
    bits(GPIO2+4,0xaaaa,0);return result;
}
static void touch_init(void) {
    u8 id[4];
    touch_contacts=0;
    mux(0x00a4,0x0330,5,0x17059);mux(0x00a8,0x0334,5,0x1b0b0);
    output(GPIO1,24,0);output(GPIO1,25,1);mdelay(20);udelay(200);
    level(GPIO1,24,1);mdelay(7);bits(GPIO1+4,1u<<24,0);
    level(GPIO1,25,0);mdelay(50);bits(GPIO1+4,1u<<25,0);
    touch_ready=!i2c_get_chip_for_busnum(1,0x14,2,&touch) && !dm_i2c_read(touch,0x8140,id,4) &&
                id[0]>='0' && id[0]<='9' && id[1]>='0' && id[1]<='9';
}
void lf_hw_touch(struct lf_menu *m,uint32_t now) {
    u8 report[9],zero=0;int n;
    if(!touch_ready)return;
    if(dm_i2c_read(touch,0x814e,report,sizeof(report))) {touch_contacts=-1;lf_menu_touch(m,now,-1,0,0,0);return;}
    if(!(report[0]&0x80)) {
        if(!touch_contacts)lf_menu_touch(m,now,0,0,0,0);
        if(m->touch_target>=0 && (u32)(now-m->touch_at)>250)lf_menu_touch(m,now,-1,0,0,0);
        return;
    }
    n=report[0]&15;
    if(dm_i2c_write(touch,0x814e,&zero,1)) {touch_contacts=-1;lf_menu_touch(m,now,-1,0,0,0);return;}
    touch_contacts=n;
    lf_menu_touch(m,now,n,report[1]&15,report[2]|report[3]<<8,report[4]|report[5]<<8);
}
int lf_hw_init(void) {
    unsigned i;u32 clk,div;
    static const u8 gamma[]={0xa7,0x55,0x71,0x71,0x73,0x55,0x18,0x62};
    if(display_ready)return 0;
    keys_init();
    /* Keep both backlight controls dark until the first frame is ready. */
    mux(0x01d0,0x045c,5,0x17059);output(GPIO2,21,0);
    mux(0x01dc,0x0468,5,0x110b0);output(GPIO4,19,0);
    if(pmic_panel_power()) {puts("Lefony menu: panel supply unavailable\n");return -1;}
    for(i=0;i<2;i++) {if(!buffers[i])buffers[i]=memalign(64,BYTES);if(!buffers[i])return -1;memset(buffers[i],0,BYTES);flush_dcache_range((ulong)buffers[i],(ulong)buffers[i]+BYTES);}
    mux(0x01e4,0x0470,5,0x70a1);mux(0x01e8,0x0474,5,0x70a1);mux(0x01ec,0x0478,5,0x70a1);
    output(GPIO4,21,1);output(GPIO4,22,1);output(GPIO4,23,0);
    mux(0x0114,0x03a0,5,0x17059);output(GPIO3,4,0);mdelay(20);
    level(GPIO3,4,1);mdelay(10);level(GPIO3,4,0);mdelay(10);
    for(i=0;i<8;i++)mux(0x0118+i*4,0x03a4+i*4,0,0x79);
    for(i=0;i<4;i++)mux(0x0104+i*4,0x0390+i*4,0,0x79);
    /* PLL2_BUS 528 MHz / 6 / 5 = 17.6 MHz, captured Prime serial RGB timing. */
    bits(CCM+0x74,3u<<10,0);bits(CCM+0x38,0x1ffu<<9,5u<<12);
    bits(CCM+0x18,7u<<23,4u<<23);bits(CCM+0x70,3u<<28,3u<<28);bits(CCM+0x74,3u<<10,3u<<10);
    writel(1u<<31,LCD+8);if(wait_bit(LCD,1u<<31,0,1000))return -1;
    writel(1u<<30,LCD+8);writel(1u<<31,LCD+4);if(wait_bit(LCD,1u<<30,1,1000))return -1;
    writel(1u<<31,LCD+8);if(wait_bit(LCD,1u<<31,0,1000))return -1;
    writel(1u<<30,LCD+8);if(wait_bit(LCD,1u<<30,0,1000))return -1;
    writel((1u<<19)|(1u<<14)|(1u<<10)|(1u<<8)|(1u<<5),LCD);
    writel(7u<<16,LCD+0x10);writel(4u<<21,LCD+0x20);writel((240u<<16)|960,LCD+0x30);
    front=0;writel((ulong)buffers[0],LCD+0x40);writel((ulong)buffers[0],LCD+0x50);
    writel(0x11300001,LCD+0x70);writel(264,LCD+0x80);writel((1u<<18)|1132,LCD+0x90);
    writel((72u<<16)|18,LCD+0xa0);writel((1u<<18)|960,LCD+0xb0);
    writel((1u<<17)|(1u<<5)|1,LCD+4);writel(1u<<24,LCD+0x14);
    level(GPIO3,4,1);mdelay(120);
    panel(7,0xee);panel(1,0x14);panel(2,0x3a);panel(5,0x67);panel(6,0x0f);panel(0x0a,0x49);panel(0x0b,5);
    for(i=0;i<8;i++)panel(0x10+i,gamma[i]);
    panel(7,0xef);mdelay(200);panel(0x30,0x0d);mdelay(400);
    /* Use the existing PERCLK without disturbing U-Boot's timer source. */
    clk=mxc_get_clock(MXC_IPG_PERCLK);div=(clk+200*65535-1)/(200*65535);if(!div||div>4096)return -1;
    bits(CCM+0x80,3u<<30,3u<<30);writel(8,PWM);if(wait_bit(PWM,8,0,1000))return -1;
    writel(clk/div/200-2,PWM+0x10);writel(clk/div/200*3/4,PWM+0xc);
    writel((1u<<24)|(1u<<23)|(1u<<22)|(2u<<16)|((div-1)<<4)|1,PWM);
    mux(0x01dc,0x0468,6,0x110b0);touch_init();display_ready=1;return 0;
}
int lf_hw_present(const struct lf_menu *m,uint32_t now) {
    unsigned next=1-front,tries=100;ulong address;
    if(!display_ready)return -1;
    /* Never overwrite either a scanned or still-pending frame. */
    if(readl(LCD+0x40)!=(ulong)buffers[front]) {puts("Boot menu: unexpected active framebuffer\n");return -1;}
    lf_menu_draw(m,now,buffers[next]);address=(ulong)buffers[next];
    flush_dcache_range(address,address+BYTES);writel(address,LCD+0x50);
    /* Acknowledge the previous frame before waiting for this exchange. */
    writel(1u<<9,LCD+0x18);
    while(readl(LCD+0x40)!=address && tries--) {WATCHDOG_RESET();udelay(1000);}
    if(readl(LCD+0x40)!=address) {printf("Boot menu: frame exchange timed out (ctrl=%08x status=%08x current=%08x next=%08x)\n",readl(LCD),readl(LCD+0x10),readl(LCD+0x40),readl(LCD+0x50));return -1;}
    front=next;level(GPIO2,21,1);return 0;
}
void lf_hw_shutdown(void) {
    level(GPIO2,21,0);
    if(display_ready) {panel(0x30,9);panel(7,0xee);mdelay(100);}
    writel(1,LCD+8);wait_bit(LCD,1,0,50000);
    bits(GPIO2+4,0xaaaa,0);touch_ready=0;display_ready=0;
}
