/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef PRIME_G2_BCH_H
#define PRIME_G2_BCH_H
#include <stddef.h>
#include <stdint.h>
typedef struct PrimeBCH PrimeBCH;
PrimeBCH *prime_bch_new(unsigned m, unsigned strength, unsigned primitive);
void prime_bch_free(PrimeBCH *bch);
unsigned prime_bch_bits(const PrimeBCH *bch);
unsigned prime_bch_bytes(const PrimeBCH *bch);
/* MSB-first data/parity, last parity byte left aligned. Return -1 on invalid
 * input. Decode returns correction count or -2 for an uncorrectable word;
 * no caller buffer is changed on failure. Beyond-strength errors may alias. */
int prime_bch_encode(const PrimeBCH *bch, const uint8_t *data, size_t length,
                     uint8_t *parity);
int prime_bch_decode(const PrimeBCH *bch, uint8_t *data, size_t length,
                     uint8_t *parity, unsigned *positions);
#endif
