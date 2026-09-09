ion_src += $(addprefix ion/src/prime_g2/, \
  backlight.cpp \
  battery_adc.cpp \
  block_storage.cpp \
  board.cpp \
  console.cpp \
  diagnostics.cpp \
  development_update.cpp \
  display.cpp \
  emulator.cpp \
  events.cpp \
  i2c.cpp \
  interrupts.cpp \
  keyboard.cpp \
  nand_update.cpp \
  nand_physical.cpp \
  platform.cpp \
  persistence.cpp \
  services.cpp \
  support.cpp \
  system.cpp \
  timing.cpp \
  touch.cpp \
  uart.cpp \
  usb.cpp \
  usb_diagnostics.cpp \
  watchdog.cpp \
  boot/runtime.cpp \
  boot/start.s \
)

# Remaining unsupported services are explicit conservative stubs.
ion_src += $(addprefix ion/src/shared/dummy/, \
  board.cpp \
  exam_mode.cpp \
)

ion_src += ion/src/shared/collect_registers.cpp

$(call object_for,$(ion_src)): SFLAGS += -Iion/src/prime_g2
