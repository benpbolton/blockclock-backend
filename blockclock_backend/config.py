"""Environment-based configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

# name, url env, json-path env, default json path (used when URL is set)
_PRICE_VENUE_ENV = (
    ("coinbase", "PRICE_COINBASE_URL", "PRICE_COINBASE_JSON_PATH", "data.amount"),
    ("kraken", "PRICE_KRAKEN_URL", "PRICE_KRAKEN_JSON_PATH", "result.XXBTZUSD.c.0"),
    ("bitstamp", "PRICE_BITSTAMP_URL", "PRICE_BITSTAMP_JSON_PATH", "last"),
    ("gemini", "PRICE_GEMINI_URL", "PRICE_GEMINI_JSON_PATH", "last"),
)


def _optional_float(name: str) -> Optional[float]:
    value = os.getenv(name, "").strip()
    return float(value) if value else None


def _optional_port(name: str, default: str) -> Optional[int]:
    """Parse a TCP port. Empty or 0 disables the listener."""
    value = os.getenv(name, default).strip()
    if not value or value == "0":
        return None
    port = int(value)
    if port < 0:
        raise ValueError(f"{name} must be >= 0")
    return port


def _boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _price_venues_from_env() -> Tuple[Tuple[str, str, str], ...]:
    """Return (name, url, json_path) for each venue with a non-empty URL."""
    venues = []
    for name, url_env, path_env, default_path in _PRICE_VENUE_ENV:
        url = os.getenv(url_env, "").strip()
        if not url:
            continue
        path = os.getenv(path_env, default_path).strip() or default_path
        venues.append((name, url, path))
    return tuple(venues)


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    health_host: str
    health_port: Optional[int]
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
    price_cache_seconds: float
    price_venues: Tuple[Tuple[str, str, str], ...]
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
            health_port=_optional_port("HEALTH_PORT", "8080"),
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
            price_cache_seconds=float(os.getenv("PRICE_CACHE_SECONDS", "30")),
            price_venues=_price_venues_from_env(),
            mock_height=int(os.getenv("MOCK_BLOCK_HEIGHT", "840000")),
        )
