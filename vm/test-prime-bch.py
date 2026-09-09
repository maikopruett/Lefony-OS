#!/usr/bin/env python3
"""Independent BCH differential qualification; requires a local U-Boot tree."""
import argparse
import ctypes as C
import hashlib
import itertools
from pathlib import Path
import random
import subprocess
import tempfile

from prime_bch import BCH, UncorrectableError

ROOT = Path(__file__).resolve().parents[1]


class Control(C.Structure):
    _fields_ = [(name, C.c_uint) for name in ('m', 'n', 't', 'ecc_bits', 'ecc_bytes')]


def corrupt(data, parity, positions):
    wire = bytearray(data + parity)
    for bit in positions:
        wire[bit // 8] ^= 1 << (7 - bit % 8)
    return bytes(wire[:len(data)]), bytes(wire[len(data):])


def qualify(library):
    library.init_bch.argtypes = [C.c_int, C.c_int, C.c_uint]
    library.init_bch.restype = C.POINTER(Control)
    library.free_bch.argtypes = [C.POINTER(Control)]
    library.encode_bch.argtypes = [C.POINTER(Control), C.c_void_p, C.c_uint, C.c_void_p]
    library.decode_bch.argtypes = [C.POINTER(Control), C.c_void_p, C.c_uint,
                                  C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
    rng = random.Random(0x606)
    cases = 0
    for m, strength, primitive, length in (
            (5, 2, 0x25, 2), (13, 2, 0x201b, 522), (13, 4, 0x201b, 512),
            (13, 6, 0x201b, 512),
            (13, 8, 0x201b, 512), (13, 8, 0x201b, 522), (13, 16, 0x201b, 512),
            (13, 40, 0x201b, 512), (14, 8, 0x402b, 1024)):
        codec = BCH(m, strength, primitive)
        control = library.init_bch(m, strength, primitive)
        assert control, 'oracle rejected configuration'
        try:
            assert control.contents.ecc_bits == codec.ecc_bits
            assert control.contents.ecc_bytes == codec.ecc_bytes
            for data in (bytes(length), b'\xff' * length,
                         bytes(i % 256 for i in range(length)), rng.randbytes(length)):
                expected = C.create_string_buffer(codec.ecc_bytes)
                library.encode_bch(control, data, len(data), expected)
                parity = codec.encode(data)
                assert parity == expected.raw, (m, strength, 'parity mismatch')
                bits = len(data) * 8 + codec.ecc_bits
                patterns = [(), (0,), (len(data) * 8,), (bits - 1,),
                            tuple(rng.sample(range(bits), strength))]
                if m == 5:
                    patterns += list(itertools.combinations(range(bits), 2))
                for positions in patterns:
                    damaged, damaged_ecc = corrupt(data, parity, positions)
                    fixed, fixed_ecc, found = codec.decode(damaged, damaged_ecc)
                    assert (fixed, fixed_ecc) == (data, parity)
                    assert found == tuple(sorted(positions))
                    locations = (C.c_uint * strength)()
                    count = library.decode_bch(control, damaged, len(data),
                                               damaged_ecc, None, None, locations)
                    assert count == len(positions), (m, strength, count, positions)
                    assert sorted(locations[i] ^ 7 for i in range(count)) == sorted(positions)
                    cases += 1
            print(f'PASS GF({m}) t={strength}: parity and correction match U-Boot')
        finally:
            library.free_bch(control)
    codec = BCH(13, 8, 0x201b)
    data = rng.randbytes(512)
    parity = codec.encode(data)
    damaged, damaged_ecc = corrupt(data, parity, range(32))
    try:
        codec.decode(damaged, damaged_ecc)
    except UncorrectableError:
        pass
    else:
        raise AssertionError('selected overload vector was not rejected')
    for action in (lambda: codec.encode(bytes(1024)),
                   lambda: codec.decode(data, parity[:-1]),
                   lambda: BCH(5, 2, 0x21)):
        try:
            action()
        except ValueError:
            pass
        else:
            raise AssertionError('invalid input was not rejected')
    print(f'PASS {cases} differential decode cases and invalid/overload checks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uboot', type=Path, default=ROOT / 'build/lefony-prime-g2-u-boot')
    args = parser.parse_args()
    source = args.uboot.resolve() / 'lib/bch.c'
    print('Oracle source SHA-256:', hashlib.sha256(source.read_bytes()).hexdigest())
    with tempfile.TemporaryDirectory(prefix='prime-bch-') as directory:
        library = Path(directory) / 'oracle.so'
        subprocess.run(['clang', '-shared', '-fPIC', '-DUSE_HOSTCC',
                        f'-DPRIME_BCH_ORACLE_SOURCE="{source}"',
                        '-I', str(ROOT / 'vm/bch-oracle-compat'),
                        '-idirafter', str(args.uboot.resolve() / 'include'),
                        str(ROOT / 'vm/bch-oracle-compat/oracle.c'), '-o', str(library)],
                       check=True)
        qualify(C.CDLL(str(library)))


if __name__ == '__main__':
    main()
