#include "registers.h"
#include "display.h"
#include "backlight.h"
#include "diagnostics.h"
#include "usb_diagnostics.h"
#include "system.h"
#include "frame_presenter.h"
#include "refresh_trial.h"
#include "timing.h"
#include "development_update.h"

#include <ion/display.h>
#include <ion/timing.h>
#include <ion.h>
#include <stddef.h>

namespace {

constexpr int Width = Ion::Display::Width;
constexpr int Height = Ion::Display::Height;
constexpr int GuardWords = 16;
constexpr uint32_t GuardValue = 0xA55A5AA5;

struct FramebufferStorage {
  uint32_t before[GuardWords];
  uint32_t pixels[Width * Height];
  uint32_t after[GuardWords];
};

FramebufferStorage sFramebufferStorage
  __attribute__((section(".framebuffer"), aligned(64)));
FramebufferStorage sScanout[2]
  __attribute__((section(".framebuffer"), aligned(64)));
static_assert(sizeof(FramebufferStorage) * 3 <= 1024 * 1024,
              "Drawing and scanout buffers must fit the framebuffer region");

uint32_t * const sFramebuffer = sFramebufferStorage.pixels;
PrimeG2::FramePresenter<Width * Height> sPresenter;
unsigned sFrameDepth = 0;
bool sPresentationEnabled = false;
bool sPresentationFault = false;
unsigned sRefreshRate = 59;
PrimeG2::RefreshTrial sRefreshTrial;

struct PresentationHardware {
  const uint32_t * current() {
    return reinterpret_cast<const uint32_t *>(PrimeG2::reg32(PrimeG2::LCDIF + 0x40));
  }
  void publish(uint32_t * buffer, size_t size) {
    if (PrimeG2::System::memoryType(reinterpret_cast<uintptr_t>(buffer)) !=
        PrimeG2::System::MemoryType::Framebuffer) {
      PrimeG2::System::cleanDataCacheRange(buffer, size);
    }
    PrimeG2::System::dataSyncBarrier();
  }
  void queue(uint32_t * buffer) {
    // NEXT is latched by LCDIF at the frame boundary; never change CUR live.
    PrimeG2::reg32(PrimeG2::LCDIF + 0x50) = reinterpret_cast<uintptr_t>(buffer);
    // Discard the previous frame's sticky completion status. Ownership is
    // established from CUR, not an IRQ flag which could predate this request.
    PrimeG2::reg32(PrimeG2::LCDIF + 0x18) = 1u << 9;
    PrimeG2::System::dataSyncBarrier();
  }
  void pause() {
#if PRIME_G2_EMULATOR
    Ion::Timing::usleep(100);
#else
    // Bounded even during early boot, before runtime GPT-independent delays.
    uint32_t loops = 13200;
    __asm volatile("1: subs %0, %0, #1\n bne 1b" : "+r"(loops) :: "cc");
#endif
  }
};

bool presentFrame() {
  if (!sPresentationEnabled || sFrameDepth) return true;
  PresentationHardware hardware;
  bool ok = sPresenter.present(sFramebuffer, sScanout[0].pixels,
                               sScanout[1].pixels, hardware);
  if (sPresentationFault == ok) {
    sPresentationFault = !ok;
    PrimeG2::Diagnostics::record(ok ? PrimeG2::Diagnostics::FrameSwapRecovered :
                                    PrimeG2::Diagnostics::FrameSwapTimeout,
      PrimeG2::reg32(PrimeG2::LCDIF + 0x40),
      PrimeG2::reg32(PrimeG2::LCDIF + 0x50), sPresenter.timeouts());
  }
  return ok;
}
bool sControllerResetFailed = false;
uint32_t sBootProgress = 0;
uint64_t sPublishedPixels = 0;
uint32_t sPublishCount = 0;
bool sPanelInitialized = false;
bool sPanelInStandby = false;

#ifndef PRIME_G2_VISIBLE_BOOT_DIAGNOSTICS
#define PRIME_G2_VISIBLE_BOOT_DIAGNOSTICS 0
#endif

/* Twenty compact slots keep the complete first-redraw diagnostic visible on
 * the physical 320-pixel panel. Unreached stages stay near-black. */
#if PRIME_G2_VISIBLE_BOOT_DIAGNOSTICS
constexpr unsigned BootProgressStages = 20;
constexpr int BootProgressSize = 10;
constexpr int BootProgressGap = 5;
constexpr int BootProgressY = Height - BootProgressSize - 2;

KDColor bootProgressColor(unsigned stage) {
  constexpr KDColor Colors[] = {
    KDColor::RGB888(0x20, 0x70, 0xFF),
    KDColor::RGB888(0xFF, 0xD0, 0x20),
    KDColor::RGB888(0x20, 0xD0, 0x50),
    KDColor::RGB888(0x20, 0xD0, 0xD0),
    KDColor::RGB888(0xE0, 0x30, 0xD0),
    KDColor::RGB888(0xFF, 0x70, 0x20),
    KDColor::RGB888(0x80, 0x40, 0xE0),
  };
  return Colors[(stage - 1) % (sizeof(Colors) / sizeof(Colors[0]))];
}
#endif

bool validRect(KDRect rect) {
  return rect.width() > 0 && rect.height() > 0;
}

bool pointOnScreen(int x, int y) {
  return x >= 0 && x < Width && y >= 0 && y < Height;
}

void publishRect(KDRect rect) {
  int left = rect.left() < 0 ? 0 : rect.left();
  int top = rect.top() < 0 ? 0 : rect.top();
  int right = rect.right() >= Width ? Width - 1 : rect.right();
  int bottom = rect.bottom() >= Height ? Height - 1 : rect.bottom();
  if (left > right || top > bottom) return;
  sPublishedPixels += static_cast<uint64_t>(right - left + 1) *
    static_cast<uint64_t>(bottom - top + 1);
  sPublishCount++;
  sPresenter.changed();
  uint32_t *first = sFramebuffer + top * Width + left;
  uint32_t *last = sFramebuffer + bottom * Width + right + 1;
  if (PrimeG2::System::memoryType(reinterpret_cast<uintptr_t>(first)) ==
      PrimeG2::System::MemoryType::Framebuffer) {
    /* The selected LCDIF mapping is normal non-cacheable; a DSB publishes
     * writes and avoids thousands of pointless line maintenance operations. */
    PrimeG2::System::dataSyncBarrier();
  } else {
    PrimeG2::System::cleanDataCacheRange(first,
      reinterpret_cast<uintptr_t>(last) - reinterpret_cast<uintptr_t>(first));
  }
  presentFrame();
}

uint32_t xrgb8888(KDColor color) {
  uint16_t p = static_cast<uint16_t>(color);
  uint32_t r = (p >> 11) & 0x1F;
  uint32_t g = (p >> 5) & 0x3F;
  uint32_t b = p & 0x1F;
  r = (r << 3) | (r >> 2);
  g = (g << 2) | (g >> 4);
  b = (b << 3) | (b >> 2);
  return (r << 16) | (g << 8) | b;
}

KDColor rgb565(uint32_t pixel) {
  uint16_t r = ((pixel >> 16) & 0xFF) >> 3;
  uint16_t g = ((pixel >> 8) & 0xFF) >> 2;
  uint16_t b = (pixel & 0xFF) >> 3;
  return KDColor::RGB16((r << 11) | (g << 5) | b);
}

/* Prime G2 ILI9322 control bus: GPIO4_IO21=SCK, IO22=CS, IO23=MOSI.
 * The device-tree requests SPI mode 3, so data is sampled on the rising edge. */
void spiDelay() {
  Ion::Timing::usleep(5);
}

void panelRegister(uint8_t address, uint8_t value) {
  PrimeG2::gpioWrite(PrimeG2::GPIO4, 22, false);
  uint8_t bytes[] = {address, value};
  for (uint8_t byte : bytes) {
    for (int bit = 7; bit >= 0; bit--) {
      PrimeG2::gpioWrite(PrimeG2::GPIO4, 21, false);
      PrimeG2::gpioWrite(PrimeG2::GPIO4, 23, byte & (1u << bit));
      spiDelay();
      PrimeG2::gpioWrite(PrimeG2::GPIO4, 21, true);
      spiDelay();
    }
  }
  PrimeG2::gpioWrite(PrimeG2::GPIO4, 22, true);
  spiDelay(); // ILI9322 tCH: keep CS high for at least 50 ns
  PrimeG2::Diagnostics::record(
    PrimeG2::Diagnostics::PanelRegisterWrite, address, value,
    PrimeG2::reg32(PrimeG2::GPIO4));
  PrimeG2::USBDiagnostics::poll();
}

void preparePanelReset() {
  PrimeG2::mux(0x01E4, 0x0470, 5, 0x70A1); // CSI_DATA00 GPIO4_IO21
  PrimeG2::mux(0x01E8, 0x0474, 5, 0x70A1); // CSI_DATA01 GPIO4_IO22
  PrimeG2::mux(0x01EC, 0x0478, 5, 0x70A1); // CSI_DATA02 GPIO4_IO23
  PrimeG2::mux(0x0114, 0x03A0, 5, 0x17059); // LCD_RESET GPIO3_IO04

  /* Select the inactive output levels before enabling output drivers. This
   * prevents an inherited bootloader DR value from releasing reset during a
   * battery-cold start. */
  PrimeG2::gpioWrite(PrimeG2::GPIO4, 21, true);
  PrimeG2::gpioWrite(PrimeG2::GPIO4, 22, true);
  PrimeG2::gpioWrite(PrimeG2::GPIO4, 23, false);
  PrimeG2::gpioWrite(PrimeG2::GPIO3, 4, false);
  PrimeG2::gpioDirection(PrimeG2::GPIO4, 21, true);
  PrimeG2::gpioDirection(PrimeG2::GPIO4, 22, true);
  PrimeG2::gpioDirection(PrimeG2::GPIO4, 23, true);
  PrimeG2::gpioDirection(PrimeG2::GPIO3, 4, true);

  /* ILI9322DS section 10.1 requires at least 20 ms after system power-on
   * before reset. LDO1 was just verified by Services::init(), so measure the
   * delay from a known-good panel supply rather than from an unknown ROM or
   * U-Boot state. */
  Ion::Timing::msleep(20);

  /* Match the proven Prime reset pulse, but keep RESET asserted until LCDIF
   * is running. ILI9322DS v1.12 section 10 requires interface signals before
   * charge-pump/display activation. Prinux gets this ordering naturally
   * because mxsfb probes before the panel driver. */
  PrimeG2::gpioWrite(PrimeG2::GPIO3, 4, true);
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::PanelResetHigh,
                               PrimeG2::reg32(PrimeG2::GPIO3),
                               PrimeG2::reg32(PrimeG2::GPIO3 + 4), 0);
  Ion::Timing::msleep(10);
  PrimeG2::gpioWrite(PrimeG2::GPIO3, 4, false);
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::PanelResetLow,
                               PrimeG2::reg32(PrimeG2::GPIO3), 0, 0);
  Ion::Timing::msleep(10);
}

void initPanel() {
  /* LCDIF is now producing DCLK/HSYNC/VSYNC/DE. Release the panel and retain
   * the conservative 120 ms recovery used by the working Prinux driver. */
  PrimeG2::gpioWrite(PrimeG2::GPIO3, 4, true);
  Ion::Timing::msleep(120);
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::PanelResetReleased,
                               PrimeG2::reg32(PrimeG2::GPIO3), 120, 0);
  PrimeG2::USBDiagnostics::poll();

  panelRegister(0x07, 0xEE); // charge pumps off / standby while configuring
  panelRegister(0x01, 0x14); // board-proven VCOM amplitude
  panelRegister(0x02, 0x3A); // board-proven VCOM high level
  /* Prinux writes 0xEF to R05. Bits 7 and 3 are reserved in the datasheet,
   * so write the same effective Power Setting value with those bits clear. */
  panelRegister(0x05, 0x67);
  panelRegister(0x06, 0x0F); // serial RGB through, auto, normal H/V direction
  /* Keep REV set, matching the ILI9322 reset default and the working Prime
   * Linux driver.  On this panel REV=1 is the normal user-visible grayscale
   * direction; clearing it makes white black and turns Lefony green purple. */
  panelRegister(0x0A, 0x49); // REV, rising DCLK, active-high DE, low H/VSYNC
  panelRegister(0x0B, 0x05); // HSYNC+VSYNC+DE, line inversion
  const uint8_t gamma[] = {0xA7, 0x55, 0x71, 0x71, 0x73, 0x55, 0x18, 0x62};
  for (unsigned i = 0; i < sizeof(gamma); i++) {
    panelRegister(0x10 + i, gamma[i]);
  }
  panelRegister(0x07, 0xEF); // automatic charge-pump sequence, normal mode
  /* Datasheet section 10 requires 10-80 complete frames before display-on.
   * At the captured ~60 Hz timing, 200 ms supplies twelve full frames. */
  Ion::Timing::msleep(200);
  panelRegister(0x30, 0x0D); // AUTO_DP + DISP_ON + 20 white startup frames
  /* Keep the backlight disabled until AUTO_DP's 20-frame white interval has
   * elapsed. This prevents a normal power-on transition from looking like
   * the persistent white-screen failure we are diagnosing. */
  Ion::Timing::msleep(400);
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::PanelReady,
                               0x07EF, 0x300D, 0);
  sPanelInitialized = true;
  sPanelInStandby = false;
}

void enterPanelStandby() {
  if (!sPanelInitialized || sPanelInStandby) return;

  /* ILI9322DS v1.12 sections 8.2.3 and 10.1: remove DISP_ON while DCLK is
   * still present, put the charge-pump controller in standby, then provide
   * at least five complete frames before stopping DCLK.  At the Prime's
   * captured ~60 Hz timing 100 ms is a conservative six-frame interval. */
  panelRegister(0x30, 0x09); // AUTO_DP retained, DISP_ON cleared
  panelRegister(0x07, 0xEE); // STB=0, charge pumps off / digital standby
  Ion::Timing::msleep(100);
  sPanelInStandby = true;
}

void leavePanelStandby() {
  if (!sPanelInitialized || !sPanelInStandby) return;

  /* DCLK is already running when this is called.  The controller requires
   * 10-80 frames after STB is released; twelve frames followed by AUTO_DP's
   * 20-frame blanking interval keeps the backlight-dark wake deterministic. */
  panelRegister(0x07, 0xEF);
  Ion::Timing::msleep(200);
  panelRegister(0x30, 0x0D);
  Ion::Timing::msleep(400);
  sPanelInStandby = false;
}

bool waitForControllerBit(uintptr_t address, uint32_t mask, bool set) {
  for (unsigned timeout = 0x400; timeout > 0; timeout--) {
    if ((PrimeG2::reg32(address) & mask) == (set ? mask : 0)) {
      return true;
    }
    Ion::Timing::usleep(1);
  }
  return false;
}

bool resetController(uintptr_t base) {
  constexpr uint32_t CTRL_SFTRST = 1u << 31;
  constexpr uint32_t CTRL_CLKGATE = 1u << 30;

  /* This is the i.MX stmp_reset_block sequence used by the working Linux
   * mxsfb driver and required by the eLCDIF reference manual. */
  PrimeG2::reg32(base + 0x08) = CTRL_SFTRST;
  PrimeG2::barrier();
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::LcdifResetStep, 1,
                               PrimeG2::reg32(base), 0);
  if (!waitForControllerBit(base, CTRL_SFTRST, false)) {
    PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::LcdifResetFailed,
                                 1, PrimeG2::reg32(base), 0);
    return false;
  }
  PrimeG2::reg32(base + 0x08) = CTRL_CLKGATE;
  PrimeG2::reg32(base + 0x04) = CTRL_SFTRST;
  PrimeG2::barrier();
  Ion::Timing::usleep(1);
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::LcdifResetStep, 2,
                               PrimeG2::reg32(base), 0);
  if (!waitForControllerBit(base, CTRL_CLKGATE, true)) {
    PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::LcdifResetFailed,
                                 2, PrimeG2::reg32(base), 0);
    return false;
  }
  PrimeG2::reg32(base + 0x08) = CTRL_SFTRST;
  PrimeG2::barrier();
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::LcdifResetStep, 3,
                               PrimeG2::reg32(base), 0);
  if (!waitForControllerBit(base, CTRL_SFTRST, false)) {
    PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::LcdifResetFailed,
                                 3, PrimeG2::reg32(base), 0);
    return false;
  }
  PrimeG2::reg32(base + 0x08) = CTRL_CLKGATE;
  PrimeG2::barrier();
  bool result = waitForControllerBit(base, CTRL_CLKGATE, false);
  PrimeG2::Diagnostics::record(
    result ? PrimeG2::Diagnostics::LcdifResetStep :
             PrimeG2::Diagnostics::LcdifResetFailed,
    4, PrimeG2::reg32(base), 0);
  return result;
}

void initPins() {
  for (uint32_t offset = 0x0118, pad = 0x03A4;
       offset <= 0x0134; offset += 4, pad += 4) {
    PrimeG2::mux(offset, pad, 0, 0x79);
  }
  PrimeG2::mux(0x0104, 0x0390, 0, 0x79); // LCD clock
  PrimeG2::mux(0x0108, 0x0394, 0, 0x79); // data enable
  PrimeG2::mux(0x010C, 0x0398, 0, 0x79); // hsync
  PrimeG2::mux(0x0110, 0x039C, 0, 0x79); // vsync
}

void initPixelClock() {
  /* PLL2_BUS=528 MHz, /6 pre-divider, /5 post-divider = 17.6 MHz. This is
   * within the panel timing tolerance of the device-tree's 18 MHz request and
   * avoids retuning a PLL that U-Boot may be using. */
  /* Stop the pixel gate while changing its parent and dividers. */
  PrimeG2::clearBits(PrimeG2::CCM + 0x74, 3u << 10);
  PrimeG2::updateBits(PrimeG2::CCM + 0x38,
                      (7u << 15) | (7u << 12) | (7u << 9),
                      (sRefreshRate == 55 ? 7u : 5u) << 12);
  PrimeG2::updateBits(PrimeG2::CCM + 0x18, 7u << 23,
                      (sRefreshRate == 55 ? 3u : 4u) << 23);
  PrimeG2::gate(0x70, 28); // LCDIF APB
  PrimeG2::gate(0x74, 10); // LCDIF pixel
}

void initController() {
  constexpr uintptr_t base = PrimeG2::LCDIF;
  constexpr uint32_t CTRL_BYPASS_COUNT = 1u << 19;
  constexpr uint32_t CTRL_DOTCLK_MODE = 1u << 17;
  constexpr uint32_t CTRL_PIXEL_FORMAT =
    (1u << 14) | (1u << 8) | (1u << 10);
  constexpr int TransferWidth = Width * 3;
  constexpr uint32_t CTRL_MASTER = 1u << 5;
  constexpr uint32_t CTRL_RUN = 1u;

  sControllerResetFailed = !resetController(base);
  /* The Prime has an 8-bit serial RGB bus but the framebuffer is XRGB8888.
   * These values mirror the Prime Linux LCDIF driver's special 32-bpp/8-bit
   * path. The hardware-faithful VM must accept these exact values too. */
  PrimeG2::reg32(base + 0x00) = CTRL_BYPASS_COUNT | CTRL_MASTER |
    CTRL_PIXEL_FORMAT;
  PrimeG2::reg32(base + 0x10) = 7u << 16; // one 32-bit pixel per word
  PrimeG2::reg32(base + 0x20) = 4u << 21; // 16 outstanding AXI requests
  PrimeG2::reg32(base + 0x30) = (Height << 16) | TransferWidth;
  sPresenter.reset();
  for (int i = 0; i < Width * Height; i++) {
    sScanout[0].pixels[i] = sFramebuffer[i];
  }
  PresentationHardware hardware;
  hardware.publish(sScanout[0].pixels, sizeof(sScanout[0].pixels));
  PrimeG2::reg32(base + 0x40) = reinterpret_cast<uintptr_t>(sScanout[0].pixels);
  PrimeG2::reg32(base + 0x50) = reinterpret_cast<uintptr_t>(sScanout[0].pixels);

  constexpr uint32_t VDCTRL0_ENABLE_PRESENT = 1u << 28;
  constexpr uint32_t VDCTRL0_ENABLE_HIGH = 1u << 24;
  constexpr uint32_t VDCTRL0_VSYNC_PERIOD_UNIT = 1u << 21;
  constexpr uint32_t VDCTRL0_VSYNC_PULSE_UNIT = 1u << 20;
  /* The working Prinux register snapshot is 0x11300001. In particular,
   * DOTCLK_ACT_FALLING (bit 25) is clear: the panel samples the rising-active
   * configuration selected by pixelclk-active=1 in the board device tree. */
  PrimeG2::reg32(base + 0x70) = VDCTRL0_ENABLE_PRESENT |
    VDCTRL0_ENABLE_HIGH | VDCTRL0_VSYNC_PERIOD_UNIT |
    VDCTRL0_VSYNC_PULSE_UNIT | 1u;
  PrimeG2::reg32(base + 0x80) = 264; // 240 + 6 + 1 + 17
  PrimeG2::reg32(base + 0x90) = (1u << 18) |
    (TransferWidth + 100 + 1 + 71);
  PrimeG2::reg32(base + 0xA0) = (72u << 16) | 18u;
  PrimeG2::reg32(base + 0xB0) = (1u << 18) | TransferWidth;

  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::LcdifConfigured,
                               PrimeG2::reg32(base + 0x00),
                               PrimeG2::reg32(base + 0x30),
                               PrimeG2::reg32(base + 0xB0));

  PrimeG2::reg32(base + 0x04) = CTRL_DOTCLK_MODE | CTRL_MASTER | CTRL_RUN;
  PrimeG2::reg32(base + 0x14) = 1u << 24; // recover after FIFO underflow
  PrimeG2::barrier();
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::LcdifStarted,
                               PrimeG2::reg32(base + 0x00),
                               PrimeG2::reg32(base + 0x10),
                               PrimeG2::reg32(base + 0x1D0));
  PrimeG2::USBDiagnostics::poll();
}

}

namespace PrimeG2 {
namespace Display {

void shutdown() {
  sPresentationEnabled = false;
  /* The panel must enter standby while DCLK/sync are still valid. */
  enterPanelStandby();

  /* Clear RUN through the LCDIF atomic CLR alias only after the required
   * standby frame interval has elapsed. */
  reg32(LCDIF + 0x08) = 1u;
  for (unsigned timeout = 0; timeout < 50000 && (reg32(LCDIF) & 1u);
       timeout++) {
    __asm volatile("nop");
  }
}

void init() {
  sPresentationEnabled = false;
  Diagnostics::record(Diagnostics::DisplayInitStart,
                      reinterpret_cast<uintptr_t>(sFramebuffer), Width,
                      Height);
  for (int i = 0; i < GuardWords; i++) {
    sFramebufferStorage.before[i] = GuardValue;
    sFramebufferStorage.after[i] = GuardValue;
    for (auto & buffer : sScanout) {
      buffer.before[i] = GuardValue;
      buffer.after[i] = GuardValue;
    }
  }
  for (int i = 0; i < Width * Height; i++) {
    sFramebuffer[i] = 0x00000000;
  }
  initPins();
  Diagnostics::record(Diagnostics::DisplayPinsReady,
                      reg32(IOMUXC + 0x0104), reg32(IOMUXC + 0x0114),
                      reg32(IOMUXC + 0x01E4));
  USBDiagnostics::poll();
  initPixelClock();
  Diagnostics::record(Diagnostics::DisplayClockReady,
                      reg32(CCM + 0x18), reg32(CCM + 0x38),
                      reg32(CCM + 0x74));
  USBDiagnostics::poll();
  preparePanelReset();
  initController();
  initPanel();
  Diagnostics::captureSnapshot();
  Diagnostics::record(Diagnostics::DisplayInitComplete,
                      Display::selfTest(), reg32(LCDIF),
                      reg32(LCDIF + 0x1D0));
  Display::bootProgress(1);
  sPresentationEnabled = true;
  presentFrame();
  USBDiagnostics::poll();
}

void resume() {
  sPresentationEnabled = false;
  /* RAM, the framebuffer and ILI9322 register state survive normal suspend.
   * Reconstruct the SoC-side pixel path, start DCLK, then leave standby.  Do
   * not pulse panel reset: doing so loses state and creates the long white
   * power-on sequence that users previously saw as an incomplete power-off. */
  initPins();
  initPixelClock();
  initController();
  leavePanelStandby();
  Diagnostics::record(Diagnostics::DisplayInitComplete,
                      Display::selfTest(), reg32(LCDIF),
                      reg32(LCDIF + 0x1D0));
  sPresentationEnabled = true;
  presentFrame();
}

bool isInStandby() { return sPanelInStandby; }
void cancelFrame() { sFrameDepth = 0; }

static bool applyRefreshRate(unsigned hz) {
  if (hz == sRefreshRate) return true;
  if (sFrameDepth || !sPanelInitialized || sPanelInStandby) return false;
  bool visible = Backlight::isVisible();
  Backlight::hide();
  shutdown(); // Panel standby while sync is still running, then stop LCDIF.
  sRefreshRate = hz;
  initPixelClock(); // Change only the LCDIF dividers; never retune shared PLLs.
  initController();
  leavePanelStandby();
  sPresentationEnabled = true;
  bool ok = presentFrame();
  if (visible) Backlight::reveal();
  return ok;
}

bool requestRefreshRate(unsigned hz) {
  if ((hz != 55 && hz != 59) || DevelopmentUpdate::busy() || sFrameDepth ||
      !sPanelInitialized || sPanelInStandby) return false;
  sRefreshTrial.cancel();
  if (!applyRefreshRate(hz)) {
    applyRefreshRate(59);
    return false;
  }
  if (hz == 55) sRefreshTrial.start(Timing::elapsedMillis());
  return true;
}

bool confirmRefreshRate() {
  pollRefreshTrial();
  return sRefreshTrial.confirm(Timing::elapsedMillis());
}

void cancelRefreshTrial() {
  if (!sRefreshTrial.active()) return;
  if (applyRefreshRate(59)) sRefreshTrial.cancel();
}

void pollRefreshTrial() {
  if (sRefreshTrial.expired(Timing::elapsedMillis())) cancelRefreshTrial();
}

bool refreshTrialActive() { return sRefreshTrial.active(); }
uint32_t refreshMilliHz() {
  return uint64_t(sRefreshRate == 55 ? 16500000 : 17600000) * 1000 / (1132 * 264);
}

void bootProgress(unsigned stage) {
  if (stage == 0 || stage > 32) {
    return;
  }
  uint32_t stageBit = 1u << (stage - 1);
  if (!(sBootProgress & stageBit)) {
    Diagnostics::record(Diagnostics::BootProgress, stage, sBootProgress,
                        sPublishCount);
  }
  sBootProgress |= stageBit;
#if PRIME_G2_VISIBLE_BOOT_DIAGNOSTICS
  for (unsigned i = 0; i < BootProgressStages; i++) {
    int x = 2 + i * (BootProgressSize + BootProgressGap);
    KDColor color = (sBootProgress & (1u << i)) ?
      bootProgressColor(i + 1) : KDColor::RGB888(0x18, 0x18, 0x18);
    Ion::Display::pushRectUniform(
      KDRect(x, BootProgressY, BootProgressSize, BootProgressSize), color);
  }
  PrimeG2::barrier();
#endif
}

void resetBootProgress() {
  sBootProgress = 0;
#if PRIME_G2_VISIBLE_BOOT_DIAGNOSTICS
  for (unsigned i = 0; i < BootProgressStages; i++) {
    int x = 2 + i * (BootProgressSize + BootProgressGap);
    Ion::Display::pushRectUniform(
      KDRect(x, BootProgressY, BootProgressSize, BootProgressSize),
      KDColor::RGB888(0x18, 0x18, 0x18));
  }
  PrimeG2::barrier();
#endif
}

void keypadMatrixDiagnostic(const uint8_t matrix[8]) {
#if !PRIME_G2_EMULATOR && PRIME_G2_VISIBLE_BOOT_DIAGNOSTICS
  static uint8_t previous[8] = {0xFF, 0xFF, 0xFF, 0xFF,
                                0xFF, 0xFF, 0xFF, 0xFF};
  for (unsigned column = 0; column < 8; column++) {
    if (previous[column] == matrix[column]) continue;
    previous[column] = matrix[column];
    uint8_t rows = matrix[column];
    KDColor color = KDColor::RGB888(0x18, 0x18, 0x18);
    if (rows != 0) {
      unsigned firstRow = 1;
      while (firstRow < 8 && !(rows & (1u << firstRow))) firstRow++;
      color = rows & (rows - 1) ? KDColorWhite : bootProgressColor(firstRow);
    }
    int x = 2 + column * (BootProgressSize + BootProgressGap);
    Ion::Display::pushRectUniform(
      KDRect(x, BootProgressY, BootProgressSize, BootProgressSize), color);
  }
  PrimeG2::barrier();
#else
  (void)matrix;
#endif
}

bool guardsIntact() {
  for (int i = 0; i < GuardWords; i++) {
    if (sFramebufferStorage.before[i] != GuardValue ||
        sFramebufferStorage.after[i] != GuardValue) {
      return false;
    }
    for (const auto & buffer : sScanout) {
      if (buffer.before[i] != GuardValue || buffer.after[i] != GuardValue)
        return false;
    }
  }
  return true;
}

uint32_t selfTest() {
  sFrameDepth++;
  uint32_t failures = 0;
  for (uint32_t value = 0; value <= 0xFFFF; value++) {
    KDColor color = KDColor::RGB16(static_cast<uint16_t>(value));
    if (static_cast<uint16_t>(rgb565(xrgb8888(color))) != value) {
      failures |= 1u << 0;
      break;
    }
  }

  constexpr KDColor colors[] = {
    KDColorBlack, KDColorWhite, KDColorRed, KDColorGreen, KDColorBlue,
    KDColor::RGB16(0x7BEF), KDColor::RGB16(0x4208)
  };
  for (unsigned i = 0; i < sizeof(colors) / sizeof(colors[0]); i++) {
    Ion::Display::pushRectUniform(KDRect(i, 0, 1, 1), colors[i]);
    KDColor result;
    Ion::Display::pullRect(KDRect(i, 0, 1, 1), &result);
    if (result != colors[i]) {
      failures |= 1u << 1;
    }
  }

  KDColor gradient[256];
  for (unsigned i = 0; i < 256; i++) {
    gradient[i] = KDColor::RGB888(i, 255 - i, i / 2);
  }
  Ion::Display::pushRect(KDRect(0, 1, 256, 1), gradient);
  KDColor pulled[256];
  Ion::Display::pullRect(KDRect(0, 1, 256, 1), pulled);
  for (unsigned i = 0; i < 256; i++) {
    if (pulled[i] != gradient[i]) {
      failures |= 1u << 2;
      break;
    }
  }

  KDColor clipped[16];
  for (int i = 0; i < 16; i++) {
    clipped[i] = KDColor::RGB16(0x1234 + i);
  }
  Ion::Display::pushRect(KDRect(-2, -2, 4, 4), clipped);
  Ion::Display::pushRectUniform(KDRect(Width - 2, Height - 2, 4, 4), KDColorRed);
  KDColor clippedPull[16];
  for (int i = 0; i < 16; i++) {
    clippedPull[i] = KDColorBlue;
  }
  Ion::Display::pullRect(KDRect(-2, -2, 4, 4), clippedPull);
  if (clippedPull[0] != KDColorBlue || clippedPull[10] != clipped[10] ||
      clippedPull[15] != clipped[15]) {
    failures |= 1u << 3;
  }
  Ion::Display::pushRectUniform(KDRect(-100, -100, 1, 1), KDColorGreen);
  if (!guardsIntact()) {
    failures |= 1u << 4;
  }
  if (sControllerResetFailed) {
    failures |= 1u << 5;
  }
  sFrameDepth--;
  presentFrame();
  return failures;
}

uint32_t checksum() {
  System::dataSyncBarrier();
  return Ion::crc32Byte(reinterpret_cast<const uint8_t *>(sFramebuffer),
                        Width * Height * sizeof(uint32_t));
}

uint64_t publishedPixels() { return sPublishedPixels; }
uint32_t publishCount() { return sPublishCount; }
const uint32_t * drawingBuffer() { return sFramebuffer; }
uint32_t presentedFrames() { return sPresenter.frames(); }
uint32_t presentationTimeouts() { return sPresenter.timeouts(); }

}
}

extern "C" void prime_g2_boot_progress(unsigned stage) {
  PrimeG2::Display::bootProgress(stage);
}

extern "C" void prime_g2_boot_progress_reset() {
  PrimeG2::Display::resetBootProgress();
}

extern "C" void prime_g2_first_frame_ready() {
  /* One full 60 Hz scan after the final framebuffer write guarantees the
   * panel has consumed a complete Upsilon frame before it becomes visible. */
  if (!PrimeG2::Backlight::isVisible()) {
    Ion::Timing::msleep(20);
    PrimeG2::Backlight::reveal();
  }
}

extern "C" void prime_g2_begin_frame() { sFrameDepth++; }
extern "C" void prime_g2_cancel_frame() { PrimeG2::Display::cancelFrame(); }
extern "C" void prime_g2_end_frame() {
  if (sFrameDepth) sFrameDepth--;
  presentFrame();
}

namespace Ion {
namespace Display {

void pushRect(KDRect rect, const KDColor * pixels) {
  if (!validRect(rect) || pixels == nullptr) {
    return;
  }
  for (int y = rect.top(); y <= rect.bottom(); y++) {
    for (int x = rect.left(); x <= rect.right(); x++) {
      size_t source = static_cast<size_t>(y - rect.top()) * rect.width() +
        (x - rect.left());
      if (pointOnScreen(x, y)) {
        sFramebuffer[y * Width + x] = xrgb8888(pixels[source]);
      }
    }
  }
  /* The framebuffer is deliberately mapped normal non-cacheable, but retain
   * explicit ownership maintenance so this remains correct if a board variant
   * uses a cacheable write-combining mapping. */
  publishRect(rect);
}

void pushRectUniform(KDRect rect, KDColor color) {
  if (!validRect(rect)) {
    return;
  }
  uint32_t pixel = xrgb8888(color);
  for (int y = rect.top(); y <= rect.bottom(); y++) {
    for (int x = rect.left(); x <= rect.right(); x++) {
      if (pointOnScreen(x, y)) {
        sFramebuffer[y * Width + x] = pixel;
      }
    }
  }
  publishRect(rect);
}

void pullRect(KDRect rect, KDColor * pixels) {
  if (!validRect(rect) || pixels == nullptr) {
    return;
  }
  for (int y = rect.top(); y <= rect.bottom(); y++) {
    for (int x = rect.left(); x <= rect.right(); x++) {
      size_t destination = static_cast<size_t>(y - rect.top()) * rect.width() +
        (x - rect.left());
      if (pointOnScreen(x, y)) {
        pixels[destination] = rgb565(sFramebuffer[y * Width + x]);
      }
    }
  }
}

bool waitForVBlank() {
  return presentFrame();
}

void POSTPushMulticolor(int rootNumberTiles, int tileSize) {
  for (int y = 0; y < rootNumberTiles; y++) {
    for (int x = 0; x < rootNumberTiles; x++) {
      pushRectUniform(KDRect(x * tileSize, y * tileSize, tileSize, tileSize),
        KDColor::RGB16(1u << ((x + y) & 15)));
    }
  }
}

int displayUniformTilingSize10(KDColor color) {
  pushRectUniform(KDRect(0, 0, Width, Height), color);
  int failures = 0;
  KDColor result;
  for (int y = 0; y < Height; y += 10) {
    for (int x = 0; x < Width; x += 10) {
      pullRect(KDRect(x, y, 1, 1), &result);
      failures += result != color;
    }
  }
  return failures;
}

int displayColoredTilingSize10() {
  constexpr KDColor colors[] = {KDColorRed, KDColorGreen, KDColorBlue};
  int failures = 0;
  KDColor result;
  for (int y = 0; y < Height / 10; y++) {
    for (int x = 0; x < Width / 10; x++) {
      KDColor color = colors[(x + y) % 3];
      pushRectUniform(KDRect(x * 10, y * 10, 10, 10), color);
      pullRect(KDRect(x * 10 + 9, y * 10 + 9, 1, 1), &result);
      failures += result != color;
    }
  }
  return failures;
}

}
}
