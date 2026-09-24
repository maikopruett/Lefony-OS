# System services candidate

Include `lefony/system.h` from C11 or C++17. Service 16 uses API 10 and capability
2048. Required use declares `minimum_api: 10` and adds 2048 to
`required_capabilities`; optional use adds it to `optional_capabilities` and
handles older firmware's `-3`. ABI 1 and the package/storage formats are unchanged.
This is a local implementation candidate. Its validation is recorded in the
[SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md), separately from downloads.
Maintainer qualification uses `dist/lefony-os-prime-g2-system-vm.elf`; supply that
matching candidate explicitly with the SDK test command's `--firmware` option.
The standard dist filenames may still contain the earlier recovery candidate.

```c
#include <lefony/system.h>
LefonySystemInfo info;
if (lefony_system_info(&info) == 0) {
  uint64_t elapsed_ms = lefony_system_millis(&info);
  /* Use calendar and battery values only with their validity flags. */
  (void)elapsed_ms;
}
```

## Snapshot and validity

`lefony_system_info` copies a 160-byte snapshot. No OS pointer or writable
preference object is returned. The 64-bit monotonic millisecond clock is separate
from the calendar; setting the OS date backward does not reset elapsed time.
Calendar fields are local civil time, with months 1–12 and Monday=0 weekdays.
`LEFONY_CLOCK_READABLE` means a stable calendar read passed field validation.
`LEFONY_CLOCK_SET_THIS_BOOT` means the OS explicitly accepted a representable
calendar setting this boot. It does not establish external accuracy. Startup
defaults and retained values after cold boot have no trust marker. The SDK does
not assume UTC: `utcOffsetMinutes` is `LEFONY_UTC_OFFSET_UNKNOWN`. A clock hidden
in the title bar can still be readable.

Battery flags distinguish fresh charger/battery-presence telemetry, external
power, charging, full, fault/suspension and a fresh voltage estimate. Percent and
millivolts are `LEFONY_SYSTEM_UNKNOWN` unless both fresh state and a present
battery's averaged voltage estimate (at most 2000 ms old) are available. Percent
is the existing coarse 0/25/50/75/100 voltage estimate; it is not a calibrated
remaining-capacity measurement. Age is milliseconds since the last valid
averaged estimate, or unknown. No PMIC or ADC register is exposed.

The snapshot copies eight RGB565 OS palette colors, the two-letter ISO 639-1
language code, and read-only angle, display, complex-number, editor, significant
digit and unit preferences. Numeric enum meanings are in `system_wire.h`.
These preferences do not change the behavior of app-linked math automatically.
Apps must implement a selected mode or report it unsupported.

## Temporary brightness

`lefony_brightness(value)` accepts 0 through `maximumBrightness` (currently 240)
while foreground. It updates the OS preference and driver so normal keyboard
activity retains the requested value. `actualBrightness` can differ during OS
dimming; apps do not acquire control of the idle/power policy.

The first request remembers the current preference. Further requests keep that
original until `lefony_restore_brightness`, normal program exit, Home/focus loss,
fault, forced close or unload. Restoration applies only while the current
preference still equals the app's last setting. A later OS preference change
wins; a subsequent app request captures that newer value as its restore target.
Brightness requests are temporary and never persist an app preference in firmware.

## User-initiated clipboard

The clipboard is the existing calculator clipboard. API 10 apps use Shift+View
for Copy, Shift+Menu for Paste, and Shift+OK for Cut. The Cut shortcut applies
only to foreground apps declaring capability 2048; all other apps retain their
existing Shift+OK semantics. Input snapshots add logical keys Copy=54, Paste=55
and Cut=56. C apps can obtain the current gesture/action from the system snapshot.

A Copy/Cut gesture grants one write; Paste grants one read. Pass its exact input
sequence to `lefony_clipboard_write` or `lefony_clipboard_read`. A grant expires
after 2000 ms, is consumed on success and is revoked by the next ordinary key or
touch event, focus loss or termination. Timer callbacks and foreground resumes
do not consume it. Merely declaring the capability or querying system info does
not grant access. Invalid calls do not consume a still-live grant.

The maximum is 219 UTF-8 bytes. Writes pass a byte count excluding the NUL;
reads pass a capacity including the NUL and return the payload byte count.
Reads and writes never truncate. Empty writes clear the clipboard. Valid Unicode
scalars, tab and newline are supported; other C0/C1 controls, DEL, embedded NUL,
surrogates and malformed UTF-8 are rejected. OS math-layout placeholders are not
plain text and return a text error. Font support is a separate typography limit.
A read snapshots the stored bytes without modifying the OS clipboard.

## Errors and ownership

| Result | Meaning |
| --- | --- |
| 0 | Successful request; the read helper instead returns payload bytes |
| -3 | Service unavailable on older firmware |
| -4 | Invalid request, reserved field, brightness, pointer, overlap or length |
| -5 | Undeclared capability, no foreground, wrong/expired/consumed gesture |
| -6 | Clipboard read buffer too small; output is unchanged |
| -7 | Clipboard contains text outside the supported plain-text format |

Raw requests are 48 bytes, schema 1, with flags/reserved/output fields zero on
input. The complete request and payload ranges are checked before accessing OS
services. Payloads cannot overlap the request. A failed request leaves the
request and destination bytes unchanged. No pointer is retained after return.

The SDK cannot set the wall clock, timezone, language, exam mode or persistent
OS preferences through this service. Physical battery accuracy, PWM behavior,
input feel and timekeeping require separate hardware qualification.
