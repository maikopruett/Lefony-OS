/* Compile the unmodified U-Boot codec without colliding with macOS fls(). */
#include <string.h>
#define fls prime_oracle_fls
#include PRIME_BCH_ORACLE_SOURCE
