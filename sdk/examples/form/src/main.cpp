// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/ui.h>
static Lefony::NumberField<> field;
extern "C" void lefony_event(Lefony::Event event,uint32_t first,uint32_t second) {
  if(event==Lefony::Event::Start || field.handle({event,first,second})) {
    Lefony::fill({0,0,320,240,Lefony::White});
    Lefony::label(15,20,"Enter a number");
    field.draw(15,60);
    Lefony::label(15,110,"Use digits and Backspace");
  }
}
