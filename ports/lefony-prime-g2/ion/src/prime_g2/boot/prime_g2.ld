/* RAM-loaded HP Prime G2 image. U-Boot owns DDR initialization and loads the
 * ELF. The native image deliberately stays away from U-Boot's normal load
 * address and the top-of-RAM framebuffer. */

ENTRY(_start)

MEMORY {
  IMAGE (rwx) : ORIGIN = 0x82000000, LENGTH = 48M
  FRAMEBUFFER (rw) : ORIGIN = 0x8F000000, LENGTH = 1M
}

STACK_SIZE = 1M;

SECTIONS {
  .text : {
    _text_start = .;
    KEEP(*(.vectors))
    KEEP(*(.text._start))
    *(.text)
    *(.text.*)
  } > IMAGE

  .rodata : {
    . = ALIGN(16);
    *(.rodata)
    *(.rodata.*)
  } > IMAGE

  .init_array : {
    . = ALIGN(4);
    _init_array_start = .;
    KEEP(*(.init_array*))
    _init_array_end = .;
  } > IMAGE

  .data : {
    /* A section boundary lets the ARMv7 first-level table protect all code
     * and constants read-only while keeping mutable state RW+XN. */
    . = ALIGN(1M);
    _text_end = .;
    _data_start = .;
    *(.data)
    *(.data.*)
  } > IMAGE

  .bss (NOLOAD) : {
    . = ALIGN(16);
    _bss_start = .;
    KEEP(*(.static_storage))
    *(.bss)
    *(.bss.*)
    *(COMMON)
    _bss_end = .;
  } > IMAGE

  .heap (NOLOAD) : {
    . = ALIGN(16);
    _heap_start = .;
    . = ORIGIN(IMAGE) + LENGTH(IMAGE) - STACK_SIZE;
    _heap_end = .;
  } > IMAGE

  .stack (NOLOAD) : {
    . = ALIGN(16);
    _stack_bottom = .;
    . += STACK_SIZE;
    _stack_top = .;
    _stack_exception_und = _stack_top - 0x1000;
    _stack_exception_abt = _stack_top - 0x2000;
    _stack_exception_irq = _stack_top - 0x3000;
    _stack_exception_fiq = _stack_top - 0x4000;
    _stack_main_top = _stack_top - 0x5000;
    _data_end = .;
  } > IMAGE

  .framebuffer (NOLOAD) : {
    . = ALIGN(64);
    _framebuffer_start = .;
    KEEP(*(.framebuffer))
    _framebuffer_end = .;
  } > FRAMEBUFFER

  /DISCARD/ : {
    *(.ARM.exidx*)
    *(.ARM.extab*)
    *(.comment)
  }
}

ASSERT(_heap_start < _heap_end, "Prime G2 image leaves no heap")
ASSERT((_framebuffer_end - _framebuffer_start) <= LENGTH(FRAMEBUFFER),
       "Prime G2 framebuffer overflow")
