#include "registers.h"

#include <ion.h>
#include <ion/clipboard.h>

namespace Ion {

static uint32_t crc32Helper(const uint8_t * data, size_t length,
                            bool wordAccess) {
  constexpr size_t wordSize = sizeof(uint32_t);
  uint32_t crc = 0xFFFFFFFF;
  size_t byteLength = wordAccess ? length * wordSize : length;
  size_t wordLength = byteLength / wordSize;
  for (size_t i = 0; i < wordLength; i++) {
    for (int j = wordSize - 1; j >= 0; j--) {
      crc = crc32EatByte(crc, data[i * wordSize + j]);
    }
  }
  for (size_t i = wordLength * wordSize; i < byteLength; i++) {
    crc = crc32EatByte(crc, data[i]);
  }
  return crc;
}

uint32_t crc32Word(const uint32_t * data, size_t length) {
  return crc32Helper(reinterpret_cast<const uint8_t *>(data), length, true);
}

uint32_t crc32Byte(const uint8_t * data, size_t length) {
  return crc32Helper(data, length, false);
}

uint32_t random() {
  static uint32_t state = 0x4D414841u;
  state ^= PrimeG2::reg32(PrimeG2::GPT1 + 0x24);
  state ^= state << 13;
  state ^= state >> 17;
  state ^= state << 5;
  return state;
}

namespace Clipboard {
void write(const char *) {
}
const char * read() {
  return nullptr;
}
}

}
