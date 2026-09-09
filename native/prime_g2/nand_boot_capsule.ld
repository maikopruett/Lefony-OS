ENTRY(_start)

SECTIONS
{
  . = 0x80800000;
  .text : ALIGN(4)
  {
    KEEP(*(.text.boot))
  }

  /DISCARD/ :
  {
    *(.ARM.attributes)
    *(.comment)
  }
}
