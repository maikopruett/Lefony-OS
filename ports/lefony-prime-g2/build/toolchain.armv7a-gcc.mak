include build/toolchain.arm-gcc.mak

SFLAGS += -mcpu=cortex-a7 -marm -mfloat-abi=hard -mfpu=neon-vfpv4
SFLAGS += -fno-pic -fno-pie
LDFLAGS += -nostartfiles -no-pie
