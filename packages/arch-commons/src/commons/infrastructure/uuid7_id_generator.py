from __future__ import annotations

import os
import time
import uuid


class Uuid7IdGenerator:
    """UUIDv7 identifiers (spec Section 0: identifiers are application-generated,
    UUIDv7). Python's stdlib ``uuid`` module has no ``uuid7()`` before 3.14, so
    this implements RFC 9562's layout directly: a 48-bit millisecond timestamp,
    a 4-bit version, a 2-bit variant, and 74 random bits.
    """

    def new_id(self) -> str:
        timestamp_ms = int(time.time() * 1000)
        rand = os.urandom(10)
        time_bytes = timestamp_ms.to_bytes(6, "big")
        version_and_rand_a = ((0x7 << 12) | (int.from_bytes(rand[0:2], "big") & 0x0FFF)).to_bytes(
            2, "big"
        )
        variant_and_rand_b = bytes([0x80 | (rand[2] & 0x3F), *rand[3:10]])
        raw = time_bytes + version_and_rand_a + variant_and_rand_b
        return str(uuid.UUID(bytes=raw))
