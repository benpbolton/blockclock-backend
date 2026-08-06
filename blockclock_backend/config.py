"""Environment-based configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _optional_float(name: str) -> Optional[float]:
    value = os.getenv(name, "").strip()
    return float(value) if value else None


def _boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    health_host: str
    health_port: int
    log_level: str
    bitcoin_source: str
    cache_seconds: float
    rpc_url: str
    rpc_user: str
    rpc_password: str
    rpc_cookie_file: str
    electrum_host: str
    electrum_port: int
    electrum_tls: bool
    request_timeout: float
    static_price: Optional[float]
    price_url: str
    price_json_path: str
    mock_height: int

    @classmethod
    def from_env(cls) -> "Config":
        source = os.getenv("BITCOIN_SOURCE", "rpc").strip().lower()
        if source not in {"rpc", "electrum", "mock"}:
            raise ValueError("BITCOIN_SOURCE must be rpc, electrum, or mock")
        return cls(
            host=os.getenv("BLOCKCLOCK_HOST", "0.0.0.0"),
            port=int(os.getenv("BLOCKCLOCK_PORT", "21021")),
            health_host=os.getenv("HEALTH_HOST", "0.0.0.0"),
            health_port=int(os.getenv("HEALTH_PORT", "8080")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            bitcoin_source=source,
            cache_seconds=float(os.getenv("CACHE_SECONDS", "15")),
            rpc_url=os.getenv("BITCOIN_RPC_URL", "http://127.0.0.1:8332"),
            rpc_user=os.getenv("BITCOIN_RPC_USER", ""),
            rpc_password=os.getenv("BITCOIN_RPC_PASSWORD", ""),
            rpc_cookie_file=os.getenv("BITCOIN_RPC_COOKIE_FILE", ""),
            electrum_host=os.getenv("ELECTRUM_HOST", "127.0.0.1"),
            electrum_port=int(os.getenv("ELECTRUM_PORT", "50001")),
            electrum_tls=_boolean("ELECTRUM_TLS"),
            request_timeout=float(os.getenv("REQUEST_TIMEOUT", "8")),
            static_price=_optional_float("BITCOIN_PRICE_USD"),
            price_url=os.getenv("PRICE_URL", "").strip(),
            price_json_path=os.getenv("PRICE_JSON_PATH", "").strip(),
            mock_height=int(os.getenv("MOCK_BLOCK_HEIGHT", "840000")),
        )
