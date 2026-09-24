# SPDX-License-Identifier: GPL-3.0-or-later
"""Checked, idempotent foreground scheduling in the prepared Upsilon tree.

Embedded Upsilon code transformations retain the core's CC-BY-NC-SA-4.0 terms.
Run after the key-edge patch and coordinate-touch integration.
"""
import argparse
from pathlib import Path


def prepare(source):
    def edit(name, old, new):
        path = source / name
        content = path.read_text()
        if content.count(new) == 1:
            return
        if content.count(old) != 1:
            raise ValueError(f'Unexpected native scheduling context: {name}: {old[:70]}')
        path.write_text(content.replace(old, new))

    edit('ion/include/ion/events.h',
         'constexpr Event Touch = Event::Special(7);',
         'constexpr Event Touch = Event::Special(7);\nconstexpr Event NativeAppResume = Event::Special(8);\nconstexpr Event NativeKeyApproval = Event::Special(9);\nconstexpr Event NativeArchiveApproval = Event::Special(10);')
    edit('ion/src/shared/events.cpp',
         '  if (*this == Touch) return true;',
         '  if (*this == Touch || *this == NativeAppResume || *this == NativeKeyApproval || *this == NativeArchiveApproval) return true;')
    keyboard = 'ion/src/shared/events_keyboard.cpp'
    edit(keyboard, 'Event getPlatformEvent();', '''Event getPlatformEvent();
#if defined(PLATFORM_PRIME_G2)
Event getDeferredPlatformEvent();
bool hasDeferredPlatformWork();
void observeNativeKeyboard(Keyboard::State state);
static uint64_t sLastRepeatMillis = 0;
#endif''')
    edit(keyboard, '  int time = 0;', '''#if !defined(PLATFORM_PRIME_G2)
  int time = 0;
#endif''')
    edit(keyboard, '    Keyboard::State state = Keyboard::scan();', '''    Keyboard::State state = Keyboard::scan();
#if defined(PLATFORM_PRIME_G2)
    observeNativeKeyboard(state);
#endif''')
    edit(keyboard, '      sLastKeyboardState = state;\n      return event;', '''      sLastKeyboardState = state;
#if defined(PLATFORM_PRIME_G2)
      sLastRepeatMillis = Timing::millis();
#endif
      return event;''')
    sleep = '''    PrimeG2BootProgress(11);
    if (sleepWithTimeout(10, timeout)) {
      PrimeG2BootProgress(12);
      // Timeout occurred
      resetLongRepetition();
      return Events::None;
    }
    PrimeG2BootProgress(12);'''
    edit(keyboard, sleep + '\n    time += 10;',
         '#if !defined(PLATFORM_PRIME_G2)\n' + sleep + '\n    time += 10;\n#endif')
    edit(keyboard, '      if (time >= delay) {', '''#if defined(PLATFORM_PRIME_G2)
      if (Timing::millis() - sLastRepeatMillis >= static_cast<uint64_t>(delay)) {
        sLastRepeatMillis = Timing::millis();
#else
      if (time >= delay) {
#endif''')
    edit(keyboard, '''        return sLastEvent;
      }
    }
  }
}''', '''        return sLastEvent;
      }
    }
#if defined(PLATFORM_PRIME_G2)
    // Real input and its repeat policy take priority over foreground work.
    Event deferred = getDeferredPlatformEvent();
    if (deferred != None) return deferred;
    // Advance one storage step per normal service/input scan without an idle
    // delay. Return to RunLoop so real elapsed time still advances UI timers.
    // No synthetic input event, redraw or user-activity notification is sent.
    if (hasDeferredPlatformWork()) return Events::None;
''' + sleep + '''
#endif
  }
}''')

    # Count time spent dispatching/returning from apps as well as event waits.
    # Coalesce overdue UI ticks after stalls instead of replaying an unbounded
    # timer backlog; normal 300 ms periods and other target behavior are intact.
    edit('escher/include/escher/run_loop.h', '  int m_time;', '''#if defined(PLATFORM_PRIME_G2)
  uint64_t m_time = 0;
  uint64_t m_lastTimerPoll = 0;
  bool m_timerClockStarted = false;
#else
  int m_time;
#endif''')
    loop = 'escher/src/run_loop.cpp'
    edit(loop, 'bool RunLoop::step() {', '''bool RunLoop::step() {
#if defined(PLATFORM_PRIME_G2)
  if (!m_timerClockStarted) {
    m_lastTimerPoll = Ion::Timing::millis();
    m_timerClockStarted = true;
  }
#endif''')
    edit(loop, '  m_time += eventDuration;', '''#if defined(PLATFORM_PRIME_G2)
  uint64_t now = Ion::Timing::millis();
  m_time += now >= m_lastTimerPoll ? now - m_lastTimerPoll : 0;
  m_lastTimerPoll = now;
#else
  m_time += eventDuration;
#endif''')
    edit(loop, '    m_time -= Timer::TickDuration;', '''#if defined(PLATFORM_PRIME_G2)
    m_time %= Timer::TickDuration;
#else
    m_time -= Timer::TickDuration;
#endif''')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    prepare(parser.parse_args().source.resolve())
