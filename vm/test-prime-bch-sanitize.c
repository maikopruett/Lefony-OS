/* Standalone memory/undefined-behavior qualification, not linked into QEMU.
 * SPDX-License-Identifier: GPL-2.0-or-later */
#include "qemu/prime_g2_bch.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    unsigned m, t, trial, i, state = 606;
    for (m = 13; m <= 14; m++) {
        for (t = 2; t <= 40; t += 2) {
            PrimeBCH *b = prime_bch_new(m, t, m == 13 ? 0x201b : 0x402b);
            unsigned r = prime_bch_bits(b), bytes = prime_bch_bytes(b);
            assert(b);
            for (trial = 0; trial < 12; trial++) {
                unsigned length = trial ? (((1u << m) - 1 - r) / 8) : 0;
                uint8_t data[2048], parity[70], original[2048], original_ecc[70];
                unsigned positions[40], count = 0;
                for (i = 0; i < length; i++) {
                    state = state * 1664525u + 1013904223u;
                    data[i] = state >> 24;
                }
                assert(!prime_bch_encode(b, data, length, parity));
                memcpy(original, data, length);
                memcpy(original_ecc, parity, bytes);
                for (i = 0; i < t; i++) {
                    unsigned bit = i * (length * 8 + r) / t;
                    uint8_t *target = bit < length * 8 ? data : parity;
                    if (bit >= length * 8) {
                        bit -= length * 8;
                    }
                    target[bit / 8] ^= 1u << (7 - bit % 8);
                    count++;
                }
                assert(prime_bch_decode(b, data, length, parity, positions) == (int)count);
                assert(!memcmp(data, original, length));
                assert(!memcmp(parity, original_ecc, bytes));
                assert(prime_bch_encode(b, data, 2048, parity) == -1);
            }
            prime_bch_free(b);
        }
    }
    puts("PASS 480 ASan/UBSan BCH maximum-length and parity-only correction cases");
    return 0;
}
