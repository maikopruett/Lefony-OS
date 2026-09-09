ENTRY(_start)

SECTIONS
{
    . = 0x80010000;
    .text : ALIGN(4) {
        KEEP(*(.text.entry))
        *(.text*)
        *(.rodata*)
    }
    /DISCARD/ : {
        *(.ARM.attributes)
        *(.comment)
        *(.note*)
    }
}

ASSERT(SIZEOF(.text) <= 4096, "ROM recovery stub exceeds one page")
