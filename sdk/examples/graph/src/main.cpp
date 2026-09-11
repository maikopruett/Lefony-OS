// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/ui.h>
static int center=160;
extern "C" void lefony_event(Lefony::Event event,uint32_t first,uint32_t) {
  if(event==Lefony::Event::Key) {
    if(first==static_cast<unsigned>(Lefony::Key::Left) && center>10) center-=10;
    if(first==static_cast<unsigned>(Lefony::Key::Right) && center<310) center+=10;
  }
  if(event!=Lefony::Event::Start && event!=Lefony::Event::Key) return;
  Lefony::fill({0,0,320,240,Lefony::White});
  Lefony::fill({0,180,320,1,Lefony::Black});
  Lefony::fill({center,0,1,240,Lefony::Black});
  Lefony::plotQuadratic(center,180,80);
  Lefony::label(10,210,"Left / Right moves the graph");
}
