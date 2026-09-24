/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#ifndef LEFONY_DATA_WIRE_H
#define LEFONY_DATA_WIRE_H
#include <stdint.h>
#define LEFONY_DATA_SERVICE 14u
#define LEFONY_DATA_CAPABILITY 512u
#define LEFONY_DATA_API 8u
/* API 8 development checkpoint interface. No application pointers
 * or caller-selected namespace are retained by the transaction controller. */
enum LefonyDataOperation {
  LEFONY_DATA_POLL=0, LEFONY_DATA_INSPECT=1, LEFONY_DATA_CHECKPOINT=2,
  LEFONY_DATA_BEGIN_MIGRATION=3, LEFONY_DATA_ACCEPT=4, LEFONY_DATA_CANCEL=5
};
enum LefonyDataState {
  LEFONY_DATA_PENDING=1, LEFONY_DATA_COMPLETE=2,
  LEFONY_DATA_FAILED=3, LEFONY_DATA_CANCELLED=4
};
enum LefonyDataFlags {
  LEFONY_DATA_DIRTY=1, LEFONY_DATA_PENDING_UPGRADE=2,
  LEFONY_DATA_MIGRATING=4, LEFONY_DATA_COMMITTED=8,
  LEFONY_DATA_COMMIT_UNCERTAIN=16
};
/* Errors 1..16 share the file-service meanings. */
#define LEFONY_DATA_CANCELLED_ERROR 17u
typedef struct LefonyDataRequest {
  uint32_t size,schema,operation,token,generation,dataSchema,bytes,flags;
  uint32_t state,error,appSchema,stagedBytes,editRevision,snapshotRevision;
  uint32_t reserved[2];
} LefonyDataRequest;
#endif
