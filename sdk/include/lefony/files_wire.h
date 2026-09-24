/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
#ifndef LEFONY_FILES_WIRE_H
#define LEFONY_FILES_WIRE_H
#include <stdint.h>
/* Experimental API revision 2, capability 8, service 10. No host pointers,
 * native errno values, filesystem paths or caller-selected app identities. */
enum LefonyFileOperation {
  LEFONY_FILE_POLL=0, LEFONY_FILE_OPEN=1, LEFONY_FILE_CLOSE=2,
  LEFONY_FILE_READ=3, LEFONY_FILE_WRITE=4, LEFONY_FILE_SEEK=5,
  LEFONY_FILE_STAT=6, LEFONY_FILE_MKDIR=7, LEFONY_FILE_UNLINK=8,
  LEFONY_FILE_RENAME=9, LEFONY_FILE_FINISH=10,
  /* Additive API revision 5, capability 64. Keeps the descriptor open. */
  LEFONY_FILE_SYNC=11,
  /* Additive API revision 6, capability 128. Read-only committed metadata. */
  LEFONY_FILE_LIST=12, LEFONY_FILE_SPACE=13,
  /* Additive API revision 7, capability 256. Logical app-data allowance. */
  LEFONY_FILE_QUOTA=14,
  /* Additive API revision 12, capability 8192. Discards uncommitted edits. */
  LEFONY_FILE_ABORT=15
};
enum LefonyFileFlags {
  LEFONY_FILE_READABLE=1, LEFONY_FILE_WRITABLE=2, LEFONY_FILE_CREATE=4,
  LEFONY_FILE_TRUNCATE=8, LEFONY_FILE_APPEND=16, LEFONY_FILE_EXCLUSIVE=32
};
enum LefonyFileError {
  LEFONY_FILE_OK=0, LEFONY_FILE_INVALID=1, LEFONY_FILE_BAD_HANDLE=2,
  LEFONY_FILE_NOT_FOUND=3, LEFONY_FILE_EXISTS=4, LEFONY_FILE_IS_DIRECTORY=5,
  LEFONY_FILE_NO_SPACE=6, LEFONY_FILE_TOO_LARGE=7, LEFONY_FILE_IO=8,
  LEFONY_FILE_BUSY=9, LEFONY_FILE_LIMIT=10, LEFONY_FILE_SCHEMA=11,
  LEFONY_FILE_DENIED=12, LEFONY_FILE_NOT_EMPTY=13,
  LEFONY_FILE_NOT_DIRECTORY=14, LEFONY_FILE_CHANGED=15,
  LEFONY_FILE_QUOTA_EXCEEDED=16
};
typedef struct LefonyFileRequest {
  uint32_t size, schema, operation, handle, flags, offset, length;
  uint32_t path, pathBytes, destination, destinationBytes, buffer, capacity, token;
  int32_t result;
  uint32_t error;
} LefonyFileRequest;
typedef struct LefonyFileInfo { uint32_t bytes, position, kind, flags; } LefonyFileInfo;
#define LEFONY_DIRECTORY_PAGE_ENTRIES 16u
typedef struct LefonyDirectoryEntry { char path[96];uint32_t kind,bytes; } LefonyDirectoryEntry;
typedef struct LefonyDirectoryPage {
  uint32_t size,schema,generation,next,count,reserved;
  LefonyDirectoryEntry entries[LEFONY_DIRECTORY_PAGE_ENTRIES];
} LefonyDirectoryPage;
typedef struct LefonyFileSpace {
  uint32_t size,schema,flags,generation;
  uint32_t packageBytes,privateBytes,fileBytes,files,directories,extents;
  uint32_t capacityBytes,allocatedBytes,availableBytes,reservedBytes;
  uint32_t writerBytes,writerCommittedBytes;
} LefonyFileSpace;
typedef struct LefonyFileQuota {
  uint32_t size,schema,flags,generation;
  uint32_t limitBytes,committedBytes,projectedBytes,ceilingBytes,remainingBytes;
  uint32_t reserved[3];
} LefonyFileQuota;
#define LEFONY_FILE_QUOTA_WRITER_OPEN 1u
#define LEFONY_FILE_QUOTA_OVER_LIMIT 2u
#define LEFONY_FILE_QUOTA_WRITER_FAILED 4u
#define LEFONY_FILE_SPACE_WRITER_OPEN 1u
#define LEFONY_FILE_TRANSFER_BYTES 2048u
#define LEFONY_FILE_PATH_BYTES 95u
#define LEFONY_FILE_SYNC_API 5u
#define LEFONY_FILE_SYNC_CAPABILITY 64u
#define LEFONY_FILE_CATALOG_API 6u
#define LEFONY_FILE_CATALOG_CAPABILITY 128u
#define LEFONY_FILE_QUOTA_API 7u
#define LEFONY_FILE_QUOTA_CAPABILITY 256u
#define LEFONY_FILE_ABORT_API 12u
#define LEFONY_FILE_ABORT_CAPABILITY 8192u
#endif
