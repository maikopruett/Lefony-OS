/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
#ifndef LEFONY_INPUT_STREAM_H
#define LEFONY_INPUT_STREAM_H
#include "app_c.h"
#include "input_stream_wire.h"

/* Physical positions, including reserved keys for map inspection. Home and
 * Apps never appear in the stream; power has no matrix position. */
enum {
  LEFONY_PHYSICAL_ALPHA=19,
  LEFONY_PHYSICAL_APPS=36,
  LEFONY_PHYSICAL_BACK=38,
  LEFONY_PHYSICAL_BACKSPACE=16,
  LEFONY_PHYSICAL_CAS=41,
  LEFONY_PHYSICAL_COMMA=48,
  LEFONY_PHYSICAL_COS=29,
  LEFONY_PHYSICAL_DIVIDE=10,
  LEFONY_PHYSICAL_DOT=46,
  LEFONY_PHYSICAL_DOWN=37,
  LEFONY_PHYSICAL_EE=8,
  LEFONY_PHYSICAL_EIGHT=49,
  LEFONY_PHYSICAL_FIVE=52,
  LEFONY_PHYSICAL_FOUR=53,
  LEFONY_PHYSICAL_FRACTION=20,
  LEFONY_PHYSICAL_HELP=47,
  LEFONY_PHYSICAL_HOME=35,
  LEFONY_PHYSICAL_LEFT=15,
  LEFONY_PHYSICAL_LN=27,
  LEFONY_PHYSICAL_LOG=26,
  LEFONY_PHYSICAL_MENU=42,
  LEFONY_PHYSICAL_MINUS=12,
  LEFONY_PHYSICAL_MULTIPLY=11,
  LEFONY_PHYSICAL_NINE=40,
  LEFONY_PHYSICAL_NUM=32,
  LEFONY_PHYSICAL_OK=56,
  LEFONY_PHYSICAL_ONE=45,
  LEFONY_PHYSICAL_PARENTHESIS=39,
  LEFONY_PHYSICAL_PLOT=33,
  LEFONY_PHYSICAL_PLUS=13,
  LEFONY_PHYSICAL_PLUSMINUS=24,
  LEFONY_PHYSICAL_POWER=31,
  LEFONY_PHYSICAL_RIGHT=57,
  LEFONY_PHYSICAL_SEVEN=50,
  LEFONY_PHYSICAL_SHIFT=30,
  LEFONY_PHYSICAL_SIN=22,
  LEFONY_PHYSICAL_SIX=51,
  LEFONY_PHYSICAL_SPACE=14,
  LEFONY_PHYSICAL_SQUARE=25,
  LEFONY_PHYSICAL_SYMB=34,
  LEFONY_PHYSICAL_TAN=28,
  LEFONY_PHYSICAL_THREE=54,
  LEFONY_PHYSICAL_TOOLBOX=23,
  LEFONY_PHYSICAL_TWO=55,
  LEFONY_PHYSICAL_UNITS=18,
  LEFONY_PHYSICAL_UP=44,
  LEFONY_PHYSICAL_VAR=21,
  LEFONY_PHYSICAL_VIEW=43,
  LEFONY_PHYSICAL_XNT=17,
  LEFONY_PHYSICAL_ZERO=9
};

/* Removes at most eight events. On overflow, returns current state with zero
 * events: discard local transitions and resynchronize held keys/contacts. The
 * snapshot describes now, which can be newer than a partial batch of events. */
static inline int32_t lefony_read_input_stream(LefonyInputStream *out) {
  if(!out) return -4;
  out->size=sizeof(*out);out->version=1;out->reserved=0;
  return lefony_service(LEFONY_INPUT_STREAM_SERVICE,out);
}
static inline int lefony_input_key_held(const uint32_t mask[2],uint32_t key) {
  return key<64 && (mask[key/32] & (UINT32_C(1)<<(key%32)))!=0;
}
#endif
