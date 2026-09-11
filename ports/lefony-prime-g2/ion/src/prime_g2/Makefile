ion_src += $(addprefix ion/src/prime_g2/, \
  app_management.cpp \
  app_storage.cpp \
  legacy_app_storage.cpp \
  littlefs/lfs.c \
  littlefs/lfs_util.c \
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
  native_app.cpp \
  native_app_context.s \
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

# Static littlefs caches; no allocator, stdout, or assertion dependencies.
$(call object_for,$(ion_src)): SFLAGS += -Iion/src/prime_g2/littlefs_compat -DLFS_NO_MALLOC -DLFS_NO_DEBUG -DLFS_NO_WARN -DLFS_NO_ERROR -DLFS_NO_ASSERT

$(call object_for,$(filter %/littlefs/lfs.c %/littlefs/lfs_util.c,$(ion_src))): SFLAGS += -DLFS_DEFINES=littlefs_compat/defines.h
