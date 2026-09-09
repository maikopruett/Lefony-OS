#ifndef ION_PRIME_G2_BLOCK_STORAGE_H
#define ION_PRIME_G2_BLOCK_STORAGE_H

#include <stddef.h>
#include <stdint.h>

namespace PrimeG2 {
namespace BlockStorage {

constexpr uint32_t BlockSize = 512;
constexpr uint32_t PersistenceStartBlock = 131072;
constexpr uint32_t PersistenceBlockCount = 2048;

bool available();
void initializeMode();
bool writable();
bool read(uint32_t block, void *buffer, size_t blockCount = 1);
bool write(uint32_t block, const void *buffer, size_t blockCount = 1);
bool flush();

}
}

#endif
