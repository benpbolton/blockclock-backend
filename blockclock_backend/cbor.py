"""Small, dependency-free CBOR codec for the Blockclock wire protocol.

The firmware uses only definite-length maps, arrays, strings, byte strings,
numbers, booleans and null.  Keeping this codec local makes the Docker image
small and avoids pulling a general-purpose web framework into a TCP daemon.
"""

from __future__ import annotations

import math
import struct
from typing import Any


class CBORError(ValueError):
    pass


def _head(major: int, value: int) -> bytes:
    if value < 0:
        raise CBORError("negative CBOR length")
    if value < 24:
        return bytes(((major << 5) | value,))
    if value < 1 << 8:
        return bytes(((major << 5) | 24, value))
    if value < 1 << 16:
        return bytes(((major << 5) | 25,)) + struct.pack(">H", value)
    if value < 1 << 32:
        return bytes(((major << 5) | 26,)) + struct.pack(">I", value)
    if value < 1 << 64:
        return bytes(((major << 5) | 27,)) + struct.pack(">Q", value)
    raise CBORError("integer is too large for CBOR")


def dumps(value: Any) -> bytes:
    if value is None:
        return b"\xf6"
    if value is False:
        return b"\xf4"
    if value is True:
        return b"\xf5"
    if isinstance(value, int):
        return _head(0, value) if value >= 0 else _head(1, -1 - value)
    if isinstance(value, float):
        if math.isnan(value):
            return b"\xfb" + struct.pack(">d", value)
        return b"\xfb" + struct.pack(">d", value)
    if isinstance(value, bytes):
        return _head(2, len(value)) + value
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        return _head(3, len(encoded)) + encoded
    if isinstance(value, (list, tuple)):
        return _head(4, len(value)) + b"".join(dumps(item) for item in value)
    if isinstance(value, dict):
        return _head(5, len(value)) + b"".join(
            dumps(key) + dumps(item) for key, item in value.items()
        )
    raise TypeError(f"unsupported CBOR value: {type(value).__name__}")


class _Decoder:
    def __init__(self, data: bytes):
        self.data = memoryview(data)
        self.position = 0

    def _take(self, count: int) -> memoryview:
        end = self.position + count
        if end > len(self.data):
            raise CBORError("truncated CBOR value")
        result = self.data[self.position:end]
        self.position = end
        return result

    def _argument(self, additional: int) -> int:
        if additional < 24:
            return additional
        sizes = {24: 1, 25: 2, 26: 4, 27: 8}
        if additional not in sizes:
            raise CBORError("indefinite or reserved CBOR value is unsupported")
        raw = self._take(sizes[additional])
        return int.from_bytes(raw, "big")

    def item(self) -> Any:
        initial = self._take(1)[0]
        major, additional = initial >> 5, initial & 31

        if major == 7:
            if additional == 20:
                return False
            if additional == 21:
                return True
            if additional in (22, 23):
                return None
            if additional == 25:
                return struct.unpack(">e", self._take(2))[0]
            if additional == 26:
                return struct.unpack(">f", self._take(4))[0]
            if additional == 27:
                return struct.unpack(">d", self._take(8))[0]
            raise CBORError(f"unsupported CBOR simple value {additional}")

        argument = self._argument(additional)
        if major == 0:
            return argument
        if major == 1:
            return -1 - argument
        if major == 2:
            return bytes(self._take(argument))
        if major == 3:
            try:
                return bytes(self._take(argument)).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CBORError("invalid UTF-8 CBOR string") from exc
        if major == 4:
            return [self.item() for _ in range(argument)]
        if major == 5:
            result = {}
            for _ in range(argument):
                key = self.item()
                result[key] = self.item()
            return result
        if major == 6:
            # Tags are not emitted by the Mini, but transparently accepting one
            # makes the decoder tolerant of standard CBOR encoders.
            return self.item()
        raise CBORError(f"unsupported CBOR major type {major}")


def loads(data: bytes) -> Any:
    decoder = _Decoder(data)
    result = decoder.item()
    if decoder.position != len(decoder.data):
        raise CBORError("trailing data after CBOR value")
    return result
