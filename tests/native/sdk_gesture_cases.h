// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef SDK_GESTURE_CASES_H
#define SDK_GESTURE_CASES_H
#include <lefony/gestures.h>
namespace GestureTests {
inline bool test() {
  using namespace Lefony;using namespace Lefony::UI;
  Gestures gestures({10,10,300,200});InputSnapshot input;input.event=3;input.touchPhase=0;input.contactCount=1;
  input.contacts[0]={7,100,100};input.millis=UINT32_MAX-200;
  if(gestures.update(input).kind!=GestureKind::Begin) return false;
  input.event=2;input.millis=100;if(gestures.update(input).kind!=GestureKind::None) return false;
  input.millis=300;if(gestures.update(input).kind!=GestureKind::LongPress || gestures.update(input).kind!=GestureKind::None) return false;
  input.event=3;input.touchPhase=2;input.contactCount=0;
  if(gestures.update(input).kind!=GestureKind::End) return false;
  input.touchPhase=0;input.contactCount=1;input.millis=1000;
  if(gestures.update(input).kind!=GestureKind::Begin) return false;
  input.touchPhase=1;input.contacts[0].x=103;
  if(gestures.update(input).kind!=GestureKind::None) return false;
  input.contacts[0].x=110;auto pan=gestures.update(input);
  if(pan.kind!=GestureKind::Pan || pan.dx!=10 || pan.dy) return false;
  input.contacts[0].x=111;pan=gestures.update(input);
  if(pan.kind!=GestureKind::Pan || pan.dx!=1) return false;
  input.contactCount=2;input.contacts[1]={2,211,100};input.flags=ContactsChanged;
  if(gestures.update(input).kind!=GestureKind::Begin) return false;
  input.contacts[0]={2,231,100};input.contacts[1]={7,91,100};input.flags=0;
  auto pinch=gestures.update(input);
  if(pinch.kind!=GestureKind::Pinch || pinch.dx || pinch.dy || Math::abs(pinch.scale-100./140)>1e-14) return false;
  input.contactCount=1;input.flags=ContactsChanged;
  if(gestures.update(input).kind!=GestureKind::Begin) return false;
  input.contacts[0].id=9;if(gestures.update(input).kind!=GestureKind::Cancel) return false;
  if(gestures.update(input).kind!=GestureKind::None) return false;
  input.touchPhase=0;input.flags=0;input.contacts[0]={3,20,20};input.millis=2000;gestures.update(input);
  input.touchPhase=2;input.contactCount=0;input.millis=2100;
  if(gestures.update(input).kind!=GestureKind::Tap) return false;
  input.touchPhase=0;input.contactCount=1;gestures.update(input);
  input.touchPhase=2;input.contactCount=0;input.contacts[0].x=200;
  if(gestures.update(input).kind!=GestureKind::End) return false;
  input.touchPhase=0;input.contactCount=1;gestures.update(input);
  input.event=1;if(gestures.update(input).kind!=GestureKind::Cancel) return false;
  input.event=3;input.touchPhase=1;if(gestures.update(input).kind!=GestureKind::None) return false;
  input.touchPhase=0;input.contacts[0]={2,2,2};if(gestures.update(input).kind!=GestureKind::None) return false;
  input.contacts[0]={2,100,100};gestures.update(input);input.touchPhase=3;
  if(gestures.update(input).kind!=GestureKind::Cancel) return false;
  return true;
}
}
#endif
