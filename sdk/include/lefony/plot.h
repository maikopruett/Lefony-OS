// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_PLOT_H
#define LEFONY_PLOT_H
#include "graphics.h"
namespace Lefony { namespace Plot {
using Graphics::Point;
struct View {
  double xMin=-5,xMax=5,yMin=-3,yMax=3;
  bool valid() const {
    return Numeric::finite(xMin) && Numeric::finite(xMax) && Numeric::finite(yMin) && Numeric::finite(yMax) &&
      xMin>=-1e6 && xMax<=1e6 && yMin>=-1e6 && yMax<=1e6 && xMax-xMin>=1e-6 && yMax-yMin>=1e-6;
  }
  bool pan(double dx,double dy) {
    if(!valid() || !Numeric::finite(dx) || !Numeric::finite(dy) || Numeric::abs(dx)>1 || Numeric::abs(dy)>1) return false;
    View next=*this;double x=(xMax-xMin)*dx,y=(yMax-yMin)*dy;
    next.xMin+=x;next.xMax+=x;next.yMin+=y;next.yMax+=y;
    if(!next.valid()) return false;
    *this=next;return true;
  }
  bool zoom(double factor,double anchorX=.5,double anchorY=.5) {
    if(!valid() || !Numeric::finite(factor) || factor<.125 || factor>8 ||
       !Numeric::finite(anchorX) || !Numeric::finite(anchorY) || anchorX<0 || anchorX>1 || anchorY<0 || anchorY>1) return false;
    double width=(xMax-xMin)*factor,height=(yMax-yMin)*factor;
    double x=xMin+(xMax-xMin)*anchorX,y=yMin+(yMax-yMin)*anchorY;
    View next{x-width*anchorX,x+width*(1-anchorX),y-height*anchorY,y+height*(1-anchorY)};
    if(!next.valid()) return false;
    *this=next;return true;
  }
  Point project(Point p,UI::Box box) const {
    box=Graphics::clip(box);
    if(!valid() || box.width<2 || box.height<2) return {__builtin_nan(""),__builtin_nan("")};
    return {box.x+(p.x-xMin)/(xMax-xMin)*(box.width-1),box.y+(yMax-p.y)/(yMax-yMin)*(box.height-1)};
  }
};
enum class Status { Idle, Running, Complete, Invalid, Limit, Cancelled, OutputFailed };
struct Progress { Status status;unsigned evaluations,segments,gaps,intervals,totalIntervals; };
struct Options {
  UI::Box box{0,0,320,240};View view{};double start=-5,end=5,tolerancePixels=1;
  unsigned intervals=32,maxDepth=6,maxEvaluations=4096;
};
// Adaptive midpoint-error sampler for y=f(x), parametric (x(t),y(t)), or polar
// functions converted to Point by the caller. Stack/state are fixed; step()
// evaluates at most 64 points and is intended to run over multiple callbacks.
// Midpoint testing is a rendering heuristic, not proof of continuity or a way
// to locate every narrow feature. Unresolved/invalid segments become gaps.
class Curve {
public:
  constexpr Curve() : m_options{},m_stack{},m_count(0),m_progress{Status::Idle,0,0,0,0,0},m_left{},m_haveLeft(false) {}
  bool begin(const Options &options) {
    UI::Box box=Graphics::clip(options.box);
    if(!options.view.valid() || box.width<2 || box.height<2 || !Numeric::finite(options.start) || !Numeric::finite(options.end) ||
       options.start < -1e6 || options.end>1e6 || options.start>=options.end || !Numeric::finite(options.tolerancePixels) ||
       options.tolerancePixels<.25 || options.tolerancePixels>16 || options.intervals<1 || options.intervals>256 ||
       options.maxDepth>8 || options.maxEvaluations<3 || options.maxEvaluations>4096) return false;
    m_options=options;m_options.box=box;m_count=0;m_haveLeft=false;
    m_progress={Status::Running,0,0,0,0,options.intervals};return true;
  }
  void cancel() { if(m_progress.status==Status::Running) m_progress.status=Status::Cancelled; }
  Progress progress() const { return m_progress; }
  template<typename Function,typename Emit,typename Cancel>
  Progress step(unsigned budget,Function function,Emit emit,Cancel cancelled) {
    if(budget>64) return {Status::Invalid,m_progress.evaluations,m_progress.segments,m_progress.gaps,m_progress.intervals,m_progress.totalIntervals};
    while(budget && m_progress.status==Status::Running) {
      if(cancelled()) { cancel();break; }
      if(!m_count && m_progress.intervals==m_options.intervals) { m_progress.status=Status::Complete;break; }
      if(m_progress.evaluations==m_options.maxEvaluations) { m_progress.status=Status::Limit;break; }
      if(!m_haveLeft) { m_left=sample(m_options.start,function);m_haveLeft=true;budget--;continue; }
      if(!m_count) {
        double fraction=double(m_progress.intervals+1)/m_options.intervals;
        Sample right=sample(m_options.start*(1-fraction)+m_options.end*fraction,function);budget--;
        m_stack[m_count++]={m_left,right,0};m_left=right;continue;
      }
      Segment segment=m_stack[--m_count];
      Sample middle=sample(segment.left.t/2+segment.right.t/2,function);budget--;
      bool all=segment.left.valid && segment.right.valid && middle.valid;
      double error=all?maximum(Numeric::abs(middle.point.x-(segment.left.point.x/2+segment.right.point.x/2)),
                               Numeric::abs(middle.point.y-(segment.left.point.y/2+segment.right.point.y/2))):1e100;
      if(all && error<=m_options.tolerancePixels) {
        if(!emit(segment.left.point,segment.right.point)) { m_progress.status=Status::OutputFailed;break; }
        m_progress.segments++;
      } else if(segment.depth<m_options.maxDepth && middle.t>segment.left.t && middle.t<segment.right.t &&
                (segment.left.valid || segment.right.valid || middle.valid)) {
        m_stack[m_count++]={middle,segment.right,segment.depth+1};
        m_stack[m_count++]={segment.left,middle,segment.depth+1};
      } else m_progress.gaps++;
      if(!m_count) m_progress.intervals++;
    }
    if(m_progress.status==Status::Running && !m_count && m_haveLeft && m_progress.intervals==m_options.intervals)
      m_progress.status=Status::Complete;
    return m_progress;
  }
private:
  struct Sample { double t;Point point;bool valid; };
  struct Segment { Sample left,right;unsigned depth; };
  static double maximum(double a,double b) { return a>b?a:b; }
  template<typename Function> Sample sample(double t,Function function) {
    Point point=function(t);m_progress.evaluations++;
    point=m_options.view.project(point,m_options.box);
    return {t,point,Graphics::coordinate(point.x) && Graphics::coordinate(point.y)};
  }
  Options m_options;Segment m_stack[9];unsigned m_count;Progress m_progress;Sample m_left;bool m_haveLeft;
};
}}
#endif
