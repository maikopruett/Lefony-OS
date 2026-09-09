"""i.MX6 GPMI/BCH page-layout reference, separate from decoded NAND dumps.

Register units/metadata placement follow the Prime U-Boot mxs_nand driver;
LSB-first packing follows Linux gpmi_copy_bits and i.MX nandbcb BCH encoding.
This is not a timing model. Physical codeword captures are still required.
"""
from dataclasses import dataclass
from functools import lru_cache

from prime_bch import BCH, UncorrectableError

REVERSE = bytes(int(f'{value:08b}'[::-1], 2) for value in range(256))


@lru_cache(maxsize=32)
def codec(field, strength):
    return BCH(field, strength, {13: 0x201b, 14: 0x402b}[field])


@dataclass(frozen=True)
class Chunk:
    data_bytes: int
    metadata_bytes: int
    field: int
    strength: int
    start_bit: int

    @property
    def message_bytes(self):
        return self.data_bytes + self.metadata_bytes

    @property
    def parity_bits(self):
        return self.field * self.strength

    @property
    def end_bit(self):
        return self.start_bit + self.message_bytes * 8 + self.parity_bits


@dataclass(frozen=True)
class DecodedPage:
    payload: bytes
    metadata: bytes
    status: tuple[int, ...]  # 0=clean, 1..40=corrected, FE=failed, FF=erased
    erased_zero_count: int = 0

    @property
    def failed(self):
        return 0xfe in self.status


class Layout:
    def __init__(self, layout0: int, layout1: int):
        if not 0 <= layout0 <= 0xffffffff or not 0 <= layout1 <= 0xffffffff:
            raise ValueError('layout register outside uint32')
        self.page_bytes = layout1 >> 16
        self.metadata_bytes = (layout0 >> 16) & 0xff
        self.status_offset = (self.metadata_bytes + 3) & ~3
        blocks_after_first = layout0 >> 24
        self.chunks = []
        start = 0
        for index in range(blocks_after_first + 1):
            register = layout0 if index == 0 else layout1
            chunk = Chunk((register & 0x3ff) * 4,
                          self.metadata_bytes if index == 0 else 0,
                          14 if register & (1 << 10) else 13,
                          ((register >> 11) & 0x1f) * 2, start)
            if chunk.strength > 40:
                raise ValueError('strength exceeds i.MX6ULL BCH capability')
            if chunk.message_bytes == 0:
                raise ValueError('empty BCH block')
            if chunk.strength:
                bch = codec(chunk.field, chunk.strength)
                bch._check_length(chunk.message_bytes)
                if bch.ecc_bits != chunk.parity_bits:
                    raise ValueError('unsupported shortened generator degree')
            self.chunks.append(chunk)
            start = chunk.end_bit
        if start > self.page_bytes * 8:
            raise ValueError('BCH blocks exceed physical page size')
        self.payload_bytes = sum(chunk.data_bytes for chunk in self.chunks)
        self.used_bits = start

    def marker_payload_bit(self):
        """Locate the conventional OOB marker within decoded payload bits."""
        marker = self.payload_bytes * 8
        payload = 0
        for chunk in self.chunks:
            begin = chunk.start_bit + chunk.metadata_bytes * 8
            if begin <= marker and marker + 8 <= begin + chunk.data_bytes * 8:
                return payload + marker - begin
            payload += chunk.data_bytes * 8
        raise ValueError('bad-block marker overlaps parity or metadata')

    def swap_marker(self, payload, metadata):
        """Driver-side involution; the BCH hardware itself does not swap."""
        if len(payload) != self.payload_bytes or len(metadata) != self.metadata_bytes:
            raise ValueError('incorrect DMA buffer lengths')
        if not metadata:
            raise ValueError('marker swap needs metadata')
        bit = self.marker_payload_bit()
        word = int.from_bytes(payload, 'little')
        marker = (word >> bit) & 0xff
        word = (word & ~(0xff << bit)) | (metadata[0] << bit)
        return word.to_bytes(len(payload), 'little'), bytes([marker]) + metadata[1:]

    def encode(self, payload: bytes, metadata: bytes, encoder=None) -> bytes:
        """Encode controller DMA buffers, with no implicit driver marker swap."""
        if len(payload) != self.payload_bytes or len(metadata) != self.metadata_bytes:
            raise ValueError('incorrect DMA buffer lengths')
        word = (1 << (self.page_bytes * 8)) - 1
        offset = 0
        for chunk in self.chunks:
            data = payload[offset:offset + chunk.data_bytes]
            message = (metadata if chunk.metadata_bytes else b'') + data
            bits = chunk.message_bytes * 8
            encoded = int.from_bytes(message, 'little')
            if chunk.strength:
                parity = (encoder or codec)(chunk.field, chunk.strength).encode(message.translate(REVERSE))
                encoded |= int.from_bytes(parity.translate(REVERSE), 'little') << bits
            width = bits + chunk.parity_bits
            mask = (1 << width) - 1
            word = (word & ~(mask << chunk.start_bit)) | ((encoded & mask) << chunk.start_bit)
            offset += chunk.data_bytes
        return word.to_bytes(self.page_bytes, 'little')

    def decode(self, physical: bytes, erase_threshold: int = 0) -> DecodedPage:
        """Decode actual interleaved codewords, not payload+OOB capture records.

        MODE's threshold counts zero bits in each complete codeword. Erased
        data is NOT filled with FF here: that is the guest driver's job.
        DEBUG1 aggregation/saturation follows our provisional functional model,
        pending a physical capture of multi-chunk and overflow cases.
        Uncorrectable blocks retain damaged bytes and do not hide their status.
        """
        if len(physical) != self.page_bytes:
            raise ValueError('incorrect physical page length')
        if not 0 <= erase_threshold <= 255:
            raise ValueError('erase threshold outside uint8')
        word = int.from_bytes(physical, 'little')
        payload, metadata, statuses = bytearray(), b'', []
        erased_zeros = 0
        for chunk in self.chunks:
            bits = chunk.message_bytes * 8
            codeword = word >> chunk.start_bit
            message = (codeword & ((1 << bits) - 1)).to_bytes(chunk.message_bytes, 'little')
            parity_word = (codeword >> bits) & ((1 << chunk.parity_bits) - 1)
            status = 0
            if chunk.strength:
                bch = codec(chunk.field, chunk.strength)
                parity = parity_word.to_bytes(bch.ecc_bytes, 'little')
                width = bits + chunk.parity_bits
                zeros = width - (codeword & ((1 << width) - 1)).bit_count()
                if zeros <= erase_threshold:
                    status = 0xff
                    erased_zeros += zeros
                else:
                    try:
                        corrected, _, errors = bch.decode(message.translate(REVERSE),
                                                          parity.translate(REVERSE))
                        message = corrected.translate(REVERSE)
                        status = len(errors)
                    except UncorrectableError:
                        status = 0xfe
            if chunk.metadata_bytes:
                metadata = message[:chunk.metadata_bytes]
            payload.extend(message[chunk.metadata_bytes:])
            statuses.append(status)
        return DecodedPage(bytes(payload), metadata, tuple(statuses), min(erased_zeros, 0x1ff))

    def auxiliary(self, result: DecodedPage) -> bytes:
        """Construct DMA auxiliary metadata, alignment padding and BCH status."""
        if len(result.metadata) != self.metadata_bytes or len(result.status) != len(self.chunks):
            raise ValueError('result belongs to another layout')
        return (result.metadata + b'\xff' * (self.status_offset - self.metadata_bytes)
                + bytes(result.status))
