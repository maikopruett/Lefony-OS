/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
#ifndef LEFONY_FILES_H
#define LEFONY_FILES_H
#include "app_c.h"
#include "files_wire.h"
/* Submit once, then poll the returned token using a fresh request. Return 1 is
 * pending; 0 delivers result/error; negative values reject the request. Paths
 * and input bytes are copied on submit. A too-small poll buffer preserves the
 * completion. CLOSE publishes a writer atomically; API 5 SYNC publishes while
 * retaining its handle. READ uses a committed snapshot. Unsaved staging is
 * aborted on app termination. See FILES.md. */
static inline LefonyFileRequest lefony_file_request(uint32_t operation) {
#ifdef __cplusplus
  LefonyFileRequest r{};
#else
  LefonyFileRequest r={0};
#endif
  r.size=sizeof(r);r.schema=1;r.operation=operation;return r;
}
static inline int32_t lefony_files(LefonyFileRequest *request) { return lefony_service(10,request); }
/* Synchronous helpers supplied by foreground-newlib-1. Require declared named
 * files (8) and catalog (128); failures return -1 with errno. Empty directory
 * or "." selects the root. Start with offset/generation zero, then pass the
 * preceding page's next/generation until next is zero. ESTALE requires restart. */
#ifdef __cplusplus
extern "C" {
#endif
int lefony_file_list(const char *directory,uint32_t offset,uint32_t generation,LefonyDirectoryPage *out);
int lefony_file_space(LefonyFileSpace *out);
/* Requires named files (8) and quota query (256). See FILES.md for the
 * committed/projected distinction and grandfathered oversized saves. */
int lefony_file_quota(LefonyFileQuota *out);
/* Requires named files (8) and writer abort (8192). Discards edits since the
 * last close/sync and invalidates the writer descriptor. Snapshot readers and
 * committed data remain intact. Use before closing stdio after rejected data;
 * see FILES.md for stream cleanup and failure handling. */
int lefony_file_abort(int descriptor);
#ifdef __cplusplus
}
#endif
#endif
