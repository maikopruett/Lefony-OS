/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
/* One foreground C/C++ invocation. The OS supplies initialized data and BSS. */
#include <lefony/foreground.h>
#include <stdlib.h>
typedef void (*Initializer)(void);
extern Initializer __preinit_array_start[], __preinit_array_end[];
extern Initializer __init_array_start[], __init_array_end[];
extern Initializer __fini_array_start[], __fini_array_end[];
extern int main(int argc, char **argv);
extern int lefony_main_argc;
extern char *lefony_main_argv[];
void *__dso_handle = &__dso_handle;

static void finalize(void) {
  for (Initializer *p = __fini_array_end; p != __fini_array_start;) (*--p)();
}

void lefony_event(lefony_event_t event, uint32_t first, uint32_t second) {
  (void)first; (void)second;
  if (event != LEFONY_START || lefony_program_enter() != 0) {
    __asm__ volatile("udf #0");
    return;
  }
  if (atexit(finalize) != 0) lefony_program_exit(127);
  for (Initializer *p = __preinit_array_start; p != __preinit_array_end; ++p) (*p)();
  for (Initializer *p = __init_array_start; p != __init_array_end; ++p) (*p)();
  exit(main(lefony_main_argc, lefony_main_argv));
}
