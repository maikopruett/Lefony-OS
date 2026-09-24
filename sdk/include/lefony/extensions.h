// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_EXTENSIONS_H
#define LEFONY_EXTENSIONS_H
#include "app.h"
namespace Lefony {
// Experimental additive services. Old ABI 1 firmware returns -3 for discovery.
// Schema 0 keeps these optional. Explicit package schema 1 can require them;
// its minimum_api/feature requirements are checked before install and launch.
enum Capability : uint32_t { RectangleBatch=1,InputSnapshots=2,AppNavigation=4,NamedFiles=8,ForegroundRuntime=16,InputStream=32,FileSync=64,FileCatalog=128,FileQuota=256,DataCheckpoints=512,Typography=1024,SystemServices=2048,AppChannel=4096,FileAbort=8192 };
struct Capabilities {
  uint32_t size=sizeof(Capabilities),version=1,reserved=0;
  uint32_t features=0,abi=0,width=0,height=0,privateDataBytes=0,transferBytes=0;
  uint32_t maxBatchRects=0,maxBatchPixels=0,callbackMs=0;
};
static_assert(sizeof(Capabilities)==48,"discovery wire size");
inline int32_t discover(Capabilities &out) { return service(6,&out); }
struct RectBatch { uint32_t size,version,reserved;const Rect *rects;uint32_t count; };
static_assert(sizeof(RectBatch)==20,"batch wire size");
// Atomic validation, <=64 rectangles, <=76800 total pixels. The OS copies
// descriptors and owns presentation; no framebuffer pointer is exported.
inline int32_t batch(const Rect *rects,uint32_t count) {
  RectBatch request{sizeof(RectBatch),1,0,rects,count};return service(7,&request);
}
}
#endif
