/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
/* VM-only R0 probe. Experimental SVCs are deliberately outside the public SDK. */
#include <lefony/app_c.h>

extern int execution_registers(unsigned yield);
static unsigned launches;

static void require(int ok) {
  if (!ok) __asm__ volatile("udf #0");
}

static void nested(unsigned depth) {
  volatile uint32_t canary[32];
  for (unsigned i=0; i<32; ++i) canary[i]=0x12340000u+depth*32+i;
  if (depth) nested(depth-1);
  else {
    require(execution_registers(0)==1);
    require(execution_registers(1)==1);
  }
  for (unsigned i=0; i<32; ++i) require(canary[i]==0x12340000u+depth*32+i);
}

int main(void) {
  require(lefony_service(0x7fff0001u, 0)==0);
  require(lefony_service(0x7fff0001u, 0)==-4); /* No second opt-in. */
#ifdef EXECUTION_SPIN
  for (;;) __asm__ volatile("" ::: "memory");
#else
  nested(8);
  lefony_rect_t rectangle={0,0,320,240,LEFONY_GREEN};
  require(lefony_fill(rectangle)==0);
  return 0;
#endif
}

void lefony_event(lefony_event_t event, uint32_t first, uint32_t second) {
  (void)event; (void)first; (void)second;
  require(++launches==1);
  require(main()==0);
}
