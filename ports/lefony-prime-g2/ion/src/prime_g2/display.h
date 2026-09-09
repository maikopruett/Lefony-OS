#ifndef ION_PRIME_G2_DISPLAY_H
#define ION_PRIME_G2_DISPLAY_H

#include <stdint.h>

namespace PrimeG2 {
namespace Display {

void init();
void resume();
bool isInStandby();
void cancelFrame();
// 59 selects the proven 58.893 Hz mode; 55 tests 55.212 Hz until confirmed.
// Experimental choices are intentionally not persisted across reboot.
bool requestRefreshRate(unsigned hz);
bool confirmRefreshRate();
void cancelRefreshTrial();
void pollRefreshTrial();
bool refreshTrialActive();
uint32_t refreshMilliHz();
bool guardsIntact();
uint32_t selfTest();
uint32_t checksum();
uint64_t publishedPixels();
uint32_t publishCount();
const uint32_t * drawingBuffer();
uint32_t presentedFrames();
uint32_t presentationTimeouts();
void bootProgress(unsigned stage);
void resetBootProgress();
void keypadMatrixDiagnostic(const uint8_t matrix[8]);
void shutdown();

}
}

#endif
