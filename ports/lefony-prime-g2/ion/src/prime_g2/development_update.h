#pragma once
#include <stdint.h>
#include <stddef.h>
namespace PrimeG2 { namespace DevelopmentUpdate {
enum State : uint32_t { Idle, Checking=4, Erasing, Writing, Verifying, Complete, Failed };
struct Status { uint32_t magic, version, state, done, total, error, changed, crc; };
const Status &status();
bool busy();
void clearResult();
bool begin(const uint8_t *image, size_t length, uint32_t crc);
void poll();
} }
