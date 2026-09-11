/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
ENTRY(_start)
PHDRS { code PT_LOAD FLAGS(5); data PT_LOAD FLAGS(6); }
SECTIONS {
  . = 0x10000000;
  .text : { KEEP(*(.text.entry)) *(.text*) *(.rodata*) } :code
  ASSERT(. <= 0x10100000, "app code exceeds reservation")
  . = 0x10201000;
  .data : { *(.data*) } :data
  .bss (NOLOAD) : { *(.bss*) *(COMMON) } :data
  ASSERT(. <= 0x102ef000, "app data exceeds reservation")
  .unsupported : { *(.init_array*) *(.fini_array*) *(.ctors*) *(.dtors*) }
  ASSERT(SIZEOF(.unsupported) == 0, "dynamic global constructors are unsupported")
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.note*) }
}
