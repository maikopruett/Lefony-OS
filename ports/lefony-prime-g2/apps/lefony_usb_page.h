#pragma once
#include <escher.h>
#include <ion/backlight.h>
#include <ion/timing.h>
#include "global_preferences.h"
#include "../ion/src/prime_g2/usb_diagnostics.h"
#include "../ion/src/prime_g2/lefony_build_identity.h"
#include "../ion/src/prime_g2/app_management.h"

class LefonyUSBPage : public ViewController {
  class Content : public View {
  public:
    bool appMode = false;
    bool refresh(bool force = false) {
      auto app = PrimeG2::AppManagement::installationStatus();
      bool layoutChanged = appMode != m_appMode || app.phase != m_app.phase ||
        app.updating != m_app.updating || strcmp(app.name, m_app.name);
      bool appChanged = appMode && (layoutChanged || app.percent != m_app.percent);
      m_app = app;
      m_appMode = appMode;
      auto next = PrimeG2::USBDiagnostics::transferStatus();
      uint32_t percent = next.total ? (next.received >= next.total ? 100 :
        uint64_t(next.received) * 100 / next.total) : 0;
      force = force || layoutChanged;
      bool changed = force || appChanged || next.state != m_status.state ||
        bool(next.total) != bool(m_status.total) || percent != m_percent;
      m_status = next;
      m_percent = percent;
      if (changed) markRectAsDirty(force ? bounds() : KDRect(16, 28, 288, 144));
      return changed;
    }
    void drawRect(KDContext *ctx, KDRect rect) const override {
      const KDColor green = KDColor::RGB24(0x466645);
      ctx->fillRect(rect, KDColorWhite);
      if (m_appMode) {
        using PrimeG2::AppInstallProgress::Phase;
        const char *title = m_app.updating ? "Updating app" : "Installing app";
        const char *detail = "Receiving app";
        switch (m_app.phase) {
          case Phase::Package: detail = "Installing package"; break;
          case Phase::Data: title = "Installing app data"; detail = "Saving data"; break;
          case Phase::Icon: detail = "Saving app icon"; break;
          case Phase::Complete: title = "Done"; detail = ""; break;
          case Phase::Failed: title = "Installation stopped"; detail = "Check the installer to continue"; break;
          default: break;
        }
        ctx->drawString(title, KDPoint(16, 28), KDFont::LargeFont, green, KDColorWhite);
        // Authenticated manifest names are printable ASCII. Fit two lines at
        // the small font's 7-pixel width without drawing outside the screen.
        char first[41]{}, second[41]{};
        size_t length = strlen(m_app.name);
        memcpy(first, m_app.name, length < 40 ? length : 40);
        if (length > 40) memcpy(second, m_app.name + 40, length - 40);
        ctx->drawString(first, KDPoint(16, 62), KDFont::SmallFont, KDColorBlack, KDColorWhite);
        ctx->drawString(second, KDPoint(16, 80), KDFont::SmallFont, KDColorBlack, KDColorWhite);
        drawProgress(ctx, m_app.percent, green);
        ctx->drawString(detail, KDPoint(16, 158), KDFont::SmallFont, KDColorBlack, KDColorWhite);
        if (m_app.active()) ctx->drawString("Keep the USB cable connected", KDPoint(16, 190),
          KDFont::SmallFont, KDColorBlack, KDColorWhite);
        return;
      }
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
        drawProgress(ctx, percent, green);
      }
      ctx->drawString("Display stays awake on USB power", KDPoint(16, 179),
                      KDFont::SmallFont, KDColorBlack, KDColorWhite);
      ctx->drawString(LEFONY_BUILD_ID, KDPoint(16, 201), KDFont::SmallFont,
                      KDColor::RGB24(0x657184), KDColorWhite);
    }
  private:
    void drawProgress(KDContext *ctx, uint32_t percent, KDColor green) const {
      ctx->fillRect(KDRect(16, 106, 288, 16), KDColor::RGB24(0xe5ece5));
      ctx->fillRect(KDRect(16, 106, 288 * percent / 100, 16), green);
      char number[5] = {char('0' + percent / 100), char('0' + percent / 10 % 10),
                       char('0' + percent % 10), '%', 0};
      ctx->drawString(number + (percent < 100 ? (percent < 10 ? 2 : 1) : 0),
                      KDPoint(16, 132), KDFont::SmallFont, green, KDColorWhite);
    }
    PrimeG2::AppInstallProgress::Status m_app{};
    bool m_appMode = false;
    PrimeG2::USBDiagnostics::TransferStatus m_status = {};
    uint32_t m_percent = 0;
  } m_view;
public:
  LefonyUSBPage() : ViewController(nullptr) {}
  View *view() override { return &m_view; }
  bool refresh() { return m_view.refresh(); }
  void setAppMode(bool enabled) { m_view.appMode = enabled; }
  void viewWillAppear() override { shown = true; m_view.refresh(true); }
  void viewDidDisappear() override { shown = false; }
  bool handleEvent(Ion::Events::Event event) override {
    if (event == Ion::Events::Back && !m_view.appMode &&
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
    bool appVisible = m_presentation.update(PrimeG2::AppManagement::installationStatus(),
                                           Ion::Timing::millis());
    bool osBusy = status.state == 1 || (status.state >= 4 && status.state <= 7);
    appVisible = appVisible && !osBusy;
    m_page.setAppMode(appVisible);
    if (m_appVisible && !appVisible && !osBusy && m_page.shown && Container::activeApp()) {
      Container::activeApp()->dismissModalViewController();
      changed = true;
    }
    if (appVisible || (connected && (!m_connected || (status.state == 1 && m_previousState != 1)))) {
      if (Container::activeApp() && !m_page.shown) {
        Container::activeApp()->displayModalViewController(&m_page, 0, 0);
        changed = true;
      }
    }
    if (!appVisible && !connected && m_connected && (status.state < 4 || status.state > 7) &&
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
    m_appVisible = appVisible;
    if (m_page.shown) changed = m_page.refresh() || changed;
    return changed;
  }
private:
  LefonyUSBPage m_page;
  PrimeG2::AppInstallProgress::Presentation m_presentation;
  bool m_appVisible = false;
  bool m_connected = false;
  uint32_t m_previousState = 0;
};
inline Timer *lefonyUSBPageTimer() { static LefonyUSBPageTimer timer; return &timer; }
