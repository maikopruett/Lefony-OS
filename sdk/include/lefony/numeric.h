// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_NUMERIC_H
#define LEFONY_NUMERIC_H
#include <stdint.h>
namespace Lefony { namespace Numeric {
enum class Status { Ok, Empty, Invalid, Domain, Limit, Cancelled };
inline bool finite(double x) { return __builtin_isfinite(x); }
inline double abs(double x) { return x<0?-x:x; }
// Welford's algorithm. Rejected samples leave the accumulator unchanged.
class Statistics {
public:
  constexpr Statistics() : m_count(0),m_mean(0),m_m2(0),m_min(0),m_max(0) {}
  Status add(double x) {
    if(!finite(x)) return Status::Invalid;
    if(m_count==65536) return Status::Limit;
    double delta=x-m_mean,mean=m_mean+delta/(m_count+1),m2=m_m2+delta*(x-mean);
    if(!finite(mean) || !finite(m2)) return Status::Domain;
    if(!m_count || x<m_min) m_min=x;
    if(!m_count || x>m_max) m_max=x;
    m_count++;m_mean=mean;m_m2=m2;return Status::Ok;
  }
  uint32_t count() const { return m_count; }
  Status mean(double &out) const { if(!m_count) return Status::Empty;out=m_mean;return Status::Ok; }
  Status variance(double &out,bool sample=true) const {
    if(m_count<(sample?2u:1u)) return Status::Empty;
    out=m_m2/(m_count-(sample?1:0));return Status::Ok;
  }
  Status range(double &low,double &high) const { if(!m_count) return Status::Empty;low=m_min;high=m_max;return Status::Ok; }
private:
  uint32_t m_count;double m_mean,m_m2,m_min,m_max;
};
struct Root { Status status;double value;uint32_t iterations; };
// Callbacks are app-side and subject to the normal app deadline. This routine
// requires a continuous function and a sign-changing finite bracket. It does
// not certify continuity; convergence also requires a small residual.
template<typename Function,typename Cancel> Root bisect(Function f,double low,double high,double tolerance,uint32_t limit,Cancel cancel) {
  if(!finite(low) || !finite(high) || low>=high || !finite(tolerance) || tolerance<=0 || !limit || limit>256) return {Status::Invalid,0,0};
  if(cancel()) return {Status::Cancelled,0,0};
  double a=f(low),b=f(high);
  if(!finite(a) || !finite(b)) return {Status::Domain,0,0};
  if(a==0) return {Status::Ok,low,0};
  if(b==0) return {Status::Ok,high,0};
  if((a<0)==(b<0)) return {Status::Domain,0,0};
  double mid=low;
  for(uint32_t i=0;i<limit;i++) {
    if(cancel()) return {Status::Cancelled,mid,i};
    mid=low/2+high/2;
    double value=f(mid);
    if(!finite(value)) return {Status::Domain,mid,i+1};
    if(abs(value)<=tolerance) return {Status::Ok,mid,i+1};
    if(mid==low || mid==high) return {Status::Limit,mid,i+1};
    if((value<0)==(a<0)) { low=mid;a=value; }else high=mid;
  }
  return {Status::Limit,mid,limit};
}
}}
#endif
