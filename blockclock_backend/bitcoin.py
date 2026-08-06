"""Bitcoin Core and Electrum data sources."""

from __future__ import annotations

import asyncio
import base64
import json
import socket
import ssl
import struct
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .config import Config


class DataSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class BitcoinSnapshot:
    height: int
    difficulty: Optional[float] = None
    block_time: Optional[int] = None
    merkle_root: Optional[str] = None
    nonce: Optional[int] = None
    previous_hash: Optional[str] = None
    utxo_count: Optional[int] = None
    mempool_transactions: Optional[int] = None
    mempool_vsize: Optional[int] = None
    network_hashrate: Optional[float] = None


class BitcoinSource:
    async def snapshot(self) -> BitcoinSnapshot:
        raise NotImplementedError


class CachedBitcoinSource(BitcoinSource):
    def __init__(self, source: BitcoinSource, ttl: float):
        self.source = source
        self.ttl = ttl
        self._value: Optional[BitcoinSnapshot] = None
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()

    async def snapshot(self) -> BitcoinSnapshot:
        now = time.monotonic()
        if self._value is not None and now - self._loaded_at < self.ttl:
            return self._value
        async with self._lock:
            now = time.monotonic()
            if self._value is not None and now - self._loaded_at < self.ttl:
                return self._value
            self._value = await self.source.snapshot()
            self._loaded_at = time.monotonic()
            return self._value


class BitcoinRPCSource(BitcoinSource):
    def __init__(
        self,
        url: str,
        user: str,
        password: str,
        cookie_file: str,
        timeout: float,
    ):
        self.url = url
        self.user = user
        self.password = password
        self.cookie_file = cookie_file
        self.timeout = timeout

    def _credentials(self) -> str:
        if self.cookie_file:
            try:
                return Path(self.cookie_file).read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise DataSourceError(f"cannot read Bitcoin RPC cookie: {exc}") from exc
        if self.user or self.password:
            return f"{self.user}:{self.password}"
        return ""

    def _call(self, method: str, params: Optional[list[Any]] = None) -> Any:
        body = json.dumps(
            {"jsonrpc": "2.0", "id": "blockclock", "method": method, "params": params or []}
        ).encode()
        headers = {"Content-Type": "application/json", "User-Agent": "blockclock-backend/0.1"}
        credentials = self._credentials()
        if credentials:
            headers["Authorization"] = "Basic " + base64.b64encode(credentials.encode()).decode()
        request = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                decoded = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise DataSourceError(f"Bitcoin RPC {method} failed: {exc}") from exc
        if decoded.get("error"):
            raise DataSourceError(f"Bitcoin RPC {method}: {decoded['error']}")
        return decoded.get("result")

    def _snapshot(self) -> BitcoinSnapshot:
        chain = self._call("getblockchaininfo")
        mempool = self._call("getmempoolinfo")
        header = self._call("getblockheader", [chain["bestblockhash"]])
        try:
            hashrate = float(self._call("getnetworkhashps"))
        except DataSourceError:
            hashrate = None
        return BitcoinSnapshot(
            height=int(chain["blocks"]),
            difficulty=float(chain.get("difficulty", header.get("difficulty", 0))) or None,
            block_time=int(header["time"]),
            merkle_root=header.get("merkleroot"),
            nonce=int(header["nonce"]),
            previous_hash=header.get("previousblockhash"),
            mempool_transactions=int(mempool.get("size", 0)),
            mempool_vsize=int(mempool.get("bytes", mempool.get("vsize", 0))),
            network_hashrate=hashrate,
        )

    async def snapshot(self) -> BitcoinSnapshot:
        return await asyncio.to_thread(self._snapshot)


def _difficulty_from_bits(bits: int) -> float:
    exponent = bits >> 24
    mantissa = bits & 0xFFFFFF
    target = mantissa * (1 << (8 * (exponent - 3)))
    difficulty_one_target = 0xFFFF * (1 << (8 * (0x1D - 3)))
    return difficulty_one_target / target


def _parse_header(height: int, header_hex: str) -> BitcoinSnapshot:
    try:
        raw = bytes.fromhex(header_hex)
    except ValueError as exc:
        raise DataSourceError("Electrum returned a non-hex block header") from exc
    if len(raw) < 80:
        raise DataSourceError("Electrum returned a short block header")
    return BitcoinSnapshot(
        height=height,
        previous_hash=raw[4:36][::-1].hex(),
        merkle_root=raw[36:68][::-1].hex(),
        block_time=struct.unpack_from("<I", raw, 68)[0],
        difficulty=_difficulty_from_bits(struct.unpack_from("<I", raw, 72)[0]),
        nonce=struct.unpack_from("<I", raw, 76)[0],
    )


class ElectrumSource(BitcoinSource):
    def __init__(self, host: str, port: int, use_tls: bool, timeout: float):
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.timeout = timeout

    def _snapshot(self) -> BitcoinSnapshot:
        request = json.dumps(
            {"id": 1, "method": "blockchain.headers.subscribe", "params": []},
            separators=(",", ":"),
        ).encode() + b"\n"
        try:
            connection = socket.create_connection((self.host, self.port), timeout=self.timeout)
            if self.use_tls:
                connection = ssl.create_default_context().wrap_socket(
                    connection, server_hostname=self.host
                )
            with connection:
                connection.sendall(request)
                stream = connection.makefile("rb")
                raw = stream.readline(1024 * 1024)
        except OSError as exc:
            raise DataSourceError(f"Electrum connection failed: {exc}") from exc
        if not raw:
            raise DataSourceError("Electrum closed the connection without a response")
        try:
            response = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DataSourceError("Electrum returned invalid JSON") from exc
        if response.get("error"):
            raise DataSourceError(f"Electrum error: {response['error']}")
        result = response.get("result") or {}
        return _parse_header(int(result["height"]), result["hex"])

    async def snapshot(self) -> BitcoinSnapshot:
        return await asyncio.to_thread(self._snapshot)


class MockBitcoinSource(BitcoinSource):
    def __init__(self, height: int):
        self.height = height

    async def snapshot(self) -> BitcoinSnapshot:
        return BitcoinSnapshot(
            height=self.height,
            difficulty=83_000_000_000_000.0,
            block_time=int(time.time()) - 300,
            merkle_root="00" * 32,
            nonce=0,
            previous_hash="00" * 32,
            mempool_transactions=0,
            mempool_vsize=0,
        )


def build_bitcoin_source(config: Config) -> BitcoinSource:
    if config.bitcoin_source == "rpc":
        source: BitcoinSource = BitcoinRPCSource(
            config.rpc_url,
            config.rpc_user,
            config.rpc_password,
            config.rpc_cookie_file,
            config.request_timeout,
        )
    elif config.bitcoin_source == "electrum":
        source = ElectrumSource(
            config.electrum_host,
            config.electrum_port,
            config.electrum_tls,
            config.request_timeout,
        )
    else:
        source = MockBitcoinSource(config.mock_height)
    return CachedBitcoinSource(source, config.cache_seconds)

