#include "global_preferences.h"

#include <ion.h>
#include <ion/storage.h>
#include <ion/timing.h>
#include <poincare/preferences.h>
#include <string.h>

namespace {
constexpr uint32_t Magic = 0x31465250; // "PRF1"
constexpr uint16_t Version = 1;
constexpr char RecordName[] = "mahalo.preferences";

enum Flag : uint8_t {
  ShowPopUp = 1 << 0,
  AutoComplete = 1 << 1,
  SyntaxHighlighting = 1 << 2,
  ClearShift = 1 << 3,
  SmallFont = 1 << 4,
};

struct __attribute__((packed)) Payload {
  uint32_t magic;
  uint16_t version;
  uint16_t size;
  uint8_t language;
  uint8_t country;
  uint8_t flags;
  uint8_t brightness;
  uint16_t idleSuspend;
  uint16_t idleDimming;
  uint8_t brightnessShortcut;
  uint8_t angleUnit;
  uint8_t displayMode;
  uint8_t editionMode;
  uint8_t complexFormat;
  uint8_t significantDigits;
  uint8_t symbolMultiplication;
  uint8_t symbolFunction;
  uint8_t pythonFont;
  uint32_t crc;
};

static_assert(sizeof(Payload) == 29, "Preference payload layout changed");
bool sInitialized = false;
uint64_t sNextSync = 0;

uint32_t checksum(const Payload &source) {
  Payload copy = source;
  copy.crc = 0;
  return Ion::crc32Byte(reinterpret_cast<const uint8_t *>(&copy), sizeof(copy));
}

Payload currentPayload() {
  GlobalPreferences *global = GlobalPreferences::sharedGlobalPreferences();
  Poincare::Preferences *math = Poincare::Preferences::sharedPreferences();
  Payload result = {};
  result.magic = Magic;
  result.version = Version;
  result.size = sizeof(Payload);
  result.language = static_cast<uint8_t>(global->language());
  result.country = static_cast<uint8_t>(global->country());
  result.flags = (global->showPopUp() ? ShowPopUp : 0) |
    (global->autocomplete() ? AutoComplete : 0) |
    (global->syntaxhighlighting() ? SyntaxHighlighting : 0) |
    (global->clearShift() ? ClearShift : 0) |
    (global->font() == KDFont::SmallFont ? SmallFont : 0);
  result.brightness = global->brightnessLevel();
  result.idleSuspend = global->idleBeforeSuspendSeconds();
  result.idleDimming = global->idleBeforeDimmingSeconds();
  result.brightnessShortcut = global->brightnessShortcut();
  result.angleUnit = static_cast<uint8_t>(math->angleUnit());
  result.displayMode = static_cast<uint8_t>(math->displayMode());
  result.editionMode = static_cast<uint8_t>(math->editionMode());
  result.complexFormat = static_cast<uint8_t>(math->complexFormat());
  result.significantDigits = math->numberOfSignificantDigits();
  result.symbolMultiplication = static_cast<uint8_t>(math->symbolOfMultiplication());
  result.symbolFunction = static_cast<uint8_t>(math->symbolOfFunction());
  result.pythonFont = static_cast<uint8_t>(math->pythonFont());
  result.crc = checksum(result);
  return result;
}

bool valid(const Payload &value) {
  constexpr uint8_t KnownFlags = ShowPopUp | AutoComplete |
    SyntaxHighlighting | ClearShift | SmallFont;
  return value.magic == Magic && value.version == Version &&
    value.size == sizeof(Payload) && value.crc == checksum(value) &&
    value.language < I18n::NumberOfLanguages &&
    value.country < I18n::NumberOfCountries &&
    (value.flags & ~KnownFlags) == 0 &&
    value.brightness <= Ion::Backlight::MaxBrightness &&
    value.idleSuspend >= 5 && value.idleSuspend <= 7200 &&
    value.idleDimming >= 3 && value.idleDimming <= 1200 &&
    value.brightnessShortcut <= GlobalPreferences::NumberOfBrightnessStates &&
    value.angleUnit <= 2 && value.displayMode <= 2 &&
    value.editionMode <= 1 && value.complexFormat <= 2 &&
    value.significantDigits >= 1 && value.significantDigits <= 14 &&
    value.symbolMultiplication <= 3 && value.symbolFunction <= 2 &&
    value.pythonFont <= 1;
}

void apply(const Payload &value) {
  GlobalPreferences *global = GlobalPreferences::sharedGlobalPreferences();
  Poincare::Preferences *math = Poincare::Preferences::sharedPreferences();
  global->setLanguage(static_cast<I18n::Language>(value.language));
  global->setCountry(static_cast<I18n::Country>(value.country));
  global->setShowPopUp(value.flags & ShowPopUp);
  global->setAutocomplete(value.flags & AutoComplete);
  global->setSyntaxhighlighting(value.flags & SyntaxHighlighting);
  global->setClearShift(value.flags & ClearShift);
  global->setFont(value.flags & SmallFont ? KDFont::SmallFont : KDFont::LargeFont);
  global->setBrightnessLevel(value.brightness);
  global->setIdleBeforeSuspendSeconds(value.idleSuspend);
  global->setIdleBeforeDimmingSeconds(value.idleDimming);
  global->setBrightnessShortcut(value.brightnessShortcut);
  math->setAngleUnit(static_cast<Poincare::Preferences::AngleUnit>(value.angleUnit));
  math->setDisplayMode(static_cast<Poincare::Preferences::PrintFloatMode>(value.displayMode));
  math->setEditionMode(static_cast<Poincare::Preferences::EditionMode>(value.editionMode));
  math->setComplexFormat(static_cast<Poincare::Preferences::ComplexFormat>(value.complexFormat));
  math->setNumberOfSignificantDigits(value.significantDigits);
  math->setSymbolMultiplication(static_cast<Poincare::Preferences::SymbolMultiplication>(value.symbolMultiplication));
  math->setSymbolOfFunction(static_cast<Poincare::Preferences::SymbolFunction>(value.symbolFunction));
  math->setPythonFont(static_cast<Poincare::Preferences::PythonFont>(value.pythonFont));
  Ion::Backlight::setBrightness(global->brightnessLevel());
}

void save(const Payload &value) {
  Ion::Storage *storage = Ion::Storage::sharedStorage();
  Ion::Storage::Record record = storage->recordNamed(RecordName);
  if (record.isNull()) {
    storage->createRecordWithFullName(RecordName, &value, sizeof(value));
  } else {
    Ion::Storage::Record::Data data = record.value();
    if (data.size != sizeof(value) || memcmp(data.buffer, &value, sizeof(value)) != 0) {
      record.setValue({&value, sizeof(value)});
    }
  }
}

void resetDefaults() {
  GlobalPreferences *global = GlobalPreferences::sharedGlobalPreferences();
  Poincare::Preferences *math = Poincare::Preferences::sharedPreferences();
  global->setLanguage(static_cast<I18n::Language>(0));
  global->setCountry(static_cast<I18n::Country>(0));
  global->setShowPopUp(true);
  global->setAutocomplete(true);
  global->setSyntaxhighlighting(true);
  global->setClearShift(true);
  global->setBrightnessLevel(Ion::Backlight::MaxBrightness);
  global->setIdleBeforeSuspendSeconds(55);
  global->setIdleBeforeDimmingSeconds(45);
  global->setBrightnessShortcut(4);
  global->setFont(KDFont::LargeFont);
  math->setAngleUnit(Poincare::Preferences::AngleUnit::Degree);
  math->setDisplayMode(Poincare::Preferences::PrintFloatMode::Decimal);
  math->setEditionMode(Poincare::Preferences::EditionMode::Edition2D);
  math->setComplexFormat(Poincare::Preferences::ComplexFormat::Real);
  math->setNumberOfSignificantDigits(Poincare::Preferences::LargeNumberOfSignificantDigits);
  math->setSymbolMultiplication(Poincare::Preferences::SymbolMultiplication::Auto);
  math->setSymbolOfFunction(Poincare::Preferences::SymbolFunction::Default);
  math->setPythonFont(Poincare::Preferences::PythonFont::Large);
  Ion::Backlight::setBrightness(global->brightnessLevel());
}
}

extern "C" void prime_g2_preferences_sync() {
  if (!sInitialized) {
    sInitialized = true;
    Ion::Storage::Record record = Ion::Storage::sharedStorage()->recordNamed(RecordName);
    if (!record.isNull()) {
      Ion::Storage::Record::Data data = record.value();
      if (data.size == sizeof(Payload)) {
        Payload stored;
        memcpy(&stored, data.buffer, sizeof(stored));
        if (valid(stored)) {
          apply(stored);
        }
      }
    }
    save(currentPayload());
    sNextSync = Ion::Timing::millis() + 250;
    return;
  }
  uint64_t now = Ion::Timing::millis();
  if (now >= sNextSync) {
    save(currentPayload());
    sNextSync = now + 250;
  }
}

extern "C" void prime_g2_preferences_factory_reset() {
  resetDefaults();
  sInitialized = true;
  save(currentPayload());
  sNextSync = Ion::Timing::millis() + 250;
}

extern "C" int prime_g2_preferences_get_for_test(const char *name) {
  GlobalPreferences *global = GlobalPreferences::sharedGlobalPreferences();
  Poincare::Preferences *math = Poincare::Preferences::sharedPreferences();
  if (strcmp(name, "ANGLE") == 0) return static_cast<int>(math->angleUnit());
  if (strcmp(name, "DISPLAY") == 0) return static_cast<int>(math->displayMode());
  if (strcmp(name, "COMPLEX") == 0) return static_cast<int>(math->complexFormat());
  if (strcmp(name, "DIGITS") == 0) return math->numberOfSignificantDigits();
  if (strcmp(name, "BRIGHTNESS") == 0) return global->brightnessLevel();
  if (strcmp(name, "AUTOCOMPLETE") == 0) return global->autocomplete();
  if (strcmp(name, "FONT") == 0) return global->font() == KDFont::SmallFont;
  return -1;
}

extern "C" bool prime_g2_preferences_set_for_test(const char *name, unsigned value) {
  GlobalPreferences *global = GlobalPreferences::sharedGlobalPreferences();
  Poincare::Preferences *math = Poincare::Preferences::sharedPreferences();
  if (strcmp(name, "ANGLE") == 0 && value <= 2) math->setAngleUnit(static_cast<Poincare::Preferences::AngleUnit>(value));
  else if (strcmp(name, "DISPLAY") == 0 && value <= 2) math->setDisplayMode(static_cast<Poincare::Preferences::PrintFloatMode>(value));
  else if (strcmp(name, "COMPLEX") == 0 && value <= 2) math->setComplexFormat(static_cast<Poincare::Preferences::ComplexFormat>(value));
  else if (strcmp(name, "DIGITS") == 0 && value >= 1 && value <= 14) math->setNumberOfSignificantDigits(value);
  else if (strcmp(name, "BRIGHTNESS") == 0 && value <= Ion::Backlight::MaxBrightness) global->setBrightnessLevel(value);
  else if (strcmp(name, "AUTOCOMPLETE") == 0 && value <= 1) global->setAutocomplete(value);
  else if (strcmp(name, "FONT") == 0 && value <= 1) global->setFont(value ? KDFont::SmallFont : KDFont::LargeFont);
  else return false;
  save(currentPayload());
  return true;
}
