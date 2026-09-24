/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
ENTRY(_start)
PHDRS { code PT_LOAD FLAGS(5); data PT_LOAD FLAGS(6); }
SECTIONS {
  . = 0x10000000;
  .text : { KEEP(*(.text.entry)) *(.text*) *(.rodata*) } :code
  .preinit_array ALIGN(4) : {
    PROVIDE_HIDDEN(__preinit_array_start = .);
    KEEP(*(.preinit_array*))
    PROVIDE_HIDDEN(__preinit_array_end = .);
  } :code
  .init_array ALIGN(4) : {
    PROVIDE_HIDDEN(__init_array_start = .);
    KEEP(*(SORT_BY_INIT_PRIORITY(.init_array.*))) KEEP(*(.init_array))
    PROVIDE_HIDDEN(__init_array_end = .);
  } :code
  .fini_array ALIGN(4) : {
    PROVIDE_HIDDEN(__fini_array_start = .);
    KEEP(*(SORT_BY_INIT_PRIORITY(.fini_array.*))) KEEP(*(.fini_array))
    PROVIDE_HIDDEN(__fini_array_end = .);
  } :code
  ASSERT(. <= 0x10100000, "app code exceeds reservation")
  . = 0x10201000;
  .data : { *(.data*) } :data
  .lefony.heap_profile ALIGN(4) : { KEEP(*(.lefony.heap_profile)) } :data
  .bss (NOLOAD) : { *(.bss*) *(COMMON) } :data
  ASSERT(. <= 0x102ef000, "app data exceeds reservation")
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.note*) }
}
