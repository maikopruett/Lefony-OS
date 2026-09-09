#ifndef ION_PRIME_G2_USB_DIAGNOSTICS_H
#define ION_PRIME_G2_USB_DIAGNOSTICS_H

#include <stdint.h>

namespace PrimeG2 {
namespace USBDiagnostics {

constexpr uint16_t VendorId = 0xCAFE;
constexpr uint16_t ProductId = 0x5052;

bool init();
void poll();
bool managementActive();
bool externalPowerConnected();
struct TransferStatus { uint32_t state, received, total; };
TransferStatus transferStatus();
uint32_t statusFlags();
uint32_t firstErrorStep();
// Historical last request survives bus resets; counts disambiguate retries.
struct EnumerationTrace {
  uint32_t magic, version, request, phase, setups, completed, resets, length;
};
EnumerationTrace enumerationTrace();
struct DebugSnapshot {
  EnumerationTrace trace;
  uint32_t flags, error;
  uint32_t command, status, mode, port, setup, prime, flush, complete;
  uint32_t address, list, inToken, outToken, rawSetup0, rawSetup1;
  uint32_t addressWaitPolls, fastAddressCompletions;
};
DebugSnapshot debugSnapshot();
bool configured();
bool plugged();
void shutdown();

}
}

#endif
