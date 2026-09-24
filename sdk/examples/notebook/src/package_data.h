// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef NOTEBOOK_PACKAGE_DATA_H
#define NOTEBOOK_PACKAGE_DATA_H
#include <lefony/data.h>
#include <lefony/foreground.h>
namespace NotebookPackage {
inline bool operation(unsigned kind,unsigned generation,LefonyDataRequest *out) {
  LefonyDataRequest r=lefony_data_request(kind);r.generation=generation;
  if(lefony_data(&r)!=1) return false;
  unsigned token=r.token,start=lefony_millis();
  for(;;) {
    r=lefony_data_request(LEFONY_DATA_POLL);r.token=token;int status=lefony_data(&r);
    if(status==0) {
      if(out) *out=r;
      return r.state==LEFONY_DATA_COMPLETE && !r.error && !(r.flags&LEFONY_DATA_COMMIT_UNCERTAIN);
    }
    if(status!=1 || (unsigned)(lefony_millis()-start)>=120000) {
      LefonyDataRequest cancel=lefony_data_request(LEFONY_DATA_CANCEL);cancel.token=token;lefony_data(&cancel);return false;
    }
    lefony_program_yield();
  }
}
inline bool inspect(LefonyDataRequest *out) {
  return operation(LEFONY_DATA_INSPECT,0,out) && !out->appSchema && !out->dataSchema && !out->bytes;
}
inline bool accept(const LefonyDataRequest &before) {
  if(!(before.flags&LEFONY_DATA_PENDING_UPGRADE)) return true;
  LefonyDataRequest after;
  return operation(LEFONY_DATA_ACCEPT,before.generation,&after) && (after.flags&LEFONY_DATA_COMMITTED) &&
    !(after.flags&LEFONY_DATA_PENDING_UPGRADE);
}
}
#endif
