// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
namespace NativeApps {
// Stable, versioned names: built-ins use #name; installed apps use their ID.
// Unknown/removed apps are ignored and new apps append in their default order.
class HomeOrder {
public:
  static constexpr int Capacity=544;
  static constexpr size_t MaximumBytes=8+Capacity*50;
  void reset(const char *const *keys,int count,const void *saved,size_t size) {
    m_keys=keys;m_count=count<Capacity?count:Capacity;
    for(int i=0;i<m_count;i++) m_indices[i]=i;
    if(!saved || size<8 || size>MaximumBytes || memcmp(saved,"LFHO\1\0\0\0",8)) return;
    auto bytes=static_cast<const char *>(saved);size_t offset=8;int placed=0;
    // Validate all strings before accepting any of the record.
    while(offset<size) {
      size_t n=0;while(offset+n<size && bytes[offset+n] && n<50) n++;
      if(!n || n>=50 || offset+n>=size) return;
      offset+=n+1;
    }
    for(offset=8;offset<size;offset+=strlen(bytes+offset)+1) {
      for(int i=placed;i<m_count;i++) if(!strcmp(keys[m_indices[i]],bytes+offset)) {
        move(i,placed++);break;
      }
    }
  }
  int at(int position) const {return position>=0 && position<m_count?m_indices[position]:-1;}
  bool move(int from,int to) {
    if(from<0 || to<0 || from>=m_count || to>=m_count) return false;
    int index=m_indices[from];
    for(int i=from;i!=to;) {int next=i+(from<to?1:-1);m_indices[i]=m_indices[next];i=next;}
    m_indices[to]=index;return true;
  }
  size_t encode(void *output,size_t capacity) const {
    size_t size=8;for(int i=0;i<m_count;i++) size+=strlen(m_keys[m_indices[i]])+1;
    if(size>capacity) return 0;
    auto bytes=static_cast<char *>(output);memcpy(bytes,"LFHO\1\0\0\0",8);size_t offset=8;
    for(int i=0;i<m_count;i++) {const char *key=m_keys[m_indices[i]];size_t n=strlen(key)+1;memcpy(bytes+offset,key,n);offset+=n;}
    return size;
  }
private:
  const char *const *m_keys=nullptr;
  int m_count=0,m_indices[Capacity]{};
};
}
