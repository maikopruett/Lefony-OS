# SPDX-License-Identifier: GPL-3.0-or-later
"""Public fail-closed patch-plan tests; no HP firmware required."""
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from prime_hp_confinement import BASE,Patch,apply_patches,patch_image
from analyze_hp_prime_compatibility import AuditError


def test_patch_is_atomic_and_does_not_mutate_input():
    original=bytes(32)
    good=Patch(BASE+4,bytes(4),b'ABCD','synthetic')
    bad=Patch(BASE+12,b'xxxx',b'yyyy','synthetic mismatch')
    with pytest.raises(AuditError,match='unexpected bytes'):
        apply_patches(original,(good,bad))
    assert original==bytes(32)
    assert apply_patches(original,(good,))==bytes(4)+b'ABCD'+bytes(24)


@pytest.mark.parametrize('patch',[
    Patch(BASE-1,b'x',b'y','underflow'),
    Patch(BASE+32,b'x',b'y','overflow'),
    Patch(BASE+4,b'',b'','empty'),
    Patch(BASE+4,bytes(4),b'x','resize'),
])
def test_invalid_patch_range_and_size(patch):
    with pytest.raises(AuditError):apply_patches(bytes(32),(patch,))


def test_overlap_rejected_even_with_matching_bytes():
    with pytest.raises(AuditError,match='overlapping'):
        apply_patches(bytes(32),(Patch(BASE+4,bytes(8),b'a'*8,'a'),Patch(BASE+8,bytes(8),b'b'*8,'b')))


@pytest.mark.parametrize('name,data',[('other.img',b''),('HPPrime.img',b'V15751'),('bootloader.img',bytes(358316))])
def test_original_whole_image_identity_required(name,data):
    with pytest.raises(AuditError):patch_image(name,data)
