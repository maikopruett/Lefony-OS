/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "preferences.h"
#ifndef __UBOOT__
#include <string.h>
#endif
static uint32_t get(const uint8_t *b) { return (uint32_t)b[0] | (uint32_t)b[1]<<8 | (uint32_t)b[2]<<16 | (uint32_t)b[3]<<24; }
static void put(uint8_t *b, uint32_t v) { unsigned i; for(i=0;i<4;i++) b[i]=(uint8_t)(v>>(8*i)); }
static uint32_t crc(const uint8_t *b, unsigned n) {
    uint32_t v=~0u; unsigned i;
    while(n--) { v ^= *b++; for(i=0;i<8;i++) v=(v>>1)^((0u-(v&1))&0xedb88320u); }
    return ~v;
}
void lf_pref_encode(uint8_t *b, uint32_t generation, unsigned priority) {
    memset(b,0,LF_PREF_BYTES); memcpy(b,"LFBP",4);
    put(b+4,1); put(b+8,LF_PREF_LAYOUT); put(b+12,generation); put(b+16,priority);
    put(b+60,crc(b,60));
}
static int decode(const uint8_t *b, struct lf_preference *p) {
    unsigned i;
    if(memcmp(b,"LFBP",4) || get(b+4)!=1 || get(b+8)!=LF_PREF_LAYOUT ||
       !get(b+12) || get(b+16)>1 || get(b+60)!=crc(b,60)) return -1;
    for(i=20;i<60;i++) if(b[i]) return -1;
    p->generation=get(b+12); p->priority=get(b+16); p->valid=1; return 0;
}
int lf_pref_load(const struct lf_pref_io *io, struct lf_preference *out) {
    struct lf_preference p[2]={{0},{0}}; uint8_t b[LF_PREF_BYTES]; unsigned i;
    memset(out,0,sizeof(*out));
    for(i=0;i<2;i++) if(!io->read(io->ctx,i,b)) { decode(b,&p[i]); p[i].slot=i; }
    if(p[0].valid && p[1].valid && p[0].generation==p[1].generation && p[0].priority!=p[1].priority) return -1;
    if(!p[0].valid && !p[1].valid) return -1;
    *out = !p[0].valid || (p[1].valid && p[1].generation>p[0].generation) ? p[1] : p[0];
    return 0;
}
int lf_pref_save(const struct lf_pref_io *io, unsigned priority) {
    struct lf_preference old; uint8_t b[LF_PREF_BYTES], verify[LF_PREF_BYTES];
    unsigned slot; uint32_t gen;
    /* Blank, unreadable and conflicting media require explicit provisioning. */
    if(priority>1 || lf_pref_load(io,&old) || old.generation==0xffffffffu) return -1;
    slot=1-old.slot; gen=old.generation+1;
    lf_pref_encode(b,gen,priority);
    if(io->replace(io->ctx,slot,b) || io->read(io->ctx,slot,verify) || memcmp(b,verify,sizeof(b))) return -1;
    return 0;
}
