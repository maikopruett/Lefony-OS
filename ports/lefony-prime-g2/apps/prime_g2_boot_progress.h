#ifndef PRIME_G2_BOOT_PROGRESS_H
#define PRIME_G2_BOOT_PROGRESS_H

#if defined(PLATFORM_PRIME_G2)
extern "C" void prime_g2_boot_progress(unsigned stage);
extern "C" void prime_g2_boot_progress_reset();
extern "C" void prime_g2_first_frame_ready();
extern "C" void prime_g2_update_boot_ready();
inline void PrimeG2BootProgress(unsigned stage) {
  prime_g2_boot_progress(stage);
}
inline void PrimeG2BootProgressReset() {
  prime_g2_boot_progress_reset();
}
inline void PrimeG2FirstFrameReady() {
  prime_g2_first_frame_ready();
}
inline void PrimeG2UpdateBootReady() {
  prime_g2_update_boot_ready();
}
#else
inline void PrimeG2BootProgress(unsigned stage) {
  (void)stage;
}
inline void PrimeG2BootProgressReset() {}
inline void PrimeG2FirstFrameReady() {}
inline void PrimeG2UpdateBootReady() {}
#endif

#endif
