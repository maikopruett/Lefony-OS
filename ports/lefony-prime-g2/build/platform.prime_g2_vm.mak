include build/platform.prime_g2.mak

# Upstream QEMU's mcimx6ul-evk machine does not implement the Prime's KPP,
# GPT oscillator selector 5, or LCDIF serial-RGB path. Keep these substitutions
# isolated from the physical Prime build.
SFLAGS += -DPRIME_G2_EMULATOR=1 -mno-unaligned-access
