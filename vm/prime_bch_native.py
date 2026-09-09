"""Temporary host build of the same C codec used by QEMU, for image encoding."""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile


class NativeBCH:
    def __init__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='prime-bch-native-')
        self.instances = {}
        library = Path(self.temporary.name) / 'bch.so'
        source = Path(__file__).resolve().parent / 'qemu/prime_g2_bch.c'
        try:
            subprocess.run(['clang', '-O2', '-shared', '-fPIC', '-DPRIME_BCH_STANDALONE',
                            str(source), '-o', str(library)], check=True)
            self.lib = C.CDLL(str(library))
            self.lib.prime_bch_new.argtypes = [C.c_uint] * 3
            self.lib.prime_bch_new.restype = C.c_void_p
            self.lib.prime_bch_free.argtypes = [C.c_void_p]
            self.lib.prime_bch_bytes.argtypes = [C.c_void_p]
            self.lib.prime_bch_encode.argtypes = [C.c_void_p, C.c_void_p, C.c_size_t, C.c_void_p]
        except Exception:
            self.temporary.cleanup()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        for instance in self.instances.values():
            self.lib.prime_bch_free(instance.pointer)
        self.instances.clear()
        self.temporary.cleanup()

    def __call__(self, field, strength):
        key = field, strength
        if key not in self.instances:
            self.instances[key] = NativeEncoder(self.lib, field, strength)
        return self.instances[key]


class NativeEncoder:
    def __init__(self, library, field, strength):
        self.lib = library
        self.pointer = library.prime_bch_new(field, strength, {13: 0x201b, 14: 0x402b}[field])
        if not self.pointer:
            raise ValueError('unsupported native BCH configuration')
        self.size = library.prime_bch_bytes(self.pointer)

    def encode(self, data):
        parity = C.create_string_buffer(self.size)
        if self.lib.prime_bch_encode(self.pointer, data, len(data), parity):
            raise ValueError('invalid native BCH message size')
        return parity.raw
