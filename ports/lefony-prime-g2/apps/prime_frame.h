#ifndef PRIME_FRAME_H
#define PRIME_FRAME_H
#if defined(PLATFORM_PRIME_G2)
extern "C" void prime_g2_begin_frame();
extern "C" void prime_g2_end_frame();
extern "C" void prime_g2_cancel_frame();
class PrimeFrame {
public:
  PrimeFrame() { prime_g2_begin_frame(); }
  ~PrimeFrame() { prime_g2_end_frame(); }
  static void cancel() { prime_g2_cancel_frame(); }
};
#else
class PrimeFrame { public: static void cancel() {} };
#endif
#endif
