// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef SDK_LINEAR_CASES_H
#define SDK_LINEAR_CASES_H
#include <lefony/linear.h>
namespace LinearTests {
using namespace Lefony::Linear;
inline bool close(double a,double b,double tolerance=1e-9) { return Lefony::Numeric::finite(a) && Lefony::Numeric::abs(a-b)<=tolerance; }
template<unsigned N> bool dimensions(uint32_t &random) {
  for(unsigned trial=0;trial<20;trial++) {
    Matrix<N,N> a;Matrix<N,2> b,expected,result;
    for(unsigned r=0;r<N;r++) {
      expected.values[r][0]=static_cast<int>(r)-4;expected.values[r][1]=static_cast<int>(r)*2+1;
      for(unsigned c=0;c<N;c++) {
        random=random*1664525+1013904223;
        a.values[r][c]=static_cast<int>(random%15)-7;
      }
      a.values[r][r]+=N*16;
    }
    // Small integer A and X make construction of B exact in binary64.
    for(unsigned r=0;r<N;r++) for(unsigned column=0;column<2;column++)
      for(unsigned c=0;c<N;c++) b.values[r][column]+=a.values[r][c]*expected.values[c][column];
    if(solve(a,b,result)!=Status::Ok) return false;
    for(unsigned r=0;r<N;r++) for(unsigned c=0;c<2;c++) if(!close(result.values[r][c],expected.values[r][c])) return false;
    Matrix<N,N> inv,identity;
    if(inverse(a,inv)!=Status::Ok || multiply(a,inv,identity)!=Status::Ok) return false;
    for(unsigned r=0;r<N;r++) for(unsigned c=0;c<N;c++) if(!close(identity.values[r][c],r==c?1:0)) return false;
    if(solve(a,b,b)!=Status::Ok) return false;
    for(unsigned r=0;r<N;r++) for(unsigned c=0;c<2;c++) if(!close(b.values[r][c],expected.values[r][c])) return false;
  }
  return true;
}
inline bool test() {
  uint32_t random=0x40273125;
  if(!dimensions<1>(random) || !dimensions<2>(random) || !dimensions<3>(random) || !dimensions<4>(random) ||
     !dimensions<8>(random) || !dimensions<16>(random)) return false;
  Matrix<3,3> a{{{0,2,1},{1,-2,-3},{2,3,1}}};Matrix<3,1> b{{{3},{0},{7}}},result{{{42},{43},{44}}};
  if(solve(a,b,result)!=Status::Ok || !close(result.values[0][0],1) || !close(result.values[1][0],2) || !close(result.values[2][0],-1)) return false;
  Matrix<3,3> saved=a;
  if(transpose(a,a)!=Status::Ok || transpose(a,a)!=Status::Ok) return false;
  for(unsigned r=0;r<3;r++) for(unsigned c=0;c<3;c++) if(a.values[r][c]!=saved.values[r][c]) return false;
  if(a.at(3,0) || a.at(0,3) || a.at(UINT32_MAX,UINT32_MAX) || a.at(2,2)!=&a.values[2][2]) return false;
  unsigned checkpoints=0;
  if(solve(a,b,result,1e-12,[&](){checkpoints++;return false;})!=Status::Ok) return false;
  for(unsigned cut=1;cut<=checkpoints;cut++) {
    result.values[0][0]=42;result.values[1][0]=43;result.values[2][0]=44;unsigned step=0;
    if(solve(a,b,result,1e-12,[&](){return ++step==cut;})!=Status::Cancelled ||
       result.values[0][0]!=42 || result.values[1][0]!=43 || result.values[2][0]!=44) return false;
  }
  Matrix<2,2> singular{{{1,2},{2,4}}},out{{{9,8},{7,6}}};
  if(inverse(singular,out)!=Status::Singular || out.values[0][0]!=9) return false;
  singular.values[1][1]+=1e-14;
  if(inverse(singular,out)!=Status::Singular || out.values[1][1]!=6) return false;
  if(inverse(singular,out,0)!=Status::Invalid || inverse(singular,out,1)!=Status::Invalid ||
     inverse(singular,out,__builtin_nan(""))!=Status::Invalid) return false;
  singular.values[0][0]=__builtin_inf();
  if(inverse(singular,out)!=Status::Invalid || multiply(singular,out,out)!=Status::Invalid || transpose(singular,out)!=Status::Invalid) return false;
  Matrix<1,1> huge{{{1e308}}},tiny{{{1e-308}}},single{{{7}}};
  if(multiply(huge,huge,single)!=Status::Domain || single.values[0][0]!=7 ||
     solve(tiny,huge,single)!=Status::Domain || single.values[0][0]!=7) return false;
  Matrix<2,2> scale{{{1e100,0},{0,1e-100}}},right{{{1e100,0},{0,1e-100}}};
  if(solve(scale,right,out)!=Status::Ok || out.values[0][0]!=1 || out.values[1][1]!=1 || out.values[0][1]!=0 || out.values[1][0]!=0) return false;
  Matrix<2,2> identity{{{1,0},{0,1}}};
  if(multiply(identity,out,out,[](){return true;})!=Status::Cancelled || out.values[0][0]!=1) return false;
  return true;
}
}
#endif
