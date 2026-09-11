// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "menu.h"
#include "../apps_container.h"
#include "../../ion/src/prime_g2/app_management.h"
#include <apps/external/external_icon.h>
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
const Image *installedIcon() { return ImageStore::ExternalIcon; }
uint32_t catalogRevision() { return PrimeG2::AppManagement::revision(); }
}
