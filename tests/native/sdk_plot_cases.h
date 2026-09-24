// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef SDK_PLOT_CASES_H
#define SDK_PLOT_CASES_H
#include <lefony/plot.h>
namespace PlotTests {
using namespace Lefony::Plot;
inline bool test() {
  View view{-1,1,-1,1};
  if(!view.valid() || !view.pan(.25,-.25) || view.xMin!=-.5 || view.yMax!=.5) return false;
  if(!view.zoom(.5) || view.xMin!=0 || view.xMax!=1 || view.yMin!=-1 || view.yMax!=0) return false;
  if(view.pan(2,0) || view.zoom(__builtin_nan("")) || view.zoom(1,-1,.5) || view.xMax!=1) return false;
  view={-1,1,-1,1};Point origin=view.project({0,0},{0,0,320,240});
  if(origin.x!=159.5 || origin.y!=119.5) return false;
  if(Lefony::Numeric::finite(view.project({0,0},{INT32_MAX,INT32_MIN,INT32_MIN,INT32_MAX}).x)) return false;
  Curve curve;Options options;options.start=-1;options.end=1;options.view={-1,1,-1,1};options.intervals=8;
  if(!curve.begin(options)) return false;
  unsigned evaluated=0,emitted=0;
  auto square=[&](double x) { evaluated++;return Point{x,x*x}; };
  auto draw=[&](Point a,Point b) {
    emitted++;
    double middle=(a.x+b.x)/2,worldX=middle/319*2-1,expectedY=(1-worldX*worldX)*239/2;
    return a.x<=b.x && Lefony::Numeric::abs((a.y+b.y)/2-expectedY)<=1.00001;
  };
  for(unsigned i=0;i<4096 && curve.progress().status==Status::Running;i++) {
    unsigned before=evaluated;curve.step(3,square,draw,[](){return false;});
    if(evaluated-before>3) return false;
  }
  auto result=curve.progress();
  if(result.status!=Status::Complete || result.evaluations!=evaluated || result.segments!=emitted || result.gaps || emitted<=8) return false;
  unsigned before=evaluated;curve.step(3,square,draw,[](){return false;});if(evaluated!=before) return false;
  options.maxEvaluations=3;curve.begin(options);
  curve.step(64,square,draw,[](){return false;});
  if(curve.progress().status!=Status::Limit || curve.progress().evaluations!=3) return false;
  options.maxEvaluations=4096;curve.begin(options);
  if(curve.step(65,square,draw,[](){return false;}).status!=Status::Invalid || curve.progress().evaluations) return false;
  if(curve.step(1,square,draw,[](){return true;}).status!=Status::Cancelled || curve.progress().evaluations) return false;
  curve.begin(options);
  auto fail=[](Point,Point) { return false; };
  curve.step(64,square,fail,[](){return false;});if(curve.progress().status!=Status::OutputFailed) return false;
  curve.begin(options);
  bool bridged=false;
  auto reciprocal=[](double t) { return Point{t,t==0?__builtin_nan(""):1/t}; };
  auto gaps=[&](Point a,Point b) { if(a.x<159.5 && b.x>159.5) bridged=true;return true; };
  for(unsigned i=0;i<4096 && curve.progress().status==Status::Running;i++) curve.step(7,reciprocal,gaps,[](){return false;});
  if(curve.progress().status!=Status::Complete || !curve.progress().gaps || bridged) return false;
  curve.begin(options);
  auto invalid=[](double t) { return Point{t,__builtin_nan("")}; };
  for(unsigned i=0;i<64 && curve.progress().status==Status::Running;i++) curve.step(2,invalid,gaps,[](){return false;});
  if(curve.progress().status!=Status::Complete || curve.progress().segments || curve.progress().gaps!=8) return false;
  Options bad=options;bad.maxDepth=9;
  if(curve.begin(bad) || curve.progress().status!=Status::Complete) return false;
  // Deep alternating data stresses the bounded depth-first stack and budget.
  options.maxDepth=8;options.intervals=1;options.maxEvaluations=4096;curve.begin(options);
  uint32_t random=9811;
  auto jagged=[&](double t) { random=random*1664525+1013904223;return Point{t,static_cast<double>(random%1000)/500-1}; };
  for(unsigned i=0;i<4096 && curve.progress().status==Status::Running;i++) curve.step(1,jagged,gaps,[](){return false;});
  return curve.progress().status==Status::Complete && curve.progress().evaluations<=1025 && curve.progress().gaps>0;
}
}
#endif
