# Brightness policy and experimental physical LCD refresh selection

Installer candidate: `260909-063048-2889ea`.
Capsule SHA-256: `2dae72f9cf9308d4420db863b7d59c42fa8d101e668aceac596a250f5a503f35`.
No physical installation or refresh-mode change was performed in this task.
The connected calculator was queried read-only over USB. U-Boot, NAND layout,
and the proven default boot timing are unchanged.

## Brightness

The USB page's 300 ms timer previously forced `Ion::Backlight::MaxBrightness`
whenever external power was connected, including after dismissing the page.
That undid the user's Settings preference. It now restores the selected
brightness, not maximum. The app dimming timer skips external power as well
as active updates, so USB keep-awake no longer depends on repeatedly fighting
the dimming animation. Touch also interrupts battery-powered dimming.

The existing slider's Left/Right and +/- controls remain. In the actual
emulated Settings UI, six Left presses selected value 144; PWM7's sample
became 33882 and stayed there over subsequent USB page timer firings. A second
preference value of 170 produced sample 40000. These are driver register and
emulator observations, not a physical luminance measurement.

## Physical refresh-rate selection

Settings > Brightness settings > LCD refresh rate offers:

- **58.9 Hz (default)**: unchanged PLL2 / 6 / 5 = 17.6 MHz pixel clock.
- **Test 55.2 Hz (experimental)**: PLL2 / 8 / 4 = 16.5 MHz pixel clock.

With 1132 serial RGB clocks per line and 264 lines per frame, these are
58.892815 Hz and 55.212014 Hz. This changes actual LCDIF clock dividers, not
the UI render frequency or a frame-rate cap. Active resolution, horizontal
and vertical porches, polarity, VCOM/gamma, the shared PLL, and PWM/PERCLK
remain unchanged. The lower rate is not yet physically panel-qualified.

The [ILI9322 v1.12 datasheet](https://www.df.lth.se/~triad/krad/dlink-dir-685/ILI9322DS_V1.12.pdf),
especially the serial RGB timing tables on page 24, was reviewed visually.
Those tables give typical configurations and setup/hold constraints, **not
a supported variable-refresh range for the Prime's particular panel module**.
The proven board timing comes from the pinned Prinux device tree. This review
is why the existing mode is preserved, higher rates are not offered, and the
lower divider combination is explicitly a reversible experiment rather than
advertised as a validated panel capability. Lowering the clock alone is not
proof of optical correctness or battery savings.

For a mode change the driver hides the backlight, puts ILI9322 into standby
while sync is still active, stops LCDIF, changes only its dividers, reconstructs
the controller, exits standby, presents the retained image, and reveals the
backlight. Existing bounded buffer-ownership checks remain in force.

A 55.2 Hz trial requires confirmation within 15 seconds measured by the
platform elapsed clock. Its rollback is polled by the platform event path,
not the settings page timer. Cancel or closing/replacing the page restores
the baseline if the trial was not confirmed. Failed presentation attempts
also attempt baseline restoration. Starting a trial is rejected during a
development update, an active drawing transaction, or panel standby.

Confirmation keeps the rate **for the current session only**. Every reboot
starts at the proven 58.9 Hz setting, including if the panel was unreadable
at the experimental rate. The confirm action has a one-second guard against
accidental repeated Enter presses. Both buttons support coordinate touch.
The page timer is registered once and its list link is cleared when removed,
so repeated visits do not retain stale timer links.

## Emulator and diagnostics

QEMU patchset **r70** derives Prime frame-completion deadlines from its
programmed pixel clock and timing totals; the previous fixed 16 ms delay
would incorrectly treat both modes alike. Non-Prime behavior is unchanged.
Existing modeled panel timing acceptance limits were **not relaxed** to make
the new mode pass. This is still a digital timing model, not optical proof.
The existing r69 source checkout was reused via the build script's explicit
source override; a fresh r70 runtime/build directory was used.

`vm/test-prime-display-clock.py` checks latch deadlines at 16,980,000 ns and
18,112,000 ns, including no swap one nanosecond early. The UI tests read the
actual divider, vertical-total and PWM registers, exercise unattended timeout,
keyboard/touch confirmation, cancel on exit, and repeated page visits. The
test waits for guest elapsed time rather than assuming virtual TCG time
matches host wall time. Trial screenshots are taken after the mode-switch
handler completes, not during its intentional backlight-off interval.

USB diagnostic interpretation accepts both frame-swap buffer addresses instead
of incorrectly flagging the second scanout buffer as invalid. VM diagnostics
expose `DISPLAY REFRESH` (millihertz) and `DISPLAY TRIAL`.

## Qualification

- Both native and emulator-target firmware builds completed.
- 130 targeted tests pass, including the compiled trial deadline state machine.
- Modeled LCDIF latch-deadline checks and the real Shift/event decoder pass.
- Coordinate-touch regression checks cover launcher/menu scrolling and palette
  insertion, alongside the new brightness and refresh-page workflows.
- Physical-target emulated NAND boot, main/elapsed timing and battery fault
  checks are used before adding the candidate to installer history.
- Physical brightness behavior and 55.2 Hz optical stability require user
  confirmation after installation. No new hardware mode was selected remotely.
