// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_system.h"
#include "services.h"
#include <ion/backlight.h>
#include <ion/timing.h>
#include <string.h>
namespace PrimeG2 { namespace AppSystem {
namespace { Session sSession; }
void finish() {
  sSession.revoke();
  uint32_t current=prime_app_system_brightness();
  uint32_t next=sSession.restoreBrightness(current);
  if(next!=current) prime_app_system_set_brightness(next);
}
void input(uint32_t event,uint32_t key,uint32_t sequence) {
  uint32_t action=key==54?LEFONY_CLIPBOARD_COPY:key==55?LEFONY_CLIPBOARD_PASTE:key==56?LEFONY_CLIPBOARD_CUT:LEFONY_CLIPBOARD_NONE;
  sSession.input(event,action,sequence,Ion::Timing::millis());
}
int request(LefonySystemRequest &r,void *buffer,bool foreground) {
  if(!validRequest(r)) return -LEFONY_SYSTEM_INVALID;
  if(r.operation==LEFONY_SYSTEM_INFO) {
    LefonySystemInfo info={};info.size=sizeof(info);info.schema=1;
    uint64_t now=Ion::Timing::millis();info.monotonicLow=now;info.monotonicHigh=now>>32;
    info.utcOffsetMinutes=LEFONY_UTC_OFFSET_UNKNOWN;
    Ion::RTC::DateTime date;bool set=false;
    if(Services::calendarSnapshot(&date,&set)) {
      info.clockFlags=LEFONY_CLOCK_READABLE|(set?LEFONY_CLOCK_SET_THIS_BOOT:0);
      info.year=date.tm_year;info.month=date.tm_mon;info.day=date.tm_mday;
      info.hour=date.tm_hour;info.minute=date.tm_min;info.second=date.tm_sec;info.weekday=date.tm_wday;
    }
    info.batteryPercent=info.batteryMillivolts=LEFONY_SYSTEM_UNKNOWN;
    info.batteryEstimateAgeMillis=Services::batteryEstimateAgeMillis();
    if(Services::batteryTelemetryFresh()) {
      info.batteryFlags=LEFONY_BATTERY_STATE_FRESH;
      if(Services::batteryPresent()) info.batteryFlags|=LEFONY_BATTERY_PRESENT;
      if(Services::externalPowerPresent()) info.batteryFlags|=LEFONY_BATTERY_EXTERNAL_POWER;
      if(Ion::Battery::isCharging()) info.batteryFlags|=LEFONY_BATTERY_CHARGING;
      if(Services::batteryFull()) info.batteryFlags|=LEFONY_BATTERY_FULL;
      if(Services::chargerFaultOrSuspended()) info.batteryFlags|=LEFONY_BATTERY_FAULT;
      if(Services::batteryPresent() && info.batteryEstimateAgeMillis<=2000) {
        info.batteryFlags|=LEFONY_BATTERY_ESTIMATE_FRESH;
        info.batteryPercent=Services::batteryPercent();info.batteryMillivolts=Services::batteryMillivolts();
      }
    }
    info.brightness=prime_app_system_brightness();info.actualBrightness=Ion::Backlight::brightness();
    info.maximumBrightness=Ion::Backlight::MaxBrightness;
    prime_app_system_preferences(&info);
    info.clipboardMaximum=LEFONY_CLIPBOARD_MAXIMUM;
    if(foreground) {info.clipboardSequence=sSession.sequence(now);info.clipboardAction=sSession.action(now);}
    memcpy(buffer,&info,sizeof(info));r.transferred=sizeof(info);return 0;
  }
  if(!foreground) return -LEFONY_SYSTEM_DENIED;
  if(r.operation==LEFONY_SYSTEM_BRIGHTNESS) {
    if(r.value>Ion::Backlight::MaxBrightness) return -LEFONY_SYSTEM_INVALID;
    sSession.brightness(prime_app_system_brightness(),r.value);prime_app_system_set_brightness(r.value);return 0;
  }
  if(r.operation==LEFONY_SYSTEM_RESTORE_BRIGHTNESS) {
    uint32_t current=prime_app_system_brightness(),next=sSession.restoreBrightness(current);
    if(next!=current) prime_app_system_set_brightness(next);
    return 0;
  }
  const bool write=r.operation==LEFONY_SYSTEM_CLIPBOARD_WRITE;
  if(!sSession.permits(write,r.sequence,Ion::Timing::millis())) return -LEFONY_SYSTEM_DENIED;
  char text[LEFONY_CLIPBOARD_MAXIMUM+1];uint32_t length=r.capacity;
  if(write) {
    if(length) memcpy(text,buffer,length);
    text[length]=0;
  } else {
    int result=prime_app_system_clipboard_read(text,sizeof(text));
    if(result<0 || result>int(LEFONY_CLIPBOARD_MAXIMUM)) return -LEFONY_SYSTEM_TEXT;
    length=static_cast<uint32_t>(result);
  }
  if(!validClipboard(text,length)) return -LEFONY_SYSTEM_TEXT;
  if(!write && length>=r.capacity) return -LEFONY_SYSTEM_TOO_SMALL;
  if(write) prime_app_system_clipboard_write(text,length);
  else memcpy(buffer,text,length+1);
  sSession.revoke();r.transferred=length;return 0;
}
}}
