TOOLCHAIN ?= armv7a-gcc
USE_LIBA = 1
EXE = elf
MODEL = prime_g2
THEME_NAME = lefony_light
THEME_REPO = local

# Reader and External are host/filesystem-oriented Upsilon additions. Keep the
# initial native image to applications that use Ion's in-memory record store.
EPSILON_APPS = calculation graph rpn code statistics probability solver atomic sequence regression settings

ION_KEYBOARD_LAYOUT = layout_B2
EPSILON_TELEMETRY = 0
EPSILON_GETOPT = 0
LTO ?= 0

SFLAGS += -DPLATFORM_PRIME_G2 -DPRIME_G2_MEMORY_TELEMETRY=1
apps_src += apps/prime_g2_persistent_preferences.cpp \
  apps/prime_g2_persistent_datasets.cpp apps/prime_g2_test_state.cpp
LDSCRIPT = ion/src/prime_g2/boot/prime_g2.ld

HANDY_TARGETS_EXTENSIONS += bin u-boot.elf

include build/targets.prime_g2.mak
