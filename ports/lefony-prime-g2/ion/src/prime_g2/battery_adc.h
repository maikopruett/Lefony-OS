#ifndef ION_PRIME_G2_BATTERY_ADC_H
#define ION_PRIME_G2_BATTERY_ADC_H

#include <stdint.h>

namespace PrimeG2 {
namespace BatteryADC {

bool init();
bool readRaw(uint16_t *raw);
uint16_t millivoltsForRaw(uint16_t raw);
bool isInitialized();
bool conversionPending();

}
}

#endif
