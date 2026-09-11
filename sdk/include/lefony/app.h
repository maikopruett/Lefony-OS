// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_H
#define LEFONY_APP_H
#include <stdint.h>

// ABI 1. Numeric service/event values and wire structs are frozen.
// ABI 0 remains an emulator-only compatibility path.
namespace Lefony {
enum class Event : uint32_t { Start = 0, Key = 1, Tick = 2, Touch = 3, Close = 4 };
enum class Key : uint32_t { Unknown=0, Left=1, Right=2, Up=3, Down=4, Confirm=5, Delete=6, Digit0=16, Decimal=26, Minus=27 };
enum class TouchPhase : uint32_t { Down=0, Move=1, Up=2, Cancel=3 };
struct Input {
  Event event; uint32_t first,second;
  int x() const { return static_cast<int16_t>(first&65535); }
  int y() const { return static_cast<int16_t>(first>>16); }
  TouchPhase phase() const { return static_cast<TouchPhase>(second&255); }
};
struct Rect { int32_t x, y, width, height; uint32_t color; };
struct Text { int32_t x, y; uint32_t color, background; const char *value; uint32_t length; };
inline int32_t service(uint32_t number, const void *argument = nullptr) {
  register uint32_t r0 asm("r0") = number;
  register const void *r1 asm("r1") = argument;
  asm volatile("svc #0" : "+r"(r0), "+r"(r1) : : "r2", "r3", "r12", "lr", "cc", "memory");
  return static_cast<int32_t>(r0);
}
inline int32_t fill(Rect rect) { return service(1, &rect); }
inline int32_t text(Text value) { return service(2, &value); }
struct DataTransfer { uint32_t offset; void *buffer; uint32_t length; };
// App-private 64 KiB data, at most 4096 bytes per call. Writes commit with the
// package when leaving the app; zero/positive bytes or a negative error.
inline int32_t readData(uint32_t offset,void *buffer,uint32_t length) {
  DataTransfer transfer{offset,buffer,length}; return service(4,&transfer);
}
inline int32_t writeData(uint32_t offset,const void *buffer,uint32_t length) {
  DataTransfer transfer{offset,const_cast<void *>(buffer),length}; return service(5,&transfer);
}
inline uint32_t millis() { return static_cast<uint32_t>(service(3)); }
constexpr uint32_t Width = 320, Height = 240;
constexpr uint32_t White = 0xffff, Green = 0x2528, Black = 0;
}
extern "C" void lefony_event(Lefony::Event event, uint32_t first, uint32_t second);
#endif
