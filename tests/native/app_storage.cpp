// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_storage.h"
#include <array>
#include <map>
#include <set>
#include <vector>
#include <cstring>
#include <cassert>
#include <stdexcept>
using namespace PrimeG2::AppStorage;
using Page=std::array<uint8_t,PageBytes>;
struct PowerCut {};
struct Flash {
  std::map<uint32_t,Page> pages;
  std::set<uint32_t> bad;
  int writes=0,cut=-1;
  bool torn=false;
  static void range(uint32_t block) { assert(block>=FirstBlock && block<FirstBlock+BlockCount); }
  static bool usable(void *p,uint32_t b) { range(b); return !static_cast<Flash *>(p)->bad.count(b); }
  static bool read(void *p,uint32_t page,uint8_t *data) {
    range(page/PagesPerBlock); auto &f=*static_cast<Flash *>(p);
    if(f.bad.count(page/PagesPerBlock)) return false;
    auto it=f.pages.find(page); if(it==f.pages.end()) memset(data,255,PageBytes); else memcpy(data,it->second.data(),PageBytes);
    return true;
  }
  static bool erase(void *p,uint32_t block) {
    range(block); auto &f=*static_cast<Flash *>(p); assert(!f.bad.count(block));
    bool cut=f.writes++==f.cut;
    if(cut && !f.torn) throw PowerCut{};
    for(unsigned i=0;i<(cut?7:PagesPerBlock);i++) f.pages.erase(block*PagesPerBlock+i);
    if(cut) throw PowerCut{};
    return true;
  }
  static bool program(void *p,uint32_t page,const uint8_t *data) {
    range(page/PagesPerBlock); auto &f=*static_cast<Flash *>(p); assert(!f.bad.count(page/PagesPerBlock));
    // NAND pages may only be programmed once between erases.
    assert(!f.pages.count(page));
    bool cut=f.writes++==f.cut;
    if(cut && !f.torn) throw PowerCut{};
    Page bytes; bytes.fill(255); memcpy(bytes.data(),data,cut?37:PageBytes); f.pages.emplace(page,bytes);
    if(cut) throw PowerCut{};
    return true;
  }
  Backend backend() { return {this,usable,read,erase,program}; }
};
static void finish(Volume &v) {
  for(unsigned i=0;i<10000 && v.state()!=State::Complete && v.state()!=State::Failed;i++) v.step();
  assert(v.state()==State::Complete);
}
int main() {
  Flash flash;
  Volume v(flash.backend()); assert(!v.mount());
  std::vector<uint8_t> old(7131,0x23),next(9321,0x61),oldData(17,0x91),newData(4099,0x85);
  assert(!v.begin(0,old.data(),old.size(),nullptr,0));
  uint8_t backup[32]; memset(backup,0x15,32);
  // First install can reserve blank/stock UBI space without a backup. A later
  // call must not erase apps, even if both volume markers have disappeared.
  Flash automatic;
  Page ubi;ubi.fill(0xff);memcpy(ubi.data(),"UBI#",4);
  automatic.pages[FirstBlock*PagesPerBlock]=ubi;
  Volume reserved(automatic.backend());assert(!reserved.mount());
  assert(automatic.writes==0);
  assert(reserved.reserve());assert(!reserved.reserve());
  assert(reserved.begin(0,old.data(),old.size(),oldData.data(),oldData.size()));finish(reserved);
  automatic.pages.erase(FirstBlock*PagesPerBlock);
  automatic.pages.erase((FirstBlock+1)*PagesPerBlock);
  int before=automatic.writes;
  Volume missing(automatic.backend());assert(!missing.mount());assert(!missing.reserve());assert(automatic.writes==before);
  // Unknown data and torn markers are errors, never an automatic reformat.
  Flash unknown;Page data;data.fill(0x42);unknown.pages[FirstBlock*PagesPerBlock]=data;
  Volume u(unknown.backend());assert(!u.mount());assert(!u.reserve());assert(unknown.writes==0);
  Flash unreadable;unreadable.bad.insert(FirstBlock);
  Volume unavailable(unreadable.backend());assert(!unavailable.mount());assert(!unavailable.reserve());assert(unreadable.writes==0);
  for(bool torn:{false,true}) for(int cut=0;cut<4;cut++) {
    Flash f;f.cut=cut;f.torn=torn;Volume p(f.backend());assert(!p.mount());
    try { p.reserve(); } catch(PowerCut &) {}
    f.cut=-1;Volume recovered(f.backend());
    if(recovered.mount()) assert(recovered.entry(0).bank==-1);
    else {
      bool damaged=false;for(const auto &page:f.pages) damaged|=!memcmp(page.second.data(),"LFAVOL1",7);
      int writes=f.writes;
      if(damaged) { assert(!recovered.reserve());assert(f.writes==writes); }
      else assert(recovered.reserve());
    }
  }
  assert(reserved.capacity(0)==MaximumPackage);
  assert(v.provision(backup)); assert(!v.provision(backup));
  assert(v.begin(0,old.data(),old.size(),oldData.data(),oldData.size())); finish(v);
  Flash baseline=flash;
  // Cut before every mutation, and tear every erase/program. A fresh mount must
  // recover an entire old or new package/data pair, never a mixture.
  for(bool torn:{false,true}) for(int cut=0;cut<50;cut++) {
    Flash f=baseline; f.cut=f.writes+cut; f.torn=torn;
    Volume update(f.backend()); assert(update.mount());
    try { assert(update.begin(0,next.data(),next.size(),newData.data(),newData.size())); finish(update); } catch(PowerCut &) {}
    f.cut=-1;
    Volume recovered(f.backend()); assert(recovered.mount());
    std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
    assert(recovered.read(0,package.data(),package.size(),data.data(),data.size()));
    auto e=recovered.entry(0);
    if(e.generation==1) { assert(e.packageBytes==old.size() && e.dataBytes==oldData.size()); assert(!memcmp(package.data(),old.data(),old.size()) && !memcmp(data.data(),oldData.data(),oldData.size())); }
    else { assert(e.generation==2 && e.packageBytes==next.size() && e.dataBytes==newData.size()); assert(!memcmp(package.data(),next.data(),next.size()) && !memcmp(data.data(),newData.data(),newData.size())); }
  }
  // Deletion is a committed tombstone, including across every power-cut point.
  for(int cut=0;cut<36;cut++) {
    Flash f=baseline; f.cut=f.writes+cut; f.torn=true;
    Volume update(f.backend()); assert(update.mount());
    try { assert(update.begin(0,nullptr,0,nullptr,0)); finish(update); } catch(PowerCut &) {}
    f.cut=-1; Volume recovered(f.backend()); assert(recovered.mount());
    assert(recovered.entry(0).packageBytes==old.size() || recovered.entry(0).packageBytes==0);
  }
  // Factory bad blocks are skipped; insufficient capacity fails before erasing.
  Flash bad=baseline; bad.bad.insert(FirstBlock+16+BankBlocks); bad.bad.insert(FirstBlock+16+BankBlocks+2);
  Volume b(bad.backend()); assert(b.mount()); assert(b.begin(0,next.data(),next.size(),nullptr,0)); finish(b);
  for(unsigned i=1;i<BankBlocks;i++) bad.bad.insert(FirstBlock+16+i);
  assert(b.capacity(0)==0);assert(b.capacity(Slots)==0);
  int writes=bad.writes;
  std::vector<uint8_t> maximum(MaximumPackage,42);
  assert(!b.begin(0,maximum.data(),maximum.size(),nullptr,0)); assert(bad.writes==writes);
  assert(!b.begin(Slots,next.data(),next.size(),nullptr,0));
  assert(!b.begin(1,nullptr,0,newData.data(),newData.size()));
  // Cancellation before commit preserves the active generation.
  Flash cancel=baseline; Volume c(cancel.backend()); assert(c.mount()); assert(c.begin(0,next.data(),next.size(),nullptr,0)); c.step(); c.cancel();
  Volume check(cancel.backend()); assert(check.mount() && check.entry(0).generation==1);
  // A damaged newer payload falls back to the previous authenticated generation.
  Flash damaged=baseline; Volume d(damaged.backend()); assert(d.mount()); assert(d.begin(0,next.data(),next.size(),newData.data(),newData.size())); finish(d);
  damaged.pages[(FirstBlock+16+BankBlocks+1)*PagesPerBlock][100]^=1;
  Volume fallback(damaged.backend()); assert(fallback.mount() && fallback.entry(0).generation==1);
  // Provisioning interruption is either unprovisioned or the same empty volume.
  for(int cut=0;cut<4;cut++) {
    Flash f; f.cut=cut; f.torn=true; Volume p(f.backend()); assert(!p.mount());
    try { p.provision(backup); } catch(PowerCut &) {}
    f.cut=-1; Volume r(f.backend()); if(r.mount()) assert(!memcmp(r.identity(),backup,32) && r.entry(0).bank==-1);
  }
}
