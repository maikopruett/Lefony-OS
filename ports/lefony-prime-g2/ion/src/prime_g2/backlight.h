#ifndef ION_PRIME_G2_BACKLIGHT_H
#define ION_PRIME_G2_BACKLIGHT_H

namespace PrimeG2 {
namespace Backlight {

/* Configure PWM and both output pins while keeping the optical path disabled.
 * Cold boot uses this before the application has produced its first frame. */
void prepare();

/* Expose the already-configured PWM output. This is idempotent so every later
 * Window::redraw may safely report frame completion. */
void reveal();
void hide();
bool isVisible();

}
}

#endif
