/* Binary BCH arithmetic for Prime G2 NAND. Independently implemented and
 * differentially checked against Linux/U-Boot and the Python reference.
 * SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef PRIME_BCH_STANDALONE
#include "qemu/osdep.h"
#endif
#include "prime_g2_bch.h"
#include <stdlib.h>
#include <string.h>

#define MAX_T 40
#define MAX_R (14 * MAX_T)
#define MAX_ECC ((MAX_R + 7) / 8)

struct PrimeBCH {
    unsigned n, t, r, bytes;
    uint16_t *exp, *log;
    uint8_t generator[MAX_R + 1]; /* ascending binary coefficients */
    uint8_t table[256][MAX_ECC];
};

static unsigned multiply(const PrimeBCH *b, unsigned a, unsigned c)
{
    return a && c ? b->exp[b->log[a] + b->log[c]] : 0;
}

static unsigned divide(const PrimeBCH *b, unsigned a, unsigned c)
{
    return a ? b->exp[(b->log[a] + b->n - b->log[c]) % b->n] : 0;
}

static unsigned getbit(const uint8_t *bytes, unsigned bit)
{
    return (bytes[bit / 8] >> (7 - bit % 8)) & 1;
}

static void flipbit(uint8_t *bytes, unsigned bit)
{
    bytes[bit / 8] ^= 1u << (7 - bit % 8);
}

void prime_bch_free(PrimeBCH *b)
{
    if (b) {
        free(b->exp);
        free(b->log);
        free(b);
    }
}

PrimeBCH *prime_bch_new(unsigned m, unsigned t, unsigned primitive)
{
    PrimeBCH *b;
    uint8_t *roots;
    uint16_t poly[MAX_R + 1] = {1}, next[MAX_R + 1];
    unsigned i, j, root, value = 1, degree = 0;
    if (m < 2 || m > 14 || !t || t > MAX_T || 2 * t >= (1u << m) ||
        primitive < (1u << m) || primitive >= (2u << m)) {
        return NULL;
    }
    b = calloc(1, sizeof(*b));
    if (!b) {
        return NULL;
    }
    b->n = (1u << m) - 1;
    b->t = t;
    b->exp = calloc(2 * b->n, sizeof(*b->exp));
    b->log = malloc((b->n + 1) * sizeof(*b->log));
    roots = calloc(b->n, 1);
    if (!b->exp || !b->log || !roots) {
        goto fail;
    }
    memset(b->log, 0xff, (b->n + 1) * sizeof(*b->log));
    for (i = 0; i < b->n; i++) {
        if (!value || b->log[value] != 0xffff) {
            goto fail;
        }
        b->exp[i] = value;
        b->log[value] = i;
        value <<= 1;
        if (value & (1u << m)) {
            value ^= primitive;
        }
    }
    if (value != 1) {
        goto fail;
    }
    memcpy(b->exp + b->n, b->exp, b->n * sizeof(*b->exp));
    for (i = 1; i <= 2 * t; i++) {
        for (root = i; !roots[root]; root = root * 2 % b->n) {
            roots[root] = 1;
        }
    }
    for (root = 0; root < b->n; root++) {
        if (!roots[root]) {
            continue;
        }
        if (degree == MAX_R) {
            goto fail;
        }
        memset(next, 0, sizeof(next));
        for (i = 0; i <= degree; i++) {
            next[i] ^= multiply(b, poly[i], b->exp[root]);
            next[i + 1] ^= poly[i];
        }
        memcpy(poly, next, sizeof(poly));
        degree++;
    }
    b->r = degree;
    b->bytes = (degree + 7) / 8;
    for (i = 0; i <= degree; i++) {
        if (poly[i] > 1) {
            goto fail;
        }
        b->generator[i] = poly[i];
    }
    /* Byte-at-a-time LFSR table. The register's unused low bits stay zero. */
    for (value = 0; value < 256; value++) {
        uint8_t word[1 + MAX_ECC] = {0};
        word[0] = value;
        for (i = 0; i < 8; i++) {
            if (getbit(word, i)) {
                for (j = 0; j <= degree; j++) {
                    if (b->generator[degree - j]) {
                        flipbit(word, i + j);
                    }
                }
            }
        }
        memcpy(b->table[value], word + 1, b->bytes);
    }
    free(roots);
    return b;
fail:
    free(roots);
    prime_bch_free(b);
    return NULL;
}

unsigned prime_bch_bits(const PrimeBCH *b) { return b->r; }
unsigned prime_bch_bytes(const PrimeBCH *b) { return b->bytes; }

int prime_bch_encode(const PrimeBCH *b, const uint8_t *data, size_t length,
                     uint8_t *parity)
{
    size_t i;
    unsigned j;
    if (!b || !parity || (!data && length) || length > (b->n - b->r) / 8) {
        return -1;
    }
    memset(parity, 0, b->bytes);
    for (i = 0; i < length; i++) {
        unsigned index = parity[0] ^ data[i];
        for (j = 0; j + 1 < b->bytes; j++) {
            parity[j] = parity[j + 1] ^ b->table[index][j];
        }
        parity[b->bytes - 1] = b->table[index][b->bytes - 1];
    }
    return 0;
}

static int syndromes(const PrimeBCH *b, const uint8_t *word, unsigned bits,
                      uint16_t *syn)
{
    unsigned i, j, any = 0;
    memset(syn, 0, 2 * b->t * sizeof(*syn));
    for (i = 0; i < bits; i++) {
        if (getbit(word, i)) {
            unsigned power = bits - 1 - i;
            for (j = 0; j < 2 * b->t; j++) {
                syn[j] ^= b->exp[((j + 1) * power) % b->n];
            }
        }
    }
    for (j = 0; j < 2 * b->t; j++) {
        any |= syn[j];
    }
    return any != 0;
}

int prime_bch_decode(const PrimeBCH *b, uint8_t *data, size_t length,
                     uint8_t *parity, unsigned *positions)
{
    uint8_t calculated[MAX_ECC], *word;
    uint16_t syn[2 * MAX_T], locator[2 * MAX_T + 1] = {1};
    uint16_t previous[2 * MAX_T + 1] = {1}, saved[2 * MAX_T + 1];
    unsigned errors[MAX_T], degree = 0, distance = 1, last = 1;
    unsigned i, j, step, bits, count = 0, diff = 0;
    if (prime_bch_encode(b, data, length, calculated) || !parity) {
        return -1;
    }
    for (i = 0; i < b->r; i++) {
        diff |= getbit(calculated, i) ^ getbit(parity, i);
    }
    if (!diff) {
        return 0;
    }
    bits = length * 8 + b->r;
    word = malloc(length + b->bytes);
    if (!word) {
        return -1;
    }
    memcpy(word, data, length);
    memcpy(word + length, parity, b->bytes);
    syndromes(b, word, bits, syn);
    for (step = 0; step < 2 * b->t; step++) {
        unsigned discrepancy = syn[step];
        for (i = 1; i <= degree; i++) {
            discrepancy ^= multiply(b, locator[i], syn[step - i]);
        }
        if (!discrepancy) {
            distance++;
            continue;
        }
        memcpy(saved, locator, sizeof(saved));
        for (i = 0; i + distance <= 2 * b->t; i++) {
            locator[i + distance] ^= multiply(b, divide(b, discrepancy, last), previous[i]);
        }
        if (2 * degree <= step) {
            degree = step + 1 - degree;
            memcpy(previous, saved, sizeof(previous));
            last = discrepancy;
            distance = 1;
        } else {
            distance++;
        }
    }
    if (degree > b->t) {
        goto failed;
    }
    for (i = 0; i < bits; i++) {
        unsigned x = b->exp[(b->n - i % b->n) % b->n], value = 0;
        for (j = 2 * b->t + 1; j > 0; j--) {
            value = multiply(b, value, x) ^ locator[j - 1];
        }
        if (!value) {
            if (count == b->t) {
                goto failed;
            }
            errors[count++] = bits - 1 - i;
        }
    }
    if (count != degree) {
        goto failed;
    }
    for (i = 0; i < count; i++) {
        flipbit(word, errors[i]);
    }
    if (syndromes(b, word, bits, syn)) {
        goto failed;
    }
    memcpy(data, word, length);
    memcpy(parity, word + length, b->bytes);
    if (positions) {
        for (i = 0; i < count; i++) {
            positions[i] = errors[count - 1 - i];
        }
    }
    free(word);
    return count;
failed:
    free(word);
    return -2;
}
