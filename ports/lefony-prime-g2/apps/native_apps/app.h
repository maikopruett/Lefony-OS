// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_NATIVE_APPS_APP_H
#define LEFONY_NATIVE_APPS_APP_H
#include "../shared/shared_app.h"
#include <escher.h>
namespace NativeApps {
class App : public ::App, public Timer {
public:
  class Descriptor : public ::App::Descriptor {
  public:
    I18n::Message name() override;
    I18n::Message upperName() override;
    const Image *icon() override;
  };
  class Snapshot : public SharedApp::Snapshot {
  public:
    App *unpack(Container *container) override;
    Descriptor *descriptor() override;
  };
  void didBecomeActive(Window *window) override;
  void willBecomeInactive() override;
  bool fire() override;
private:
  class SurfaceView : public View {
  public:
    unsigned selected=0;
    void invalidate() { markRectAsDirty(bounds()); }
    void drawRect(KDContext *context,KDRect rect) const override;
  };
  class Controller : public ViewController {
  public:
    Controller() : ViewController(nullptr) {}
    View *view() override { return &m_view; }
    void refresh() { m_view.invalidate(); }
    void closeInstalled();
    bool installed=false;
    bool handleEvent(Ion::Events::Event event) override;
    bool handleTouch(const Ion::Touch::Event &event) override;
    bool acceptsMultitouch() const override { return true; }
  private:
    bool activate(unsigned slot);
    int m_touchSlot=-1;
    SurfaceView m_view;
  };
  explicit App(Snapshot *snapshot);
  Controller m_controller;
};
}
#endif
