#include "usb_diagnostics.h"

#include "diagnostics.h"
#include "battery_adc.h"
#include "nand_update.h"
#include "nand_physical.h"
#include "development_update.h"
#include "registers.h"
#include "services.h"
#include "system.h"
#include "watchdog.h"

#include <ion.h>
#include <ion/timing.h>
#include "timing.h"
#include <stddef.h>
#include <string.h>

namespace {

using PrimeG2::reg32;

constexpr uintptr_t USB = PrimeG2::USBOTG1;
constexpr uintptr_t USBCMD = USB + 0x140;
constexpr uintptr_t USBSTS = USB + 0x144;
constexpr uintptr_t USBINTR = USB + 0x148;
constexpr uintptr_t DEVICEADDR = USB + 0x154;
constexpr uintptr_t ENDPTLISTADDR = USB + 0x158;
constexpr uintptr_t BURSTSIZE = USB + 0x160;
constexpr uintptr_t PORTSC1 = USB + 0x184;
constexpr uintptr_t OTGSC = USB + 0x1A4;
constexpr uintptr_t USBMODE = USB + 0x1A8;
constexpr uintptr_t ENDPTSETUPSTAT = USB + 0x1AC;
constexpr uintptr_t ENDPTPRIME = USB + 0x1B0;
constexpr uintptr_t ENDPTFLUSH = USB + 0x1B4;
constexpr uintptr_t ENDPTSTAT = USB + 0x1B8;
constexpr uintptr_t ENDPTCOMPLETE = USB + 0x1BC;
constexpr uintptr_t ENDPTCTRL0 = USB + 0x1C0;

constexpr uint32_t InterruptUsb = 1u << 0;
constexpr uint32_t InterruptError = 1u << 1;
constexpr uint32_t InterruptPortChange = 1u << 2;
constexpr uint32_t InterruptReset = 1u << 6;
constexpr uint32_t InterruptSuspend = 1u << 8;
constexpr uint32_t InterruptMask = InterruptUsb | InterruptError |
  InterruptPortChange | InterruptReset | InterruptSuspend;
constexpr uint32_t Endpoint0Mask = (1u << 0) | (1u << 16);
constexpr uint32_t TransferActive = 1u << 7;
constexpr uint32_t TransferIoc = 1u << 15;
constexpr uint32_t TransferTerminate = 1u;

enum Status : uint32_t {
  StatusClock = 1u << 0,
  StatusPhy = 1u << 1,
  StatusController = 1u << 2,
  StatusBusReset = 1u << 3,
  StatusConfigured = 1u << 4,
  StatusHighSpeed = 1u << 5,
  StatusError = 1u << 31,
};

enum class ControlState {
  Idle,
  DataIn,
  DataOut,
  StatusIn,
  StatusOut,
};

struct __attribute__((packed)) SetupPacket {
  uint8_t requestType;
  uint8_t request;
  uint16_t value;
  uint16_t index;
  uint16_t length;
};

struct alignas(64) QueueHead {
  volatile uint32_t capability;
  volatile uint32_t current;
  volatile uint32_t overlayNext;
  volatile uint32_t overlayToken;
  volatile uint32_t overlayBuffer[5];
  volatile uint32_t overlayReserved;
  volatile uint32_t setup[2];
  volatile uint32_t reserved[4];
};

struct alignas(32) TransferDescriptor {
  volatile uint32_t next;
  volatile uint32_t token;
  volatile uint32_t buffer[5];
  volatile uint32_t reserved;
};

static_assert(sizeof(QueueHead) == 64, "ChipIdea queue head must be 64 bytes");
static_assert(sizeof(TransferDescriptor) == 32,
              "ChipIdea transfer descriptor must be 32 bytes");

struct alignas(2048) ControllerMemory {
  QueueHead queueHeads[2]; // endpoint 0 OUT, endpoint 0 IN
  TransferDescriptor descriptors[2];
};

ControllerMemory sControllerMemory;
uint8_t sControlBuffer[512] __attribute__((aligned(64)));
ControlState sControlState = ControlState::Idle;
uint32_t sStatus = 0;
uint32_t sFirstErrorStep = 0;
PrimeG2::USBDiagnostics::EnumerationTrace sEnumeration = {0x4c465554, 1};
bool sTraceCurrentRequest = false;
uint32_t sLastSetupWords[2] = {};
// Phase: 1 setup, 2 IN data queued, 3 OUT status queued, 4 IN status
// queued, 5 status completed, 6 stalled, 7 transfer error, 8 OUT data queued.
uint8_t sConfiguration = 0;
uint64_t sLastManagementTime = 0;
bool sManagementSeen = false;
bool sInstallAfterStatus = false;

constexpr uint32_t RecoveryMagic = 0x4D475243; // "CRGM" little endian
constexpr size_t RecoveryCapacity = 8u * 1024u * 1024u;
enum class RecoveryState : uint32_t { Idle, Receiving, Ready, Error };
uint8_t sRecoveryImage[RecoveryCapacity] __attribute__((aligned(64)));
RecoveryState sRecoveryState = RecoveryState::Idle;
uint32_t sRecoveryLength = 0;
uint32_t sRecoveryReceived = 0;
uint32_t sRecoveryCRC = 0;
SetupPacket sPendingOut = {};
bool sRebootAfterStatus = false;
bool sRecoveryAfterStatus = false;
int sPendingAddress = -1; // -1 means none; USB address zero is valid
uint32_t sAddressWaitPolls = 0;
uint32_t sFastAddressCompletions = 0;
void handleComplete(uint32_t complete);

// SET_ADDRESS is timing-sensitive: after the status packet the host can
// immediately use the new address. Do not defer that write to a later UI
// poll. Bound the wait so a missing host ACK cannot hang the calculator.
void finishAddressStatusPromptly() {
  sAddressWaitPolls = 0;
  for (unsigned attempt = 0; attempt < 2000; attempt++) {
    sAddressWaitPolls++;
    // Reset or replacement SETUP aborts this request. Leave both pending
    // events for the normal handler rather than consuming stale completion.
    if ((reg32(USBSTS) & InterruptReset) || (reg32(ENDPTSETUPSTAT) & 1u)) {
      sPendingAddress = -1;
      return;
    }
    if (reg32(ENDPTCOMPLETE) & (1u << 16)) {
      reg32(ENDPTCOMPLETE) = 1u << 16;
      handleComplete(1u << 16);
      if (sControlState == ControlState::Idle && sPendingAddress < 0)
        sFastAddressCompletions++;
      return;
    }
    Ion::Timing::usleep(10);
  }
  // No reset/retry/forced address: an eventual ACK is still handled by poll.
}

constexpr uint8_t DeviceDescriptor[] = {
  18, 1, 0x00, 0x02, 0x00, 0x00, 0x00, 64,
  0xFE, 0xCA, 0x52, 0x50, 0x00, 0x01, 1, 2, 3, 1
};

constexpr uint8_t ConfigurationDescriptor[] = {
  9, 2, 18, 0, 1, 1, 0, 0x80, 25,
  9, 4, 0, 0, 0, 0xFF, 0x4D, 0x47, 0
};

constexpr uint8_t DeviceQualifierDescriptor[] = {
  10, 6, 0x00, 0x02, 0x00, 0x00, 0x00, 64, 1, 0
};

bool waitFor(uintptr_t address, uint32_t mask, bool set,
             unsigned attempts = 2000) {
  while (attempts--) {
    if ((reg32(address) & mask) == (set ? mask : 0)) return true;
    Ion::Timing::usleep(10);
  }
  return false;
}

void fail(uint32_t step, uint32_t address) {
  if (!sFirstErrorStep) sFirstErrorStep = step;
  sStatus |= StatusError;
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::UsbError, step,
                               address, reg32(address));
}

bool initClockAndPhy() {
  // Match mxs_phy_init(): allow the PHY clock domain to switch away from its
  // 32 kHz low-power source before enabling the AHB/controller clock.
  Ion::Timing::usleep(400);

  // USB OH3 IPG/AHB clock.
  PrimeG2::gate(0x80, 0);

  // PLL3 USB1: power, enable its 480 MHz USB output, and select the PLL
  // rather than the bypass input. Preserve U-Boot's multiplier selection.
  uint32_t pll = reg32(PrimeG2::ANATOP + 0x10);
  // IMX6UL_CLK_USBPHY1 is the ANATOP bit-20 gate. Bit 6 is the USB 480 MHz
  // output gate enabled globally by Linux's clock init. USBOH3 alone clocks
  // only the ChipIdea register interface.
  pll |= (1u << 20) | (1u << 13) | (1u << 12) | (1u << 6);
  pll &= ~(1u << 16);
  reg32(PrimeG2::ANATOP + 0x10) = pll;
  PrimeG2::barrier();
  if (!waitFor(PrimeG2::ANATOP + 0x10, 1u << 31, true)) {
    fail(1, PrimeG2::ANATOP + 0x10);
    return false;
  }
  sStatus |= StatusClock;
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::UsbClock, pll,
                               reg32(PrimeG2::CCM + 0x80), 0);

  constexpr uint32_t SoftReset = 1u << 31;
  constexpr uint32_t ClockGate = 1u << 30;
  uintptr_t control = PrimeG2::USBPHY1 + 0x30;
  reg32(control + 0x08) = SoftReset;
  Ion::Timing::usleep(1);
  if (!waitFor(control, SoftReset, false)) {
    fail(2, control);
    return false;
  }
  reg32(control + 0x08) = ClockGate;
  reg32(control + 0x04) = SoftReset;
  Ion::Timing::usleep(1);
  if (!waitFor(control, ClockGate, true)) {
    fail(3, control);
    return false;
  }
  reg32(control + 0x08) = SoftReset;
  if (!waitFor(control, SoftReset, false)) {
    fail(4, control);
    return false;
  }
  reg32(control + 0x08) = ClockGate;
  if (!waitFor(control, ClockGate, false)) {
    fail(5, control);
    return false;
  }

  // Prime DT: phy-3p0-supply = &reg_3p0, with enable bit 0 in
  // ANATOP_REG_3P0. Linux enables this supply before clearing PHY PWD.
  PrimeG2::setBits(PrimeG2::ANATOP + 0x120, 1u);
  reg32(PrimeG2::USBPHY1 + 0x00) = 0; // power every PHY block
  constexpr uint32_t AutoPhy = (1u << 26) | (1u << 25) | (1u << 20) |
    (1u << 19) | (1u << 18) | (1u << 15) | (1u << 14);
  reg32(PrimeG2::USBPHY1 + 0x34) = AutoPhy;

  // Prime device tree fsl,tx-d-cal=106 maps to hardware calibration code 5.
  PrimeG2::updateBits(PrimeG2::USBPHY1 + 0x10, 0xFu, 5u);

  // Disable charger detection so its analog pulldowns do not interfere with
  // normal USB device enumeration.
  reg32(PrimeG2::ANATOP + 0x1B4) = (1u << 20) | (1u << 19);

  // Mirror the i.MX6UL usbmisc setup: non-burst mode, BVALID as the VBUS
  // wake source, and no DP/DM wakeup while running as a peripheral.
  PrimeG2::setBits(PrimeG2::USBNC + 0x00, 1u << 1);
  PrimeG2::clearBits(PrimeG2::USBNC + 0x00,
                     (1u << 29) | (1u << 17) | (1u << 16) | (1u << 10));
  PrimeG2::setBits(PrimeG2::USBNC + 0x18, 2u << 8);
  PrimeG2::barrier();

  sStatus |= StatusPhy;
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::UsbPhyReset,
                               reg32(control),
                               reg32(PrimeG2::USBPHY1 + 0x10),
                               reg32(PrimeG2::USBNC));
  return true;
}

void initializeQueueHeads() {
  memset(&sControllerMemory, 0, sizeof(sControllerMemory));
  sControllerMemory.queueHeads[0].capability =
    (64u << 16) | (1u << 15) | (1u << 29); // IOS, ZLT
  sControllerMemory.queueHeads[1].capability =
    (64u << 16) | (1u << 15) | (1u << 29); // IOS, ZLT
  sControllerMemory.queueHeads[0].overlayNext = TransferTerminate;
  sControllerMemory.queueHeads[1].overlayNext = TransferTerminate;
  sControlState = ControlState::Idle;
  // Publish the initialized queue heads before the controller may DMA into
  // their SETUP buffer. A barrier alone does not write back dirty cache lines.
  PrimeG2::System::cleanDataCacheRange(&sControllerMemory, sizeof(sControllerMemory));
  PrimeG2::barrier();
}

bool resetController() {
  reg32(USBCMD) &= ~1u;
  reg32(USBCMD) |= 1u << 1;
  PrimeG2::barrier();
  if (!waitFor(USBCMD, 1u << 1, false)) {
    fail(6, USBCMD);
    return false;
  }

  reg32(USBMODE) = 0;
  // Device mode, setup lockout mode, and the mandatory i.MX6UL device
  // streaming disable erratum flag (CI_HDRC_DISABLE_DEVICE_STREAMING).
  reg32(USBMODE) = 2u | (1u << 3) | (1u << 4);
  if ((reg32(USBMODE) & 3u) != 2u) {
    fail(7, USBMODE);
    return false;
  }

  reg32(BURSTSIZE) = (16u << 8) | 16u;
  uint32_t portsc = reg32(PORTSC1);
  // Never write a sampled W1C status bit back as one while changing the PHY
  // mode fields.  Doing so would acknowledge a connection/enable/overcurrent
  // transition before the polling loop has observed it.
  portsc &= ~((3u << 30) | (1u << 28) | (1u << 24) | (1u << 23) |
              (1u << 5) | (1u << 3) | (1u << 1));
  reg32(PORTSC1) = portsc;
  // Clear OTG status and leave OTG interrupts disabled. Bits 0 and 3 are
  // reserved on this ChipIdea revision and must never be forced high.
  reg32(OTGSC) = 0x007F0000u;

  initializeQueueHeads();
  reg32(ENDPTLISTADDR) =
    reinterpret_cast<uintptr_t>(&sControllerMemory.queueHeads[0]);
  reg32(DEVICEADDR) = 0;
  reg32(USBSTS) = reg32(USBSTS);
  reg32(USBINTR) = InterruptMask;
  reg32(USBCMD) = (reg32(USBCMD) & ~0x00FF0000u) | 1u;
  PrimeG2::barrier();

  sStatus |= StatusController;
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::UsbControllerReset,
                               reg32(USBMODE), reg32(PORTSC1),
                               reg32(ENDPTLISTADDR));
  return true;
}

bool flushEndpoint0() {
  if ((reg32(ENDPTSTAT) | reg32(ENDPTPRIME)) & Endpoint0Mask) {
    reg32(ENDPTFLUSH) = Endpoint0Mask;
    if (!waitFor(ENDPTFLUSH, Endpoint0Mask, false, 2000)) {
      fail(8, ENDPTFLUSH);
      return false;
    }
  }
  return true;
}

void prime(unsigned direction, const void *data, uint16_t length) {
  QueueHead &qh = sControllerMemory.queueHeads[direction];
  TransferDescriptor &td = sControllerMemory.descriptors[direction];
  memset(&td, 0, sizeof(td));
  td.next = TransferTerminate;
  td.token = (static_cast<uint32_t>(length) << 16) |
    TransferIoc | TransferActive;
  if (data != nullptr) {
    uintptr_t address = reinterpret_cast<uintptr_t>(data);
    td.buffer[0] = address;
    for (unsigned i = 1; i < 5; i++) {
      td.buffer[i] = (address + i * 0x1000u) & ~0xFFFu;
    }
  }
  qh.overlayToken &= ~((1u << 7) | (1u << 6));
  qh.overlayNext = reinterpret_cast<uintptr_t>(&td);
  if (direction && data != nullptr && length != 0)
    PrimeG2::System::cleanDataCacheRange(data, length);
  if (!direction && data != nullptr && length != 0)
    PrimeG2::System::cleanInvalidateDataCacheRange(data, length);
  PrimeG2::System::cleanDataCacheRange(&sControllerMemory,
                                        sizeof(sControllerMemory));
  PrimeG2::barrier();
  reg32(ENDPTPRIME) = 1u << (direction ? 16 : 0);
}

void stallControl() {
  sPendingAddress = -1;
  if (sTraceCurrentRequest) sEnumeration.phase = 6;
  if (!flushEndpoint0()) return;
  reg32(ENDPTCTRL0) |= (1u << 0) | (1u << 16);
  sControlState = ControlState::Idle;
}

void controlIn(const void *data, uint16_t length, uint16_t requested) {
  if (length > requested) length = requested;
  if (length > sizeof(sControlBuffer)) length = sizeof(sControlBuffer);
  if (length != 0 && data != sControlBuffer) {
    memcpy(sControlBuffer, data, length);
  }
  prime(1, sControlBuffer, length);
  sControlState = ControlState::DataIn;
  if (sTraceCurrentRequest) sEnumeration.phase = 2;
}

void statusIn() {
  prime(1, nullptr, 0);
  sControlState = ControlState::StatusIn;
  if (sTraceCurrentRequest) sEnumeration.phase = 4;
}

void controlOut(const SetupPacket &setup) {
  if (setup.length == 0 || setup.length > sizeof(sControlBuffer)) {
    stallControl();
    return;
  }
  sPendingOut = setup;
  prime(0, sControlBuffer, setup.length);
  sControlState = ControlState::DataOut;
  if (sTraceCurrentRequest) sEnumeration.phase = 8;
}

uint32_t setupValue32(const SetupPacket &setup) {
  return static_cast<uint32_t>(setup.value) |
    (static_cast<uint32_t>(setup.index) << 16);
}

bool validRecoveryCapsule() {
  if (sRecoveryLength < 0x30 || sRecoveryReceived != sRecoveryLength) return false;
  uint32_t magic;
  uint32_t declaredLength;
  memcpy(&magic, sRecoveryImage + 0x24, sizeof(magic));
  memcpy(&declaredLength, sRecoveryImage + 0x2C, sizeof(declaredLength));
  return magic == 0x016F2818 && declaredLength == sRecoveryLength;
}

void handleRecoveryDataOut(uint16_t received) {
  uint32_t offset = setupValue32(sPendingOut);
  if (sRecoveryState != RecoveryState::Receiving ||
      offset != sRecoveryReceived || received != sPendingOut.length ||
      offset > sRecoveryLength || received > sRecoveryLength - offset) {
    sRecoveryState = RecoveryState::Error;
    return;
  }
  memcpy(sRecoveryImage + offset, sControlBuffer, received);
  sRecoveryReceived += received;
}

uint16_t makeStringDescriptor(const char *text) {
  size_t length = strlen(text);
  if (length > 126) length = 126;
  sControlBuffer[0] = static_cast<uint8_t>(2 + length * 2);
  sControlBuffer[1] = 3;
  for (size_t i = 0; i < length; i++) {
    sControlBuffer[2 + i * 2] = static_cast<uint8_t>(text[i]);
    sControlBuffer[3 + i * 2] = 0;
  }
  return sControlBuffer[0];
}

bool descriptor(const SetupPacket &setup) {
  uint8_t type = setup.value >> 8;
  uint8_t index = setup.value & 0xFF;
  switch (type) {
    case 1:
      controlIn(DeviceDescriptor, sizeof(DeviceDescriptor), setup.length);
      return true;
    case 2:
      controlIn(ConfigurationDescriptor, sizeof(ConfigurationDescriptor),
                setup.length);
      return true;
    case 3:
      if (index == 0) {
        const uint8_t language[] = {4, 3, 0x09, 0x04};
        controlIn(language, sizeof(language), setup.length);
      } else if (index == 1) {
        uint16_t length = makeStringDescriptor("Lefony OS");
        controlIn(sControlBuffer, length, setup.length);
      } else if (index == 2) {
        uint16_t length = makeStringDescriptor("Lefony OS Hardware Diagnostics");
        controlIn(sControlBuffer, length, setup.length);
      } else if (index == 3) {
        uint16_t length = makeStringDescriptor("LEFONY-PG2-DIAG-01");
        controlIn(sControlBuffer, length, setup.length);
      } else {
        return false;
      }
      return true;
    case 6:
      controlIn(DeviceQualifierDescriptor, sizeof(DeviceQualifierDescriptor),
                setup.length);
      return true;
    case 7: {
      memcpy(sControlBuffer, ConfigurationDescriptor,
             sizeof(ConfigurationDescriptor));
      sControlBuffer[1] = 7;
      controlIn(sControlBuffer, sizeof(ConfigurationDescriptor), setup.length);
      return true;
    }
    default:
      return false;
  }
}

bool standardRequest(const SetupPacket &setup) {
  switch (setup.request) {
    case 0: { // GET_STATUS
      const uint8_t status[] = {0, 0};
      controlIn(status, sizeof(status), setup.length);
      return true;
    }
    case 5: // SET_ADDRESS
      if (setup.requestType != 0x00 || setup.index != 0 ||
          setup.length != 0 || setup.value > 127) return false;
      // Like Linux's isr_setup_status_complete, apply this only after the
      // status IN completes at the OLD address. USBADRA is not used here.
      sPendingAddress = setup.value;
      statusIn();
      finishAddressStatusPromptly();
      return true;
    case 6: // GET_DESCRIPTOR
      return descriptor(setup);
    case 8: // GET_CONFIGURATION
      sControlBuffer[0] = sConfiguration;
      controlIn(sControlBuffer, 1, setup.length);
      return true;
    case 9: // SET_CONFIGURATION
      if (setup.value > 1) return false;
      sConfiguration = setup.value;
      if (sConfiguration) sStatus |= StatusConfigured;
      else sStatus &= ~StatusConfigured;
      PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::UsbConfigured,
                                   sConfiguration, reg32(PORTSC1), sStatus);
      statusIn();
      return true;
    case 10: // GET_INTERFACE
      sControlBuffer[0] = 0;
      controlIn(sControlBuffer, 1, setup.length);
      return true;
    case 11: // SET_INTERFACE
      if (setup.value != 0 || setup.index != 0) return false;
      statusIn();
      return true;
    default:
      return false;
  }
}

bool vendorRequest(const SetupPacket &setup) {
  // The staged payload and shared NAND DMA buffers are immutable while the
  // native writer runs. USB status queries remain available, but no abort,
  // new upload, NAND probe/read, or recovery command can interrupt it.
  if (PrimeG2::DevelopmentUpdate::busy() &&
      !(setup.requestType == 0xc0 && setup.request == 0x53)) return false;
  /* A full capsule can take longer than the normal idle-suspend interval on
   * slow hosts and instrumented emulators. USB management traffic is active
   * use of the calculator and must keep the runtime awake. */
  PrimeG2::Services::noteUserActivity();
  sLastManagementTime = Ion::Timing::millis();
  sManagementSeen = true;
  if ((setup.requestType & 0x80) == 0) {
    switch (setup.request) {
      case 0x53:
        if (setup.requestType != 0x40 || setup.length ||
            sRecoveryState != RecoveryState::Ready ||
            setupValue32(setup) != sRecoveryCRC) return false;
        sInstallAfterStatus = true;
        statusIn();
        return true;
      case 0x54:
        if (setup.requestType != 0x40 || setup.length ||
            PrimeG2::DevelopmentUpdate::status().state != PrimeG2::DevelopmentUpdate::Complete)
          return false;
        sRebootAfterStatus = true;
        statusIn();
        return true;
      case 0x44: { // begin sequential RAM staging; wIndex:wValue is size
        uint32_t length = setupValue32(setup);
        if (setup.length != 0 || length < 0x30 || length > RecoveryCapacity)
          return false;
        sRecoveryLength = length;
        PrimeG2::DevelopmentUpdate::clearResult();
        sRecoveryReceived = 0;
        sRecoveryCRC = 0;
        sRecoveryState = RecoveryState::Receiving;
        statusIn();
        return true;
      }
      case 0x45: // sequential capsule chunk; wIndex:wValue is offset
        if (sRecoveryState != RecoveryState::Receiving) return false;
        controlOut(setup);
        return true;
      case 0x46: { // finish; wIndex:wValue is CRC32
        if (setup.length != 0 || !validRecoveryCapsule()) {
          sRecoveryState = RecoveryState::Error;
          return false;
        }
        sRecoveryCRC = Ion::crc32Byte(sRecoveryImage, sRecoveryLength);
        if (sRecoveryCRC != setupValue32(setup)) {
          sRecoveryState = RecoveryState::Error;
          return false;
        }
        if (PrimeG2::NANDUpdate::status().state ==
              static_cast<uint32_t>(PrimeG2::NANDUpdate::State::ManifestReady) &&
            !PrimeG2::NANDUpdate::noteCapsuleReady(sRecoveryImage,
                                                   sRecoveryLength)) {
          sRecoveryState = RecoveryState::Error;
          return false;
        }
        sRecoveryState = RecoveryState::Ready;
        statusIn();
        return true;
      }
      case 0x47: // abort staging
        sRecoveryState = RecoveryState::Idle;
        sRecoveryLength = sRecoveryReceived = sRecoveryCRC = 0;
        PrimeG2::NANDUpdate::abort();
        statusIn();
        return true;
      case 0x48: // signed A/B update manifest in the OUT data stage
        if (setup.length != PrimeG2::NANDUpdate::ManifestBytes) return false;
        controlOut(setup);
        return true;
      case 0x49: // verify readback, commit pending metadata
        if (setup.length != 0 || sRecoveryState != RecoveryState::Ready ||
            !PrimeG2::NANDUpdate::install(sRecoveryImage, sRecoveryLength))
          return false;
        statusIn();
        return true;
      case 0x4B: // reboot only after a verified pending commit
        if (setup.length != 0 || PrimeG2::NANDUpdate::status().state !=
              static_cast<uint32_t>(PrimeG2::NANDUpdate::State::PendingReboot))
          return false;
        sRebootAfterStatus = true;
        statusIn();
        return true;
      case 0x51: // BCH-corrected read of a physical page in the OS slot only
        if (setup.requestType != 0x40 || setup.length != 0 ||
            sRecoveryState == RecoveryState::Receiving) return false;
        PrimeG2::NANDPhysical::readPage(setupValue32(setup));
        statusIn();
        return true;
      case 0x50: // explicitly requested read-only physical NAND qualification
        if (setup.requestType != 0x40 || setup.length != 0 ||
            setup.value != 0x4e50 || setup.index != 0 ||
            sRecoveryState == RecoveryState::Receiving) return false;
        PrimeG2::NANDPhysical::probe();
        statusIn();
        return true;
      case 0x4E: // explicit development handoff; no native NAND programming
        if (setup.requestType != 0x40 || setup.length != 0 ||
            sRecoveryState != RecoveryState::Ready ||
            setupValue32(setup) != sRecoveryCRC) return false;
        sRecoveryAfterStatus = true;
        statusIn();
        return true;
      case 0x4C: // authenticated physical update handoff to ROM recovery
#if !PRIME_G2_EMULATOR
        if (setup.length != 0 || PrimeG2::NANDUpdate::status().state !=
              static_cast<uint32_t>(PrimeG2::NANDUpdate::State::CapsuleReady))
          return false;
        sRecoveryAfterStatus = true;
        statusIn();
        return true;
#else
        return false;
#endif
      default:
        return false;
    }
  }
  switch (setup.request) {
    case 0x55: { // read-only battery/timer diagnostics; never consume ADC R0
      if (setup.requestType != 0xC0 || setup.index) return false;
      if (setup.value == 2) {
        uint64_t elapsed = PrimeG2::Timing::elapsedMillis();
        const uint32_t clock[] = {0x3143544c, 1,
          static_cast<uint32_t>(elapsed), static_cast<uint32_t>(elapsed >> 32)};
        controlIn(clock, sizeof(clock), setup.length);
        return true;
      }
      if (setup.value == 1) {
        const uint32_t display[] = {0x3154424c, 1,
          static_cast<uint32_t>(Ion::Battery::level()),
          PrimeG2::Services::batteryPercent()};
        controlIn(display, sizeof(display), setup.length);
        return true;
      }
      if (setup.value != 0) return false;
      uint32_t cycles;
      asm volatile("mrc p15, 0, %0, c9, c13, 0" : "=r"(cycles));
      constexpr uintptr_t adc = 0x02198000;
      const uint32_t report[] = {
        0x3154424c, 1, static_cast<uint32_t>(Ion::Timing::millis()), cycles,
        reg32(PrimeG2::GPT1), reg32(PrimeG2::GPT1 + 4),
        reg32(PrimeG2::GPT1 + 0x24), reg32(PrimeG2::CCM + 0x6C),
        reg32(adc), reg32(adc + 8), reg32(adc + 0x14),
        reg32(adc + 0x18), reg32(adc + 0x1C),
        PrimeG2::BatteryADC::isInitialized(),
        PrimeG2::BatteryADC::conversionPending(),
        PrimeG2::Services::batteryRawADC(),
        PrimeG2::Services::batteryMillivolts(),
        PrimeG2::Services::batteryEstimateIsCalibrated(),
        reg32(PrimeG2::SNVS + 0x38), reg32(PrimeG2::SNVS + 0x50),
        reg32(PrimeG2::SNVS + 0x54), reg32(PrimeG2::CCM + 0x1C),
        reg32(PrimeG2::CCM + 0x54), reg32(PrimeG2::GPT1 + 8),
      };
      controlIn(report, sizeof(report), setup.length);
      return true;
    }
    case 0x53: {
      const auto &status = PrimeG2::DevelopmentUpdate::status();
      controlIn(&status, sizeof(status), setup.length);
      return true;
    }
    case 0x51: {
      const auto &report = PrimeG2::NANDPhysical::pageReport();
      controlIn(&report, sizeof(report), setup.length);
      return true;
    }
    case 0x52: {
      const uint8_t *data = PrimeG2::NANDPhysical::pageData();
      if (!data || setup.index != 0 || setup.value >= 2048) return false;
      uint16_t length = 2048 - setup.value;
      if (length > sizeof(sControlBuffer)) length = sizeof(sControlBuffer);
      controlIn(data + setup.value, length, setup.length);
      return true;
    }
    case 0x50: { // frozen probe report; read alone never starts NAND activity
      if (setup.requestType != 0xC0) return false;
      const auto &report = PrimeG2::NANDPhysical::report();
      controlIn(&report, sizeof(report), setup.length);
      return true;
    }
    case 0x4E: { // development protocol capabilities, independent of signed A/B
      if (setup.requestType != 0xC0) return false;
      const uint32_t capabilities[] = {0x3156444c, 1, 3, RecoveryCapacity};
      controlIn(capabilities, sizeof(capabilities), setup.length);
      return true;
    }
    case 0x40: { // protocol/device info
      PrimeG2::Diagnostics::captureSnapshot();
      uint32_t info[16] = {
        0x4D474449, PrimeG2::Diagnostics::ProtocolVersion, sStatus,
        PrimeG2::Diagnostics::firstSequence(),
        PrimeG2::Diagnostics::nextSequence(),
        sizeof(PrimeG2::Diagnostics::Event),
        sizeof(PrimeG2::Diagnostics::Snapshot),
        PrimeG2::Diagnostics::EventCapacity,
        reg32(PORTSC1), reg32(USBSTS), reg32(USBMODE), reg32(ENDPTCTRL0),
        reg32(PrimeG2::LCDIF + 0x00), reg32(PrimeG2::LCDIF + 0x10),
        reg32(PrimeG2::LCDIF + 0x1D0), 0
      };
      controlIn(info, sizeof(info), setup.length);
      return true;
    }
    case 0x4D: { // read-only enumeration trace; does not replace last request
      auto trace = sEnumeration;
      controlIn(&trace, sizeof(trace), setup.length);
      return true;
    }
    case 0x41: { // one boot event; sequence is wIndex:wValue
      uint32_t sequence = static_cast<uint32_t>(setup.value) |
        (static_cast<uint32_t>(setup.index) << 16);
      PrimeG2::Diagnostics::Event event;
      if (!PrimeG2::Diagnostics::event(sequence, &event)) return false;
      controlIn(&event, sizeof(event), setup.length);
      return true;
    }
    case 0x42: { // frozen snapshot page; byte offset is wValue
      const PrimeG2::Diagnostics::Snapshot &snapshot =
        PrimeG2::Diagnostics::snapshot();
      uint16_t offset = setup.value;
      if (offset >= sizeof(snapshot)) return false;
      uint16_t available = sizeof(snapshot) - offset;
      controlIn(reinterpret_cast<const uint8_t *>(&snapshot) + offset,
                available, setup.length);
      return true;
    }
    case 0x43: { // recovery transport state
      uint32_t info[] = {RecoveryMagic, 1, static_cast<uint32_t>(sRecoveryState),
                         RecoveryCapacity, sRecoveryLength, sRecoveryReceived,
                         sRecoveryCRC, sizeof(sControlBuffer)};
      controlIn(info, sizeof(info), setup.length);
      return true;
    }
    case 0x48: // signed A/B updater status
      controlIn(&PrimeG2::NANDUpdate::status(),
                sizeof(PrimeG2::NANDUpdate::Status), setup.length);
      return true;
    default:
      return false;
  }
}

void handleSetup() {
  sInstallAfterStatus = false;
  sRecoveryAfterStatus = false;
  sRebootAfterStatus = false;
  // A replacement SETUP aborts the previous request, including its address.
  sPendingAddress = -1;
  SetupPacket setup = {};
  volatile uint8_t *source = reinterpret_cast<volatile uint8_t *>(
    sControllerMemory.queueHeads[0].setup);
  uint8_t *destination = reinterpret_cast<uint8_t *>(&setup);
  // Acknowledge only EP0, then use the ChipIdea setup tripwire as Linux does.
  // A replacement SETUP clears the tripwire while we copy: retry rather than
  // processing a torn packet. Bound retries so a noisy host cannot freeze UI.
  reg32(ENDPTSETUPSTAT) = 1u;
  constexpr uint32_t SetupTripwire = 1u << 13;
  bool captured = false;
  for (unsigned attempt = 0; attempt < 16; attempt++) {
    reg32(USBCMD) |= SetupTripwire;
    PrimeG2::barrier();
    PrimeG2::System::invalidateDataCacheRange(&sControllerMemory.queueHeads[0],
                                             sizeof(QueueHead));
    for (size_t i = 0; i < sizeof(setup); i++) destination[i] = source[i];
    PrimeG2::barrier();
    captured = (reg32(USBCMD) & SetupTripwire) != 0;
    reg32(USBCMD) &= ~SetupTripwire;
    if (captured) break;
  }
  if (!captured) { fail(14, USBCMD); return; }
  sTraceCurrentRequest = !(setup.requestType == 0xC0 && setup.request == 0x4D);
  if (sTraceCurrentRequest) {
    memcpy(sLastSetupWords, &setup, sizeof(setup));
    sEnumeration.request = (uint32_t(setup.requestType) << 24) |
      (uint32_t(setup.request) << 16) | setup.value;
    sEnumeration.length = setup.length;
    sEnumeration.setups++;
    sEnumeration.phase = 1;
  }
  if (!flushEndpoint0()) return;
  reg32(ENDPTCTRL0) &= ~((1u << 0) | (1u << 16));

  bool isVendorLogRead = (setup.requestType & 0x60) == 0x40 &&
    (setup.request == 0x41 || setup.request == 0x42);
  if (!isVendorLogRead) {
    PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::UsbSetup,
      (static_cast<uint32_t>(setup.requestType) << 24) |
      (static_cast<uint32_t>(setup.request) << 16) | setup.value,
      (static_cast<uint32_t>(setup.index) << 16) | setup.length, sStatus);
  }

  bool handled = false;
  uint8_t requestClass = setup.requestType & 0x60;
  if (requestClass == 0x00) handled = standardRequest(setup);
  else if (requestClass == 0x40) handled = vendorRequest(setup);
  if (!handled) stallControl();
}

void handleBusReset() {
  sInstallAfterStatus = false;
  sRecoveryAfterStatus = false;
  sRebootAfterStatus = false;
  sPendingAddress = -1;
  sEnumeration.resets++;
  // Keep the last request and phase as evidence across host retry resets.
  sTraceCurrentRequest = false;
  // A broken or clock-starved controller must not trap the entire calculator
  // in the diagnostic path. Every hardware wait is bounded and logged.
  if (!waitFor(ENDPTPRIME, 0xFFFFFFFFu, false, 2000)) {
    fail(11, ENDPTPRIME);
    return;
  }
  reg32(ENDPTFLUSH) = 0xFFFFFFFFu;
  if (!waitFor(ENDPTFLUSH, 0xFFFFFFFFu, false, 2000)) {
    fail(12, ENDPTFLUSH);
    return;
  }
  reg32(ENDPTSETUPSTAT) = reg32(ENDPTSETUPSTAT);
  reg32(ENDPTCOMPLETE) = reg32(ENDPTCOMPLETE);
  initializeQueueHeads();
  reg32(ENDPTLISTADDR) =
    reinterpret_cast<uintptr_t>(&sControllerMemory.queueHeads[0]);
  reg32(DEVICEADDR) = 0;
  sConfiguration = 0;
  sStatus &= ~StatusConfigured;
  sStatus |= StatusBusReset;
  uint32_t speed = (reg32(PORTSC1) >> 26) & 3u;
  if (speed == 2) sStatus |= StatusHighSpeed;
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::UsbBusReset,
                               reg32(PORTSC1), reg32(USBSTS), sStatus);
}

void handleComplete(uint32_t complete) {
  PrimeG2::System::invalidateDataCacheRange(&sControllerMemory,
                                             sizeof(sControllerMemory));
  if (complete & (1u << 16)) {
    if (sControlState == ControlState::DataIn) {
      prime(0, nullptr, 0);
      sControlState = ControlState::StatusOut;
      if (sTraceCurrentRequest) sEnumeration.phase = 3;
    } else if (sControlState == ControlState::StatusIn) {
      if (sControllerMemory.descriptors[1].token & 0xE8u) {
        sInstallAfterStatus = false;
        sPendingAddress = -1;
        sRecoveryAfterStatus = false;
        sRebootAfterStatus = false;
        if (sTraceCurrentRequest) sEnumeration.phase = 7;
        fail(9, ENDPTCOMPLETE);
        return;
      }
      if (sPendingAddress >= 0) {
        reg32(DEVICEADDR) = static_cast<uint32_t>(sPendingAddress) << 25;
        PrimeG2::barrier();
        sPendingAddress = -1;
      }
      sControlState = ControlState::Idle;
      if (sInstallAfterStatus) {
        sInstallAfterStatus = false;
        PrimeG2::DevelopmentUpdate::begin(sRecoveryImage, sRecoveryLength, sRecoveryCRC);
      }
      if (sTraceCurrentRequest) { sEnumeration.phase = 5; sEnumeration.completed++; }
      if (sRebootAfterStatus) {
        sRebootAfterStatus = false;
        PrimeG2::Watchdog::rebootForUpdate();
      }
      if (sRecoveryAfterStatus) {
        sRecoveryAfterStatus = false;
        PrimeG2::Watchdog::rebootToROMRecovery();
      }
    }
  }
  if ((complete & 1u) && sControlState == ControlState::StatusOut) {
    sControlState = ControlState::Idle;
    if (sTraceCurrentRequest) { sEnumeration.phase = 5; sEnumeration.completed++; }
  } else if ((complete & 1u) && sControlState == ControlState::DataOut) {
    PrimeG2::System::invalidateDataCacheRange(sControlBuffer,
                                               sizeof(sControlBuffer));
    uint16_t remaining = (sControllerMemory.descriptors[0].token >> 16) & 0x7FFF;
    uint16_t received = sPendingOut.length - remaining;
    if (sPendingOut.request == 0x48) {
      PrimeG2::NANDUpdate::acceptManifest(sControlBuffer, received);
    } else {
      handleRecoveryDataOut(received);
    }
    statusIn();
  }
  uint32_t token = sControllerMemory.descriptors[0].token |
    sControllerMemory.descriptors[1].token;
  if (token & ((1u << 6) | (1u << 5) | (1u << 3))) {
    if (sTraceCurrentRequest) sEnumeration.phase = 7;
    fail(9, ENDPTCOMPLETE);
  }
}

}

namespace PrimeG2 {
namespace USBDiagnostics {

bool init() {
  // Ion may enable USB again after a plug event or DFU entry. Do not reset
  // an active EP0 transaction, address, or staged update in that case.
  // A deliberate shutdown clears StatusController and permits a fresh init.
  if (sStatus & StatusController) return !(sStatus & StatusError);
  sStatus = 0;
  sManagementSeen = false;
  sFirstErrorStep = 0;
  sPendingAddress = -1;
  sEnumeration = {0x4c465554, 1, 0, 0, 0, 0, 0, 0};
  sAddressWaitPolls = sFastAddressCompletions = 0;
  sTraceCurrentRequest = false;
  sConfiguration = 0;
  sLastSetupWords[0] = sLastSetupWords[1] = 0;
  sRebootAfterStatus = false;
  sRecoveryAfterStatus = false;
  PrimeG2::NANDUpdate::init();
  if (!initClockAndPhy()) return false;
  Ion::Timing::usleep(1000);
  if (!resetController()) return false;
  Diagnostics::record(Diagnostics::UsbStarted, reg32(USBCMD),
                      reg32(USBMODE), reg32(OTGSC));
  return true;
}

void poll() {
  if (!(sStatus & StatusController)) return;
  // Service consecutive control-transfer phases during an upload instead of
  // waiting a whole UI event interval between SETUP, data and status. Keep the
  // burst bounded: disconnected/interrupted uploads must not trap the UI or
  // prevent the platform loop from servicing the watchdog.
  for (unsigned uploadPoll = 0; uploadPoll < 200; ++uploadPoll) {
  uint32_t status = reg32(USBSTS) & InterruptMask;
  if (status) reg32(USBSTS) = status;
  if (status & InterruptReset) handleBusReset();
  if (status & InterruptError) fail(10, USBSTS);
  if ((status & InterruptPortChange) &&
      (((reg32(PORTSC1) >> 26) & 3u) == 2)) {
    sStatus |= StatusHighSpeed;
  }
  if ((reg32(PORTSC1) & 1u) == 0) {
    sConfiguration = 0;
    sStatus &= ~(StatusConfigured | StatusHighSpeed);
  }

  uint32_t complete = reg32(ENDPTCOMPLETE) & Endpoint0Mask;
  if (complete) {
    reg32(ENDPTCOMPLETE) = complete;
    handleComplete(complete);
  }
  if (reg32(ENDPTSETUPSTAT) & 1u) handleSetup();
  if (sRecoveryState != RecoveryState::Receiving ||
      !(reg32(PORTSC1) & 1u) || (sStatus & StatusError)) break;
  Ion::Timing::usleep(10);
  }
}

uint32_t statusFlags() { return sStatus; }
bool managementActive() {
  return externalPowerConnected() || (sManagementSeen && (sStatus & StatusConfigured) &&
    Ion::Timing::millis() - sLastManagementTime < 2000);
}
bool externalPowerConnected() {
  return plugged() || PrimeG2::Services::externalPowerPresent();
}
TransferStatus transferStatus() {
  auto update = PrimeG2::DevelopmentUpdate::status();
  if (update.state >= PrimeG2::DevelopmentUpdate::Checking)
    return {update.state, update.done, update.total};
  return {static_cast<uint32_t>(sRecoveryState), sRecoveryReceived, sRecoveryLength};
}
uint32_t firstErrorStep() { return sFirstErrorStep; }
EnumerationTrace enumerationTrace() { return sEnumeration; }
DebugSnapshot debugSnapshot() {
  DebugSnapshot snapshot = {};
  snapshot.trace = sEnumeration;
  snapshot.flags = sStatus;
  snapshot.error = sFirstErrorStep;
  snapshot.addressWaitPolls = sAddressWaitPolls;
  snapshot.fastAddressCompletions = sFastAddressCompletions;
  snapshot.rawSetup0 = sLastSetupWords[0];
  snapshot.rawSetup1 = sLastSetupWords[1];
  if (!(sStatus & StatusClock)) return snapshot;
  snapshot.command = reg32(USBCMD); snapshot.status = reg32(USBSTS);
  snapshot.mode = reg32(USBMODE); snapshot.port = reg32(PORTSC1);
  snapshot.setup = reg32(ENDPTSETUPSTAT); snapshot.prime = reg32(ENDPTPRIME);
  snapshot.flush = reg32(ENDPTFLUSH); snapshot.complete = reg32(ENDPTCOMPLETE);
  snapshot.address = reg32(DEVICEADDR); snapshot.list = reg32(ENDPTLISTADDR);
  PrimeG2::System::invalidateDataCacheRange(sControllerMemory.descriptors,
                                           sizeof(sControllerMemory.descriptors));
  snapshot.outToken = sControllerMemory.descriptors[0].token;
  snapshot.inToken = sControllerMemory.descriptors[1].token;
  return snapshot;
}
bool configured() { return (sStatus & StatusConfigured) != 0; }
bool plugged() { return (reg32(PORTSC1) & 1u) != 0; }
void shutdown() {
  sPendingAddress = -1;
  reg32(USBINTR) = 0;
  reg32(ENDPTFLUSH) = 0xFFFFFFFFu;
  waitFor(ENDPTFLUSH, 0xFFFFFFFFu, false, 2000);
  reg32(USBCMD) &= ~1u;
  sConfiguration = 0;
  sStatus &= ~(StatusConfigured | StatusController);
}

}
}
