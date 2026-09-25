#ifndef SETTINGS_LEFONY_RECOVERY_CONTROLLER_H
#define SETTINGS_LEFONY_RECOVERY_CONTROLLER_H

#include <escher/pop_up_controller.h>
#include "../../../ion/src/prime_g2/watchdog.h"

namespace Settings {

class LefonyRecoveryController : public ::PopUpController {
public:
  LefonyRecoveryController() : ::PopUpController(4, Invocation(
    [](void *, void *) {
      if (!PrimeG2::Watchdog::rebootToUBootRecovery()) {
        Container::activeApp()->dismissModalViewController();
        Container::activeApp()->displayWarning(I18n::Message::LefonyRecoveryFailed);
      }
      return true;
    }, nullptr)) {
    m_contentView.setMessage(0, I18n::Message::LefonyRecoveryWarning1);
    m_contentView.setMessage(1, I18n::Message::LefonyRecoveryWarning2);
    m_contentView.setMessage(2, I18n::Message::LefonyRecoveryWarning3);
    m_contentView.setMessage(3, I18n::Message::LefonyRecoveryWarning4);
  }
};

}

#endif
