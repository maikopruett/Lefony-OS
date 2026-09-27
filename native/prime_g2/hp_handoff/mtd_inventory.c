/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Read-only Linux ARM EABI MTD inventory, usable without a recovery libc.
 * Build: arm-none-eabi-gcc -Os -marm -march=armv7-a -nostdlib -static
 *   -fno-builtin -Wl,-e,_start -Wl,--build-id=none mtd_inventory.c -lgcc -o inventory
 * Only open(O_RDONLY), ioctl(MEMGETINFO/MEMGETBADBLOCK), write(stdout), exit.
 * Constants/ABI: Linux v4.14 include/uapi/mtd/mtd-abi.h. */
typedef unsigned int u32;
typedef unsigned long long u64;
struct mtd_info { unsigned char type; u32 flags,size,erase,write,oob; u64 padding; };
_Static_assert(sizeof(struct mtd_info)==32, "Linux ARM MTD ABI size");
void *memset(void *p, int value, unsigned size) {
    volatile unsigned char *bytes=p; unsigned i;
    for(i=0;i<size;i++)bytes[i]=(unsigned char)value;
    return p;
}
static long syscall3(long n,long a,long b,long c) {
    register long r0 asm("r0")=a, r1 asm("r1")=b, r2 asm("r2")=c;
    register long r7 asm("r7")=n;
    asm volatile("svc 0" : "+r"(r0) : "r"(r1),"r"(r2),"r"(r7) : "memory", "cc");
    return r0;
}
static void put(const char *s) {
    const char *end=s; while(*end)end++;
    if(syscall3(4,1,(long)s,end-s)!=end-s)syscall3(1,2,0,0);
}
static void number(u32 value) {
    char b[11]; unsigned i=10; b[i]=0;
    do {b[--i]='0'+value%10; value/=10;}while(value);
    put(b+i);
}
void _start(void) {
    static const u32 sizes[]={0x400000,0x800000,0x100000,0x100000,0x1f200000};
    char path[]="/dev/mtd0";
    unsigned part;
    for(part=0;part<5;part++) {
        struct mtd_info m={0}; long fd,ret; u64 offset;
        path[8]='0'+part;
        fd=syscall3(5,(long)path,0,0);
        if(fd<0 || syscall3(54,fd,0x80204d01,(long)&m)<0 ||
           m.type!=4 || m.size!=sizes[part] || m.erase!=131072 ||
           m.write!=2048 || m.oob!=64) {
            put("ERROR geometry/open\n");syscall3(1,1,0,0);for(;;);
        }
        put("mtd ");number(part);put(" size ");number(m.size);put(" bad");
        for(offset=0;offset<m.size;offset+=m.erase) {
            ret=syscall3(54,fd,0x40084d0b,(long)&offset);
            if(ret<0) {put(" ERROR ioctl\n");syscall3(1,1,0,0);for(;;);}
            if(ret) {put(" ");number((u32)offset/m.erase);}
        }
        put("\n");syscall3(6,fd,0,0);
    }
    put("INVENTORY-READONLY-OK\n");syscall3(1,0,0,0);for(;;);
}
