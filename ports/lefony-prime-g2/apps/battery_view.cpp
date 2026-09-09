#include "battery_view.h"

extern "C" bool prime_g2_battery_present() __attribute__((weak));
extern "C" bool prime_g2_charger_fault_or_suspended() __attribute__((weak));

const uint8_t flashMask[BatteryView::k_flashHeight][BatteryView::k_flashWidth] = {
  {0xDB, 0x00, 0x00, 0xFF}, {0xB7, 0x00, 0x6D, 0xFF},
  {0x6D, 0x00, 0xDB, 0xFF}, {0x24, 0x00, 0x00, 0x00},
  {0x00, 0x00, 0x00, 0x24}, {0xFF, 0xDB, 0x00, 0x6D},
  {0xFF, 0x6D, 0x00, 0xB7}, {0xFF, 0x00, 0x00, 0xDB},
};

const uint8_t tickMask[BatteryView::k_tickHeight][BatteryView::k_tickWidth] = {
  {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xDB, 0x00, 0x24},
  {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x6D, 0x00, 0xDB},
  {0x6D, 0x00, 0xB7, 0xFF, 0xB7, 0x00, 0x24, 0xFF},
  {0xDB, 0x00, 0x00, 0xFF, 0x00, 0x00, 0xFF, 0xFF},
  {0xFF, 0xB7, 0x00, 0x24, 0x00, 0xB7, 0xFF, 0xFF},
  {0xFF, 0xFF, 0x24, 0x00, 0x24, 0xFF, 0xFF, 0xFF},
};

bool BatteryView::readBatteryPresent() {
  return !prime_g2_battery_present || prime_g2_battery_present();
}

bool BatteryView::readChargerFault() {
  return prime_g2_charger_fault_or_suspended &&
    prime_g2_charger_fault_or_suspended();
}

BatteryView::BatteryView() :
  m_chargeState(Ion::Battery::Charge::SOMEWHERE_INBETWEEN),
  m_batteryPresent(readBatteryPresent()),
  m_chargerFault(readChargerFault()),
  m_isCharging(false),
  m_isPlugged(false)
{}

bool BatteryView::setChargeState(Ion::Battery::Charge chargeState) {
  chargeState = chargeState == Ion::Battery::Charge::EMPTY ?
    Ion::Battery::Charge::LOW : chargeState;
  bool batteryPresent = readBatteryPresent();
  bool chargerFault = readChargerFault();
  if (chargeState != m_chargeState ||
      batteryPresent != m_batteryPresent ||
      chargerFault != m_chargerFault) {
    m_chargeState = chargeState;
    m_batteryPresent = batteryPresent;
    m_chargerFault = chargerFault;
    markRectAsDirty(bounds());
    return true;
  }
  return false;
}

bool BatteryView::setIsCharging(bool isCharging) {
  if (m_isCharging == isCharging) return false;
  m_isCharging = isCharging;
  markRectAsDirty(bounds());
  return true;
}

bool BatteryView::setIsPlugged(bool isPlugged) {
  if (m_isPlugged == isPlugged) return false;
  m_isPlugged = isPlugged;
  markRectAsDirty(bounds());
  return true;
}

void BatteryView::drawRect(KDContext * ctx, KDRect) const {
  constexpr KDCoordinate x = 0;
  constexpr KDCoordinate y = (14 - k_batteryHeight) / 2;
  ctx->fillRect(KDRect(x, y + 1, k_elementWidth, k_batteryHeight - 2), Palette::Battery);
  ctx->fillRect(KDRect(x + 1, y, k_batteryWidth - 3, 1), Palette::Battery);
  ctx->fillRect(KDRect(x + 1, y + k_batteryHeight - 1, k_batteryWidth - 3, 1), Palette::Battery);
  constexpr KDCoordinate insideX = k_elementWidth + k_separatorThickness;
  constexpr KDCoordinate insideWidth = k_batteryWidth - 3 * k_elementWidth - 2 * k_separatorThickness;
  if (m_isCharging) {
    ctx->fillRect(KDRect(x + insideX, y + 2, insideWidth, k_batteryHeight - 4), Palette::BatteryInCharge);
    KDRect frame(x + (k_batteryWidth - k_flashWidth) / 2, y, k_flashWidth, k_flashHeight);
    KDColor work[k_flashHeight * k_flashWidth];
    ctx->blendRectWithMask(frame, Palette::Battery, (const uint8_t *)flashMask, work);
  } else if (m_chargerFault && m_isPlugged) {
    ctx->fillRect(KDRect(x + insideX, y + 2, insideWidth,
                         k_batteryHeight - 4), Palette::BatteryLow);
    /* A compact exclamation mark distinguishes a PF1550 charger fault or
     * suspend from normal external-power and charge-complete states. */
    ctx->fillRect(KDRect(x + k_batteryWidth / 2, y + 2, 1, 3),
                  Palette::Toolbar);
    ctx->fillRect(KDRect(x + k_batteryWidth / 2, y + 6, 1, 1),
                  Palette::Toolbar);
  } else if (!m_batteryPresent) {
    ctx->fillRect(KDRect(x + insideX, y + 2, insideWidth,
                         k_batteryHeight - 4),
                  KDColor::blend(Palette::Toolbar, Palette::Battery, 128));
  } else if (m_chargeState == Ion::Battery::Charge::LOW) {
    ctx->fillRect(KDRect(x + insideX, y + 2, 2 * k_elementWidth, k_batteryHeight - 4), Palette::BatteryLow);
    ctx->fillRect(KDRect(x + 3 * k_elementWidth + k_separatorThickness, y + 2,
      k_batteryWidth - 5 * k_elementWidth - 2 * k_separatorThickness,
      k_batteryHeight - 4), KDColor::blend(Palette::Toolbar, Palette::Battery, 128));
  } else if (m_chargeState == Ion::Battery::Charge::SOMEWHERE_INBETWEEN) {
    constexpr KDCoordinate middle = insideWidth / 2;
    ctx->fillRect(KDRect(x + insideX, y + 2, middle, k_batteryHeight - 4), Palette::Battery);
    ctx->fillRect(KDRect(x + insideX + middle, y + 2, middle + 1, k_batteryHeight - 4),
      KDColor::blend(Palette::Toolbar, Palette::Battery, 128));
  } else {
    ctx->fillRect(KDRect(x + insideX, y + 2, insideWidth, k_batteryHeight - 4), Palette::Battery);
    if (m_isPlugged) {
      KDRect frame(x + (k_batteryWidth - k_tickWidth) / 2,
        y + (k_batteryHeight - k_tickHeight) / 2, k_tickWidth, k_tickHeight);
      KDColor work[k_tickHeight * k_tickWidth];
      ctx->blendRectWithMask(frame, Palette::Toolbar, (const uint8_t *)tickMask, work);
    }
  }
  ctx->fillRect(KDRect(x + k_batteryWidth - 2 * k_elementWidth, y + 1,
    k_elementWidth, k_batteryHeight - 2), Palette::Battery);
  ctx->fillRect(KDRect(x + k_batteryWidth - k_elementWidth,
    y + (k_batteryHeight - k_capHeight) / 2, k_elementWidth, k_capHeight), Palette::Battery);
}

KDSize BatteryView::minimalSizeForOptimalDisplay() const {
  return KDSize(k_batteryWidth, 14);
}
