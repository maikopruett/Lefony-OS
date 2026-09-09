#ifndef SETTINGS_LEFONY_USB_CONTROLLER_H
#define SETTINGS_LEFONY_USB_CONTROLLER_H

#include <escher.h>
#include <string.h>
#include "../../../ion/src/prime_g2/usb_diagnostics.h"
#include "../../../ion/src/prime_g2/lefony_build_identity.h"

namespace Settings {

// Frozen snapshot: drawing the page never touches controller registers or
// refreshes itself underneath a photograph. OK explicitly captures again.
class LefonyUsbController : public ViewController {
  class SnapshotView : public View {
  public:
    void refresh() {
      m_snapshot = PrimeG2::USBDiagnostics::debugSnapshot();
      markRectAsDirty(bounds());
    }
    void drawRect(KDContext *ctx, KDRect rect) const override {
      ctx->fillRect(rect, KDColorWhite);
      line(ctx, 0, "LEFONY USB DIAGNOSTICS (snapshot)");
      line(ctx, 1, LEFONY_BUILD_ID);
      pair(ctx, 2, "FLAGS", m_snapshot.flags, "ERR", m_snapshot.error);
      pair(ctx, 3, "REQ", m_snapshot.trace.request, "PH", m_snapshot.trace.phase);
      pair(ctx, 4, "LEN", m_snapshot.trace.length, "SETUPS", m_snapshot.trace.setups);
      pair(ctx, 5, "DONE", m_snapshot.trace.completed, "RESET", m_snapshot.trace.resets);
      pair(ctx, 6, "CMD", m_snapshot.command, "STS", m_snapshot.status);
      pair(ctx, 7, "MODE", m_snapshot.mode, "PORT", m_snapshot.port);
      pair(ctx, 8, "SETUP", m_snapshot.setup, "PRIME", m_snapshot.prime);
      pair(ctx, 9, "FLUSH", m_snapshot.flush, "CMPL", m_snapshot.complete);
      pair(ctx, 10, "ADDR", m_snapshot.address, "LIST", m_snapshot.list);
      pair(ctx, 11, "IN-TD", m_snapshot.inToken, "OUT-TD", m_snapshot.outToken);
      pair(ctx, 12, "RAW0", m_snapshot.rawSetup0, "RAW1", m_snapshot.rawSetup1);
      pair(ctx, 13, "WAIT", m_snapshot.addressWaitPolls, "FAST", m_snapshot.fastAddressCompletions);
      line(ctx, 14, "All values hex. OK refresh / Back exit");
    }
  private:
    static void line(KDContext *ctx, int row, const char *text) {
      ctx->drawString(text, KDPoint(4, 4 + row * 14), KDFont::SmallFont,
                      KDColorBlack, KDColorWhite);
    }
    static void pair(KDContext *ctx, int row, const char *a, uint32_t av,
                     const char *b, uint32_t bv) {
      char text[40] = {};
      unsigned n = 0;
      auto append = [&](const char *s) { while (*s) text[n++] = *s++; };
      auto hex = [&](uint32_t value) {
        const char *digits = "0123456789ABCDEF";
        for (int shift = 28; shift >= 0; shift -= 4) text[n++] = digits[(value >> shift) & 15];
      };
      append(a); append(" "); hex(av); append("  "); append(b); append(" "); hex(bv);
      line(ctx, row, text);
    }
    PrimeG2::USBDiagnostics::DebugSnapshot m_snapshot = {};
  };
public:
  LefonyUsbController() : ViewController(nullptr) {}
  View *view() override { return &m_view; }
  void viewWillAppear() override { m_view.refresh(); }
  bool handleEvent(Ion::Events::Event event) override {
    if (event == Ion::Events::OK || event == Ion::Events::EXE) {
      m_view.refresh(); return true;
    }
    if (event == Ion::Events::Back || event == Ion::Events::Left) {
      Container::activeApp()->dismissModalViewController(); return true;
    }
    return false;
  }
private:
  SnapshotView m_view;
};

}
#endif
