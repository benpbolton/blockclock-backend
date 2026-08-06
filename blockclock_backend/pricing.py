"""BTC/USD price sources (venue average + optional overrides)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .bitcoin import DataSourceError
from .config import Config

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Venue:
    name: str
    url: str
    json_path: str


class PriceSource:
    async def price_usd(self) -> float:
        raise NotImplementedError

    async def coinbase_spot_usd(self) -> float:
        raise NotImplementedError


class ConfiguredPriceSource(PriceSource):
    def __init__(
        self,
        static_price: Optional[float],
        url: str,
        json_path: str,
        timeout: float,
        ttl: float,
        venues: Tuple[Venue, ...] = (),
    ):
        self.static_price = static_price
        self.url = url
        self.json_path = json_path
        self.timeout = timeout
        self.ttl = ttl
        self.venues = venues
        self._prices: Dict[str, float] = {}
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()
        self._down: set[str] = set()
        self._all_failed_logged = False

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

    def _http_json(self, url: str) -> Any:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "blockclock-backend/0.1"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def _read_venue(self, venue: Venue) -> float:
        document = self._http_json(venue.url)
        value = float(self._extract(document, venue.json_path))
        if value <= 0:
            raise DataSourceError(f"{venue.name} returned a non-positive value")
        return value

    def _read_custom(self) -> float:
        if not self.url:
            raise DataSourceError("PRICE_URL is empty")
        try:
            document = self._http_json(self.url)
            value = float(self._extract(document, self.json_path))
        except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
            raise DataSourceError(f"price fetch failed: {exc}") from exc
        if value <= 0:
            raise DataSourceError("price source returned a non-positive value")
        return value

    def _mark_ok(self, name: str) -> None:
        if name in self._down:
            log.info("price source %s recovered", name)
            self._down.discard(name)

    def _mark_fail(self, name: str, exc: BaseException) -> None:
        if name not in self._down:
            log.warning("price source %s failed: %s", name, exc)
            self._down.add(name)

    async def _fetch_venue(self, venue: Venue) -> Optional[Tuple[str, float]]:
        try:
            value = await asyncio.to_thread(self._read_venue, venue)
        except (
            OSError,
            urllib.error.URLError,
            json.JSONDecodeError,
            KeyError,
            IndexError,
            ValueError,
            DataSourceError,
        ) as exc:
            self._mark_fail(venue.name, exc)
            return None
        self._mark_ok(venue.name)
        return venue.name, value

    async def _refresh_venues(self) -> None:
        if not self.venues:
            raise DataSourceError(
                "no price venues configured; set PRICE_*_URL or BITCOIN_PRICE_USD"
            )
        results = await asyncio.gather(*(self._fetch_venue(venue) for venue in self.venues))
        got = {item[0]: item[1] for item in results if item is not None}
        now = time.monotonic()
        if got:
            self._prices = got
            self._loaded_at = now
            self._all_failed_logged = False
            return
        if self._prices:
            self._loaded_at = now
            if not self._all_failed_logged:
                log.warning("all price sources failed; serving cached prices")
                self._all_failed_logged = True
            return
        self._loaded_at = now
        if not self._all_failed_logged:
            log.warning("all price sources failed")
            self._all_failed_logged = True
        raise DataSourceError("all price sources failed")

    async def _ensure_venues(self) -> Dict[str, float]:
        now = time.monotonic()
        if self._prices and now - self._loaded_at < self.ttl:
            return self._prices
        async with self._lock:
            now = time.monotonic()
            if self._prices and now - self._loaded_at < self.ttl:
                return self._prices
            await self._refresh_venues()
            return self._prices

    async def price_usd(self) -> float:
        if self.static_price is not None:
            if self.static_price <= 0:
                raise DataSourceError("BITCOIN_PRICE_USD must be positive")
            return self.static_price
        if self.url:
            now = time.monotonic()
            if self._prices.get("custom") is not None and now - self._loaded_at < self.ttl:
                return self._prices["custom"]
            async with self._lock:
                now = time.monotonic()
                cached = self._prices.get("custom")
                if cached is not None and now - self._loaded_at < self.ttl:
                    return cached
                try:
                    value = await asyncio.to_thread(self._read_custom)
                except DataSourceError as exc:
                    self._mark_fail("custom", exc)
                    if cached is not None:
                        self._loaded_at = time.monotonic()
                        return cached
                    raise
                self._mark_ok("custom")
                self._prices = {"custom": value}
                self._loaded_at = time.monotonic()
                return value
        prices = await self._ensure_venues()
        if not prices:
            raise DataSourceError("no price sources available")
        return sum(prices.values()) / len(prices)

    async def coinbase_spot_usd(self) -> float:
        if self.static_price is not None:
            if self.static_price <= 0:
                raise DataSourceError("BITCOIN_PRICE_USD must be positive")
            return self.static_price
        prices = await self._ensure_venues()
        value = prices.get("coinbase")
        if value is None:
            raise DataSourceError(
                "coinbase price is unavailable; set PRICE_COINBASE_URL or BITCOIN_PRICE_USD"
            )
        return value


def build_price_source(config: Config) -> PriceSource:
    venues = tuple(Venue(name, url, path) for name, url, path in config.price_venues)
    return ConfiguredPriceSource(
        config.static_price,
        config.price_url,
        config.price_json_path,
        config.request_timeout,
        config.price_cache_seconds,
        venues,
    )
