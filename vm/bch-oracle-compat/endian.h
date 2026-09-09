#include <stdint.h>
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define htobe32(value) __builtin_bswap32(value)
#else
#define htobe32(value) (value)
#endif
