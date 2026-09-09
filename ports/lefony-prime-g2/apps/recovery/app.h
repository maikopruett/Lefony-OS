#ifndef RECOVERY_APP_H
#define RECOVERY_APP_H

#include "../shared/shared_app.h"
#include <escher.h>

namespace Recovery {

class App : public ::App {
public:
  class Descriptor : public ::App::Descriptor {
  public:
    I18n::Message name() override;
    I18n::Message upperName() override;
    const Image * icon() override;
  };

  class Snapshot : public SharedApp::Snapshot {
  public:
    App * unpack(Container * container) override;
    Descriptor * descriptor() override;
  };

  void didBecomeActive(Window * window) override;

private:
  class Controller : public ViewController {
  public:
    Controller();
    View * view() override { return &m_view; }

  private:
    SolidColorView m_view;
  };

  App(Snapshot * snapshot);
  Controller m_controller;
};

}

#endif
