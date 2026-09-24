// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "menu.h"
#include "home_order.h"
#include "home_builtin_ids.h"
#include <apps/home/apps_layout.h>

#include "../apps_container.h"
#include "../../ion/src/prime_g2/app_management.h"
#include <apps/external/external_icon.h>
#include "../../ion/src/prime_g2/app_icon.h"
namespace NativeApps {
int builtInCount() { return AppsContainer::sharedAppsContainer()->numberOfApps()-2; }
int menuCount() {
  int count=builtInCount();
  for(unsigned slot=0;slot<PrimeG2::AppManagement::count();slot++) count+=PrimeG2::AppManagement::entry(slot).bytes?1:0;
  return count;
}
int slotAt(int index) {
  if(index<0) return -1;
  for(unsigned slot=0;slot<PrimeG2::AppManagement::count();slot++) if(PrimeG2::AppManagement::entry(slot).bytes && index--==0) return slot;
  return -1;
}
const char *installedName(unsigned slot) { return PrimeG2::AppManagement::entry(slot).metadata.name; }
const Image *installedIcon(unsigned slot) {
  using namespace PrimeG2;
  struct Icon : Image { Icon() : Image(AppIcon::Width,AppIcon::Height,nullptr,0) {} };
  static Icon images[AppManagement::MaximumIcons];
  const uint8_t *pixels=AppManagement::icon(slot);
  if(!pixels || slot>=AppManagement::MaximumIcons) return ImageStore::ExternalIcon;
  static_cast<Image &>(images[slot])=Image(AppIcon::Width,AppIcon::Height,pixels,AppIcon::CompressedBytes);
  return &images[slot];
}
namespace {
HomeOrder sOrder;
const char *sOrderKeys[HomeOrder::Capacity];
char sOrderBuffer[HomeOrder::MaximumBytes];
uint32_t sOrderRevision=0;
bool sOrderLoaded=false;

void ensureOrder() {
  uint32_t revision=PrimeG2::AppManagement::revision();
  if(sOrderLoaded && revision==sOrderRevision) return;
  int builtins=builtInCount(),count=menuCount();
  for(int i=0;i<count && i<HomeOrder::Capacity;i++) {
    sOrderKeys[i]=i<builtins?HomeBuiltinIds[Home::PermutedAppSnapshotIndex(i+1)-1]:
      PrimeG2::AppManagement::entry(slotAt(i-builtins)).metadata.id;
  }
  uint32_t bytes=0;const uint8_t *data=PrimeG2::AppManagement::homeOrder(&bytes);
  sOrder.reset(sOrderKeys,count,data,bytes);
  sOrderRevision=revision;sOrderLoaded=true;
}
}
int menuIndex(int position) {ensureOrder();return sOrder.at(position)+1;}
const Image *menuIcon(int position) {
  int index=menuIndex(position);
  if(index<=0) return nullptr;
  if(index>builtInCount()) return installedIcon(slotAt(index-builtInCount()-1));
  return AppsContainer::sharedAppsContainer()->appSnapshotAtIndex(Home::PermutedAppSnapshotIndex(index))->descriptor()->icon();
}
bool moveMenuIcon(int from,int to) {ensureOrder();return sOrder.move(from,to);}
void reloadMenuOrder() {sOrderLoaded=false;ensureOrder();}
bool saveMenuOrder() {
  ensureOrder();size_t size=sOrder.encode(sOrderBuffer,sizeof(sOrderBuffer));if(!size) return false;
  return PrimeG2::AppManagement::saveHomeOrder(reinterpret_cast<const uint8_t *>(sOrderBuffer),size);
}
bool menuOrderSaveFailed() {return PrimeG2::AppManagement::homeOrderSaveFailed();}
uint32_t catalogRevision() { return PrimeG2::AppManagement::revision(); }
}
