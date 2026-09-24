/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#ifndef LEFONY_SYSTEM_WIRE_H
#define LEFONY_SYSTEM_WIRE_H
#include <stdint.h>
#define LEFONY_SYSTEM_SERVICE 16u
#define LEFONY_SYSTEM_CAPABILITY 2048u
#define LEFONY_SYSTEM_API 10u
#define LEFONY_CLIPBOARD_MAXIMUM 219u
#define LEFONY_CLIPBOARD_GESTURE_MILLIS 2000u
#define LEFONY_SYSTEM_UNKNOWN 0xffffffffu
#define LEFONY_UTC_OFFSET_UNKNOWN (-2147483647-1)
enum LefonySystemOperation {
  LEFONY_SYSTEM_INFO=1, LEFONY_SYSTEM_BRIGHTNESS=2, LEFONY_SYSTEM_RESTORE_BRIGHTNESS=3,
  LEFONY_SYSTEM_CLIPBOARD_READ=4, LEFONY_SYSTEM_CLIPBOARD_WRITE=5
};
enum LefonySystemError {
  LEFONY_SYSTEM_UNSUPPORTED=3, LEFONY_SYSTEM_INVALID=4, LEFONY_SYSTEM_DENIED=5,
  LEFONY_SYSTEM_TOO_SMALL=6, LEFONY_SYSTEM_TEXT=7
};
enum LefonyClockFlag { LEFONY_CLOCK_READABLE=1, LEFONY_CLOCK_SET_THIS_BOOT=2 };
enum LefonyBatteryFlag {
  LEFONY_BATTERY_STATE_FRESH=1, LEFONY_BATTERY_PRESENT=2, LEFONY_BATTERY_EXTERNAL_POWER=4,
  LEFONY_BATTERY_CHARGING=8, LEFONY_BATTERY_FULL=16, LEFONY_BATTERY_FAULT=32,
  LEFONY_BATTERY_ESTIMATE_FRESH=64
};
enum LefonyClipboardAction { LEFONY_CLIPBOARD_NONE=0, LEFONY_CLIPBOARD_COPY=1,
  LEFONY_CLIPBOARD_PASTE=2, LEFONY_CLIPBOARD_CUT=3 };
enum LefonySystemColor {
  LEFONY_COLOR_TEXT=0, LEFONY_COLOR_SECONDARY_TEXT=1, LEFONY_COLOR_BACKGROUND=2,
  LEFONY_COLOR_APP_BACKGROUND=3, LEFONY_COLOR_ACCENT=4, LEFONY_COLOR_DISABLED=5,
  LEFONY_COLOR_SELECTION=6, LEFONY_COLOR_ERROR=7
};
/* Fixed copied snapshot. Calendar is local civil time, Monday=0, no timezone
 * assumption. SET_THIS_BOOT records explicit OS setting, not external accuracy.
 * Unknown battery values are UINT32_MAX. Colors are RGB565. Math preferences:
 * angle degree/radian/gradian=0/1/2; display decimal/scientific/engineering=0/1/2;
 * complex real/cartesian/polar=0/1/2; editor 2D/1D=0/1; units metric/imperial=0/1.
 * language is a NUL-terminated ISO 639-1 code, or empty when unavailable. */
typedef struct {
  uint32_t size,schema,monotonicLow,monotonicHigh,clockFlags;
  uint32_t year,month,day,hour,minute,second,weekday;
  int32_t utcOffsetMinutes;
  uint32_t batteryFlags,batteryPercent,batteryMillivolts,batteryEstimateAgeMillis;
  uint32_t brightness,actualBrightness,maximumBrightness,colors[8];
  uint32_t angleUnit,displayMode,complexFormat,editionMode,significantDigits,unitFormat;
  char language[4];
  uint32_t clipboardSequence,clipboardAction,clipboardMaximum,reserved[2];
} LefonySystemInfo;
/* All flags/reserved/outputs must be zero on input. INFO requires a separate
 * writable sizeof(LefonySystemInfo) buffer. Clipboard READ capacity includes
 * the NUL; WRITE capacity is input bytes excluding NUL. Neither truncates.
 * Sequence must match the current one-use Copy/Cut(write) or Paste(read) grant.
 * Negative errors preserve the request and output buffer. */
typedef struct {
  uint32_t size,schema,operation,flags,value,sequence,buffer,capacity,transferred,reserved[3];
} LefonySystemRequest;
#ifdef __cplusplus
static_assert(sizeof(LefonySystemInfo)==160,"system info wire size");
static_assert(sizeof(LefonySystemRequest)==48,"system request wire size");
#else
_Static_assert(sizeof(LefonySystemInfo)==160,"system info wire size");
_Static_assert(sizeof(LefonySystemRequest)==48,"system request wire size");
#endif
#endif
