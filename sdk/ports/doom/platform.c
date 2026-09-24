/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Lefony platform implementation for the pinned doomgeneric engine.
 * The conventional SDK runtime offers a scoped MIT alternative. Third-party
 * engine and library notices remain in effect; see THIRD_PARTY_NOTICES.md. */
#include "doomgeneric.h"
#include "doomkeys.h"
#include "i_system.h"
#include "m_controls.h"
#include "output.h"
#include <lefony/foreground.h>
#include <lefony/input_stream.h>
#include <string.h>
#include <stdlib.h>

static uint16_t frame[320*200];
static LefonyInputStream input;
static unsigned next_event;
static unsigned char wanted[256],delivered[256];
typedef struct { unsigned physical,game; } Binding;
static const Binding bindings[]={
  {LEFONY_PHYSICAL_LEFT,KEY_LEFTARROW},{LEFONY_PHYSICAL_RIGHT,KEY_RIGHTARROW},
  {LEFONY_PHYSICAL_UP,KEY_UPARROW},{LEFONY_PHYSICAL_DOWN,KEY_DOWNARROW},
  {LEFONY_PHYSICAL_OK,KEY_ENTER},{LEFONY_PHYSICAL_BACK,KEY_ESCAPE},
  {LEFONY_PHYSICAL_MENU,KEY_ESCAPE},{LEFONY_PHYSICAL_BACKSPACE,KEY_BACKSPACE},
  {LEFONY_PHYSICAL_XNT,KEY_FIRE},{LEFONY_PHYSICAL_SPACE,KEY_USE},
  {LEFONY_PHYSICAL_SHIFT,KEY_RSHIFT},{LEFONY_PHYSICAL_ALPHA,KEY_RALT},
  {LEFONY_PHYSICAL_HELP,KEY_TAB},{LEFONY_PHYSICAL_NUM,KEY_F2},
  {LEFONY_PHYSICAL_SYMB,KEY_F3},{LEFONY_PHYSICAL_PLOT,KEY_F6},
  {LEFONY_PHYSICAL_VIEW,KEY_F9},{LEFONY_PHYSICAL_POWER,KEY_PAUSE},
  {LEFONY_PHYSICAL_TOOLBOX,KEY_F10},
  {LEFONY_PHYSICAL_PLUS,KEY_EQUALS},{LEFONY_PHYSICAL_MINUS,KEY_MINUS},
  {LEFONY_PHYSICAL_ZERO,'0'},{LEFONY_PHYSICAL_ONE,'1'},
  {LEFONY_PHYSICAL_TWO,'2'},{LEFONY_PHYSICAL_THREE,'3'},
  {LEFONY_PHYSICAL_FOUR,'4'},{LEFONY_PHYSICAL_FIVE,'5'},
  {LEFONY_PHYSICAL_SIX,'6'},{LEFONY_PHYSICAL_SEVEN,'7'},
  {LEFONY_PHYSICAL_EIGHT,'8'},{LEFONY_PHYSICAL_NINE,'9'}
};
static void target(const uint32_t held[2]) {
  memset(wanted,0,sizeof(wanted));
  for(unsigned i=0;i<sizeof(bindings)/sizeof(bindings[0]);i++)
    if(lefony_input_key_held(held,bindings[i].physical)) wanted[bindings[i].game]=1;
}
void DG_Init(void) {
  key_menu_confirm=KEY_ENTER;key_menu_abort=KEY_ESCAPE;
  uint32_t navigation[]={16,1,0,1};
  if(lefony_service(9,navigation)) I_Error("App navigation is unavailable");
  if(lefony_read_input_stream(&input)) I_Error("Input stream is unavailable");
  target(input.held);next_event=input.count;
  lefony_fill((lefony_rect_t){0,0,320,240,LEFONY_BLACK});
  // WAD reads can take minutes on physical NAND. Present feedback before
  // engine initialization; the first 320x200 game frame replaces these lines.
  static const char *const loading[]={
    "Loading Doom...",
    "Reading and checking game data.",
    "This can take several minutes.",
    "Home returns to the menu."
  };
  for(unsigned row=0;row<sizeof(loading)/sizeof(loading[0]);row++)
    lefony_text((lefony_text_t){16,(int32_t)(64+row*24),LEFONY_WHITE,
      LEFONY_BLACK,loading[row],strlen(loading[row])});
  if(lefony_program_yield()) I_Error("Foreground yield failed");
}
void DG_DrawFrame(void) {
  for(unsigned i=0;i<320*200;i++) {
    uint32_t pixel=DG_ScreenBuffer[i];
    frame[i]=(uint16_t)(((pixel>>8)&0xf800)|((pixel>>5)&0x07e0)|((pixel>>3)&0x001f));
  }
  if(lefony_present(frame,0,20,320,200,320)) I_Error("Pixel presentation failed");
}
void DG_SleepMs(uint32_t milliseconds) {
  while(milliseconds) {
    uint32_t interval=milliseconds>60000?60000:milliseconds;
    if(lefony_program_sleep(interval)) I_Error("Foreground sleep failed");
    milliseconds-=interval;
  }
}
uint32_t DG_GetTicksMs(void) { return lefony_millis(); }
int DG_GetKey(int *pressed,unsigned char *key) {
  // Keep complete transitions, including a press and release in one batch.
  // Aliased keys are ORed before comparison so releasing one alias cannot
  // release a second still-held key. No unbounded platform-side event queue.
  unsigned batches=0;
  for(;;) {
    for(unsigned code=0;code<256;code++) if(wanted[code]!=delivered[code]) {
      delivered[code]=wanted[code];*pressed=wanted[code];*key=(unsigned char)code;return 1;
    }
    if(next_event<input.count) {
      const LefonyStreamEvent *event=&input.events[next_event++];
      if(event->kind==LEFONY_INPUT_KEYS) target(event->data.keys.held);
      continue;
    }
    if(batches++==4) return 0;
    if(lefony_read_input_stream(&input)) I_Error("Input stream read failed");
    next_event=0;
    if(input.flags&(LEFONY_INPUT_OVERFLOW|LEFONY_INPUT_FOCUS_RESET)) {
      target(input.held);continue;
    }
    if(!input.count) return 0;
  }
}
void DG_SetWindowTitle(const char *title) {
  // Also used by the checked fatal-error adaptation: the calculator has no
  // window title or terminal. Keep the error visible in the returned app frame.
  lefony_fill((lefony_rect_t){0,0,320,240,LEFONY_BLACK});
  unsigned offset=0;
  for(unsigned row=0;row<12 && title[offset];row++) {
    char line[41];unsigned n=0;
    while(n<40 && title[offset] && title[offset]!='\n') {
      unsigned char c=(unsigned char)title[offset++];line[n++]=c>=32 && c<127?(char)c:'?';
    }
    if(title[offset]=='\n') offset++;
    line[n]=0;
    lefony_text((lefony_text_t){4,(int32_t)(4+row*18),LEFONY_WHITE,LEFONY_BLACK,line,n});
  }
  lefony_program_yield();
}
int main(int argc,char **argv) {
  if(atexit(DG_DiscardOutput)) I_Error("Cannot register save cleanup");
  doomgeneric_Create(argc,argv);
  for(;;) doomgeneric_Tick();
}
