"""Optional USD price sources."""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from .bitcoin import DataSourceError
from .config import Config


class PriceSource:
    async def price_usd(self) -> float:
        raise NotImplementedError


class ConfiguredPriceSource(PriceSource):
    def __init__(
        self,
        static_price: Optional[float],
        url: str,
        json_path: str,
        timeout: float,
        ttl: float,
    ):
        self.static_price = static_price
        self.url = url
        self.json_path = json_path
        self.timeout = timeout
        self.ttl = ttl
        self._value: Optional[float] = None
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()

    @staticmethod
    def _extract(document: Any, path: str) -> Any:
        value = document
        if not path:
            return value
        for component in path.split("."):
            if isinstance(value, list):
                value = value[int(component)]
            else:
                value = value[component]
        return value

    def _fetch(self) -> float:
        if not self.url:
            raise DataSourceError(
                "price is disabled; set BITCOIN_PRICE_USD or PRICE_URL/PRICE_JSON_PATH"
            )
        request = urllib.request.Request(
            self.url, headers={"Accept": "application/json", "User-Agent": "blockclock-backend/0.1"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                document = json.load(response)
            value = float(self._extract(document, self.json_path))
        except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
            raise DataSourceError(f"price fetch failed: {exc}") from exc
        if value <= 0:
            raise DataSourceError("price source returned a non-positive value")
        return value

    async def price_usd(self) -> float:
        if self.static_price is not None:
            if self.static_price <= 0:
                raise DataSourceError("BITCOIN_PRICE_USD must be positive")
            return self.static_price
        now = time.monotonic()
        if self._value is not None and now - self._loaded_at < self.ttl:
            return self._value
        async with self._lock:
            now = time.monotonic()
            if self._value is not None and now - self._loaded_at < self.ttl:
                return self._value
            self._value = await asyncio.to_thread(self._fetch)
            self._loaded_at = time.monotonic()
            return self._value


def build_price_source(config: Config) -> PriceSource:
    return ConfiguredPriceSource(
        config.static_price,
        config.price_url,
        config.price_json_path,
        config.request_timeout,
        config.cache_seconds,
    )
