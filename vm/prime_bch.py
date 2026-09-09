"""Binary BCH reference codec for validating the Prime NAND model.

This computes codewords, syndromes and error locations; it has no access to
the injected error positions. It is not yet the GPMI wire-layout adapter.
Bytes are MSB first, with parity bits left-aligned in the last byte, matching
the Linux/U-Boot generic BCH codec's default (non-bit-swapped) convention.
"""


class UncorrectableError(ValueError):
    pass


class BCH:
    def __init__(self, m: int, strength: int, primitive: int):
        if not 2 <= m <= 15 or not 1 <= strength < (1 << m) // 2:
            raise ValueError("invalid BCH field/strength")
        if primitive.bit_length() != m + 1:
            raise ValueError("primitive polynomial has wrong degree")
        self.m, self.strength, self.n = m, strength, (1 << m) - 1
        self.exp = [0] * (2 * self.n)
        self.log = [-1] * (self.n + 1)
        value = 1
        for i in range(self.n):
            if self.log[value] != -1:
                raise ValueError("polynomial is not primitive")
            self.exp[i], self.log[value] = value, i
            value <<= 1
            if value & (1 << m):
                value ^= primitive
        if value != 1:
            raise ValueError("polynomial does not generate the field")
        self.exp[self.n:] = self.exp[:self.n]

        roots = set()
        for root in range(1, 2 * strength + 1):
            exponent = root
            while exponent not in roots:
                roots.add(exponent)
                exponent = (2 * exponent) % self.n
        polynomial = [1]  # ascending coefficients in GF(2^m)
        for exponent in sorted(roots):
            expanded = [0] * (len(polynomial) + 1)
            for i, coefficient in enumerate(polynomial):
                expanded[i] ^= self.mul(coefficient, self.exp[exponent])
                expanded[i + 1] ^= coefficient
            polynomial = expanded
        if any(coefficient not in (0, 1) for coefficient in polynomial):
            raise ValueError("generator is not binary")
        self.generator = sum(coefficient << i for i, coefficient in enumerate(polynomial))
        self.ecc_bits = self.generator.bit_length() - 1
        self.ecc_bytes = (self.ecc_bits + 7) // 8
        self.padding = 8 * self.ecc_bytes - self.ecc_bits

    def mul(self, a: int, b: int) -> int:
        return self.exp[self.log[a] + self.log[b]] if a and b else 0

    def div(self, a: int, b: int) -> int:
        if not b:
            raise ZeroDivisionError("GF division by zero")
        return self.exp[(self.log[a] - self.log[b]) % self.n] if a else 0

    def _check_length(self, length: int) -> None:
        if length < 0 or 8 * length + self.ecc_bits > self.n:
            raise ValueError("shortened codeword exceeds field capacity")

    def encode(self, data: bytes) -> bytes:
        self._check_length(len(data))
        remainder = int.from_bytes(data, "big") << self.ecc_bits
        while remainder.bit_length() > self.ecc_bits:
            remainder ^= self.generator << (remainder.bit_length() - self.ecc_bits - 1)
        return (remainder << self.padding).to_bytes(self.ecc_bytes, "big")

    def _syndromes(self, word: int) -> list[int]:
        result = [0] * (2 * self.strength)
        while word:
            bit = word & -word
            position = bit.bit_length() - 1
            for index in range(len(result)):
                result[index] ^= self.exp[((index + 1) * position) % self.n]
            word ^= bit
        return result

    def decode(self, data: bytes, parity: bytes) -> tuple[bytes, bytes, tuple[int, ...]]:
        """Return corrected data/parity and MSB-first wire bit positions.

        As for any bounded-distance BCH decoder, errors beyond the designed
        strength can be undetected or miscorrect to another valid codeword.
        No assertion of universal t+1-error detection is made here.
        """
        self._check_length(len(data))
        if len(parity) != self.ecc_bytes:
            raise ValueError("wrong parity length")
        bits = len(data) * 8 + self.ecc_bits
        word = (int.from_bytes(data, "big") << self.ecc_bits) | (
            int.from_bytes(parity, "big") >> self.padding)
        syndrome = self._syndromes(word)
        if not any(syndrome):
            return data, parity, ()

        # Berlekamp-Massey over GF(2^m), ascending locator coefficients.
        locator, previous = [1], [1]
        degree, distance, last = 0, 1, 1
        for step in range(2 * self.strength):
            discrepancy = syndrome[step]
            for i in range(1, degree + 1):
                discrepancy ^= self.mul(locator[i] if i < len(locator) else 0,
                                        syndrome[step - i])
            if not discrepancy:
                distance += 1
                continue
            saved = locator[:]
            scale = self.div(discrepancy, last)
            locator += [0] * max(0, len(previous) + distance - len(locator))
            for i, coefficient in enumerate(previous):
                locator[i + distance] ^= self.mul(scale, coefficient)
            if 2 * degree <= step:
                degree = step + 1 - degree
                previous, last, distance = saved, discrepancy, 1
            else:
                distance += 1
        if degree > self.strength:
            raise UncorrectableError("locator degree exceeds BCH strength")

        # Chien search only across transmitted (shortened) positions.
        errors = []
        for position in range(bits):
            x = self.exp[(-position) % self.n]
            value = 0
            for coefficient in reversed(locator):
                value = self.mul(value, x) ^ coefficient
            if value == 0:
                errors.append(position)
        if len(errors) != degree:
            raise UncorrectableError("locator roots do not fit the transmitted word")
        for position in errors:
            word ^= 1 << position
        if any(self._syndromes(word)):
            raise UncorrectableError("corrected word still has a syndrome")
        corrected_data = (word >> self.ecc_bits).to_bytes(len(data), "big")
        corrected_parity = ((word & ((1 << self.ecc_bits) - 1)) << self.padding).to_bytes(
            self.ecc_bytes, "big")
        return corrected_data, corrected_parity, tuple(sorted(bits - 1 - p for p in errors))
