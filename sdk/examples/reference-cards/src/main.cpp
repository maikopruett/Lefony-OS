// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/ui_controls.h>
#include <lefony/graphics_screen.h>
#include <lefony/resources.h>
namespace {
using namespace Lefony;
using namespace Lefony::UI;
Resources::Bundle bundle;Resources::Resource cards,book;
Focus<2> focus;unsigned page=0,starts[9]{},lengths[9]{};bool ready=false;
constexpr Box Previous{10,202,140,30},Next{170,202,140,30};
bool load() {
  using namespace Resources;
  if(bundle.open(embedded,embeddedBytes)!=Status::Ok || !bundle.find("cards",cards) || !bundle.find("book",book) ||
     cards.kind!=Kind::Blob || cards.bytes>512 || book.kind!=Kind::RGB565) return false;
  unsigned line=0,start=0;
  for(unsigned i=0;i<cards.bytes;i++) {
    if(cards.data[i]=='\n') {
      if(line>=9 || i==start || i-start>40) return false;
      starts[line]=start;lengths[line++]=i-start;start=i+1;
    } else if(cards.data[i]<32 || cards.data[i]>126) return false;
  }
  return line==9 && start==cards.bytes;
}
void redraw() {
  Canvas canvas;canvas.fill({0,0,320,240},Theme::Paper);canvas.fill({0,0,320,28},Theme::Accent);
  canvas.text({10,7,300,14},"REFERENCE CARDS",15,White,Theme::Accent);
  if(!ready) { canvas.text({10,65,300,14},"Resource validation failed",26);return; }
  char numberText[]="CARD 1 / 3";numberText[5]=static_cast<char>('1'+page);
  canvas.text({14,43,210,14},numberText,10,Theme::Muted);
  canvas.fill({10,82,300,107},White);canvas.outline({10,82,300,107},Theme::Selected);
  Graphics::Screen output;
  auto status=Graphics::image({0,0,320,240},258,36,book.width,book.height,book.stride,book.data,book.bytes,
    [&](int x,int y,int width,uint16_t color){return output.span(x,y,width,color);},book.transparent,book.key);
  if(status!=Graphics::Status::Ok || !output.flush()) { ready=false;redraw();return; }
  for(unsigned i=0;i<3;i++) {
    unsigned row=page*3+i;
    canvas.text({20,94+static_cast<int>(i)*30,280,14},reinterpret_cast<const char *>(cards.data+starts[row]),lengths[row],i?Theme::Ink:Theme::Accent,White);
  }
  button(canvas,Previous,"Previous",focus.focused()==1,focus.pressed()==1);
  button(canvas,Next,"Next / OK",focus.focused()==2,focus.pressed()==2);
}
void next(int direction) { page=(page+(direction<0?2:1))%3;focus.select(2);redraw(); }
}
extern "C" void lefony_event(Lefony::Event event,uint32_t first,uint32_t second) {
  using namespace Lefony;
  if(event==Event::Start) { focus.add(1,Previous);focus.add(2,Next);focus.select(2);ready=load();redraw();return; }
  if(event==Event::Close) { focus.cancel();return; }
  InputSnapshot input;if(!ready || !UI::read({event,first,second},input)) return;
  if(event==Event::Key) {
    focus.cancel();
    if(input.key==InputKey::Left) next(-1);
    else if(input.key==InputKey::Right || input.key==InputKey::Confirm) next(1);
  } else if(event==Event::Touch) {
    unsigned id=focus.touch(input.touchPhase,input.contactCount,input.contacts[0].x,input.contacts[0].y,input.flags&ContactsChanged);
    if(id) next(id==1?-1:1);else redraw();
  }
}
