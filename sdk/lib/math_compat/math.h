// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Private C adaptation header. This is not a general libc math.h for apps.
#ifndef LEFONY_MATH_COMPAT_H
#define LEFONY_MATH_COMPAT_H
#include <stdint.h>
#include <float.h>
_Static_assert(sizeof(double)==8 && DBL_MANT_DIG==53,"math requires IEEE binary64");
#define acos lefony_math_acos
#define asin lefony_math_asin
#define atan lefony_math_atan
#define atan2 lefony_math_atan2
#define ceil lefony_math_ceil
#define copysign lefony_math_copysign
#define cos lefony_math_cos
#define erf lefony_math_erf
#define erfc lefony_math_erfc
#define exp lefony_math_exp
#define expm1 lefony_math_expm1
#define fabs lefony_math_fabs
#define floor lefony_math_floor
#define fmod lefony_math_fmod
#define frexp lefony_math_frexp
#define hypot lefony_math_hypot
#define log lefony_math_log
#define log1p lefony_math_log1p
#define log10 lefony_math_log10
#define log2 lefony_math_log2
#define modf lefony_math_modf
#define nextafter lefony_math_nextafter
#define pow lefony_math_pow
#define rint lefony_math_rint
#define round lefony_math_round
#define scalbn lefony_math_scalbn
#define sin lefony_math_sin
#define sqrt lefony_math_sqrt
#define tan lefony_math_tan
#define trunc lefony_math_trunc
#define __ieee754_rem_pio2 lefony_math_rem_pio2
#define __kernel_rem_pio2 lefony_math_kernel_rem_pio2
#define __kernel_sin lefony_math_kernel_sin
#define __kernel_cos lefony_math_kernel_cos
#define __kernel_tan lefony_math_kernel_tan
#define HUGE_VAL __builtin_huge_val()
#define INFINITY __builtin_inff()
#define NAN __builtin_nanf("")
#define isnan(x) __builtin_isnan(x)
#define isinf(x) __builtin_isinf(x)
#define isfinite(x) __builtin_isfinite(x)
#define finite(x) __builtin_isfinite(x)
#define signbit(x) __builtin_signbit(x)
#define M_PI 3.14159265358979323846
#define M_PI_2 1.57079632679489661923
#define M_LN2 0.69314718055994530942
double acos(double);double asin(double);double atan(double);double atan2(double,double);
double ceil(double);double copysign(double,double);double cos(double);
double erf(double);double erfc(double);double exp(double);double expm1(double);
double fabs(double);double floor(double);double fmod(double,double);double frexp(double,int *);
double hypot(double,double);double log(double);double log1p(double);double log10(double);double log2(double);
double modf(double,double *);double nextafter(double,double);double pow(double,double);
double rint(double);double round(double);double scalbn(double,int);double sin(double);double sqrt(double);double tan(double);double trunc(double);
#endif
