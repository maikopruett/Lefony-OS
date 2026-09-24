// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_UI_SYSTEM_H
#define LEFONY_UI_SYSTEM_H
#include "ui_widgets.h"
#include "system.h"
namespace Lefony { namespace UI {
// Derive a widget palette from a successful OS system snapshot. The OS remains
// the owner of its theme; changing this returned palette customizes only the app.
inline Palette systemPalette(const LefonySystemInfo &info) {
  Palette p;
  p.paper=info.colors[LEFONY_COLOR_APP_BACKGROUND];p.surface=info.colors[LEFONY_COLOR_BACKGROUND];
  p.ink=info.colors[LEFONY_COLOR_TEXT];p.muted=info.colors[LEFONY_COLOR_SECONDARY_TEXT];
  p.accent=info.colors[LEFONY_COLOR_ACCENT];p.disabled=info.colors[LEFONY_COLOR_DISABLED];
  p.selection=info.colors[LEFONY_COLOR_SELECTION];p.error=info.colors[LEFONY_COLOR_ERROR];
  // Choose a readable button label for either a light or dark accent.
  unsigned r=(p.accent>>11)*255/31,g=((p.accent>>5)&63)*255/63,b=(p.accent&31)*255/31;
  p.onAccent=(r*299+g*587+b*114>=140000)?0:0xffff;return p;
}
}}
#endif
