/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#ifndef LEFONY_DATA_H
#define LEFONY_DATA_H
#include "app_c.h"
#include "data_wire.h"
/* API 8 development candidate; explicitly declare capability 512.
 * Close all file descriptors before submitting a data operation. Submit once,
 * then poll its token with a fresh zeroed request. Return 1 is pending; return
 * 0 delivers state/error. Only a COMMITTED response qualifies as a saved
 * checkpoint. A later edit keeps DIRTY set. Cancellation can drain an already
 * committed operation. See the checkpoint implementation ledger. */
static inline LefonyDataRequest lefony_data_request(uint32_t operation) {
#ifdef __cplusplus
  LefonyDataRequest r{};
#else
  LefonyDataRequest r={0};
#endif
  r.size=sizeof(r);r.schema=1;r.operation=operation;return r;
}
static inline int32_t lefony_data(LefonyDataRequest *request) { return lefony_service(LEFONY_DATA_SERVICE,request); }
#endif
