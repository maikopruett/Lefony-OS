#pragma once
#include <escher.h>
#include <ion/touch.h>
#include "../../apps_container.h"
#include "../../../ion/src/prime_g2/display.h"
#include "../../../ion/src/prime_g2/timing.h"

namespace Settings {
class LefonyRefreshController : public ViewController, public Timer {
  class Content : public View {
  public:
    explicit Content(LefonyRefreshController * owner) : m_owner(owner) {}
    void refresh() { markRectAsDirty(bounds()); }
    void drawRect(KDContext * ctx, KDRect rect) const override {
      auto green = KDColor::RGB24(0x466645);
      ctx->fillRect(rect, KDColorWhite);
      ctx->drawString("LCD refresh rate", KDPoint(18, 18), KDFont::LargeFont, green, KDColorWhite);
      bool trial = PrimeG2::Display::refreshTrialActive();
      const char * current = PrimeG2::Display::refreshMilliHz() < 57000 ?
        "Current: 55.2 Hz (experimental)" : "Current: 58.9 Hz (default)";
      ctx->drawString(current, KDPoint(18, 48), KDFont::SmallFont, KDColorBlack, KDColorWhite);
      for (int row = 0; row < 2; row++) {
        bool selected = row == m_owner->m_row;
        auto background = selected ? green : KDColor::RGB24(0xe5ece5);
        ctx->fillRect(button(row), background);
        const char * label = trial ? (row == 0 ? "Keep 55.2 Hz" : "Restore 58.9 Hz") :
          (row == 0 ? "58.9 Hz - default" : "Test 55.2 Hz");
        ctx->drawString(label, KDPoint(30, 78 + row * 42), KDFont::SmallFont,
                        selected ? KDColorWhite : KDColorBlack, background);
      }
      ctx->drawString(trial ? "Picture OK? Confirm within 15 seconds." :
                      "New rate reverts unless confirmed.", KDPoint(18, 162),
                      KDFont::SmallFont, KDColorBlack, KDColorWhite);
      ctx->drawString("Reboot always restores 58.9 Hz.", KDPoint(18, 182),
                      KDFont::SmallFont, KDColorBlack, KDColorWhite);
      if (m_owner->m_failed)
        ctx->drawString("Mode switch unavailable or failed.", KDPoint(18, 202),
                        KDFont::SmallFont, KDColorRed, KDColorWhite);
    }
    static KDRect button(int row) { return KDRect(18, 70 + row * 42, 284, 32); }
  private:
    LefonyRefreshController * m_owner;
  } m_view;
public:
  LefonyRefreshController() : ViewController(nullptr), Timer(1), m_view(this) {}
  View * view() override { return &m_view; }
  void viewWillAppear() override {
    m_row = 0; m_failed = false; m_trial = PrimeG2::Display::refreshTrialActive();
    if (!m_timerAdded) {
      setNext(nullptr);
      AppsContainer::sharedAppsContainer()->addTimer(this); m_timerAdded = true;
    }
    Timer::reset(); m_view.refresh();
  }
  void viewDidDisappear() override {
    if (m_timerAdded) {
      AppsContainer::sharedAppsContainer()->removeTimer(this);
      setNext(nullptr); // RunLoop::removeTimer does not detach the next link.
      m_timerAdded = false;
    }
    PrimeG2::Display::cancelRefreshTrial();
    m_touchRow = -1;
  }
  bool handleEvent(Ion::Events::Event e) override {
    if (e == Ion::Events::Back) { Container::activeApp()->dismissModalViewController(); return true; }
    if (e == Ion::Events::Up || e == Ion::Events::Down) {
      m_row = e == Ion::Events::Up ? 0 : 1;
      m_view.refresh(); return true;
    }
    if (e == Ion::Events::OK || e == Ion::Events::EXE) { activate(); return true; }
    return true;
  }
  bool handleTouch(const Ion::Touch::Event & touch) override {
    auto origin = m_view.touchOrigin();
    KDPoint point(touch.x - origin.x(), touch.y - origin.y());
    int row = -1;
    for (int i = 0; i < 2; i++) if (Content::button(i).contains(point)) row = i;
    using Ion::Touch::Phase;
    if (touch.phase == Phase::Down) { m_touchRow = row; return true; }
    if (touch.phase == Phase::Cancel || touch.dragging) m_touchRow = -1;
    if (touch.phase == Phase::Up) {
      bool click = row >= 0 && row == m_touchRow;
      m_touchRow = -1;
      if (click) { m_row = row; activate(); }
    }
    return true;
  }
protected:
  bool fire() override {
    bool trial = PrimeG2::Display::refreshTrialActive();
    if (trial == m_trial) return false;
    m_trial = trial; m_view.refresh(); return true;
  }
private:
  void activate() {
    bool trial = PrimeG2::Display::refreshTrialActive();
    if (trial && m_row == 0 && PrimeG2::Timing::elapsedMillis() < m_confirmAfter) return;
    m_failed = !(trial ? (m_row == 0 ? PrimeG2::Display::confirmRefreshRate() :
                                      PrimeG2::Display::requestRefreshRate(59)) :
                          PrimeG2::Display::requestRefreshRate(m_row == 0 ? 59 : 55));
    if (!trial && m_row == 1 && !m_failed) {
      m_row = 0; m_confirmAfter = PrimeG2::Timing::elapsedMillis() + 1000;
    }
    m_trial = PrimeG2::Display::refreshTrialActive();
    m_view.refresh();
  }
  int m_row = 0, m_touchRow = -1;
  bool m_timerAdded = false, m_trial = false, m_failed = false;
  uint64_t m_confirmAfter = 0;
};

inline void showLefonyRefreshController() {
  static LefonyRefreshController controller;
  Container::activeApp()->displayModalViewController(&controller, 0, 0);
}
}
