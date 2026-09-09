#include "app.h"

#include <apps/settings/settings_icon.h>
#include "../../ion/src/prime_g2/watchdog.h"
#include <apps/i18n.h>

namespace Recovery {

I18n::Message App::Descriptor::name() {
  return I18n::Message::RecoveryApp;
}

I18n::Message App::Descriptor::upperName() {
  return I18n::Message::RecoveryAppCapital;
}

const Image * App::Descriptor::icon() {
  // Reuse the always-built Settings artwork until Recovery gets a dedicated
  // icon in the Lefony theme. The launcher label remains unambiguous.
  return ImageStore::SettingsIcon;
}

App * App::Snapshot::unpack(Container * container) {
  return new (container->currentAppBuffer()) App(this);
}

App::Descriptor * App::Snapshot::descriptor() {
  static Descriptor descriptor;
  return &descriptor;
}

App::Controller::Controller() :
  ViewController(nullptr),
  m_view(Palette::BackgroundHard)
{
}

App::App(Snapshot * snapshot) :
  ::App(snapshot, &m_controller)
{
}

void App::didBecomeActive(Window * window) {
  ::App::didBecomeActive(window);
  PrimeG2::Watchdog::rebootToROMRecovery();
}

}
