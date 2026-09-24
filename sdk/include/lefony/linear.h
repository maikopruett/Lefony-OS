// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_LINEAR_H
#define LEFONY_LINEAR_H
#include "numeric.h"
namespace Lefony { namespace Linear {
enum class Status { Ok, Invalid, Domain, Singular, Cancelled };
// Fixed dimensions keep every work buffer bounded; no heap or OS pointers.
template<unsigned Rows,unsigned Columns> struct Matrix {
  static_assert(Rows>0 && Rows<=16 && Columns>0 && Columns<=16,"matrix dimensions must be 1..16");
  double values[Rows][Columns]{};
  double *at(unsigned row,unsigned column) { return row<Rows && column<Columns?&values[row][column]:nullptr; }
  const double *at(unsigned row,unsigned column) const { return row<Rows && column<Columns?&values[row][column]:nullptr; }
  bool finite() const { for(const auto &row:values) for(double x:row) if(!Numeric::finite(x)) return false;return true; }
};
struct NeverCancel { bool operator()() const { return false; } };
// All outputs remain unchanged on any failure, including cancellation. Aliased
// input/output is supported. Cancellation is checked before each output row.
template<unsigned R,unsigned K,unsigned C,typename Cancel=NeverCancel>
Status multiply(const Matrix<R,K> &a,const Matrix<K,C> &b,Matrix<R,C> &out,Cancel cancel={}) {
  if(!a.finite() || !b.finite()) return Status::Invalid;
  Matrix<R,C> result;
  for(unsigned row=0;row<R;row++) {
    if(cancel()) return Status::Cancelled;
    for(unsigned column=0;column<C;column++) {
      double value=0;
      for(unsigned k=0;k<K;k++) value+=a.values[row][k]*b.values[k][column];
      if(!Numeric::finite(value)) return Status::Domain;
      result.values[row][column]=value;
    }
  }
  out=result;return Status::Ok;
}
template<unsigned R,unsigned C> Status transpose(const Matrix<R,C> &a,Matrix<C,R> &out) {
  if(!a.finite()) return Status::Invalid;
  Matrix<C,R> result;
  for(unsigned r=0;r<R;r++) for(unsigned c=0;c<C;c++) result.values[c][r]=a.values[r][c];
  out=result;return Status::Ok;
}
// Scaled partial-pivot Gaussian elimination for AX=B. Relative pivot tolerance
// is explicit and finite in (0,1). Singular also covers rejected near-singular
// systems; callers must not interpret a solution as a conditioning guarantee.
// Maximum solve scratch: 4224 bytes for N=RHS=16, plus local scalars.
template<unsigned N,unsigned RHS,typename Cancel=NeverCancel>
Status solve(const Matrix<N,N> &matrix,const Matrix<N,RHS> &right,Matrix<N,RHS> &out,
             double tolerance=1e-12,Cancel cancel={}) {
  if(!matrix.finite() || !right.finite() || !Numeric::finite(tolerance) || tolerance<=0 || tolerance>=1) return Status::Invalid;
  Matrix<N,N> a=matrix;Matrix<N,RHS> b=right;double scale[N]{};
  for(unsigned r=0;r<N;r++) {
    if(cancel()) return Status::Cancelled;
    for(unsigned c=0;c<N;c++) { double x=Numeric::abs(a.values[r][c]);if(x>scale[r]) scale[r]=x; }
    if(!scale[r]) return Status::Singular;
  }
  for(unsigned k=0;k<N;k++) {
    if(cancel()) return Status::Cancelled;
    unsigned pivot=k;double largest=0;
    for(unsigned r=k;r<N;r++) {
      double score=Numeric::abs(a.values[r][k])/scale[r];
      if(score>largest) { largest=score;pivot=r; }
    }
    if(largest<=tolerance) return Status::Singular;
    if(pivot!=k) {
      for(unsigned c=0;c<N;c++) { double x=a.values[k][c];a.values[k][c]=a.values[pivot][c];a.values[pivot][c]=x; }
      for(unsigned c=0;c<RHS;c++) { double x=b.values[k][c];b.values[k][c]=b.values[pivot][c];b.values[pivot][c]=x; }
      double x=scale[k];scale[k]=scale[pivot];scale[pivot]=x;
    }
    for(unsigned r=k+1;r<N;r++) {
      if(cancel()) return Status::Cancelled;
      double factor=a.values[r][k]/a.values[k][k];
      if(!Numeric::finite(factor)) return Status::Domain;
      a.values[r][k]=0;
      for(unsigned c=k+1;c<N;c++) {
        a.values[r][c]-=factor*a.values[k][c];
        if(!Numeric::finite(a.values[r][c])) return Status::Domain;
      }
      for(unsigned c=0;c<RHS;c++) {
        b.values[r][c]-=factor*b.values[k][c];
        if(!Numeric::finite(b.values[r][c])) return Status::Domain;
      }
    }
  }
  for(unsigned next=N;next;next--) {
    if(cancel()) return Status::Cancelled;
    unsigned r=next-1;
    for(unsigned c=0;c<RHS;c++) {
      double x=b.values[r][c];
      for(unsigned k=r+1;k<N;k++) x-=a.values[r][k]*b.values[k][c];
      x/=a.values[r][r];if(!Numeric::finite(x)) return Status::Domain;
      b.values[r][c]=x;
    }
  }
  out=b;return Status::Ok;
}
template<unsigned N,typename Cancel=NeverCancel>
Status inverse(const Matrix<N,N> &a,Matrix<N,N> &out,double tolerance=1e-12,Cancel cancel={}) {
  Matrix<N,N> identity;for(unsigned i=0;i<N;i++) identity.values[i][i]=1;
  return solve(a,identity,out,tolerance,cancel);
}
}}
#endif
