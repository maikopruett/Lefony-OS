// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/app.h>

extern "C" void lefony_event(Lefony::Event event, uint32_t, uint32_t) {
  if (event == Lefony::Event::Start) {
    Lefony::fill({0, 0, 320, 240, Lefony::White});
    Lefony::fill({0, 0, 320, 40, Lefony::Green});
    constexpr char title[] = "Hello from a native app";
    Lefony::text({10, 12, Lefony::White, Lefony::Green, title, sizeof(title)-1});
    constexpr char detail[] = "ARM code running in user mode";
    Lefony::text({10, 65, Lefony::Black, Lefony::White, detail, sizeof(detail)-1});
  }
}
