#pragma once
#include <escher.h>
#include <ion/backlight.h>
#include "global_preferences.h"
#include "../ion/src/prime_g2/usb_diagnostics.h"
#include "../ion/src/prime_g2/lefony_build_identity.h"

class LefonyUSBPage : public ViewController {
  class Content : public View {
  public:
    bool refresh(bool force = false) {
      auto next = PrimeG2::USBDiagnostics::transferStatus();
      uint32_t percent = next.total ? (next.received >= next.total ? 100 :
        uint64_t(next.received) * 100 / next.total) : 0;
      bool changed = force || next.state != m_status.state ||
        bool(next.total) != bool(m_status.total) || percent != m_percent;
      m_status = next;
      m_percent = percent;
      if (changed) markRectAsDirty(force ? bounds() : KDRect(16, 28, 288, 144));
      return changed;
    }
    void drawRect(KDContext *ctx, KDRect rect) const override {
      const KDColor green = KDColor::RGB24(0x466645);
      ctx->fillRect(rect, KDColorWhite);
      auto status = m_status;
      const char *title = "USB connected";
      const char *detail = "Ready for the Lefony OS installer";
      if (status.state == 1) { title = "Receiving update"; detail = "Keep the USB cable connected"; }
      if (status.state == 2) { title = "Image received"; detail = "Transfer verified; not installed yet"; }
      if (status.state == 3) { title = "Update transfer failed"; detail = "The installed OS was not changed"; }
      if (status.state == 4) { title = "Checking NAND"; detail = "Checking target blocks before writing"; }
      if (status.state == 5) { title = "Preparing NAND"; detail = "Do not disconnect power or reset"; }
      if (status.state == 6) { title = "Installing update"; detail = "Do not disconnect power or reset"; }
      if (status.state == 7) { title = "Verifying update"; detail = "Reading the written image back"; }
      if (status.state == 8) { title = "Update verified"; detail = "Ready to reboot into Lefony OS"; }
      if (status.state == 9) { title = "Installation stopped"; detail = "Check installer; recovery may be needed"; }
      ctx->drawString(title, KDPoint(16, 28), KDFont::LargeFont, green, KDColorWhite);
      ctx->drawString(detail, KDPoint(16, 62), KDFont::SmallFont, KDColorBlack, KDColorWhite);
      if (status.total) {
        uint32_t percent = status.received >= status.total ? 100 :
          uint64_t(status.received) * 100 / status.total;
        ctx->fillRect(KDRect(16, 106, 288, 16), KDColor::RGB24(0xe5ece5));
        ctx->fillRect(KDRect(16, 106, 288 * percent / 100, 16), green);
        char number[5] = {char('0' + percent / 100), char('0' + percent / 10 % 10),
                          char('0' + percent % 10), '%', 0};
        ctx->drawString(number + (percent < 100 ? (percent < 10 ? 2 : 1) : 0),
                        KDPoint(16, 132), KDFont::SmallFont, green, KDColorWhite);
      }
      ctx->drawString("Display stays awake on USB power", KDPoint(16, 179),
                      KDFont::SmallFont, KDColorBlack, KDColorWhite);
      ctx->drawString(LEFONY_BUILD_ID, KDPoint(16, 201), KDFont::SmallFont,
                      KDColor::RGB24(0x657184), KDColorWhite);
    }
  private:
    PrimeG2::USBDiagnostics::TransferStatus m_status = {};
    uint32_t m_percent = 0;
  } m_view;
public:
  LefonyUSBPage() : ViewController(nullptr) {}
  View *view() override { return &m_view; }
  bool refresh() { return m_view.refresh(); }
  void viewWillAppear() override { shown = true; m_view.refresh(true); }
  void viewDidDisappear() override { shown = false; }
  bool handleEvent(Ion::Events::Event event) override {
    if (event == Ion::Events::Back &&
        PrimeG2::USBDiagnostics::transferStatus().state == 0) {
      Container::activeApp()->dismissModalViewController();
      return true;
    }
    return true;
  }
  bool shown = false;
};

class LefonyUSBPageTimer : public Timer {
public:
  LefonyUSBPageTimer() : Timer(1) {}
  bool fire() override {
    bool changed = false;
    bool connected = PrimeG2::USBDiagnostics::externalPowerConnected();
    auto status = PrimeG2::USBDiagnostics::transferStatus();
    if (connected && (!m_connected || (status.state == 1 && m_previousState != 1))) {
      if (Container::activeApp() && !m_page.shown) {
        Container::activeApp()->displayModalViewController(&m_page, 0, 0);
        changed = true;
      }
    }
    if (!connected && m_connected && (status.state < 4 || status.state > 7) &&
        m_page.shown && Container::activeApp()) {
      Container::activeApp()->dismissModalViewController();
      changed = true;
    }
    // USB inhibits idle dimming, not the user's brightness preference.
    uint8_t chosen = GlobalPreferences::sharedGlobalPreferences()->brightnessLevel();
    if (connected && Ion::Backlight::brightness() != chosen)
      Ion::Backlight::setBrightness(chosen);
    m_connected = connected;
    m_previousState = status.state;
    if (m_page.shown) changed = m_page.refresh() || changed;
    return changed;
  }
private:
  LefonyUSBPage m_page;
  bool m_connected = false;
  uint32_t m_previousState = 0;
};
inline Timer *lefonyUSBPageTimer() { static LefonyUSBPageTimer timer; return &timer; }
