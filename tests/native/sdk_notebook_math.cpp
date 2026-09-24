// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/expression.h>
#include <lefony/number_format.h>
#include <string.h>
using namespace Lefony;
struct Case {Math::Angle angle;const char *source;double expected;};
static const Case cases[]={
  {Math::Angle::Radians,"sin(pi/6)+cos(pi/3)",1},
  {Math::Angle::Radians,"asin(1)+acos(-1)+atan(1)",Math::Pi*1.75},
  {Math::Angle::Degrees,"sin(30)+cos(60)",1},
  {Math::Angle::Degrees,"asin(1)+acos(-1)+atan(1)",315},
  {Math::Angle::Gradians,"sin(100)+cos(200)+tan(50)",1},
  {Math::Angle::Gradians,"asin(1)+acos(-1)+atan(1)",350},
  {Math::Angle::Gradians,"sin(-100)+cos(400)",0},
  {Math::Angle::Gradians,"2^3^2",512},
  {Math::Angle::Degrees,"sqrt(2)^2",2},
  {Math::Angle::Radians,"ln(e)+log10(100)+log2(8)",6}
};
int main() {
  Expression::Context math;
  for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
    const auto &c=cases[i];if(!math.angle(c.angle)) return 100+i;
    auto parsed=math.parse(c.source,strlen(c.source));if(parsed.status!=Expression::Status::Ok) return 200+i;
    auto answer=math.evaluate(parsed.expression);
    if(answer.status!=Expression::Status::Ok || Numeric::abs(answer.value-c.expected)>1e-12*(1+Numeric::abs(c.expected))) return 300+i;
  }
  if(math.angle(static_cast<Math::Angle>(77)) || math.angle()!=Math::Angle::Radians) return 400;
  auto parsed=math.parse("sqrt(-1)",8);
  if(parsed.status!=Expression::Status::Ok || math.evaluate(parsed.expression).status!=Expression::Status::Domain) return 401;
  parsed=math.parse("gamma(2)",8);if(parsed.status!=Expression::Status::Unsupported) return 402;
  parsed=math.parse("unknown+1",9);if(parsed.status!=Expression::Status::Ok || math.evaluate(parsed.expression).status!=Expression::Status::Unbound) return 403;
  if(Numeric::abs(Math::radians(200,Math::Angle::Gradians)-Math::Pi)>1e-15 || Numeric::abs(Math::gradians(Math::Pi)-200)>1e-12) return 404;
  char text[64];if(lefony_format_number(text,sizeof(text),Math::Pi,9,LEFONY_FORMAT_AUTO)!=10 || strcmp(text,"3.14159265")) return 405;
  return 0;
}
