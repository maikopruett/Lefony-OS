#include "emulator.h"

#include "display.h"
#include "registers.h"
#include "persistence.h"
#include "services.h"
#include "timing.h"
#include "touch.h"
#include "usb_diagnostics.h"
#include "uart.h"
#include "system.h"
#include "interrupts.h"
#include "watchdog.h"
#include "native_app.h"

#include <ion/timing.h>
#include <ion.h>
#include <ion/storage.h>
#include <ion/console.h>
#include <ion/backlight.h>
#include <ion/display.h>
#include <ion/events.h>
#include <ion/battery.h>
#include <ion/led.h>
#include <ion/power.h>
#include <ion/rtc.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern "C" {
bool __attribute__((weak)) prime_g2_launch_native_app() { return false; }
bool __attribute__((weak)) prime_g2_launch_installed_native_app(unsigned) { return false; }
void __attribute__((weak)) prime_g2_preferences_sync() {}
void __attribute__((weak)) prime_g2_preferences_factory_reset() {}
int __attribute__((weak)) prime_g2_preferences_get_for_test(const char *) { return -1; }
bool __attribute__((weak)) prime_g2_preferences_set_for_test(const char *, unsigned) { return false; }
void __attribute__((weak)) prime_g2_datasets_sync() {}
void __attribute__((weak)) prime_g2_datasets_factory_reset() {}
bool __attribute__((weak)) prime_g2_test_dataset_set(unsigned, unsigned, unsigned, unsigned, int) { return false; }
bool __attribute__((weak)) prime_g2_test_dataset_get(unsigned, unsigned, unsigned, unsigned, int *) { return false; }
unsigned prime_g2_heap_capacity();
unsigned prime_g2_heap_current();
unsigned prime_g2_heap_high_water();
unsigned prime_g2_heap_allocation_count();
int prime_g2_heap_fragmentation_self_test();
int __attribute__((weak)) prime_g2_test_active_app() { return -1; }
bool __attribute__((weak)) prime_g2_test_home_selection(int *, int *) { return false; }
int __attribute__((weak)) prime_g2_test_graph_tab() { return -1; }
float __attribute__((weak)) prime_g2_test_graph_range(unsigned) { return 0.f; }
const char * __attribute__((weak)) prime_g2_test_calculation_text(unsigned) { return nullptr; }
}

Ion::Events::Event prime_g2_last_event_for_test();
int prime_g2_repetition_count_for_test();
void prime_g2_reset_event_state_for_test();

namespace {
#if PRIME_G2_EMULATOR
Ion::Keyboard::State sKeyboardState;
Ion::Keyboard::Key sReleasedKey = Ion::Keyboard::Key::None;
uint64_t sReleaseAt = 0;
Ion::Events::Event sPendingEvent = Ion::Events::None;
char sExternalText[48];
char sLine[96];
unsigned sLineLength = 0;
bool sLineOverflow = false;
uint8_t sStorageTestData[Ion::InternalStorage::k_storageSize];
bool sControlReadyLogged = false;
char sReplyPrefix[24];
uint64_t sColdResetAt = 0;
uint64_t sFaultAt = 0;
unsigned sFaultKind = 0;
uint64_t sWatchdogHangAt = 0;
unsigned sWatchdogHangKind = 0;

void ensureHeapInitialized() {
  static bool initialized = false;
  if (!initialized) {
    void *probe = malloc(1);
    free(probe);
    initialized = true;
  }
}

void writeString(const char *text) {
  while (*text) {
    PrimeG2::UART::write(PrimeG2::UART3, *text++);
  }
}

void reply(const char * text) {
  writeString(sReplyPrefix);
  writeString(text);
  PrimeG2::UART::write(PrimeG2::UART3, '\n');
}

void replyData(const void * data, size_t size) {
  static constexpr char Hex[] = "0123456789abcdef";
  const uint8_t * bytes = static_cast<const uint8_t *>(data);
  writeString(sReplyPrefix);
  const char prefix[] = "DATA ";
  for (char c : prefix) {
    if (c != 0) {
      PrimeG2::UART::write(PrimeG2::UART3, c);
    }
  }
  for (size_t i = 0; i < size; i++) {
    PrimeG2::UART::write(PrimeG2::UART3, Hex[bytes[i] >> 4]);
    PrimeG2::UART::write(PrimeG2::UART3, Hex[bytes[i] & 0x0F]);
  }
  PrimeG2::UART::write(PrimeG2::UART3, '\n');
}

void replyText(const char *prefix, const char *text) {
  writeString(sReplyPrefix);
  writeString(prefix);
  writeString(text);
  PrimeG2::UART::write(PrimeG2::UART3, '\n');
}

void replyInteger(const char *prefix, int value) {
  char buffer[32];
  size_t length = 0;
  while (*prefix) {
    buffer[length++] = *prefix++;
  }
  if (value < 0) {
    buffer[length++] = '-';
    value = -value;
  }
  char digits[12];
  size_t digitCount = 0;
  do {
    digits[digitCount++] = '0' + value % 10;
    value /= 10;
  } while (value != 0);
  while (digitCount > 0) {
    buffer[length++] = digits[--digitCount];
  }
  buffer[length] = 0;
  reply(buffer);
}

bool takeWord(const char *& cursor, const char ** start, size_t * length) {
  while (*cursor == ' ') {
    cursor++;
  }
  *start = cursor;
  while (*cursor != 0 && *cursor != ' ') {
    cursor++;
  }
  *length = cursor - *start;
  return *length > 0;
}

int hexDigit(char c) {
  if (c >= '0' && c <= '9') {
    return c - '0';
  }
  if (c >= 'a' && c <= 'f') {
    return c - 'a' + 10;
  }
  if (c >= 'A' && c <= 'F') {
    return c - 'A' + 10;
  }
  return -1;
}

bool takeUnsigned(const char *& cursor, unsigned & value) {
  while (*cursor == ' ') {
    cursor++;
  }
  if (*cursor < '0' || *cursor > '9') {
    return false;
  }
  value = 0;
  while (*cursor >= '0' && *cursor <= '9') {
    value = value * 10 + (*cursor++ - '0');
  }
  return true;
}

void setReplyPrefix(unsigned requestID) {
  const char base[] = "V1 ";
  size_t length = 0;
  for (char c : base) {
    if (c != 0) {
      sReplyPrefix[length++] = c;
    }
  }
  char digits[12];
  size_t digitCount = 0;
  do {
    digits[digitCount++] = '0' + requestID % 10;
    requestID /= 10;
  } while (requestID != 0);
  while (digitCount > 0) {
    sReplyPrefix[length++] = digits[--digitCount];
  }
  sReplyPrefix[length++] = ' ';
  sReplyPrefix[length] = 0;
}

Ion::Keyboard::Key keyForEvdevCode(unsigned code) {
  using Key = Ion::Keyboard::Key;
  switch (code) {
#define PRIME_G2_KEY(name, evdev, ion, row, column) case evdev: return Key::ion;
#include "keymap.inc"
#undef PRIME_G2_KEY
    default: return Key::None;
  }
}

void resetInput() {
  sKeyboardState = Ion::Keyboard::State();
  sReleasedKey = Ion::Keyboard::Key::None;
  sReleaseAt = 0;
  sPendingEvent = Ion::Events::None;
  Ion::Events::setShiftAlphaStatus(Ion::Events::ShiftAlphaStatus::Default);
  prime_g2_reset_event_state_for_test();
}

[[noreturn]] void triggerFault(unsigned kind) {
  if (kind == 1) {
    __asm volatile(".word 0xe7f000f0");
  } else if (kind == 2) {
    __asm volatile("svc #0");
  } else if (kind == 3) {
    reinterpret_cast<void (*)()>(0xFFFFFFFC)();
  } else {
    (void)*reinterpret_cast<volatile uint32_t *>(0xFFFFFFFC);
  }
  while (true) __asm volatile("wfe");
}

void processLine() {
  const char * cursor = sLine;
  sReplyPrefix[0] = 0;
  if (strncmp(cursor, "V1 ", 3) == 0) {
    cursor += 3;
    unsigned requestID;
    if (!takeUnsigned(cursor, requestID)) {
      reply("ERR malformed envelope");
      return;
    }
    setReplyPrefix(requestID);
    while (*cursor == ' ') {
      cursor++;
    }
    if (*cursor == 0) {
      reply("ERR missing command");
      return;
    }
  }
  if (strcmp(cursor, "PING") == 0) {
    reply("PONG");
    return;
  }
  if (strncmp(cursor, "APP LOAD ", 9) == 0) {
    cursor += 9;
    unsigned size;
    if (!takeUnsigned(cursor,size) || *cursor || size>PrimeG2::NativeApp::MaximumPackage) {
      reply("ERR app size"); return;
    }
    reply(PrimeG2::NativeApp::load(reinterpret_cast<const uint8_t *>(PrimeG2::NativeApp::StagingAddress),size)?"OK":"ERR app package");
    return;
  }
  if(strcmp(cursor,"APP PROFILE VERSION")==0) {replyInteger("VALUE ",1);return;}
  if(strcmp(cursor,"APP PROFILE HEAP VERSION")==0) {replyInteger("VALUE ",1);return;}
  if(strcmp(cursor,"APP PROFILE HEAP SNAPSHOT")==0) {
    const auto &profile=PrimeG2::NativeApp::heapResourceProfile();
    replyData(&profile,sizeof(profile));return;
  }
  if(strncmp(cursor,"APP PROFILE HEAP ",17)==0) {
    cursor+=17;unsigned address;
    if(!takeUnsigned(cursor,address) || *cursor) {reply("ERR heap address");return;}
    reply(PrimeG2::NativeApp::configureHeapResourceProfile(address)?"OK":"ERR heap profile");return;
  }
  if(strncmp(cursor,"APP PROFILE ARM ",16)==0) {
    cursor+=16;uint8_t hash[32];
    if(strlen(cursor)!=64) {reply("ERR profile hash");return;}
    for(unsigned i=0;i<32;i++) {
      int high=hexDigit(cursor[2*i]),low=hexDigit(cursor[2*i+1]);
      if(high<0 || low<0) {reply("ERR profile hash");return;}
      hash[i]=(high<<4)|low;
    }
    reply(PrimeG2::NativeApp::armResourceProfile(hash)?"OK":"ERR app loaded");return;
  }
  if(strcmp(cursor,"APP PROFILE SNAPSHOT")==0) {
    const auto &profile=PrimeG2::NativeApp::resourceProfile();
    replyData(&profile,sizeof(profile));return;
  }
  if (strncmp(cursor, "APP DIAG ", 9) == 0) {
    cursor+=9; unsigned index;
    if (!takeUnsigned(cursor,index) || *cursor || index>21) { reply("ERR app diagnostic"); return; }
    replyInteger("VALUE ",PrimeG2::NativeApp::diagnostic(index)); return;
  }
  if (strcmp(cursor,"APP LAUNCH")==0) {
    reply(prime_g2_launch_native_app()?"OK":"ERR app launcher"); return;
  }
  if (strncmp(cursor,"APP OPEN ",9)==0) {
    cursor+=9;unsigned slot;
    if(!takeUnsigned(cursor,slot) || *cursor) { reply("ERR app slot");return; }
    reply(prime_g2_launch_installed_native_app(slot)?"OK":"ERR installed app launcher");return;
  }
  if (strncmp(cursor, "APP EVENT ", 10) == 0) {
    cursor += 10;
    unsigned event,first,second;
    if (!takeUnsigned(cursor,event) || !takeUnsigned(cursor,first) || !takeUnsigned(cursor,second) || *cursor) {
      reply("ERR app event"); return;
    }
    replyInteger("RESULT ",PrimeG2::NativeApp::invoke(event,first,second));
    return;
  }
  if (strcmp(cursor, "INFO") == 0) {
    reply("INFO protocol=1 firmware=1.1.2-native build=f36520e0 platform=prime_g2_vm storage=1");
    return;
  }
  if (strcmp(cursor, "STATE") == 0) {
    int app = prime_g2_test_active_app();
    int row = -1;
    int column = -1;
    prime_g2_test_home_selection(&row, &column);
    char state[64];
    const char *labels[] = {"STATE app=", " home_row=", " home_column="};
    int values[] = {app, row, column};
    size_t length = 0;
    for (unsigned i = 0; i < 3; i++) {
      const char *label = labels[i];
      while (*label) state[length++] = *label++;
      int value = values[i];
      if (value < 0) {
        state[length++] = '-';
        value = -value;
      }
      char digits[12];
      size_t count = 0;
      do {
        digits[count++] = '0' + value % 10;
        value /= 10;
      } while (value != 0);
      while (count > 0) state[length++] = digits[--count];
    }
    state[length] = 0;
    reply(state);
    return;
  }
  if (strncmp(cursor, "RESULT ", 7) == 0) {
    cursor += 7;
    unsigned kind = strcmp(cursor, "INPUT") == 0 ? 0 :
      strcmp(cursor, "EXACT") == 0 ? 1 :
      strcmp(cursor, "APPROX") == 0 ? 2 : 3;
    const char *text = prime_g2_test_calculation_text(kind);
    if (text == nullptr) {
      reply("ERR no calculation result");
    } else {
      replyText("TEXT ", text);
    }
    return;
  }
  if (strcmp(cursor, "TIME GET") == 0) {
    uint64_t value = Ion::Timing::millis();
    if (value > 0x7FFFFFFF) value = 0x7FFFFFFF;
    replyInteger("VALUE ", static_cast<int>(value));
    return;
  }
  if (strcmp(cursor, "TIME ROLLOVER SELFTEST") == 0) {
    reply(PrimeG2::Timing::rolloverSelfTest() ? "OK" : "ERR rollover");
    return;
  }
  if (strcmp(cursor, "MOD STATE") == 0) {
    replyInteger("VALUE ", static_cast<int>(Ion::Events::shiftAlphaStatus()));
    return;
  }
  if (strcmp(cursor, "EVENT LAST TEXT") == 0) {
    const char *text = prime_g2_last_event_for_test().text();
    replyText("TEXT ", text == nullptr ? "" : text);
    return;
  }
  if (strcmp(cursor, "EVENT LAST BYTE") == 0) {
    const char *text = prime_g2_last_event_for_test().text();
    replyInteger("VALUE ", text == nullptr || text[0] == 0 ? -1 :
      static_cast<unsigned char>(text[0]));
    return;
  }
  if (strcmp(cursor, "EVENT LAST") == 0) {
    replyInteger("VALUE ", prime_g2_last_event_for_test().id());
    return;
  }
  if (strcmp(cursor, "EVENT REPEAT") == 0) {
    replyInteger("VALUE ", prime_g2_repetition_count_for_test());
    return;
  }
  if (strcmp(cursor, "INPUT RESET") == 0) {
    resetInput();
    reply("OK");
    return;
  }
  if (strcmp(cursor, "RESET WARM") == 0) {
    resetInput();
    sPendingEvent = Ion::Events::Apps;
    reply("OK");
    return;
  }
  if (strcmp(cursor, "RESET COLD") == 0) {
    reply("OK");
    sColdResetAt = Ion::Timing::millis() + 20;
    return;
  }
  if (strncmp(cursor, "FAULT ", 6) == 0) {
    cursor += 6;
    sFaultKind = strcmp(cursor, "UNDEFINED") == 0 ? 1 :
      strcmp(cursor, "SVC") == 0 ? 2 :
      strcmp(cursor, "PREFETCH") == 0 ? 3 :
      strcmp(cursor, "DATA") == 0 ? 4 : 0;
    if (sFaultKind == 0) {
      reply("ERR invalid fault kind");
      return;
    }
    reply("OK");
    sFaultAt = Ion::Timing::millis() + 20;
    return;
  }
  if (strcmp(cursor, "KEYMAP DRAW") == 0) {
    Ion::Display::pushRectUniform(
      KDRect(0, 0, Ion::Display::Width, Ion::Display::Height), KDColorWhite);
#define PRIME_G2_KEY(name, evdev, ion, row, column) \
    if (row < 8 && column < 8) { \
      Ion::Display::pushRectUniform(KDRect(8 + column * 39, 8 + row * 28, 30, 20), \
        Ion::Keyboard::Key::ion == Ion::Keyboard::Key::Shift || \
        Ion::Keyboard::Key::ion == Ion::Keyboard::Key::Alpha ? KDColorOrange : KDColorBlue); \
    }
#include "keymap.inc"
#undef PRIME_G2_KEY
    Ion::Display::pushRectUniform(KDRect(282, 8, 30, 20), KDColorRed);
    reply("OK");
    return;
  }
  if (strcmp(cursor, "DISPLAY SELFTEST") == 0) {
    replyInteger("VALUE ", static_cast<int>(PrimeG2::Display::selfTest()));
    return;
  }
  if (strcmp(cursor, "DISPLAY GUARDS") == 0) {
    reply(PrimeG2::Display::guardsIntact() ? "OK" : "ERR framebuffer guard");
    return;
  }
  if (strcmp(cursor, "DISPLAY CRC") == 0) {
    replyInteger("VALUE ", static_cast<int>(PrimeG2::Display::checksum() & 0x7FFFFFFF));
    return;
  }
  if (strcmp(cursor, "DISPLAY PUBLISHES") == 0) {
    replyInteger("VALUE ", PrimeG2::Display::publishCount());
    return;
  }
  if (strcmp(cursor, "DISPLAY FRAMES") == 0) {
    replyInteger("VALUE ", PrimeG2::Display::presentedFrames());
    return;
  }
  if (strcmp(cursor, "DISPLAY REFRESH") == 0) {
    replyInteger("VALUE ", PrimeG2::Display::refreshMilliHz()); return;
  }
  if (strcmp(cursor, "DISPLAY TRIAL") == 0) {
    replyInteger("VALUE ", PrimeG2::Display::refreshTrialActive()); return;
  }
  if (strcmp(cursor, "DISPLAY TIMEOUTS") == 0) {
    replyInteger("VALUE ", PrimeG2::Display::presentationTimeouts());
    return;
  }
  if (strcmp(cursor, "DISPLAY PIXELS") == 0) {
    uint64_t pixels = PrimeG2::Display::publishedPixels();
    replyInteger("VALUE ", pixels > 0x7FFFFFFF ? 0x7FFFFFFF : static_cast<int>(pixels));
    return;
  }
  if (strcmp(cursor, "BRIGHTNESS GET") == 0) {
    replyInteger("VALUE ", Ion::Backlight::brightness());
    return;
  }
  if (strncmp(cursor, "BRIGHTNESS SET ", 15) == 0) {
    cursor += 15;
    unsigned brightness;
    if (!takeUnsigned(cursor, brightness) || brightness > Ion::Backlight::MaxBrightness) {
      reply("ERR invalid brightness");
      return;
    }
    Ion::Backlight::setBrightness(brightness);
    reply("OK");
    return;
  }
  if (strncmp(cursor, "BATTERY SET ", 12) == 0) {
    cursor += 12;
    unsigned level, millivolts, charging;
    if (!takeUnsigned(cursor, level) || !takeUnsigned(cursor, millivolts) ||
        !takeUnsigned(cursor, charging) || level > 3 || charging > 1 ||
        !PrimeG2::Services::setBatteryForTest(
          static_cast<Ion::Battery::Charge>(level), millivolts, charging)) {
      reply("ERR invalid battery state");
      return;
    }
    reply("OK");
    return;
  }
  if (strncmp(cursor, "BATTERY PF1550 SET ", 19) == 0) {
    cursor += 19;
    unsigned externalPower, chargerState, batterySenseState;
    if (!takeUnsigned(cursor, externalPower) ||
        !takeUnsigned(cursor, chargerState) ||
        !takeUnsigned(cursor, batterySenseState) || externalPower > 1 ||
        chargerState > 0x0F || batterySenseState > 0x07 ||
        !PrimeG2::Services::setChargerStateForTest(
          externalPower, chargerState, batterySenseState)) {
      reply("ERR invalid PF1550 charger state");
      return;
    }
    reply("OK");
    return;
  }
  if (strcmp(cursor, "BATTERY PF1550 READ FAIL") == 0) {
    if (!PrimeG2::Services::failBatteryRefreshForTest()) {
      reply("ERR unable to simulate PF1550 read failure");
      return;
    }
    reply("OK");
    return;
  }
  if (strcmp(cursor, "BATTERY LEVEL") == 0) {
    replyInteger("VALUE ", static_cast<int>(Ion::Battery::level()));
    return;
  }
  if (strcmp(cursor, "BATTERY VOLTAGE") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::batteryMillivolts());
    return;
  }
  if (strcmp(cursor, "BATTERY ADC RAW") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::batteryRawADC());
    return;
  }
  if (strcmp(cursor, "BATTERY CHARGING") == 0) {
    replyInteger("VALUE ", Ion::Battery::isCharging());
    return;
  }
  if (strcmp(cursor, "BATTERY EXTERNAL") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::externalPowerPresent());
    return;
  }
  if (strcmp(cursor, "BATTERY PRESENT") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::batteryPresent());
    return;
  }
  if (strcmp(cursor, "BATTERY FULL") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::batteryFull());
    return;
  }
  if (strcmp(cursor, "BATTERY FAULT") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::chargerFaultOrSuspended());
    return;
  }
  if (strcmp(cursor, "BATTERY CHARGER STATE") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::chargerState());
    return;
  }
  if (strcmp(cursor, "BATTERY SENSE STATE") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::batterySenseState());
    return;
  }
  if (strcmp(cursor, "BATTERY VBUS SENSE") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::vbusSense());
    return;
  }
  if (strcmp(cursor, "BATTERY TELEMETRY FRESH") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::batteryTelemetryFresh());
    return;
  }
  if (strcmp(cursor, "BATTERY PMIC AVAILABLE") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::pmicAvailable());
    return;
  }
  if (strcmp(cursor, "BATTERY CHARGER OPERATION") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::chargerOperation());
    return;
  }
  if (strcmp(cursor, "BATTERY CHARGER CONFIGURED") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::chargerConfigured());
    return;
  }
  if (strcmp(cursor, "BATTERY PERCENT") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::batteryPercent());
    return;
  }
  if (strcmp(cursor, "BATTERY CALIBRATED") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::batteryEstimateIsCalibrated());
    return;
  }
  if (strncmp(cursor, "RTC SET ", 8) == 0) {
    cursor += 8;
    unsigned year, month, day, hour, minute, second, weekday;
    if (!takeUnsigned(cursor, year) || !takeUnsigned(cursor, month) ||
        !takeUnsigned(cursor, day) || !takeUnsigned(cursor, hour) ||
        !takeUnsigned(cursor, minute) || !takeUnsigned(cursor, second) ||
        !takeUnsigned(cursor, weekday) ||
        !PrimeG2::Services::setRTCForTest({static_cast<int>(second),
          static_cast<int>(minute), static_cast<int>(hour),
          static_cast<int>(day), static_cast<int>(month),
          static_cast<int>(year), static_cast<int>(weekday)})) {
      reply("ERR invalid rtc value");
      return;
    }
    reply("OK");
    return;
  }
  if (strcmp(cursor, "RTC DATE") == 0) {
    Ion::RTC::DateTime value = Ion::RTC::dateTime();
    replyInteger("VALUE ", value.tm_year * 10000 + value.tm_mon * 100 + value.tm_mday);
    return;
  }
  if (strcmp(cursor, "RTC TIME") == 0) {
    Ion::RTC::DateTime value = Ion::RTC::dateTime();
    replyInteger("VALUE ", value.tm_hour * 10000 + value.tm_min * 100 + value.tm_sec);
    return;
  }
  if (strncmp(cursor, "LED SET ", 8) == 0) {
    cursor += 8;
    unsigned color;
    if (!takeUnsigned(cursor, color) || color > 0xFFFF) {
      reply("ERR invalid led color");
      return;
    }
    Ion::LED::setColor(KDColor::RGB16(color));
    reply("OK");
    return;
  }
  if (strncmp(cursor, "LED BLINK ", 10) == 0) {
    cursor += 10;
    unsigned period, duty;
    if (!takeUnsigned(cursor, period) || !takeUnsigned(cursor, duty) ||
        period > 60000 || duty > 100) {
      reply("ERR invalid led blink");
      return;
    }
    Ion::LED::setBlinking(period, duty / 100.0f);
    reply("OK");
    return;
  }
  if (strcmp(cursor, "LED COLOR") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::ledColor());
    return;
  }
  if (strcmp(cursor, "LED PERIOD") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::ledBlinkPeriod());
    return;
  }
  if (strcmp(cursor, "LED DUTY") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::ledBlinkDutyPercent());
    return;
  }
  if (strcmp(cursor, "POWER SUSPEND") == 0) {
    Ion::Power::suspend(false);
    reply("OK");
    return;
  }
  if (strcmp(cursor, "POWER RESUME") == 0) {
    reply(PrimeG2::Services::resumeForTest() ? "OK" : "ERR powered off");
    return;
  }
  if (strcmp(cursor, "POWER STATE") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::powerSuspended());
    return;
  }
  if (strcmp(cursor, "POWER COUNT") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::suspendCount());
    return;
  }
  if (strcmp(cursor, "POWER HARDWARE") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::powerHardwareState());
    return;
  }
  if (strcmp(cursor, "POWER PMIC") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::pmicPowerControl());
    return;
  }
  if (strcmp(cursor, "POWER PANEL") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::lcdSupplyControl());
    return;
  }
  if (strcmp(cursor, "POWER OFF") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::powerOffForTest());
    return;
  }
  if (strncmp(cursor, "POWER IDLE ADVANCE ", 19) == 0) {
    cursor += 19;
    unsigned duration;
    if (!takeUnsigned(cursor, duration) ||
        !PrimeG2::Services::advanceIdleForTest(duration)) {
      reply("ERR invalid idle delta");
    } else {
      reply("OK");
    }
    return;
  }
  if (strncmp(cursor, "POWER BUTTON ", 13) == 0) {
    cursor += 13;
    unsigned duration;
    if (!takeUnsigned(cursor, duration) ||
        !PrimeG2::Services::buttonForTest(duration)) {
      reply("ERR invalid power transition");
    } else {
      reply("OK");
    }
    return;
  }
  if (strcmp(cursor, "USB STATUS") == 0) {
    replyInteger("VALUE ", PrimeG2::USBDiagnostics::statusFlags());
    return;
  }
  if (strcmp(cursor, "TOUCH STATUS") == 0) {
    replyInteger("VALUE ", PrimeG2::Touch::available());
    return;
  }
  if (strcmp(cursor, "TOUCH PRODUCT") == 0) {
    replyInteger("VALUE ", PrimeG2::Touch::productId());
    return;
  }
  if (strcmp(cursor, "TOUCH X") == 0) {
    replyInteger("VALUE ", PrimeG2::Touch::lastX());
    return;
  }
  if (strcmp(cursor, "TOUCH Y") == 0) {
    replyInteger("VALUE ", PrimeG2::Touch::lastY());
    return;
  }
  if (strcmp(cursor, "TOUCH DURATION") == 0) {
    replyInteger("VALUE ", PrimeG2::Touch::lastDuration());
    return;
  }
  if (strcmp(cursor, "TOUCH SEQUENCE") == 0) {
    replyInteger("VALUE ", PrimeG2::Touch::sequence());
    return;
  }
  if (strcmp(cursor, "TOUCH CANCELLED") == 0) {
    replyInteger("VALUE ", PrimeG2::Touch::lastReportCancelled());
    return;
  }
  if (strcmp(cursor, "TOUCH REINIT") == 0) {
    replyInteger("VALUE ", PrimeG2::Touch::reinitializeForTest());
    return;
  }
  if (strncmp(cursor, "TOUCH FAULT ", 12) == 0) {
    cursor += 12;
    unsigned mode;
    reply(takeUnsigned(cursor, mode) && mode <= 3 &&
          PrimeG2::Touch::setFaultForTest(mode) ?
          "OK" : "ERR invalid touch fault");
    return;
  }
  if (strcmp(cursor, "STACK SAFE") == 0) {
    replyInteger("VALUE ", Ion::stackSafe());
    return;
  }
  if (strcmp(cursor, "STACK HIGHWATER") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::stackHighWaterBytes());
    return;
  }
  if (strcmp(cursor, "STACK CAPACITY") == 0) {
    replyInteger("VALUE ", PrimeG2::Services::stackCapacityBytes());
    return;
  }
  if (strcmp(cursor, "HEAP CAPACITY") == 0) {
    ensureHeapInitialized();
    replyInteger("VALUE ", prime_g2_heap_capacity());
    return;
  }
  if (strcmp(cursor, "HEAP CURRENT") == 0) {
    ensureHeapInitialized();
    replyInteger("VALUE ", prime_g2_heap_current());
    return;
  }
  if (strcmp(cursor, "HEAP HIGHWATER") == 0) {
    ensureHeapInitialized();
    replyInteger("VALUE ", prime_g2_heap_high_water());
    return;
  }
  if (strcmp(cursor, "HEAP ALLOCATIONS") == 0) {
    ensureHeapInitialized();
    replyInteger("VALUE ", prime_g2_heap_allocation_count());
    return;
  }
  if (strcmp(cursor, "HEAP SELFTEST") == 0) {
    ensureHeapInitialized();
    reply(prime_g2_heap_fragmentation_self_test() ? "OK" : "ERR heap fragmentation");
    return;
  }
  if (strcmp(cursor, "SYSTEM SELFTEST") == 0) {
    reply(PrimeG2::System::selfTest() ? "OK" : "ERR memory attributes");
    return;
  }
  if (strcmp(cursor, "SYSTEM CONTROL") == 0) {
    replyInteger("VALUE ", PrimeG2::System::controlRegister());
    return;
  }
  if (strncmp(cursor, "MEMORY SIZE ", 12) == 0) {
    cursor += 12;
    uint32_t size = strcmp(cursor, "CODE") == 0 ? PrimeG2::System::codeSize() :
      strcmp(cursor, "DATA") == 0 ? PrimeG2::System::dataSize() :
      strcmp(cursor, "HEAP") == 0 ? PrimeG2::System::heapSize() :
      strcmp(cursor, "STACK") == 0 ? PrimeG2::System::stackSize() :
      strcmp(cursor, "FRAMEBUFFER") == 0 ? PrimeG2::System::framebufferSize() : 0;
    if (size == 0) reply("ERR invalid memory region");
    else replyInteger("VALUE ", size);
    return;
  }
  if (strncmp(cursor, "SYSTEM TYPE ", 12) == 0) {
    cursor += 12;
    uintptr_t address = strcmp(cursor, "NULL") == 0 ? 0u :
      strcmp(cursor, "CODE") == 0 ? reinterpret_cast<uintptr_t>(&processLine) :
      strcmp(cursor, "DATA") == 0 ? reinterpret_cast<uintptr_t>(&sLine) :
      strcmp(cursor, "DEVICE") == 0 ? PrimeG2::UART1 :
      strcmp(cursor, "FRAMEBUFFER") == 0 ? 0x8F000000u : 0xFFFFFFFFu;
    if (address == 0xFFFFFFFFu) reply("ERR invalid region");
    else replyInteger("VALUE ", static_cast<int>(PrimeG2::System::memoryType(address)));
    return;
  }
  if (strcmp(cursor, "IRQ SELFTEST") == 0) {
    reply(PrimeG2::Interrupts::selfTest() ? "OK" : "ERR GIC");
    return;
  }
  if (strncmp(cursor, "IRQ COUNT ", 10) == 0) {
    cursor += 10;
    unsigned interrupt;
    if (!takeUnsigned(cursor, interrupt) || interrupt >= PrimeG2::Interrupts::Maximum)
      reply("ERR invalid interrupt");
    else replyInteger("VALUE ", PrimeG2::Interrupts::handledCount(interrupt));
    return;
  }
  if (strncmp(cursor, "IRQ INJECT ", 11) == 0) {
    cursor += 11;
    unsigned interrupt;
    if (!takeUnsigned(cursor, interrupt) || interrupt >= PrimeG2::Interrupts::Maximum)
      reply("ERR invalid interrupt");
    else {
      PrimeG2::Interrupts::setPending(interrupt);
      reply("OK");
    }
    return;
  }
  if (strcmp(cursor, "IRQ UNHANDLED") == 0) {
    replyInteger("VALUE ", PrimeG2::Interrupts::unhandledCount());
    return;
  }
  if (strcmp(cursor, "IRQ SPURIOUS") == 0) {
    replyInteger("VALUE ", PrimeG2::Interrupts::spuriousCount());
    return;
  }
  if (strcmp(cursor, "IRQ LATENCY") == 0) {
    replyInteger("VALUE ", PrimeG2::Interrupts::maximumLatencyMicroseconds());
    return;
  }
  if (strcmp(cursor, "TIMER IRQ TICKS") == 0) {
    uint64_t ticks = PrimeG2::Timing::interruptTicks();
    replyInteger("VALUE ", ticks > 0x7FFFFFFF ? 0x7FFFFFFF : static_cast<int>(ticks));
    return;
  }
  if (strcmp(cursor, "TIMER MISSED") == 0) {
    replyInteger("VALUE ", PrimeG2::Timing::missedDeadlines());
    return;
  }
  if (strcmp(cursor, "WATCHDOG STATUS") == 0) {
    replyInteger("VALUE ", PrimeG2::Watchdog::enabled());
    return;
  }
  if (strcmp(cursor, "WATCHDOG FEEDS") == 0) {
    replyInteger("VALUE ", PrimeG2::Watchdog::feedCount());
    return;
  }
  if (strcmp(cursor, "WATCHDOG PREVIOUS") == 0) {
    replyInteger("VALUE ", static_cast<int>(PrimeG2::Watchdog::previousResetReason()));
    return;
  }
  if (strncmp(cursor, "WATCHDOG HANG ", 14) == 0) {
    cursor += 14;
    sWatchdogHangKind = strcmp(cursor, "DEADLOCK") == 0 ? 1 :
      strcmp(cursor, "IRQ_STORM") == 0 ? 2 :
      strcmp(cursor, "INFINITE") == 0 ? 3 : 0;
    if (sWatchdogHangKind == 0) reply("ERR invalid hang kind");
    else {
      PrimeG2::Watchdog::ResetReason reason = sWatchdogHangKind == 1 ?
        PrimeG2::Watchdog::ResetReason::EventLoopDeadlock :
        sWatchdogHangKind == 2 ? PrimeG2::Watchdog::ResetReason::InterruptStorm :
        PrimeG2::Watchdog::ResetReason::DeliberateTest;
      PrimeG2::Watchdog::prepareForHang(reason);
      reply("OK");
      sWatchdogHangAt = Ion::Timing::millis() + 20;
    }
    return;
  }
  if (strncmp(cursor, "TEXT ", 5) == 0) {
    cursor += 5;
    size_t hexLength = strlen(cursor);
    if ((hexLength & 1) != 0 || hexLength == 0 ||
        hexLength >= 2 * sizeof(sExternalText)) {
      reply("ERR invalid text payload");
      return;
    }
    for (size_t i = 0; i < hexLength / 2; i++) {
      int high = hexDigit(cursor[2 * i]);
      int low = hexDigit(cursor[2 * i + 1]);
      if (high < 0 || low < 0) {
        reply("ERR invalid text payload");
        return;
      }
      sExternalText[i] = static_cast<char>((high << 4) | low);
      if (sExternalText[i] == 0) {
        reply("ERR invalid text payload");
        return;
      }
    }
    sExternalText[hexLength / 2] = 0;
    sPendingEvent = Ion::Events::ExternalText;
    reply("OK");
    return;
  }
  if (strncmp(cursor, "DATA SET ", 9) == 0) {
    cursor += 9;
    unsigned kind, series, column, row, value;
    if (!takeUnsigned(cursor, kind) || !takeUnsigned(cursor, series) ||
        !takeUnsigned(cursor, column) || !takeUnsigned(cursor, row) ||
        !takeUnsigned(cursor, value) || value > 0x7FFFFFFF ||
        !prime_g2_test_dataset_set(kind, series, column, row,
          static_cast<int>(value))) {
      reply("ERR invalid dataset value");
      return;
    }
    reply("OK");
    return;
  }
  if (strncmp(cursor, "DATA GET ", 9) == 0) {
    cursor += 9;
    unsigned kind, series, column, row;
    int value;
    if (!takeUnsigned(cursor, kind) || !takeUnsigned(cursor, series) ||
        !takeUnsigned(cursor, column) || !takeUnsigned(cursor, row) ||
        !prime_g2_test_dataset_get(kind, series, column, row, &value)) {
      reply("ERR dataset value unavailable");
      return;
    }
    replyInteger("VALUE ", value);
    return;
  }
  if (strncmp(cursor, "TIME ADVANCE ", 13) == 0) {
    cursor += 13;
    unsigned milliseconds;
    if (!takeUnsigned(cursor, milliseconds)) {
      reply("ERR invalid time delta");
      return;
    }
    PrimeG2::Timing::advanceForTest(milliseconds);
    PrimeG2::Services::advancePowerForTest(milliseconds);
    reply("OK");
    return;
  }
  if (strcmp(cursor, "STORAGE COMMIT") == 0) {
    reply(PrimeG2::Persistence::commit() ? "OK" : "ERR commit failed");
    return;
  }
  if (strcmp(cursor, "STORAGE CORRUPT ACTIVE") == 0) {
    reply(PrimeG2::Persistence::corruptActiveHeaderForTest() ?
      "OK" : "ERR corruption failed");
    return;
  }
  if (strcmp(cursor, "STORAGE RESET CONFIRM") == 0) {
    reply(PrimeG2::Persistence::factoryReset() ? "OK" : "ERR reset failed");
    return;
  }
  if (strcmp(cursor, "STORAGE RESET") == 0) {
    using Key = Ion::Keyboard::Key;
    Ion::Keyboard::State physicalState = Ion::Keyboard::scan();
    if (!physicalState.keyDown(Key::Shift) ||
        !physicalState.keyDown(Key::Alpha) ||
        !physicalState.keyDown(Key::Backspace)) {
      reply("ERR confirmation required");
      return;
    }
    bool result = PrimeG2::Persistence::factoryReset();
    resetInput();
    reply(result ? "OK" : "ERR reset failed");
    return;
  }
  if (strcmp(cursor, "STORAGE SELFTEST") == 0) {
    using Status = Ion::Storage::Record::ErrorStatus;
    Ion::Storage *storage = Ion::Storage::sharedStorage();
    Ion::Console::writeLine("Lefony storage self-test: begin");
    storage->destroyAllRecords();
    Status zero = storage->createRecordWithFullName("zero.bin", sStorageTestData, 0);
    Ion::Storage::Record zeroRecord = storage->recordNamed("zero.bin");
    Status duplicate = storage->createRecordWithFullName("zero.bin", sStorageTestData, 0);
    Ion::Console::writeLine("Lefony storage self-test: zero and duplicate complete");
    Status renamed = zeroRecord.setName("renamed.bin");
    bool renameWorked = storage->recordNamed("zero.bin").isNull() &&
      !storage->recordNamed("renamed.bin").isNull();
    storage->recordNamed("renamed.bin").destroy();
    bool deleteWorked = storage->recordNamed("renamed.bin").isNull();
    Ion::Console::writeLine("Lefony storage self-test: rename and delete complete");
    storage->destroyAllRecords();
    const char maximumName[] = "maximum.bin";
    size_t maximumDataSize = storage->availableSize() - sizeof(uint16_t) -
      sizeof(maximumName);
    Status maximum = storage->createRecordWithFullName(maximumName,
      sStorageTestData, maximumDataSize);
    Ion::Console::writeLine("Lefony storage self-test: maximum complete");
    Status full = storage->createRecordWithFullName("overflow.bin", sStorageTestData, 0);
    unsigned failures = 0;
    failures |= zero != Status::None ? 1u << 0 : 0;
    failures |= zeroRecord.isNull() ? 1u << 1 : 0;
    failures |= duplicate != Status::NameTaken ? 1u << 2 : 0;
    failures |= renamed != Status::None ? 1u << 3 : 0;
    failures |= !renameWorked ? 1u << 4 : 0;
    failures |= !deleteWorked ? 1u << 5 : 0;
    failures |= maximum != Status::None ? 1u << 6 : 0;
    failures |= full != Status::NotEnoughSpaceAvailable ? 1u << 7 : 0;
    failures |= storage->availableSize() != 0 ? 1u << 8 : 0;
    storage->destroyAllRecords();
    Ion::Console::writeLine("Lefony storage self-test: reset complete");
    prime_g2_preferences_factory_reset();
    if (failures == 0) {
      reply("OK");
    } else {
      replyInteger("VALUE ", static_cast<int>(failures));
    }
    return;
  }
  if (strncmp(cursor, "STORAGE INTERRUPT ", 18) == 0) {
    cursor += 18;
    unsigned phase;
    if (!takeUnsigned(cursor, phase)) {
      reply("ERR invalid phase");
      return;
    }
    reply(PrimeG2::Persistence::simulateInterruptedCommitForTest(phase) ?
      "OK" : "ERR interruption failed");
    return;
  }
  if (strncmp(cursor, "STORAGE COMPAT SET ", 19) == 0) {
    cursor += 19;
    unsigned index;
    unsigned value;
    if (!takeUnsigned(cursor, index) || !takeUnsigned(cursor, value) ||
        !PrimeG2::Persistence::setCompatibleFieldForTest(index, value)) {
      reply("ERR invalid compatible field");
      return;
    }
    reply("OK");
    return;
  }
  if (strncmp(cursor, "STORAGE COMPAT GET ", 19) == 0) {
    cursor += 19;
    unsigned index;
    uint32_t value;
    if (!takeUnsigned(cursor, index) ||
        !PrimeG2::Persistence::getCompatibleFieldForTest(index, &value) ||
        value > 0x7FFFFFFF) {
      reply("ERR invalid compatible field");
      return;
    }
    replyInteger("VALUE ", static_cast<int>(value));
    return;
  }
  if (strncmp(cursor, "PREF GET ", 9) == 0) {
    int value = prime_g2_preferences_get_for_test(cursor + 9);
    if (value < 0) {
      reply("ERR unknown preference");
    } else {
      replyInteger("VALUE ", value);
    }
    return;
  }
  if (strncmp(cursor, "PREF SET ", 9) == 0) {
    cursor += 9;
    const char *nameStart;
    size_t nameLength;
    if (!takeWord(cursor, &nameStart, &nameLength) || nameLength >= 16) {
      reply("ERR invalid preference");
      return;
    }
    unsigned value;
    if (!takeUnsigned(cursor, value)) {
      reply("ERR invalid preference value");
      return;
    }
    char name[16];
    memcpy(name, nameStart, nameLength);
    name[nameLength] = 0;
    reply(prime_g2_preferences_set_for_test(name, value) ?
      "OK" : "ERR invalid preference");
    return;
  }
  if (strncmp(cursor, "STORAGE PUT ", 12) == 0) {
    cursor += 12;
    const char * nameStart;
    size_t nameLength;
    if (!takeWord(cursor, &nameStart, &nameLength) || nameLength >= 32) {
      reply("ERR invalid name");
      return;
    }
    while (*cursor == ' ') {
      cursor++;
    }
    size_t hexLength = strlen(cursor);
    if ((hexLength & 1) != 0 || hexLength > 16) {
      reply("ERR invalid data");
      return;
    }
    char name[32];
    memcpy(name, nameStart, nameLength);
    name[nameLength] = 0;
    uint8_t data[8];
    for (size_t i = 0; i < hexLength / 2; i++) {
      int high = hexDigit(cursor[2 * i]);
      int low = hexDigit(cursor[2 * i + 1]);
      if (high < 0 || low < 0) {
        reply("ERR invalid data");
        return;
      }
      data[i] = (high << 4) | low;
    }
    Ion::Storage * storage = Ion::Storage::sharedStorage();
    Ion::Storage::Record record = storage->recordNamed(name);
    Ion::Storage::Record::ErrorStatus result;
    if (record.isNull()) {
      result = storage->createRecordWithFullName(name, data, hexLength / 2);
    } else {
      result = record.setValue({data, hexLength / 2});
    }
    reply(result == Ion::Storage::Record::ErrorStatus::None ? "OK" : "ERR storage rejected record");
    return;
  }
  if (strncmp(cursor, "STORAGE GET ", 12) == 0) {
    cursor += 12;
    Ion::Storage::Record record = Ion::Storage::sharedStorage()->recordNamed(cursor);
    if (record.isNull()) {
      reply("ERR not found");
      return;
    }
    Ion::Storage::Record::Data data = record.value();
    if (data.size > 8) {
      reply("ERR data too large for bridge");
      return;
    }
    replyData(data.buffer, data.size);
    return;
  }
  if (strncmp(cursor, "STORAGE VALIDATE ", 17) == 0) {
    cursor += 17;
    size_t hexLength = strlen(cursor);
    if ((hexLength & 1) != 0 || hexLength > 64) {
      reply("ERR invalid test payload");
      return;
    }
    uint8_t data[32];
    for (size_t i = 0; i < hexLength / 2; i++) {
      int high = hexDigit(cursor[2 * i]);
      int low = hexDigit(cursor[2 * i + 1]);
      if (high < 0 || low < 0) {
        reply("ERR invalid test payload");
        return;
      }
      data[i] = (high << 4) | low;
    }
    reply(PrimeG2::Persistence::validatePayloadForTest(data, hexLength / 2) ?
      "VALID" : "INVALID");
    return;
  }
  if (strncmp(cursor, "PRESS ", 6) == 0) {
    cursor += 6;
    unsigned code;
    if (!takeUnsigned(cursor, code)) {
      reply("ERR invalid key");
      return;
    }
    unsigned duration = 100;
    const char *durationCursor = cursor;
    while (*durationCursor == ' ') {
      durationCursor++;
    }
    if (*durationCursor != 0 &&
        (!takeUnsigned(cursor, duration) || duration == 0 || duration > 60000)) {
      reply("ERR invalid press duration");
      return;
    }
    Ion::Keyboard::Key key = keyForEvdevCode(code);
    if (key == Ion::Keyboard::Key::None) {
      reply("ERR unknown key");
      return;
    }
    if (sReleasedKey != Ion::Keyboard::Key::None) {
      sKeyboardState.clearKey(sReleasedKey);
    }
    sKeyboardState.setKey(key);
    sReleasedKey = key;
    sReleaseAt = Ion::Timing::millis() + duration;
    PrimeG2::Services::noteUserActivity();
    reply("OK");
    return;
  }
  if (strncmp(cursor, "KEY ", 4) == 0 &&
      strncmp(cursor, "KEY STATE ", 10) != 0) {
    cursor += 4;
    unsigned code;
    unsigned pressed;
    if (!takeUnsigned(cursor, code) || !takeUnsigned(cursor, pressed)) {
      reply("ERR invalid key state");
      return;
    }
    Ion::Keyboard::Key key = keyForEvdevCode(code);
    if (key == Ion::Keyboard::Key::None) {
      reply("ERR unknown key");
      return;
    }
    if (pressed) {
      sKeyboardState.setKey(key);
      PrimeG2::Services::noteUserActivity();
    } else {
      sKeyboardState.clearKey(key);
    }
    reply("OK");
    return;
  }
  if (strncmp(cursor, "KEY STATE ", 10) == 0) {
    cursor += 10;
    unsigned code;
    if (!takeUnsigned(cursor, code)) {
      reply("ERR invalid key");
      return;
    }
    Ion::Keyboard::Key key = keyForEvdevCode(code);
    if (key == Ion::Keyboard::Key::None) {
      reply("ERR unknown key");
      return;
    }
    replyInteger("VALUE ", sKeyboardState.keyDown(key));
    return;
  }
  if (strcmp(cursor, "GRAPH TAB") == 0 && prime_g2_test_active_app() == 2) {
    replyInteger("VALUE ", prime_g2_test_graph_tab());
    return;
  }
  if (strncmp(cursor, "GRAPH RANGE ", 12) == 0 && prime_g2_test_active_app() == 2) {
    cursor += 12;
    unsigned index;
    if (!takeUnsigned(cursor, index) || index > 3) { reply("ERR invalid axis"); return; }
    float value = prime_g2_test_graph_range(index);
    replyData(&value, sizeof(value));
    return;
  }
  if (strncmp(cursor, "TOUCH FRAME ", 12) == 0) {
    cursor += 12;
    unsigned count;
    if (!takeUnsigned(cursor, count) || count > 3) { reply("ERR invalid contacts"); return; }
    uint8_t report[17] = {};
    report[0] = 0x80 | count;
    for (unsigned i = 0; i < count && i < 2; i++) {
      unsigned id, x, y;
      if (!takeUnsigned(cursor, id) || !takeUnsigned(cursor, x) || !takeUnsigned(cursor, y) ||
          id > 15 || x > 65535 || y > 65535) { reply("ERR invalid contact"); return; }
      report[1 + 8*i] = id;
      report[2 + 8*i] = x; report[3 + 8*i] = x >> 8;
      report[4 + 8*i] = y; report[5 + 8*i] = y >> 8;
    }
    reply(PrimeG2::Touch::injectFrameForTest(report) ? "OK" : "ERR touch injection failed");
    return;
  }
  if (strncmp(cursor, "TAP ", 4) == 0) {
    cursor += 4;
    unsigned x;
    unsigned y;
    if (!takeUnsigned(cursor, x) || !takeUnsigned(cursor, y) ||
        x > 0xFFFF || y > 0xFFFF) {
      reply("ERR invalid tap");
      return;
    }
    bool injected = PrimeG2::Touch::injectForTest(x, y, x, y);
    if (injected) PrimeG2::Services::noteUserActivity();
    reply(injected ? "OK" : "ERR touch injection failed");
    return;
  }
  if (strncmp(cursor, "SWIPE ", 6) == 0) {
    cursor += 6;
    unsigned x1, y1, x2, y2;
    if (!takeUnsigned(cursor, x1) || !takeUnsigned(cursor, y1) ||
        !takeUnsigned(cursor, x2) || !takeUnsigned(cursor, y2) ||
        x1 > 0xFFFF || y1 > 0xFFFF || x2 > 0xFFFF || y2 > 0xFFFF) {
      reply("ERR invalid swipe");
      return;
    }
    bool injected = PrimeG2::Touch::injectForTest(x1, y1, x2, y2);
    if (injected) PrimeG2::Services::noteUserActivity();
    reply(injected ? "OK" : "ERR touch injection failed");
    return;
  }
  if (strncmp(cursor, "HOLD ", 5) == 0) {
    cursor += 5;
    unsigned x, y, duration;
    if (!takeUnsigned(cursor, x) || !takeUnsigned(cursor, y) ||
        !takeUnsigned(cursor, duration) || x > 0xFFFF || y > 0xFFFF ||
        duration < 1 || duration > 60000) {
      reply("ERR invalid hold");
      return;
    }
    bool injected = PrimeG2::Touch::injectForTest(x, y, x, y, duration);
    if (injected) PrimeG2::Services::noteUserActivity();
    reply(injected ? "OK" : "ERR touch injection failed");
    return;
  }
  reply("ERR unknown command");
}
#endif
}

namespace PrimeG2 {
namespace Emulator {

void init() {
#if PRIME_G2_EMULATOR
  UART::init(UART3, 0x6C, 10);
#endif
}

void poll() {
#if PRIME_G2_EMULATOR
  if (sWatchdogHangAt != 0 && Ion::Timing::millis() >= sWatchdogHangAt) {
    if (sWatchdogHangKind == 1) {
      while (true) __asm volatile("wfi");
    } else if (sWatchdogHangKind == 2) {
      while (true) PrimeG2::Interrupts::setPending(PrimeG2::Interrupts::KPP);
    } else {
      while (true) __asm volatile("nop");
    }
  }
  if (sFaultAt != 0 && Ion::Timing::millis() >= sFaultAt) {
    triggerFault(sFaultKind);
  }
  if (sColdResetAt != 0 && Ion::Timing::millis() >= sColdResetAt) {
    /* WDOG1 timeout=minimum, watchdog enabled. With -no-reboot this exits the
     * current VM, exactly like pulling power and cold-starting it again. */
    PrimeG2::reg16(PrimeG2::WDOG1) = 1u << 2;
    PrimeG2::barrier();
    while (true) {
      __asm volatile("wfi");
    }
  }
  if (sReleasedKey != Ion::Keyboard::Key::None &&
      Ion::Timing::millis() >= sReleaseAt) {
    sKeyboardState.clearKey(sReleasedKey);
    sReleasedKey = Ion::Keyboard::Key::None;
  }
  while (UART::available(UART3)) {
    char c = static_cast<char>(UART::read(UART3));
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      if (sLineOverflow) {
        sReplyPrefix[0] = 0;
        reply("ERR line too long");
      } else {
        sLine[sLineLength] = 0;
        processLine();
      }
      sLineLength = 0;
      sLineOverflow = false;
    } else if (sLineOverflow) {
      continue;
    } else if (sLineLength + 1 < sizeof(sLine)) {
      sLine[sLineLength++] = c;
    } else {
      sLineLength = 0;
      sLineOverflow = true;
    }
  }
  prime_g2_preferences_sync();
  prime_g2_datasets_sync();
  Persistence::poll();
  if (!sControlReadyLogged) {
    Ion::Console::writeLine("Lefony OS: control ready");
    sControlReadyLogged = true;
  }
#endif
}

Ion::Keyboard::State keyboardState() {
#if PRIME_G2_EMULATOR
  return sKeyboardState;
#else
  return Ion::Keyboard::State();
#endif
}

Ion::Events::Event popEvent() {
#if PRIME_G2_EMULATOR
  Ion::Events::Event result = sPendingEvent;
  sPendingEvent = Ion::Events::None;
  return result;
#else
  return Ion::Events::None;
#endif
}

const char *eventText() {
#if PRIME_G2_EMULATOR
  return sExternalText;
#else
  return nullptr;
#endif
}

}
}
