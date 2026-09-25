import struct
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prime_g2_uboot_recovery import ram_capsule


def test_ram_wrapper_preserves_payload_and_fixes_destination():
    payload = struct.pack('<I', 0xea0000b8) + bytes(4092)
    image = ram_capsule(payload)
    assert image[4096:] == payload
    assert struct.unpack_from('<4I', image) == (0x3155424c, 1, 0x87800000, 4096)
    assert struct.unpack_from('<3I', image, 0x24) == (0x016f2818, 0, len(image))


@pytest.mark.parametrize('payload', [b'', bytes(4096), struct.pack('<I', 0xea000000),
                                    struct.pack('<I', 0xea000000) + bytes(0xff000)])
def test_wrong_binary_or_size_rejected(payload):
    with pytest.raises(ValueError):
        ram_capsule(payload)
