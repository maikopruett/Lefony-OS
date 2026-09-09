#ifndef ION_PRIME_G2_DIAGNOSTICS_H
#define ION_PRIME_G2_DIAGNOSTICS_H

#include <stddef.h>
#include <stdint.h>

namespace PrimeG2 {
namespace Diagnostics {

constexpr uint32_t EventMagic = 0x4D474445;    // "MGDE"
constexpr uint32_t SnapshotMagic = 0x4D475253; // "MGRS"
constexpr uint32_t ProtocolVersion = 1;
constexpr size_t EventCapacity = 128;
constexpr size_t SnapshotWords = 64;

enum EventCode : uint32_t {
  BootStart = 0x0001,
  FatalFaultRegisters = 0x00FD,
  FatalAbort = 0x00FE,
  FatalException = 0x00FF,
  UsbClock = 0x0101,
  UsbPhyReset = 0x0102,
  UsbControllerReset = 0x0103,
  UsbStarted = 0x0104,
  UsbBusReset = 0x0105,
  UsbSetup = 0x0106,
  UsbConfigured = 0x0107,
  UsbError = 0x01FF,
  DisplayInitStart = 0x0201,
  DisplayPinsReady = 0x0202,
  DisplayClockReady = 0x0203,
  PanelResetHigh = 0x0210,
  PanelResetLow = 0x0211,
  PanelResetReleased = 0x0212,
  PanelRegisterWrite = 0x0213,
  PanelReady = 0x0214,
  LcdifResetStep = 0x0220,
  LcdifResetFailed = 0x0221,
  LcdifConfigured = 0x0222,
  LcdifStarted = 0x0223,
  FrameSwapTimeout = 0x0224,
  FrameSwapRecovered = 0x0225,
  DisplayInitComplete = 0x02FF,
  BacklightReady = 0x0301,
  IonMainEntry = 0x0401,
  BootProgress = 0x0402,
  LcdifFault = 0x02FE,
};

struct Event {
  uint32_t magic;
  uint32_t sequence;
  uint32_t timestamp;
  uint32_t code;
  uint32_t value0;
  uint32_t value1;
  uint32_t value2;
};

struct Snapshot {
  uint32_t words[SnapshotWords];
};

void init();
void record(uint32_t code, uint32_t value0 = 0, uint32_t value1 = 0,
            uint32_t value2 = 0);
uint32_t firstSequence();
uint32_t nextSequence();
bool event(uint32_t sequence, Event *result);
void captureSnapshot();
const Snapshot &snapshot();
void monitorDisplay();

}
}

#endif
