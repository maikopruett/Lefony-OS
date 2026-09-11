// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/ui.h>
namespace {
unsigned count=0;
Lefony::Button add({20,140,120,38,Lefony::Green},"Add one");
Lefony::Button reset({175,140,120,38,Lefony::Green},"Reset");
void draw() {
  Lefony::fill({0,0,320,240,Lefony::White});
  Lefony::label(20,20,"Native counter");
  char value[11]; Lefony::number(value,count);
  Lefony::label(20,75,value);
  add.draw(); reset.draw();
}
}
extern "C" void lefony_event(Lefony::Event event,uint32_t first,uint32_t second) {
  Lefony::Input input{event,first,second};
  if(event==Lefony::Event::Start) { count=0; Lefony::readData(0,&count,sizeof(count)); draw(); }
  if(add.handle(input) || (event==Lefony::Event::Key && first==static_cast<unsigned>(Lefony::Key::Confirm))) { count++; Lefony::writeData(0,&count,sizeof(count)); draw(); }
  if(reset.handle(input)) { count=0; Lefony::writeData(0,&count,sizeof(count)); draw(); }
}
