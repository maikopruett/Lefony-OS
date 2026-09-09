#!/usr/bin/env python3
"""Qualify the QEMU C codec against the U-Boot-checked Python reference."""
import ctypes as C
from pathlib import Path
import random
import subprocess
import tempfile

from prime_bch import BCH, UncorrectableError

ROOT = Path(__file__).resolve().parents[1]


def qualify(lib):
    lib.prime_bch_new.argtypes = [C.c_uint] * 3
    lib.prime_bch_new.restype = C.c_void_p
    lib.prime_bch_free.argtypes = [C.c_void_p]
    lib.prime_bch_bits.argtypes = lib.prime_bch_bytes.argtypes = [C.c_void_p]
    lib.prime_bch_encode.argtypes = [C.c_void_p, C.c_void_p, C.c_size_t, C.c_void_p]
    lib.prime_bch_decode.argtypes = [C.c_void_p, C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p]
    rng = random.Random(0x606bc)
    cases = 0
    for m, t, primitive, length in [(5, 2, 0x25, 2), (13, 2, 0x201b, 522),
                                    (13, 6, 0x201b, 512), (13, 8, 0x201b, 522),
                                    (13, 16, 0x201b, 512), (13, 40, 0x201b, 128),
                                    (14, 8, 0x402b, 1024)]:
        reference = BCH(m, t, primitive)
        bch = lib.prime_bch_new(m, t, primitive)
        assert bch
        try:
            assert lib.prime_bch_bits(bch) == reference.ecc_bits
            assert lib.prime_bch_bytes(bch) == reference.ecc_bytes
            for data in (bytes(length), b'\xff' * length,
                         bytes(i % 256 for i in range(length)), rng.randbytes(length)):
                parity = C.create_string_buffer(reference.ecc_bytes)
                assert lib.prime_bch_encode(bch, data, length, parity) == 0
                assert parity.raw == reference.encode(data), (m, t, 'encode')
                for count in sorted({0, 1, t, t + 1, t + 4}):
                    positions = rng.sample(range(length * 8 + reference.ecc_bits), count)
                    wire = bytearray(data + parity.raw)
                    for bit in positions:
                        wire[bit // 8] ^= 1 << (7 - bit % 8)
                    message, ecc = bytes(wire[:length]), bytes(wire[length:])
                    buffer = C.create_string_buffer(message, length)
                    damaged_ecc = C.create_string_buffer(ecc, len(ecc))
                    found = (C.c_uint * t)()
                    result = lib.prime_bch_decode(bch, buffer, length, damaged_ecc, found)
                    try:
                        expected_data, expected_ecc, expected_positions = reference.decode(message, ecc)
                    except UncorrectableError:
                        assert result == -2, (m, t, count, result)
                        assert buffer.raw == message and damaged_ecc.raw == ecc
                    else:
                        assert result == len(expected_positions), (m, t, count, result)
                        assert buffer.raw == expected_data
                        assert damaged_ecc.raw == expected_ecc
                        assert tuple(found[:result]) == expected_positions
                    cases += 1
        finally:
            lib.prime_bch_free(bch)
    assert not lib.prime_bch_new(5, 2, 0x21)
    assert not lib.prime_bch_new(14, 41, 0x402b)
    print(f'PASS {cases} C/Python BCH differential cases; failed decode preserves buffers')


def main():
    with tempfile.TemporaryDirectory(prefix='prime-bch-c-') as folder:
        library = Path(folder) / 'codec.so'
        subprocess.run(['clang', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-DPRIME_BCH_STANDALONE', str(ROOT / 'vm/qemu/prime_g2_bch.c'),
                        '-o', str(library)], check=True)
        qualify(C.CDLL(str(library)))


if __name__ == '__main__':
    main()
