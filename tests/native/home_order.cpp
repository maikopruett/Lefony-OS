// SPDX-License-Identifier: GPL-3.0-or-later
#include "home_order.h"
#include <cassert>
#include <cstring>
using NativeApps::HomeOrder;
int main() {
  HomeOrder order;const char *keys[]={"#calculation","#graph","doom","counter"};char saved[256];
  order.reset(keys,4,nullptr,0);assert(order.at(0)==0 && order.at(3)==3 && order.at(-1)==-1 && order.at(4)==-1);
  assert(order.move(2,0));assert(order.at(0)==2 && order.at(1)==0 && order.at(2)==1 && order.at(3)==3);
  assert(!order.move(-1,0) && !order.move(0,4));
  size_t size=order.encode(saved,sizeof(saved));assert(size && !order.encode(saved,1));
  HomeOrder restored;restored.reset(keys,4,saved,size);assert(restored.at(0)==2);
  // Catalog slot changes and upgrades keep position by app ID; new apps append.
  const char *changed[]={"#calculation","#graph","counter","new-app","doom"};
  restored.reset(changed,5,saved,size);
  assert(restored.at(0)==4 && restored.at(3)==2 && restored.at(4)==3);
  const char *removed[]={"#calculation","#graph","counter"};
  restored.reset(removed,3,saved,size);assert(restored.at(0)==0 && restored.at(2)==2);
  restored.reset(keys,4,"bad",3);assert(restored.at(0)==0);
  restored.reset(keys,4,saved,size-1);assert(restored.at(0)==0); // Truncated record is ignored.
  char duplicate[]="LFHO\1\0\0\0doom\0doom\0#graph\0";
  restored.reset(keys,4,duplicate,sizeof(duplicate)-1);
  assert(restored.at(0)==2 && restored.at(1)==1 && restored.at(2)==0 && restored.at(3)==3);
  restored.move(0,3);assert(restored.at(3)==2);restored.move(3,0);assert(restored.at(0)==2);
}
