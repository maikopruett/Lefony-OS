/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#include <lefony/number_format.h>
#include <float.h>
#include <math.h>
#include <string.h>
struct Case {double value;unsigned digits,format;const char *expected;};
static const struct Case cases[]={
  {0,3,0,"0"},{-0.0,3,0,"-0"},{-0.0,3,1,"-0.00e+00"},{-0.0,3,2,"-0.00e+0"},
  {123456,4,0,"1.235e+05"},{123456,4,1,"1.235e+05"},{123456,4,2,"123.5e+3"},
  {1234,3,2,"1.23e+3"},{12.5,4,2,"12.50e+0"},{123,1,2,"100e+0"},
  {.0125,4,2,"12.50e-3"},{.125,3,2,"125e-3"},{.9999,3,2,"1.00e+0"},
  {9.999e-4,3,2,"1.00e-3"},{1e308,3,2,"100e+306"},
  {DBL_MAX,14,2,"179.76931348623e+306"},{0x1p-1074,2,2,"4.9e-324"},
  {1e-308,3,2,"10.0e-309"},{1.23456789,7,0,"1.234568"},
  {-12345.0,5,2,"-12.345e+3"}
};
int main(void) {
  char output[64],before[64];
  for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
    const struct Case *c=&cases[i];unsigned n=strlen(c->expected);
    if(lefony_format_number(output,sizeof(output),c->value,c->digits,c->format)!=(int)n || strcmp(output,c->expected)) return 100+i;
    memset(output,0x5a,sizeof(output));memcpy(before,output,sizeof(output));
    if(lefony_format_number(output,n,c->value,c->digits,c->format)!=-LEFONY_FORMAT_TOO_SMALL || memcmp(output,before,sizeof(output))) return 200+i;
    if(lefony_format_number(output,n+1,c->value,c->digits,c->format)!=(int)n || strcmp(output,c->expected) || output[n+1]!=0x5a) return 300+i;
  }
  memset(output,0x5a,sizeof(output));memcpy(before,output,sizeof(output));
  if(lefony_format_number(output,sizeof(output),1,0,0)!=-LEFONY_FORMAT_INVALID ||
     lefony_format_number(output,sizeof(output),1,15,0)!=-LEFONY_FORMAT_INVALID ||
     lefony_format_number(output,sizeof(output),1,1,3)!=-LEFONY_FORMAT_INVALID ||
     lefony_format_number(NULL,20,1,1,0)!=-LEFONY_FORMAT_INVALID ||
     lefony_format_number(output,0,1,1,0)!=-LEFONY_FORMAT_TOO_SMALL ||
     lefony_format_number(output,sizeof(output),NAN,3,0)!=-LEFONY_FORMAT_NONFINITE ||
     lefony_format_number(output,sizeof(output),INFINITY,3,1)!=-LEFONY_FORMAT_NONFINITE ||
     lefony_format_number(output,sizeof(output),-INFINITY,3,2)!=-LEFONY_FORMAT_NONFINITE ||
     memcmp(output,before,sizeof(output))) return 400;
  return 0;
}
