/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#ifndef LEFONY_NUMBER_FORMAT_H
#define LEFONY_NUMBER_FORMAT_H
#include <stdint.h>
#include <stdio.h>
#include <string.h>
enum LefonyNumberFormat { LEFONY_FORMAT_AUTO=0, LEFONY_FORMAT_SCIENTIFIC=1, LEFONY_FORMAT_ENGINEERING=2 };
enum LefonyNumberFormatError { LEFONY_FORMAT_INVALID=1, LEFONY_FORMAT_TOO_SMALL=2, LEFONY_FORMAT_NONFINITE=3 };
/* App-linked newlib-profile helper, C locale. Format finite binary64 with 1..14
 * significant digits. AUTO uses %g; SCIENTIFIC uses %e; ENGINEERING uses that
 * same rounded significand with an exponent divisible by three. Negative zero
 * is preserved. Returns bytes excluding NUL, or a negative error; failures leave
 * the destination unchanged. Does not read or change OS/global preferences. */
static inline int32_t lefony_format_number(char *destination,uint32_t capacity,double value,
                                         uint32_t digits,uint32_t format) {
  if(!destination || !digits || digits>14 || format>LEFONY_FORMAT_ENGINEERING) return -LEFONY_FORMAT_INVALID;
  if(!__builtin_isfinite(value)) return -LEFONY_FORMAT_NONFINITE;
  char scientific[64],result[64];int count;
  if(format!=LEFONY_FORMAT_ENGINEERING) {
    count=snprintf(result,sizeof(result),format==LEFONY_FORMAT_AUTO?"%.*g":"%.*e",
                   (int)(format==LEFONY_FORMAT_AUTO?digits:digits-1),value);
  } else {
    count=snprintf(scientific,sizeof(scientific),"%.*e",(int)digits-1,value);
    if(count<0 || count>=(int)sizeof(scientific)) return -LEFONY_FORMAT_INVALID;
    char significand[14];unsigned at=0,n=0,used=0;
    if(scientific[at]=='-') {result[used++]='-';at++;}
    while(scientific[at] && scientific[at]!='e') {
      char c=scientific[at++];if(c=='.') continue;
      if(c<'0' || c>'9' || n>=sizeof(significand)) return -LEFONY_FORMAT_INVALID;
      significand[n++]=c;
    }
    if(scientific[at++]!='e' || n!=digits) return -LEFONY_FORMAT_INVALID;
    int sign=scientific[at]=='-'?-1:1;
    if(scientific[at]!='-' && scientific[at]!='+') return -LEFONY_FORMAT_INVALID;
    at++;int exponent=0;unsigned exponentDigits=0;
    while(scientific[at]) {
      char c=scientific[at++];if(c<'0' || c>'9' || ++exponentDigits>3) return -LEFONY_FORMAT_INVALID;
      exponent=exponent*10+c-'0';
    }
    if(!exponentDigits) return -LEFONY_FORMAT_INVALID;
    exponent*=sign;
    int engineering=exponent>=0?exponent/3*3:-((-exponent+2)/3)*3;
    unsigned whole=(unsigned)(exponent-engineering+1);
    for(unsigned i=0;i<whole;i++) result[used++]=i<n?significand[i]:'0';
    if(n>whole) {result[used++]='.';for(unsigned i=whole;i<n;i++) result[used++]=significand[i];}
    int suffix=snprintf(result+used,sizeof(result)-used,"e%+d",engineering);
    if(suffix<0 || (unsigned)suffix>=sizeof(result)-used) return -LEFONY_FORMAT_INVALID;
    count=(int)used+suffix;
  }
  if(count<0 || count>=(int)sizeof(result)) return -LEFONY_FORMAT_INVALID;
  if((uint32_t)count>=capacity) return -LEFONY_FORMAT_TOO_SMALL;
  memcpy(destination,result,(unsigned)count+1);return count;
}
#endif
