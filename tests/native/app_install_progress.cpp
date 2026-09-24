// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_install_progress.h"
#include <cassert>
#include <cstring>
using namespace PrimeG2::AppInstallProgress;
int main() {
  Tracker t;Presentation p;
  assert(!p.update(t.status(),0));
  t.begin(Phase::Receiving,1000);
  assert(p.update(t.status(),1));
  t.progress(500);assert(t.status().percent==50);
  t.progress(1000);assert(t.status().percent==99);
  t.identify("Counter",true);
  t.phase(Phase::Package,1000);
  assert(t.status().updating && !strcmp(t.status().name,"Counter"));
  assert(t.status().percent==0);
  t.progress(700);t.progress(0);assert(t.status().percent==70);
  t.progress(1000);assert(t.status().percent==99);
  assert(p.update(t.status(),20000)); // Slow writes never hide an active page.
  t.finish(true);assert(t.status().percent==100);
  assert(p.update(t.status(),20001));
  assert(p.update(t.status(),20900));
  assert(!p.update(t.status(),20901));
  assert(!p.update(t.status(),30000)); // No reopening from stale completion.
  t.begin(Phase::Data,10);assert(p.update(t.status(),30001));
  t.progress(4);t.finish(false);assert(t.status().percent==40);
  assert(p.update(t.status(),30002));
  assert(p.update(t.status(),31801));
  assert(!p.update(t.status(),31802));
  t.begin(Phase::Icon,1);t.finish(true); // Fast operation between UI ticks.
  assert(p.update(t.status(),40000));
  t.begin(Phase::Receiving,100);assert(p.update(t.status(),40100));
  t.cancel();assert(!p.update(t.status(),40101));
  t.finish(true);assert(t.status().phase==Phase::Idle);
  t.begin(Phase::Package,1);t.progress(0xffffffffu);assert(t.status().percent==99);
  char longName[100];memset(longName,'a',99);longName[99]=0;
  t.identify(longName,false);assert(strlen(t.status().name)==80);
  t.finish(true);assert(p.update(t.status(),0xffffff00u));
  assert(p.update(t.status(),500));assert(!p.update(t.status(),644)); // Clock wrap.
  t.begin(Phase::Data,0);t.progress(123);assert(t.status().percent==0);
  t.finish(true);assert(t.status().percent==100);
}
