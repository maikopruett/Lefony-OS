// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/expression.h>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <limits>
using namespace Lefony::Expression;
static Evaluated evaluate(Context &context,const char *source) {
  auto parsed=context.parse(source,strlen(source));assert(parsed.status==Status::Ok);
  return context.evaluate(parsed.expression);
}
static void answer(Context &context,const char *source,double expected) {
  auto result=evaluate(context,source);assert(result.status==Status::Ok);
  assert(std::abs(result.value-expected)<=1e-12*std::max(1.,std::abs(expected)));
}
int main() {
  Context a,b;
  answer(a,"2+3*4",14);answer(a,"(2+3)*4",20);answer(a,"-2^2",-4);
  answer(a,"2^3^2",512);answer(a,"2^-2",.25);answer(a,"-(-7)",7);
  answer(a,"sqrt(2)^2",2);answer(a,"abs(-1.25)+2.5e-2",1.275);
  answer(a,"1e-308 * 1e308",1);answer(a,"8/2/2",2);answer(a,"1--2",3);
  answer(a,"sin(pi/6)+cos(pi/3)",1);answer(a,"ln(e)+log10(100)+log2(8)",6);
  answer(a,"2^0.5",std::sqrt(2.));answer(a,"2^33",8589934592.);
  answer(a,"exp(2)",std::exp(2.));answer(a,"asin(0.5)",std::asin(.5));
  answer(a,"acos(0.5)+atan(1)",std::acos(.5)+std::atan(1.));
  answer(a,"tan(.5)+erf(1)",std::tan(.5)+std::erf(1.));
  answer(a,"floor(-.5)+ceil(.5)+round(-.5)",-1);
  assert(a.angle()==Lefony::Math::Angle::Radians);
  assert(a.angle(Lefony::Math::Angle::Degrees));
  answer(a,"sin(30)+cos(60)",1);answer(a,"asin(.5)+acos(.5)+atan(1)",135);
  assert(!a.angle(static_cast<Lefony::Math::Angle>(77)) && a.angle()==Lefony::Math::Angle::Degrees);
  assert(a.angle(Lefony::Math::Angle::Gradians));
  answer(a,"sin(100)+cos(200)+tan(50)",1);
  answer(a,"asin(1)+acos(-1)+atan(1)",350);
  assert(std::abs(Lefony::Math::radians(200,Lefony::Math::Angle::Gradians)-Lefony::Math::Pi)<1e-15);
  assert(std::abs(Lefony::Math::gradians(Lefony::Math::Pi)-200)<1e-12);
  assert(a.angle(Lefony::Math::Angle::Radians));
  assert(a.set("x",7));assert(b.set("x",9));answer(a,"x*x+2",51);answer(b,"x*x+2",83);
  assert(!a.set("abs",1) && !a.set("sqrt",1) && !a.set("",1) && !a.set("0a",1));
  assert(!a.set("pi",1) && !a.set("e",1) && !a.set("log10",1));
  assert(a.set("a0",4));answer(a,"a0+1",5);
  assert(!a.set("x",std::numeric_limits<double>::infinity()));answer(a,"x",7);
  a.clearVariables();assert(evaluate(a,"x").status==Status::Unbound);
  for(unsigned i=0;i<16;i++) { char name[3]={'v',static_cast<char>('a'+i),0};assert(a.set(name,i)); }
  assert(!a.set("overflow",1));assert(a.set("va",17));answer(a,"va",17);
  auto saved=a.parse("3+4",3);assert(saved.status==Status::Ok);
  assert(b.evaluate(saved.expression).status==Status::Stale);
  assert(a.parse("?",1).status==Status::Invalid);assert(a.evaluate(saved.expression).status==Status::Stale);
  for(const char *source:{"", ".", "1e", "1e-", "1..2", "1 2", "(1", "1)", "1/", "sqrt()", "abs", "x_1", "2x"})
    assert(a.parse(source,strlen(source)).status==Status::Invalid);
  assert(a.parse("gamma(2)",8).status==Status::Unsupported);
  assert(a.parse("abcdefghijklmnop",16).status==Status::Limit);
  assert(a.parse("1e309",5).status==Status::Limit);
  assert(a.parse(nullptr,1).status==Status::Invalid);
  std::string deep(17,'(');deep+="1";deep+=std::string(17,')');
  assert(a.parse(deep.data(),deep.size()).status==Status::Limit);
  std::string longSource(257,'1');assert(a.parse(longSource.data(),longSource.size()).status==Status::Limit);
  for(const char *source:{"1/0", "sqrt(-1)", "0^0", "0^-1", "1e308*1e308", "(-2)^.5", "ln(0)", "ln(-1)", "exp(1000)", "asin(2)", "acos(-2)"})
    assert(evaluate(a,source).status==Status::Domain);
  auto parsed=a.parse("1+2+3+4+5",9);unsigned calls=0;
  auto cancelled=a.evaluate(parsed.expression,[&](){return ++calls==4;});
  assert(cancelled.status==Status::Cancelled && cancelled.steps==3);
  answer(a,"3+4",7);
  // Repeated malformed and arbitrary bounded text must neither overrun the
  // parser nor bypass expression ownership, node or depth limits.
  uint32_t random=0x913fc091;const char alphabet[]="0123456789.+-*/^()eE abcxyzsqrt?\x80";
  for(unsigned trial=0;trial<10000;trial++) {
    std::string source;random=random*1664525+1013904223;unsigned size=random%300;
    for(unsigned i=0;i<size;i++) { random=random*1664525+1013904223;source+=alphabet[random%(sizeof(alphabet)-1)]; }
    auto result=a.parse(source.data(),source.size());
    if(result.status==Status::Ok) {
      auto value=a.evaluate(result.expression);assert(value.steps<=Context::MaximumNodes);
      if(value.status==Status::Ok) assert(std::isfinite(value.value));
    }
  }
  printf("{\"status\":\"passed\",\"context_bytes\":%zu,\"maximum_source_bytes\":%u,\"maximum_nodes\":%u,\"maximum_depth\":%u,\"fuzz_cases\":10000}\n",
         sizeof(Context),Context::MaximumSource,Context::MaximumNodes,Context::MaximumDepth);
}
