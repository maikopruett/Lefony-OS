// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_storage.h"
#include "legacy_app_storage.h"
#include "nand_physical.h"
#include <string>
#include <cstdio>
#include <array>
#include <map>
#include <memory>
#include <set>
#include <vector>
#include <cstring>
#include <cassert>
#include <stdexcept>
using namespace PrimeG2::AppStorage;
using Page = std::array<uint8_t, PageBytes>;
struct PowerCut {};
struct Flash {
  std::map<uint32_t, Page> pages;
  std::set<uint32_t> bad;
  int writes = 0, cut = -1;
  uint64_t programmed = 0, reads = 0;
  bool torn = false;
  static void range(uint32_t block) {
    assert(block >= FirstBlock && block < FirstBlock + BlockCount);
  }
  static bool usable(void *p, uint32_t b) {
    range(b);
    return !static_cast<Flash *>(p)->bad.count(b);
  }
  static bool read(void *p, uint32_t page, uint8_t *data) {
    range(page / PagesPerBlock);
    auto &f = *static_cast<Flash *>(p);
    f.reads++;
    if (f.bad.count(page / PagesPerBlock))
      return false;
    auto it = f.pages.find(page);
    if (it == f.pages.end())
      memset(data, 255, PageBytes);
    else
      memcpy(data, it->second.data(), PageBytes);
    return true;
  }
  static bool erase(void *p, uint32_t block) {
    range(block);
    auto &f = *static_cast<Flash *>(p);
    assert(!f.bad.count(block));
    bool cut = f.writes++ == f.cut;
    if (cut && !f.torn)
      throw PowerCut{};
    for (unsigned i = 0; i < (cut ? 7 : PagesPerBlock); i++)
      f.pages.erase(block * PagesPerBlock + i);
    if (cut)
      throw PowerCut{};
    return true;
  }
  static bool program(void *p, uint32_t page, const uint8_t *data) {
    range(page / PagesPerBlock);
    auto &f = *static_cast<Flash *>(p);
    assert(!f.bad.count(page / PagesPerBlock));
    // NAND pages may only be programmed once between erases.
    assert(!f.pages.count(page));
    const auto later = f.pages.lower_bound(page);
    assert(later == f.pages.end() || later->first / PagesPerBlock != page / PagesPerBlock);
    bool cut = f.writes++ == f.cut;
    if (cut && !f.torn)
      throw PowerCut{};
    Page bytes;
    bytes.fill(255);
    memcpy(bytes.data(), data, cut ? 37 : PageBytes);
    f.pages.emplace(page, bytes);
    f.programmed += cut ? 37 : PageBytes;
    if (cut)
      throw PowerCut{};
    return true;
  }
  Backend backend() { return {this, usable, read, erase, program}; }
};
static void finish(Volume &v) {
  for (unsigned i = 0; i < 10000 && v.state() != State::Complete && v.state() != State::Failed; i++)
    v.step();
  assert(v.state() == State::Complete);
}
static bool nameReader(const uint8_t *, size_t, char id[49]) {
  strcpy(id, "legacy-app");
  return true;
}
static bool numberedName(const uint8_t *package, size_t, char id[49]) {
  snprintf(id, 49, "legacy-%u", package[0]);
  return true;
}
static std::vector<uint8_t> packageBuffer(MaximumPackage), dataBuffer(MaximumData);
static bool initialize(Volume &v) {
  return v.initialize(packageBuffer.data(), packageBuffer.size(), dataBuffer.data(),
                      dataBuffer.size(), nameReader);
}
static Entry check(Volume &v, const char *id, const std::vector<uint8_t> &package,
                   const std::vector<uint8_t> &data) {
  Entry e;
  assert(v.entry(id, &e));
  assert(e.packageBytes == package.size() && e.dataBytes == data.size());
  assert(
      v.read(id, packageBuffer.data(), packageBuffer.size(), dataBuffer.data(), dataBuffer.size()));
  assert(!memcmp(packageBuffer.data(), package.data(), package.size()));
  if (data.size())
    assert(!memcmp(dataBuffer.data(), data.data(), data.size()));
  return e;
}
static void testHomeOrder() {
  std::vector<uint8_t> original(280,0x31),replacement(4096,0x72),readback(Volume::MaximumHomeOrder);
  Flash flash;
  {
    auto volume=std::make_unique<Volume>(flash.backend());assert(initialize(*volume));
    assert(volume->readHomeOrder(readback.data(),readback.size())==0);
    assert(!volume->beginHomeOrder(original.data(),7));
    assert(!volume->beginHomeOrder(original.data(),Volume::MaximumHomeOrder+1));
    assert(volume->beginHomeOrder(original.data(),original.size()));finish(*volume);
    assert(volume->readHomeOrder(readback.data(),readback.size())==int(original.size()));
    assert(!memcmp(readback.data(),original.data(),original.size()));
  }
  for(bool torn:{false,true}) for(int cut=0;cut<24;cut++) {
    Flash candidate=flash;candidate.cut=candidate.writes+cut;candidate.torn=torn;
    try {
      auto volume=std::make_unique<Volume>(candidate.backend());assert(initialize(*volume));
      assert(volume->beginHomeOrder(replacement.data(),replacement.size()));finish(*volume);
    } catch(PowerCut &) {}
    candidate.cut=-1;
    auto restored=std::make_unique<Volume>(candidate.backend());assert(initialize(*restored));
    int bytes=restored->readHomeOrder(readback.data(),readback.size());
    assert((bytes==int(original.size()) && !memcmp(readback.data(),original.data(),original.size())) ||
           (bytes==int(replacement.size()) && !memcmp(readback.data(),replacement.data(),replacement.size())));
    int count=0;assert(restored->list([](void *p,const char *,const Entry &){++*static_cast<int *>(p);return true;},&count));
    assert(count==0); // The OS preference must never appear as an installed app.
  }
}
int main() {
  testHomeOrder();
  uint8_t raw[2112];
  memset(raw, 0xff, sizeof(raw));
  assert(PrimeG2::NANDPhysical::erasedRawAppPage(raw));
  assert(!PrimeG2::NANDPhysical::erasedRawAppPage(nullptr));
  for (unsigned i = 0; i < sizeof(raw); i++) {
    raw[i] = 0xfe;
    assert(!PrimeG2::NANDPhysical::erasedRawAppPage(raw));
    raw[i] = 0xff;
  }
  std::vector<uint8_t> old(17301, 0x23), next(31989, 0x61), oldData(17, 0x91), newData(4099, 0x85);
  Flash flash;
  auto vOwner=std::make_unique<Volume>(flash.backend());Volume &v=*vOwner;
  assert(!v.mount());
  assert(initialize(v));
  Space empty;
  assert(v.space(&empty));
  assert(empty.available > 60 * 1024 * 1024);
  assert(v.begin("surface-3d", old.data(), old.size(), oldData.data(), oldData.size()));
  finish(v);
  check(v, "surface-3d", old, oldData);
  Space one;
  assert(v.space(&one));
  assert(empty.available - one.available <= 2 * BlockBytes);
  Flash baseline = flash;
  for (bool torn : {false, true})
    for (int cut = 0; cut < 70; cut++) {
      Flash f = baseline;
      f.cut = f.writes + cut;
      f.torn = torn;
      try {
        auto updateOwner=std::make_unique<Volume>(f.backend());Volume &update=*updateOwner;
        assert(update.mount());
        assert(
            update.begin("surface-3d", next.data(), next.size(), newData.data(), newData.size()));
        finish(update);
      } catch (PowerCut &) {
      }
      f.cut = -1;
      auto recoveredOwner=std::make_unique<Volume>(f.backend());Volume &recovered=*recoveredOwner;
      assert(initialize(recovered));
      Entry e;
      assert(recovered.entry("surface-3d", &e));
      if (e.generation == 1)
        check(recovered, "surface-3d", old, oldData);
      else {
        assert(e.generation == 2);
        check(recovered, "surface-3d", next, newData);
      }
    }
  for (bool torn : {false, true})
    for (int cut = 0; cut < 12; cut++) {
      Flash f = baseline;
      f.cut = f.writes + cut;
      f.torn = torn;
      try {
        auto updateOwner=std::make_unique<Volume>(f.backend());Volume &update=*updateOwner;
        assert(update.mount());
        assert(update.begin("surface-3d", nullptr, 0, nullptr, 0));
        finish(update);
      } catch (PowerCut &) {
      }
      f.cut = -1;
      auto recoveredOwner=std::make_unique<Volume>(f.backend());Volume &recovered=*recoveredOwner;
      assert(initialize(recovered));
      Entry e;
      if (recovered.entry("surface-3d", &e))
        check(recovered, "surface-3d", old, oldData);
    }
  // Icons use the same verified atomic file replacement, without touching
  // executable bytes, private data, app generations or catalog enumeration.
  std::vector<uint8_t> icon(6576,0x53), changedIcon(6576,0x84), iconRead(6576);
  Flash withIcon=baseline;
  {
    auto iconsOwner=std::make_unique<Volume>(withIcon.backend());Volume &icons=*iconsOwner; assert(initialize(icons));
    assert(!icons.begin("surface-3d",icon.data(),icon.size()-1,nullptr,0,true));
    assert(icons.begin("surface-3d",icon.data(),icon.size(),nullptr,0,true)); finish(icons);
    assert(check(icons,"surface-3d",old,oldData).generation==1);
  }
  for (bool first : {true,false}) for (bool torn : {false,true}) for(int cut=0;cut<30;cut++) {
    Flash f=first?baseline:withIcon; f.cut=f.writes+cut; f.torn=torn;
    try {
      auto updateOwner=std::make_unique<Volume>(f.backend());Volume &update=*updateOwner; assert(initialize(update));
      assert(update.begin("surface-3d",changedIcon.data(),changedIcon.size(),nullptr,0,true)); finish(update);
    } catch(PowerCut &) {}
    f.cut=-1; auto recoveredOwner=std::make_unique<Volume>(f.backend());Volume &recovered=*recoveredOwner; assert(initialize(recovered));
    assert(check(recovered,"surface-3d",old,oldData).generation==1);
    Entry e;
    if(recovered.entry("surface-3d",&e,true)) {
      assert(recovered.read("surface-3d",iconRead.data(),iconRead.size(),nullptr,0,true));
      assert(iconRead==changedIcon || (!first && iconRead==icon));
    } else assert(first);
  }
  {
    auto iconsOwner=std::make_unique<Volume>(withIcon.backend());Volume &icons=*iconsOwner; assert(initialize(icons));
    assert(icons.read("surface-3d",iconRead.data(),iconRead.size(),nullptr,0,true)); assert(iconRead==icon);
    unsigned count=0;
    assert(icons.list([](void *p,const char *,const Entry &){++*static_cast<unsigned *>(p);return true;},&count)); assert(count==1);
    assert(icons.begin("surface-3d",nullptr,0,nullptr,0));finish(icons);
    Entry e; assert(!icons.entry("surface-3d",&e)); assert(!icons.entry("surface-3d",&e,true));
  }
  // Real profile-1 bank fixtures, not invented migration headers.
  Flash legacy;
  {
    PrimeG2::LegacyAppStorage::Volume l(legacy.backend());
    assert(!l.mount());
    uint8_t identity[32] = {42};
    assert(l.provision(identity));
    assert(l.begin(0, old.data(), old.size(), oldData.data(), oldData.size()));
    while (l.state() != PrimeG2::LegacyAppStorage::State::Complete)
      l.step();
  }
  Flash migrationComplete = legacy;
  {
    auto migratedOwner=std::make_unique<Volume>(migrationComplete.backend());Volume &migrated=*migratedOwner;
    assert(initialize(migrated));
    check(migrated, "legacy-app", old, oldData);
  }
  const int migrationWrites = migrationComplete.writes - legacy.writes;
  printf("Migration mutations: %d\n", migrationWrites);
  for (bool torn : {false, true})
    for (int cut = 0; cut <= migrationWrites; cut++) {
      Flash f = legacy;
      f.cut = f.writes + cut;
      f.torn = torn;
      try {
        auto migratedOwner=std::make_unique<Volume>(f.backend());Volume &migrated=*migratedOwner;
        initialize(migrated);
      } catch (PowerCut &) {
      }
      f.cut = -1;
      auto recoveredOwner=std::make_unique<Volume>(f.backend());Volume &recovered=*recoveredOwner;
      assert(initialize(recovered));
      check(recovered, "legacy-app", old, oldData);
    }
  // Migrate all eight maximum-size apps together; neither their data nor
  // their generations may be lost when the old banks are reclaimed.
  Flash allLegacy;
  std::vector<uint8_t> biggest(MaximumPackage, 0), privateData(MaximumData, 0x47);
  {
    PrimeG2::LegacyAppStorage::Volume l(allLegacy.backend());
    assert(!l.mount());
    uint8_t identity[32] = {73};
    assert(l.provision(identity));
    for (unsigned i = 0; i < 8; i++) {
      biggest[0] = i;
      assert(l.begin(i, biggest.data(), biggest.size(), privateData.data(), privateData.size()));
      while (l.state() != PrimeG2::LegacyAppStorage::State::Complete)
        l.step();
    }
  }
  {
    auto migratedOwner=std::make_unique<Volume>(allLegacy.backend());Volume &migrated=*migratedOwner;
    assert(migrated.initialize(packageBuffer.data(), packageBuffer.size(), dataBuffer.data(),
                               dataBuffer.size(), numberedName));
    for (unsigned i = 0; i < 8; i++) {
      biggest[0] = i;
      char id[49];
      numberedName(biggest.data(), biggest.size(), id);
      assert(check(migrated, id, biggest, privateData).generation == 1);
    }
  }
  // Empty stock layouts can be initialized; unknown/damaged data cannot.
  Flash unknown;
  Page garbage;
  garbage.fill(0x42);
  unknown.pages[FirstBlock * PagesPerBlock] = garbage;
  auto rejectOwner=std::make_unique<Volume>(unknown.backend());Volume &reject=*rejectOwner;
  assert(!initialize(reject));
  assert(unknown.writes == 0);
  // Cancellation affects only the unpublished temporary file.
  {
    Flash f = baseline;
    auto updateOwner=std::make_unique<Volume>(f.backend());Volume &update=*updateOwner;
    assert(update.mount());
    assert(update.begin("surface-3d", next.data(), next.size(), nullptr, 0));
    update.step();
    update.step();
    update.cancel();
    check(update, "surface-3d", old, oldData);
  }
  // More than eight files and more than 16 MiB of packages share the pool.
  std::vector<uint8_t> large(1500000, 0xa5);
  Flash pool;
  auto sharedOwner=std::make_unique<Volume>(pool.backend());Volume &shared=*sharedOwner;
  assert(initialize(shared));
  for (unsigned i = 0; i < 16; i++) {
    char id[49];
    snprintf(id, sizeof(id), "app-%u", i);
    assert(shared.begin(id, large.data(), large.size(), nullptr, 0));
    finish(shared);
  }
  unsigned count = 0;
  assert(shared.list(
      [](void *p, const char *, const Entry &) {
        ++*static_cast<unsigned *>(p);
        return true;
      },
      &count));
  assert(count == 16);
  Space used;
  assert(shared.space(&used));
  assert(used.available < empty.available - 20 * 1024 * 1024);
  assert(shared.begin("app-7", nullptr, 0, nullptr, 0));
  finish(shared);
  Space removed;
  assert(shared.space(&removed));
  assert(removed.available > used.available + 1024 * 1024);
  // Fill the volume with distinct files, then replace an existing file at
  // capacity. Atomic replacement must use the reserved headroom.
  unsigned added = 0;
  for (unsigned i = 16; i < 100; i++) {
    char id[49];
    snprintf(id, sizeof(id), "app-%u", i);
    if (!shared.begin(id, large.data(), large.size(), nullptr, 0))
      break;
    finish(shared);
    added++;
  }
  assert(added > 15 && added < 80);
  Space full;
  assert(shared.space(&full));
  assert(full.available < 12 * BlockBytes);
  large[0] ^= 0x55;
  assert(shared.begin("app-0", large.data(), large.size(), nullptr, 0));
  finish(shared);
  check(shared, "app-0", large, {});
  assert(shared.begin("app-1", nullptr, 0, nullptr, 0));
  finish(shared);
  assert(shared.begin("reclaimed-space", large.data(), large.size(), nullptr, 0));
  finish(shared);
  check(shared, "reclaimed-space", large, {});
  {
    auto rebootOwner=std::make_unique<Volume>(pool.backend());Volume &reboot=*rebootOwner;
    assert(initialize(reboot));
    check(reboot, "app-0", large, {});
  }
  // Damage to a completed filesystem cannot trigger reformatting.
  Flash damaged = baseline;
  for (unsigned b = 2; b < 4; b++)
    for (unsigned page = 0; page < PagesPerBlock; page++) {
      Page invalid;
      invalid.fill(0);
      damaged.pages[(FirstBlock + b) * PagesPerBlock + page] = invalid;
    }
  int before = damaged.writes;
  auto brokenOwner=std::make_unique<Volume>(damaged.backend());Volume &broken=*brokenOwner;
  assert(!initialize(broken));
  assert(damaged.writes == before);
  // Factory bad payload blocks are excluded from capacity and allocation.
  Flash bad;
  bad.bad.insert(FirstBlock + 40);
  bad.bad.insert(FirstBlock + 80);
  auto bOwner=std::make_unique<Volume>(bad.backend());Volume &b=*bOwner;
  assert(initialize(b));
  Space reduced;
  assert(b.space(&reduced));
  assert(reduced.capacity == empty.capacity - 2 * BlockBytes);
  assert(b.begin("bad-block-test", large.data(), large.size(), nullptr, 0));
  finish(b);
  check(b, "bad-block-test", large, {});
  puts("Shared filesystem, migration, atomic replacement/removal and bad blocks passed");
}
