"""Blockclock Mini TCP framing."""

from __future__ import annotations

import asyncio
import struct
from typing import Any

from . import cbor

MAGIC = 0xBC
HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 256 * 1024


class ProtocolError(ValueError):
    pass


def encode_frame(message: Any) -> bytes:
    payload = cbor.dumps(message)
    if not 0 < len(payload) <= MAX_MESSAGE_SIZE:
        raise ProtocolError("invalid Blockclock message size")
    header = struct.pack(">I", (MAGIC << 24) | len(payload))
    return header + payload


def decode_frame(frame: bytes) -> Any:
    if len(frame) < HEADER_SIZE:
        raise ProtocolError("short Blockclock frame")
    word = struct.unpack(">I", frame[:HEADER_SIZE])[0]
    if word >> 24 != MAGIC:
        raise ProtocolError("bad Blockclock frame magic")
    size = word & 0xFFFFFF
    if size != len(frame) - HEADER_SIZE:
        raise ProtocolError("Blockclock frame length mismatch")
    return cbor.loads(frame[HEADER_SIZE:])


async def read_message(reader: asyncio.StreamReader) -> Any:
    header = await reader.readexactly(HEADER_SIZE)
    word = struct.unpack(">I", header)[0]
    if word >> 24 != MAGIC:
        raise ProtocolError("bad Blockclock frame magic")
    size = word & 0xFFFFFF
    if not 0 < size <= MAX_MESSAGE_SIZE:
        raise ProtocolError("invalid Blockclock frame length")
    return cbor.loads(await reader.readexactly(size))


async def write_message(writer: asyncio.StreamWriter, message: Any) -> None:
    writer.write(encode_frame(message))
    await writer.drain()

