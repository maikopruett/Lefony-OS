// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/ui_controls.h>
#include <lefony/graphics_screen.h>
#include <lefony/plot.h>
#include <lefony/gestures.h>
namespace {
using namespace Lefony;
using namespace Lefony::UI;
constexpr Box PlotBox{10,64,300,115},Next{10,201,102,30},ZoomIn{118,201,92,30},ZoomOut{216,201,94,30};
Plot::View view{-5,5,-2,2};Plot::Curve curve;Gestures gestures(PlotBox);Focus<3> focus;
unsigned mode=0;bool traced=false;Graphics::Point trace{};
constexpr const char *Hint="Arrows pan. Drag / pinch. Hold to reset.";
const char *message=Hint;
void append(char *out,unsigned &size,const char *text,unsigned maximum=63) {
  while(*text && size<maximum) out[size++]=*text++;
  out[size]=0;
}
void fixed(char *out,double value) {
  int32_t scaled=static_cast<int32_t>(Math::round(value*100));unsigned size=0;
  uint32_t magnitude=scaled<0?static_cast<uint32_t>(-scaled):static_cast<uint32_t>(scaled);
  if(scaled<0) out[size++]='-';
  char whole[11];number(whole,magnitude/100);
  append(out,size,whole,15);out[size++]='.';out[size++]=static_cast<char>('0'+magnitude/10%10);
  out[size++]=static_cast<char>('0'+magnitude%10);out[size]=0;
}
Graphics::Point function(double t) {
  if(mode==0) return {t,Math::sin(t)};
  if(mode==1) return {t,t==0?__builtin_nan(""):1/t};
  return {Math::cos(t),Math::sin(t)};
}
void range(Canvas &canvas,int y,const char *name,double low,double high) {
  char text[64]{},value[16];unsigned size=0;append(text,size,name);fixed(value,low);append(text,size,value);
  append(text,size," to ");fixed(value,high);append(text,size,value);canvas.text({10,y,300,14},text,size,Theme::Muted);
}
void footer() {
  Canvas canvas;canvas.fill({0,182,320,17},Theme::Paper);
  Plot::Progress result=curve.progress();
  const char *status=result.status==Plot::Status::Running?"Sampling... Home remains available":
    result.status==Plot::Status::Limit?"Sampling limit: partial curve shown":
    result.status==Plot::Status::OutputFailed?"Drawing failed":result.gaps?"Gaps mark unresolved / invalid samples":message;
  canvas.text({10,183,300,14},status,length(status,63),Theme::Muted);
}
void drawTrace() {
  if(!traced || curve.progress().status!=Plot::Status::Complete) return;
  Graphics::Point p=view.project(trace,PlotBox);
  if(!Numeric::finite(p.x) || !Numeric::finite(p.y) || p.x<PlotBox.x || p.x>=PlotBox.x+PlotBox.width || p.y<PlotBox.y || p.y>=PlotBox.y+PlotBox.height) return;
  Graphics::Screen output;auto sink=[&](int x,int y,int width,uint16_t color) { return output.span(x,y,width,color); };
  Graphics::circle(PlotBox,static_cast<int>(p.x+.5),static_cast<int>(p.y+.5),3,Theme::Ink,sink);
  output.flush();
}
void controls() {
  Canvas canvas;
  button(canvas,Next,"Curve / OK",focus.focused()==1,focus.pressed()==1);
  button(canvas,ZoomIn,"Zoom +",focus.focused()==2,focus.pressed()==2);
  button(canvas,ZoomOut,"Zoom -",focus.focused()==3,focus.pressed()==3);
}
void advance() {
  if(curve.progress().status!=Plot::Status::Running) return;
  Graphics::Screen output;auto sink=[&](int x,int y,int width,uint16_t color) { return output.span(x,y,width,color); };
  curve.step(64,function,[&](Graphics::Point a,Graphics::Point b) {
    return Graphics::line(PlotBox,a,b,Green,sink)==Graphics::Status::Ok;
  },[](){return false;});
  if(!output.flush()) message="Drawing failed";
  footer();drawTrace();
}
void redraw() {
  curve.cancel();Canvas canvas;canvas.fill({0,0,320,240},Theme::Paper);canvas.fill({0,0,320,28},Theme::Accent);
  canvas.text({10,7,180,14},"GRAPH EXPLORER",14,White,Theme::Accent);
  const char *title=mode==0?"sin(x)":mode==1?"1 / x":"Circle";
  canvas.text({225,7,85,14},title,length(title),White,Theme::Accent);
  range(canvas,31,"x: ",view.xMin,view.xMax);range(canvas,47,"y: ",view.yMin,view.yMax);
  canvas.fill(PlotBox,White);canvas.outline(PlotBox,Theme::Muted);
  Graphics::Screen output;auto sink=[&](int x,int y,int width,uint16_t color) { return output.span(x,y,width,color); };
  if(view.xMin<=0 && view.xMax>=0) Graphics::line(PlotBox,view.project({0,view.yMin},PlotBox),view.project({0,view.yMax},PlotBox),Theme::Selected,sink);
  if(view.yMin<=0 && view.yMax>=0) Graphics::line(PlotBox,view.project({view.xMin,0},PlotBox),view.project({view.xMax,0},PlotBox),Theme::Selected,sink);
  output.flush();
  controls();
  Plot::Options options;options.box=PlotBox;options.view=view;
  options.start=mode==2?0:view.xMin;options.end=mode==2?2*Math::Pi:view.xMax;
  if(!curve.begin(options)) message="View exceeds plot limits";
  advance();
}
void reset() { view=mode==2?Plot::View{-1.5,1.5,-1.5,1.5}:Plot::View{-5,5,-2,2};traced=false;message=Hint;redraw(); }
void action(unsigned id) {
  gestures.cancel();traced=false;message=Hint;
  if(id==1) { mode=(mode+1)%3;reset();return; }
  if(id==2 || id==3) { if(view.zoom(id==2?.5:2)) redraw();else { message="Zoom limit reached";footer(); } }
}
}
extern "C" void lefony_event(Lefony::Event event,uint32_t first,uint32_t second) {
  using namespace Lefony;
  if(event==Event::Start) { focus.add(1,Next);focus.add(2,ZoomIn);focus.add(3,ZoomOut);redraw();return; }
  if(event==Event::Close) { gestures.cancel();focus.cancel();curve.cancel();return; }
  InputSnapshot input;if(!UI::read({event,first,second},input)) return;
  auto gesture=gestures.update(input);
  if(event==Event::Tick) { if(gesture.kind==UI::GestureKind::LongPress) reset();else advance();return; }
  if(event==Event::Key) {
    focus.cancel();traced=false;message=Hint;
    if(input.key==InputKey::Confirm) { action(1);return; }
    if(input.key==InputKey::Plus || input.key==InputKey::Minus) { action(input.key==InputKey::Plus?2:3);return; }
    double dx=input.key==InputKey::Left?-.15:input.key==InputKey::Right?.15:0;
    double dy=input.key==InputKey::Up?.15:input.key==InputKey::Down?-.15:0;
    if((dx || dy) && view.pan(dx,dy)) redraw();
  }
  if(event==Event::Touch) {
    unsigned id=focus.touch(input.touchPhase,input.contactCount,input.contacts[0].x,input.contacts[0].y,input.flags&ContactsChanged);
    if(id) { action(id);return; }
    controls();
    if(gesture.kind==UI::GestureKind::Pan || gesture.kind==UI::GestureKind::Pinch) {
      Plot::View next=view;
      bool good=next.pan(-gesture.dx/(PlotBox.width-1),gesture.dy/(PlotBox.height-1));
      if(gesture.kind==UI::GestureKind::Pinch) {
        double factor=gesture.scale<.125?.125:gesture.scale>8?8:gesture.scale;
        double x=(gesture.x-PlotBox.x)/(PlotBox.width-1),y=1-(gesture.y-PlotBox.y)/(PlotBox.height-1);
        x=x<0?0:x>1?1:x;y=y<0?0:y>1?1:y;good=good && next.zoom(factor,x,y);
      }
      if(good) { view=next;traced=false;message=Hint;redraw(); }
    }
    if(gesture.kind==UI::GestureKind::Tap) {
      double x=view.xMin+(gesture.x-PlotBox.x)/(PlotBox.width-1)*(view.xMax-view.xMin);
      double y=view.yMax-(gesture.y-PlotBox.y)/(PlotBox.height-1)*(view.yMax-view.yMin);
      double parameter=mode==2?Math::atan2(y,x):x;trace=function(parameter);traced=true;
      static char status[64];char value[16];unsigned size=0;append(status,size,"Trace x=");fixed(value,trace.x);append(status,size,value);
      if(Numeric::finite(trace.y) && Numeric::abs(trace.y)<=1e6) { append(status,size," y=");fixed(value,trace.y);append(status,size,value); }
      else append(status,size," undefined / outside range");
      message=status;redraw();
    }
  }
}
