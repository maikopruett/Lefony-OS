// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_MATH_H
#define LEFONY_MATH_H
#include "numeric.h"
namespace Lefony { namespace Math {
constexpr double Pi=3.141592653589793238462643383279502884;
constexpr double E=2.718281828459045235360287471352662498;
enum class Angle { Radians,Degrees,Gradians };
namespace Detail {
extern "C" {
double lefony_math_acos(double);double lefony_math_asin(double);double lefony_math_atan(double);
double lefony_math_atan2(double,double);double lefony_math_ceil(double);double lefony_math_copysign(double,double);
double lefony_math_cos(double);double lefony_math_erf(double);double lefony_math_erfc(double);
double lefony_math_exp(double);double lefony_math_expm1(double);double lefony_math_fabs(double);
double lefony_math_floor(double);double lefony_math_fmod(double,double);double lefony_math_frexp(double,int *);
double lefony_math_hypot(double,double);double lefony_math_log(double);double lefony_math_log1p(double);
double lefony_math_log10(double);double lefony_math_log2(double);double lefony_math_modf(double,double *);
double lefony_math_nextafter(double,double);double lefony_math_pow(double,double);double lefony_math_rint(double);
double lefony_math_round(double);double lefony_math_scalbn(double,int);double lefony_math_sin(double);
double lefony_math_sqrt(double);double lefony_math_tan(double);double lefony_math_trunc(double);
}
}
// IEEE-style scalar results. Domain errors can return NaN and overflow infinity;
// no exceptions/errno/global OS preferences. Check finite() or checked() when
// displaying a result. All linked code runs within the app's normal deadline.
inline bool finite(double x) { return Numeric::finite(x); }
inline double sin(double x) { return Detail::lefony_math_sin(x); }
inline double cos(double x) { return Detail::lefony_math_cos(x); }
inline double tan(double x) { return Detail::lefony_math_tan(x); }
inline double asin(double x) { return Detail::lefony_math_asin(x); }
inline double acos(double x) { return Detail::lefony_math_acos(x); }
inline double atan(double x) { return Detail::lefony_math_atan(x); }
inline double atan2(double y,double x) { return Detail::lefony_math_atan2(y,x); }
inline double sqrt(double x) { return Detail::lefony_math_sqrt(x); }
inline double exp(double x) { return Detail::lefony_math_exp(x); }
inline double expm1(double x) { return Detail::lefony_math_expm1(x); }
inline double log(double x) { return Detail::lefony_math_log(x); }
inline double log1p(double x) { return Detail::lefony_math_log1p(x); }
inline double log10(double x) { return Detail::lefony_math_log10(x); }
inline double log2(double x) { return Detail::lefony_math_log2(x); }
inline double pow(double x,double y) { return Detail::lefony_math_pow(x,y); }
inline double hypot(double x,double y) { return Detail::lefony_math_hypot(x,y); }
inline double erf(double x) { return Detail::lefony_math_erf(x); }
inline double erfc(double x) { return Detail::lefony_math_erfc(x); }
inline double abs(double x) { return Detail::lefony_math_fabs(x); }
inline double floor(double x) { return Detail::lefony_math_floor(x); }
inline double ceil(double x) { return Detail::lefony_math_ceil(x); }
inline double trunc(double x) { return Detail::lefony_math_trunc(x); }
inline double round(double x) { return Detail::lefony_math_round(x); }
inline double fmod(double x,double y) { return Detail::lefony_math_fmod(x,y); }
inline double copySign(double x,double y) { return Detail::lefony_math_copysign(x,y); }
inline double nextAfter(double x,double y) { return Detail::lefony_math_nextafter(x,y); }
inline double scale(double x,int exponent) { return Detail::lefony_math_scalbn(x,exponent); }
inline double fraction(double x,double &whole) { return Detail::lefony_math_modf(x,&whole); }
inline double fractionExponent(double x,int &exponent) { return Detail::lefony_math_frexp(x,&exponent); }
inline double radians(double x,Angle angle) { return angle==Angle::Radians?x:angle==Angle::Degrees?x*(Pi/180):angle==Angle::Gradians?x*(Pi/200):__builtin_nan(""); }
inline double degrees(double x) { return x*(180/Pi); }
inline double gradians(double x) { return x*(200/Pi); }
struct Checked { Numeric::Status status;double value; };
inline Checked checked(double value) { return {finite(value)?Numeric::Status::Ok:Numeric::Status::Domain,value}; }
}}
#endif
